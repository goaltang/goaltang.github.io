# TaoHub Blog（极简静态博客）

极致极简：近乎裸 HTML，只有文字、链接和一枚签名。零 JavaScript、零配色，手机自适应。
文章用 Markdown 写，一条命令生成静态页面。

## 目录结构

```
personal-blog/
├── index.html     首页（样式就内联在页面里，几行）
├── build.py       构建脚本（Markdown → 静态页 + 刷新文章列表）
├── assets/
│   └── signature.svg   艺术签名（字体已内嵌）
├── posts/
│   ├── xxx.md     你写的文章（Markdown）
│   └── xxx.html   生成的文章页（不用管）
└── README.md
```

## 写一篇文章

在 `posts/` 下新建 `.md` 文件，开头写三行信息：

```markdown
---
title: 文章标题
date: 2026-08-22
summary: 一句话摘要，会显示在首页目录里。
---

正文，支持 # 标题、**加粗**、*斜体*、`代码`、
> 引用、- 列表、1. 有序列表、[链接](https://...)、``` 代码块、--- 分隔线
```

然后运行：

```bash
python build.py          # 生成文章页 + 更新首页目录
python build.py --serve  # 顺便启动本地预览：http://localhost:8000
```

文章按日期倒序排在首页，最新的在最上面。

## 改成你自己的信息

编辑 `index.html`（构建脚本会自动读取名字和印章同步到文章页）：

| 位置 | 改成 |
|---|---|
| `<h1>` 和 `<title>` | 你的名字 / 网名 |
| 各段文字 | 直接改文字 |
| `<meta name="description">` | 一句话介绍（影响搜索/分享预览） |
| `assets/signature.svg` | 艺术签名（字体已内嵌，可直接当图片用） |

## 部署（免费）

**GitHub Pages（推荐）**
1. GitHub 建仓库 `yourname.github.io`，把整个文件夹传上去
2. Settings → Pages → Source 选 main 分支
3. 几分钟后访问 `https://yourname.github.io`

Cloudflare Pages / Vercel / Netlify 同样可用，无需任何构建配置
（build.py 在本地运行，平台上只放生成好的静态文件）。

## 自有服务器（nginx）

整站纯静态，把整个文件夹原样放进 web 目录即可，**服务器上不需要装 Python**
（build.py 只在你自己电脑上运行，生成物一起上传）。

最小 nginx 配置：

```nginx
server {
    listen 80;
    server_name your.domain.com;
    root /var/www/personal-blog;
    index index.html;

    gzip on;
    gzip_types text/css image/svg+xml;

    location / {
        try_files $uri $uri/ =404;
    }

    # css/svg 长缓存；html 不缓存，保证更新即时生效
    location ~* \.(css|svg)$ {
        expires 7d;
        add_header Cache-Control "public";
    }
    location ~* \.html$ {
        add_header Cache-Control "no-cache";
    }
}
```

HTTPS：`apt install certbot python3-certbot-nginx && certbot --nginx -d your.domain.com`

## 部署前自查

- [ ] `index.html` 里名字、介绍、联系方式已替换
- [ ] 邮箱 `mailto:` 链接正确
- [ ] 有域名后：加回 canonical 一行（head 里有注释）
- [ ] 本地跑过 `python build.py`，把生成的 `posts/*.html` 一起上传

## 之后可以加的东西

- 自定义域名
- 免 cookie 的访问统计（Umami / Cloudflare 自带）
- RSS：需要的话可以给 build.py 加十几行生成 feed.xml
