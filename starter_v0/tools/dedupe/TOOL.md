---
name: dedupe
track: team_new
kind: local_pure
provider: none
requires_env: []
inputs: [items, key]
outputs: [items, removed, kept_count, removed_count]
side_effect: false
---
# dedupe

Removes duplicate items from a list the agent **already has** from previous
tool results. Pure local function — no network, no API key, no quota.

## When to use

- After combining results from two sources (e.g. `lookup` + `social_search`,
  or `lookup` + `hn_top`) where the same article can appear twice.
- Before `format`, so the digest does not repeat a story.

## When NOT to use

- To *find* items — this tool never fetches anything. It only filters a list
  the agent already holds.
- On a single-source result set that cannot contain duplicates. Calling it
  there is an unnecessary tool call.

## Arguments

| Arg | Convention |
|---|---|
| `items` | The list of item objects from earlier tool results. |
| `key` | `url` (default) matches on canonical URL. `title` matches on normalized title. `both` treats an item as duplicate if either matches. |

## Matching rules

URLs are canonicalized before comparison: scheme dropped, `www.` stripped,
trailing `/` removed, and tracking params (`utm_*`, `fbclid`, `gclid`, `ref`)
discarded. So these three collapse to one item:

```
https://www.example.com/post/
http://example.com/post
https://example.com/post?utm_source=x
```

Titles are compared with `fold_text` (lowercase, Vietnamese diacritics removed).

Items with neither a `url` nor a `title` are kept, never silently dropped.
