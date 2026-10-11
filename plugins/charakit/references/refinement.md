# Bounded refinement from review findings

**Legacy workflow:** this reference applies to existing `refinements` cases only. For all new requests, use [candidate selection and human review](candidate-review.md). Preserve old budgets, lineage and scores; do not convert a failed case into a fresh allowance.

Use this workflow when the user requests automatic improvement of failed results or enables a bounded refinement budget. Authorization is per expression/mouth-state combination or garment/color or garment/replacement option. Default maximum: **three total image/review rounds**, the first image plus at most two revisions. Stop immediately on passage. Ordinary requests without this mode retain their requested generation count; do not silently add retries.

The helper tracks rounds and gates; Codex still invokes the host image tool, views the actual comparisons and writes the assessment. It does not run a hidden image model or automatic visual scorer.

## Review calibration

New assessments use `rubric_version: "1.1"`: total at least 80, every dimension at least 4, complete inspection, no critical defects or unresolved uncertainty, all active domain checks passed and applicable technical/fidelity gates passed. Four 4/5 scores now mean an acceptable result with minor imperfections. Rubric 1.0 remains readable with its original 85 threshold; do not rewrite historical scores to change the verdict.

At a concrete normal display size, distinguish minor rendering variation from a requirement violation. Small brushwork/antialiasing changes that do not visibly alter identity, material, structure, pose or the requested result can receive 4 and a passed domain item with an explicit minor-imperfection note. Do not require pixel equality from an image model. Wrong emotion/mouth state/garment color, unintended facial redesign or iris recoloring, changed protected construction or composition, missing parts and conspicuous artifacts still fail. Use detail views to establish whether a difference is structural or only minor rendering variation. Domain checks are not a rule that every detectable difference is a veto. Exact pixel preservation applies only if explicitly required by the user and feasible in the available workflow.

## Round loop

1. Generate and save the first requested full image with ordinary `add`. Start its case with `refine-start --project ... --asset <first-id>`. An already reviewed first version counts as round one without rescoring it. A legacy project needs `enable-quality` before new work; an old review without the current domain must be inspected again before starting.
2. Inspect each candidate against the immutable original, never only against the previous version. Save whole-image, target and protected-detail comparisons in distinct paths per round so earlier evidence remains valid. For Outfits, record fresh `fidelity` before completing `quality`. Each tracked image receives one quality assessment and one applicable fidelity record; do not repeatedly rescore unchanged art until it passes.
3. Read `refine-status --project ... --case <first-id>` before a new generation. `review` means finish the current inspection; `deliver` means stop generating; `exhausted` or `blocked` means stop and report the unmet criteria. Only `revise` permits the next image.
4. Read `strategy`, `references` and `repair_brief` from the returned plan. Build the prompt using the reference roles and compact instructions below. Supply **two complete references in this order**: immutable original, then previous complete candidate. The second image's role depends on the strategy; never silently assume it is always the edit target.
5. Save the actual submitted prompt. Import the raw tool result with `refine-add --strategy <returned-strategy>`, recording the same two actual reference paths with repeated `--reference` arguments. This preserves the requested expression/state or outfit definition and brief, binds the revision to its parent and review findings, records reference roles, consumes the next round and starts fresh quality/fidelity observations.
6. Inspect, review and read status again. For a passed case, use `refine-deliver`; it returns only the latest passed full image. If round three still fails, report that no qualified final exists and retain all evidence. Do not label the highest scoring failed candidate accepted, reset the same case's budget or generate a fourth image.

### Reference strategy

- `continue_previous`: image 1 is the original identity/design/material authority; image 2 is the edit target. Correct observed defects toward image 1 while retaining successful requested changes in image 2. This remains the strategy for Expressions, legacy refinement cases and round two.
- `source_rebase`: image 1 is both the edit target and the preservation authority; image 2 is **only a reference for the successful requested garment design/color**. Reapply that garment change to image 1, within the original boundaries. Do not copy image 2's face, hair, props, other garments or framing. This consumes round three of the same case; it does not reset the budget.

New cases created with helper 0.1.17 use refinement-record version 1.1. For Outfits, the helper selects `source_rebase` before round three when the target check passes in round two, a face/protection domain check failed in both earlier rounds, and its corresponding identity/protection score did not improve. This is a routing signal from saved observations, not a visual claim that two failures are identical. If protection improves or the target still fails, continue the previous candidate. Both references and the chosen strategy must be recorded exactly. Old version 1.0 cases retain their original strategy and history, including their spent budget.

### Compact prompt construction

Use `repair_brief.findings` as the starting point. It normalizes repeated evidence and retains contributing check IDs; raw `issues` remains the audit record. Codex must additionally merge paraphrases about the same component/property. Do not concatenate domain evidence, dimension evidence, critical-defect summaries and fidelity notes as separate repeated instructions. Preserve distinct defects and unresolved uncertainty.

Write the prompt in the user's language, with each requirement stated once:

1. Reference roles and the selected strategy.
2. Requested target change and successful design properties to retain.
3. For each distinct defect: the affected component/property, observed deviation and source-grounded correction. Avoid generic requests to reconstruct or beautify the face.
4. Allowed boundaries/interfaces and protected remainder from the prepared brief.
5. One complete image, source framing/canvas and original transparency/background; no comparison panel or text.

For `source_rebase`, phrase protection defects as properties to preserve from image 1 while applying the garment change. For `continue_previous`, phrase them as corrections to image 2 toward image 1. The strategy and preservation directions remain semantic instructions; no mask, regional pixel lock, local compositing or MCP backend is involved. Quality must be tested on real outputs before claiming an improvement.

Generation or tool errors do not authorize an extra request. A stale review, modified/missing reference, or explicit user rejection blocks the case. Process history is available through `refine-status`, ordinary `status` and `preview`; viewing it is not an acceptance condition. Preserve actual user feedback separately. Internally passed finals remain `unreviewed` until the user accepts them, and formal selection/export retain their existing technical gates. A canvas mismatch alone is not a protection defect or a reason to switch strategy or spend another round; record it separately without resizing candidate pixels.

Default conversation delivery contains only the passed final per case, plus a concise result when the limit is reached. Show intermediate images only if the user asks to inspect them. Host-native image-tool previews can appear automatically and cannot be suppressed by this Skill; do not promise the host will display no process images. All candidate bytes remain archived. This mode can use up to three images per requested case; “final only” describes presentation, not eliminating intermediate generation work or cost.

Finish the batch with the shared [delivery report](delivery-report.md). `report` assembles passed final PNGs, a final-only preview with source references, and a Markdown/JSON report of all in-scope cases. Exhausted cases receive a failure explanation without a final PNG; if none pass, no image preview is generated. Saved per-round scores/findings and process evidence are included without regrading. Use helper 0.1.15 or later for this delivery package.

## Helper example

Replace paths and IDs with actual returned values. The image-tool step remains a Codex action between status and import; this is not an autonomous Python image-generation loop.

```text
python <skill>/scripts/studio.py refine-start --project <project> --asset <first-id> --max-rounds 3
python <skill>/scripts/studio.py refine-status --project <project> --case <first-id>
# When action is revise, edit using original + previous complete image and save the submitted prompt.
python <skill>/scripts/studio.py refine-add --project <project> --case <first-id> --strategy <returned-strategy> --image <new.png> --prompt-file <repair.txt> --reference <project/source.png> --reference <previous-candidate.png>
# Create and inspect fresh comparison paths, record fidelity when applicable, then quality.
python <skill>/scripts/studio.py quality --project <project> --asset <new-id> --assessment-file <review-1.1.json> --comparison <new-comparison.png>
python <skill>/scripts/studio.py refine-deliver --project <project> --case <first-id>
```

Use helper 0.1.17 or later for new cases and adaptive reference roles. Additive `refinements`, candidate `refinement_case`, `refinement_round` and `refinement_inputs` records retain the existing project schema, including replacement schema 1.3. Initial history does not acquire invented improvement claims. Older helpers cannot enforce the new strategy records; use the matching packaged helper for tracked projects.
