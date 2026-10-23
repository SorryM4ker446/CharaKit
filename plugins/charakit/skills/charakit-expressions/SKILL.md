---
name: charakit-expressions
description: Generate full visual novel character expressions and static mouth-open or mouth-closed variants from existing artwork while preserving facial detail, original style, design, and visual harmony. Use for expression editing, individual revisions, comparison previews, version selection, and PNG exports.
---

# CharaKit Expressions

Apply the shared [repeatable QA methods](../../references/qa-methods.md) during internal review. Inspect each requested static expression or mouth state at normal display sizes as well as full-face and protected-region details. Preview switching helps compare variants; file checks and actual user acceptance remain distinct.

The available expression module of the CharaKit plugin. Deliver complete, independent character images that a game can switch between. Edit the user's source artwork and change only the requested facial expression.

Read the shared [editing boundaries](../../references/edit-boundaries.md) when defining a request and inspecting a result. Distinguish allowed expression movements from facial design invariants; a mouth-only request protects the established emotion and non-mouth features. Protect every unrequested component/property, and derive concrete boundaries and comparison regions from the actual source rather than a previous test character.

Support twelve fixed expression presets and independently selectable static mouth states. Read [expression-guidelines.md](references/expression-guidelines.md) to map a request to a preset and shape its prompt; `presets` lists expressions and mouth states. For mouth-open/closed requests or revisions, read [mouth-states.md](references/mouth-states.md). Generate only requested expressions and states. Gaze and emotion-specific closed-eye states remain planned.

Garment editing, full-outfit bases and accessory/prop edits use the separate [CharaKit Outfits Skill](../charakit-outfits/SKILL.md). Static dialogue pose edits use [CharaKit Poses](../charakit-poses/SKILL.md). A resulting PNG can manually become this Skill's new source; modules do not share state or automatically invoke each other. Complex poses remain planned in [the module roadmap](../../ROADMAP.md). Keep expression projects and candidates separate.

## Candidate selection and human review

Human review defaults to all readable candidates in the current batch, including failures and earlier rounds. Recommendations stay separate and never preselect the user's decision. Failed versions can receive actual feedback and specific revision requests; final delivery still requires all gates. Do not restrict the view without an explicit user request and a recorded omission reason.

For optional expression or mouth reference images, follow the shared [scoped edit references](../../references/edit-references.md). Snapshot and bind their actual inputs, include a target check for every reference, and retain them in every internal redraw and human revision. This rule also governs future editing modules.

For every new request, follow [candidate selection and human review](../../references/candidate-review.md). Define source-grounded checks before generation, start a candidate pool before scoring, and use rubric 1.2 with five evidence-linked dimensions. Default to three total attempts per requested result, including the initial image. A requested output count is distinct from an image-tool attempt cap; honor an explicit smaller cap. If any of the five dimensions, domain checks or applicable fidelity checks fails or remains uncertain, redraw from the recorded findings and reassess every check. A total of 80 or more cannot override a dimension below 4/5. Stop on full internal passage or budget exhaustion; only then create the user review page, explaining unresolved issues when exhausted. Show an anonymous review page and inline candidates, collect actual user feedback, and only then deliver/package accepted eligible artwork. Chat replies are sufficient; do not demand a second approval or a feedback file. This workflow replaces sequential refinement for new work; old tracked cases retain [their original workflow](../../references/refinement.md).

Follow the reserved input strategy. New initial pools can use [source restart](../../references/candidate-review.md#restart-after-stalled-protection) after two target-achieving candidates repeat stalled identity/protection failures. The third call receives only the original and all already-bound scoped references; the failed candidate remains review evidence. Reapply the fixed expression/mouth requirements without inventing an absent candidate reference. Human revisions keep their chosen baseline.

For a specific correction after human review, follow the [linked human-revision procedure](../../references/candidate-review.md#continue-a-specific-human-correction). Use `revision-prepare` and `revision-import` to retain the actual chosen parent, original comment and protection checks. One correction starts a new default three-attempt internal review/redraw batch with fresh assessments; show the returned before/after comparison. Do not substitute the latest candidate or inherit acceptance.

## User language

- Respond in the language of the user's current request, or their explicitly preferred language. Follow a later language change without asking again.
- Apply this to progress updates, expression names, preview captions, quality explanations, limitations, revision discussions, delivery notes, and saved human-readable review notes.
- Write the generation prompt in the user's language unless they request another prompt language.
- English repository documentation does not set the conversation language. Do not answer in English merely because this Skill is written in English.
- Keep CLI arguments, JSON keys, expression IDs, filenames, and error/status codes stable. Explain their meaning in the user's language rather than changing machine-readable values.
- Before authoring prompts or review content, read and follow [task language](../../references/localization.md): identify the user's language, honor explicit preferences, persist it with `language-set`, and prepare/reuse a complete pack for any language without a built-in catalog. Author new content in that language and register it with `content-register`; translate historical prose only for display using `content-plan`. Reports, HTML and PNG inherit the saved language. Retain exact custom names through partial `--labels-file` overrides; handle fonts and text direction as described in the shared reference.

## Generation rules

- Inspect the source first. Prefer a single character with a clear front or slightly angled face. Preserve transparency for transparent artwork; do not assume an illustration with a background is a transparent sprite.
- Use the OpenAI image editing tool currently available in the Codex host. Follow its current reference-image, transparency, and file-saving requirements. If unavailable, explain the missing capability. This plugin has no external API integration and cannot select a hidden model through a prompt.
- Initial expressions use the immutable source as their primary reference. For human corrections, follow the shared [revision baseline rules](../../references/candidate-review.md#revision-baselines-and-task-based-inspection): edit the user-chosen version first, preserve successful changes, and separately recheck still-protected regions against the original. Use all returned references in their recorded order. Saved legacy plans retain their strategy.
- Preserve the **entire face**: eyes, eyebrows, nose, lips, contours, proportions, skin tone, shading, linework, and brushwork. Eyes are one part of this requirement. Allow necessary expression changes without redesigning, blurring, or simplifying facial features.
- Preserve the original style and character design: hair, ears, accessories, clothing, weapons, pose, proportions, composition, materials, and lighting. Make only the changes needed for the requested emotion; keep the expression harmonious with the whole illustration.
- Return the complete original framing. Do not deliver a face crop as the final asset, extract reusable facial parts, or composite a generated face onto the original. Subtle blush is appropriate for `shy`, and visible tears are part of `crying`, unless excluded by the user. Do not add these effects to other presets by default, or add emotion symbols, sweat drops, or text without a request.
- Adapt intensity and wording to the source and request.
- Build the prompt using the expression-specific structure in [expression-guidelines.md](references/expression-guidelines.md). Prioritize quality and faithful preservation over prompt length. Inherit source attributes instead of guessing or assigning iris/skin colors, and retain the detail needed to protect facial design/rendering and distinguish the emotion. Do not apply an Outfits color-only template or suppress every emotion to a slight change.
- Before submitting, compare the actual prompt with the source and request: no invented appearance attributes, required emotion effects present, and only the intended movements allowed. Check the first result of a larger set before reusing a shared description in the remaining prompts; correct a mistaken description in unsubmitted jobs without expanding the generation count.

## Save and check

Save each generated image as a candidate before checking it. Saving or displaying an image does not imply art approval.

Read and apply the shared [quality review and delivery policy](../../references/quality-review.md) for every generation/revision. New projects enable internal review by default; before generating into a legacy project, run `enable-quality`. Inspect actual comparisons, record five evidence-linked rubric 1.2 scores with `quality`, then use the anonymous review sheet for inspection and `deliver` only after actual user acceptance. Serious defects, uncertainty and technical failures other than nonblocking canvas mismatch block delivery independently of the total. This is assistant visual judgment with deterministic record validation, not an automatic objective identity metric. User acceptance stays separate.

Include the active `domain_review` checklist: `expression` checks emotion, facial design, nonface protection and rendering; an explicit open/closed candidate uses `mouth_state` and also checks the specified mouth state. Preserve established emotion for mouth-only edits; for combined requests inspect the requested emotion and state together. Record actual source-specific evidence for each item. Any failed/uncertain domain item blocks delivery regardless of global scores. Explain the failed module/component and visible deviation in the user's language, rather than reporting only a number.

- Use the user's destination, or `art-output/<character-key>/` in the workspace. Never put user artwork in the plugin installation directory.
- Preserve the original file and all candidate versions. The helper does not repaint, remove backgrounds, change alpha, or resize candidate images.
- Check decoding, PNG format, actual canvas dimensions, and background requirements. Record size mismatches as warnings without lowering visual scores or blocking acceptance, selection or PNG/ZIP export. Tell the user the source and actual sizes and that the files remain unchanged. Do not hide mismatches with stretching, tight crops, or automatic centering.
- Inspect both full images and enlarged **whole-face** comparisons. Check facial detail, style, design, and harmony at normal game display size; see [quality-checklist.md](references/quality-checklist.md).
- Keep full-image inspection and choose local views for the current edit and observed risks. Expression changes generally need a whole-face view; a focused correction can use a more specific localized region. Save a task-based `--inspection-file` for a revision or review, or use explicit `--face-box` / `--detail-box` for simple views. New revisions do not inherit every prior view. Source-protection inspection remains required without a human face menu. Accepted regions appear separately in final reports.
- Explain checks and visible problems in the user's language. Scripts verify file requirements and recorded rubric gates, not artistic fidelity. Use only inspected, attributed rubric scores; do not invent objective identity metrics or model identifiers.
- Explicit satisfaction or version selection is sufficient art feedback; do not request the same approval again. Unreviewed candidates remain `unreviewed`.
- The helper only sets `accepted` after technical checks pass. If a user likes a technically failed candidate, save their positive feedback separately and explain the remaining technical issue; do not erase their feedback or mark the technical check as passed. Such candidates remain available for inspection but cannot enter a formal export.

## Local helper

`scripts/studio.py` uses Python 3.11+, Pillow and fonttools, runs once, and exits. Resolve its absolute path from the actual installed Skill location. Keep the complete plugin including its shared `lib/studio_core.py` together. Use proper shell quoting for paths with spaces or Unicode.

File-management command reference (not the full generation workflow). Follow candidate-review.md for pool/review-sheet/human-feedback ordering; replace bracketed paths with actual paths:

```text
python <skill>/scripts/studio.py presets
python <skill>/scripts/studio.py init --project <output-dir> --source <source.png> --character <character-key>
python <skill>/scripts/studio.py add --project <output-dir> --expression angry --image <generated.png> --prompt-file <prompt.txt>
python <skill>/scripts/studio.py add --project <output-dir> --expression happy --mouth-state closed --image <generated-closed.png> --prompt-file <closed-prompt.txt>
python <skill>/scripts/studio.py add --project <output-dir> --expression happy --mouth-state open --image <generated-open.png> --prompt-file <open-prompt.txt>
python <skill>/scripts/studio.py preview --project <output-dir> --output <preview.png> --face-box <left> <top> <right> <bottom> --labels-file <labels.json>
python <skill>/scripts/studio.py quality --project <output-dir> --asset angry_v001 --assessment-file <assessment.json> --comparison <output-dir/preview/light.png> --comparison <output-dir/preview/dark.png>
python <skill>/scripts/studio.py review-sheet --project <output-dir> --asset angry_v001 --purpose user --face-box <left> <top> <right> <bottom>
# Wait for actual user feedback, then record its packet and alias.
python <skill>/scripts/studio.py human-feedback --project <output-dir> --feedback-file <feedback.json>
python <skill>/scripts/studio.py deliver --project <output-dir> --asset angry_v001
python <skill>/scripts/studio.py select --project <output-dir> --asset angry_v001
python <skill>/scripts/studio.py export --project <output-dir>
```

- `presets` returns expression IDs and `mouth_states` with English names and directions without a project. Translate names and directions for the user; fixed IDs remain unchanged.
- `init` snapshots the source and records canvas and background mode without overwriting a project. Existing images can be checked with `inspect` / `validate` without initialization.
- `add --mouth-state default|closed|open` preserves a candidate and returns a report even if technical checks fail. Omission uses `default`, which does not mean closed. Explicit states have independent versions; the first explicit state backs up schema 1.0 metadata and upgrades it to 1.1. A nonzero exit code does not mean the saved candidate should be discarded.
- `preview` shows full images on light, dark, or checker backgrounds. `--face-box` uses source-canvas pixel coordinates; magnification is for inspection only. Use repeated `--asset` arguments to compare chosen candidates side by side, including two candidates for one state. `--expression` and `--mouth-state` optionally filter candidates; an expression filter retains all its states and versions. Size mismatches are explicitly labeled, not corrected.
- `review` accepts a technically valid candidate and selects it for its expression and mouth state. `select` switches between accepted versions in that same state, preserving the other selections.
- `export` rechecks selected files and fingerprints and packages only accepted, technically valid PNGs with a manifest.
- Check for Pillow and fonttools before first use and install `requirements.txt` in the current environment if needed. No API key is involved.
- Operate sequentially within one character directory; multiple chats must not modify the same `run.json` concurrently.

## Revisions and delivery

For new generation and revision batches, use the candidate-pool and human-review workflow above. The [bounded refinement reference](../../references/refinement.md) applies only to existing `refinements` records; never reset those budgets or rewrite historical assessments. New pools use rubric 1.2 and the default three-attempt review/redraw policy (helper 0.1.23). Explicit smaller limits remain binding. Saved 1.0 pools and legacy refinements retain their original strategy and spent budgets.

Revise only the requested image; preserve other expressions and history. Use the new fixed-budget batch for an explicit revision request and review each candidate afresh; show it as a deliverable only after the internal gate passes. Report blocked results in text, unless the user requested inspection of failed/experimental images. No generation outside the recorded revision or attempt budget; do not retry indefinitely or silently regenerate images the user likes.

After internal evaluation, present the human review stage before final delivery. Once actual user acceptance is recorded and gates pass, finish with the shared [delivery report](../../references/delivery-report.md): show accepted full PNGs and final preview inline, and link the Markdown report. Complete already requested packaging without another permission question. If no candidate passes, provide a failure report and clearly labeled inspection candidates for user feedback; they are not final assets. Keep all prompts, findings, candidates and actual feedback.
