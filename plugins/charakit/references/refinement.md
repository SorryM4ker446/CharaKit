# Bounded refinement from review findings

Use this workflow when the user requests automatic improvement of failed results or enables a bounded refinement budget. Authorization is per expression/mouth-state combination or garment/color option. Default maximum: **three total image/review rounds**, the first image plus at most two revisions. Stop immediately on passage. Ordinary requests without this mode retain their requested generation count; do not silently add retries.

The helper tracks rounds and gates; Codex still invokes the host image tool, views the actual comparisons and writes the assessment. It does not run a hidden image model or automatic visual scorer.

## Review calibration

New assessments use `rubric_version: "1.1"`: total at least 80, every dimension at least 4, complete inspection, no critical defects or unresolved uncertainty, all active domain checks passed and applicable technical/fidelity gates passed. Four 4/5 scores now mean an acceptable result with minor imperfections. Rubric 1.0 remains readable with its original 85 threshold; do not rewrite historical scores to change the verdict.

At a concrete normal display size, distinguish minor rendering variation from a requirement violation. Small brushwork/antialiasing changes that do not visibly alter identity, material, structure, pose or the requested result can receive 4 and a passed domain item with an explicit minor-imperfection note. Do not require pixel equality from an image model. Wrong emotion/mouth state/garment color, unintended facial redesign or iris recoloring, changed protected construction or composition, missing parts and conspicuous artifacts still fail. Use detail views to establish whether a difference is structural or only minor rendering variation. Domain checks are not a rule that every detectable difference is a veto. Exact pixel preservation applies only if explicitly required by the user and feasible in the available workflow.

## Round loop

1. Generate and save the first requested full image with ordinary `add`. Start its case with `refine-start --project ... --asset <first-id>`. An already reviewed first version counts as round one without rescoring it. A legacy project needs `enable-quality` before new work; an old review without the current domain must be inspected again before starting.
2. Inspect each candidate against the immutable original, never only against the previous version. Save whole-image, target and protected-detail comparisons in distinct paths per round so earlier evidence remains valid. For Outfits, record fresh `fidelity` before completing `quality`. Each tracked image receives one quality assessment and one applicable fidelity record; do not repeatedly rescore unchanged art until it passes.
3. Read `refine-status --project ... --case <first-id>` before a new generation. `review` means finish the current inspection; `deliver` means stop generating; `exhausted` or `blocked` means stop and report the unmet criteria. Only `revise` permits the next image.
4. Build a targeted repair prompt from the returned `issues`: quote the observed component/property deviations, the intended correction, successful parts to retain, and the original edit boundaries. Supply **two complete references in this order**: the immutable original as the identity/design/geometry/material authority, then the previous complete candidate as the edit target. Improve the previous image while restoring identified defects toward the original. Do not propagate incidental redraws, beautify the face, change the requested emotion/color, or repair an unrelated part without an observed defect. Use the actual source and current findings, not a generic repair list.
5. Save the actual submitted prompt. Import the raw tool result with `refine-add`, recording the same two actual reference paths with repeated `--reference` arguments. This preserves the requested expression/state or outfit definition and brief, binds the revision to its parent and review findings, consumes the next round and starts fresh quality/fidelity observations.
6. Inspect, review and read status again. For a passed case, use `refine-deliver`; it returns only the latest passed full image. If round three still fails, report that no qualified final exists and retain all evidence. Do not label the highest scoring failed candidate accepted, reset the same case's budget or generate a fourth image.

Generation or tool errors do not authorize an extra request. A stale review, modified/missing edit target, or explicit user rejection blocks the case. Process history is available through `refine-status`, ordinary `status` and `preview`; viewing it is not an acceptance condition. Preserve actual user feedback separately. Internally passed finals remain `unreviewed` until the user accepts them, and formal selection/export retain their existing technical gates.

Default conversation delivery contains only the passed final per case, plus a concise result when the limit is reached. Show intermediate images only if the user asks to inspect them. Host-native image-tool previews can appear automatically and cannot be suppressed by this Skill; do not promise the host will display no process images. All candidate bytes remain archived. This mode can use up to three images per requested case; “final only” describes presentation, not eliminating intermediate generation work or cost.

## Helper example

Replace paths and IDs with actual returned values. The image-tool step remains a Codex action between status and import; this is not an autonomous Python image-generation loop.

```text
python <skill>/scripts/studio.py refine-start --project <project> --asset <first-id> --max-rounds 3
python <skill>/scripts/studio.py refine-status --project <project> --case <first-id>
# When action is revise, edit using original + previous complete image and save the submitted prompt.
python <skill>/scripts/studio.py refine-add --project <project> --case <first-id> --image <new.png> --prompt-file <repair.txt> --reference <project/source.png> --reference <previous-candidate.png>
# Create and inspect fresh comparison paths, record fidelity when applicable, then quality.
python <skill>/scripts/studio.py quality --project <project> --asset <new-id> --assessment-file <review-1.1.json> --comparison <new-comparison.png>
python <skill>/scripts/studio.py refine-deliver --project <project> --case <first-id>
```

Use helper 0.1.14 or later. Additive `refinements`, candidate `refinement_case`, `refinement_round` and `refinement_inputs` records retain project schemas 1.0/1.1/1.2. Initial history does not acquire invented improvement claims. Older helpers cannot enforce these new budgets or final-only gates; use the matching packaged helper for tracked projects.
