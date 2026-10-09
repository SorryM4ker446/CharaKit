# Quality checks: technical validity and art approval

Explain the checks, outcomes, and limitations in the user's language. Internal status and error codes remain unchanged.

## Entire face

Compare enlarged corresponding face regions in the original and candidate:

- Eyes: iris color and layers, pupils, highlights, eyelashes, eyeliner, and eyelid rendering.
- Eyebrows: characteristic shape, thickness, color, and brushwork; position may change for expression.
- Nose: original form, linework, shading, and volume.
- Lips and mouth: rendering, color, edges, and proportions; mouth shape may change for expression.
- Contours and proportions: cheeks, chin, and the relationships between facial features.
- Skin: tone, subtle detail, shading, and lighting; no flattening, dirty colors, or excessive sharpening.
- Whole face: consistent linework, brushwork, and detail density. Do not limit inspection to the eyes or recognizability in a thumbnail.
- Expression: distinguish `confused` from `surprised`, `worried` from `sad`, and `wry_smile` from `happy`. Keep confidence suited to the character. Blush for `shy` and tears for `crying` must match the source rendering and retain facial detail; do not flag these intended changes as defects merely because they differ from the source.

## Full image and game display

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
- A previous experiment exposed whole-face fidelity and canvas-size problems. A later five-expression batch received positive user feedback on its art effect while still failing canvas validation. Do not carry the older rejection forward as a rejection of later candidates.

## Localized preview labels

The helper's default labels and raw JSON diagnostics are English. Codex must explain them in the user's language. To localize the preview itself, write a flat UTF-8 JSON object containing short translated labels, then pass `--labels-file <path>`.

Optional label keys:

| Keys | Meaning |
| --- | --- |
| `source`, `reference` | Source image title and reference status |
| `neutral`, `happy`, `sad`, `angry`, `surprised`, `eyes_closed` | Visible expression titles; version numbers are retained |
| `shy`, `confused`, `wry_smile`, `worried`, `confident`, `crying` | Newer fixed expression titles; version numbers are retained |
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
