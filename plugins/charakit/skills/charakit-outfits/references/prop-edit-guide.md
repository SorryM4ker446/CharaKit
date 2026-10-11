# Accessory and prop editing

Use `prop_edit` inside Outfits to add, remove or replace one explicitly scoped accessory or prop on a complete character image. Examples include glasses, a hair ornament, worn jewelry or a held object. Shoes, hosiery and gloves use garment modes. A naturally connected pair, such as earrings, can be one target when the request covers the pair; unrelated objects are separate options. This mode does not authorize a clothing redesign, new pose, expression change or arbitrary background cleanup.

## Scope and operation

Inspect the full source and resolve the actual object, placement, attachment or grip before generation. Do not assume a weapon, accessory or hand contact exists in every image. Record `edit_type: prop_edit`, `target` and `prop_action`:

| Action | Definition | Permitted changes |
| --- | --- | --- |
| `add` | `target` identifies the requested object and its source-coordinate addition site; `replacement` describes its design and placement. | Introduce the specified object at that site, with necessary contact, shadow and occlusion. No unrelated new objects. |
| `remove` | `target` identifies the existing object and its full visible extent; omit `replacement`. | Remove the entire target and its attachment/contact traces; naturally complete the newly revealed source regions. Do not introduce a substitute. |
| `replace` | `target` identifies the existing object; `replacement` describes the new design and its compatible placement. | Replace the target, including its visible extent and necessary interfaces; no old fragments or duplicate new objects. |

Describe scale, orientation, material and placement only as needed by the actual request. Infer a compatible placement from the artwork when clear; ask only if multiple materially different placements or grips remain possible. If removal finds no target, explain that no edit is needed rather than generating and fabricating completion. A new placement or design that requires an arm/body pose change exceeds this mode: resolve a compatible design or the conflict before generation, rather than quietly changing the pose.

In `boundary`, specify the object extent and only the necessary interfaces and reconstruction: hair/ear attachment, skin contact, clothing fastening, hand grip, overlap order, object shadow, and newly exposed regions as applicable. Small finger/contact adjustments can be allowed when necessary to release or hold the target, while preserving the hand's location, plausible anatomy, arm pose and body proportions. These permissions must be explicit before generation. Removal may reveal previously hidden hair, skin or clothing; extend the source-consistent local design without treating it as known original pixels or redesigning the surrounding component.

Protect the entire facial design, expression and mouth state, hair design, existing visible skin, clothing, unrelated props, pose, proportions, composition and background. Added glasses or ornaments can necessarily occlude a small region; this is authorized overlap, not permission to repaint the face or hairstyle. Object shadows/contact and necessary uncovered-area completion are distinct from unrequested global color or lighting changes. A source crop is a placement/inspection aid, not an edit mask or segmentation.

## Prompt and references

Use the immutable complete source as the identity, style, pose and composition authority. A supplied object reference gives object design only; inspect it and save its role when actually submitted. Do not treat a costume/reference figure as the character identity. Full source is the default reference; a prepared detail crop is sent only when it resolves target ambiguity. No mask or regional lock is implemented.

Adapt this prompt to the operation and actual source, in the user's language:

> Edit the complete source. [Add/remove/replace the explicitly scoped target, including requested design and placement]. Permit only [necessary attachment/grip/occlusion/shadow/uncovered-area changes]. [For removal/replacement: no old fragments or duplicate object]. Preserve [source-specific protected remainder], facial design and expression, hair design, clothing, body/arm pose, proportions, original rendering and framing. Keep contact, anatomy, overlap and newly revealed regions natural. Output one complete image with the original canvas and transparency/background, without text or comparison panels.

Do not ask for facial reconstruction or general beautification. All final editing remains in the host image tool; local code never erases an object, inpaints, composites body parts or repairs pixels. Save raw output, the actual prompt and reference paths.

## Prepare and import

```text
python <skill>/scripts/studio.py prepare --project <outfits-dir> --outfit <object-option-id> --edit-type prop_edit --prop-action <add-remove-replace> --target <object-and-source-location> [--replacement <new-object-design-and-placement>] --boundary <necessary-contacts-occlusion-reconstruction> --protect <face-hair-clothing-pose-other-objects-background> --target-box <left> <top> <right> <bottom>
python <skill>/scripts/studio.py add --project <outfits-dir> --outfit <same-id> --target <same-target> [--replacement <same-design>] --image <raw-generated.png> --prompt-file <actual-prompt.txt> --brief-file <returned-brief.json>
```

Do not pass `--color` or `--components-file`. `add` inherits the mode and action from the matching brief; an explicitly supplied action must match. Add/replace require `--replacement`; remove forbids it rather than using a placeholder design. A changed action, target or object design needs a new option ID. Human corrections of the same definition retain that ID and increment versions.

Use helper 0.1.22 or later. `prepare` saves brief schema 1.3 without mutating project metadata. The first prop import backs up exact legacy schema 1.2/1.3/1.4 metadata before upgrading to project schema 1.5. Existing candidates, user opinions and selected versions remain unchanged; later garment imports never downgrade the project. Expressions projects are separate.

## Fresh review and delivery

Follow [candidate selection and human review](../../../references/candidate-review.md). Define the contract before generation, including a `target` criterion whose `component` equals the recorded `target`, plus source-grounded identity, protection, integration and rendering checks. Start the pool before scoring and keep the actual authorized budget. Props require rubric 1.2 and `domain_review.kind: prop_edit`, with `prop_action` matching the candidate; garment checklists cannot replace this domain.

| Check | Required observation |
| --- | --- |
| `target_object` | Add: correct new object, count, design and site. Remove: target fully absent, no substitute or remnants. Replace: requested new design present and old target absent. |
| `placement_contacts` | Correct scale, orientation and stable attachment/grip relative to the source. For removal, released contact is natural and obsolete straps, grip traces or object shadows are gone. |
| `occlusion_reconstruction` | Plausible front/back overlaps. Removal/replacement newly exposed hair, skin, clothing or background is continuous and source-consistent, without holes, old fragments or pasted-looking patches. Adding-only still checks new occlusion; do not invent a reconstruction defect for an area that was never revealed. |
| `anatomy_pose` | Hands/fingers and visible anatomy plausible; necessary local grip changes stay within the brief. No extra/missing fingers, displaced arms, changed body proportions or new pose. For an object away from the hands, inspect the relevant contact area and protected pose rather than pretending a grip exists. |
| `face_expression` | Source facial identity, feature design, expression, mouth state and rendering preserved outside necessary object occlusion. |
| `non_target_protection` | Hair design, clothing, other objects, composition and background preserved, excluding only the authorized interfaces/revealed areas. |
| `rendering` | Original style, lighting, material behavior, normal-size readability and clean visible edges. Transparent background remains transparent; opaque background remains coherent. |

Record every item's `passed`, `failed` or `uncertain` and actual visible evidence after inspecting full, face, target/interface, protected details, normal display and light/dark alpha views. The five common weights, minimum criterion per dimension, 80 total threshold and 4/5 dimension floor remain unchanged. Any failed/uncertain domain item vetoes delivery. Record fresh target/protection `fidelity` separately; do not claim objective automated visual scoring or pixel preservation.

After full internal passage or fixed-budget exhaustion, show anonymous human review and explain any unresolved failures. Actual chat or JSON feedback drives adoption, revision or rejection. A specific correction uses `revision-prepare`/`revision-import`, retains the chosen parent, action, design and brief, starts a default three-attempt review/redraw batch and requires fresh internal/fidelity checks before human review. Positive feedback never bypasses quality, fidelity or technical gates. Before feedback, reports are internal drafts; after feedback, final reports can record adoption, revision or rejection even when no image is eligible.

Eligible adopted PNGs export unchanged under the existing `sprites/<character>/outfits/<option-id>.png` path. Schema 1.5 manifests and reports retain action, definition, evidence, actual feedback and revision provenance. Canvas mismatch is excluded from visual scoring but still blocks formal selection/ZIP. Synthetic workflow tests establish these mechanics, not real generated-art quality. This mode remains independent of Expressions: users can manually use a resulting PNG as a new expression source without shared state or automatic generation.
