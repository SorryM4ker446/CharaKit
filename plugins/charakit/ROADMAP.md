# CharaKit roadmap

CharaKit currently provides expression editing, recoloring and replacement of one specified existing garment. Full outfit replacement and pose editing are planned extensions.

| Module | Status | Scope |
| --- | --- | --- |
| CharaKit Expressions | Available | Twelve fixed expression presets, static mouth-open/closed states, revisions, comparisons, and PNG exports |
| CharaKit Outfits | Available | One-garment recoloring/replacement workflows, edit boundaries, mode-specific reviews, comparisons and PNG exports; full outfit replacement planned |
| CharaKit Poses | Planned | Static pose and action edits |

Expressions and the recolor/replacement workflows in Outfits are available. Replacement workflow tests do not establish generated-art quality; real replacement preservation still requires validation. Module IDs and availability are listed in [modules.json](modules.json).

## Planned direction

All future development follows the shared [quality-first baseline and internal delivery review](references/quality-review.md). Current modules record assistant rubric observations and enforce technical/quality/fidelity gates before delivery. This filters candidates; improved generation fidelity and a lower user revision rate still need validation against real feedback.

1. Improve expression consistency, canvas alignment, and transparent edges for use in games.
2. Validate expression and static mouth-state quality on actual artwork. Independent gaze states are deferred while Outfits is the current development priority.
3. Evaluate quality-focused, domain-specific editing instructions using one complete source by default, optional target references, and enlarged checks of target and protected regions on actual artwork before expanding garment edits.
4. Validate single-garment replacement on actual artwork (such as stockings to socks and boots to shoes), including necessary coverage changes and protected equipment, before expanding to full outfit replacement.
5. Introduce simple static pose changes before more complex action poses.
6. Support requested combinations of outfits, poses, and expressions.

Plans may change based on image quality and practical game use. Planned features have no committed release dates and will be marked available only after implementation and validation.

Non-target repainting is a known unresolved limitation of the current recolor workflow. Prompt/reference changes do not enforce pixel preservation. Research into a backend exposing native regional controls, potentially through ComfyUI/MCP, is deferred; no such integration is implemented, and its preservation behavior would need validation. Final artwork editing remains the image tool's responsibility.

## Scope

Each editing mode aims to change only the requested features while preserving character identity, facial detail, original style, unrelated design details, and overall visual harmony.

Apply the shared [editing boundaries](references/edit-boundaries.md) throughout prompt construction, generation inputs, comparison, and revision. Each active domain specifies allowed properties, invariants within the target, and protected interfaces/remainder; concrete instructions come from the request and source. Future outfit and pose modes must define these permissions before implementation, including only interface changes necessary for the requested operation. Domain guidance does not create new callable modules.

CharaKit remains a lightweight Codex plugin that produces complete character images. Animation, Live2D parts, and rigging are outside this roadmap.
