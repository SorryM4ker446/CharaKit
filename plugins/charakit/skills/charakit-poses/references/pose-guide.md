# Static dialogue poses

| Preset | Action | Focus |
| --- | --- | --- |
| `natural_standing` | Relaxed standing, both arms naturally lowered; side `none` | Proportions, support, shoulders and cuffs; reuse an already matching source rather than force a redraw. |
| `hand_on_hip` | Specified hand rests at the waist | Palm/waist contact, elbow and shoulder connection, sleeve/body overlaps. |
| `wave` | Specified hand near shoulder height, palm outward | Anatomical side, palm orientation, fingers, wrist, shoulder and sleeve continuity. |
| `palm_up` | Specified hand extends slightly forward, palm upward | Palm/wrist rotation, restrained perspective, forearm length and sleeve response. |

Use the actual character, request and reference to set amplitude and hand shape. Keep the other arm as requested or otherwise preserve it. Preserve intentional left/right asymmetry and do not horizontally mirror the entire image to change sides. The source can be cropped at the legs; do not invent unseen feet merely to prove balance. Inspect visible support and torso alignment honestly. If pose feasibility depends on an unresolved object or framing conflict, resolve it before generation; changing the object is outside this first version.

## Permissions and prompt

The target is an action, not a new costume, face or emotion. Preserve facial shape, eyes/irises/pupils/highlights, nose rendering, expression, mouth state, gaze, head orientation, hairstyle design, clothing construction/materials/colors/patterns, equipment design, proportions, style, lighting, source canvas and background. Allow only the requested limb movement and necessary joint/contact/occlusion/fold/hair placement adjustments. Keep the head and torso near the source orientation; larger viewpoint changes are deferred. Newly uncovered skin/clothing/hair follows the source's design and rendering; unknown pixels are reconstructed, not recovered. Preserve existing coverage except movement-required interfaces. No unrelated cloth redesign or object editing.

Pose references guide structural relationships and the gesture only. Ignore their face, emotion, clothes, proportions, rendering, framing and backdrop. Record each reference with `scope: ["pose"]` and notes identifying the permitted cues. An expression or outfit reference is not a pose authorization.

Adapt this template to the user's language:

> Edit the complete source into [action, character anatomical side, amplitude, palm orientation and other arm]. Permit [necessary limb, joint, contact, folds and overlap changes]. Retain [source-grounded identity, expression, mouth state, head orientation, hair/clothing/equipment designs, proportions, style and protected remainder]. Any pose reference guides only [recorded structural cues]. Keep [canvas, framing, background/transparency and requested anchors]. Output one complete PNG without text or comparison panels.

## Domain review

`domain_review` uses `version: "1.0"`, `kind: "pose_edit"`, the actual action in `component`, the matching preset in `pose`, the matching anatomical `side` and exactly these `checks`. Each observation has `status` (`passed`, `failed`, `uncertain`) and concrete `evidence`. Combine with the shared rubric 1.2 contract/assessment; this is visual judgment, not automatic landmark or pixel scoring.

| Check ID | Required observation |
| --- | --- |
| `target_pose` | Requested action, side, amplitude and palm/hand orientation are visibly achieved; reference cues stay within scope. |
| `limbs_joints` | Plausible visible shoulders, elbows, wrists, hands/fingers, limb count, lengths and connections; clothing follows the correct limb. |
| `balance_support` | Plausible visible stance, torso alignment and support without inventing evidence about cropped/hidden anatomy. |
| `contacts` | Natural required hand/waist or other allowed contact; no floating or interpenetration. For contact-free gestures inspect separation and do not invent a required contact. |
| `occlusion_clothing` | Correct front/back ownership, design-continuous folds and sleeves; exposed regions are plausible, without old arm fragments, holes or unintended design changes. |
| `face_expression` | Identity, facial detail, current emotion, mouth state, gaze and protected head orientation remain consistent. |
| `non_target_protection` | Designs, equipment, proportions, style and protected remainder remain intact; authorized action/fold/overlap changes are excluded from drift. |
| `framing_anchors` | Complete framing on the original canvas, no clipped raised hand or unintended translation; actual user-specified anchors checked without auto alignment. With no requested anchor, check framing only and say so. |
| `rendering` | Source-consistent lines, materials, shading, local interfaces and transparent/background edges; no extra text, panels or artifacts. |

Every failure or uncertainty blocks passage, including when the five dimensions total 100. Avoid duplicate scoring of one defect across dimensions. For revisions retain the chosen pose, correct the specific finding and recheck still-protected designs against the original. Never use the original body silhouette as a substitute for checking anatomical/design continuity.

## Inspection locations

The helper uses common canvas coordinates for source, revision parent and all candidates. Inspect actual positions before specifying detail boxes; use a common region large enough to include the moved shoulder/hand and relevant baseline region. Default human pages show full images and do not reuse the prepared source target box. If positions make a common crop uninformative, inspect each full/raw image directly. No independent candidate boxes, game-anchor detector, landmark tracking or alignment is implemented.
