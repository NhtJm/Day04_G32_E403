---
name: hn_top
track: team_new
kind: live_api
provider: Hacker News (Algolia)
requires_env: []
inputs: [query, sort_by, limit]
outputs: [items]
side_effect: false
---
# hn_top

Searches Hacker News stories through the public Algolia endpoint. No API key
and no quota registration required.

## When to use

- The user names Hacker News / HN explicitly.
- The user wants what the developer community is discussing or upvoting.
- The user wants story points and comment counts, not general web coverage.

## When NOT to use

- General web news → `lookup` with `topic="news"`.
- Posts from X/Twitter → `social_search` or `timeline`.
- Reading one specific URL the user already gave → `fetch`.

## Arguments

| Arg | Convention |
|---|---|
| `query` | Topic keyword only (`AI`, `rust`). Empty string returns the current front page. |
| `sort_by` | `top` ranks by popularity (default). `latest` ranks by recency — use for "mới nhất". |
| `limit` | Clamped to 1–20; defaults to 5. |

## Output

`items[]` with `title`, `url`, `source`, `summary`, `points`, `num_comments`,
`date`, `discussion_url`. `url` falls back to the HN discussion page for
text-only "Ask HN" posts. Errors return `{"tool", "error", "message"}`.
