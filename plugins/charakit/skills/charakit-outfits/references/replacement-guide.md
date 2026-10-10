# Replacing one existing garment

Use `replace` to change the design of one existing garment, such as long stockings to short socks or boots to low shoes. An explicitly requested pair counts as one garment option; preserve intentional asymmetry. Full outfit replacement, independent accessory edits, undressing and pose/expression changes remain outside this mode. Resolve the component and requested design from the source and request, asking only for information that affects the edit.

## Boundaries and prompt

Record the existing `target`, requested `replacement`, necessary interface changes in `boundary`, and protected remainder in `protected_regions`. The replacement description includes requested cut, length, color, material, pattern and construction. Inherit unspecified properties where compatible with the new design. Do not apply recolor's requirement to preserve the old garment's cut/material to a replacement.

The permitted area follows the garment and its necessary new boundaries, not the rectangular reference crop. Shorter socks or lower shoes may expose previously covered leg/ankle regions. Permit source-consistent skin rendering only in those newly visible areas, preserving existing exposed skin, anatomy, proportions and pose. Do not add invented skin markings or redesign the body. Inspect distorted feet/joints, missing/repeated limbs and floating footwear.

Protect the entire face, expression, mouth state, hair, other clothing, weapons and separate straps, garters, buckles and accessories. Do not automatically remove equipment touching the target. Resolve a replacement that cannot coexist with a protected item before generating; do not silently expand the edit. Necessary garment interfaces do not authorize another garment's redesign or independent accessory additions/removals.

Submit the immutable complete source by default. Prepared crops normally remain inspection aids; include them only for ambiguous identification or a requested comparison when supported. They are not masks or pixel locks. If the user supplies a design reference, inspect it and describe its sole garment-design role; keep source identity/style/pose authoritative and record actual submitted references.

Adapt this prompt to the actual source and request:

> Edit the complete source. Replace only [existing garment] with [requested new design]. Permit [necessary garment-boundary and newly visible-area changes]. Preserve [actual separate equipment and protected interfaces], the whole face, expression, mouth state, hair, anatomy, pose, other clothing and props, original style, lighting and framing. Render natural fit, material, folds and occlusion. Output one complete image with the source canvas and original transparency/background, without text or a comparison sheet.

Prompts guide generation without guaranteeing preservation. All final artwork editing stays in the host image tool; local helpers never paint/composite or resize candidates.

## Prepare and save

```text
python <skill>/scripts/studio.py prepare --project <outfits-dir> --outfit short_socks --edit-type replace --target <existing-stockings> --replacement <requested-short-sock-design> --boundary <garment-and-necessary-new-edges> --protect <face-expression-hair-pose> --protect <other-clothing-straps-shoes-weapons> --target-box <left> <top> <right> <bottom>
python <skill>/scripts/studio.py add --project <outfits-dir> --outfit short_socks --edit-type replace --target <same-existing-stockings> --replacement <same-requested-short-sock-design> --image <raw-generated.png> --prompt-file <actual-prompt.txt> --brief-file <returned-brief.json>
```

Do not pass `--color` in replace mode; include color in `--replacement`. Use a new option ID for a different target, mode or requested design. `prepare` saves a schema 1.1 brief and source detail reference without changing project metadata or artwork. The first replacement requires a matching prepared brief and nonempty actual submitted prompt. Ordinary revisions retain the definition and inherit the brief unless a matching updated brief is supplied.

Adding the first replacement backs up a schema 1.2 project's exact metadata to `run.schema-1.2.backup.json`, then writes schema 1.3. Existing candidates, selections and scores stay unchanged. If the legacy project has no quality policy, this import enables it for subsequent work while retaining existing assets as legacy records. A different existing backup blocks migration rather than being overwritten. Read-only commands and recolor-only projects do not migrate. Old helpers cannot read schema 1.3; use 0.1.16 or later. New replacement candidates always require fresh quality and fidelity observations, even in legacy projects without a quality policy.

## Replacement review

Actually view full-image, whole-face, garment, boundary and protected-detail comparisons on suitable backgrounds and at a recorded normal display size. `fidelity` records target replacement and protected-region preservation separately. Use `garment_replace`, with actual source-specific evidence for every check:

| Check | Passing observation |
| --- | --- |
| `target_garment` | Requested garment is visibly replaced, matching specified cut, length, color, material and construction. Recoloring alone does not satisfy a new-design request. |
| `fit_interfaces` | Natural fit/contact/occlusion at relevant waist, collar, cuff, ankle or foot boundaries; protected equipment remains coherent. |
| `coverage_anatomy` | Coverage matches the new design; newly exposed skin is plausible and limited to necessary areas; anatomy, proportions and pose remain intact. |
| `face_expression` | Complete face, expression and mouth state retain source design/rendering. |
| `non_target_protection` | Other garments, separate accessories, hair, weapons and background retain protected properties. |
| `rendering` | Replacement matches source style, lighting and materials, without seams, clipping, missing parts or alpha defects. |

Failed/uncertain domain items or either fidelity failure veto delivery independently of the total score. Do not require preservation of old garment geometry explicitly replaced by the request, or excuse unrequested redesign as necessary.

Follow the existing bounded refinement only within the user's budget: first image plus at most two targeted revisions, immutable source first and previous complete candidate second. Repair recorded defects while retaining the requested replacement. Stop on passage or exhaustion. Finish with `report`: passed full PNGs separately inline, final preview and report; if none pass, deliver the failure report only. Internal passage is separate from user acceptance; formal export retains its canvas gate. Helper tests do not establish actual artistic replacement quality.
