#!/usr/bin/env python3
"""构建站点：作品集首页是手写的静态文件，这里只把文章编译成页面，并在公开构建时把整站拷进独立目录。"""
import argparse
import html
import json
import pathlib
import re
import shutil

import yaml

ROOT = pathlib.Path(__file__).resolve().parent
SITE = "TaopleOne"
# 分享卡片和 canonical 用的绝对地址；works.json 的 site.url 优先
DEFAULT_SITE_URL = "https://goaltang.github.io/"
# 公开构建拷进站点的文件；视频不在仓库里，部署时由 workflow 从 Release「web」下载到 films/
SITE_FILES = ["index.html", "work.html", "data/works.json"]
SITE_DIRS = ["assets", "covers", "figures"]


# ---------------- Markdown（够用就好） ----------------

def inline(s: str) -> str:
    s = html.escape(s)
    stash = []

    def keep(m):
        stash.append("<code>%s</code>" % m.group(1))
        return "\x00%d\x00" % (len(stash) - 1)

    s = re.sub(r"`([^`]+)`", keep, s)
    s = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1">', s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2" target="_blank" rel="noreferrer">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", s)
    return re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], s)


def md_to_html(text: str) -> str:
    out, para, buf = [], [], []
    mode = None  # None | 'ul' | 'ol' | 'quote' | 'code'

    def flush_para():
        if para:
            out.append("<p>%s</p>" % inline(" ".join(para)))
            para.clear()

    def flush_block():
        nonlocal mode
        if mode == "ul":
            out.append("<ul>" + "".join("<li>%s</li>" % inline(l) for l in buf) + "</ul>")
        elif mode == "ol":
            out.append("<ol>" + "".join("<li>%s</li>" % inline(l) for l in buf) + "</ol>")
        elif mode == "quote":
            out.append("<blockquote>" + "".join("<p>%s</p>" % inline(l) for l in buf) + "</blockquote>")
        elif mode == "code":
            out.append("<pre><code>%s</code></pre>" % html.escape("\n".join(buf)))
        buf.clear()
        mode = None

    for line in text.splitlines():
        if line.startswith("```"):
            if mode == "code":
                flush_block()
            else:
                flush_para(); flush_block(); mode = "code"
            continue
        if mode == "code":
            buf.append(line)
            continue
        if not line.strip():
            flush_para(); flush_block()
            continue
        m = re.match(r"^(#{1,3})\s+(.*)", line)
        if m:
            flush_para(); flush_block()
            lvl = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (lvl, inline(m.group(2)), lvl))
            continue
        if re.match(r"^(-{3,}|\*{3,})$", line.strip()):
            flush_para(); flush_block()
            out.append("<hr>")
            continue
        m = re.match(r"^[-*]\s+(.*)", line)
        if m:
            flush_para()
            if mode != "ul":
                flush_block(); mode = "ul"
            buf.append(m.group(1))
            continue
        m = re.match(r"^\d+\.\s+(.*)", line)
        if m:
            flush_para()
            if mode != "ol":
                flush_block(); mode = "ol"
            buf.append(m.group(1))
            continue
        m = re.match(r"^>\s?(.*)", line)
        if m:
            flush_para()
            if mode != "quote":
                flush_block(); mode = "quote"
            buf.append(m.group(1))
            continue
        flush_block()
        para.append(line.strip())

    flush_para(); flush_block()
    return "\n".join(out)


def parse_post(path: pathlib.Path):
    text = path.read_text(encoding="utf-8")
    meta = {"title": path.stem, "date": "", "summary": "", "published": False}
    if text.startswith("---\n"):
        front, separator, body = text[4:].partition("\n---")
        if not separator:
            raise ValueError(f"{path}: frontmatter 未闭合")
        fields = yaml.safe_load(front) or {}
        if not isinstance(fields, dict):
            raise ValueError(f"{path}: frontmatter 必须是字段")
        meta.update(fields)
        text = body
    meta["date"] = str(meta["date"] or "")
    meta["title"] = str(meta["title"])
    meta["summary"] = str(meta["summary"])
    if not isinstance(meta["published"], bool):
        raise ValueError(f"{path}: published 必须是 true 或 false")
    return meta, md_to_html(text)


# ---------------- 文章页模板 ----------------

POST_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · {site}</title>
<meta name="description" content="{summary}">
<meta name="theme-color" content="#131a19">
<link rel="stylesheet" href="../assets/css/site.css">
<style>
  .post {{ max-width: 780px; margin: 0 auto; padding: 0 var(--pad) 100px; }}
  .post-header {{ padding: 40px 0 44px; }}
  .post h1 {{ margin: 0 0 18px; font-family: var(--serif); font-weight: 900; font-size: clamp(2.2rem, 5vw, 3.8rem); line-height: 1.15; }}
  .post time {{ color: var(--chalk-dim); }}
  .post p {{ margin: 0 0 1.4em; font-family: var(--serif); font-size: 1.08rem; line-height: 1.95; }}
  .post h2 {{ margin: 2.4em 0 .8em; font-family: var(--serif); font-size: clamp(1.5rem, 3vw, 2rem); }}
  .post blockquote {{ margin: 0 0 1.4em; padding-left: 1em; border-left: 2px solid var(--line); color: var(--chalk-dim); }}
  .post img {{ width: 100%; height: auto; }}
  .post code {{ padding: 0 .3em; background: var(--board-2); }}
  .post pre {{ overflow-x: auto; padding: 14px; background: var(--board-2); }}
  .post-list {{ margin: 0; padding: 0; list-style: none; }}
  .post-list li {{ padding: 16px 0; border-bottom: 1px solid var(--line); }}
  .post-list a {{ font-family: var(--serif); font-size: 1.2rem; }}
  .post-list span {{ display: block; color: var(--chalk-dim); font-size: .9rem; }}
</style>
</head>
<body>
<header class="top" style="position:relative"><a class="top-home" href="../">{site}</a><nav class="top-nav" style="display:flex"><a href="./">文章</a></nav></header>
<main class="post">
<header class="post-header">
<h1>{title}</h1>
<time datetime="{date}">{date}</time>
</header>
{body}
</main>
<footer class="foot"><small>© {year} {site}</small></footer>
</body>
</html>
"""

# ---------------- 作品页（静态版） ----------------
# 首页和作品页都靠 JS 读 works.json，爬虫和分享卡片等不到 JS。
# 这里给每部有封面的作品生成 work/<id>.html：标题、简介、og:image 都是真值，
# 进去以后仍然可以跳到原来那个带播放器的 work.html?id=<id>。

WORK_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title} · {site}</title>
<meta name="description" content="{description}">
<meta name="theme-color" content="#050505">
<link rel="canonical" href="{url}">
<meta property="og:type" content="video.other">
<meta property="og:site_name" content="{site}">
<meta property="og:locale" content="zh_CN">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{image}">
<meta property="og:image:width" content="1280">
<meta property="og:image:height" content="720">
<meta property="og:image:alt" content="{image_alt}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="{image}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' fill='%23050505'/><circle cx='16' cy='16' r='7' fill='%23ff5a00'/><path d='M3 3h5M3 3v5M29 3h-5M29 3v5M3 29h5M3 29v-5M29 29h-5M29 29v-5' stroke='%23ece8df' stroke-width='2' fill='none'/></svg>">
<link rel="preload" href="../assets/fonts/archivo-wdth.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="../assets/css/site.css">
</head>
<body class="work-page">
<header class="top">
  <a class="top-home" href="../" aria-label="TaopleOne 首页"><i class="rec" aria-hidden="true"></i>{site}</a>
  <nav class="top-nav" aria-label="分区"><a href="../#{section_id}"><small>{section_no}</small>{section_name}</a></nav>
</header>

<main id="work" class="work work-static">
  <a class="work-back" href="../#{section_id}"><b>卷 {section_no}</b> 回到{section_name}（{section_brand}）</a>
  <h1 class="work-title">{title}</h1>
  <div class="static-stage"><img src="../covers/{cover}.jpg" alt="{image_alt}" width="1280" height="720"></div>
  <div class="work-info">
    <dl class="slate">
      <div><dt>卷</dt><dd>{section_no}  {section_name}</dd></div>
      <div><dt>编号</dt><dd>{work_no}</dd></div>
      <div><dt>时长</dt><dd>{duration}</dd></div>
      <div><dt>画幅</dt><dd>{ratio}</dd></div>
{extra_cells}    </dl>
    <div class="work-text">
      <p class="work-blurb">{blurb}</p>
      <div class="work-actions">
{actions}
      </div>
      <p class="static-note">这一页是给搜索引擎和分享卡片看的静态版；<a href="../work.html?id={id_url}{play_hash}">打开带播放器、能动手玩的作品页</a>。</p>
    </div>
  </div>
</main>

<footer class="foot"><small class="foot-copy">© 2026 {site}。作品由 AI 参与制作。</small></footer>
</body>
</html>
"""

RATIO_LABEL = {"16:9": "16:9 横屏", "9:16": "9:16 竖屏"}


def work_duration(seconds) -> str:
    if not seconds:
        return "—"
    seconds = int(round(float(seconds)))
    return "%02d:%02d" % (seconds // 60, seconds % 60)


def work_pages(root: pathlib.Path, output: pathlib.Path) -> list[str]:
    """按 data/works.json 生成 work/<id>.html；没有封面的（待出片）跳过。"""
    data_path = root / "data" / "works.json"
    if not data_path.is_file():
        return []
    data = json.loads(data_path.read_text(encoding="utf-8"))
    base = str((data.get("site") or {}).get("url") or DEFAULT_SITE_URL)
    if not base.endswith("/"):
        base += "/"
    full_base = str((data.get("site") or {}).get("fullBase") or "")
    sections = data.get("sections") or []
    works = data.get("works") or []

    written = []
    for index, section in enumerate(sections):
        section["_no"] = "%02d" % (index + 1)

    for work in works:
        wid = work.get("id")
        if not wid or not (root / "covers" / (wid + ".jpg")).is_file():
            continue
        section = next((s for s in sections if s.get("id") == work.get("series")), None)
        if section is None:
            continue
        siblings = [w for w in works
                    if w.get("series") == section["id"] or section["id"] in (w.get("also") or [])]
        number = "%02d/%02d" % (siblings.index(work) + 1, len(siblings))
        tall = work.get("ratio") == "9:16"
        title = str(work.get("title") or wid)
        blurb = str(work.get("blurb") or "")
        if work.get("status") == "soon" and not blurb:
            blurb = "还在做，做好就放上来。"
        image_alt = "《%s》的画面" % title
        url = base + "work/" + wid + ".html"
        image = base + "covers/" + wid + ".jpg"

        cells = []
        if work.get("level"):
            cells.append(("适合", str(work["level"])))
        if work.get("group"):
            cells.append(("系列", "课本系列" if work["group"] == "textbook" else "生活系列"))
        if work.get("maker"):
            cells.append(("制作", str(work["maker"])))
        extra_cells = "".join(
            '      <div><dt>%s</dt><dd>%s</dd></div>\n' % (html.escape(k), html.escape(v))
            for k, v in cells)

        actions = []
        if work.get("video", True) and work.get("status") != "soon":
            actions.append('        <a class="btn primary" href="../work.html?id=%s">打开作品页</a>' % html.escape(wid, quote=True))
            if full_base:
                actions.append('        <a class="btn" href="%s%s.mp4" download>下载完整版</a>'
                               % (html.escape(full_base, quote=True), html.escape(wid, quote=True)))
        if work.get("figure"):
            actions.append('        <a class="btn" href="../figures/%s.html">全屏交互图</a>'
                           % html.escape(str(work["figure"]), quote=True))
        if work.get("bilibili"):
            actions.append('        <a class="btn" href="%s" rel="noopener">在 B 站看</a>'
                           % html.escape(str(work["bilibili"]), quote=True))
        if not actions:
            actions.append('        <a class="btn primary" href="../work.html?id=%s">打开作品页</a>' % html.escape(wid, quote=True))

        page = WORK_TEMPLATE.format(
            site=SITE,
            title=html.escape(title),
            description=html.escape(blurb),
            url=html.escape(url, quote=True),
            image=html.escape(image, quote=True),
            image_alt=html.escape(image_alt, quote=True),
            section_id=html.escape(section["id"], quote=True),
            section_no=section["_no"],
            section_name=html.escape(str(section.get("name") or "")),
            section_brand=html.escape(str(section.get("brand") or "")),
            cover=html.escape(wid, quote=True),
            work_no=html.escape(number),
            duration=html.escape(work_duration(work.get("duration"))),
            ratio=html.escape(RATIO_LABEL.get(work.get("ratio"), "16:9 横屏")),
            blurb=html.escape(blurb) or "&nbsp;",
            extra_cells=extra_cells,
            actions="\n".join(actions),
            id_url=html.escape(wid, quote=True),
            play_hash="#play" if work.get("figure") and work.get("video", True) else "",
        )
        destination = output / "work" / (wid + ".html")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(page, encoding="utf-8")
        written.append(wid)
    return written


def copy_post_images(markdown: str, root: pathlib.Path, output: pathlib.Path):
    image_root = (root / "posts" / "images").resolve()
    for url in re.findall(r"\]\(([^)\s]+)\)", markdown):
        if url.startswith("/posts/images/"):
            relative = url.removeprefix("/posts/")
        elif url.startswith("images/"):
            relative = url
        else:
            continue
        source = (root / "posts" / relative).resolve()
        if not source.is_relative_to(image_root):
            raise ValueError(f"图片路径超出 posts/images: {url}")
        if not source.is_file():
            raise FileNotFoundError(source)
        destination = output / "posts" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def build(root: pathlib.Path = ROOT, output: pathlib.Path | None = None, published_only: bool = False):
    root = root.resolve()
    output = (output or root).resolve()
    if published_only:
        if output == root or (output.exists() and any(output.iterdir())):
            raise ValueError("公开构建须输出到独立的空目录，防止旧草稿残留")
        output.mkdir(parents=True, exist_ok=True)

    posts = []
    for md in sorted((root / "posts").glob("*.md")):
        meta, body = parse_post(md)
        if not published_only or meta["published"]:
            posts.append((md, meta, body))
    posts.sort(key=lambda p: p[1]["date"] or p[0].stem, reverse=True)
    visible_posts = [post for post in posts if post[1]["published"]]

    output_posts = output / "posts"
    output_posts.mkdir(parents=True, exist_ok=True)
    for md, meta, body in posts:
        (output_posts / (md.stem + ".html")).write_text(POST_TEMPLATE.format(
            title=html.escape(meta["title"]),
            summary=html.escape(meta["summary"]),
            site=SITE,
            date=html.escape(meta["date"]),
            year=(meta["date"] or "2026")[:4],
            body=body,
        ), encoding="utf-8")
        if published_only:
            copy_post_images(md.read_text(encoding="utf-8"), root, output)

    # 文章目录页 posts/index.html：只列已公开的文章，草稿仍可在本地直接打开预览
    if visible_posts:
        rows = ['<li><a href="%s.html">%s</a><span>%s</span></li>'
                % (md.stem, html.escape(meta["title"]), html.escape(meta["date"]))
                for md, meta, _ in visible_posts]
        listing = '<ul class="post-list">\n%s\n</ul>' % "\n".join(rows)
    else:
        listing = "<p>还没有公开的文章。</p>"
    (output_posts / "index.html").write_text(POST_TEMPLATE.format(
        title="文章", summary=f"{SITE} 的文章", site=SITE, date="", year="2026", body=listing,
    ), encoding="utf-8")

    if published_only:
        for name in SITE_FILES:
            destination = output / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / name, destination)
        for name in SITE_DIRS:
            shutil.copytree(root / name, output / name)

    written_works = work_pages(root, output)

    print("构建完成：%d 篇文章、%d 张作品静态页" % (len(posts), len(written_works)))
    for md, meta, _ in posts:
        print("  - posts/%s.html  %s" % (md.stem, meta["title"]))
    for wid in written_works:
        print("  - work/%s.html" % wid)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-output", type=pathlib.Path, help="只发布已公开的文章到独立目录")
    parser.add_argument("--serve", action="store_true", help="本地构建后预览")
    args = parser.parse_args()
    if args.public_output and args.serve:
        parser.error("--serve 不能与 --public-output 同用")
    build(output=args.public_output, published_only=bool(args.public_output))
    if args.serve:
        import functools
        import http.server
        import socketserver

        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
        with socketserver.TCPServer(("127.0.0.1", 8000), handler) as httpd:
            print("本地预览：http://localhost:8000 （Ctrl+C 停止）")
            httpd.serve_forever()


if __name__ == "__main__":
    main()
