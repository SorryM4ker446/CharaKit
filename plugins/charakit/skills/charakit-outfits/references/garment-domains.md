# Garment domains for selective recoloring

Read only the relevant rows when preparing an edit and its comparison. These domains specialize the shared [editing boundaries](../../../references/edit-boundaries.md); they are not separate Skills, CLI modes, or permissions to replace a garment.

The requested property is color on identified existing surfaces. All domains preserve cut, topology, visible coverage, attachment, material response, texture, pattern geometry, opacity, folds, and shading structure. Recolor both visible instances only when the request identifies the pair; keep intentional asymmetry. A bounding reference rectangle never defines the permitted edit by itself.

## Component rules

| Domain | Identify the intended surface | Invariants inside the target | Interface exclusions and inspection |
| --- | --- | --- | --- |
| Upper-body garments: shirts, jackets, coats | Main body, sleeves, or explicitly named panels | Neckline, lapels, openings, sleeve length, cuffs, seams, buttons, lining, layering and fit | Skin/hair at collar, hands at cuffs, adjacent garments, belts and decorations. Inspect both sides and covered boundaries. |
| Lower-body garments: skirts, trousers, shorts | Fabric panels and requested pattern colors | Waistline, hem, length, pleats, pockets, seams, leg separation, pattern shape/placement | Belts, skin, hosiery, overlying panels and other layers. Inspect waist, hem and folds; do not turn a multi-color pattern into a solid fill. |
| Connected garments: dresses, robes, jumpsuits | Continuous garment fabric or a named section | Bodice-to-lower continuity, openings, panel boundaries, sleeves, coverage and silhouette | Separately layered clothing, fasteners and ornaments. Distinguish connected fabric from another garment that shares its color. |
| Legwear: socks, stockings, tights | Covered fabric area and which visible leg(s) | Length, thickness, opacity/translucency, knit/texture, seams and existing shading | Exposed skin, shoes, straps, garters, buckles and overlapping equipment where present. Inspect upper edge, ankle and occlusions. Light colors must not become bare skin or a new material. |
| Handwear: gloves, mittens | Fabric/leather panels on the specified hand(s) | Finger coverage, openings, fit, seams, thickness, silhouette and material highlights | Exposed fingers, wrist/cuff pieces, held objects and attached decorations. Inspect fingers, wrist and grip contacts. |
| Footwear: shoes, boots | Requested upper, shaft, or other explicitly identified surface | Sole/heel shape, toe, openings, closures, stitching, leather/fabric response and contact pose | Socks, skin, laces, buckles, soles and separate equipment unless included. Inspect toe, heel, ankle and each visible shoe. |
| Textile headwear: hats, caps, hoods | Existing cloth/headwear panels | Brim, crown, openings, seams, fit and attachment; a hood's continuity with its garment | Hair, ears, face, fasteners and separate ornaments. Inspect headwear edges and overlap without altering head or hair shape. |

Treat a garment spanning multiple domains as one garment, not several unrelated edits. Apply only the relevant constraints. Do not automatically include nearby jewelry, weapons, armor, or other props as recolor targets; independent accessory/prop editing remains outside the current mode. Their geometry and rendering are protected when present.

## Material and pattern rules

- Preserve the source material's behavior: cloth texture and folds, leather grain and specular highlights, translucent fabric coverage, or another visibly supported material. Do not infer a replacement material from a color name.
- Keep pattern boundaries, motif shapes, spacing, logos, embroidery, and panel identities. Recolor the requested color channel/surface; separately colored decoration stays unchanged unless explicitly included. Clarify a pattern-color ambiguity that changes which surfaces are edited.
- Permit base-color hue, saturation, and lightness adjustments needed for the request, including achromatic colors, while preserving highlight/shadow placement, relative shading, and fold volume. Do not demand one exact shaded pixel value or permit global lighting changes.
- Treat trim, stitching, hardware, lining and ornament as separate surfaces when the source distinguishes them. Include them only when the request does; inspect the corresponding interface rather than assuming a garment label includes everything touching it.

## Use in the workflow

Apply the shared [domain-review gate](../../../references/quality-review.md) after inspecting the result. Record `garment_recolor` with the actual garment and relevant domain(s) in `component`. Fill `target_color`, `garment_invariants` and `interfaces` using the selected row's surfaces, material/structure and contact exclusions; separately check `face_expression`, `non_target_protection` and `rendering`. A failed/uncertain item blocks delivery independently of the global score. Avoid copying observations across rows or requiring a feature absent from the source.

Populate `prepare` with the actual garment, requested color, included/excluded surfaces, and protected remainder. Build the submitted prompt from those decisions using the shared template; no domain assigns a default color. Save the detailed checklist in the brief, and inspect target material/structure plus the relevant interfaces in enlarged previews. Compare protected components selected from the actual source, not a checklist tied to any prior test image.

If no row fits, apply the shared surface/property/invariant/interface rules to an existing garment and record the concrete scope. Do not force a category, invent a new CLI ID scheme, or broaden into replacement/accessory editing.
