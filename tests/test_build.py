import json
import tempfile
import unittest
from pathlib import Path

from build import build, work_pages


class SiteBuildTest(unittest.TestCase):
    def make_source(self, directory):
        root = Path(directory) / "source"
        (root / "posts" / "images").mkdir(parents=True)
        (root / "data").mkdir()
        for name in ("assets", "covers", "figures", "films"):
            (root / name).mkdir()
        (root / "assets" / "site.css").write_text("body{}")
        (root / "covers" / "a.jpg").write_bytes(b"jpg")
        (root / "figures" / "a.html").write_text("<p>figure</p>")
        (root / "films" / "a.mp4").write_bytes(b"film")
        (root / "data" / "works.json").write_text(json.dumps({
            "site": {"url": "https://example.test/", "films": "films/", "fullBase": "https://example.test/films/"},
            "sections": [{"id": "manimgx", "name": "讲解", "brand": "ManimGX", "ratio": "16:9",
                          "site": {"url": "https://example.test/manimgx/", "works": "https://example.test/manimgx/works.html#"}}],
            "works": [
                {"id": "a", "series": "manimgx", "title": "A 作品", "blurb": "A 的简介", "duration": 26, "ratio": "16:9", "code": "a"},
                {"id": "b", "series": "manimgx", "title": "B 没有封面", "blurb": "B 的简介", "duration": 118, "ratio": "16:9"},
            ],
        }, ensure_ascii=False), encoding="utf-8")
        (root / "data" / "ai-journey.json").write_text("{}")
        self.homepage = "<title>作品集</title><main id=\"works\"></main>"
        (root / "index.html").write_text(self.homepage, encoding="utf-8")
        (root / "work.html").write_text("<title>作品</title>", encoding="utf-8")
        (root / "posts" / "draft.md").write_text(
            "---\ntitle: Draft\ndate: 2026-09-24\npublished: false\n---\n"
            "![private](images/private.webp)", encoding="utf-8",
        )
        (root / "posts" / "public.md").write_text(
            "---\ntitle: 'Public: with colon'\ndate: 2026-09-23\npublished: true\n---\n"
            "![public](/posts/images/public.webp)\n[高清图](images/hires.webp)", encoding="utf-8",
        )
        (root / "posts" / "images" / "private.webp").write_bytes(b"private")
        (root / "posts" / "images" / "public.webp").write_bytes(b"public")
        (root / "posts" / "images" / "hires.webp").write_bytes(b"hires")
        return root

    def test_public_build_copies_the_portfolio_and_only_published_posts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_source(directory)
            output = Path(directory) / "published"
            build(root, output, published_only=True)

            self.assertEqual((output / "index.html").read_text(encoding="utf-8"), self.homepage)
            self.assertTrue((output / "work.html").exists())
            self.assertTrue((output / "data" / "works.json").exists())
            self.assertFalse((output / "data" / "ai-journey.json").exists())
            self.assertTrue((output / "covers" / "a.jpg").exists())
            self.assertTrue((output / "figures" / "a.html").exists())
            self.assertTrue((output / "assets" / "site.css").exists())
            # 视频由 workflow 从 Release 下载，构建不拷本地 films/
            self.assertFalse((output / "films").exists())

            listing = (output / "posts" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Public: with colon", listing)
            self.assertNotIn("Draft", listing)
            self.assertFalse((output / "posts" / "draft.html").exists())
            self.assertFalse((output / "posts" / "images" / "private.webp").exists())
            self.assertTrue((output / "posts" / "public.html").exists())
            self.assertEqual((output / "posts" / "images" / "public.webp").read_bytes(), b"public")
            self.assertEqual((output / "posts" / "images" / "hires.webp").read_bytes(), b"hires")

    def test_work_pages_carry_absolute_social_meta(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_source(directory)
            output = Path(directory) / "published"
            build(root, output, published_only=True)

            page = (output / "work" / "a.html").read_text(encoding="utf-8")
            self.assertIn("<title>A 作品 · TaopleOne</title>", page)
            self.assertIn('<meta name="description" content="A 的简介">', page)
            self.assertIn('<link rel="canonical" href="https://example.test/work/a.html">', page)
            self.assertIn('<meta property="og:url" content="https://example.test/work/a.html">', page)
            self.assertIn('<meta property="og:image" content="https://example.test/covers/a.jpg">', page)
            self.assertIn('<meta property="og:image:width" content="1280">', page)
            self.assertIn('<meta name="twitter:card" content="summary_large_image">', page)
            # 原来那条带播放器的链接还得能用
            self.assertIn('href="../work.html?id=a"', page)
            self.assertIn('href="https://example.test/films/a.mp4"', page)
            # 独立站里有同名锚点的，链过去看代码
            self.assertIn('<a class="btn" href="https://example.test/manimgx/works.html#a">看代码</a>', page)
            # 没有封面的作品不出静态页
            self.assertFalse((output / "work" / "b.html").exists())

    def test_local_build_previews_drafts_without_touching_the_homepage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_source(directory)
            build(root)
            self.assertTrue((root / "posts" / "draft.html").exists())
            self.assertTrue((root / "work" / "a.html").exists())
            self.assertNotIn("draft.html", (root / "posts" / "index.html").read_text(encoding="utf-8"))
            self.assertEqual((root / "index.html").read_text(encoding="utf-8"), self.homepage)

    def test_public_build_refuses_a_non_empty_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_source(directory)
            output = Path(directory) / "published"
            output.mkdir()
            (output / "old.html").write_text("old")
            with self.assertRaises(ValueError):
                build(root, output, published_only=True)


class RealWorksTest(unittest.TestCase):
    """拿仓库里真正的 data/works.json 来检查首页精选和作品页。"""

    ROOT = Path(__file__).resolve().parent.parent

    def setUp(self):
        self.data = json.loads((self.ROOT / "data" / "works.json").read_text(encoding="utf-8"))
        self.manimgx = [w for w in self.data["works"] if w["series"] == "manimgx"]

    def test_home_features_three_or_four_manimgx_episodes(self):
        picks = [w["id"] for w in self.manimgx if w.get("featured")]
        self.assertGreaterEqual(len(picks), 3)
        self.assertLessEqual(len(picks), 4)
        # 和 ManimGX 独立站首页「先看这三集」一致
        for wid in ("pythagoras", "projectile", "roadster"):
            self.assertIn(wid, picks)
        # 精选只是标记，条目一个都不删
        self.assertEqual(len(self.manimgx), 8)

    def test_manimgx_section_links_to_the_standalone_site_once(self):
        sec = next(s for s in self.data["sections"] if s["id"] == "manimgx")
        self.assertEqual(sec["site"]["url"], "https://goaltang.github.io/manimgx/")
        self.assertTrue(sec["site"]["more"] and sec["site"]["label"])
        site_js = (self.ROOT / "assets" / "js" / "site.js").read_text(encoding="utf-8")
        self.assertIn("w.featured", site_js)
        self.assertEqual(site_js.count("sec.site.url"), 1)

    def test_every_manimgx_work_page_is_built_with_code_link(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            (root / "data").mkdir(parents=True)
            (root / "covers").mkdir()
            (root / "data" / "works.json").write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
            for w in self.manimgx:
                (root / "covers" / (w["id"] + ".jpg")).write_bytes(b"jpg")
            output = Path(directory) / "out"
            output.mkdir()
            work_pages(root, output)
            for w in self.manimgx:
                page = output / "work" / (w["id"] + ".html")
                self.assertTrue(page.exists(), w["id"])
                html_text = page.read_text(encoding="utf-8")
                self.assertIn('href="../work.html?id=%s"' % w["id"], html_text)
                self.assertIn("https://goaltang.github.io/manimgx/works.html#%s\">看代码" % w["code"], html_text)

    def test_no_standalone_tao(self):
        for rel in ("data/works.json", "assets/js/site.js", "index.html"):
            text = (self.ROOT / rel).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"(?<![A-Za-z])Tao(?![A-Za-z])", rel)


if __name__ == "__main__":
    unittest.main()
