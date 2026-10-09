# CharaKit

**English** | [简体中文](README.zh-CN.md)

**CharaKit** is a modular Codex plugin for visual novel character artwork. Its available **CharaKit Expressions** module creates complete expression variants from an existing illustration.

The current module combines a focused Skill with a local Python helper. Codex uses its available OpenAI image editing tool to generate images; the helper preserves versions, checks files, creates full-image and whole-face comparisons, and exports selected resources.

Development version: **0.1.3**.

## Modules

| Module | Skill ID | Status |
| --- | --- | --- |
| CharaKit Expressions | `charakit-expressions` | Available: full expression variants |
| CharaKit Outfits | `charakit-outfits` | Planned: clothing edits and outfit replacement |
| CharaKit Poses | `charakit-poses` | Planned: static pose and action edits |

Install the plugin as `charakit`; invoke the available expression Skill as `$charakit-expressions`. Outfit and pose IDs are reserved in the [module definitions](plugins/charakit/modules.json). Their Skills are not packaged or callable yet. See the [roadmap](plugins/charakit/ROADMAP.md) for the development sequence.

## Current expression features

- Generate neutral, happy, sad, angry, surprised, and eyes-closed variants.
- Preserve the entire face, original art style, character design, pose, and visual harmony.
- Revise a single expression while keeping other candidates and history.
- Compare full illustrations and enlarged face regions on light, dark, or checker backgrounds.
- Check exact canvas dimensions, actual PNG content, transparency, and file fingerprints.
- Export accepted, technically valid PNGs with a manifest and ZIP.

Every variant is a complete image. There is no facial-part extraction, face compositing, database, external image API, ComfyUI integration, MCP service, or dedicated application.

## Requirements

- A Codex host with plugin/Skill support and an available image editing tool.
- Python 3.11+ and Pillow for the local helper.

Installing the plugin does not supply a missing image tool or select a model. Use the current host-provided tool; record the model as unknown when the tool does not report one.

## Install

For a local clone, run from the repository root:

```shell
codex plugin marketplace add .
codex plugin add charakit@charakit-local
```

After publishing to GitHub, users can install from the repository. Replace `YOUR_GITHUB_OWNER/CharaKit` with the actual repository:

```shell
codex plugin marketplace add YOUR_GITHUB_OWNER/CharaKit --ref main
codex plugin add charakit@charakit-local
```

The marketplace name `charakit-local` is a stable identifier used by both local and Git sources. Refresh or restart Codex and open a new chat after installation.

Install the helper dependency in the desired Python environment:

```shell
python -m pip install -r plugins/charakit/requirements.txt
```

## Use

Attach a source illustration in Codex, then ask:

```text
Use $charakit-expressions to generate happy, sad, angry,
surprised, and eyes-closed versions of this character.
Preserve the entire face, original style, design, and visual harmony.
```

Ask for a specific intensity, revise one version, or select images for export.

**The plugin responds in your language.** Progress updates, visible expression names, generation prompts, quality explanations, limitations, and delivery notes follow your current request or explicitly preferred language. CLI arguments, JSON keys, filenames, and status/error codes remain stable English identifiers. Preview labels can be localized through `--labels-file`.

Outputs default to `art-output/<character-key>/`. User artwork and experiment records are ignored by Git and excluded from distribution packages.

## Local helper example

Run from the repository root. Replace image paths and the face coordinates for your artwork:

```shell
python plugins/charakit/skills/charakit-expressions/scripts/studio.py init --project art-output/my-character --source character.png --character my-character
python plugins/charakit/skills/charakit-expressions/scripts/studio.py add --project art-output/my-character --expression angry --image generated-angry.png --prompt-file prompt.txt
python plugins/charakit/skills/charakit-expressions/scripts/studio.py preview --project art-output/my-character --output art-output/my-character/preview/comparison-v001.png --face-box 100 100 200 200 --background light
python plugins/charakit/skills/charakit-expressions/scripts/studio.py review --project art-output/my-character --asset angry_v001 --status accepted --note "User selected this version."
python plugins/charakit/skills/charakit-expressions/scripts/studio.py export --project art-output/my-character
```

A failing `add` returns exit code 2 with a structured report and retains the candidate. A technical pass does not imply art approval. Formal export requires both technical validity and actual user acceptance.

If a user likes an image that fails technical checks, preserve their feedback separately. The helper does not set the `accepted` status until those checks pass.

## Repository layout

```text
README.md                           English overview and instructions
README.zh-CN.md                     Simplified Chinese overview and instructions
.agents/plugins/marketplace.json     Local/Git marketplace entry
.github/workflows/ci.yml             Tests and plugin package verification
plugins/charakit/
  plugin.json                       Plugin manifest
  README.md                         Standalone plugin instructions
  modules.json                      Available and planned module definitions
  ROADMAP.md                        Module scope and development sequence
  requirements.txt                  Helper dependency
  skills/charakit-expressions/
    SKILL.md                        Workflow and language behavior
    references/                     Expression and review guidelines
    scripts/studio.py               Local file helper
tests/test_studio.py                 Synthetic-fixture workflow tests
tools/build_plugin.py               Plugin ZIP builder
CHANGELOG.md                        Version notes
```

## Development

```shell
python -m pip install -r plugins/charakit/requirements.txt
python -m unittest discover -s tests -v
python tools/build_plugin.py --output dist/charakit-0.1.3.zip
```

Tests use synthetic images; no third-party character art is required. CI runs on Linux and Windows. The build refuses to overwrite an existing ZIP.

The plugin ZIP contains only the plugin's files. Keep user images, prompts, local feedback, caches, credentials, and personal machine paths out of commits.

## Current limitations

Image editing can redraw details outside the face or return a different canvas size. Prompt constraints do not guarantee identity, style, design, or positional stability. Automatic checks validate file requirements; users evaluate the actual art and test expression switching in their game.

The initial single-expression experiment was rejected. A later five-expression batch received positive feedback on its visual effect, but its output canvas still failed validation. Those private test images are not distributed with this repository.

See the [plugin guide](plugins/charakit/README.md) and [changelog](CHANGELOG.md) for details.
