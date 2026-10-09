# CharaKit

Version **0.1.9**. A modular Codex plugin for visual novel character artwork.

Use the shared [editing boundaries](references/edit-boundaries.md) across available modules: target, allowed property, target invariants, and protected interfaces/remainder. Unrequested components and properties remain protected. Derive prompt wording and inspection regions from the actual source and active domain; Outfits uses [garment domains](skills/charakit-outfits/references/garment-domains.md), while Expressions distinguishes emotion movements from mouth-only changes. These rules do not expand implemented capabilities or enforce pixel locks.

The available **CharaKit Expressions** module preserves the entire face, original art style, character design, and visual harmony. Each expression is an independent image. Generation uses the image editing tool available in the Codex host; the plugin does not lock a model or include an external API, database, MCP server, background service, or separate UI.

## Modules

| Module | Skill ID | Status |
| --- | --- | --- |
| Expressions | `charakit-expressions` | Available |
| Outfits | `charakit-outfits` | Available: one-garment recoloring |
| Poses | `charakit-poses` | Planned |

The plugin ID is `charakit`. Use `$charakit-expressions` for expressions and static mouth states, or `$charakit-outfits` for recoloring one existing garment. Full outfit replacement, accessory additions/removals, and poses remain planned. [modules.json](modules.json) and [ROADMAP.md](ROADMAP.md) define availability and scope.

## Install

From the repository root, using a Codex CLI that supports plugins:

```shell
codex plugin marketplace add .
codex plugin add charakit@charakit
```

For a published repository, replace the first command with:

```shell
codex plugin marketplace add YOUR_GITHUB_OWNER/CharaKit --ref main
```

The selector `charakit@charakit` combines the plugin ID and marketplace ID; both are `charakit`.

Restart or refresh Codex and open a new chat to load the installed Skill. Image editing tool availability depends on the host; installing the plugin does not add a missing image tool.

## Use

Attach your character illustration and request expressions:

```text
Use $charakit-expressions to create happy, sad, angry, surprised,
and eyes-closed versions. Preserve the entire face, original style,
character design, composition, and transparent background.
```

Twelve fixed presets are supported: `neutral`, `happy`, `sad`, `angry`, `surprised`, `eyes_closed`, `shy`, `confused`, `wry_smile`, `worried`, `confident`, and `crying`. Request a subset or revise only one expression/state. Each combination keeps its own history and selected version. Generated art still needs visual review. See the [expression guide](skills/charakit-expressions/references/expression-guidelines.md).

Static mouth-open and mouth-closed states use this same Skill. For example: “Create happy, mouth closed and naturally open for speaking, two candidates per state, with paired previews.” See [mouth-states.md](skills/charakit-expressions/references/mouth-states.md). These are full static images, without lip synchronization or animation.

The omitted mouth state is `default` (unspecified), not automatically closed. Schema 1.0 projects remain readable. The first explicit-state import backs up metadata and upgrades it to schema 1.1 while preserving source files, candidates, and selections. Use 0.1.5 or later with upgraded projects.

You can also request a revision or export:

```text
Revise only the happy version with a more restrained smile.
Keep the nose shading and original brushwork.
```

```text
Export the versions I selected as game-ready PNGs and a ZIP.
```

**Use any language.** Responses, check explanations, prompt wording, captions, and review notes follow the user's current or preferred language. English source files do not force English answers. Machine-readable IDs and codes stay unchanged.

## Local helper

For garment recoloring, attach the source and ask:

```text
Use $charakit-outfits to recolor only the jacket fabric to navy blue.
Keep trim, buttons, material, folds, lighting, face, expression, mouth state,
hair, other clothing, and pose. Generate two candidates and compare them.
```

Outfits uses its own project, such as `art-output/my-character/outfits/`, with schema 1.2. Each target garment/color option has independent versions, review, and selection. Actual image quality requires visual review. See the [Outfits Skill](skills/charakit-outfits/SKILL.md).

Use `prepare` before generation to save the allowed boundary, protected regions, and a source-only detail reference. Default to one complete source and a concise prompt describing the allowed recolor, exclusions, preservation, and output. Retain the detailed checklist in the brief; send the crop only for ambiguous target identification or a requested reference comparison when supported. The local crop is not an edit mask or a final asset; all final edits stay in the host image tool.

Compare the full image, whole face, target garment, and relevant non-target details such as weapons, hair, hands, and neighboring equipment. Repeat `preview --detail-box` with distinct output paths for additional regions. After inspection, use `fidelity` to record target and protection observations independently. Assistant observations remain separate from user acceptance and technical checks. Non-target repainting remains a known limitation; this simplified workflow is not a proven visual fix.

```shell
python skills/charakit-outfits/scripts/studio.py init --project art-output/my-character/outfits --source character.png --character my-character
python skills/charakit-outfits/scripts/studio.py prepare --project art-output/my-character/outfits --outfit coat_navy --target "jacket fabric" --color "navy blue" --boundary "Fabric only; exclude trim and buttons" --protect "Entire face, expression, hair, pose and other clothing" --target-box 80 250 280 500
python skills/charakit-outfits/scripts/studio.py add --project art-output/my-character/outfits --outfit coat_navy --target "jacket fabric" --color "navy blue" --image generated.png --prompt-file prompt.txt --brief-file art-output/my-character/outfits/briefs/coat_navy_v001.json
python skills/charakit-outfits/scripts/studio.py preview --project art-output/my-character/outfits --outfit coat_navy --output comparison.png --face-box 100 100 200 200 --detail-box 80 250 280 500
python skills/charakit-outfits/scripts/studio.py fidelity --project art-output/my-character/outfits --asset coat_navy_v001 --target-check passed --protection-check uncertain --note "Color changed; protected regions need further inspection"
```

Replace paths and coordinates. `--detail-box` adds a garment enlargement below the optional face row. Revisions use the same target/color definition; use a new outfit ID for a different garment or color. Review, select, and export commands follow the Expressions workflow. Selected outfit PNGs export unchanged to `sprites/<character>/outfits/<outfit-id>.png`.

Brief-linked candidates require both observed checks passed before acceptance, selection, or export. The example records uncertainty, not approval; report only actual visible findings. A failed/uncertain record clears this candidate's selection without rewriting the user's review history. Revisions inherit the brief and need fresh observations. Legacy records remain readable without invented checks; use helper 0.1.7 or newer for the new gates, which older helpers do not enforce. Prompt guidance and extra references cannot guarantee unchanged non-target pixels.

Requires Python **3.11+** and Pillow. Install from this plugin directory:

```shell
python -m pip install -r requirements.txt
```

The entrypoints are `skills/charakit-expressions/scripts/studio.py` and `skills/charakit-outfits/scripts/studio.py`; both use `lib/studio_core.py` inside this plugin. Keep the complete plugin together. Use the entrypoint's absolute installed path when calling it outside this directory:

```shell
python skills/charakit-expressions/scripts/studio.py --help
```

Commands: `inspect`, `validate`, `init`, `add`, `status`, `review`, `select`, `preview`, `export`; Expressions also provides `presets`, and Outfits provides `prepare` and `fidelity`. The CLI rejects a project belonging to the other module before writing. Existing Expressions projects retain schema 1.0/1.1 and their original paths.

- Source snapshots, versioned candidates, preview images, and exports are not overwritten.
- `presets` lists supported expressions and mouth states, English names, and starting directions without a project. Codex translates the human-readable descriptions into the user's language.
- `add --mouth-state default|closed|open` versions each expression/state independently.
- `run.json` records fingerprints, technical checks, feedback, and selected versions.
- Failed `add` checks return exit code 2 but keep the saved candidate.
- `preview --face-box LEFT TOP RIGHT BOTTOM` uses source-canvas coordinates for whole-face inspection. `--background` accepts `checker`, `light`, or `dark`.
- `preview --labels-file labels.json` supports user-language labels; see the Skill's quality checklist.
- `preview --expression happy` includes all happy candidates and states; `--mouth-state open` optionally narrows it. Use repeated `--asset` arguments for a specific two-candidate comparison.
- `review --status accepted` requires explicit user feedback and passing technical checks. Positive feedback on a failed candidate can be saved separately.
- `export` revalidates the selected, accepted versions and packages their unchanged PNG bytes with a manifest. Explicit states export separately, for example `happy_mouth_open.png` and `happy_mouth_closed.png`; duplicates within one expression/state are blocked.
- Work sequentially within a character directory; simultaneous writers are unsupported.

Inputs are static PNG/JPEG files up to 50 MiB and 40 million pixels. Final assets must be PNGs matching the source canvas. Transparency checks are basic; artistic fidelity, clean edges, and game-switching stability require visual review. The helper never generates images, repairs faces, composites facial parts, rescales candidates, or changes alpha.

User artwork belongs in a workspace output directory, not inside this plugin. The distribution ZIP includes only the plugin and its supporting resources.
