# Editing full character expressions

Twelve fixed presets are supported. Users can specify intensity and particular facial changes. Translate visible expression names and generation prompts into the user's language; keep IDs unchanged. The helper's `presets` command lists the supported IDs and starting directions without initializing a project.

| Expression | Starting direction |
| --- | --- |
| neutral | Calm. Reuse the source when it already matches; no generation is necessary. |
| happy | Relaxed brows, warmer eyes and visibly lifted mouth corners form a natural moderate smile. Distinguish from the source's baseline smile; do not default to laughter. |
| sad | Raised inner brows, lowered/softened eyelids and downward mouth corners convey sadness. No tears or additional emotion symbols by default. |
| angry | Lowered, inward-drawn brows, tighter eyelids and a tense displeased mouth convey anger. Preserve eye design; do not default to shouting. |
| surprised | Moderately widened eyes and a slightly open mouth; preserve facial proportions and body pose. |
| eyes_closed | Natural closed eyes; preserve other facial features and the original mouth unless requested otherwise. |
| shy | Bashfulness for praise or intimate dialogue: a slightly averted gaze, restrained mouth, and subtle blush unless excluded. Keep the head and body pose unchanged. |
| confused | A slightly asymmetric questioning brow and an uncertain mouth convey trying to understand. Distinguish from a startled wide-eyed expression and worried tension; do not add question-mark symbols or tilt the head. |
| wry_smile | An uneasy or resigned brow with a small asymmetric smile conveys embarrassment, dry humor, or compromise. Distinguish its reluctant smile from warm happiness and from a worried nonsmiling mouth; avoid a grimace. |
| worried | Inner brows drawn together and slightly raised, attentive concerned eyes and a tense nonsmiling mouth convey anticipation or unease. Distinguish from the asymmetric questioning brow of confusion and downcast sadness; no tears, sweat drops, or panic by default. |
| confident | A composed, assured gaze and a restrained pleased smile for pride or teasing. Adapt to the character's temperament; do not default to a villainous smirk or change the stance. |
| crying | Visible tear pooling along the lower eyelids and fine natural cheek tear tracks, with distressed brows and a tightened or downturned mouth. Preserve original iris layers, pupils, highlights, lashes, and skin rendering. Tears must be identifiable beyond existing eye highlights; avoid flooding the face or defaulting to loud sobbing. |

## Selecting and revising presets

Generate only the expressions requested. If the user requests a complete standard set, use these twelve presets, reusing the source for `neutral` when appropriate. Map ordinary-language requests to the fixed IDs; explain the available choices when a request has no suitable preset rather than silently substituting a different emotion.

`wry_smile` covers both an awkward smile and resignation at this stage; `confident` covers confidence and pride. Do not invent extra IDs for synonyms. Intensity changes remain versions of the same expression and mouth state, with one selected version per combination. Static mouth-open and mouth-closed states are supported through [mouth-states.md](mouth-states.md); gaze and emotion-specific closed-eye states remain planned.

Blush is appropriate to `shy`, and tears are part of `crying`; apply user exclusions and the source style. These effects are not defaults for other presets. Revise only the requested preset with the immutable source as the design authority, retain prior candidates, and keep other selections intact. Explicit [bounded refinement](../../../references/refinement.md) also uses the previous complete image as the edit target for corrections identified in its review.

The six newer presets (`shy` through `crying`) have file-workflow support and editing directions. Artistic fidelity and distinctness require reviewing actual generated images; automated workflow tests do not validate image-generation quality.

## Construct the expression prompt

Use the shared [editing boundaries](../../../references/edit-boundaries.md) and the chosen preset's starting direction to identify the allowed facial movements and protected remainder. Preserve four distinct pieces: emotion and visible action/effect cues, facial design invariants, protected non-face artwork, and complete-image output. Include the detail needed for a faithful, clearly achieved result; do not shorten the prompt at the expense of any of these pieces. The shared template and Outfits' color-only permission do not replace the expression domain's positive movement/effect instructions.

Use a natural, discernible emotion unless the user requests another intensity. "Not shouting" excludes a manner of expression; it does not require barely visible brows or lips. Do not blanket all presets with "slight," "restrained," or "unchanged face." A source that already smiles still needs a perceptible change for `happy`. Inspect whether the chosen movements are enough to distinguish similar presets.

For protected appearance, inherit source values rather than naming a guessed color, ethnicity, age, eye shape, or face design. Preserve each eye's original color distribution, gradients, iris pattern, pupil design and highlights; do not normalize mixed tones or different eyes to a single named color. A reflection is not proof of the iris base color. If uncertain, say "the source's original iris colors and their distribution" instead of inventing a label. Introduce a new attribute only when the user requested that change and the operation supports it.

Translate and instantiate this structure in the user's language, replacing brackets with the actual request and canvas:

> Edit the complete original character illustration for a visual novel expression variant. Emotion: [emotion and intensity]. Visible changes: [coordinated brow/eyelid/lip actions and required effects]. Change only those expression movements/effects. Inherit each eye's original iris colors, their spatial distribution and gradients, pupil design, highlight layers, eyelashes and line style; eyelids/brows may move without recoloring or redesigning the eyes. Preserve nose form and shading, skin tone and rendering, lip rendering, face shape/proportions and original brushwork. Preserve the complete non-face artwork, pose, head position, silhouette, clothing and props. Return one full image using the source's [canvas and framing] and original [transparency/background], without text or a comparison sheet.

Adapt eye constraints for `eyes_closed`: cover the existing eyes with natural eyelids without inventing visible irises, and preserve the original mouth. For explicit mouth states, use [mouth-states.md](mouth-states.md); an opening/closure instruction takes precedence over a preset's default lip shape while keeping its emotion. Intended blush/tears may affect local skin rendering; other skin remains protected.

Before submission, read the actual prompt back against the source and request. Check factual appearance claims, required effects, and conflicts between allowed motion and protected design. Save that submitted text. In a larger set, inspect the first returned face against its source before propagating a common description; correct discovered input errors for jobs not yet submitted. Preserve failed candidates and respect the requested count.

Keep prompt correctness and tool preservation separate. A wrong color instruction is an input defect; correct instructions followed by recoloring or redesign are output defects. Neither a workflow test nor a recognizable face proves that the iris and expression were preserved.

Eyes/brows may move as needed for the expression while retaining iris design, lash/line style, and characteristic brow rendering. Lips may change shape while preserving their style and facial proportions. Nose form, identity, head pose, skin rendering, and unrelated regions remain protected. Translate the concrete instruction into the user's language and derive named exclusions from the source. Preserve its transparency or opaque background; hidden RGB is not visible background content.

For an unsatisfactory candidate, identify a visible issue before a targeted revision: weakened nose shading, thicker mouth lines, a rounder face, changed skin tone, or simplified iris layers. Do not use "prettier" or "more detailed" as a reason to redesign the face.

Always provide the original illustration as the primary edit reference. An additional facial reference may reinforce fidelity without changing the full-image deliverable.
