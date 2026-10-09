# Editing boundaries across CharaKit modules

Use these rules before constructing a generation prompt and again when comparing the output. They define editing intent and inspection requirements, not a tool-enforced mask or pixel lock. Read the active module's domain guide for its specific allowed changes.

## Derive the scope from the request

Identify four things from the user's request and actual source:

1. **Target:** the existing component, its visible extent, and any explicitly requested subregions. Do not infer the target from color alone: different components may share a hue, material, or texture.
2. **Allowed properties:** exactly what may change, such as a garment's base color, an emotion's facial movements, or a mouth's open/closed state. Permission to change one property does not grant permission to redesign the component.
3. **Invariants inside the target:** all properties the operation does not need to change. For recoloring these include geometry, construction, texture, pattern layout, material, opacity, and shading structure.
4. **Protected remainder and interfaces:** everything outside the allowed edit, plus where the target meets skin, other components, or an occluding object. Preserve visible overlap order, contact, and boundaries unless the operation explicitly requires otherwise.

An unmentioned component or property is protected by default. Necessary changes must follow from the active operation; do not invent permission for cosmetic repair, cleanup, global grading, or enhancement. Explicit user requirements take precedence over domain defaults, within implemented capabilities. Clarify only ambiguity that materially changes the edit. Do not invent components hidden behind clothing or outside the source.

## Module-specific permissions

| Operation | Allowed change | Invariants and boundary |
| --- | --- | --- |
| Garment recolor | Requested base color on specified existing surfaces, including necessary hue/saturation/lightness changes | Preserve garment construction, material, texture, pattern placement, silhouette, opacity, and shading structure; protect excluded decoration and all other components. Use the Outfits domain guide. |
| Expression | Facial movements needed for the requested emotion and intensity; preset-specific effects where requested or defined | Preserve facial identity, feature design and detail, proportions, skin rendering, head/body pose, hair, clothing, and props. Movement of a brow or lip is permitted; redesign of the feature is not. |
| Mouth state | Lip shape and mouth interior needed for a natural opening or closure | Preserve established emotion, eyes, brows, gaze, facial proportions, and non-mouth components. Use the static mouth-state guide; avoid converting speaking into shouting or surprise. |

Full outfit replacement, additions/removals, and poses remain planned. This table does not make them callable or add arbitrary component-edit support. Future modes must define their own permissions and necessary interface changes before implementation.

## Construct the prompt

Prioritize artwork quality, faithful preservation, and a clearly achieved edit. Prompt length is not an optimization target. Build a complete, organized instruction from the selected operation and domain, using enough detail to express the necessary changes and constraints. Do not copy a fixed prompt from a test character:

> Edit the complete source. Apply [requested property change] only to [identified target and included surfaces]. Preserve [target properties that must stay fixed]. Exclude [source-specific boundary components]. Keep all other components and their original rendering unchanged. Output the complete source framing and canvas with its original transparency/background, without text or a comparison sheet.

Fill the slots with inspected source facts; omit irrelevant exclusions. Domain guidance supplies constraints, not default colors, costumes, props, or visual features. Mention a particular neighboring component only when it exists and helps disambiguate the edit. Do not list every imaginable object, copy a previous character's defects, or describe how to reconstruct protected regions. Retain all necessary target cues, internal invariants, boundary exclusions and remainder protection; include detailed preservation requirements when they help protect the source's design or rendering.

When preserving an attribute, prefer inheritance from the source over an uncertain descriptive label. Do not turn a guessed iris/skin/material color into a generation instruction. Retain the active domain's positive target cues: expression movements and required tears/blush differ from a recolor's color-only permission. Clear organization, consistency with the source, and visual success determine whether a prompt is suitable; brevity does not.

Use the immutable complete source as the primary edit reference. Auxiliary references have an explicit purpose and must not silently replace the source or grant further editing permission. Save the actual submitted prompt and reference paths. For Outfits, persist scope in the existing `prepare` brief's target, color, boundary, and protected descriptions; for Expressions, retain it in the prompt and review notes. These rules introduce no JSON fields or schema migration.

## Inspect the same scope

Choose inspection regions from the source and active domain before generation. Compare the full image, the edited region, its invariant details, its interfaces, and representative protected regions. Use enlarged previews for fine or complex designs; there is no mandatory weapon or particular garment when none is present. Inspect source transparency edges on suitable light and dark backgrounds.

Report separately whether the target changed as requested and whether target invariants and protected regions survived. A color match or recognizable character does not establish preservation. Visible unrelated geometry, texture, pattern, or rendering changes are preservation defects; insufficient evidence is uncertain. Do not claim pixel equality from scaled previews or automatic artistic scores from file checks.

Use the module's existing review mechanism. Outfits records independent manual `target_check` and `protection_check`; Expressions records observations in review notes without borrowing Outfits CLI gates. Technical validity, visual observations, and actual user acceptance remain distinct. Keep failed candidates and their bytes; do not automatically repair another component or expand the requested generation count.
