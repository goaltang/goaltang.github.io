#!/usr/bin/env bash
# 从本机原片做两样东西，仓库里不放任何 mp4：
#   out/web/<id>.mp4   预览片：H.264 High + faststart，短边 ≤720，视频码率封顶 1.2M 且不超过原片（平均约 1 Mbps），静音片不出音轨、有声片 AAC 96k → 上传到 Release「web」，部署时下载进站点 films/
#   out/web/reel.mp4   首屏混剪：每支截 2.4 秒，静音，1280×720 → 同上
#   out/web/<id>-loop.mp4 短循环：3.5 秒、短边 ≤480、无音轨，约 300KB，给首屏胶片墙和悬停/点按预览用 → 同上
#   out/full/<id>.mp4  原画质完整版（原片改名，不重压）→ 上传到 Release「films」，给「下载完整版」按钮用
#
# 用法：
#   scripts/make-previews.sh                  做全部预览片、短循环、混剪和完整版
#   scripts/make-previews.sh whale star-cc    只做这几个 id 的预览片、短循环和完整版
#   scripts/make-previews.sh --reel           只重做首屏混剪
#   scripts/make-previews.sh --loops          只重做短循环（从 films/ 或 out/web/ 已有的预览片切）
#   scripts/make-previews.sh --local [id…]    只做预览片、短循环和混剪，直接放进站点 films/（被 .gitignore），本地预览用
#
# 环境变量：SRC_ROOT（原片根目录，默认 /mnt/d）；预览片可用 CRF（默认 20）、MAXKBPS（默认 1200）覆盖
# 预览片已存在且比原片新时跳过；ffmpeg 失败时继续做下一支，最后以 1 退出。
#
# 上传（由 CLI管家 执行，本脚本不上传）：
#   gh release upload web   out/web/*.mp4  --clobber --repo goaltang/goaltang.github.io
#   gh release upload films out/full/*.mp4 --clobber --repo goaltang/goaltang.github.io
set -euo pipefail
cd "$(dirname "$0")/.."

SRC_ROOT=${SRC_ROOT:-/mnt/d}
# 预览片编码参数：CRF 20，maxrate = min(MAXKBPS, 源码率)、bufsize = 2×maxrate → 平均约 1 Mbps，720p 封顶
CRF=${CRF:-20}
MAXKBPS=${MAXKBPS:-1200}   # 视频码率封顶，约 1 Mbps；音频另算
WEB=out/web
FULL=out/full
only_reel=0
only_loops=0
local_mode=0
ids=()
for arg in "$@"; do
  case $arg in
    --reel) only_reel=1 ;;
    --loops) only_loops=1 ;;
    --local) local_mode=1 ;;
    -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
    *) ids+=("$arg") ;;
  esac
done
if [ "$local_mode" = 1 ]; then WEB=films; FULL=; fi
mkdir -p "$WEB"
[ -n "$FULL" ] && mkdir -p "$FULL"

fail=0
declare -A SRC START LOOP
order=()
while IFS=$'\t' read -r id path start loop; do
  [[ -z "$id" || "$id" == \#* ]] && continue
  SRC[$id]="$SRC_ROOT/$path"
  START[$id]=${start:-}
  LOOP[$id]=${loop:-}
  order+=("$id")
done < scripts/sources.tsv

for id in "${ids[@]}"; do
  [ -n "${SRC[$id]:-}" ] || { echo "✗ $id 不在 scripts/sources.tsv 里" >&2; exit 1; }
done
[ ${#ids[@]} -gt 0 ] || ids=("${order[@]}")

probe() { ffprobe -v error -select_streams v:0 -show_entries "$1" -of csv=p=0 "$2" | head -n1 | tr -d ',\r'; }

# 预览片：短边缩到 720，H.264 High，CRF 20，maxrate 封顶 min(MAXKBPS, 源视频码率)（约 1 Mbps），
# 窄带（国内拉 GitHub Pages 只有 ~400KB/s）也能连续播；无音轨的片子不出音轨，有声的 AAC 96k。
# 封顶跟着源码率走，所以重跑一遍不会把已经压过的片子越压越大。
webcut() {   # webcut <id>
  local id=$1 src=${SRC[$1]} out=$WEB/$1.mp4
  [ -f "$src" ] || { echo "✗ $id: 找不到原片 $src" >&2; fail=1; return; }
  if [ -f "$out" ] && [ ! "$src" -nt "$out" ]; then echo "  $id 已是最新，跳过"; return; fi
  local srate cap
  srate=$(probe stream=bit_rate "$src")
  cap=$MAXKBPS
  if [ -n "$srate" ] && [ "$srate" != "N/A" ] && [ $((srate / 1000)) -lt "$cap" ]; then cap=$((srate / 1000)); fi
  if ffmpeg -v error -y -i "$src" -map 0:v:0 -map '0:a:0?' \
      -vf "scale='if(gte(iw,ih),-2,min(720,iw))':'if(gte(iw,ih),min(720,ih),-2)':flags=lanczos,format=yuv420p" \
      -c:v libx264 -profile:v high -level 4.0 -preset slow -crf "$CRF" \
      -maxrate "${cap}k" -bufsize "$((cap * 2))k" \
      -c:a aac -b:a 96k -ac 2 -movflags +faststart -tag:v avc1 -f mp4 "$out.part"; then
    mv "$out.part" "$out"; echo "  $id  $(du -h "$out" | cut -f1)  (封顶 ${cap}k)"
  else
    rm -f "$out.part"; echo "✗ $id: ffmpeg 压不出预览片（$src）" >&2; fail=1
  fi
}

# 短循环：3.5 秒、短边 ≤480、无音轨、faststart，约 300KB。
# 首屏胶片墙、悬停/点按预览都用它，别再往首屏塞整支预览片。
# 源片优先用刚压好的预览片（同一时间轴，帧和封面一致），没有就退回原片。
loopcut() {  # loopcut <id>
  local id=$1 src=$WEB/$1.mp4 out=$WEB/$1-loop.mp4 start
  [ -f "$src" ] || src=${SRC[$1]}
  [ -f "$src" ] || { echo "✗ $id: 找不到预览片 $WEB/$1.mp4，也没找到原片" >&2; fail=1; return; }
  if [ -f "$out" ] && [ ! "$src" -nt "$out" ]; then echo "  $id 短循环已是最新，跳过"; return; fi
  start=${LOOP[$id]:-}
  if [ -z "$start" ]; then
    # 默认从 2 秒（或 12% 处）开始，避开片头的黑场/淡入
    start=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$src" |
      awk '{ s = $1 * 0.12; if (s > 2) s = 2; if (s < 0.4) s = 0.4; if ($1 < 4) s = 0; printf "%.2f", s }')
  fi
  if ffmpeg -v error -y -ss "$start" -t 3.5 -i "$src" -map 0:v:0 \
      -vf "scale='if(gte(iw,ih),-2,min(480,iw))':'if(gte(iw,ih),min(480,ih),-2)':flags=lanczos,format=yuv420p" \
      -an -c:v libx264 -profile:v high -preset slow -b:v 700k -maxrate 900k -bufsize 1400k \
      -movflags +faststart -tag:v avc1 -f mp4 "$out.part"; then
    mv "$out.part" "$out"; echo "  $id  $(du -h "$out" | cut -f1)  短循环 ${start}s 起"
  else
    rm -f "$out.part"; echo "✗ $id: ffmpeg 压不出短循环（$src）" >&2; fail=1
  fi
}

# 完整版：原片原样复制，只改名
fullcopy() {
  local id=$1 src=${SRC[$1]} out=$FULL/$1.mp4
  [ -f "$src" ] || return 0
  if [ -f "$out" ] && [ ! "$src" -nt "$out" ]; then return; fi
  cp "$src" "$out" && echo "  $id 完整版 $(du -h "$out" | cut -f1)"
}

# 混剪：横屏铺满裁成 16:9；竖屏放中间，两边垫一层模糊放大的自己
reel() {
  local inputs=() filters="" n=0 seg=2.4
  for id in "${order[@]}"; do
    local start=${START[$id]} src=${SRC[$id]}
    [ -n "$start" ] && [ -f "$src" ] || continue
    local w h
    w=$(probe stream=width "$src"); h=$(probe stream=height "$src")
    inputs+=(-ss "$start" -t "$seg" -i "$src")
    if [ "$w" -ge "$h" ]; then
      filters+="[$n:v]scale=1280:720:force_original_aspect_ratio=increase:flags=lanczos,crop=1280:720,setsar=1,fps=30[v$n];"
    else
      filters+="[$n:v]split[a$n][b$n];[a$n]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,boxblur=24:2,eq=brightness=-0.12[bg$n];[b$n]scale=-2:720:flags=lanczos[fg$n];[bg$n][fg$n]overlay=(W-w)/2:0,setsar=1,fps=30[v$n];"
    fi
    n=$((n + 1))
  done
  [ "$n" -gt 0 ] || { echo "✗ 混剪：sources.tsv 里没有一支填了起点" >&2; fail=1; return; }
  local chain=""
  for ((i = 0; i < n; i++)); do chain+="[v$i]"; done
  if ffmpeg -v error -y "${inputs[@]}" -filter_complex "${filters}${chain}concat=n=$n:v=1:a=0,format=yuv420p[out]" -map "[out]" \
      -c:v libx264 -profile:v high -level 4.0 -preset slow -crf 27 -an -movflags +faststart -tag:v avc1 "$WEB/reel.mp4.part.mp4"; then
    mv "$WEB/reel.mp4.part.mp4" "$WEB/reel.mp4"; echo "  reel  $n 段  $(du -h "$WEB/reel.mp4" | cut -f1)"
  else
    rm -f "$WEB/reel.mp4.part.mp4"; echo "✗ 混剪：ffmpeg 失败" >&2; fail=1
  fi
}

if [ "$only_loops" = 1 ]; then
  echo "短循环 → $WEB/"
  for id in "${ids[@]}"; do loopcut "$id"; done
elif [ "$only_reel" = 0 ]; then
  echo "预览片 → $WEB/"
  for id in "${ids[@]}"; do webcut "$id"; done
  echo "短循环 → $WEB/"
  for id in "${ids[@]}"; do loopcut "$id"; done
  if [ -n "$FULL" ]; then
    echo "完整版 → $FULL/"
    for id in "${ids[@]}"; do fullcopy "$id"; done
  fi
fi
if [ "$only_reel" = 1 ] || [ $# -eq 0 ] || { [ "$local_mode" = 1 ] && [ ${#ids[@]} -eq ${#order[@]} ]; }; then
  echo "首屏混剪 → $WEB/reel.mp4"
  reel
fi
du -sh "$WEB"
[ "$fail" = 0 ] || exit 1
