#!/usr/bin/env python3
"""把文章和 AI 使用轨迹编译成静态站点。"""
import argparse
import html
import json
import pathlib
import re
import shutil

import yaml

ROOT = pathlib.Path(__file__).resolve().parent
POSTS_START, POSTS_END = "<!-- POSTS:START -->", "<!-- POSTS:END -->"


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


def replace_section(page: str, start: str, end: str, body: str) -> str:
    before, marker, rest = page.partition(start)
    if not marker:
        raise ValueError(f"首页缺少 {start}")
    _, marker, after = rest.partition(end)
    if not marker:
        raise ValueError(f"首页缺少 {end}")
    return before + start + "\n" + body + "\n" + end + after


def render_timeline(moments: list[dict], available_posts: set[str]) -> str:
    if not isinstance(moments, list):
        raise ValueError("AI 轨迹须为数组")
    rows = []
    for moment in moments:
        when = html.escape(moment["when"])
        date = moment.get("date", "")
        if date and not re.fullmatch(r"\d{4}-\d{2}", date):
            raise ValueError("时间轴 date 须为 YYYY-MM")
        stamp = (f'<time class="moment-when" datetime="{date}">{when}</time>' if date
                 else f'<span class="moment-when">{when}</span>')
        tags = []
        for tool in moment["tools"]:
            name = html.escape(tool["name"])
            note = html.escape(tool.get("note") or "")
            link = tool.get("link") or ""
            if link and not (link.startswith("https://") or link.startswith("posts/")):
                raise ValueError(f"{name}: 链接只能是 HTTPS 或站内文章")
            if link.startswith("posts/") and link not in available_posts:
                link = ""
            if note or link:
                more = f' <a href="{html.escape(link, quote=True)}">阅读记录</a>' if link else ""
                tags.append(f'<details class="moment-detail"><summary>{name}</summary>'
                            f'<p class="moment-copy">{note}{more}</p></details>')
            else:
                tags.append(f'<span class="moment-tag">{name}</span>')
        current = ' class="moment-current"' if moment.get("current") is True else ""
        rows.append(
            f'        <li{current}>\n'
            f'          {stamp}\n'
            '          <span class="moment-dot" aria-hidden="true"></span>\n'
            f'          <h4 class="moment-title">{html.escape(moment["title"])}</h4>\n'
            f'          <div class="moment-tags">{"".join(tags)}</div>\n'
            '        </li>'
        )
    return "\n".join(rows)


# ---------------- 文章页模板 ----------------

POST_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · {site}</title>
<meta name="description" content="{summary}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' fill='black'/><text x='16' y='23' font-size='18' text-anchor='middle' fill='white' font-family='serif'>T</text></svg>">
<style>
  :root {{ --forest: #344539; --cream: #f2eddf; --ink: #30382e; --muted: #565e51; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    color: var(--ink);
    background: var(--cream);
    font-family: "Songti SC", "Noto Serif CJK SC", "Source Han Serif SC", Georgia, serif;
    line-height: 1.8;
  }}
  a {{ color: inherit; text-underline-offset: .25em; }}
  a:hover {{ color: #a34b28; }}
  a:focus-visible {{ outline: 2px solid #e68a58; outline-offset: 4px; }}
  .top {{
    padding: 20px max(24px, calc((100vw - 1100px) / 2));
    color: var(--cream);
    background: var(--forest);
  }}
  .top a {{ display: inline-block; min-height: 44px; line-height: 44px; text-decoration: none; }}
  .post {{ max-width: 1148px; margin: 0 auto; padding: 0 24px 100px; }}
  .post-header {{ max-width: 780px; padding: 76px 0 52px; }}
  h1 {{ margin: 0 0 26px; font-size: clamp(2.4rem, 5vw, 4.6rem); font-weight: 400; line-height: 1.2; }}
  time {{ color: var(--muted); font-family: Georgia, serif; }}
  .post > p, .post > h2, .post > ul, .post > ol, .post > blockquote {{
    max-width: 720px;
  }}
  .post > p {{ margin: 0 0 28px; font-size: 1.1rem; }}
  .post > h2 {{ margin: 68px 0 24px; font-size: clamp(1.7rem, 3vw, 2.3rem); font-weight: 500; }}
  .post > p:has(> img) {{ max-width: none; margin: 44px 0 10px; }}
  .post > p:has(> img) + p {{ color: var(--muted); font-size: .95rem; }}
  .post img {{ display: block; width: 100%; height: auto; }}
  footer {{
    padding: 28px max(24px, calc((100vw - 1100px) / 2));
    color: var(--cream);
    background: var(--forest);
    font-size: .9rem;
  }}
</style>
</head>
<body>
<nav class="top"><a href="../index.html">← 返回 {site}</a></nav>
<main class="post">
<header class="post-header">
<h1>{title}</h1>
<time datetime="{date}">{date}</time>
</header>
{body}
</main>
<footer>© {year} {site}</footer>
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

    index_html = (root / "index.html").read_text(encoding="utf-8")
    site = re.search(r"<title>(.*?)</title>", index_html, re.S)
    site = html.unescape(site.group(1).strip()) if site else "我的文集"
    tracks = json.loads((root / "data" / "ai-journey.json").read_text(encoding="utf-8"))
    if not isinstance(tracks, dict) or any(not isinstance(tracks.get(key), list) for key in ("llm", "agents")):
        raise ValueError("AI 轨迹须包含 llm 与 agents 两条列表")
    if sum(moment.get("current") is True for key in ("llm", "agents")
           for moment in tracks[key]) > 1:
        raise ValueError("AI 轨迹至多一个节点可标记为当前")

    posts = []
    for md in sorted((root / "posts").glob("*.md")):
        meta, body = parse_post(md)
        if not published_only or meta["published"]:
            posts.append((md, meta, body))
    posts.sort(key=lambda p: p[1]["date"] or p[0].stem, reverse=True)
    visible_posts = [post for post in posts if post[1]["published"]]
    available_posts = {f"posts/{md.stem}.html" for md, _, _ in visible_posts}
    for key in ("llm", "agents"):
        marker = key.upper()
        index_html = replace_section(
            index_html, f"<!-- {marker}:START -->", f"<!-- {marker}:END -->",
            render_timeline(tracks[key], available_posts)
        )

    if visible_posts:
        rows = ['  <li><a href="posts/%s.html">%s</a>（%s）</li>'
                % (md.stem, html.escape(meta["title"]), html.escape(meta["date"]))
                for md, meta, _ in visible_posts]
        block = "\n".join(rows)
    else:
        block = "  <li>暂无文章。</li>"
    index_html = replace_section(index_html, POSTS_START, POSTS_END, block)

    output_posts = output / "posts"
    output_posts.mkdir(parents=True, exist_ok=True)
    for md, meta, body in posts:
        (output_posts / (md.stem + ".html")).write_text(POST_TEMPLATE.format(
            title=html.escape(meta["title"]),
            summary=html.escape(meta["summary"]),
            site=html.escape(site),
            date=html.escape(meta["date"]),
            year=(meta["date"] or "2026")[:4],
            body=body,
        ), encoding="utf-8")
        if published_only:
            copy_post_images(md.read_text(encoding="utf-8"), root, output)

    (output / "index.html").write_text(index_html, encoding="utf-8")
    if published_only:
        shutil.copytree(root / "assets", output / "assets")

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
