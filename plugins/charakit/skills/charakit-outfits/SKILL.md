---
name: charakit-outfits
description: Recolor one specified existing garment in complete visual novel character artwork while preserving its materials, patterns, folds, face, expression, pose, and original style. Use for clothing color variants, individual revisions, comparison previews, version selection, and PNG exports. Full outfit replacement and accessory additions or removals are not implemented.
---

# CharaKit Outfits

Create complete character images with one requested garment recolored. The current mode is `recolor`. Preserve the garment's design, texture, pattern, folds, seams, trim, buttons, and shading; retain all other clothing, accessories, hair, the entire face, expression, mouth state, pose, proportions, and composition.

Read the shared [editing boundaries](../../references/edit-boundaries.md) before defining an edit, then the relevant [garment domain](references/garment-domains.md) for target surfaces, material/structure invariants, and interfaces. Use [recolor-guide.md](references/recolor-guide.md) for submission, comparison, and revision. Full outfit replacement, clothing removal, accessory additions/removals, and pose editing remain planned. Expressions and static mouth states use the separate `charakit-expressions` Skill. Keep a combined request within the implemented scope and explain any remaining work accurately.

## Language and input

Respond and write generation prompts, visible names, explanations, and review notes in the user's current or preferred language. Keep CLI arguments, JSON keys, outfit IDs, filenames, and status/error codes stable English identifiers. Translate preview titles with a flat UTF-8 JSON file whose keys include outfit IDs, `source`, `reference`, review statuses, technical statuses, and error codes; pass it to `preview --labels-file`.

Inspect the actual source first and identify the requested garment, its boundaries, and the color. Ask only when the garment or requested color cannot be resolved from the request and artwork. A garment name can be free text; the helper records it but cannot verify that a model changed only that garment.

Use a separate project such as `art-output/<character-key>/outfits/`; do not initialize or add outfits inside an existing Expressions project. Each project has one immutable source snapshot. Start each candidate from that same source, including revisions, to avoid carrying incidental redraws forward. Include an earlier candidate only when the user needs it as a color reference; retain the source as the edit target and explain each reference's role.

Before generating a new option, use `prepare` to record the requested color property, included surfaces, domain-specific target invariants, boundary exclusions, and protected remainder in the user's language. Every unrequested component/property is protected, including the face, expression, mouth state, hair, pose, and other clothing/props. Derive concrete exclusions from the actual source; sharing a color or material does not join two components into one target. Choose a source-coordinate target box with enough context; it is a rectangular reference crop, not an exact selection or edit mask.

## Generation and inspection

Read and apply the shared [quality review and delivery policy](../../references/quality-review.md). New projects enable internal review by default; run `enable-quality` before a new generation in a legacy project. After inspecting comparisons, record evidence-backed rubric scores with `quality`, keep the independent `fidelity` observations, and run `deliver` before presenting deliverables. Serious defects, uncertainty and technical failure other than temporarily excluded canvas mismatch cannot be offset by a high total. Internal passage does not imply user acceptance.

Include a `garment_recolor` domain review of target color, garment invariants, interfaces, face/expression, non-target protection and rendering. Identify the actual garment/domain in `component` and specialize evidence using its [garment-domain rules](references/garment-domains.md). Socks, gloves, shoes and other garments have different material/structure/interface checks; do not copy one component's observations to another. Failed/uncertain domain items veto delivery even at 100/100. Explain the failed component/property and visible finding in the user's language; keep the entire protected remainder within inspection scope.

Use the OpenAI image editing tool available in the host. This Skill supplies instructions and local file management, not an image model or external API. If the tool is unavailable, explain the missing capability. Record the model as `unknown` unless reported.

Generate only requested color options and candidate counts. Each deliverable is one full illustration with original framing. Preserve source transparency or its opaque background as appropriate. Do not crop to the garment, extract body parts, paste recolored clothing onto the source, or claim that a global tint is a selective recolor.

State the target garment and color in the prompt; distinguish fabric from trim, buttons, lining, and nearby garments when that affects the request. Preserve the original lighting and material behavior instead of using one flat color. A color name or hex value is a direction, not a guarantee that every shaded pixel has that exact value.

Read the prepared brief and default to one complete source reference. Build a complete prompt stating the sole allowed color change, domain invariants, concrete boundary exclusions, preservation of everything else, and complete-image output. Quality and preservation take priority over prompt length; include necessary detail from the brief rather than removing it to shorten the submission. Facial preservation instructions retain the original features and rendering; they do not ask for facial reconstruction, beautification, cleanup, or style enhancement. See the guide's prompt template. Semantic instructions are not a demonstrated pixel-preservation solution.

Keep the prepared detail for inspection. Submit it only when the garment is ambiguous in the full source or the user requests a reference comparison, and the host supports additional references. Inspect it first and state that it only locates the target in the full source, not the output framing or a replacement design. Save the actual submitted prompt and reference paths, including whether the prepared crop was sent. Do not claim a mask was applied unless the host actually accepts a mask. All final artwork edits stay in the host image tool; local reference/preview crops do not recolor or composite candidate pixels.

Save each real tool output before reviewing it. The helper copies original image bytes and never resizes, repaints, changes alpha, or removes backgrounds. Check PNG content, exact source canvas, transparency requirements, source and candidate fingerprints. Keep failed readable candidates and explain their errors; technical failure does not discard progress.

Temporarily exclude output resolution/source-canvas mismatch from rubric scoring and preview-delivery rejection. Record actual dimensions and retain the raw mismatch report; evaluate visible quality defects on their own evidence. Other technical/fidelity/quality gates remain, and formal acceptance/selection/ZIP export still require the source canvas. See the shared delivery policy.

Inspect full-image comparisons, whole-face enlargements, target invariants, and interfaces from the selected domain. Enlarge relevant protected details chosen from the source, especially fine construction or complex overlaps; do not require an object absent from the artwork. Reuse `preview --detail-box` with distinct output paths. Check color spill and changes in geometry, texture, patterns, seams, folds, trim, expression, pose, and outline; an unchanged broad color is insufficient. Inspect edges on light and dark backgrounds. Scripts cannot judge these artistic properties or game-switching quality.

After viewing the actual source and candidate comparisons, use `fidelity` to record two independent observations: target recoloring and preservation of protected regions. Choose `passed`, `failed`, or `uncertain` for each and cite the visible findings in the note. A recognizable character or successful color change alone is insufficient: extra facial repainting, changed weapon/hair geometry, or color spill makes protection fail. Use `uncertain` when evidence is insufficient; never fabricate pixel equality or objective automatic visual scores. The shared quality rubric records attributed assistant judgments and cannot override failed fidelity. Assistant observations use `--basis assistant`; use `user` only for findings actually supplied by the user. These checks remain separate from technical status and user acceptance. Preserve failed results and describe the limitation; revise through the image tool only when requested, without automatically repairing the face or other protected parts.

## Local helper

`scripts/studio.py` uses Python 3.11+ and the plugin's Pillow dependency. Resolve its absolute installed path; keep the complete plugin including `lib/studio_core.py` together. It runs once and exits, with no service or API key. Work sequentially within one project.

```text
python <skill>/scripts/studio.py init --project <outfits-dir> --source <source.png> --character <character-key>
python <skill>/scripts/studio.py prepare --project <outfits-dir> --outfit coat_navy --target <garment-description> --color <requested-color> --boundary <fabric-only-and-exclusions> --protect <face-expression-hair-pose> --protect <other-clothing-and-nearby-trim> --target-box <left> <top> <right> <bottom>
python <skill>/scripts/studio.py add --project <outfits-dir> --outfit coat_navy --target <garment-description> --color <requested-color> --image <generated.png> --prompt-file <prompt.txt> --brief-file <prepared-brief.json>
python <skill>/scripts/studio.py preview --project <outfits-dir> --asset coat_navy_v001 --asset coat_navy_v002 --output <comparison.png> --face-box <left> <top> <right> <bottom> --detail-box <left> <top> <right> <bottom> --background light --labels-file <labels.json>
python <skill>/scripts/studio.py fidelity --project <outfits-dir> --asset coat_navy_v001 --target-check passed --protection-check <passed-failed-or-uncertain> --basis assistant --note <actual-visible-findings>
python <skill>/scripts/studio.py quality --project <outfits-dir> --asset coat_navy_v001 --assessment-file <assessment.json> --comparison <outfits-dir/preview/light.png> --comparison <outfits-dir/preview/dark.png>
python <skill>/scripts/studio.py deliver --project <outfits-dir> --asset coat_navy_v001
python <skill>/scripts/studio.py review --project <outfits-dir> --asset coat_navy_v001 --status accepted --note <user-feedback>
python <skill>/scripts/studio.py select --project <outfits-dir> --asset coat_navy_v001
python <skill>/scripts/studio.py export --project <outfits-dir>
```

- `init` creates a module-specific schema 1.2 project. Expression projects retain their schema 1.0/1.1 behavior and are not migrated into outfits. Wrong-module CLI operations fail before writing.
- `prepare` saves versioned `briefs/` JSON and `references/` source detail PNG without changing project metadata or source/candidate bytes. Use its returned paths, inspect the reference, and preserve both. It does not generate an image, create a mask, or lock pixels.
- `add` requires a lowercase outfit option ID, the garment `target`, and requested `color`. Use one ID per target/color combination, for example `coat_navy` and `coat_red`. Revisions use the exact existing target/color values, preserve history, and increment versions within that ID. Use a new ID when changing the garment or color. These are color options, not a new costume design.
- `add --brief-file` validates the source/option definition and detail-reference fingerprint, then embeds the brief with the candidate. Later revisions inherit the latest brief if omitted; each new candidate needs its own fidelity observations. Old schema 1.2 assets without a brief or fidelity record remain readable with their prior gates; never infer past checks or silently rewrite them. Use the prepared workflow for new generation requests.
- `preview --outfit coat_navy` filters one option's versions. Repeated `--asset` arguments compare specific candidates. `--face-box` and `--detail-box` use source-canvas coordinates and add separate face and garment rows. Candidate-size mapping is for viewing only; it does not fix alignment.
- `review accepted` records real user satisfaction and selects a technically valid version for that outfit ID. `select` switches accepted versions. Unreviewed candidates remain unreviewed. Explicit user satisfaction or selection is sufficient; do not request duplicate approval.
- `fidelity` records manual observations without accepting a candidate. It can record readable, unchanged candidates even when canvas checks fail. Brief-linked candidates require both observations passed before acceptance, selection, or export; a recorded failed/uncertain check also blocks legacy candidates. Recording a failure removes that candidate's selection while retaining user-review history. Passing fidelity alone does not select anything or satisfy technical/user-review gates. Preview labels `fidelity_pending`, `fidelity_passed`, `fidelity_failed`, and `fidelity_uncertain` can be localized.
- If the user likes a technically failed image, preserve their feedback separately; the helper cannot mark it accepted or include it in formal export until checks pass.
- `export` rechecks accepted selections, allows one version per outfit ID, and copies unchanged PNG bytes into `sprites/<character>/outfits/<outfit-id>.png`. The schema 1.2 manifest records target, color, edit type, candidate version, and fingerprint. ZIPs, previews, source files, and existing candidates are not overwritten.

## Revision and delivery

Revise only the requested option and preserve other candidates and selections. Produce one new candidate for a targeted revision and review it afresh; no additional generations without an explicit revision or attempt budget. Show actual images and file links returned by `deliver`, plus submitted prompts. Keep blocked candidates internally and report unmet criteria in text, unless the user explicitly requested failed/experimental comparisons; label those as inspection evidence. Report visual limitations and technical status separately. Workflow support and internal scoring do not guarantee preservation or a lower user revision rate.
