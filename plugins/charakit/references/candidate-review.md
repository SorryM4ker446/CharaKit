# Candidate selection and human review (helper 0.1.31)

## Revision baselines and task-based inspection

These shared rules apply to Expressions, every Outfits edit type, Poses and future modules. Derive concrete regions and permitted changes from the current request and artwork; never use a past character or test edit as a template.

For a new human correction, the **user-chosen candidate is the primary editing baseline**. New `revision-prepare` plans return that edit target first, the immutable source second, and all scoped design references afterward. Explicit prompt roles are required; input order alone does not enforce preservation. Later internal redraws edit their recorded correction parent while retaining the original user-chosen baseline and policy. Saved revisions without this policy keep their existing order, contract and budget.

Preserve successful authorized edits outside the current correction. The immutable source remains a mandatory secondary review reference for identity and all **still-protected** regions. Compare those regions with the source on every revision, recording visible differences and whether they violate the contract. Exclude previously authorized clothing, props, expression/pose movements and necessary interfaces from source-restoration requirements. A source check is not permission to put back superseded features. Two explicit protection checks, `revision_continuity` and `source_protection_recheck`, are added to new revision contracts; either can block passage and trigger redraw even above 80. Documented unauthorized drift is a repair target under the existing protection contract and does not require another permission request. Repair only the observed protected properties, never revert authorized differences. They do not replace the five dimensions or domain/fidelity checks. Their observations are visual judgments, not automatic similarity percentages; summarize the two comparisons without double-counting the same defect.

When the user explicitly asks to recover an original protected feature, name the applicable identity/protection criterion with repeated `revision-prepare --restore-check <criterion-id>`. Limit restoration instructions to those properties; the remaining edited image stays the baseline. Keep this scope through every redraw. Do not reset a budget or silently switch to rebuilding the entire edit from the source. A broad rebuild requires an explicit request explaining which successful changes must survive.

An already edited image supplied as a new task's source becomes that project's immutable baseline. Do not search for an earlier illustration of the same character and silently use it as generation authority. Reuse an earlier project's source only when the user continues that recorded project or explicitly supplies its reference role.

Human revision previews default to **before revision versus new candidate**; the viewer can switch its comparison baseline to the original source for secondary preservation review. Source, before-revision image, design references and every available candidate remain visible, with context images nonselectable.

Keep the full image in all reviews. Choose local views from the **current correction and demonstrated risks**, not every previous page: an expression edit generally warrants a whole-face view; a garment or object edit needs its actual target and affected interfaces; add protected-region views when they help inspect a reported or observed issue. Internal full/protected inspection remains required even if the human menu has no face crop. The helper does not detect landmarks or infer boxes from prose; Codex inspects the images and records the task-based plan.

Use `--inspection-file` on `revision-prepare` to save up to four focused regions for that correction. `review-sheet --inspection-file` can supply an explicit review plan in either module; it cannot be combined with individual face/detail boxes. Use `[]` for full-image-only review. New human corrections default to full images if no focused plan is supplied, rather than inheriting unrelated regions or the whole old outfit box. Give each region a stable filename-safe `id`, a source-coordinate `box`, a short label in the user's language, and a concrete `reason` tied to the task or observed risk:

```json
[{"id":"edited_interface","box":[40,200,240,420],"label":"<localized edited interface>","reason":"<current correction or observed risk>"}]
```

Replace coordinates and text with inspected facts. A region can identify any relevant garment, object, hair, facial detail or other editable/protected area; these are inspection views, not masks or new edit types. Full-only pages hide the redundant range selector. Recorded regions and their labels follow actual acceptance into the final report; revision detail comparisons use the chosen pre-revision baseline. Source coordinates are shared across images without automatic alignment or pixel repair.

Human pages default to **every readable, unchanged candidate in the same batch**, including failed and earlier versions. Supplying one `--asset` identifies the batch; it does not hide its other candidates. Recommendations and internal findings appear separately, without preselecting a decision. A/B/C are anonymous labels, not generation order. Assistant packets remain blind and follow their explicitly supplied inspection IDs.

Optional references in every current or future editing mode follow [scoped edit references](edit-references.md): each gets a recorded target criterion, is shown as nonselectable context, and remains an actual input in every redraw and human revision. Always use the complete returned input list; the two-input CLI examples below assume no extra scoped references.

Review pages retain a full-canvas overview and add optional, collapsed detail comparisons. Pass `review-sheet --face-box <left> <top> <right> <bottom>` for a source-grounded whole-face view and `--detail-box` for another inspected region; Outfits defaults to the saved brief's target box. Use inspected coordinates rather than guessed facial landmarks. All candidates use the same source coordinates; a different canvas is mapped proportionally for viewing, never aligned, recentered or repaired. A full-outfit target may span most of the body. Returned `detail_views` contains inspection PNGs, not deliverable sprites. Legacy human correction pages retain their previous inspection boxes; new corrections use their own recorded task-based regions.

The large-image dialog opens fitted to the window, supports the recorded full/detail views and synchronized comparison with the source or chosen before-revision baseline, and retains scale and position while switching candidates. Drag or scroll either pane, change the backdrop, and close with Esc. Candidate-level use/revise buttons only fill a feedback draft; viewing another image does not change that choice. Extra ratings remain optional and collapsed. Copy feedback into chat or download its JSON; clipboard failure reveals selectable text. Neither action submits, selects project assets, generates or packages anything automatically. Only actual feedback returned to the assistant enters `human-feedback`. Detail files are bound to the review packet and changed files invalidate the evidence.

Helper 0.1.24 preserves actual attempt numbers in reports even when a tool call fails, directs exhausted new pools into human review, and retains the original correction comment and before-revision image for multi-candidate revision pages. Full-outfit component IDs cannot hide same-named domain failures from the redraw plan.

Before authoring, follow [localization.md](localization.md) to identify and persist the task language. `review-sheet`, `preview` and `report` inherit that language and the same complete, reviewed language pack; an explicit `--language` is an output-only override. Interface controls, hints, choices, validation and download messages use the selected language. Author and register new requests and criteria in that language; translate historical prose only for display, preserving original records and scores. HTML packets retain both original and display content and refresh from their saved presentation snapshot. Built-in Chinese/English and arbitrary external packs share this workflow. Legacy complete `--ui-file` pages remain compatible; new tasks use a shared pack for all output types. Keep JSON schema keys, anonymous aliases and asset IDs stable. The renderer stays in `candidate_review.py`; HTML pages are generated only in artwork output directories, not added to the plugin source tree.

To update an unanswered older page, use `refresh-review-sheet --project <project> --packet <packet-id>`. It returns a new HTML page for the same packet, preserves anonymous aliases and all source/candidate/assessment bindings, and retains the original HTML snapshot. Link the new page to the user. Completed feedback packets cannot be refreshed.

Refresh preserves the packet's existing inspection regions; to add a new region, create a new packet with explicit source coordinates. Older custom-language pages without the new interaction labels retain their prior translated interface rather than receiving untranslated controls. Final reports carry the recorded task-based regions into baseline-versus-selected comparisons only after actual acceptance and all delivery gates; rejected or failed candidates never become final detail assets.

This is the default workflow for new expression, mouth-state, recolor, single-garment replacement, full-outfit, prop-edit and pose-edit requests. It supersedes the sequential revision instructions for **new** work. Existing `refinements` cases keep their saved strategy, reviews and spent budget; never migrate or rescore them to obtain a new allowance. Read [quality review](quality-review.md) and the active mode's boundaries first. This workflow improves selection and accountability; it does not promise more faithful image generation.

For Poses with recorded arm/contact/overlap requirements, include the preparation result's four `interaction_criteria` in the contract before generation. Keep their exact components, dimensions and expected descriptions. Internal redraws, source restarts and human revisions preserve the same `pose_interaction`; a new arrangement uses a new option ID. Follow the [pose interaction definition](../skills/charakit-poses/references/pose-guide.md#arm-contact-and-occlusion-definition) when reviewing visible contacts and legitimately hidden hands.

## Define the request before generating

Save a UTF-8 contract JSON list derived from the actual source and user request. Each check has exactly `id`, `dimension`, `component`, `property`, `expected`, `view`. Choose 5–30 focused checks covering the five rubric 1.2 dimensions. Use one property per check and make it answerable from a named inspection view. The dimensions are `target`, `identity`, `protection`, `integration`, `rendering`; views are `full_image`, `target_detail`, `protected_details`, `normal_display`, `background_edges`.

For each check, describe what is permitted and what must remain. Do not encode a particular test character, a mandatory weapon, hairstyle, garment or color. A requested expression permits appropriate feature movement; a replacement can create legitimate coverage/occlusion changes. Identity checks concern character-defining feature design; protection checks concern other unrequested content; integration checks concern construction, contact, anatomy and occlusion at the edited interface. Avoid counting the same defect independently under several dimensions. Separate genuine different consequences only when evidence supports them.

A definition has this shape (replace placeholders with inspected facts, not literal generic criteria):

```json
{"id":"target_result","dimension":"target","component":"<actual target>","property":"<requested property>","expected":"<visible success condition and permitted change>","view":"target_detail"}
```

Keep the request and contract fixed across the pool. New user requirements form a new explicit revision request; do not retroactively relax old checks. Save the prepared Outfits brief as before. Use one initial complete-source reference and a concise prompt stating target, permitted changes, invariants and output requirements once each.

## Fixed attempt budget and candidate selection

New initial-request pools (version `1.2`, helper 0.1.30) default to **three total image-tool attempts per requested result**, including the first image. One requested deliverable is not a one-call budget. Honor explicit smaller limits with `--budget 1` or `2`. Each expression/state, outfit/prop option or pose action has its own fixed allowance. Stop early on full passage. Human-correction pools remain version `1.1`. Saved `1.0`/`1.1` pools and legacy refinements retain their original strategies, allowance and assessments; do not rewrite them or reopen spent budgets.

1. Inspect the source and save the request, contract and applicable Outfits brief before generating. Generate the initial complete image, save actual prompt and raw bytes with `add`, then `pool-start --asset <first-id> --contract-file <contract.json>` before scoring. The first tool call counts as attempt one. If it fails without a readable image, report the actual failure and stop; do not create fake art or silently retry outside the ledger.
2. Create `review-sheet --purpose assistant`, inspect its source and anonymous images, and record fresh rubric 1.2 assessments and applicable Outfits fidelity. View full image, target/protected details, normal-size display and light/dark alpha edges. Scores never carry over. Preserve the fixed contract definitions in `criteria` and link saved comparisons and the `blind_packet`.
3. Follow `pool-status`. `review` means finish internal evidence. Passage requires total ≥80, **each of all five dimensions ≥4/5**, every active domain item passed, completed inspections, no critical defects/uncertainty, and applicable fidelity/file evidence. A high total with a failed dimension or domain still requires correction. `human_review` means stop generation and present the eligible artwork. `redraw` means continue within the remaining budget, not ask the user to diagnose an already recorded failure.
4. `pool-reserve` consumes one attempt and returns a token, the chosen `review_redraw` or `source_restart` strategy, exact reference paths, parent assessment fingerprint and `blocking_findings`. Execute the image tool once, then `pool-import` with the raw image, actual prompt and returned references. Tool failures remain spent; a local import failure uses the existing raw output, never a second image call for the same token.
5. Build the prompt from recorded failures, merging repeated observations of the same component/property. Follow the returned strategy and actual input roles. `review_redraw` uses the source first and earlier candidate second; the candidate supplies successful edited details, not its defects. `source_restart` reapplies the fixed request/brief to the source with all already-bound scoped references, **without submitting the failed candidate image**. Describe the successful action/design through its recorded requirements; do not refer to an absent candidate as “image 2” or add an unbound reference. Human revisions keep their recorded edit target first and retain successful edits. References are not masks or pixel locks; do not reset budgets, weaken criteria or repaint locally.
6. Review every new candidate completely, including previously passed dimensions. With two or more assessed images, create a fresh anonymous assistant packet for all pool candidates and record `pool-compare` with actual evidence. A failed image cannot outrank a passed one. For `1.1`/`1.2` pools, a tie or `repairable: false` does not cancel remaining attempts. The preferred version or latest assessed fallback remains the failure-evidence parent even when excluded from tool inputs. The old near-pass restriction applies only to saved `1.0` pools.
7. On full passage, stop; on `exhausted`, stop after the recorded limit and explain the remaining failed dimensions/domain items and actual generation failures before human review. Retain earlier candidates if later ones regress. No fourth attempt is permitted. Missing/changed evidence is `blocked`: resolve the existing files/evidence rather than resetting the ledger or fabricating a pass. Final artwork still requires actual human acceptance and all delivery gates.

Scores are assistant observations, not calibrated measurements. The anonymous packet hides chronology, prompts and prior scores in the review material, but an assistant in the same chat may remember earlier context. Describe this as anonymous presentation, **not an independent blinded experiment**. Do not invoke another agent/model or external service without an applicable authorization.

## Make human review visible and actionable

### Restart after stalled protection

Only new initial `1.2` pools can select `source_restart`. Both of the two latest assessed candidates must pass target criteria, applicable target domain checks and target fidelity, with complete inspections. A restart requires the same identity/protection criterion to fail twice with no score increase, a repeated protected-domain failure with no improvement in its corresponding dimension, or repeated failed protection fidelity with no protection-score increase. Uncertainty alone, a different failed property, improvement of the contributing check, canvas mismatch or a failed tool call does not establish this signal. A still-failed target continues candidate-based correction.

`pool-status` returns `next_strategy` and `restart_evidence`; reservation snapshots review/fidelity fingerprints and contributing checks. This routes from saved observations, not proof that defects are identical or that restarting improves quality. The restart spends the remaining third attempt and retains action/side/anchors/design definitions and every scoped reference. The failed parent stays in lineage and the gallery as review evidence, not an image input. Imports reject extra candidate inputs and changed bindings. Existing pools and all human revisions retain their baseline strategies. Assess the new image completely without inheriting scores.

### Present the complete batch

After internal passage or recorded budget exhaustion, create `review-sheet --purpose user` using an asset from the current batch. The helper expands to all its readable, unchanged candidates: first-round passage shows one; passage after redraw shows the passing version and earlier failures; exhaustion shows every available version as inspection evidence. Keep the original correction parent and scoped reference images as nonselectable context; do not mix different batches just because they share a slot.

Recommend a version using the saved comparison and its visible evidence, separately from what is displayed. The page reports internal passage/failures in an optional details section, and never selects the recommendation for the user. A failed candidate remains available for evaluation or a concrete revision request; positive feedback cannot bypass delivery gates or cause a different recommended candidate to be exported instead.

Only the user's explicit request for a narrower view permits omitting readable candidates: use `--selection-note <actual user request>` with the requested `--asset` IDs. Do not invent this request. The page records the full candidate count, shown count and omission reasons. Missing/invalid/changed candidate files may be omitted from an otherwise completed batch with visible explanation; tool failures are separately recorded and do not create phantom candidates. Changed references, unreviewed work and incomplete internal rounds remain blocked. Do not silently deduplicate or replace earlier versions with the latest. Old saved pages keep their aliases and bindings when refreshed; create a new packet to apply the new presentation policy.

This workflow authorizes an inspection presentation; it does not authorize final delivery of failed art.

Show the original and A/B(/C) images inline using the returned absolute paths, link the local HTML review page, and invite one decision in chat:

> 请选择采用的版本，或指出需要调整的地方。可以回复“采用 A”“B 需要修改：…”或“都不采用”。你的决定会用于最终交付；内部评分不能代替你的选择。

Keep the initial comparison free of scores and chronology. Explain any known blocking issue before final acceptance is processed; do not present an unexportable result as ready to package. The page supports light/dark backgrounds, enlarged inspection, a deliberate decision (no preselected acceptance), optional satisfaction facets and a JSON feedback download. It runs locally without a server, account or MCP, and cannot submit anything by itself. The user can simply reply in chat instead of downloading a file. Do not demand both.

When the user replies, map their actual choice to the same packet and call `human-feedback` with JSON:

```json
{"packet":"<returned-id>","basis":"user","candidate":"A","decision":"accept","note":"<actual user words>","facets":{}}
```

`decision` is `accept`, `revise` or `reject`; `reject` uses `candidate: null`. `revise` requires a specific user note. Facets are optional observations actually supplied by the user, never inferred ratings. Preserve the user's original words; explain any interpretation separately. Do not manufacture human feedback from internal scores, silence or initial permission to perform generation.

The helper binds feedback to image/source hashes and the reviewed assessment. It retains positive feedback even if quality, fidelity or blocking file checks prevent export. Canvas mismatch alone is a warning: show the source and actual dimensions and explain that files remain unchanged. Valid acceptance selects that exact candidate; then continue the already requested report/packaging work without asking the user to approve it a second time. If packaging was not requested, deliver the accepted PNG/report without inventing a ZIP requirement. Rejection and requested changes do not select or export. They close this batch without deleting any candidate.

For a specific user-requested correction, use the linked human-revision commands below instead of importing an unrelated candidate with `add`. A vague dislike calls for clarification of the desired change, not speculative extra generation. A new packet can record a changed user decision; earlier feedback remains in history.

After feedback, tell the user what they chose, what Codex's current checks say, and the resulting action: exported, revision requested, stopped, or blocked with concrete reasons. This is the human-to-Codex handoff. `report`, `deliver`, `review accepted`, `select`, and `export` cannot bypass required pool feedback. Reports before acceptance contain findings only, with no final PNG package.

## Continue a specific human correction

`human-feedback` with `decision: revise` returns the selected asset, original comment and review packet. Use that binding even when the user chose an earlier candidate. An explicit, actionable correction starts a new default three-attempt review/redraw batch (or the user’s explicit smaller cap); recording feedback itself does not invoke the image tool. Clarify an unspecified dislike before preparing a revision. Do not ask the user to repeat an already clear correction or choice.

1. Inspect the chosen candidate and its existing pool contract/Outfits brief. Derive the revised contract from the original and the actual comment: retain all original IDs, components, properties, inspection views and non-target expectations. Target expectations may change for the correction; add focused checks when needed. Keep this within the existing expression/mouth state or garment option and its edit boundary. A different expression/state, garment, color or replacement design needs a separate request/option, not silently altered metadata. Never relax protected-region checks to accommodate a defect.
2. Run `revision-prepare --packet <feedback-packet> --contract-file <revised-contract.json>`. It saves the original user words and immutable source/chosen-candidate fingerprints, reserves the first call of a fixed-budget revision batch, and returns both reference paths and inherited edit fields. Repeating it returns the same request; it does not reset the allowance. Inspect its `next_action`; generate only for `generate_revision`, and execute the image call once.
3. Use the returned references in order. New revisions edit the **user-chosen candidate first**, using the immutable original second for secondary protection review and explicitly scoped recovery, then all design references. Describe the specific correction and preserve successful changes outside it. Save the actual submitted prompt in the user's language. These instructions are not masks or pixel locks. Do not substitute the newest, highest-scoring or original-costume image for the selected baseline. Older recorded plans keep their returned input order.
4. Run `revision-import` with the revision ID, raw output, actual prompt and both reference paths. The helper inherits the selected version's expression/mouth state, garment definition/brief or pose action/side/anchors/brief, binds `parent_asset_id` to that version, and starts a new **version-1.1 pool with the recorded revision budget (default 3)** with the revised contract. It retains old images, feedback, reviews, pools and selections for other slots. No old quality/fidelity score or user acceptance carries over. If the image call fails, use `revision-fail --note`; the attempt stays spent. A local import error is resolved using the already generated output, not another image call.
5. Make an assistant packet and perform fresh rubric 1.2 checks and applicable Outfits/Poses fidelity checks. Follow the same internal review/redraw loop until passage or exhaustion. Then create the new user packet with `review-sheet --asset <new-id> --purpose user --language <user-language>`. It includes original, **before revision**, all readable candidates in this correction batch and the original correction comment; returned `revision_parent`/`revision_note` support inline comparison. The chosen old version is nonselectable context; any displayed new candidate, including a failed earlier revision, can receive another concrete correction. Fresh actual acceptance and every delivery gate remain required. Failure within a batch uses its remaining allowance; it does not grant a fourth call or reset the original batch.

Final reports and export manifests preserve the parent version and original correction request alongside the new assessment and decision. A newer actual decision on the same parent cancels a pending correction and keeps its history; re-preparing a cancelled request cannot generate. Do not describe the user request as fulfilled merely because import succeeded. If generation or inspection fails, retain the request and findings and explain the concrete outcome.

```text
python <skill>/scripts/studio.py revision-prepare --project <project> --packet <actual-revise-packet> --contract-file <revised-contract.json>
# Execute each reserved call once using its returned reference_paths, then:
python <skill>/scripts/studio.py revision-import --project <project> --revision <returned-revision> --image <raw.png> --prompt-file <submitted.txt> --reference <user-chosen.png> --reference <immutable-source.png>
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
# Pass ALL returned references in their recorded order. New human revisions/redraws use edit target, source, then scoped references; other or legacy pools retain their plan.
python <skill>/scripts/studio.py review-sheet --project <project> --asset <first-id> --asset <second-id> --purpose assistant
python <skill>/scripts/studio.py pool-compare --project <project> --case <first-id> --feedback-file <comparison.json>
python <skill>/scripts/studio.py review-sheet --project <project> --asset <chosen-id> --purpose user
# Present the page/images and wait for actual user feedback.
python <skill>/scripts/studio.py human-feedback --project <project> --feedback-file <actual-user-feedback.json>
python <skill>/scripts/studio.py report --project <project> --stage final --output <new-delivery-directory>
python <skill>/scripts/studio.py export --project <project>
```

Work sequentially in a project. Preserve raw image bytes; preview resizing is only for display. No mask, local repaint/composite or new backend is introduced.
