# TaopleOne（个人主页与静态博客）

深绿与暖橘构成首页封面；站点仍是纯静态文件。文章和 AI 使用轨迹可以通过独立的 Pages CMS 网页后台填写，保存到 GitHub 后再手动发布。

## 目录结构

```
personal-blog/
├── .pages.yml                在线编辑后台的表单配置
├── .github/workflows/deploy.yml  手动发布 GitHub Pages
├── data/ai-journey.json      AI 使用轨迹的节点与工具
├── index.html                首页模板（构建时刷新轨迹与文章目录）
├── build.py                  本地预览与公开构建
├── requirements.txt          构建依赖
├── assets/                   首页素材
└── posts/
    ├── *.md                  文章原稿
    ├── images/               上传的文章图片
    └── *.html                仅本地生成的预览页，不提交
```

## 在网页后台添加内容

后台地址：[app.pagescms.org](https://app.pagescms.org/)。用 GitHub 登录，安装 Pages CMS GitHub App 时只授权本站仓库；它会根据 `.pages.yml` 显示两个入口：

- **文章**：填写标题、日期、摘要，在富文本编辑器写正文并上传图片。`公开此文章` 默认关闭；关闭时保存为草稿，不出现在公开构建及其文章图片中。
- **AI 探索轨迹**：分别在“大模型（LLM）”和“Agent 与 AI 工具”两个列表中增加阶段；填写时间标签、确定时才填写准确月份、阶段标题，再逐项添加模型或工具。使用记录非必填，填写后首页标签可点击展开。两条轨迹各按列表顺序显示，合计只能有一个“当前阶段”。

点击后台的保存按钮只会将内容写入 GitHub 仓库。确认内容和公开状态后，再点 **发布网站**；这才会运行 GitHub Actions，将已公开文章和轨迹部署到 Pages。后台不在本站的 `/admin`，访客也不能通过首页编辑。

注意：如果 GitHub 仓库是公开的，保存到仓库里的草稿正文和图片仍可被人从仓库查看；`公开此文章` 只控制网站页面，不提供私密存储。敏感草稿不要保存到公开仓库。

首次使用前，必须在仓库 Settings → Pages 将 **Build and deployment → Source** 改为 **GitHub Actions**，然后才连接 CMS、上传内容。若仍用 `main` 分支直接发布，后台保存的草稿文件也可能被 GitHub Pages 当作静态文件暴露。当前本地修改尚未推送或发布；切换发布方式前，公开网站不会使用这些配置。

## 本地预览

```bash
python3 -m pip install -r requirements.txt
python3 build.py --serve
```

打开 `http://localhost:8000`。草稿不会列在首页，但可以直接打开其 `posts/文件名.html` 本地预览。已有文章仍可编辑 `posts/*.md`；轨迹的原始内容在 `data/ai-journey.json`，正常更新不需要修改它们或 `index.html`。

## 网站基础信息

站名、介绍和联系方式仍在 `index.html` 中；这些很少变动的基础配置暂时不在后台表单内。

## GitHub Pages 发布

本站仓库为 `goaltang/goaltang.github.io`。在完成上面的 Pages 来源切换、将配置提交到 `main`，并授权 Pages CMS 后：

1. 登录后台添加或修改文章、AI 轨迹。
2. 保存到 GitHub。想让文章公开时打开“公开此文章”开关；未打开则只保存草稿。
3. 点击 **发布网站**，确认后由 `.github/workflows/deploy.yml` 运行 `python3 build.py --public-output` 并部署。不会因为保存内容就自动发布。

手动部署入口也在 GitHub 仓库 Actions → Publish TaopleOne → Run workflow。不要在切换到 Actions 之前将本地草稿和构建产物推到仍按分支发布的仓库。

## 自有服务器（nginx）

站点仍是静态文件。如果使用其他静态托管，需要先用 `python3 build.py --public-output 目标空目录` 构建，并只上传那个目录；不要直接上传含草稿的原始仓库。

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
- [ ] Pages 来源已切到 GitHub Actions；公开构建只包含标记公开的文章和引用图片

## 之后可以加的东西

- 自定义域名
- 免 cookie 的访问统计（Umami / Cloudflare 自带）
- RSS：需要的话可以给 build.py 加十几行生成 feed.xml
