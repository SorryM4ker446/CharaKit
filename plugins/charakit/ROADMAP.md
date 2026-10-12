# CharaKit roadmap

0.1.32: Reports, HTML reviews and PNG previews share fixed-text catalogs and language resolution, defaulting to zh-CN with explicit English support. PNG previews add --language; regional tags resolve consistently. Partial custom names, legacy PNG status overrides and complete custom HTML UI files remain supported. Chinese/English key and format-placeholder coverage is tested; recorded observations and machine identifiers retain their authored text.

0.1.31: Poses adds hand on chest, clasped hands in front, hands behind the back and crossed arms. New actions bind left/right arm placement, contacts and front/back overlaps to preparation, contracts, redraws, human revisions, reports and exports. Two-arm actions use anatomical side `both`; hand on chest uses `left`/`right`. Original briefs and historical records stay unchanged. This stage expands the functional workflow; generated-art quality remains a separate follow-up.

0.1.30: Initial pools can restart their third attempt from the source after two target-achieving candidates repeat non-improving identity/protection failures. Failed candidate images are excluded from that call while failure evidence, action/design definitions and all scoped references remain bound. Existing pools and human revisions keep their baseline strategies. Real-image improvement still needs validation.

0.1.29: Poses adds four static dialogue presets: natural standing, one hand on hip, raised-hand greeting and palm-up explanation. Independent schema 3.0 projects bind explicit anatomical sides, action permissions, protected designs, optional game anchors and pose-only references. Pose-specific anatomy/support/contact/occlusion/framing checks reuse the five dimensions, fixed redraw budget, actual human decisions, revision continuity/source recheck and raw PNG delivery. Human pages default to full images; focused common-canvas inspection boxes must be chosen from actual moved positions. Workflow validation does not establish real generated-pose quality or game switching stability; those remain to be evaluated.

0.1.28: shared human-revision baselines preserve successful edits on the chosen version and separately recheck still-protected regions against the immutable source. New plans bind edit-target-first inputs, explicit restoration scopes and two evidence-backed protection criteria. Human revision previews default to before/after comparison with switchable original context and task-based localized detail regions. These rules apply to all current editing types and future modules; legacy budgets/history stay unchanged. No automatic similarity model, mask or module coupling is added.

0.1.27: full-canvas human overviews remain visible alongside optional whole-face/target detail comparisons. The viewer starts fitted, supports synchronized source comparison and preserves feedback while inspecting versions. Candidate-level actions fill drafts; copying feedback supplements JSON downloads without automatic submission. Recorded inspection regions follow human corrections and appear as separate source-versus-accepted detail PNGs in final reports. Old packets and custom-language interfaces remain compatible; no PDF, generation backend or module coupling is added.

0.1.26: all current and future modules use complete-batch human presentation by default. Show every readable candidate, including failed earlier rounds; keep the recommendation and internal findings separate from selection. Explicit user restrictions and unavailable files have visible omission reasons. Human feedback can target any displayed version for a concrete correction, while delivery gates, fixed budgets and independent module state remain intact. Refreshing historical packets preserves their original candidate aliases; new packets apply the new default.

0.1.25: [scoped edit references](references/edit-references.md) apply to Expressions, explicit mouth states, all Outfits modes and every future editing module. Immutable snapshots, recorded editable scopes, per-reference target checks and actual input bindings persist through internal redraws, human revisions, review pages and delivery. New modules must define their reference scopes and pass the same budget/integrity/review gates; this does not automatically link modules or implement planned Poses.

0.1.23: new requests and human-correction batches default to at most three image-tool attempts. Internal failures trigger evidence-directed redraws; full passage or exhaustion precedes human review. Explicit smaller limits, old pools, historical assessments, module independence and final delivery gates remain intact. Workflow validation does not establish lower user revision rates.

New requests use [candidate selection and human review](references/candidate-review.md): normally at most three total attempts, evidence-directed redraws until all required gates pass or the budget is spent, rubric 1.2 with five evidence-linked dimensions, and an anonymous review page with chat/JSON feedback. Actual user acceptance precedes final PNG/report and requested ZIP packaging. Legacy sampling/refinement descriptions below apply only to existing historical records. Historical scores remain unchanged; generation-quality gains are not yet established.

CharaKit provides expression editing, garment and full-outfit editing, accessory/prop workflows and eight static dialogue poses. Modules stay independent: users can manually use an output PNG as a new source without automatic invocation or shared state. Complex poses and object manipulation remain planned.

Helper 0.1.22 adds `prop_edit` within Outfits, with explicit add/remove/replace actions, contact/occlusion/reconstruction/anatomy checks, schema 1.5 and the existing human-review/revision flow. Actual object-edit quality still needs visual evaluation. Helper 0.1.21 adds full-outfit replacement with an explicit clothing inventory, component findings and ensemble checks, reusing candidate selection and human revision. Real outfit generation quality remains to be evaluated. Helper 0.1.20 links a specific correction to the user-chosen candidate, preserves prior constraints and history, and requires fresh internal/human review before delivery. Task recovery and comparisons against direct image-tool conversation are outside this phase; product acceptance concerns this plugin's own behavior and actual user feedback.

| Module | Status | Scope |
| --- | --- | --- |
| CharaKit Expressions | Available | Twelve fixed expression presets, static mouth-open/closed states, revisions, comparisons, and PNG exports |
| CharaKit Outfits | Available | Garments, full outfits and accessory/prop edits; explicit boundaries, mode-specific reviews, human revisions and PNG exports |
| CharaKit Poses | Available | Eight static dialogue poses, arm/contact/overlap definitions, scoped references, bounded redraws, human revisions and PNG exports; real art quality pending validation |

Expressions and the recolor/replacement workflows in Outfits are available. Replacement workflow tests do not establish generated-art quality; real replacement preservation still requires validation. Module IDs and availability are listed in [modules.json](modules.json).

## Planned direction

All future development follows the shared [quality-first baseline and internal delivery review](references/quality-review.md). Current modules record assistant rubric observations and enforce technical/quality/fidelity gates before delivery. This filters candidates; improved generation fidelity and a lower user revision rate still need validation against real feedback.

1. Improve expression consistency, canvas alignment, and transparent edges for use in games.
2. Validate expression and static mouth-state quality on actual artwork. Independent gaze states are deferred while Outfits is the current development priority.
3. Evaluate quality-focused, domain-specific editing instructions using one complete source by default, optional target references, and enlarged checks of target and protected regions on actual artwork before expanding garment edits.
4. Validate single-garment replacement on actual artwork, including upper/lower garments, necessary coverage changes and protected equipment. Version 0.1.18 adds compact repair prompts and a source-based third-round strategy after stalled protection checks; legacy cases retain that strategy. Full outfit base workflows are now implemented; validate their actual design adherence and protection.
5. Continue functional pose development with hand near chin, touching hair and restrained forward lean, followed by existing-object interaction as needed. Larger turns, sitting and leaning against support remain later candidates. Consolidated real-art quality work follows the chosen functional scope; retain anatomy, contact, protected-design and game-anchor gates throughout development. Eight implemented actions still need actual artwork and human-feedback validation.
6. Validate accessory/prop design adherence, stable contacts, removal reconstruction and protected-region preservation on actual artwork. Automatic outfit/expression linking is outside the current scope.

Plans may change based on image quality and practical game use. Planned features have no committed release dates and will be marked available only after implementation and validation.

Non-target repainting is a known unresolved limitation of the current recolor workflow. Prompt/reference changes do not enforce pixel preservation. Research into a backend exposing native regional controls, potentially through ComfyUI/MCP, is deferred; no such integration is implemented, and its preservation behavior would need validation. Final artwork editing remains the image tool's responsibility.

## Scope

Each editing mode aims to change only the requested features while preserving character identity, facial detail, original style, unrelated design details, and overall visual harmony.

Apply the shared [editing boundaries](references/edit-boundaries.md) throughout prompt construction, generation inputs, comparison, and revision. Each active domain specifies allowed properties, invariants within the target, and protected interfaces/remainder; concrete instructions come from the request and source. Future outfit and pose modes must define these permissions before implementation, including only interface changes necessary for the requested operation. Domain guidance does not create new callable modules.

CharaKit remains a lightweight Codex plugin that produces complete character images. Animation, Live2D parts, and rigging are outside this roadmap.
