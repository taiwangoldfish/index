"""Build the client-side search index without modifying article pages."""

import json
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATEGORY_LABELS = {
    "simple": "入門篇",
    "content": "日常操作",
    "feed": "餵食與營養",
    "filter": "過濾與水質",
    "fish-problem": "金魚有狀況",
    "buyfish": "買魚與檢疫",
    "iteam": "器材與設備",
    "knowledge": "金魚知識",
}
EXCLUDED_TEXT = {"💧 沒事多換水，多換水沒事 💧", "💧沒事多換水，多換水沒事💧"}


def clean_text(value: str) -> str:
    return " ".join(value.split())


class ArticleParser(HTMLParser):
    VOID_ELEMENTS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.description = ""
        self.title_parts = []
        self.article_parts = []
        self.headings = []
        self._article_depth = 0
        self._heading_level = None
        self._heading_parts = []
        self._in_h1 = False
        self._ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = set(attributes.get("class", "").split())
        if tag == "meta" and attributes.get("name", "").lower() == "description":
            self.description = attributes.get("content", "")
        if self._article_depth == 0 and "article-body" in classes:
            self._article_depth = 1
            return
        if self._article_depth and tag not in self.VOID_ELEMENTS:
            self._article_depth += 1
            if tag in {"script", "style", "nav"} or "water-motto" in classes:
                self._ignored_depth += 1
            if tag in {"h2", "h3", "h4"}:
                self._heading_level = tag
                self._heading_parts = []
        if tag == "h1":
            self._in_h1 = True

    def handle_endtag(self, tag):
        if self._article_depth and tag not in self.VOID_ELEMENTS:
            if tag == self._heading_level:
                heading = clean_text(" ".join(self._heading_parts))
                if heading:
                    self.headings.append(heading)
                self._heading_level = None
                self._heading_parts = []
            if self._ignored_depth and tag in {"script", "style", "nav", "p"}:
                self._ignored_depth -= 1
            self._article_depth -= 1
        if tag == "h1":
            self._in_h1 = False

    def handle_data(self, data):
        if self._in_h1:
            self.title_parts.append(data)
        if self._article_depth and not self._ignored_depth:
            self.article_parts.append(data)
            if self._heading_level:
                self._heading_parts.append(data)


def build_entry(path: Path) -> dict | None:
    relative = path.relative_to(ROOT)
    category_key = relative.parts[0] if len(relative.parts) > 1 else ""
    if category_key not in CATEGORY_LABELS:
        return None

    parser = ArticleParser()
    parser.feed(path.read_text(encoding="utf-8"))
    if not parser.article_parts:
        return None

    title = clean_text(" ".join(parser.title_parts)) or relative.stem
    description = clean_text(parser.description)
    headings = parser.headings
    content = clean_text(" ".join(parser.article_parts))
    for excluded in EXCLUDED_TEXT:
        description = description.replace(excluded, "")
        content = content.replace(excluded, "")

    return {
        "title": title,
        "url": "./" + relative.as_posix(),
        "category": CATEGORY_LABELS[category_key],
        "description": clean_text(description),
        "headings": headings,
        "content": clean_text(content),
    }


entries = []
for category in CATEGORY_LABELS:
    for html_path in sorted((ROOT / category).glob("*.html")):
        entry = build_entry(html_path)
        if entry:
            entries.append(entry)

(ROOT / "search-index.json").write_text(
    json.dumps(entries, ensure_ascii=False, separators=(",", ":")),
    encoding="utf-8",
)

knowledge_lines = [
    "# 金魚養殖經驗教學群知識庫",
    "",
    "本文件由網站現有文章自動整理，供專屬金魚 Agent 檢索。回答時必須附上對應的原始文章網址。",
    "",
    "## 固定生理知識與用語規則",
    "",
    "- 金魚沒有真正的胃，食物主要由腸道進行消化。",
    "- 描述金魚消化系統時，使用「腸道」或「消化道」，不可使用「胃」或「腸胃」。",
    "- 若下方自動整理的舊文章出現衝突用語，回答及後續編寫時以本規則為準。",
    "",
]
for entry in entries:
    public_url = entry["url"].replace("./", "https://taiwangoldfish.github.io/index/", 1)
    knowledge_lines.extend([
        f"## {entry['title']}",
        f"- 分類：{entry['category']}",
        f"- 原始文章：{public_url}",
        f"- 摘要：{entry['description']}" if entry["description"] else "",
        "",
        entry["content"] or "本頁主要為圖片或影片資料，請引導使用者查看原始文章。",
        "",
        "---",
        "",
    ])

(ROOT / "goldfish-agent-knowledge.md").write_text(
    "\n".join(line for line in knowledge_lines if line is not None),
    encoding="utf-8",
)
knowledge_package = "\n".join(line for line in knowledge_lines if line is not None)
(ROOT / "金魚AI知識包.md").write_text(knowledge_package, encoding="utf-8")
print(f"Generated search-index.json and goldfish-agent-knowledge.md with {len(entries)} pages.")
