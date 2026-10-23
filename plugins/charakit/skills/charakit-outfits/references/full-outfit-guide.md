# Replacing a complete outfit

Use `outfit_replace` for one coherent clothing ensemble on a complete character image. This produces a new outfit base image. Accessories/props use the separate [prop edit type](prop-edit-guide.md) within Outfits; garment inventory does not authorize their edits. Expressions can manually use the resulting PNG as an independent source. Pose changes and undressing remain unimplemented. A dress replacing several garments can be one component group; do not force artificial layering or a two-piece design.

## Define the clothing inventory

Inspect the actual source and resolve the requested ensemble before generation. Record an overall `target`, overall `replacement` design and `outfit_components`: a UTF-8 JSON array of one to twelve objects with exactly `id`, `source` and `replacement`. IDs are unique lowercase filename keys and source descriptions must distinguish the components; source and replacement descriptions use the user's language. The inventory describes permission, not segmentation or a mask.

```json
[
  {"id": "upper", "source": "Existing upper garment", "replacement": "Requested upper garment design"},
  {"id": "lower", "source": "Existing lower garment", "replacement": "Requested lower garment design"}
]
```

Derive every item from the artwork and request; the example is a schema illustration, not a default costume. Define compatible cut, length, material, palette and construction as needed. Several source garments may be grouped when one replacement garment spans them; describe the mapping explicitly. New clothing layers belong inside the relevant replacement description. Unspecified design properties inherit from the source where compatible with the new design. Keep intentional asymmetry.

Only listed clothing may be redesigned. Shoes, stockings, gloves, belts and clothing accessories change only when explicitly included. A request to replace the whole outfit permits deriving its visible clothing inventory; state which footwear or accessories remain protected if the request does not settle them. Ask only when the choice materially affects the result. Weapons, held objects, hair accessories and separate equipment remain protected; this mode does not independently add or remove them. An item touching clothing is not automatically part of it. Resolve actual conflicts with protected equipment before generation. Do not infer unseen garments or grant permission to redesign the body.

`boundary` defines necessary neck/waist/cuff/hem/leg interfaces, coverage changes and overlap constraints. `protected_regions` names the whole face, expression, mouth state, hair, anatomy, proportions, pose and relevant remaining clothing/equipment/background. Newly exposed skin is allowed only where the requested clothing requires it, with source-consistent anatomy and rendering. Preserve existing exposed skin and contacts with protected objects. The reference box may encompass the entire clothing region with context; it is only an inspection crop. It grants no additional editing permission.

## Prompt and references

Use the immutable complete source as the identity, pose, style and composition authority. Follow [scoped edit references](../../../references/edit-references.md) for supplied costume images: prepare immutable snapshots, map each reference to editable inventory IDs, bind actual inputs and review each reference's permitted design cues. Every internal redraw and human revision retains all references. Prepared crops remain inspection aids; no mask or regional lock is available in this workflow.

Adapt one organized prompt to the actual inventory:

> Edit the complete source. Replace [explicit listed clothing and source-to-new mappings] with [coherent requested ensemble]. Permit [necessary fit, coverage and overlap changes]. Preserve [source-specific protected clothing and equipment], the whole face and expression, mouth state, hair, body proportions, pose, existing exposed skin, original style, lighting and framing. Keep seams, layering, folds and contacts natural. Output one complete image with the original canvas and transparency/background, without text or comparison panels.

Write in the user's language. A repair changes only observed defects and retains the inventory, original boundaries and protected remainder. Identity preservation must not become an instruction to beautify or reconstruct the face. All final artwork edits use the host image tool; helpers only save raw outputs, references and previews.

## Prepare, import and review

```text
python <skill>/scripts/studio.py prepare --project <outfits-dir> --outfit <ensemble-id> --edit-type outfit_replace --target <overall-source-scope> --replacement <overall-new-design> --components-file <inventory.json> --boundary <necessary-interfaces-and-coverage> --protect <face-expression-hair-anatomy-pose> --protect <remaining-clothing-equipment-background> --target-box <left> <top> <right> <bottom>
python <skill>/scripts/studio.py add --project <outfits-dir> --outfit <ensemble-id> --edit-type outfit_replace --target <same-overall-source-scope> --replacement <same-overall-new-design> --image <raw-generated.png> --prompt-file <actual-submitted-prompt.txt> --brief-file <returned-brief.json>
```

Do not pass `--color`; include palette/material in the replacement design. `add` inherits the inventory from the matching brief; explicit `--components-file` must match. A new scope, component mapping or design needs a new outfit ID. `prepare` saves brief schema 1.2 without changing project metadata. The first full outfit import backs up the exact schema 1.2/1.3 metadata to `run.schema-<version>.backup.json` and upgrades to project schema 1.4. Conflicting backups block import. Existing images, reviews and selections remain unchanged. Use helper 0.1.21 or later; older helpers cannot read schema 1.4.

Follow [candidate selection and human review](../../../references/candidate-review.md). Define the contract before generation, including one `target` criterion naming each inventory item's exact `source` description, plus identity, protection, integration and rendering criteria. Source-based authorized attempts total one to three; full outfits use candidate pools, not legacy sequential refinement. Start the pool before scoring. Use rubric 1.2 with domain `outfit_replace` and these independent checks:

| Check | Required observation |
| --- | --- |
| `outfit_design` | Requested overall design, palette, cut and material are visible; repainting the old clothes alone is insufficient. |
| `component_completion` | Every listed source component is replaced according to its mapping; no unrequested old layer remains or required new layer disappears. |
| `ensemble_coherence` | Garments form a coherent ensemble with compatible scale, material, palette and construction; source/requested asymmetry remains intentional. |
| `fit_interfaces` | Natural seams, layering, contact, folds and occlusion at relevant joints and protected equipment. |
| `coverage_anatomy` | Clothing length/coverage matches the design; exposed areas, limbs, anatomy and pose remain plausible and source-consistent. |
| `face_expression` | Entire face, expression and mouth state retain source identity, feature design and rendering. |
| `non_target_protection` | Hair, unlisted clothing/accessories, equipment, props, composition and background retain their protected properties. |
| `rendering` | Source style, lighting, material behavior and readable finish, with no clipping, missing parts, broken edges or alpha defects. |

In `domain_review`, add `component_checks`, keyed by every inventory `id`, each with `status` (`passed`, `failed`, `uncertain`) and visible `evidence`. Missing/extra keys are invalid. Any failed or uncertain component or domain item vetoes delivery, even with a perfect weighted total. Record actual findings at full, whole-face, garment/detail, protected-detail and normal display views, plus edges on appropriate backgrounds. Do not copy evidence between items. Dimensions keep the shared five weights and minimum applicable criterion; no extra weighted score or lowered identity/protection threshold.

Record fresh target/protection `fidelity` observations. Show the anonymous user review only after full internal passage or budget exhaustion. Actual feedback drives accept/revise/reject; a correction uses `revision-prepare` and `revision-import`, retains the chosen parent's complete inventory/brief, and starts a default three-attempt review/redraw batch with fresh internal and fidelity checks before human review. Only actual acceptance of eligible images permits final delivery and requested ZIP packaging. Before feedback, reports are drafts; revise/reject decisions can also produce final disposition reports without accepted assets.

Export preserves raw PNG bytes in `sprites/<character>/outfits/<outfit-id>.png`; schema 1.4 manifests include the inventory, scope, reviews, actual feedback and revision provenance. Canvas mismatch is a nonblocking warning for acceptance, selection and export; show source and actual dimensions and keep raw bytes unchanged. Workflow tests establish file and review behavior; actual outfit quality and preservation still require real-image evaluation.
