# CharaKit roadmap

0.1.27: full-canvas human overviews remain visible alongside optional whole-face/target detail comparisons. The viewer starts fitted, supports synchronized source comparison and preserves feedback while inspecting versions. Candidate-level actions fill drafts; copying feedback supplements JSON downloads without automatic submission. Recorded inspection regions follow human corrections and appear as separate source-versus-accepted detail PNGs in final reports. Old packets and custom-language interfaces remain compatible; no PDF, generation backend or module coupling is added.

0.1.26: all current and future modules use complete-batch human presentation by default. Show every readable candidate, including failed earlier rounds; keep the recommendation and internal findings separate from selection. Explicit user restrictions and unavailable files have visible omission reasons. Human feedback can target any displayed version for a concrete correction, while delivery gates, fixed budgets and independent module state remain intact. Refreshing historical packets preserves their original candidate aliases; new packets apply the new default.

0.1.25: [scoped edit references](references/edit-references.md) apply to Expressions, explicit mouth states, all Outfits modes and every future editing module. Immutable snapshots, recorded editable scopes, per-reference target checks and actual input bindings persist through internal redraws, human revisions, review pages and delivery. New modules must define their reference scopes and pass the same budget/integrity/review gates; this does not automatically link modules or implement planned Poses.

0.1.23: new requests and human-correction batches default to at most three image-tool attempts. Internal failures trigger evidence-directed redraws; full passage or exhaustion precedes human review. Explicit smaller limits, old pools, historical assessments, module independence and final delivery gates remain intact. Workflow validation does not establish lower user revision rates.

New requests use [candidate selection and human review](references/candidate-review.md): normally at most three total attempts, evidence-directed redraws until all required gates pass or the budget is spent, rubric 1.2 with five evidence-linked dimensions, and an anonymous review page with chat/JSON feedback. Actual user acceptance precedes final PNG/report and requested ZIP packaging. Legacy sampling/refinement descriptions below apply only to existing historical records. Historical scores remain unchanged; generation-quality gains are not yet established.

CharaKit provides expression editing, single-garment editing, full-outfit bases and accessory/prop add/remove/replace workflows. Expressions stays independent: users can manually use an output PNG as a new source without automatic invocation or shared state. Pose editing remains planned.

Helper 0.1.22 adds `prop_edit` within Outfits, with explicit add/remove/replace actions, contact/occlusion/reconstruction/anatomy checks, schema 1.5 and the existing human-review/revision flow. Actual object-edit quality still needs visual evaluation. Helper 0.1.21 adds full-outfit replacement with an explicit clothing inventory, component findings and ensemble checks, reusing candidate selection and human revision. Real outfit generation quality remains to be evaluated. Helper 0.1.20 links a specific correction to the user-chosen candidate, preserves prior constraints and history, and requires fresh internal/human review before delivery. Task recovery and comparisons against direct image-tool conversation are outside this phase; product acceptance concerns this plugin's own behavior and actual user feedback.

| Module | Status | Scope |
| --- | --- | --- |
| CharaKit Expressions | Available | Twelve fixed expression presets, static mouth-open/closed states, revisions, comparisons, and PNG exports |
| CharaKit Outfits | Available | Garments, full outfits and accessory/prop edits; explicit boundaries, mode-specific reviews, human revisions and PNG exports |
| CharaKit Poses | Planned | Static pose and action edits |

Expressions and the recolor/replacement workflows in Outfits are available. Replacement workflow tests do not establish generated-art quality; real replacement preservation still requires validation. Module IDs and availability are listed in [modules.json](modules.json).

## Planned direction

All future development follows the shared [quality-first baseline and internal delivery review](references/quality-review.md). Current modules record assistant rubric observations and enforce technical/quality/fidelity gates before delivery. This filters candidates; improved generation fidelity and a lower user revision rate still need validation against real feedback.

1. Improve expression consistency, canvas alignment, and transparent edges for use in games.
2. Validate expression and static mouth-state quality on actual artwork. Independent gaze states are deferred while Outfits is the current development priority.
3. Evaluate quality-focused, domain-specific editing instructions using one complete source by default, optional target references, and enlarged checks of target and protected regions on actual artwork before expanding garment edits.
4. Validate single-garment replacement on actual artwork, including upper/lower garments, necessary coverage changes and protected equipment. Version 0.1.18 adds compact repair prompts and a source-based third-round strategy after stalled protection checks; legacy cases retain that strategy. Full outfit base workflows are now implemented; validate their actual design adherence and protection.
5. Introduce simple static pose changes before more complex action poses.
6. Validate accessory/prop design adherence, stable contacts, removal reconstruction and protected-region preservation on actual artwork. Automatic outfit/expression linking is outside the current scope.

Plans may change based on image quality and practical game use. Planned features have no committed release dates and will be marked available only after implementation and validation.

Non-target repainting is a known unresolved limitation of the current recolor workflow. Prompt/reference changes do not enforce pixel preservation. Research into a backend exposing native regional controls, potentially through ComfyUI/MCP, is deferred; no such integration is implemented, and its preservation behavior would need validation. Final artwork editing remains the image tool's responsibility.

## Scope

Each editing mode aims to change only the requested features while preserving character identity, facial detail, original style, unrelated design details, and overall visual harmony.

Apply the shared [editing boundaries](references/edit-boundaries.md) throughout prompt construction, generation inputs, comparison, and revision. Each active domain specifies allowed properties, invariants within the target, and protected interfaces/remainder; concrete instructions come from the request and source. Future outfit and pose modes must define these permissions before implementation, including only interface changes necessary for the requested operation. Domain guidance does not create new callable modules.

CharaKit remains a lightweight Codex plugin that produces complete character images. Animation, Live2D parts, and rigging are outside this roadmap.
