# Candidate selection and human review (helper 0.1.24)

Review pages show a responsive overview and a separate large-image dialog. Open any source/candidate, zoom or fit to the window, drag/scroll details, switch candidates while preserving position, change the backdrop, and close with Esc. Opening the viewer preserves the decision and written feedback. A local page does not submit feedback automatically.

Helper 0.1.24 preserves actual attempt numbers in reports even when a tool call fails, directs exhausted new pools into human review, and retains the original correction comment and before-revision image for multi-candidate revision pages. Full-outfit component IDs cannot hide same-named domain failures from the redraw plan.

Pass `review-sheet --language <user-language>` matching the user's current language. Interface controls, hints, choices, validation and download messages must use that language, as must the authored request and criteria. Chinese and English UI text are built in; for another language, supply `--ui-file` with a complete UTF-8 JSON text mapping using the `PREVIEW_EN` keys in the existing Python renderer. Do not silently fall back to another language. Keep JSON schema keys, anonymous aliases and asset IDs stable. The renderer stays in `candidate_review.py`; HTML pages are generated only in artwork output directories, not added to the plugin source tree.

To update an unanswered older page, use `refresh-review-sheet --project <project> --packet <packet-id>`. It returns a new HTML page for the same packet, preserves anonymous aliases and all source/candidate/assessment bindings, and retains the original HTML snapshot. Link the new page to the user. Completed feedback packets cannot be refreshed.

This is the default workflow for new expression, mouth-state, recolor, single-garment replacement, full-outfit and prop-edit requests. It supersedes the sequential revision instructions for **new** work. Existing `refinements` cases keep their saved strategy, reviews and spent budget; never migrate or rescore them to obtain a new allowance. Read [quality review](quality-review.md) and the active mode's boundaries first. This workflow improves selection and accountability; it does not promise more faithful image generation.

## Define the request before generating

Save a UTF-8 contract JSON list derived from the actual source and user request. Each check has exactly `id`, `dimension`, `component`, `property`, `expected`, `view`. Choose 5–30 focused checks covering the five rubric 1.2 dimensions. Use one property per check and make it answerable from a named inspection view. The dimensions are `target`, `identity`, `protection`, `integration`, `rendering`; views are `full_image`, `target_detail`, `protected_details`, `normal_display`, `background_edges`.

For each check, describe what is permitted and what must remain. Do not encode a particular test character, a mandatory weapon, hairstyle, garment or color. A requested expression permits appropriate feature movement; a replacement can create legitimate coverage/occlusion changes. Identity checks concern character-defining feature design; protection checks concern other unrequested content; integration checks concern construction, contact, anatomy and occlusion at the edited interface. Avoid counting the same defect independently under several dimensions. Separate genuine different consequences only when evidence supports them.

A definition has this shape (replace placeholders with inspected facts, not literal generic criteria):

```json
{"id":"target_result","dimension":"target","component":"<actual target>","property":"<requested property>","expected":"<visible success condition and permitted change>","view":"target_detail"}
```

Keep the request and contract fixed across the pool. New user requirements form a new explicit revision request; do not retroactively relax old checks. Save the prepared Outfits brief as before. Use one initial complete-source reference and a concise prompt stating target, permitted changes, invariants and output requirements once each.

## Fixed attempt budget and candidate selection

New pools (version `1.1`, helper 0.1.23) default to **three total image-tool attempts per requested result**, including the first image. One requested deliverable is not a one-call budget. Honor explicit smaller generation limits with `--budget 1` or `2`. Each expression/state or outfit/prop option has its own fixed allowance. Stop early once the full internal gate passes; three is a ceiling, not a quota. Saved version `1.0` pools and legacy `refinements` retain their original strategies, allowance and assessments; do not rewrite them or reopen spent budgets.

1. Inspect the source and save the request, contract and applicable Outfits brief before generating. Generate the initial complete image, save actual prompt and raw bytes with `add`, then `pool-start --asset <first-id> --contract-file <contract.json>` before scoring. The first tool call counts as attempt one. If it fails without a readable image, report the actual failure and stop; do not create fake art or silently retry outside the ledger.
2. Create `review-sheet --purpose assistant`, inspect its source and anonymous images, and record fresh rubric 1.2 assessments and applicable Outfits fidelity. View full image, target/protected details, normal-size display and light/dark alpha edges. Scores never carry over. Preserve the fixed contract definitions in `criteria` and link saved comparisons and the `blind_packet`.
3. Follow `pool-status`. `review` means finish internal evidence. Passage requires total ≥80, **each of all five dimensions ≥4/5**, every active domain item passed, completed inspections, no critical defects/uncertainty, and applicable fidelity/file evidence. A high total with a failed dimension or domain still requires correction. `human_review` means stop generation and present the eligible artwork. `redraw` means continue within the remaining budget, not ask the user to diagnose an already recorded failure.
4. `pool-reserve` consumes one attempt and returns a token, `review_redraw` strategy, exact reference paths, parent assessment fingerprint and `blocking_findings`. Execute the image tool once, then `pool-import` with the raw image, actual prompt and returned references. A tool failure uses `pool-fail --note` and remains spent; a local import failure uses the already generated output, never a second image call for the same token.
5. Build the next prompt in the user's language from the failed/uncertain criteria, domain evidence and fidelity notes. Name the property to correct and its fixed expected outcome; retain successful authorized edits and all original boundaries. Use the immutable source first as identity, protected-content, pose and framing authority. The preferred earlier candidate second supplies only successful edited details, not its observed defects. For broad redraw/identity/protection failures, explicitly reapply the requested edit to the source and avoid inheriting the defective layout. References are not masks or pixel locks. Do not reset the budget, weaken criteria, repaint locally or repeat an unchanged prompt as if it used the review.
6. Review each new candidate completely, including previously passed dimensions to detect regressions. With two or more assessed images, make a fresh anonymous assistant packet for all candidates in this pool and record `pool-compare` with `basis: assistant`, preferred alias or tie, concrete evidence and `repairable`/`repair_plan` fields. A failed image cannot outrank a passed one. For new 1.1 pools, a tie or `repairable: false` does not cancel remaining attempts; choose the named preferred version or latest assessed fallback as the next correction reference. The old near-pass restriction on a third repair applies only to saved 1.0 pools.
7. On full passage, stop; on `exhausted`, stop after the recorded limit and explain the remaining failed dimensions/domain items and actual generation failures before human review. Retain earlier candidates if later ones regress. No fourth attempt is permitted. Missing/changed evidence is `blocked`: resolve the existing files/evidence rather than resetting the ledger or fabricating a pass. Final artwork still requires actual human acceptance and all delivery gates.

Scores are assistant observations, not calibrated measurements. The anonymous packet hides chronology, prompts and prior scores in the review material, but an assistant in the same chat may remember earlier context. Describe this as anonymous presentation, **not an independent blinded experiment**. Do not invoke another agent/model or external service without an applicable authorization.

## Make human review visible and actionable

After internal passage or recorded budget exhaustion, create `review-sheet --purpose user` for the eligible candidate(s). If none pass, show the closest candidate(s) explicitly as **failed inspection evidence** along with concise blockers. This workflow authorizes an inspection presentation; it does not authorize final delivery of failed art.

Show the original and A/B(/C) images inline using the returned absolute paths, link the local HTML review page, and invite one decision in chat:

> 请选择采用的版本，或指出需要调整的地方。可以回复“采用 A”“B 需要修改：…”或“都不采用”。你的决定会用于最终交付；内部评分不能代替你的选择。

Keep the initial comparison free of scores and chronology. Explain any known blocking issue before final acceptance is processed; do not present an unexportable result as ready to package. The page supports light/dark backgrounds, enlarged inspection, a deliberate decision (no preselected acceptance), optional satisfaction facets and a JSON feedback download. It runs locally without a server, account or MCP, and cannot submit anything by itself. The user can simply reply in chat instead of downloading a file. Do not demand both.

When the user replies, map their actual choice to the same packet and call `human-feedback` with JSON:

```json
{"packet":"<returned-id>","basis":"user","candidate":"A","decision":"accept","note":"<actual user words>","facets":{}}
```

`decision` is `accept`, `revise` or `reject`; `reject` uses `candidate: null`. `revise` requires a specific user note. Facets are optional observations actually supplied by the user, never inferred ratings. Preserve the user's original words; explain any interpretation separately. Do not manufacture human feedback from internal scores, silence or initial permission to perform generation.

The helper binds feedback to image/source hashes and the reviewed assessment. It retains positive feedback even if quality/fidelity/canvas checks block export. Valid acceptance selects that exact candidate; then continue the already requested report/packaging work without asking the user to approve it a second time. If packaging was not requested, deliver the accepted PNG/report without inventing a ZIP requirement. Rejection and requested changes do not select or export. They close this batch without deleting any candidate.

For a specific user-requested correction, use the linked human-revision commands below instead of importing an unrelated candidate with `add`. A vague dislike calls for clarification of the desired change, not speculative extra generation. A new packet can record a changed user decision; earlier feedback remains in history.

After feedback, tell the user what they chose, what Codex's current checks say, and the resulting action: exported, revision requested, stopped, or blocked with concrete reasons. This is the human-to-Codex handoff. `report`, `deliver`, `review accepted`, `select`, and `export` cannot bypass required pool feedback. Reports before acceptance contain findings only, with no final PNG package.

## Continue a specific human correction

`human-feedback` with `decision: revise` returns the selected asset, original comment and review packet. Use that binding even when the user chose an earlier candidate. An explicit, actionable correction starts a new default three-attempt review/redraw batch (or the user’s explicit smaller cap); recording feedback itself does not invoke the image tool. Clarify an unspecified dislike before preparing a revision. Do not ask the user to repeat an already clear correction or choice.

1. Inspect the chosen candidate and its existing pool contract/Outfits brief. Derive the revised contract from the original and the actual comment: retain all original IDs, components, properties, inspection views and non-target expectations. Target expectations may change for the correction; add focused checks when needed. Keep this within the existing expression/mouth state or garment option and its edit boundary. A different expression/state, garment, color or replacement design needs a separate request/option, not silently altered metadata. Never relax protected-region checks to accommodate a defect.
2. Run `revision-prepare --packet <feedback-packet> --contract-file <revised-contract.json>`. It saves the original user words and immutable source/chosen-candidate fingerprints, reserves the first call of a fixed-budget revision batch, and returns both reference paths and inherited edit fields. Repeating it returns the same request; it does not reset the allowance. Inspect its `next_action`; generate only for `generate_revision`, and execute the image call once.
3. Use the returned references in order: immutable original for identity/protected details, then the **user-chosen candidate as the edit target**. Describe the specific correction and preserve its successful requested change within the original bounds. Save the actual submitted prompt in the user's language. These are reference instructions, not masks or pixel locks. Do not use the newest, highest-scoring or original-costume image as a substitute for the selected edit target.
4. Run `revision-import` with the revision ID, raw output, actual prompt and both reference paths. The helper inherits the selected version's expression/mouth state or garment definition/brief, binds `parent_asset_id` to that version, and starts a new **version-1.1 pool with the recorded revision budget (default 3)** with the revised contract. It retains old images, feedback, reviews, pools and selections for other slots. No old quality/fidelity score or user acceptance carries over. If the image call fails, use `revision-fail --note`; the attempt stays spent. A local import error is resolved using the already generated output, not another image call.
5. Make an assistant packet and perform fresh rubric 1.2 checks and applicable Outfits fidelity checks. Follow the same internal review/redraw loop until passage or exhaustion. Then create the new user packet with `review-sheet --asset <new-id> --purpose user --language <user-language>`. It includes original, **before revision**, the new anonymous candidate and the original correction comment; returned `revision_parent`/`revision_note` support inline comparison. The old version is a reference, not a selectable new candidate. Fresh actual acceptance is required before delivery. A further specific correction uses this new packet and starts another linked request; failure within this batch uses its remaining allowance; it does not grant a fourth call or reset the original batch.

Final reports and export manifests preserve the parent version and original correction request alongside the new assessment and decision. A newer actual decision on the same parent cancels a pending correction and keeps its history; re-preparing a cancelled request cannot generate. Do not describe the user request as fulfilled merely because import succeeded. If generation or inspection fails, retain the request and findings and explain the concrete outcome.

```text
python <skill>/scripts/studio.py revision-prepare --project <project> --packet <actual-revise-packet> --contract-file <revised-contract.json>
# Execute each reserved call once using its returned reference_paths, then:
python <skill>/scripts/studio.py revision-import --project <project> --revision <returned-revision> --image <raw.png> --prompt-file <submitted.txt> --reference <immutable-source.png> --reference <user-chosen.png>
# If the image call failed instead:
python <skill>/scripts/studio.py revision-fail --project <project> --revision <returned-revision> --note <actual-tool-failure>
# Import creates the new pool; do not call add or pool-start for it. Review and obtain actual user feedback anew.
```

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
python <skill>/scripts/studio.py pool-import --project <project> --case <first-id> --token <token> --image <raw.png> --prompt-file <actual.txt> --reference <source.png> --reference <preferred-candidate.png>
# For review_redraw, pass both returned references: source first, preferred candidate second.
python <skill>/scripts/studio.py review-sheet --project <project> --asset <first-id> --asset <second-id> --purpose assistant
python <skill>/scripts/studio.py pool-compare --project <project> --case <first-id> --feedback-file <comparison.json>
python <skill>/scripts/studio.py review-sheet --project <project> --asset <chosen-id> --purpose user
# Present the page/images and wait for actual user feedback.
python <skill>/scripts/studio.py human-feedback --project <project> --feedback-file <actual-user-feedback.json>
python <skill>/scripts/studio.py report --project <project> --stage final --output <new-delivery-directory>
python <skill>/scripts/studio.py export --project <project>
```

Work sequentially in a project. Preserve raw image bytes; preview resizing is only for display. No mask, local repaint/composite or new backend is introduced.
