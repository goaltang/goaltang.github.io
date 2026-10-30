#!/usr/bin/env python3
"""构建站点：作品集首页是手写的静态文件，这里只把文章编译成页面，并在公开构建时把整站拷进独立目录。"""
import argparse
import html
import pathlib
import re
import shutil

import yaml

ROOT = pathlib.Path(__file__).resolve().parent
SITE = "TaopleOne"
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

    print("构建完成：%d 篇文章" % len(posts))
    for md, meta, _ in posts:
        print("  - posts/%s.html  %s" % (md.stem, meta["title"]))


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
