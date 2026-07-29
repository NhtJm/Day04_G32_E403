---
name: dedupe_items
track: bonus
kind: local_formatter
requires_env: []
inputs: [items, max_items]
outputs: [items, removed_count]
side_effect: false
---
# dedupe_items

Removes duplicate or near-duplicate items from an existing list of results.
Use only after another tool has already returned `items`.
