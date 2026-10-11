# Final images, preview and generation report

Helper 0.1.25 records [scoped edit references](edit-references.md) for all editing modes in reports and ZIP manifests, including their permitted scopes and actual generation/redraw inputs. ZIP reference snapshots remain separate from final sprites and do not count as deliverables. Changed/missing reference snapshots invalidate reuse and block packaging. The final report still requires actual human feedback; earlier reports are internal drafts.

Helper 0.1.24 keeps actual candidate-pool attempt numbers instead of renumbering imported images after a failed call. The budget includes those failed calls; their recorded reasons appear separately. Exhausted new pools direct the user into human review with unresolved findings, without final artwork export.

Helper 0.1.23 defaults new pools to three total attempts per result. Correct recorded internal failures before human review, even when the total is ≥80; require all five dimensions ≥4/5 and all domain/fidelity checks passed. Stop on full passage or recorded exhaustion; honor explicit smaller limits and preserve legacy pools. See [the current review/redraw procedure](candidate-review.md).

For new candidate pools, first complete [human review](candidate-review.md). Before the actual user decision, `report` produces findings only; it cannot copy pool candidates into final outputs. Show the review sheet as inspection evidence, wait for feedback, and then run `report` before final delivery. Deliver the returned passed full PNGs, the final preview and the Markdown report. Use the user's language and short labels. A one-image request still gets a report; a multi-module batch can share one report. Do not add image generations to prepare these artifacts.

The report is assembled from saved quality/fidelity observations and current delivery gates, not a new visual assessment. It includes the original request, source, per-case outcome, per-round dimension/total scores, final domain checks, inspection coverage, dimensions/warnings, failure findings and links to actual prompts/comparisons. Markdown is the human-readable report; JSON retains full findings, provenance paths and final/preview hashes. Do not invent time/cost/model measurements or reinterpret old failures as passes. Report labels are localized; historical observations retain the language in which they were saved.

Helper 0.1.17 shows blocking reasons beside the score/result and records each round's generation strategy. JSON `gate_summary` distinguishes meeting the total threshold from failed dimensions, domain checks and incomplete inspections. Explain a result such as “80/100 · failed · protection 3/5; weapon structure changed” using its saved evidence. Total threshold and dimension floor follow the recorded rubric. Minor brushwork can be acceptable; identity/structure violations still block. Canvas mismatch remains separately reported and does not lower visual scores. Reporting never regrades old candidates.

```text
python <either-skill>/scripts/studio.py report --project <expressions-project> --project <outfits-project> --output <new-delivery-dir> --language zh-CN --labels-file <labels.json> --face-box <left> <top> <right> <bottom>
```

`--project` is repeatable and this shared command may read both implemented modules. By default it reports the latest candidate for each expression/mouth-state or garment/color or garment/replacement slot in the supplied projects. Use fresh task projects, or restrict a single existing project with repeated `--asset` arguments so unrelated historical slots do not enter this task's report. A legacy tracked asset selects its whole refinement case and resolves to the current version; the command cannot deliver its earlier failed version. Duplicate cases are rejected. Completed cases are `passed` or `exhausted`; pending review/revision and blocked evidence are explicitly labeled, not reported as completed successes.

`--output` must name a new directory. Optional `--language en`, `--title`, `--background light|dark|checker` and localized `--labels-file` customize presentation. Label keys use expression/outfit IDs, `mouth_open`, `mouth_closed`, a full expression/mouth slot or `source`. `--face-box` adds source-coordinate face details to the display sheet and must fit every supplied source. The preview contains source references and only passed final versions. Inspection previews produced earlier remain linked in the report, without being promoted to final assets or overwritten.

The command returns:

- `images`: unchanged passed PNG copies in `final/`; each is rechecked through `deliver` and fingerprinted. This does not accept/select/export artwork.
- `preview`: a display-only PNG with passed finals and source references, or `null` when none passed.
- `report` and `manifest`: `report.md` and `report.json`, including failed cases even in a mixed batch.

If all cases fail, deliver only the report; `images` is empty and no image preview/final PNG is created. Three failed rounds do not authorize a fourth. Keep candidates and observations archived, explain the blocking component and suggest addressing the recorded defects rather than lowering the score threshold. Users may inspect process evidence through report links; process images are not acceptance criteria.

Render/view the actual returned preview and passed images, and check the report's counts, labels and image links. In the final response, show each PNG in the returned `images` list as a separate inline image with a short localized caption, then show the returned final `preview` inline and link the Markdown `report`. In Codex, use Markdown image syntax with the actual absolute local path, for example `![Happy](D:/project/delivery/final/happy.png)`. Wrap a destination containing spaces in angle brackets, for example `![Happy](<D:/My Project/delivery/final/happy.png>)`. Plain file links alone do not provide the requested image presentation. Keep separate full PNGs available even when a comparison preview exists; do not replace them with crops or the preview sheet. For a large batch, follow the user's requested display scope and retain access to all passed PNGs through the report.

Codex controls the native image viewer, navigation and thumbnail layout. The Skill provides separate image attachments/embeds; it does not implement viewer controls or guarantee gallery grouping, order, or a particular thumbnail sidebar. Do not fabricate an interactive viewer, regenerate artwork, or alter final pixels just to imitate the host UI. Do not present failed candidates or intermediate inspection images as final images. Host-native image generation previews may already have appeared automatically.

Reports are immutable snapshots in new directories. Project metadata, candidate pixels, saved prompts and earlier evidence stay unchanged. Regenerate to a new directory after later edits; stale or missing evidence/file failures are recorded and block image delivery. A source/project that cannot be read safely produces an error instead of fabricated observations. Use helper 0.1.15 or later.

## Candidate pools in 0.1.18

### Report timing in 0.1.19 and later

Helper 0.1.20 also records a human revision's parent version and original correction request in the report and export manifest. The corrected candidate has a new assessment and actual acceptance; parent scores/acceptance are not reused. Revision review pages show original, before revision and the new candidate. Historical reports remain snapshots.

Helper 0.1.22 also reports `prop_edit` actions and their object/contact/occlusion/anatomy findings in the user's language. Schema 1.5 exports retain the action, object definition, brief, actual feedback and revision provenance, using the existing Outfits resource paths. Add/remove/replace never reuse garment-only findings or bypass common gates.

Before human feedback, `report --stage auto` (the default) creates an explicitly labeled **internal inspection draft**, with `stage: draft`, pending case IDs, no final PNGs and no final preview. It is not the final review report. After all requested pool cases have actual feedback, the same command produces a final review report. Use `report --stage final` for the final workflow step: missing actual human feedback fails with `HUMAN_REVIEW_REQUIRED` and creates no output directory.

Final review does not require a positive decision: adoption, requested changes and rejection are all recorded, together with the actual feedback facets and Codex disposition. A user-selected earlier candidate supplies the result summary and domain evidence; chronological history remains complete. Positive feedback cannot bypass technical, fidelity or quality checks. Generate to a fresh directory after human review; retain the earlier draft as an internal snapshot.

Pool reports preserve chronological candidate history, generation strategies, five rubric dimensions, criterion evidence and actual human feedback. The final image is the accepted selection in that pool, even when it is an earlier candidate; the last generation is not implicitly best. Pending acceptance is `human_review`. JSON retains the full pool/attempt ledger and original feedback. The final preview and ZIP contain only accepted, eligible raw images. Failed candidates can appear in the separate, explicitly labeled review sheet but never in the final directory. Native host previews remain outside plugin control.
