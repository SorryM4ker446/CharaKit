# CharaKit roadmap

CharaKit currently provides expression editing. Outfit and pose editing are planned extensions.

| Module | Status | Scope |
| --- | --- | --- |
| CharaKit Expressions | Available | Twelve fixed expression presets, static mouth-open/closed states, revisions, comparisons, and PNG exports |
| CharaKit Outfits | Planned | Clothing edits and full outfit replacement |
| CharaKit Poses | Planned | Static pose and action edits |

Only Expressions is available to use. Module IDs and availability are listed in [modules.json](modules.json).

## Planned direction

1. Improve expression consistency, canvas alignment, and transparent edges for use in games.
2. Validate expression and static mouth-state quality on actual artwork; add independently selectable gaze states when needed.
3. Add clothing recoloring and small accessory edits.
4. Expand to full outfit replacement.
5. Introduce simple static pose changes before more complex action poses.
6. Support requested combinations of outfits, poses, and expressions.

Plans may change based on image quality and practical game use. Planned features have no committed release dates and will be marked available only after implementation and validation.

## Scope

Each editing mode aims to change only the requested features while preserving character identity, facial detail, original style, unrelated design details, and overall visual harmony.

CharaKit remains a lightweight Codex plugin that produces complete character images. Animation, Live2D parts, and rigging are outside this roadmap.
