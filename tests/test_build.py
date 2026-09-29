import json
import tempfile
import unittest
from pathlib import Path

from build import build


class SiteBuildTest(unittest.TestCase):
    def test_drafts_stay_out_of_public_site_but_can_be_previewed_locally(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            (root / "posts" / "images").mkdir(parents=True)
            (root / "data").mkdir()
            (root / "assets").mkdir()
            (root / "assets" / "signature.svg").write_text("<svg></svg>")
            (root / "index.html").write_text(
                "<title>Test</title><ol><!-- LLM:START -->\n<!-- LLM:END --></ol>"
                "<ol><!-- AGENTS:START -->\n<!-- AGENTS:END --></ol>"
                "<ul><!-- POSTS:START -->\n<!-- POSTS:END --></ul>",
                encoding="utf-8",
            )
            (root / "data" / "ai-journey.json").write_text(json.dumps({
                "llm": [{
                    "when": "2025.02", "date": "2025-02", "title": "模型起点",
                    "tools": [{"name": "Claude 3.5 Sonnet"}],
                }],
                "agents": [{
                    "when": "随后", "title": "工具起点", "current": True,
                    "tools": [
                        {"name": "隐藏文章", "note": "试过", "link": "posts/draft.html"},
                        {"name": "公开文章", "link": "posts/public.html"},
                    ],
                }],
            }), encoding="utf-8")
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

            output = Path(directory) / "published"
            build(root, output, published_only=True)
            index = (output / "index.html").read_text(encoding="utf-8")
            llm = index.split("<!-- LLM:START -->")[1].split("<!-- LLM:END -->")[0]
            agents = index.split("<!-- AGENTS:START -->")[1].split("<!-- AGENTS:END -->")[0]
            self.assertIn("Claude 3.5 Sonnet", llm)
            self.assertNotIn("Claude 3.5 Sonnet", agents)
            self.assertIn("公开文章", agents)
            self.assertNotIn("公开文章", llm)
            self.assertIn("2025.02", index)
            self.assertIn("Public: with colon", index)
            self.assertNotIn("Draft", index)
            self.assertNotIn("posts/draft.html", index)
            self.assertIn("posts/public.html", index)
            self.assertFalse((output / "posts" / "draft.html").exists())
            self.assertFalse((output / "posts" / "images" / "private.webp").exists())
            self.assertTrue((output / "posts" / "public.html").exists())
            self.assertEqual((output / "posts" / "images" / "public.webp").read_bytes(), b"public")
            self.assertEqual((output / "posts" / "images" / "hires.webp").read_bytes(), b"hires")

            build(root)
            self.assertTrue((root / "posts" / "draft.html").exists())
            local_index = (root / "index.html").read_text(encoding="utf-8")
            self.assertNotIn("posts/draft.html", local_index)


if __name__ == "__main__":
    unittest.main()
