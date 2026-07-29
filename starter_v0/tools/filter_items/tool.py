from __future__ import annotations

from typing import Any

from tools._shared import domain, err, fold_text


def _matches_keyword(item: dict[str, Any], keyword: str) -> bool:
    if not keyword:
        return True
    haystack = " ".join([
        str(item.get("title") or ""),
        str(item.get("summary") or ""),
        str(item.get("source") or ""),
    ])
    return fold_text(keyword) in fold_text(haystack)


def _matches_source(item: dict[str, Any], source: str) -> bool:
    if not source:
        return True
    src = str(item.get("source") or domain(str(item.get("url") or "")))
    return fold_text(source) in fold_text(src)


def filter_result_items(
    items: list[dict[str, Any]] | None = None,
    keyword: str = "",
    source: str = "",
    max_items: int = 5,
) -> dict[str, Any]:
    try:
        items = items or []
        limit = max(1, int(max_items or 5))
        filtered: list[dict[str, Any]] = []

        for item in items:
            normalized = dict(item)
            if not normalized.get("source") and normalized.get("url"):
                normalized["source"] = domain(normalized["url"])
            if _matches_keyword(normalized, keyword) and _matches_source(normalized, source):
                filtered.append(normalized)
            if len(filtered) >= limit:
                break

        return {
            "tool": "filter_result_items",
            "keyword": keyword,
            "source": source,
            "items": filtered,
            "item_count": len(filtered),
        }
    except Exception as exc:
        return err("filter_result_items", exc)
