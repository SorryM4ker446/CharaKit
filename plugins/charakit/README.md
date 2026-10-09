# CharaKit

Version **0.1.3**. A modular Codex plugin for visual novel character artwork.

The available **CharaKit Expressions** module preserves the entire face, original art style, character design, and visual harmony. Each expression is an independent image. Generation uses the image editing tool available in the Codex host; the plugin does not lock a model or include an external API, database, MCP server, background service, or separate UI.

## Modules

| Module | Skill ID | Status |
| --- | --- | --- |
| Expressions | `charakit-expressions` | Available |
| Outfits | `charakit-outfits` | Planned |
| Poses | `charakit-poses` | Planned |

The plugin ID is `charakit`. Only `$charakit-expressions` is callable today. [modules.json](modules.json) reserves future module IDs; [ROADMAP.md](ROADMAP.md) defines their scope and order. Planned modules have no packaged Skills.

## Install

From the repository root, using a Codex CLI that supports plugins:

```shell
codex plugin marketplace add .
codex plugin add charakit@charakit-local
```

For a published repository, replace the first command with:

```shell
codex plugin marketplace add YOUR_GITHUB_OWNER/CharaKit --ref main
```

Restart or refresh Codex and open a new chat to load the installed Skill. Image editing tool availability depends on the host; installing the plugin does not add a missing image tool.

## Use

Attach your character illustration and request expressions:

```text
Use $charakit-expressions to create happy, sad, angry, surprised,
and eyes-closed versions. Preserve the entire face, original style,
character design, composition, and transparent background.
```

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

Requires Python **3.11+** and Pillow. Install from this plugin directory:

```shell
python -m pip install -r requirements.txt
```

The helper is `skills/charakit-expressions/scripts/studio.py`. Use its absolute installed path when calling it outside this directory:

```shell
python skills/charakit-expressions/scripts/studio.py --help
```

Commands: `inspect`, `validate`, `init`, `add`, `status`, `review`, `select`, `preview`, `export`.

- Source snapshots, versioned candidates, preview images, and exports are not overwritten.
- `run.json` records fingerprints, technical checks, feedback, and selected versions.
- Failed `add` checks return exit code 2 but keep the saved candidate.
- `preview --face-box LEFT TOP RIGHT BOTTOM` uses source-canvas coordinates for whole-face inspection. `--background` accepts `checker`, `light`, or `dark`.
- `preview --labels-file labels.json` supports user-language labels; see the Skill's quality checklist.
- `review --status accepted` requires explicit user feedback and passing technical checks. Positive feedback on a failed candidate can be saved separately.
- `export` revalidates the selected, accepted versions and packages their unchanged PNG bytes with a manifest.
- Work sequentially within a character directory; simultaneous writers are unsupported.

Inputs are static PNG/JPEG files up to 50 MiB and 40 million pixels. Final assets must be PNGs matching the source canvas. Transparency checks are basic; artistic fidelity, clean edges, and game-switching stability require visual review. The helper never generates images, repairs faces, composites facial parts, rescales candidates, or changes alpha.

User artwork belongs in a workspace output directory, not inside this plugin. The distribution ZIP includes only the plugin and its supporting resources.
