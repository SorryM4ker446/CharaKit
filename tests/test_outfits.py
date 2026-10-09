"""Recolor file workflows and shared-helper packaging, using synthetic artwork."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "plugins/charakit/skills/charakit-outfits/scripts/studio.py"
EXPRESSIONS = REPO / "plugins/charakit/skills/charakit-expressions/scripts/studio.py"
spec = importlib.util.spec_from_file_location("outfits", SCRIPT)
outfits = importlib.util.module_from_spec(spec)
spec.loader.exec_module(outfits)
build_spec = importlib.util.spec_from_file_location("builder", REPO / "tools/build_plugin.py")
builder = importlib.util.module_from_spec(build_spec)
build_spec.loader.exec_module(builder)


def fixture(path, color="#ccccdd", size=(96, 144), transparent=True):
    image = Image.new("RGBA" if transparent else "RGB", size, (0, 0, 0, 0) if transparent else "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((35, 6, 61, 34), fill="#e7c5a0")
    draw.rectangle((28, 40, 68, 95), fill=color)
    draw.line((48, 42, 48, 90), fill="#222222", width=2)
    draw.rectangle((28, 96, 68, 125), fill="#448855")
    image.save(path)


class OutfitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / "source-é.png"
        fixture(self.source)
        self.root = self.folder / "outfits output"
        outfits.init_project(self.root, self.source, "test_character")
        # Legacy projects remain compatible; default quality-gated projects have their own suite.
        state = outfits.read_state(self.root)
        state.pop("quality_policy")
        outfits.write_state(self.root, state)

    def candidate(self, outfit_id="coat_navy", color="navy blue", size=(96, 144), transparent=True):
        image = self.folder / "candidate.png"
        fixture(image, "#334477", size, transparent)
        return outfits.add_asset(self.root, image, outfit_id, "jacket fabric", color)["asset"]

    def accepted(self, outfit_id="coat_navy", color="navy blue"):
        asset = self.candidate(outfit_id, color)
        outfits.review_asset(self.root, asset["id"], "accepted", "User chose this color option.")
        return asset

    def assert_code(self, code, call, *args, **kwargs):
        with self.assertRaises(outfits.StudioError) as caught:
            call(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def cli(self, script, *args):
        return subprocess.run([sys.executable, str(script), *map(str, args)], cwd=self.folder,
                              capture_output=True, encoding="utf-8")

    def test_outfit_project_snapshots_source_and_does_not_overwrite(self):
        state = outfits.read_state(self.root)
        self.assertEqual((state["schema_version"], state["module"]), ("1.2", "outfits"))
        original = (self.root / "source.png").read_bytes()
        fixture(self.source, "#dd8833")
        self.assertEqual((self.root / "source.png").read_bytes(), original)
        before = (self.root / "run.json").read_bytes()
        self.assert_code("PROJECT_EXISTS", outfits.init_project, self.root, self.source, "another")
        self.assertEqual((self.root / "run.json").read_bytes(), before)

    def test_options_have_independent_history_selection_and_rejection(self):
        first = self.accepted()
        red = self.accepted("coat_red", "red")
        first_bytes = (self.root / first["path"]).read_bytes()
        second = self.candidate()
        self.assertEqual(second["id"], "coat_navy_v002")
        self.assertEqual(second["parent_asset_id"], first["id"])
        self.assertEqual(red["version"], 1)
        outfits.review_asset(self.root, second["id"], "accepted")
        outfits.select_asset(self.root, first["id"])
        outfits.review_asset(self.root, second["id"], "rejected")
        self.assertEqual(outfits.read_state(self.root)["selected"], {"coat_navy": first["id"], "coat_red": red["id"]})
        outfits.review_asset(self.root, first["id"], "rejected")
        self.assertEqual(outfits.read_state(self.root)["selected"], {"coat_red": red["id"]})
        self.assertEqual((self.root / first["path"]).read_bytes(), first_bytes)

    def test_export_contains_only_chosen_options_and_preserves_png_bytes(self):
        chosen = [self.accepted(), self.accepted("coat_red", "red")]
        self.candidate("coat_gold", "gold")
        result = outfits.export_pack(self.root)
        self.assertIn("-outfits-v001.zip", result["export"])
        self.assertEqual(result["manifest"]["schema_version"], "1.2")
        self.assertEqual(result["manifest"]["asset_kind"], "full_character_outfit")
        with zipfile.ZipFile(result["export"]) as archive:
            self.assertEqual(len(archive.namelist()), 3)
            for sprite, asset in zip(result["manifest"]["sprites"], chosen):
                self.assertEqual(sprite["target"], "jacket fabric")
                self.assertEqual(sprite["color"], asset["color"])
                self.assertEqual(sprite["edit_type"], "recolor")
                self.assertNotIn("expression", sprite)
                self.assertEqual(sprite["path"], f'sprites/test_character/outfits/{asset["outfit_id"]}.png')
                self.assertEqual(archive.read(sprite["path"]), (self.root / asset["path"]).read_bytes())
        with self.assertRaises(FileExistsError):
            outfits.export_pack(self.root, Path(result["export"]))

    def test_duplicate_option_versions_cannot_overwrite_archive_entries(self):
        first, second = self.accepted(), self.accepted()
        output = self.folder / "duplicate.zip"
        self.assert_code("DUPLICATE_OUTFIT", outfits.export_pack, self.root, output, [first["id"], second["id"]])
        self.assertFalse(output.exists())

    def test_failed_candidate_is_kept_without_replacing_valid_selection(self):
        first = self.accepted()
        failed = self.candidate(size=(48, 72))
        self.assertTrue((self.root / failed["path"]).is_file())
        self.assertIn("CANVAS_MISMATCH", failed["validation"]["errors"])
        self.assert_code("TECHNICAL_CHECK_FAILED", outfits.review_asset, self.root, failed["id"], "accepted")
        self.assert_code("ART_REVIEW_REQUIRED", outfits.select_asset, self.root, failed["id"])
        self.assertEqual(outfits.export_pack(self.root)["asset_ids"], [first["id"]])

    def test_changed_or_missing_selected_candidate_blocks_export(self):
        asset = self.accepted()
        fixture(self.root / asset["path"], "#aa4466")
        self.assert_code("TECHNICAL_CHECK_FAILED", outfits.export_pack, self.root)
        (self.root / asset["path"]).unlink()
        self.assert_code("TECHNICAL_CHECK_FAILED", outfits.export_pack, self.root)
        outfits.review_asset(self.root, asset["id"], "rejected", "Missing output")
        self.assertEqual(outfits.read_state(self.root)["selected"], {})

    def test_invalid_definition_or_changed_target_color_is_rejected_before_import(self):
        self.candidate()
        before = (self.root / "run.json").read_bytes()
        for outfit_id, target, color, code in [
            ("../coat", "jacket", "blue", "INVALID_OUTFIT_ID"),
            ("empty", "", "blue", "INVALID_RECOLOR"),
            ("empty", "jacket", " ", "INVALID_RECOLOR"),
            ("empty", "jacket\nshirt", "blue", "INVALID_RECOLOR"),
            ("coat_navy", "skirt", "navy blue", "OUTFIT_DEFINITION_CHANGED"),
            ("coat_navy", "jacket fabric", "red", "OUTFIT_DEFINITION_CHANGED"),
        ]:
            with self.subTest(outfit_id=outfit_id, target=target, color=color):
                self.assert_code(code, outfits.add_asset, self.root, self.source, outfit_id, target, color)
                self.assertEqual((self.root / "run.json").read_bytes(), before)
        self.assertEqual(len(list((self.root / "candidates").glob("*.png"))), 1)

    def test_wrong_module_cli_operations_do_not_modify_either_project(self):
        expressions_root = self.folder / "expressions"
        result = self.cli(EXPRESSIONS, "init", "--project", expressions_root, "--source", self.source, "--character", "test_character")
        self.assertEqual(result.returncode, 0, result.stderr)
        expression_before = (expressions_root / "run.json").read_bytes()
        result = self.cli(SCRIPT, "add", "--project", expressions_root, "--outfit", "coat_navy", "--target", "jacket", "--color", "blue", "--image", self.source)
        self.assertEqual(json.loads(result.stderr)["error"]["code"], "WRONG_MODULE")
        self.assertEqual((expressions_root / "run.json").read_bytes(), expression_before)
        outfit_before = (self.root / "run.json").read_bytes()
        result = self.cli(EXPRESSIONS, "add", "--project", self.root, "--expression", "happy", "--image", self.source)
        self.assertEqual(json.loads(result.stderr)["error"]["code"], "WRONG_MODULE")
        self.assertEqual((self.root / "run.json").read_bytes(), outfit_before)
        self.assert_code("WRONG_MODULE", outfits.add_outfit, expressions_root, self.source, "coat_navy", "jacket", "blue")

    def test_metadata_rejects_mixed_modules_and_inconsistent_option_definitions(self):
        self.candidate()
        self.candidate()
        original = outfits.read_state(self.root)
        for mutation in ("module", "schema", "expression", "edit_type", "target", "id"):
            with self.subTest(mutation=mutation):
                state = json.loads(json.dumps(original))
                if mutation == "module":
                    state["module"] = "expressions"
                elif mutation == "schema":
                    state["schema_version"] = "1.1"
                elif mutation == "expression":
                    state["assets"][0]["expression"] = "happy"
                elif mutation == "edit_type":
                    state["assets"][0]["edit_type"] = "replace"
                elif mutation == "target":
                    state["assets"][1]["target"] = "skirt"
                else:
                    state["assets"][0]["outfit_id"] = "../coat"
                outfits.write_state(self.root, state)
                self.assert_code("INVALID_PROJECT", outfits.read_state, self.root)
        outfits.write_state(self.root, original)

    def test_preview_compares_two_versions_face_and_garment_without_mutation(self):
        first, second = self.candidate(), self.candidate()
        self.candidate("coat_red", "red")
        before = (self.root / "run.json").read_bytes()
        first_bytes = (self.root / first["path"]).read_bytes()
        output = self.folder / "preview.png"
        result = outfits.make_preview(self.root, output, face_box=[34, 5, 62, 35],
                                      detail_box=[25, 38, 70, 95], outfit_id="coat_navy", background="light",
                                      labels={"source": "Original", "coat_navy": "Navy jacket"})
        self.assertEqual(result["asset_ids"], [first["id"], second["id"]])
        self.assertEqual(result["size"], [1080, 1020])
        with Image.open(output) as preview:
            self.assertEqual(preview.getpixel((0, 0)), (250, 250, 250))
            self.assertNotEqual(preview.crop((0, 770, 360, 1020)).tobytes(), preview.crop((360, 770, 720, 1020)).tobytes())
        self.assertEqual((self.root / "run.json").read_bytes(), before)
        self.assertEqual((self.root / first["path"]).read_bytes(), first_bytes)
        with self.assertRaises(FileExistsError):
            outfits.make_preview(self.root, output)

    def test_invalid_detail_box_or_empty_filter_does_not_create_preview(self):
        self.candidate()
        output = self.folder / "invalid.png"
        self.assert_code("INVALID_DETAIL_BOX", outfits.make_preview, self.root, output, detail_box=[0, 0, 200, 200])
        self.assert_code("NO_MATCHING_ASSETS", outfits.make_preview, self.root, output, outfit_id="missing")
        self.assertFalse(output.exists())

    def test_cli_records_unicode_prompt_and_failed_add_returns_saved_candidate(self):
        prompt = self.folder / "prompt.txt"
        prompt.write_text("只把外套改成深蓝，保留原表情。", encoding="utf-8")
        result = self.cli(SCRIPT, "add", "--project", self.root, "--outfit", "coat_navy", "--target", "外套面料", "--color", "深蓝色", "--image", self.source, "--prompt-file", prompt)
        self.assertEqual(result.returncode, 0, result.stderr)
        asset = json.loads(result.stdout)["asset"]
        self.assertEqual(asset["target"], "外套面料")
        self.assertEqual((self.root / asset["prompt_path"]).read_text(encoding="utf-8"), prompt.read_text(encoding="utf-8"))
        wrong = self.folder / "wrong.png"
        fixture(wrong, size=(48, 72))
        result = self.cli(SCRIPT, "add", "--project", self.root, "--outfit", "coat_red", "--target", "外套面料", "--color", "红色", "--image", wrong)
        self.assertEqual(result.returncode, 2)
        saved = json.loads(result.stdout)
        self.assertFalse(saved["passed"])
        self.assertTrue((self.root / saved["asset"]["path"]).exists())

    def test_package_runs_both_entrypoints_and_full_outfit_cli_outside_repo(self):
        package = self.folder / "plugin.zip"
        builder.build(REPO, package)
        installed = self.folder / "installed plugin"
        with zipfile.ZipFile(package) as archive:
            self.assertIsNone(archive.testzip())
            self.assertIn("lib/studio_core.py", archive.namelist())
            self.assertIn("skills/charakit-outfits/SKILL.md", archive.namelist())
            self.assertFalse(any(name.endswith(".pyc") for name in archive.namelist()))
            archive.extractall(installed)
        result = self.cli(installed / "skills/charakit-expressions/scripts/studio.py", "presets")
        self.assertEqual(result.returncode, 0, result.stderr)
        script = installed / "skills/charakit-outfits/scripts/studio.py"
        project = self.folder / "packaged outfit project"
        from test_quality import assessment
        assessment_file = self.folder / "synthetic-assessment.json"
        assessment_file.write_text(json.dumps(assessment(domain="garment_recolor")), encoding="utf-8")
        preview = project / "preview/packaged-preview.png"
        commands = [
            ("init", "--project", project, "--source", self.source, "--character", "packaged"),
            ("add", "--project", project, "--outfit", "coat_navy", "--target", "jacket", "--color", "navy", "--image", self.source),
            ("preview", "--project", project, "--outfit", "coat_navy", "--detail-box", 25, 38, 70, 95, "--output", preview),
            ("quality", "--project", project, "--asset", "coat_navy_v001", "--assessment-file", assessment_file, "--comparison", preview),
            ("deliver", "--project", project, "--asset", "coat_navy_v001"),
            ("review", "--project", project, "--asset", "coat_navy_v001", "--status", "accepted", "--note", "Synthetic workflow check"),
            ("export", "--project", project),
        ]
        for command in commands:
            result = self.cli(script, *command)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["manifest"]["asset_kind"], "full_character_outfit")

    def test_build_refuses_distribution_missing_shared_helper(self):
        clone = self.folder / "incomplete"
        shutil.copytree(REPO / "plugins/charakit", clone / "plugins/charakit")
        (clone / "plugins/charakit/lib/studio_core.py").unlink()
        output = self.folder / "broken.zip"
        with self.assertRaises(ValueError):
            builder.build(clone, output)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
