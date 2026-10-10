# Final images, preview and generation report

After a requested generation/revision batch finishes, run `report` before the final response. Deliver the returned passed full PNGs, the final preview and the Markdown report. Use the user's language and short labels. A one-image request still gets a report; a multi-module batch can share one report. Do not add image generations to prepare these artifacts.

The report is assembled from saved quality/fidelity observations and current delivery gates, not a new visual assessment. It includes the original request, source, per-case outcome, per-round dimension/total scores, final domain checks, inspection coverage, dimensions/warnings, failure findings and links to actual prompts/comparisons. Markdown is the human-readable report; JSON retains full findings, provenance paths and final/preview hashes. Do not invent time/cost/model measurements or reinterpret old failures as passes. Report labels are localized; historical observations retain the language in which they were saved.

```text
python <either-skill>/scripts/studio.py report --project <expressions-project> --project <outfits-project> --output <new-delivery-dir> --language zh-CN --labels-file <labels.json> --face-box <left> <top> <right> <bottom>
```

`--project` is repeatable and this shared command may read both implemented modules. By default it reports the latest candidate for each expression/mouth-state or garment/color slot in the supplied projects. Use fresh task projects, or restrict a single existing project with repeated `--asset` arguments so unrelated historical slots do not enter this task's report. A tracked asset selects its whole refinement case and resolves to the current version; the command cannot deliver its earlier failed version. Duplicate cases are rejected. Completed cases are `passed` or `exhausted`; pending review/revision and blocked evidence are explicitly labeled, not reported as completed successes.

`--output` must name a new directory. Optional `--language en`, `--title`, `--background light|dark|checker` and localized `--labels-file` customize presentation. Label keys use expression/outfit IDs, `mouth_open`, `mouth_closed`, a full expression/mouth slot or `source`. `--face-box` adds source-coordinate face details to the display sheet and must fit every supplied source. The preview contains source references and only passed final versions. Inspection previews produced earlier remain linked in the report, without being promoted to final assets or overwritten.

The command returns:

- `images`: unchanged passed PNG copies in `final/`; each is rechecked through `deliver` and fingerprinted. This does not accept/select/export artwork.
- `preview`: a display-only PNG with passed finals and source references, or `null` when none passed.
- `report` and `manifest`: `report.md` and `report.json`, including failed cases even in a mixed batch.

If all cases fail, deliver only the report; `images` is empty and no image preview/final PNG is created. Three failed rounds do not authorize a fourth. Keep candidates and observations archived, explain the blocking component and suggest addressing the recorded defects rather than lowering the score threshold. Users may inspect process evidence through report links; process images are not acceptance criteria.

Render/view the actual returned preview and passed images, and check the report's counts, labels and image links. In the final response, show each PNG in the returned `images` list as a separate inline image with a short localized caption, then show the returned final `preview` inline and link the Markdown `report`. In Codex, use Markdown image syntax with the actual absolute local path, for example `![Happy](D:/project/delivery/final/happy.png)`. Wrap a destination containing spaces in angle brackets, for example `![Happy](<D:/My Project/delivery/final/happy.png>)`. Plain file links alone do not provide the requested image presentation. Keep separate full PNGs available even when a comparison preview exists; do not replace them with crops or the preview sheet. For a large batch, follow the user's requested display scope and retain access to all passed PNGs through the report.

Codex controls the native image viewer, navigation and thumbnail layout. The Skill provides separate image attachments/embeds; it does not implement viewer controls or guarantee gallery grouping, order, or a particular thumbnail sidebar. Do not fabricate an interactive viewer, regenerate artwork, or alter final pixels just to imitate the host UI. Do not present failed candidates or intermediate inspection images as final images. Host-native image generation previews may already have appeared automatically.

Reports are immutable snapshots in new directories. Project metadata, candidate pixels, saved prompts and earlier evidence stay unchanged. Regenerate to a new directory after later edits; stale or missing evidence/file failures are recorded and block image delivery. A source/project that cannot be read safely produces an error instead of fabricated observations. Use helper 0.1.15 or later.
