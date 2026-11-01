#!/usr/bin/env python3
"""Crawl có kiểm soát một pilot bài viết Tày–Nùng công khai từ VOV4.

Đầu ra chỉ là dữ liệu ứng viên phục vụ audit nội bộ. Nội dung không được xem là
dataset Tày–Việt sạch và không được phát hành lại khi chưa có phép của VOV.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from collections import deque
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_pipeline.common import ensure_new, run_report, sha256, write_json


BASE_URL = "https://vov4.vov.vn"
DEFAULT_SEED = f"{BASE_URL}/taynung"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
USER_AGENT = (
    "IE501-TayViet-ResearchBot/0.1 "
    "(academic research; contact: repository maintainers)"
)
BLOCK_TAGS = {"div", "p", "li", "h1", "h2", "h3", "h4", "blockquote"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value).replace("\xa0", " ")).strip()


def normalize_url(url: str) -> str:
    parsed = urlparse(urljoin(BASE_URL, url))
    if parsed.scheme not in {"http", "https"} or parsed.netloc != "vov4.vov.vn":
        return ""
    return urlunparse(("https", parsed.netloc, parsed.path.rstrip("/"), "", "", ""))


def is_article_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.netloc == "vov4.vov.vn"
        and parsed.path.startswith("/taynung/")
        and parsed.path.endswith(".vov4")
    )


class VovArticleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, set[str]]] = []
        self.links: set[str] = set()
        self.meta: dict[str, str] = {}
        self.html_lang = ""
        self.article_depth: int | None = None
        self.body_depth: int | None = None
        self.time_depth: int | None = None
        self.body_chunks: list[str] = []
        self.current_body: list[str] = []
        self.time_chunks: list[str] = []
        self.media_urls: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        classes = set(attributes.get("class", "").split())
        if tag not in VOID_TAGS:
            self.stack.append((tag, classes))
        depth = len(self.stack)

        if tag == "html":
            self.html_lang = attributes.get("lang", "")
        if tag == "article":
            self.article_depth = depth
        if "text-long" in classes and self.article_depth is not None:
            self.body_depth = depth
        if "time-published" in classes and self.article_depth is not None:
            self.time_depth = depth

        if tag == "a" and attributes.get("href"):
            url = normalize_url(attributes["href"])
            if url:
                self.links.add(url)

        if tag == "meta":
            key = attributes.get("property") or attributes.get("name")
            value = attributes.get("content")
            if key and value:
                self.meta[key] = normalize_text(value)

        if self.body_depth is not None and tag in BLOCK_TAGS:
            self._flush_body()

        if self.article_depth is not None and tag in {"audio", "video", "source"}:
            media = attributes.get("src") or attributes.get("data-url")
            if media:
                self.media_urls.add(urljoin(BASE_URL, media))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self.body_depth is not None:
            self.current_body.append(data)
        if self.time_depth is not None:
            self.time_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        depth = len(self.stack)
        if self.body_depth is not None and tag in BLOCK_TAGS:
            self._flush_body()
        if self.body_depth == depth:
            self._flush_body()
            self.body_depth = None
        if self.time_depth == depth:
            self.time_depth = None
        if self.article_depth == depth:
            self.article_depth = None
        if self.stack:
            self.stack.pop()

    def _flush_body(self) -> None:
        text = normalize_text(" ".join(self.current_body))
        self.current_body.clear()
        if text and (not self.body_chunks or text != self.body_chunks[-1]):
            self.body_chunks.append(text)

    def article(self, source_url: str) -> dict[str, object] | None:
        self._flush_body()
        canonical = normalize_url(self.meta.get("og:url", source_url)) or source_url
        title = self.meta.get("og:title", "")
        summary = self.meta.get("og:description", "")
        if not title or (not summary and not self.body_chunks):
            return None
        return {
            "source_url": canonical,
            "source_domain": "vov4.vov.vn",
            "source_section": self.meta.get("article:section", ""),
            "title": title,
            "summary_taynung_candidate": summary,
            "body_blocks": self.body_chunks,
            "published_text": normalize_text(" ".join(self.time_chunks)),
            "media_urls": sorted(self.media_urls),
            "html_lang": self.html_lang,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "license_status": "permission_required",
            "language_label": "unverified_tay_nung",
            "alignment_level": "document_candidate",
            "review_status": "not_reviewed",
        }


def fetch_text(url: str, timeout: float) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(content_type, errors="replace")


def load_robots(timeout: float) -> RobotFileParser:
    parser = RobotFileParser()
    parser.set_url(ROBOTS_URL)
    parser.parse(fetch_text(ROBOTS_URL, timeout).splitlines())
    return parser


def load_existing_urls(path: Path) -> set[str]:
    urls: set[str] = set()
    if path.exists():
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    try:
                        row = json.loads(line)
                        if "source_url" in row:
                            urls.add(row["source_url"])
                    except json.JSONDecodeError:
                        pass
    return urls


def append_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def crawl(seed: str, max_pages: int, delay: float, timeout: float, existing_urls: set[str] | None = None) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    seed = normalize_url(seed)
    if not seed or not (seed == DEFAULT_SEED or is_article_url(seed)):
        raise ValueError("Seed phải thuộc mục Tày–Nùng của VOV4")
    if max_pages < 1 or delay < 1.0 or timeout <= 0:
        raise ValueError("max_pages >= 1, delay >= 1 giây, timeout > 0")
    robots = load_robots(timeout)
    if not robots.can_fetch(USER_AGENT, seed):
        raise RuntimeError(f"robots.txt không cho phép truy cập seed: {seed}")

    queue = deque([normalize_url(seed) or seed])
    visited: set[str] = set(existing_urls or ())
    articles: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    max_fetches = max(30, max_pages * 5)

    while queue and len(articles) < max_pages and len(visited) < max_fetches:
        url = queue.popleft()
        if not url or url in visited:
            continue
        visited.add(url)
        if not robots.can_fetch(USER_AGENT, url):
            errors.append({"url": url, "error": "blocked_by_robots"})
            continue

        if len(visited) > 1:
            time.sleep(delay)
        try:
            page = fetch_text(url, timeout)
            parser = VovArticleParser()
            parser.feed(page)
        except (HTTPError, URLError, TimeoutError, UnicodeError) as exc:
            errors.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
            continue

        article = parser.article(url) if is_article_url(url) else None
        if article is not None:
            articles.append(article)
            print(f"[{len(articles):03d}/{max_pages}] {url}", file=sys.stderr)

        for link in sorted(parser.links):
            if link not in visited and (is_article_url(link) or link == DEFAULT_SEED):
                queue.append(link)

    return articles, errors


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--output", type=Path, default=Path("data/raw/vov4/articles.jsonl"))
    parser.add_argument("--errors", type=Path, default=Path("data/manifests/vov4_crawl_errors.jsonl"))
    parser.add_argument("--append", action="store_true", help="Nối thêm dữ liệu thay vì ghi đè, bỏ qua các URL đã có")
    parser.add_argument("--manifest", type=Path, default=Path("data/manifests/crawl_run.json"))
    args = parser.parse_args()
    if args.max_pages < 1:
        parser.error("--max-pages phải >= 1")
    if args.delay < 1.0:
        parser.error("--delay phải >= 1 giây để hạn chế tải lên VOV4")

    if args.timeout <= 0:
        parser.error("--timeout phải > 0")
    if len({p.resolve() for p in (args.output, args.errors, args.manifest)}) != 3:
        parser.error("Các đường dẫn đầu ra phải khác nhau")
    ensure_new(args.manifest)
    if not args.append:
        ensure_new(args.output, args.errors)
    previous_hash = sha256(args.output) if args.output.exists() else None
    existing_urls = load_existing_urls(args.output) if args.append else set()
    if existing_urls:
        print(f"Loaded {len(existing_urls)} existing URLs. Resume crawling...", file=sys.stderr)

    articles, errors = crawl(args.seed, args.max_pages, args.delay, args.timeout, existing_urls)

    if args.append:
        append_jsonl(args.output, articles)
        append_jsonl(args.errors, errors)
    else:
        write_jsonl(args.output, articles)
        write_jsonl(args.errors, errors)

    write_json(args.manifest, run_report("crawl", [], [args.output, args.errors],
               seed=args.seed, max_pages=args.max_pages, delay=args.delay, timeout=args.timeout,
               append=args.append, previous_output_sha256=previous_hash,
               articles_fetched=len(articles), errors=len(errors)))
    print(json.dumps({"articles_fetched": len(articles), "errors": len(errors), "output": str(args.output)}))


if __name__ == "__main__":
    main()
