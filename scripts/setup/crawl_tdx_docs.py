"""Crawl TdxQuant official docs to docs/references/tqcenter_docs/.

One-shot script. Reads URLs from docs/references/tqcenter-docs-manifest.json
and fetches each page's main content, saving as Markdown.

VuePress emits static HTML; the article body lives inside
`<div class="theme-default-content">...</div>`. We extract that and strip
nav/sidebar/footer chrome.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
import urllib.error
from html.parser import HTMLParser
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / 'docs' / 'references' / 'tqcenter-docs-manifest.json'
OUT_DIR = REPO_ROOT / 'docs' / 'references' / 'tqcenter_docs'
BASE_URL = 'https://help.tdx.com.cn'


class ContentExtractor(HTMLParser):
    """Extracts text within <div class="theme-default-content">...</div>."""

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.in_article = False
        self.article_depth = 0
        self.parts: list[str] = []
        self.current_tag: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get('class', '')
        if not self.in_article and 'theme-default-content' in cls:
            self.in_article = True
            self.article_depth = self.depth
        if self.in_article:
            self.current_tag.append(tag)
            # Preserve heading structure
            if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                level = int(tag[1])
                self.parts.append('\n\n' + '#' * level + ' ')
            elif tag == 'p':
                self.parts.append('\n\n')
            elif tag == 'li':
                self.parts.append('\n- ')
            elif tag == 'br':
                self.parts.append('\n')
            elif tag in ('code', 'pre'):
                self.parts.append('`' if tag == 'code' else '\n```\n')
            elif tag == 'strong' or tag == 'b':
                self.parts.append('**')
            elif tag == 'em' or tag == 'i':
                self.parts.append('*')
            elif tag == 'tr':
                self.parts.append('\n')
            elif tag == 'th' or tag == 'td':
                self.parts.append(' | ')
        self.depth += 1

    def handle_endtag(self, tag):
        self.depth -= 1
        if self.in_article and self.depth <= self.article_depth:
            self.in_article = False
            return
        if self.in_article:
            if self.current_tag and self.current_tag[-1] == tag:
                self.current_tag.pop()
            if tag in ('strong', 'b'):
                self.parts.append('**')
            elif tag in ('em', 'i'):
                self.parts.append('*')
            elif tag == 'code':
                self.parts.append('`')
            elif tag == 'pre':
                self.parts.append('\n```\n')

    def handle_data(self, data):
        if self.in_article:
            # Drop navigation-ish placeholder text
            if data.strip() in ('#',):
                return
            self.parts.append(data)

    def get_markdown(self) -> str:
        text = ''.join(self.parts)
        # Collapse runs of blanks; leave double newlines for paragraphs
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+\n', '\n', text)
        text = re.sub(r'\n +', '\n', text)
        return text.strip()


def slug_from_path(path: str) -> str:
    """`/docs/markdown/foo/bar.html` → `foo__bar`."""
    s = path.replace('/docs/markdown/', '').strip('/')
    s = s.replace('.html', '').replace('.md', '')
    s = s.replace('/', '__')
    return s or 'index'


def fetch(url: str, retries: int = 3, timeout: int = 20) -> bytes | None:
    headers = {'User-Agent': 'Mozilla/5.0 (biyingtong doc-crawler)'}
    req = urllib.request.Request(url, headers=headers)
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError) as e:
            if i == retries - 1:
                print(f'  FAILED {url}: {e}')
                return None
            time.sleep(1 + i)
    return None


def process_page(page: dict) -> tuple[str, bool, int]:
    path = page['path']
    title = page['title'] or path
    url = BASE_URL + '/quant' + path
    slug = slug_from_path(path)
    out_path = OUT_DIR / f'{slug}.md'

    if out_path.exists() and out_path.stat().st_size > 100:
        return (slug, True, out_path.stat().st_size)

    raw = fetch(url)
    if raw is None:
        return (slug, False, 0)

    try:
        html = raw.decode('utf-8')
    except UnicodeDecodeError:
        html = raw.decode('gbk', errors='replace')

    parser = ContentExtractor()
    parser.feed(html)
    body = parser.get_markdown()

    if len(body) < 50:
        return (slug, False, 0)

    md = f'# {title}\n\n> **Source**: {url}\n> **Path**: `{path}`\n\n{body}\n'
    out_path.write_text(md, encoding='utf-8')
    return (slug, True, len(md))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))

    all_pages = []
    for cat_key, cat in manifest['categories'].items():
        for page in cat['pages']:
            all_pages.append({**page, 'category': cat_key})

    print(f'Processing {len(all_pages)} pages to {OUT_DIR}')

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(process_page, p): p for p in all_pages}
        ok = fail = 0
        total_bytes = 0
        for fut in as_completed(futures):
            slug, success, size = fut.result()
            if success:
                ok += 1
                total_bytes += size
                print(f'  [OK] {slug} ({size} B)')
            else:
                fail += 1
                print(f'  [FAIL] {slug}')

    print(f'\nDone: {ok} ok, {fail} failed, {total_bytes:,} bytes total')


if __name__ == '__main__':
    main()
