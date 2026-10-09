---
name: charakit-expressions
description: Generate full visual novel character expressions and static mouth-open or mouth-closed variants from existing artwork while preserving facial detail, original style, design, and visual harmony. Use for expression editing, individual revisions, comparison previews, version selection, and PNG exports.
---

# CharaKit Expressions

The available expression module of the CharaKit plugin. Deliver complete, independent character images that a game can switch between. Edit the user's source artwork and change only the requested facial expression.

Read the shared [editing boundaries](../../references/edit-boundaries.md) when defining a request and inspecting a result. Distinguish allowed expression movements from facial design invariants; a mouth-only request protects the established emotion and non-mouth features. Protect every unrequested component/property, and derive concrete boundaries and comparison regions from the actual source rather than a previous test character.

Support twelve fixed expression presets and independently selectable static mouth states. Read [expression-guidelines.md](references/expression-guidelines.md) to map a request to a preset and shape its prompt; `presets` lists expressions and mouth states. For mouth-open/closed requests or revisions, read [mouth-states.md](references/mouth-states.md). Generate only requested expressions and states. Gaze and emotion-specific closed-eye states remain planned.

Garment recoloring uses the separate [CharaKit Outfits Skill](../charakit-outfits/SKILL.md). Full outfit replacement and pose editing remain planned in [the module roadmap](../../ROADMAP.md). This Skill remains scoped to expressions; keep outfit projects and candidates separate.

## User language

- Respond in the language of the user's current request, or their explicitly preferred language. Follow a later language change without asking again.
- Apply this to progress updates, expression names, preview captions, quality explanations, limitations, revision discussions, delivery notes, and saved human-readable review notes.
- Write the generation prompt in the user's language unless they request another prompt language.
- English repository documentation does not set the conversation language. Do not answer in English merely because this Skill is written in English.
- Keep CLI arguments, JSON keys, expression IDs, filenames, and error/status codes stable. Explain their meaning in the user's language rather than changing machine-readable values.
- For localized preview labels, create a UTF-8 JSON labels file in the user's output directory and pass it to `preview --labels-file`; see [quality-checklist.md](references/quality-checklist.md). If the installed font cannot display a language, keep usable labels and provide the translated explanation in chat.

## Generation rules

- Inspect the source first. Prefer a single character with a clear front or slightly angled face. Preserve transparency for transparent artwork; do not assume an illustration with a background is a transparent sprite.
- Use the OpenAI image editing tool currently available in the Codex host. Follow its current reference-image, transparency, and file-saving requirements. If unavailable, explain the missing capability. This plugin has no external API integration and cannot select a hidden model through a prompt.
- Use the same immutable source as the primary reference for every expression. For a revision, keep that source as the baseline and optionally include the previous candidate. Do not derive successive expressions from generated variants.
- Preserve the **entire face**: eyes, eyebrows, nose, lips, contours, proportions, skin tone, shading, linework, and brushwork. Eyes are one part of this requirement. Allow necessary expression changes without redesigning, blurring, or simplifying facial features.
- Preserve the original style and character design: hair, ears, accessories, clothing, weapons, pose, proportions, composition, materials, and lighting. Make only the changes needed for the requested emotion; keep the expression harmonious with the whole illustration.
- Return the complete original framing. Do not deliver a face crop as the final asset, extract reusable facial parts, or composite a generated face onto the original. Subtle blush is appropriate for `shy`, and visible tears are part of `crying`, unless excluded by the user. Do not add these effects to other presets by default, or add emotion symbols, sweat drops, or text without a request.
- Adapt intensity and wording to the source and request.

## Save and check

Save each generated image as a candidate before checking it. Saving or displaying an image does not imply art approval.

- Use the user's destination, or `art-output/<character-key>/` in the workspace. Never put user artwork in the plugin installation directory.
- Preserve the original file and all candidate versions. The helper does not repaint, remove backgrounds, change alpha, or resize candidate images.
- Check decoding, PNG format, exact source canvas dimensions, and background requirements. Mark size mismatches as failures; do not hide them with stretching, tight crops, or automatic centering.
- Inspect both full images and enlarged **whole-face** comparisons. Check facial detail, style, design, and harmony at normal game display size; see [quality-checklist.md](references/quality-checklist.md).
- Explain checks and visible problems in the user's language. Scripts verify file requirements, not artistic fidelity. Do not invent identity scores, face scores, or model identifiers.
- Explicit satisfaction or version selection is sufficient art feedback; do not request the same approval again. Unreviewed candidates remain `unreviewed`.
- The helper only sets `accepted` after technical checks pass. If a user likes a technically failed candidate, save their positive feedback separately and explain the remaining technical issue; do not erase their feedback or mark the technical check as passed. Such candidates remain available for inspection but cannot enter a formal export.

## Local helper

`scripts/studio.py` uses Python 3.11+ and Pillow, runs once, and exits. Resolve its absolute path from the actual installed Skill location. Keep the complete plugin including its shared `lib/studio_core.py` together. Use proper shell quoting for paths with spaces or Unicode.

Example commands; replace bracketed paths with actual paths:

```text
python <skill>/scripts/studio.py presets
python <skill>/scripts/studio.py init --project <output-dir> --source <source.png> --character <character-key>
python <skill>/scripts/studio.py add --project <output-dir> --expression angry --image <generated.png> --prompt-file <prompt.txt>
python <skill>/scripts/studio.py add --project <output-dir> --expression happy --mouth-state closed --image <generated-closed.png> --prompt-file <closed-prompt.txt>
python <skill>/scripts/studio.py add --project <output-dir> --expression happy --mouth-state open --image <generated-open.png> --prompt-file <open-prompt.txt>
python <skill>/scripts/studio.py preview --project <output-dir> --output <preview.png> --face-box <left> <top> <right> <bottom> --labels-file <labels.json>
python <skill>/scripts/studio.py review --project <output-dir> --asset angry_v001 --status accepted --note <user-feedback>
python <skill>/scripts/studio.py select --project <output-dir> --asset angry_v001
python <skill>/scripts/studio.py export --project <output-dir>
```

- `presets` returns expression IDs and `mouth_states` with English names and directions without a project. Translate names and directions for the user; fixed IDs remain unchanged.
- `init` snapshots the source and records canvas and background mode without overwriting a project. Existing images can be checked with `inspect` / `validate` without initialization.
- `add --mouth-state default|closed|open` preserves a candidate and returns a report even if technical checks fail. Omission uses `default`, which does not mean closed. Explicit states have independent versions; the first explicit state backs up schema 1.0 metadata and upgrades it to 1.1. A nonzero exit code does not mean the saved candidate should be discarded.
- `preview` shows full images on light, dark, or checker backgrounds. `--face-box` uses source-canvas pixel coordinates; magnification is for inspection only. Use repeated `--asset` arguments to compare chosen candidates side by side, including two candidates for one state. `--expression` and `--mouth-state` optionally filter candidates; an expression filter retains all its states and versions. Size mismatches are explicitly labeled, not corrected.
- `review` accepts a technically valid candidate and selects it for its expression and mouth state. `select` switches between accepted versions in that same state, preserving the other selections.
- `export` rechecks selected files and fingerprints and packages only accepted, technically valid PNGs with a manifest.
- Check for Pillow before first use and install `requirements.txt` in the current environment if needed. No API key is involved.
- Operate sequentially within one character directory; multiple chats must not modify the same `run.json` concurrently.

## Revisions and delivery

Revise only the requested image; preserve other expressions and history. Produce one new candidate for an explicit revision request, then show its result and any remaining issue. Do not retry indefinitely or silently regenerate images the user likes.

Show actual images and file links. Export selected PNGs or ZIPs as requested. Explain dimensions, technical status, and unresolved art issues in the user's language. A request to try one expression does not require generating the whole standard set.
