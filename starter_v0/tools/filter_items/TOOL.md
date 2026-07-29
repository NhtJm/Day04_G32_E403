---
name: filter_items
track: bonus
kind: local_formatter
requires_env: []
inputs: [items, keyword, source, max_items]
outputs: [items, item_count]
side_effect: false
---
# filter_items

Filters an existing list of items by keyword or source.
Use only after another tool has already returned `items`.
