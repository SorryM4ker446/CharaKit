# Quality-first development and internal delivery review

Use this shared baseline for every implemented editing module and future development. Quality means achieving the request while preserving the source within the operation's allowed changes. Prompt length, recognizability alone, a successful recolor, and passing file tests are insufficient acceptance criteria.

## Development baseline

Define the target outcome, internal invariants, protected remainder and technical requirements before implementing a mode. Shared rules establish the baseline; domain rules define permitted movements/material changes; current source facts and user requirements determine the actual constraints. Use complete, consistent prompts without guessed appearance attributes. Evaluate real outputs against the same requirements, preserving evidence and failures. Changes to prompts, models or workflows need visual regression examples as well as appropriate file-workflow tests; neither substitutes for the other.

Every future module must integrate internal review and gated delivery before being described as available. Keep final artwork editing in the image tool. Local code manages records, comparisons and gates, without repairing or compositing candidate pixels.

## Module and component checks come first

Use a shared baseline plus the active module/state's domain review. A single whole-image score is insufficient. The helper derives `kind` from the project's module and the candidate's explicit mouth state; a caller cannot substitute another module's checklist. Each domain check records `passed`, `failed` or `uncertain` and concrete evidence. Any failed check vetoes delivery; any uncertain check blocks it even when all four global scores are 5. Only then use the weighted score as a summary of the inspected result.

| Derived kind | Required checks | Inspect against the actual operation |
| --- | --- | --- |
| `expression` | `emotion`, `face_design`, `nonface_protection`, `rendering` | Emotion/intensity and coordinated brows/eyes/lips plus requested tears/blush; each eye's colors/design, nose/lip/face details; nonface components, pose and composition; original rendering and edges |
| `mouth_state` | `emotion`, `mouth_state`, `face_design`, `nonface_protection`, `rendering` | Explicit open/closed state, natural lip/interior design; preserve established emotion for mouth-only edits or achieve the requested emotion for combined edits; protect other facial features outside the allowed movement and all nonface regions |
| `garment_recolor` | `target_color`, `garment_invariants`, `interfaces`, `face_expression`, `non_target_protection`, `rendering` | Actual garment/surfaces and requested color; cut/material/pattern/folds/coverage; exclusions and overlaps; entire face/expression/mouth state; other clothing, hair, hands, props, pose and silhouette; original style/material response/edges |

Record the actual component and applied domain in `component`; this is source-grounded text, not a new edit-mode identifier. Outfits specializes its checklist using the relevant [garment domain](../skills/charakit-outfits/references/garment-domains.md): legwear checks coverage/translucency/upper edge/ankle and straps; handwear checks finger coverage, wrist and grip; footwear checks toe/heel/sole/closures and neighboring hosiery; lower garments check waist/hem/pleats/patterns; upper garments check collars/lapels/cuffs/layering; connected garments check continuity/panels/openings; headwear checks brim/fit and hair/ear boundaries. Use only domains/components actually present. A custom existing garment uses the same surface/property/invariant/interface criteria, not a forced category.

Protection checks follow the source, including complex or overlapping components even when they are outside the edited part. Recoloring gloves does not exempt the face or weapon. Do not demand an unchanged mouth when opening it is allowed, an unchanged garment base hue when recoloring it, or a prop absent from the source. Poses/full outfit replacement remain planned: define appropriate movement/construction/occlusion checks before implementing them, without making them callable through this review table.

This check is worthwhile as a pre-delivery defect filter, particularly for scope violations. The numbers are secondary and can give false confidence: reviewers can miss defects or misinterpret source details, and the helper verifies records rather than independently observing images. Keep the workflow lightweight and evidence-based, distinguish blocking requirement violations from minor imperfections, and calibrate against user feedback instead of expanding checklists without demonstrated benefit. Filtering does not repair artwork or guarantee fewer revisions.

## Generation, inspection and delivery

1. Inspect the immutable source and define the requested change, including expression/state or garment surfaces and exclusions. Identify comparison regions before generation.
2. Initialize a new project (quality policy defaults on). For an existing project lacking `quality_policy`, run `enable-quality` before a new generation request. This backs up metadata and gates future candidates, without fabricating historical observations or undoing old selections.
3. Save each raw output with `add` before review. Retain actual submitted prompts/references. Import success only means the file was retained, not that quality passed.
4. Build and actually view source/candidate comparisons: full image, target details, protected details, normal intended display size and relevant background edges. Use light and dark backgrounds for alpha; for opaque art inspect the retained background and its boundaries. Enlargements cannot prove normal-size readability or pixel equality. If the display size is unknown, choose and record a concrete inspection size and distinguish it from untested integration in a game.
5. Save a UTF-8 assessment JSON using the domain checklist and rubric below. Attribute it to `assistant`, describe the request and actual component, record every required domain check with evidence, summarize the four dimensions, and list serious defects and uncertainty. Never turn missing evidence into a pass or assign scores without viewing the images. Outfits also records its existing independent `fidelity` checks; quality review cannot replace them.
6. Run `quality` with the assessment and the saved comparisons. The helper validates data and bindings, computes the result and records review history. It has no visual scoring model: scores come from the inspecting assistant, not Pillow, a similarity algorithm or an independent calibrated evaluator.
7. Run `deliver` with only the proposed candidate IDs. It returns image paths only if every proposed candidate passes applicable technical checks, internal review and fidelity gates. Source-canvas mismatch is temporarily a warning for visual review and preview delivery, not a rejection reason. Internal passage makes the image ready for user feedback; it does not accept, select or export it. User acceptance remains separate.

Resolution is temporarily excluded from quality assessment: do not deduct rubric points, add uncertainty or declare a critical defect solely because output dimensions differ from the source. Record actual dimensions without resizing candidates. Still inspect visible detail loss, cropping, missing parts or altered placement as artistic defects when actually present; a dimension difference alone does not prove them. Decoding, PNG, transparency, nonempty images and unchanged fingerprints remain delivery gates. Formal acceptance/selection/ZIP export retain exact-canvas technical requirements; positive feedback on an export-blocked preview is saved separately.

Default user-facing delivery shows internally passed candidates. Keep failed/pending/uncertain candidates in the project, report the unmet requirements and counts in text, and avoid embedding/linking them as deliverables. If the user explicitly requests experiments, comparisons or failed outputs, show them with clear failure labels; this does not accept them or relax export gates. Tool-native previews may appear automatically before review; the Skill cannot suppress the host's UI, and cannot promise that no rejected image will ever be visible. `preview` is an inspection command, not gated delivery.

After the batch, assemble the shared [delivery report](delivery-report.md) using `report`: passed unchanged PNGs, a final preview and a report of the actual saved observations. Failed cases appear in the report without final-image delivery. Reporting does not replace inspection, alter scores, accept/select artwork or authorize new generations. Unlike inspection `preview`, the report's final preview is gated and excludes failed/intermediate candidates.

Do not silently add generations to an explicit requested count. Default additional generations remain zero without user authorization. When the user enables review-driven automatic improvement, use [bounded refinement](refinement.md): at most three total rounds per requested case, editing the previous complete version with the immutable original as the design authority. Preserve evidence, perform fresh review and stop on passage or exhaustion. Do not reset the budget, repeatedly regrade unchanged artwork, or weaken gates to force passage. Protected-region restoration is allowed only for defects observed in the review, and all final editing stays in the host image tool, never local repainting/compositing.

## Rubrics 1.0 and 1.1

Fresh reviews use rubric **1.1**, with an 80/100 total threshold and the same 4/5 dimension floor and domain/technical/fidelity vetoes. This makes four scores of 4 (acceptable with minor imperfections) eligible to pass. Rubric **1.0** keeps its historical 85/100 threshold; saved verdicts are not rewritten. See [refinement calibration](refinement.md#review-calibration) for minor rendering variation versus material identity/structure/scope violations. A detectable difference alone is not a failed domain item; do not demand pixel equality unless explicitly required.

Each dimension receives an integer 0–5 with source-grounded evidence. These are ordinal assistant judgments, not probabilities, certified identity measurements or objective pixel scores.

All active domain checks must pass in addition to the score thresholds below. Domain failure/uncertainty cannot be offset by high global scores or an empty global defect list.

| Dimension | Weight | What must be assessed |
| --- | --- | --- |
| `target` | 30 | Correct emotion and state, recognizable effects and coordinated actions; or requested garment color on the intended surfaces with no spill |
| `identity` | 25 | Facial identity, each eye's original color distribution/design, feature proportions and details; movement is permitted only within the operation |
| `protection` | 30 | Invariants inside the target, interfaces, hair, hands, clothing, props, silhouette, pose and composition outside the permitted change |
| `rendering` | 15 | Original style, line/shading/material detail, natural integration, visible defects, readable intent and background/alpha edges |

Score anchors: **5** meets the requirement with convincing inspected evidence; **4** meets it with small noncritical imperfections; **3** has an evident requirement deviation or incomplete achievement; **2** has substantial defects; **1** largely misses the requirement; **0** is unusable for that dimension. Do not reward extra beautification when it violates preservation. When evidence is insufficient, add uncertainty and mark the relevant inspection false; high guessed scores cannot clear that block.

The weighted total is `sum(score × weight) / 5`, on a 0–100 scale. Passage requires **total ≥ 80 for rubric 1.1 (≥ 85 for 1.0), every dimension ≥ 4, all inspection flags true, no critical defects, no uncertainty, and passing applicable technical/fidelity requirements**. A serious defect is a veto regardless of total: unrequested iris recoloring or face redesign, wrong expression/state/target, meaningful non-target geometry/color changes, missing/cropped parts, conspicuous redraws or artifacts. Minor rendering variations that preserve the requirement can pass with 4 and explicit evidence. File format, fingerprints, transparency and empty-image rules remain separate gates. Exact canvas blocks formal acceptance/selection/export. Record relevant uncertainty rather than pretending the checklist is exhaustive.

The thresholds and weights are product policies, not empirically calibrated predictors of user satisfaction. Rubric 1.1 corrects the inconsistency between four acceptable 4/5 scores and the old total gate; it does not establish improved generation quality. Track actual user reviews and first-attempt/final pass rates across characters and parts. Bounded improvement uses review findings but does not guarantee passage or fewer user revisions.

## Assessment and commands

Example structure below is deliberately incomplete for delivery: all scores are 4 (total 80), normal-size inspection is false and uncertainty is present. Replace it with actual inspected findings; never copy a passing assessment as a default.

```json
{
  "rubric_version": "1.1",
  "basis": "assistant",
  "request": "Actual requested operation and boundaries",
  "domain_review": {
    "version": "1.0",
    "kind": "expression",
    "component": "Actual requested expression and facial region",
    "checks": {
      "emotion": {"status": "uncertain", "evidence": "Describe the intended emotion and what remains unconfirmed"},
      "face_design": {"status": "uncertain", "evidence": "Compare each eye and the other facial design details"},
      "nonface_protection": {"status": "uncertain", "evidence": "Inspect protected components present in this source"},
      "rendering": {"status": "uncertain", "evidence": "Compare original linework, shading and edges"}
    }
  },
  "dimensions": {
    "target": {"score": 4, "evidence": "Describe the visible target result versus the request"},
    "identity": {"score": 4, "evidence": "Describe each eye and facial detail compared with the source"},
    "protection": {"score": 4, "evidence": "Describe the inspected source-specific protected regions"},
    "rendering": {"score": 4, "evidence": "Describe style, fine details and edge inspection"}
  },
  "inspection": {
    "full_image": true,
    "target_detail": true,
    "protected_details": true,
    "normal_display": false,
    "background_edges": true
  },
  "critical_defects": [],
  "uncertainties": ["Normal intended viewing size has not yet been inspected"]
}
```

```text
python <skill>/scripts/studio.py enable-quality --project <existing-project>
python <skill>/scripts/studio.py quality --project <project> --asset <candidate-id> --assessment-file <assessment.json> --comparison <project/preview/light.png> --comparison <project/preview/dark.png>
python <skill>/scripts/studio.py deliver --project <project> --asset <candidate-id>
```

`quality` records evidence even for readable technically failed candidates. A canvas mismatch alone allows internal quality passage and preview delivery, while `technical_passed` and raw validation continue to report the formal technical failure. `deliver` includes actual dimensions and warnings. Review records bind the source, candidate, actual saved prompt (when present) and in-project comparison PNG fingerprints. Changed/missing comparisons or prompts invalidate the result; changed candidates cannot reuse or replace observations. New revisions never inherit scores or observations. A failed reassessment removes selection but preserves actual user-feedback history. The helper validates records and gates, not whether the reviewer told the truth or noticed every defect.

Project schema remains 1.0/1.1 for Expressions and 1.2 for Outfits, with additive versioned `quality_policy`, candidate `quality_required`, `quality_review` and `quality_history`. Use helper **0.1.11 or later**: older helpers ignore these fields and cannot enforce the gate. Legacy projects/assets are readable without writes and retain their original acceptance/export behavior unless they acquire a quality review; the new `deliver` command requires a passed review even for legacy candidates. `enable-quality` affects future candidates, not historical claims. A quality-reviewed export includes the review in its manifest and preserves PNG bytes.

Use helper **0.1.13 or later** for mandatory domain checks, and **0.1.14 or later** for rubric 1.1 and bounded refinement. `quality` rejects missing, incomplete or wrong-module/state checklists before writing. Saved older reviews retain their own threshold and semantics without invented findings; inspect old reviews lacking domain evidence before a new generation/revision task. Project schemas, resolution exception and explicit user acceptance remain unchanged.
