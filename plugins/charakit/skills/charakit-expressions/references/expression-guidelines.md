# Editing full character expressions

Twelve fixed presets are supported. Users can specify intensity and particular facial changes. Translate visible expression names and generation prompts into the user's language; keep IDs unchanged. The helper's `presets` command lists the supported IDs and starting directions without initializing a project.

| Expression | Starting direction |
| --- | --- |
| neutral | Calm. Reuse the source when it already matches; no generation is necessary. |
| happy | Moderate smile expressed through the eyes, brows, and mouth; do not default to laughter. |
| sad | Restrained disappointment; no tears or additional emotion symbols by default. |
| angry | Slightly lowered brows, a tighter gaze, and a displeased mouth; do not default to shouting. |
| surprised | Moderately widened eyes and a slightly open mouth; preserve facial proportions and body pose. |
| eyes_closed | Natural closed eyes; preserve other facial features and the original mouth unless requested otherwise. |
| shy | Bashfulness for praise or intimate dialogue: a slightly averted gaze, restrained mouth, and subtle blush unless excluded. Keep the head and body pose unchanged. |
| confused | Questioning or uncertain brows, gaze, and mouth. Convey trying to understand rather than startled surprise; do not add question-mark symbols or tilt the head. |
| wry_smile | A small awkward or resigned smile for embarrassment, dry humor, or compromise. Coordinate subdued brows and eyes; distinguish from a happy smile without making a grimace. |
| worried | Concern or unease for waiting or anticipating danger: concerned brows and a tense gaze or mouth. Distinguish from sadness; do not default to tears, sweat drops, or panic. |
| confident | A composed, assured gaze and a restrained pleased smile for pride or teasing. Adapt to the character's temperament; do not default to a villainous smirk or change the stance. |
| crying | Visible tears for distress or parting, with coordinated brows and mouth. Preserve iris layers, highlights, lashes, and skin rendering; avoid flooding the face or defaulting to loud sobbing. |

## Selecting and revising presets

Generate only the expressions requested. If the user requests a complete standard set, use these twelve presets, reusing the source for `neutral` when appropriate. Map ordinary-language requests to the fixed IDs; explain the available choices when a request has no suitable preset rather than silently substituting a different emotion.

`wry_smile` covers both an awkward smile and resignation at this stage; `confident` covers confidence and pride. Do not invent extra IDs for synonyms. Intensity changes remain versions of the same expression, with one selected version per preset. Independently selectable mouth-open, gaze, or emotion-specific closed-eye states remain planned.

Blush is appropriate to `shy`, and tears are part of `crying`; apply user exclusions and the source style. These effects are not defaults for other presets. Revise only the requested preset from the immutable source, retain prior candidates, and keep other selections intact.

The six newer presets (`shy` through `crying`) have file-workflow support and editing directions. Artistic fidelity and distinctness require reviewing actual generated images; automated workflow tests do not validate image-generation quality.

## Prompt example

> Edit this complete character illustration to show restrained anger: slightly lower the eyebrows, tighten the gaze, and express displeasure with the mouth. Preserve the detail and existing design of the entire face, including the eyes, brows, nose, lips, facial contours, skin tone, and shading. Blend the change into the original brushwork, linework, and coloring, with coordinated eyes, brows, and mouth. Preserve the hair, accessories, clothing, weapon, pose, composition, and lighting. Return the complete original framing with a genuine transparent background and no text or emotion symbols.

Translate and adapt this starting point to the user's request. For opaque artwork, replace the transparency requirement with preservation of the source background. Hidden RGB values in transparent pixels are not visible background content.

For an unsatisfactory candidate, identify a visible issue before a targeted revision: weakened nose shading, thicker mouth lines, a rounder face, changed skin tone, or simplified iris layers. Do not use "prettier" or "more detailed" as a reason to redesign the face.

Always provide the original illustration as the primary edit reference. An additional facial reference may reinforce fidelity without changing the full-image deliverable.
