---
name: charakit-poses
description: Edit a single visual novel character into natural standing, one hand on hip, a raised-hand greeting or a palm-up explanation while preserving identity, expression, clothing design and original style. Use for these static dialogue poses, pose references, human-guided revisions, review previews and PNG exports.
---

# CharaKit Poses

Create a complete static illustration from an existing single-character source. The first version supports `natural_standing`, `hand_on_hip`, `wave` and `palm_up`. Read the [pose guide](references/pose-guide.md) to define the action and distinguish permitted movement from protected design. Larger turns, sitting, leaning, object manipulation, combat, animation and rigging remain deferred. Pure clothing/object edits use [Outfits](../charakit-outfits/SKILL.md); expression changes use [Expressions](../charakit-expressions/SKILL.md). Keep projects and state independent; users can manually use an exported PNG as another module's source.

## Define and prepare

Inspect the actual full source and any references before defining permissions. Resolve the requested side, hand orientation, amplitude, other arm, existing asymmetry and visible contacts from the request and source. `left` and `right` always mean the character's anatomical side, not the viewer's side; use `none` for natural standing. Clarify only meaningful unresolved choices or conflicts, such as a requested free-hand gesture while that hand holds an object. The first version preserves objects and does not silently remove, replace or add them.

Keep the current emotion, mouth state, gaze and facial design. A greeting does not authorize a smile; a hand on hip does not authorize anger. Preserve hair and clothing designs, equipment, body proportions, rendering, canvas and background. Permit the explicitly requested limb movement and only necessary joint, contact, fabric, hair placement, overlap and newly visible-area changes. Reconstruct revealed areas in the source's design and style without claiming recovery of unknown original pixels. Do not impose an unchanged body silhouette or restore the old pose during protection review.

Follow the shared [editing boundaries](../../references/edit-boundaries.md), [scoped edit references](../../references/edit-references.md), [candidate review](../../references/candidate-review.md) and [quality policy](../../references/quality-review.md). Pose references have only scope `pose`: action and structure, never identity, expression, clothes, color or style. Snapshot optional references with `reference-prepare`, bind them to the prepared brief, include one target criterion per reference ID and retain all actual inputs in redraws and human revisions.

Default to `art-output/<character-key>/poses/`, using a new independent project for a new source. Save a concrete five-dimension contract before generation. Initialize the project and `prepare` the action with an option ID, preset, explicit side, target, boundaries, protected attributes, source inspection box and any user-specified game anchors. Different sides/actions use different option IDs. The prepared source crop locates the initial scope; it is not a mask and does not locate a moved hand in a later image.

## Generate and review

Use the host's available image editing tool; the helper manages files and never generates or retouches artwork. Submit exactly the returned `reference_paths` in order: full immutable source, then optional pose references. Inspect local inputs before editing. Request one full PNG with the original canvas and transparency/background, and save the actual prompt and raw tool output. Record the model as `unknown` unless the tool reports it. If no editing tool is available, explain the missing capability.

Each requested result has at most three image-tool attempts including the first, unless the user specifies a smaller limit. Import the first candidate with `add` and start its pool with the already prepared contract. All further calls use the pool's reservation, actual reference order and recorded redraw findings. Stop generation when all gates pass or the fixed budget is spent; retain readable failed candidates and count failed tool calls. Use rubric 1.2: target, identity, protection, integration and rendering, with observed criteria and all `pose_edit` checks from the guide. Record separate target/protection `fidelity` observations. At least 80/100 and each dimension at least 4/5 are required; any failed/uncertain domain or fidelity check blocks passage regardless of total.

Follow the reserved strategy. New initial pools can use `source_restart` for the third attempt when the action passes but the same identity/protection checks stall across two candidates. Submit only the source and every already-bound pose reference; the failed candidate remains review evidence, not a tool input. Reapply the exact prepared action, anatomical side, hand orientation and anchors through the brief; do not restore the old pose or add new reference images mid-pool. Human revisions keep their user-chosen baseline. See the shared [restart policy](../../references/candidate-review.md#restart-after-stalled-protection).

Inspect full images, facial design, shoulder/elbow/wrist/finger anatomy, balance/support, contacts, clothing response, overlaps, framing, requested anchors and edges on light and dark backgrounds. Canvas mismatch can be viewed and recorded independently of visual scoring, but formal acceptance/export still requires the source canvas. Never resize, align, recolor, repair alpha or composite candidate artwork locally.

Review pages default to full images only for Poses. Add at most four localized regions through `--inspection-file` when actual positions justify them: each has `id`, `box`, `label`, `reason`. Boxes use common source-canvas coordinates; choose a region containing the relevant part in every compared image, including source and revision parent. Reinspect positions for every batch. If a useful common region is impossible, use the full image and direct inspection of each raw image. Independent per-candidate boxes and automatic landmark detection are not implemented. A detail preview cannot establish whole-image pose/framing preservation.

After full passage or exhaustion, present every readable candidate in the current batch in the user's language, including earlier failed rounds. Separate the recommendation and findings from the user's decision. Do not preselect or fabricate acceptance. Record actual “Accept A”, “Revise B: …”, or rejection through `human-feedback`; explicit acceptance already supplied needs no duplicate confirmation.

## Revise and deliver

For a specific human correction, use `revision-prepare` and `revision-import` in a new bounded batch. Edit the chosen candidate first, use the immutable original for a secondary check of still-protected attributes and retain all optional pose references. Keep the successful action and design outside the correction. Correct documented unauthorized drift within existing protection constraints; do not restore the original standing pose or mistake permitted fold/occlusion changes for drift. Fresh assessments must include revision continuity and source protection recheck. Choose fresh inspection regions rather than inheriting stale hand/face coordinates.

Only actually accepted candidates satisfying all gates become final artwork. Generate the [delivery report](../../references/delivery-report.md), show final full PNGs and comparison previews, and link the report. Complete a requested ZIP without another permission question. Failed candidates remain clearly labeled inspection evidence. Mechanical workflow validation and recorded visual judgments do not prove actual art quality or game switching stability.

## Helper

Resolve the absolute installed script path and keep the complete plugin with `lib/` and shared references together. Requires Python 3.11+ and Pillow. Run sequentially within each project.

```text
python <skill>/scripts/studio.py presets
python <skill>/scripts/studio.py init --project <poses-dir> --source <source.png> --character <key>
python <skill>/scripts/studio.py prepare --project <poses-dir> --pose-id wave_right --pose wave --side right --target <concrete-action> --boundary <permitted-movement-and-interfaces> --protect <identity-expression-designs-and-remainder> --target-box <left> <top> <right> <bottom>
# Use optional --reference-file <prepared-set.json> and --anchor <user-specified-anchor>.
# Generate with returned reference_paths, save the actual prompt and output.
python <skill>/scripts/studio.py add --project <poses-dir> --pose-id wave_right --image <raw.png> --prompt-file <prompt.txt> --brief-file <prepared-brief.json> --reference <poses-dir/source.png>
# Add each optional prepared reference with another --reference in the returned order.
python <skill>/scripts/studio.py pool-start --project <poses-dir> --asset wave_right_v001 --contract-file <contract.json>
python <skill>/scripts/studio.py review-sheet --project <poses-dir> --asset wave_right_v001 --purpose assistant
python <skill>/scripts/studio.py preview --project <poses-dir> --asset wave_right_v001 --output <poses-dir/preview/light.png> --background light
python <skill>/scripts/studio.py fidelity --project <poses-dir> --asset wave_right_v001 --target-check <passed-failed-uncertain> --protection-check <passed-failed-uncertain> --note <visible-findings>
python <skill>/scripts/studio.py quality --project <poses-dir> --asset wave_right_v001 --assessment-file <assessment.json> --comparison <poses-dir/preview/light.png>
python <skill>/scripts/studio.py pool-status --project <poses-dir> --case wave_right_v001
# Follow returned redraw plan while budget remains, then present user review.
python <skill>/scripts/studio.py review-sheet --project <poses-dir> --asset wave_right_v001 --purpose user
# Wait for and record actual feedback.
python <skill>/scripts/studio.py human-feedback --project <poses-dir> --feedback-file <feedback.json>
python <skill>/scripts/studio.py report --project <poses-dir> --output <new-delivery-dir> --stage final
python <skill>/scripts/studio.py export --project <poses-dir>
```

Projects use schema 3.0; each candidate snapshots the immutable action/side/anchor definition, brief, prompt, actual inputs and fresh reviews. Wrong-module operations fail before writing. ZIPs contain unchanged full PNGs at `sprites/<key>/poses/<pose-id>.png` and a `full_character_pose` manifest. No legacy project is migrated into Poses.
