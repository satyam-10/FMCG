"""
The corroboration search tool.

Wraps Tavily. If no TAVILY_API_KEY is set, returns an empty result so the
pipeline degrades gracefully to relying on cluster size alone. This keeps the
demo runnable without a search key, at the cost of thinner corroboration.
"""

from __future__ import annotations

import os


def search(query: str, max_results: int = 3) -> list[str]:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        return []
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=key)
        resp = client.search(query=query, max_results=max_results)
        return [
            f"{r.get('title', '')} ({r.get('url', '')})"
            for r in resp.get("results", [])
        ]
    except Exception as exc:  # a failed search must not crash the pipeline
        return [f"[search error: {exc}]"]
