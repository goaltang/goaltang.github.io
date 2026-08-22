#!/usr/bin/env python3
"""极简博客构建脚本：把 posts/*.md 编译成静态 HTML，并刷新首页目录。

用法：
    python build.py          # 构建
    python build.py --serve  # 构建并启动本地预览 http://localhost:8000
"""
import html
import re
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
POSTS_DIR = ROOT / "posts"
INDEX = ROOT / "index.html"

START = "<!-- POSTS:START -->"
END = "<!-- POSTS:END -->"


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
    meta = {"title": path.stem, "date": "", "summary": ""}
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            text = parts[2]
    return meta, md_to_html(text)


# ---------------- 文章页模板 ----------------

POST_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · {site}</title>
<meta name="description" content="{summary}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect x='4' y='4' width='24' height='24' rx='3' fill='%23b23a2c'/><text x='16' y='22' font-size='16' text-anchor='middle' fill='white' font-family='serif'>T</text></svg>">
<link rel="stylesheet" href="../style.css">
</head>
<body>
<div class="page">
  <header class="masthead">
    <div class="folio">
      <a href="../index.html" style="color:inherit;text-decoration:none">{site} · Blog</a>
      <span>记录 · 思考 · 创造</span>
    </div>
    <div class="mast-main">
      <h1 style="font-size:1.5rem"><a href="../index.html" style="color:inherit;text-decoration:none">{site}</a></h1>
      <span class="signature"><img class="sig-light" src="../assets/signature.svg" alt=""><img class="sig-dark" src="../assets/signature-dark.svg" alt="" aria-hidden="true"></span>
    </div>
  </header>
  <article class="post">
    <p class="crumb"><a href="../index.html">← 返回目录</a></p>
    <h1>{title}</h1>
    <span class="when">{date}</span>
    <div class="double"></div>
{body}
  </article>
  <footer>
    <span>© {year} {site}</span>
    <span><a href="../index.html" style="color:inherit">回到首页</a></span>
  </footer>
</div>
</body>
</html>
"""


def main():
    index_html = INDEX.read_text(encoding="utf-8")
    site = re.search(r"<h1[^>]*>(.*?)</h1>", index_html, re.S)
    site = html.unescape(site.group(1).strip()) if site else "我的文集"


    posts = []
    for md in sorted(POSTS_DIR.glob("*.md")):
        meta, body = parse_post(md)
        posts.append((md, meta, body))
    posts.sort(key=lambda p: p[1]["date"] or p[0].stem, reverse=True)

    # 1. 生成文章页
    for md, meta, body in posts:
        out = POSTS_DIR / (md.stem + ".html")
        out.write_text(POST_TEMPLATE.format(
            title=html.escape(meta["title"]),
            summary=html.escape(meta["summary"]),
            site=html.escape(site),
            date=html.escape(meta["date"]),
            year=(meta["date"] or "2026")[:4],
            body=body,
        ), encoding="utf-8")

    # 2. 刷新首页目录
    if posts:
        rows = []
        for i, (md, meta, _) in enumerate(posts, 1):
            rows.append(
                '        <li>\n'
                '          <a class="toc-row" href="posts/%s.html">\n'
                '            <span class="num">%02d</span>\n'
                '            <span class="t">%s</span>\n'
                '            <span class="leader"></span>\n'
                '            <span class="when">%s</span>\n'
                '          </a>\n'
                % (md.stem, i, html.escape(meta["title"]), html.escape(meta["date"]))
                + ('          <p class="summary">%s</p>\n' % html.escape(meta["summary"]) if meta["summary"] else "")
                + '        </li>'
            )
        block = "\n".join(rows)
    else:
        block = '        <li class="toc-empty">\n          <svg class="brush" viewBox="0 0 120 24" aria-hidden="true">\n            <path d="M4 13 C 28 7, 62 7, 88 11 C 100 12.8, 110 12, 116 9" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>\n            <path d="M70 17.5 C 84 16.5, 98 15.5, 110 14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" opacity=".55"/>\n          </svg>\n          <p class="e1">暂无文章</p>\n          <p class="e2">第一篇正在路上，写好后会出现在这里</p>\n        </li>'

    before = index_html.split(START)[0] + START + "\n"
    after = "\n" + END + index_html.split(END)[1]
    INDEX.write_text(before + block + after, encoding="utf-8")

    print("构建完成：%d 篇文章" % len(posts))
    for md, meta, _ in posts:
        print("  - posts/%s.html  %s" % (md.stem, meta["title"]))

    if "--serve" in sys.argv:
        import http.server, socketserver, functools
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
        with socketserver.TCPServer(("", 8000), handler) as httpd:
            print("本地预览：http://localhost:8000 （Ctrl+C 停止）")
            httpd.serve_forever()


if __name__ == "__main__":
    main()
