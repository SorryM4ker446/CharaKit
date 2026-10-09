# Static mouth states

Use the existing Expressions Skill for mouth-open and mouth-closed requests. These are complete static images for dialogue, with independently saved versions and selections. They do not provide phonemes, lip synchronization, or animation frames.

| ID | Meaning | Prompt direction |
| --- | --- | --- |
| `default` | Mouth state unspecified, including legacy assets | Follow the emotion and user details. Do not infer that an old image is closed-mouth. |
| `closed` | Explicit mouth closed | Keep the lips closed with a shape suited to the emotion. Preserve its eyes, brows, gaze, blush or tears, and intensity. |
| `open` | Explicit mouth open | Make a small natural speaking opening suited to the emotion. Preserve its eyes, brows, gaze, and intensity; do not convert it into surprise, shouting, or exaggerated laughter. |

An explicit mouth state overrides a preset's starting mouth direction. For example, surprised/closed retains surprised eyes and brows while closing the mouth. Eyes-closed/open keeps the eyes closed. Mouth state metadata describes the request; it is not an automatic visual judgment.

Apply the shared [editing boundaries](../../../references/edit-boundaries.md) at mouth-component scope. When only changing mouth state, allow the lip contour and interior changes necessary for opening/closure; retain lip rendering, facial proportions, and the established eyes, brows, gaze, emotion, and head pose. When emotion and mouth state are both requested, apply both declared permissions without extending them to clothing, hair, props, or other unrequested properties.

## Generation and revision

Generate only requested combinations. An ordinary request for happy does not require happy/open and happy/closed. For “happy, open and closed, two candidates each,” save four images: two versions in each state. Do not create new expression IDs such as `talking`.

Every image retains the immutable source as its primary design authority. Ordinary pairs/revisions may include a selected emotion image as support. Explicit [bounded refinement](../../../references/refinement.md) uses the previous complete candidate as the edit target while the original remains the baseline for all non-mouth features. Never promote an unreviewed image to the source. Keep the open/closed state during revisions; changing it creates a separate resource.

In the user's language, state the emotion, mouth state, allowed change, and preserved full-face details. When changing only mouth state, preserve emotional intensity and the established eyes/brows as well as clothing, hair, pose, and layout. Allow the lip and mouth-interior changes needed for a natural opening; do not paste a new mouth onto the source.

Use the source-inheritance and prompt checks in [expression-guidelines.md](expression-guidelines.md): retain each eye's actual color distribution and design without assigning a guessed hue. Include the preservation detail needed for quality; changing lip shape does not permit a new iris palette, face design, or weakened emotion. Avoid contradictory instructions such as requiring closed lips and a speaking opening together.

Compare full illustrations and whole-face enlargements. Check whether the requested state is visibly present, whether the emotion is stable between states, whether teeth/tongue/mouth interior match the original rendering, and whether head position, facial proportions, and outlines move during switching. Technical checks cannot verify these visual properties.

## Saved resources and compatibility

Legacy and unspecified assets retain IDs such as `happy_v001`, the selection key `happy`, and the export path `sprites/<character>/happy.png`.

Explicit states use IDs such as `happy_mouth_closed_v001` and `happy_mouth_open_v001`. Each expression/state pair starts its own version sequence and revision-parent chain. Selection keys and export filenames use `happy_mouth_closed` and `happy_mouth_open`. Selecting or rejecting one state does not remove another state.

Schema 1.0 projects are readable without modification. The first explicit-state import saves an exact `run.schema-1.0.backup.json` before upgrading `run.json` to schema 1.1. Source images, old candidate IDs, history, and selections remain intact. Existing assets without `mouth_state` mean `default`. Continue using CharaKit 0.1.5 or later after the upgrade; older helpers do not read schema 1.1. If a backup from an interrupted upgrade differs from current metadata, preserve both and resolve the conflict before retrying; do not overwrite the backup.

Exports with explicit states use manifest schema 1.1 and record `mouth_state` for every included sprite, including `default` for legacy images. Exports containing only unspecified assets retain manifest schema 1.0. Export permits one accepted, technically valid version per expression/state and copies unchanged PNG bytes.

## Helper examples

```text
python <skill>/scripts/studio.py add --project <output-dir> --expression happy --mouth-state closed --image <closed.png> --prompt-file <closed-prompt.txt>
python <skill>/scripts/studio.py add --project <output-dir> --expression happy --mouth-state open --image <open.png> --prompt-file <open-prompt.txt>
python <skill>/scripts/studio.py preview --project <output-dir> --asset happy_mouth_closed_v001 --asset happy_mouth_open_v001 --output <pair-preview.png> --face-box <left> <top> <right> <bottom>
python <skill>/scripts/studio.py preview --project <output-dir> --expression happy --mouth-state open --output <open-candidates-preview.png>
python <skill>/scripts/studio.py review --project <output-dir> --asset happy_mouth_closed_v001 --status accepted --note <user-feedback>
python <skill>/scripts/studio.py review --project <output-dir> --asset happy_mouth_open_v001 --status accepted --note <user-feedback>
python <skill>/scripts/studio.py export --project <output-dir>
```

When both variants have actual user acceptance and pass technical checks, the last command includes both. Preserve positive feedback separately for failed candidates, as in the regular expression workflow. Localize preview state labels with `mouth_closed` and `mouth_open` in the labels JSON. Labels change previews only.
