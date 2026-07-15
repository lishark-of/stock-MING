import hashlib
import importlib.util
import json
import plistlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "server/services/tauri_package_verifier.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("tauri_package_verifier", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TauriPackageVerifierTests(unittest.TestCase):
    @staticmethod
    def _write_app(app_path: Path) -> None:
        executable = app_path / "Contents/MacOS/stock_ming_command_center"
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_bytes(b"packaged executable")
        executable.chmod(0o755)
        with (app_path / "Contents/Info.plist").open("wb") as handle:
            plistlib.dump(
                {
                    "CFBundleIdentifier": "com.stockming.commandcenter",
                    "CFBundleShortVersionString": "3.0.0",
                    "CFBundleVersion": "3.0.0",
                    "CFBundleExecutable": executable.name,
                },
                handle,
            )

    def _write_evidence(self, module, project: Path, root: Path, *, screenshot_bytes: bytes = b"offline-ui") -> str:
        package_root = root / "desktop_runtime"
        package_root.mkdir(parents=True, exist_ok=True)
        app_path = project / module.FIXED_APP_RELATIVE
        dmg_path = project / module.FIXED_DMG_RELATIVE
        self._write_app(app_path)
        dmg_path.parent.mkdir(parents=True, exist_ok=True)
        dmg_path.write_bytes(b"disk image")
        app_hash = module._bundle_fingerprint(app_path)["sha256"]
        executable_hash = module._sha256_file(app_path / "Contents/MacOS/stock_ming_command_center")
        dmg_hash = module._sha256_file(dmg_path)
        artifact_hash = hashlib.sha256(
            "|".join((app_hash, dmg_hash, "com.stockming.commandcenter", "3.0.0")).encode("utf-8")
        ).hexdigest()
        screenshot = package_root / "offline_actual.png"
        screenshot.write_bytes(screenshot_bytes)
        screenshot_hash = module._sha256_file(screenshot)
        common = {
            "schema_version": "tauri_packaged_runtime_smoke.v1",
            "status": "tauri_packaged_runtime_smoke_passed",
            "local_packaged_runtime_evidence_ready": True,
            "head_full": "a" * 40,
            "build_head_full": "a" * 40,
            "build_executed": True,
            "production_package_complete": False,
            "contains_secret": False,
            "external_calls_triggered": False,
            "does_not_execute_trades": True,
            "app_path": module.FIXED_APP_RELATIVE.as_posix(),
            "dmg_path": module.FIXED_DMG_RELATIVE.as_posix(),
            "app_bundle_sha256": app_hash,
            "app_executable_sha256": executable_hash,
            "dmg_sha256": dmg_hash,
            "artifact_set_sha256": artifact_hash,
            "bundle_identifier": "com.stockming.commandcenter",
            "bundle_version": "3.0.0",
            "offline_screenshot_sha256": screenshot_hash,
            "dmg_checksum_verified": True,
            "codesign_verified": True,
            "artifacts_gitignored": True,
            "safe_config_log_evidence": True,
            "health_ready_during_launch": True,
            "backend_offline_packaged_ux_verified": True,
            "offline_notice_observed": True,
            "backend_offline_expected": True,
            "offline_backend_unavailable_observed": True,
        }
        (package_root / "tauri_packaged_runtime_online_smoke.json").write_text(
            json.dumps({**common, "backend_offline_expected": False, "offline_backend_unavailable_observed": False}),
            encoding="utf-8",
        )
        (package_root / "tauri_packaged_runtime_offline_smoke.json").write_text(
            json.dumps(common), encoding="utf-8"
        )
        (package_root / "tauri_build_receipt.json").write_text(
            json.dumps(
                {
                    "schema_version": "tauri_build_receipt.v1",
                    "build_executed": True,
                    "build_command": "cd desktop && npm run tauri build",
                    "head_full": "a" * 40,
                    "app_path": module.FIXED_APP_RELATIVE.as_posix(),
                    "dmg_path": module.FIXED_DMG_RELATIVE.as_posix(),
                    "app_bundle_sha256": app_hash,
                    "dmg_sha256": dmg_hash,
                    "artifact_set_sha256": artifact_hash,
                    "contains_secret": False,
                    "external_calls_triggered": False,
                }
            ),
            encoding="utf-8",
        )
        return screenshot_hash

    @staticmethod
    def _validation_patches(module, project: Path):
        smoke = SimpleNamespace(
            _read_bundle_identity=lambda _path: {
                "bundle_id": "com.stockming.commandcenter",
                "version": "3.0.0",
                "build_version": "3.0.0",
                "executable_name": module.FIXED_EXECUTABLE_NAME,
            }
        )
        return (
            patch.object(module, "PROJECT_ROOT", project),
            patch.object(module, "_smoke_module", return_value=smoke),
            patch.object(module, "_git_head_full", return_value="a" * 40),
        )

    def test_current_head_package_is_verified_and_manifest_is_bound(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            project.mkdir()
            root = project / ".stock_ming_3"
            self._write_evidence(module, project, root)
            patches = self._validation_patches(module, project)
            with patches[0], patches[1], patches[2]:
                result = module.validate_tauri_production_package(
                    root, expected_head_full="a" * 40, write_manifest=True
                )
            self.assertEqual(result["status"], "tauri_production_package_verified")
            self.assertTrue(result["production_package_complete"])
            self.assertFalse(result["developer_id_signing_verified"])
            self.assertFalse(result["notarization_ticket_detected"])
            self.assertTrue((root / "desktop_runtime/tauri_production_package_manifest.json").is_file())
            pointer = json.loads(
                (root / "desktop_runtime/tauri_production_package_pointer.json").read_text(encoding="utf-8")
            )
            self.assertTrue(pointer["immutable"])
            self.assertEqual(pointer["head_full"], "a" * 40)
            self.assertEqual(pointer["manifest_digest"], result["manifest_digest"])

    def test_changed_disk_artifact_blocks_promotion(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            project.mkdir()
            root = project / ".stock_ming_3"
            self._write_evidence(module, project, root)
            (project / module.FIXED_DMG_RELATIVE).write_bytes(b"tampered disk image")
            patches = self._validation_patches(module, project)
            with patches[0], patches[1], patches[2]:
                result = module.validate_tauri_production_package(root, expected_head_full="a" * 40)
            self.assertEqual(result["status"], "tauri_production_package_blocked")
            self.assertIn("online_dmg_sha256_not_recomputed_from_fixed_disk_target", result["blockers"])

    def test_alternate_paths_symlink_and_receipt_equal_artifact_forgery_are_rejected(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            project.mkdir()
            root = project / ".stock_ming_3"
            self._write_evidence(module, project, root)
            package_root = root / "desktop_runtime"
            online_path = package_root / "tauri_packaged_runtime_online_smoke.json"
            online = json.loads(online_path.read_text(encoding="utf-8"))
            online["app_path"] = str(project / "alternate.app")
            online_path.write_text(json.dumps(online), encoding="utf-8")
            patches = self._validation_patches(module, project)
            with patches[0], patches[1], patches[2]:
                alternate = module.validate_tauri_production_package(root, expected_head_full="a" * 40)
            self.assertIn("online_app_path_not_fixed_canonical_target", alternate["blockers"])

            self._write_evidence(module, project, root)
            forged = "f" * 64
            for name in (
                "tauri_packaged_runtime_online_smoke.json",
                "tauri_packaged_runtime_offline_smoke.json",
                "tauri_build_receipt.json",
            ):
                path = package_root / name
                value = json.loads(path.read_text(encoding="utf-8"))
                value["artifact_set_sha256"] = forged
                path.write_text(json.dumps(value), encoding="utf-8")
            patches = self._validation_patches(module, project)
            with patches[0], patches[1], patches[2]:
                artifact = module.validate_tauri_production_package(root, expected_head_full="a" * 40)
            self.assertIn(
                "online_artifact_set_sha256_not_recomputed_from_fixed_disk_target",
                artifact["blockers"],
            )

            self._write_evidence(module, project, root)
            dmg = project / module.FIXED_DMG_RELATIVE
            real_dmg = project / "real.dmg"
            real_dmg.write_bytes(dmg.read_bytes())
            dmg.unlink()
            dmg.symlink_to(real_dmg)
            patches = self._validation_patches(module, project)
            with patches[0], patches[1], patches[2]:
                symlink = module.validate_tauri_production_package(root, expected_head_full="a" * 40)
            self.assertIn("fixed_packaged_dmg_path_missing_or_aliased", symlink["blockers"])


if __name__ == "__main__":
    unittest.main()
