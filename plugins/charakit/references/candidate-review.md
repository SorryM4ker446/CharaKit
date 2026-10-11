# Candidate selection and human review (helper 0.1.19)

Review pages show a responsive overview and a separate large-image dialog. Open any source/candidate, zoom or fit to the window, drag/scroll details, switch candidates while preserving position, change the backdrop, and close with Esc. Opening the viewer preserves the decision and written feedback. A local page does not submit feedback automatically.

Pass `review-sheet --language <user-language>` matching the user's current language. Interface controls, hints, choices, validation and download messages must use that language, as must the authored request and criteria. Chinese and English UI text are built in; for another language, supply `--ui-file` with a complete UTF-8 JSON text mapping using the `PREVIEW_EN` keys in the existing Python renderer. Do not silently fall back to another language. Keep JSON schema keys, anonymous aliases and asset IDs stable. The renderer stays in `candidate_review.py`; HTML pages are generated only in artwork output directories, not added to the plugin source tree.

To update an unanswered older page, use `refresh-review-sheet --project <project> --packet <packet-id>`. It returns a new HTML page for the same packet, preserves anonymous aliases and all source/candidate/assessment bindings, and retains the original HTML snapshot. Link the new page to the user. Completed feedback packets cannot be refreshed.

This is the default workflow for new expression, mouth-state, recolor and single-garment replacement requests. It supersedes the sequential revision instructions for **new** work. Existing `refinements` cases keep their saved strategy, reviews and spent budget; never migrate or rescore them to obtain a new allowance. Read [quality review](quality-review.md) and the active mode's boundaries first. This workflow improves selection and accountability; it does not promise more faithful image generation.

## Define the request before generating

Save a UTF-8 contract JSON list derived from the actual source and user request. Each check has exactly `id`, `dimension`, `component`, `property`, `expected`, `view`. Choose 5–30 focused checks covering the five rubric 1.2 dimensions. Use one property per check and make it answerable from a named inspection view. The dimensions are `target`, `identity`, `protection`, `integration`, `rendering`; views are `full_image`, `target_detail`, `protected_details`, `normal_display`, `background_edges`.

For each check, describe what is permitted and what must remain. Do not encode a particular test character, a mandatory weapon, hairstyle, garment or color. A requested expression permits appropriate feature movement; a replacement can create legitimate coverage/occlusion changes. Identity checks concern character-defining feature design; protection checks concern other unrequested content; integration checks concern construction, contact, anatomy and occlusion at the edited interface. Avoid counting the same defect independently under several dimensions. Separate genuine different consequences only when evidence supports them.

A definition has this shape (replace placeholders with inspected facts, not literal generic criteria):

```json
{"id":"target_result","dimension":"target","component":"<actual target>","property":"<requested property>","expected":"<visible success condition and permitted change>","view":"target_detail"}
```

Keep the request and contract fixed across the pool. New user requirements form a new explicit revision request; do not retroactively relax old checks. Save the prepared Outfits brief as before. Use one initial complete-source reference and a concise prompt stating target, permitted changes, invariants and output requirements once each.

## Fixed attempt budget and candidate selection

Use the user's authorized count. A one-image request gets budget 1. An explicitly enabled automatic improvement batch permits at most 3 total attempts, including the initial image; this is not authorization to generate three images for every ordinary request.

1. Generate the first image, archive its actual prompt and raw bytes using `add`, then `pool-start --asset <first-id> --contract-file <contract.json> --budget <1-3>` **before** scoring. If the first tool call fails without an image, stop and report the failed call rather than silently retrying outside the ledger.
2. Create `review-sheet --purpose assistant`, inspect its source and anonymous images, and record one fresh rubric 1.2 assessment per candidate. Preserve full/detail/normal-size/light-dark comparisons with `quality --comparison`; Outfits also requires fresh `fidelity`. `blind_packet` identifies the anonymous packet, and the assessment's `criteria` retain the exact contract definitions, adding `observed`, `status`, and `score`.
3. Read `pool-status`. `review` means finish inspection. `human_review` means stop generating and present human review. `sample` permits an independent second sample **from the immutable source alone**, using the same requirements. Do not carry the first candidate's defects or appearance into that prompt.
4. Before another tool call, `pool-reserve` consumes one attempt and returns its token, strategy and exact references. Execute once, then use `pool-import` with that token, actual prompt, raw image and references. A tool failure uses `pool-fail --note`; it stays spent. Never reserve twice or retry the same token. An import/CLI failure after a successful tool call is resolved by importing the already saved image, not generating again.
5. With two or more assessed candidates, `compare` requires a new anonymous assistant packet containing all pool candidates. Record `pool-compare` with packet ID, `basis: assistant`, preferred alias (or `null` for tie), `evidence`, `repairable` boolean, and `repair_plan` when true. Compare against the source and fixed contract. Hard failures lose to passed candidates, regardless of total. Among eligible candidates compare requested-result quality, fidelity and visible finish; do not automatically favor the newest candidate or higher numerical total. A tie can stop without spending the remaining budget.
6. A third call is permitted only when no candidate passes and the preferred candidate is close: target ≥4, all dimensions ≥3, no more than two dimensions below 4, no critical defects or unresolved uncertainty, plus a concrete feasible repair plan. The helper enforces these record conditions, not whether the model can actually repair them. `repair_best` references source first and preferred candidate second; correct only evidenced defects while retaining successful changes. It may target the first candidate rather than the second.
7. Compare the third result with earlier candidates. Retain the preferred earlier version if the revision regresses. An exhausted/blocked pool authorizes no further calls. A preferred failed candidate is still failed; do not export it as a final.

Scores are assistant observations, not calibrated measurements. The anonymous packet hides chronology, prompts and prior scores in the review material, but an assistant in the same chat may remember earlier context. Describe this as anonymous presentation, **not an independent blinded experiment**. Do not invoke another agent/model or external service without an applicable authorization.

## Make human review visible and actionable

After internal inspection/selection, create `review-sheet --purpose user` for the eligible candidate(s). If none pass, show the closest candidate(s) explicitly as **failed inspection evidence** along with concise blockers. This workflow authorizes an inspection presentation; it does not authorize final delivery of failed art.

Show the original and A/B(/C) images inline using the returned absolute paths, link the local HTML review page, and invite one decision in chat:

> 请选择采用的版本，或指出需要调整的地方。可以回复“采用 A”“B 需要修改：…”或“都不采用”。你的决定会用于最终交付；内部评分不能代替你的选择。

Keep the initial comparison free of scores and chronology. Explain any known blocking issue before final acceptance is processed; do not present an unexportable result as ready to package. The page supports light/dark backgrounds, enlarged inspection, a deliberate decision (no preselected acceptance), optional satisfaction facets and a JSON feedback download. It runs locally without a server, account or MCP, and cannot submit anything by itself. The user can simply reply in chat instead of downloading a file. Do not demand both.

When the user replies, map their actual choice to the same packet and call `human-feedback` with JSON:

```json
{"packet":"<returned-id>","basis":"user","candidate":"A","decision":"accept","note":"<actual user words>","facets":{}}
```

`decision` is `accept`, `revise` or `reject`; `reject` uses `candidate: null`. `revise` requires a specific user note. Facets are optional observations actually supplied by the user, never inferred ratings. Preserve the user's original words; explain any interpretation separately. Do not manufacture human feedback from internal scores, silence or initial permission to perform generation.

The helper binds feedback to image/source hashes and the reviewed assessment. It retains positive feedback even if quality/fidelity/canvas checks block export. Valid acceptance selects that exact candidate; then continue the already requested report/packaging work without asking the user to approve it a second time. If packaging was not requested, deliver the accepted PNG/report without inventing a ZIP requirement. Rejection and requested changes do not select or export. They close this batch without deleting any candidate.

For a specific user-requested correction, preserve the old pool and start a fresh explicit one-candidate revision request (budget 1 unless the user grants more). Inspect the selected reference and preserve its successful requested change in the new brief; no hidden reset of the old automatic budget. A vague dislike calls for clarification of the desired change, not speculative extra generation. A new packet can record a changed user decision; earlier feedback remains in history.

After feedback, tell the user what they chose, what Codex's current checks say, and the resulting action: exported, revision requested, stopped, or blocked with concrete reasons. This is the human-to-Codex handoff. `report`, `deliver`, `review accepted`, `select`, and `export` cannot bypass required pool feedback. Reports before acceptance contain findings only, with no final PNG package.

## Calibration without rewriting history

Keep `human_feedback_history` and optional facets as future calibration examples: assistant-pass/user-reject and assistant-fail/user-accept are disagreements to investigate, not permission to change the recorded score. Only adopt examples as reusable scoring anchors when the user endorses the relevant general criterion; do not turn one outfit preference into a universal style rule. Compare future rubric versions against these anchored examples and version changes explicitly. Do not claim calibration has happened merely because feedback was collected.

## CLI sequence

```text
python <skill>/scripts/studio.py pool-start --project <project> --asset <first-id> --contract-file <contract.json> --budget 3
python <skill>/scripts/studio.py review-sheet --project <project> --asset <first-id> --purpose assistant
# Inspect anonymous evidence; record fidelity if applicable, then quality with rubric 1.2.
python <skill>/scripts/studio.py pool-status --project <project> --case <first-id>
python <skill>/scripts/studio.py pool-reserve --project <project> --case <first-id>
# Only now execute the returned generation plan once.
python <skill>/scripts/studio.py pool-import --project <project> --case <first-id> --token <token> --image <raw.png> --prompt-file <actual.txt> --reference <source.png>
# For repair_best also append --reference <preferred-candidate.png>.
python <skill>/scripts/studio.py review-sheet --project <project> --asset <first-id> --asset <second-id> --purpose assistant
python <skill>/scripts/studio.py pool-compare --project <project> --case <first-id> --feedback-file <comparison.json>
python <skill>/scripts/studio.py review-sheet --project <project> --asset <chosen-id> --purpose user
# Present the page/images and wait for actual user feedback.
python <skill>/scripts/studio.py human-feedback --project <project> --feedback-file <actual-user-feedback.json>
python <skill>/scripts/studio.py report --project <project> --stage final --output <new-delivery-directory>
python <skill>/scripts/studio.py export --project <project>
```

Work sequentially in a project. Preserve raw image bytes; preview resizing is only for display. No mask, local repaint/composite or new backend is introduced.
