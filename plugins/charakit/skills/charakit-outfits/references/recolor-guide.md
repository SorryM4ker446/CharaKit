# Recoloring one garment

The current Outfits mode changes the color of one existing garment. It preserves cut, material, texture, patterns, construction, pose, expression, and other design elements. It does not replace the outfit or remove clothing.

## Resolve the target

Apply the shared [editing boundaries](../../../references/edit-boundaries.md) and relevant [garment domain](garment-domains.md). Identify the existing component and requested surfaces from the source, then distinguish the color property allowed to change from the garment properties that must remain. Preserve separately colored trim and decoration unless included. Resolve a pattern-color ambiguity that changes the edit scope.

Record the intended target and color in the user's language. Give each option a stable lowercase ID, such as `jacket_navy`; alternate shades have different IDs and independent selections. A revision's recorded target and color stay unchanged. Changing those values creates a new option, preserving the earlier history.

## Default prompt

Fill the shared prompt template with the inspected target, requested hue, relevant domain invariants, and actual interface exclusions. There is no fixed garment, color, or neighboring prop in the template:

> Edit the complete source image. Change only [identified garment surfaces] to [requested color]. Preserve [relevant construction, material, texture, pattern, opacity, and shading invariants].
>
> Exclude [actual boundary surfaces not included in the request]. Keep all other components and properties unchanged, with the source's rendering, design, expression, and pose.
>
> Output one complete image with the source's canvas, framing, and original transparency/background. No text or comparison sheet.

For an opaque source, preserve its background instead of requesting transparency. Do not turn hidden RGB in transparent pixels into visible marks. A hex color, if supplied, guides the material's base hue; allow the original lighting to create lighter and darker shaded colors.

Use `prepare` to persist the detailed boundary and protection checklist and create a source detail reference. Default to the complete source alone; keep the crop as a local inspection aid. Add the crop only for ambiguous target identification or a user-requested reference comparison when the host supports it. Then add a short role sentence: “The second image only locates the garment in the complete source; edit and output the complete source.” Record actual reference paths and the submitted prompt, not just the intended inputs.

Select domain constraints rather than copying a previous test's garments or colors. Context boxes may contain protected neighboring items; they are not masks or enforced pixel boundaries. Include necessary preservation detail in the submitted prompt, including original iris color distribution, nose/lip rendering or other fine features where relevant, while retaining the complete inspection checklist in the brief. Inherit these features from the source; do not describe a replacement face or add face repair, cleanup, redesign, or global color grading.

Keep every final color edit in the host image tool. Local helpers create viewing/reference artifacts and record findings, without recoloring pixels, patching the face, or compositing generated garments onto the original. Prompt length is not a quality target; prompts and auxiliary references provide guidance, not pixel locks. Non-target repainting remains a known limitation, and a clear complete instruction does not guarantee its prevention.

## Compare before selecting

Compare the complete source and candidates, enlarge the whole face, and inspect target invariants and domain interfaces with `--detail-box`. Create additional previews with distinct output paths for relevant protected details chosen from the actual source. Choose these regions before generation so checking is not limited to defects already noticed. A detail crop is only a preview; the delivered PNG remains a complete illustration.

- Confirm that the target garment changed to the requested color without spilling into skin, hair, other clothing, or accessories.
- Check pattern placement, fabric texture, seams, buttons, trim, folds, highlights, and shadows. Recoloring should retain the garment's construction and material behavior.
- Confirm that eye detail, nose, lips, face shape, expression, mouth state, and gaze remain stable.
- Compare hands, head position, silhouette, proportions, pose, background, and transparent edges.
- Compare relevant non-target outlines, construction, and rendering even when their broad colors look unchanged. Face preservation alone does not pass the protection check.
- Check full-image placement at game display size. Preview scaling and matching file dimensions alone do not prove stable switching.

Do not write these checklist items as observed defects unless visible in the actual images or identified by the user. Technical checks cover readable files, canvas, basic transparency, and fingerprints; they cannot judge selective recoloring, exact perceived hue, identity, or preservation of artwork.

Record target and protection checks independently with `fidelity`. A target may pass while protection fails. For example, a navy jacket with altered eyes/nose shading is a failed protection check; an unchanged face with an insufficient color change can fail the target check. A result not yet inspected is pending, and ambiguous evidence is uncertain. Neither is a passed observation. These are manual observations tied to source/candidate fingerprints, not an automatic similarity score or user acceptance. Positive user feedback and technical canvas failures keep their separate meanings.

Ordinary revisions use the immutable source and the requested count. Explicit [bounded refinement](../../../references/refinement.md) edits the previous complete image with the original as design/material authority, correcting only observed review defects while retaining successful recoloring. Keep the target/color and edit boundaries fixed, preserve every version and perform fresh fidelity/quality checks. Restoration of a protected face or prop needs an identified defect and the authorized round budget; never use an unlimited repair loop or local repainting. Experiments should vary one factor where possible; one sample cannot establish reliable improvement.

## Scope of future work

Apply the shared [quality-first rubric and delivery gate](../../../references/quality-review.md) after the comparisons and independent fidelity observations. Record assistant judgments with concrete evidence using `quality`; only `deliver`-passed candidates become user-facing deliverables. Serious protection defects and technical failures remain vetoes, regardless of the weighted score. Explicitly requested failed/experimental comparisons are inspection evidence. Future garment-edit modes must define their allowed changes and integrate the same gate before becoming available.

Accessory additions/removals, clothing on/off states, changing patterns or cut, full outfit replacement, and automated outfit/expression combination management remain planned. A user-requested new design needs the corresponding future workflow; do not quietly describe it as a simple recolor. Images from accepted recolor options are not automatically promoted to expression-project sources.
