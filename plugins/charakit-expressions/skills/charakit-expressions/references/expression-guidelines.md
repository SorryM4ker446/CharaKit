# Editing full character expressions

Standard IDs: `neutral`, `happy`, `sad`, `angry`, `surprised`, `eyes_closed`. Users can specify intensity and particular facial changes. Translate visible expression names and generation prompts into the user's language; keep IDs unchanged.

| Expression | Starting direction |
| --- | --- |
| neutral | Calm. Reuse the source when it already matches; no generation is necessary. |
| happy | Moderate smile expressed through the eyes, brows, and mouth; do not default to laughter. |
| sad | Restrained disappointment; no tears or additional emotion symbols by default. |
| angry | Slightly lowered brows, a tighter gaze, and a displeased mouth; do not default to shouting. |
| surprised | Moderately widened eyes and a slightly open mouth; preserve facial proportions and body pose. |
| eyes_closed | Natural closed eyes; preserve other facial features and the original mouth unless requested otherwise. |

## Prompt example

> Edit this complete character illustration to show restrained anger: slightly lower the eyebrows, tighten the gaze, and express displeasure with the mouth. Preserve the detail and existing design of the entire face, including the eyes, brows, nose, lips, facial contours, skin tone, and shading. Blend the change into the original brushwork, linework, and coloring, with coordinated eyes, brows, and mouth. Preserve the hair, accessories, clothing, weapon, pose, composition, and lighting. Return the complete original framing with a genuine transparent background and no text or emotion symbols.

Translate and adapt this starting point to the user's request. For opaque artwork, replace the transparency requirement with preservation of the source background. Hidden RGB values in transparent pixels are not visible background content.

For an unsatisfactory candidate, identify a visible issue before a targeted revision: weakened nose shading, thicker mouth lines, a rounder face, changed skin tone, or simplified iris layers. Do not use "prettier" or "more detailed" as a reason to redesign the face.

Always provide the original illustration as the primary edit reference. An additional facial reference may reinforce fidelity without changing the full-image deliverable.
