"""
Stage 1: Ingest.

Fetch recent articles from Google News RSS. RSS is free, needs no key, and will
not surprise a live demo with a rate limit. Queries are built dynamically from
user-selected categories and regions so the newsletter stays focused.
"""

from __future__ import annotations

import time
import urllib.parse

import feedparser

from .state import Article

# Category -> representative search terms
CATEGORY_TERMS: dict[str, list[str]] = {
    "All FMCG": ["FMCG", "consumer goods", "packaged food"],
    "Food and Beverage": ["food brand", "beverage company", "packaged food"],
    "Personal Care": ["personal care brand", "cosmetics brand", "beauty brand"],
    "Household": ["household products brand", "home care brand"],
    "Dairy": ["dairy company", "dairy brand"],
    "D2C / Startup": ["D2C brand", "consumer startup", "DTC brand"],
}

# Top deal signal terms (kept short to limit query volume)
DEAL_TERMS = ["acquisition", "merger", "funding round", "stake"]

# Region -> suffixes appended to each query
REGION_SUFFIXES: dict[str, list[str]] = {
    "Global": [""],
    "India": [" India"],
    "US": [" US"],
    "Europe": [" Europe"],
    "Southeast Asia": [" Southeast Asia"],
}

RSS_TEMPLATE = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


def build_queries(
    categories: list[str] | None = None,
    regions: list[str] | None = None,
) -> list[str]:
    """Build a deduplicated query list from user-selected categories and regions."""
    categories = categories or ["All FMCG"]
    regions = regions or ["Global"]

    queries: list[str] = []
    for cat in categories:
        terms = CATEGORY_TERMS.get(cat, CATEGORY_TERMS["All FMCG"])
        for term in terms:
            for deal in DEAL_TERMS[:2]:  # top 2 deal terms keeps volume manageable
                for region in regions:
                    for suffix in REGION_SUFFIXES.get(region, [""]):
                        queries.append(f"{term} {deal}{suffix}")

    # Dedupe while preserving order
    return list(dict.fromkeys(queries))


def _source_name(entry) -> str:
    src = entry.get("source")
    if isinstance(src, dict):
        return src.get("title", "")
    if src is not None:
        return getattr(src, "title", "") or str(src)
    return ""


def ingest(
    queries: list[str] | None = None,
    categories: list[str] | None = None,
    regions: list[str] | None = None,
    per_query: int = 15,
) -> list[Article]:
    """Fetch articles. Accepts either explicit queries or category/region selections."""
    if queries is None:
        queries = build_queries(categories, regions)

    articles: list[Article] = []
    seen_urls: set[str] = set()

    for q in queries:
        url = RSS_TEMPLATE.format(q=urllib.parse.quote(q))
        feed = feedparser.parse(url)
        for entry in feed.entries[:per_query]:
            link = entry.get("link", "")
            if not link or link in seen_urls:
                continue
            seen_urls.add(link)
            articles.append(
                Article(
                    title=entry.get("title", "").strip(),
                    url=link,
                    source=_source_name(entry),
                    published=entry.get("published", ""),
                    summary=entry.get("summary", "").strip(),
                )
            )
        time.sleep(0.3)  # be polite to the feed

    return articles