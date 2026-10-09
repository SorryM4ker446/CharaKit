# Quality checks: technical validity and art approval

Explain the checks, outcomes, and limitations in the user's language. Internal status and error codes remain unchanged.

## Entire face

First compare the submitted prompt to the source/request. An incorrect appearance label, missing required tears/blush, or conflicting motion constraint is a prompt defect, even if the tool followed it. Record it separately from output fidelity; do not attribute every mismatch to the backend. Keep the actual prompt as evidence.

Compare enlarged corresponding face regions in the original and candidate:

- Eyes: each eye's source color distribution and gradients, iris layers/pattern, pupils, highlights, eyelashes, eyeliner, and eyelid rendering. Check whether a mixed iris palette was replaced by a uniform hue; emotion does not authorize recoloring.
- Eyebrows: characteristic shape, thickness, color, and brushwork; position may change for expression.
- Nose: original form, linework, shading, and volume.
- Lips and mouth: rendering, color, edges, and proportions; mouth shape may change for expression.
- Contours and proportions: cheeks, chin, and the relationships between facial features.
- Skin: tone, subtle detail, shading, and lighting; no flattening, dirty colors, or excessive sharpening.
- Whole face: consistent linework, brushwork, and detail density. Do not limit inspection to the eyes or recognizability in a thumbnail.
- Expression: check a perceptible difference from the source and between similar requested presets, especially confusion/worry/sadness/crying and wry/happy. Keep confidence suited to the character. Blush for `shy` and tears for `crying` must be visible, match the source rendering and retain facial detail; existing eye highlights alone do not establish crying. Do not flag these intended changes as defects merely because they differ from the source.
- Mouth state: verify explicit open/closed states visually. Keep emotion, gaze, brows, and intensity consistent between the two, with natural mouth-interior rendering and stable facial proportions. A metadata label does not prove the generated image matches the request.

## Full image and game display

- Compare against the allowed movements and invariants defined by the active expression/mouth domain, then inspect relevant interfaces and protected details selected from the source. Use additional `preview --detail-box` outputs for complex non-face details where useful; do not assume a particular prop or garment exists.
- Preserve style, clothing patterns, hair, accessories, weapons, and character design.
- Keep facial linework, color, materials, and lighting harmonious with the body.
- Compare at identical display size and position; inspect head/body movement and outline flicker.
- Check transparent edges on light, dark, and actual game backgrounds. Alpha presence alone does not prove clean edges.

## Status and user feedback

- `technical_status = passed | failed` is determined by the helper.
- `art_review_status = unreviewed | accepted | rejected` records actual user feedback.
- Explicit selection or satisfaction counts as art feedback; do not ask for duplicate confirmation.
- `review --status accepted` requires technical validity. If the user likes a technically failed image, preserve that feedback in a separate review note while retaining the failure. Formal export remains blocked.
- Record a specific art defect only when the user identifies it or it is visible in the current candidate. A checklist item is not evidence of a defect.
- Keep observations and feedback tied to the actual candidate/version. A defect or approval in an earlier experiment does not establish either for a later image.

## Localized preview labels

The helper's default labels and raw JSON diagnostics are English. Codex must explain them in the user's language. To localize the preview itself, write a flat UTF-8 JSON object containing short translated labels, then pass `--labels-file <path>`.

Optional label keys:

| Keys | Meaning |
| --- | --- |
| `source`, `reference` | Source image title and reference status |
| `neutral`, `happy`, `sad`, `angry`, `surprised`, `eyes_closed` | Visible expression titles; version numbers are retained |
| `shy`, `confused`, `wry_smile`, `worried`, `confident`, `crying` | Newer fixed expression titles; version numbers are retained |
| `mouth_closed`, `mouth_open` | Explicit mouth-state titles, displayed with expression and version |
| `unreviewed`, `accepted`, `rejected` | Visible art-review status |
| `technical_passed`, `technical_failed` | Visible technical status |
| Error code, such as `CANVAS_MISMATCH` | Short translated problem description |

Partial overrides are supported; omitted labels use their English defaults. Keys and internal records are never translated. Keep values short enough for the preview card. Detailed explanations belong in chat. Font glyph coverage depends on the local environment.

Example for a Spanish-language request:

```json
{
  "source": "Original",
  "reference": "Referencia",
  "happy": "Feliz",
  "unreviewed": "Sin evaluar",
  "technical_failed": "Error tecnico",
  "CANVAS_MISMATCH": "Tamano distinto al original"
}
```
