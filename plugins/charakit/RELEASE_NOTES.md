# CharaKit 0.2.0-beta.1

First public beta for editing complete, static visual novel character illustrations in Codex.

## Available workflows

- Twelve expression presets and explicit static mouth-open / mouth-closed variants.
- Garment recoloring, single-garment replacement, full-outfit replacement, and accessory / prop addition, removal and replacement.
- Eight static dialogue pose presets with explicit arm, contact and overlap requirements.
- Scoped references, bounded redraws, user-selected revisions, retained version history, human feedback and original PNG / ZIP delivery.

## Changes since development version 0.1.34

- Allow different source/output resolutions through acceptance, selection and export. Show localized source/actual dimensions and retain original file bytes.
- Keep selected-version warnings and current delivery outcomes consistent across review pages, export manifests and reports while preserving historical feedback.
- Add repeatable developer QA: immutable visual snapshots, independent export and warning audits, browser interaction checks and static illustration comparisons.
- Render page templates from Python; exclude standalone HTML template files from plugin packages. Offline preview pages are generated at runtime.
- Add MIT licensing to the repository and plugin ZIP, an installable marketplace ZIP, and a clean-environment package verifier.

## Validation scope

Validation covers automated workflow and browser checks, actual image edits across the implemented modules, and selected-version PNG/ZIP delivery with original file bytes preserved. Real-art coverage remains limited and does not establish first-attempt success or consistent quality across characters, styles and all pose presets.

Release preparation additionally verifies the final archive, fresh helper dependencies and all three installed module entrypoints. The release verification report records the actual package SHA-256, commands, environment and CI run; checks must be tied to the release commit rather than inferred from earlier green runs.

## Requirements and installation

Use a Codex host with plugin support and an available image editing tool, plus Python 3.11 or later. Install the helper dependencies from `requirements.txt`; keep `lib/`, `locales/`, references and all three Skills together. Playwright and the repository QA tools are development-only dependencies.

The marketplace release ZIP contains `.agents/plugins/marketplace.json` and `plugins/charakit/`. From its extracted root, run:

```shell
python -m pip install -r plugins/charakit/requirements.txt
codex plugin marketplace add .
codex plugin add charakit@charakit
```

Open a new chat after installation. The plugin-only ZIP needs an existing marketplace pointing to its directory. Update the installed plugin when upgrading from 0.1.34; changing a repository checkout alone does not establish that its cached install has changed.

## Known limitations

- Human inspection remains necessary: image editing can change identity, protected details, placement or framing. Cross-character/style success rates and all eight real pose outputs have not been established.
- Different resolutions are exportable, with a warning. The helper does not automatically resize, align, composite or repair artwork.
- Outputs are static images. Animation and lip-sync are not implemented. Game-engine behavior requires separate testing.
- Modules keep independent state. Cross-module automatic generation, animation, Live2D parts/rigging, large turns, sitting, leaning and object-interaction poses are outside this beta.
- Generation uses the host's image editing tool; no image model, external image API or MCP service is bundled.

## License

CharaKit code and documentation use the bundled [MIT License](LICENSE). User artwork and third-party assets remain under their respective rights and terms.
