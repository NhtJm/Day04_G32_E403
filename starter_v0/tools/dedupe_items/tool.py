from __future__ import annotations

from typing import Any

from tools._shared import domain, err, fold_text


def _item_key(item: dict[str, Any]) -> tuple[str, str]:
    url = (item.get("url") or "").strip().lower()
    title = fold_text((item.get("title") or "").strip())
    if url:
        return ("url", url)
    return ("title", title)


def remove_duplicate_items(items: list[dict[str, Any]] | None = None, max_items: int = 10) -> dict[str, Any]:
    try:
        items = items or []
        limit = max(1, int(max_items or 10))
        seen: set[tuple[str, str]] = set()
        deduped: list[dict[str, Any]] = []
        removed_count = 0

        for item in items:
            normalized = dict(item)
            if not normalized.get("source") and normalized.get("url"):
                normalized["source"] = domain(normalized["url"])
            key = _item_key(normalized)
            if key in seen:
                removed_count += 1
                continue
            seen.add(key)
            deduped.append(normalized)
            if len(deduped) >= limit:
                break

        return {
            "tool": "remove_duplicate_items",
            "items": deduped,
            "kept_count": len(deduped),
            "removed_count": removed_count,
        }
    except Exception as exc:
        return err("remove_duplicate_items", exc)
