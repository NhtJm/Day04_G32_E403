from __future__ import annotations

from typing import Any
from urllib.parse import urlparse, urlunparse

from tools._shared import err, fold_text

TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "ref", "ref_src")


def _canonical_url(url: str) -> str:
    """Strip scheme, www, tracking params and trailing slash so the same article matches."""
    try:
        parsed = urlparse(url.strip())
        if not parsed.netloc:
            return url.strip().lower()
        query = "&".join(
            part for part in parsed.query.split("&")
            if part and not part.lower().startswith(TRACKING_PREFIXES)
        )
        netloc = parsed.netloc.lower().removeprefix("www.")
        path = parsed.path.rstrip("/")
        return urlunparse(("", netloc, path, "", query, "")).lstrip("/")
    except Exception:
        return url.strip().lower()


def dedupe_items(items: list[dict[str, Any]] | None = None, key: str = "url") -> dict[str, Any]:
    """Remove duplicate research items already collected from other tools."""
    try:
        items = items or []
        if key not in {"url", "title", "both"}:
            raise ValueError(f"key must be 'url', 'title' or 'both', got {key!r}")

        kept: list[dict[str, Any]] = []
        removed: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in items:
            if not isinstance(item, dict):
                removed.append({"item": item, "reason": "not_an_object"})
                continue
            fingerprints = []
            if key in {"url", "both"} and item.get("url"):
                fingerprints.append("u:" + _canonical_url(str(item["url"])))
            if key in {"title", "both"} and item.get("title"):
                fingerprints.append("t:" + fold_text(str(item["title"])))
            if not fingerprints:
                # Nothing to compare on — keep it rather than silently dropping data.
                kept.append(item)
                continue
            if any(fingerprint in seen for fingerprint in fingerprints):
                removed.append({"title": item.get("title"), "url": item.get("url"), "reason": "duplicate"})
                continue
            seen.update(fingerprints)
            kept.append(item)

        return {
            "tool": "dedupe_items",
            "key": key,
            "input_count": len(items),
            "kept_count": len(kept),
            "removed_count": len(removed),
            "items": kept,
            "removed": removed,
        }
    except Exception as exc:
        return err("dedupe_items", exc)
