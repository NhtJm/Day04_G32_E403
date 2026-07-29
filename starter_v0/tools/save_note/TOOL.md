---
name: save_note
track: team_new
kind: local_write
provider: local filesystem
requires_env: []
inputs: [title, content, confirmed]
outputs: [status, path, chars_written]
side_effect: true
---
# save_note

Writes a finished digest to `notes/<slug>.md` inside `starter_v0/`.

## Confirmation boundary

This tool has a side effect, so it mirrors the `send` contract:

- `confirmed=false` (default) → returns `status="needs_confirmation"` and the
  path it *would* write. Nothing touches disk.
- `confirmed=true` → writes the file and returns `status="saved"`.

The agent must call `clarify` with `response_type="yes_no"` and get an explicit
yes **before** calling this tool with `confirmed=true`. "Lưu lại giúp mình" on
its own is a request, not a confirmation.

## When to use

- The user asks to save/store/archive a digest locally.
- Local-only alternative to `send` when there is no Telegram channel.

## When NOT to use

- Publishing to an external channel → `send`.
- Only formatting text for display → `format`.

## Arguments

| Arg | Convention |
|---|---|
| `title` | Short human title; slugified to the filename (lowercase, `-` separated, ≤60 chars). |
| `content` | Markdown body. Must be non-empty and ≤50,000 chars. |
| `confirmed` | Only `true` after an explicit user yes. |

## Safety

`_slugify` strips every character outside `[a-z0-9-]`, so a hostile title such
as `../../.env` collapses to `env` and the write stays inside `notes/`.
`notes/` is gitignored.
