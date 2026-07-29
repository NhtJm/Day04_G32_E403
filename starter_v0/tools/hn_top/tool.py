from __future__ import annotations

import os
from typing import Any

import requests

from tools._shared import TIMEOUT, domain, err

ALGOLIA_BASE = "https://hn.algolia.com/api/v1"


def hacker_news_top(query: str = "", sort_by: str = "top", limit: int = 5) -> dict[str, Any]:
    """Search Hacker News stories via the public Algolia API (no API key needed)."""
    try:
        limit = max(1, min(int(limit or 5), 20))
        if sort_by not in {"top", "latest"}:
            raise ValueError(f"sort_by must be 'top' or 'latest', got {sort_by!r}")

        endpoint = "search" if sort_by == "top" else "search_by_date"
        params: dict[str, Any] = {"tags": "story", "hitsPerPage": limit}
        if query:
            params["query"] = query

        response = requests.get(
            f"{ALGOLIA_BASE}/{endpoint}",
            params=params,
            headers={"User-Agent": os.getenv("ARXIV_USER_AGENT", "AI20k-Day04-Research-Agent/1.0")},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        hits = response.json().get("hits", [])

        items = []
        for hit in hits:
            story_id = hit.get("objectID")
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
            items.append({
                "title": hit.get("title") or hit.get("story_title"),
                "url": url,
                "source": domain(url) or "news.ycombinator.com",
                "summary": f"{hit.get('points') or 0} points, {hit.get('num_comments') or 0} comments",
                "points": hit.get("points"),
                "num_comments": hit.get("num_comments"),
                "date": hit.get("created_at"),
                "discussion_url": f"https://news.ycombinator.com/item?id={story_id}",
            })
        return {"tool": "hacker_news_top", "query": query, "sort_by": sort_by, "items": items}
    except Exception as exc:
        return err("hacker_news_top", exc)
