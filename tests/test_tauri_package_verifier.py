import hashlib
import importlib.util
import json
import os
import plistlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "server/services/tauri_package_verifier.py"
BUILD_SCRIPT_PATH = ROOT / "scripts/tauri_production_build.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("tauri_package_verifier", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_build_script():
    spec = importlib.util.spec_from_file_location("tauri_production_build", BUILD_SCRIPT_PATH)
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
        self.policy = {
            "schema_version": module.RELEASE_IDENTITY_POLICY_SCHEMA,
            "approved_for_distribution": True,
            "team_identifier": "TEAM123456",
            "developer_id_application_common_name": "Developer ID Application: Example Corp (TEAM123456)",
            "certificate_sha256": "c" * 64,
        }
        self.policy["policy_digest"] = module._digest(
            {key: value for key, value in self.policy.items() if key != "policy_digest"}
        )
        build_entry = project / module.BUILD_ENTRY_RELATIVE
        tauri_config = project / module.TAURI_CONFIG_RELATIVE
        build_entry.parent.mkdir(parents=True, exist_ok=True)
        tauri_config.parent.mkdir(parents=True, exist_ok=True)
        build_entry.write_bytes(b"trusted production build entry")
        tauri_config.write_bytes(b"trusted tauri config")
        self.source_binding = {
            "source_archive_sha256": "1" * 64,
            "build_entry_sha256": module._sha256_file(build_entry),
            "tauri_config_sha256": module._sha256_file(tauri_config),
        }
        unsigned_provenance = {
            "schema_version": module.PROVENANCE_SCHEMA,
            "head_full": "a" * 40,
            **self.source_binding,
            "release_identity_policy_digest": self.policy["policy_digest"],
            "build_session_nonce_sha256": "4" * 64,
            "contains_secret": False,
            "external_calls_triggered": False,
        }
        provenance = {**unsigned_provenance, "provenance_digest": module._digest(unsigned_provenance)}
        provenance_path = app_path / module.PROVENANCE_RELATIVE
        provenance_path.parent.mkdir(parents=True, exist_ok=True)
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
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
            "developer_id_signing_verified": True,
            "notarization_ticket_detected": True,
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
        build_material = {
                    "schema_version": module.BUILD_RECEIPT_SCHEMA,
                    "build_executed": True,
                    "build_command": module.PRODUCTION_BUILD_COMMAND,
                    "head_full": "a" * 40,
                    "head_binding_valid": True,
                    "app_path": module.FIXED_APP_RELATIVE.as_posix(),
                    "dmg_path": module.FIXED_DMG_RELATIVE.as_posix(),
                    "app_bundle_sha256": app_hash,
                    "dmg_sha256": dmg_hash,
                    "artifact_set_sha256": artifact_hash,
                    "source_archive_sha256": self.source_binding["source_archive_sha256"],
                    "release_identity_policy_digest": self.policy["policy_digest"],
                    "provenance_digest": provenance["provenance_digest"],
                    "build_session_nonce_sha256": "4" * 64,
                    "contains_secret": False,
                    "external_calls_triggered": False,
                    "does_not_execute_trades": True,
                    "blockers": [],
                }
        (package_root / "tauri_build_receipt.json").write_text(
            json.dumps({**build_material, "receipt_digest": module._digest(build_material)}),
            encoding="utf-8",
        )
        return screenshot_hash

    def _validation_patches(self, module, project: Path):
        smoke = SimpleNamespace(
            _read_bundle_identity=lambda _path: {
                "bundle_id": "com.stockming.commandcenter",
                "version": "3.0.0",
                "build_version": "3.0.0",
                "executable_name": module.FIXED_EXECUTABLE_NAME,
            }
        )
        distribution = {
            "schema_version": "tauri_macos_distribution_verification.v1",
            "head_full": "a" * 40,
            "artifact_set_sha256": "",
            "app_bundle_sha256": "",
            "app_executable_sha256": "",
            "dmg_sha256": "",
            "bundle_identifier": "com.stockming.commandcenter",
            "bundle_version": "3.0.0",
            "app_codesign_verified": True,
            "developer_id_application_verified": True,
            "team_identifier_present": True,
            "app_certificate_fingerprint_verified": True,
            "hardened_runtime_verified": True,
            "dmg_codesign_verified": True,
            "dmg_developer_id_application_verified": True,
            "dmg_team_identifier_verified": True,
            "dmg_certificate_fingerprint_verified": True,
            "developer_id_signing_verified": True,
            "app_gatekeeper_accepted": True,
            "app_notarization_ticket_valid": True,
            "dmg_checksum_verified": True,
            "dmg_gatekeeper_accepted": True,
            "dmg_notarization_ticket_valid": True,
            "dmg_payload_verification": {
                "dmg_attached_readonly": True,
                "dmg_mount_readonly_observed": True,
                "single_mounted_app_detected": True,
                "mounted_app_bundle_hash_matches": True,
                "mounted_app_executable_hash_matches": True,
                "mounted_app_identity_matches": True,
                "mounted_app_codesign_verified": True,
                "mounted_app_developer_id_verified": True,
                "mounted_app_team_identifier_verified": True,
                "mounted_app_certificate_verified": True,
                "mounted_app_hardened_runtime_verified": True,
                "mounted_app_provenance_matches": True,
                "mounted_app_gatekeeper_accepted": True,
                "mounted_app_notarization_ticket_valid": True,
                "dmg_detached": True,
                "payload_ready": True,
                "blockers": [],
            },
            "distribution_ready": True,
            "blockers": [],
        }

        def verified_distribution(*, measured, provenance_digest, policy, **_kwargs):
            return {
                **distribution,
                "artifact_set_sha256": measured["artifact_set_sha256"],
                "app_bundle_sha256": measured["app_bundle_sha256"],
                "app_executable_sha256": measured["app_executable_sha256"],
                "dmg_sha256": measured["dmg_sha256"],
                "bundle_identifier": measured["bundle_identifier"],
                "bundle_version": measured["bundle_version"],
                "release_identity_policy_digest": policy["policy_digest"],
                "provenance_digest": provenance_digest,
            }
        return (
            patch.object(module, "PROJECT_ROOT", project),
            patch.object(module, "_smoke_module", return_value=smoke),
            patch.object(module, "_git_head_full", return_value="a" * 40),
            patch.object(module, "_load_release_identity_policy", return_value=self.policy),
            patch.object(module, "_current_source_binding", return_value=self.source_binding),
            patch.object(module, "_macos_distribution_verification", side_effect=verified_distribution),
        )

    def test_current_head_package_is_verified_and_manifest_is_bound(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            project.mkdir()
            root = project / ".stock_ming_3"
            self._write_evidence(module, project, root)
            patches = self._validation_patches(module, project)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                result = module.validate_tauri_production_package(
                    root, expected_head_full="a" * 40, write_manifest=True
                )
            self.assertEqual(result["status"], "tauri_production_package_verified")
            self.assertTrue(result["production_package_complete"])
            self.assertTrue(result["developer_id_signing_verified"])
            self.assertTrue(result["notarization_ticket_detected"])
            self.assertTrue(result["app_gatekeeper_accepted"])
            self.assertTrue(result["dmg_gatekeeper_accepted"])
            self.assertTrue((root / "desktop_runtime/tauri_production_package_manifest.json").is_file())
            pointer = json.loads(
                (root / "desktop_runtime/tauri_production_package_pointer.json").read_text(encoding="utf-8")
            )
            self.assertTrue(pointer["immutable"])
            self.assertEqual(pointer["head_full"], "a" * 40)
            self.assertEqual(pointer["manifest_digest"], result["manifest_digest"])
            patches = self._validation_patches(module, project)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patch.object(
                module,
                "_macos_distribution_verification",
                side_effect=AssertionError("GET/readback must not execute macOS distribution tools"),
            ), patch.object(
                module,
                "_run_distribution_check",
                side_effect=AssertionError("GET/readback must not spawn system validation"),
            ), patch.object(
                module,
                "_verify_mounted_dmg_payload",
                side_effect=AssertionError("GET/readback must not mount DMG"),
            ):
                readback = module.validate_tauri_production_package(
                    root,
                    expected_head_full="a" * 40,
                    write_manifest=False,
                )
            self.assertTrue(readback["production_package_complete"])
            self.assertEqual(
                readback["macos_distribution_evidence_source"],
                "same_head_formal_manifest_readback",
            )
            manifest_path = root / "desktop_runtime/tauri_production_package_manifest.json"
            pointer_path = root / "desktop_runtime/tauri_production_package_pointer.json"
            forged = json.loads(manifest_path.read_text(encoding="utf-8"))
            forged.pop("manifest_digest")
            forged["macos_distribution_verification"]["developer_id_signing_verified"] = False
            forged_digest = module._digest(forged)
            forged["manifest_digest"] = forged_digest
            manifest_path.write_text(json.dumps(forged), encoding="utf-8")
            pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
            pointer["manifest_digest"] = forged_digest
            pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
            patches = self._validation_patches(module, project)
            with patches[0], patches[1], patches[2], patches[3], patches[4]:
                rejected = module.validate_tauri_production_package(
                    root, expected_head_full="a" * 40, write_manifest=False
                )
            self.assertFalse(rejected["production_package_complete"])
            self.assertIn(
                "formal_package_distribution_developer_id_signing_verified_not_attested",
                rejected["blockers"],
            )
            forged.pop("manifest_digest")
            forged["macos_distribution_verification"]["developer_id_signing_verified"] = True
            forged["macos_distribution_verification"]["dmg_payload_verification"][
                "mounted_app_certificate_verified"
            ] = False
            forged_digest = module._digest(forged)
            forged["manifest_digest"] = forged_digest
            manifest_path.write_text(json.dumps(forged), encoding="utf-8")
            pointer["manifest_digest"] = forged_digest
            pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
            patches = self._validation_patches(module, project)
            with patches[0], patches[1], patches[2], patches[3], patches[4]:
                rejected_payload = module.validate_tauri_production_package(
                    root, expected_head_full="a" * 40, write_manifest=False
                )
            self.assertIn(
                "formal_package_distribution_dmg_payload_mounted_app_certificate_verified_not_attested",
                rejected_payload["blockers"],
            )

    def test_changed_disk_artifact_blocks_promotion(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            project.mkdir()
            root = project / ".stock_ming_3"
            self._write_evidence(module, project, root)
            (project / module.FIXED_DMG_RELATIVE).write_bytes(b"tampered disk image")
            patches = self._validation_patches(module, project)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
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
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
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
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
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
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
                symlink = module.validate_tauri_production_package(root, expected_head_full="a" * 40)
            self.assertIn("fixed_packaged_dmg_path_missing_or_aliased", symlink["blockers"])

    def test_distribution_verifier_fails_closed_without_developer_id_or_dmg_ticket(self) -> None:
        module = _load_module()
        commands = []

        def run(command, *, timeout):
            commands.append((command, timeout))
            if command[:2] == [module.SYSTEM_XCRUN, "stapler"] and command[-1].endswith(".dmg"):
                return SimpleNamespace(returncode=1, stdout="", stderr="")
            if command[0] == module.SYSTEM_SPCTL:
                return SimpleNamespace(returncode=0, stdout="accepted\nsource=Notarized Developer ID", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        measured = {
            "artifact_set_sha256": "1" * 64,
            "app_bundle_sha256": "2" * 64,
            "app_executable_sha256": "4" * 64,
            "dmg_sha256": "3" * 64,
            "bundle_identifier": "com.stockming.commandcenter",
            "bundle_version": "3.0.0",
        }
        with patch.object(module.sys, "platform", "darwin"), patch.object(
            module, "_run_distribution_check", side_effect=run
        ), patch.object(
            module,
            "_codesign_identity_observation",
            return_value={
                "codesign_verified": False,
                "common_name_matches_policy": False,
                "team_identifier_matches_policy": False,
                "certificate_fingerprint_matches_policy": False,
                "hardened_runtime_verified": False,
            },
        ), patch.object(
            module,
            "_verify_mounted_dmg_payload",
            return_value={
                "payload_ready": False,
                "blockers": ["dmg_payload_mounted_app_bundle_hash_matches_failed"],
            },
        ):
            result = module._macos_distribution_verification(
                app_path=Path("Example.app"),
                dmg_path=Path("Example.dmg"),
                head_full="a" * 40,
                measured=measured,
                provenance_digest="5" * 64,
                policy={"policy_digest": "6" * 64},
            )
        self.assertFalse(result["distribution_ready"])
        self.assertFalse(result["developer_id_signing_verified"])
        self.assertIn("macos_distribution_developer_id_application_verified_failed", result["blockers"])
        self.assertIn("macos_distribution_team_identifier_present_failed", result["blockers"])
        self.assertIn("macos_distribution_app_certificate_fingerprint_verified_failed", result["blockers"])
        self.assertIn("macos_distribution_dmg_codesign_verified_failed", result["blockers"])
        self.assertIn("macos_distribution_hardened_runtime_verified_failed", result["blockers"])
        self.assertIn("macos_distribution_dmg_notarization_ticket_valid_failed", result["blockers"])
        self.assertIn("dmg_payload_mounted_app_bundle_hash_matches_failed", result["blockers"])
        self.assertTrue(any(command[0][0] == module.SYSTEM_HDIUTIL for command in commands))

    def test_production_build_refuses_dirty_tree_and_uses_trusted_absolute_entry(self) -> None:
        module = _load_build_script()
        tauri_config = json.loads((ROOT / "desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
        self.assertNotEqual(tauri_config["bundle"]["macOS"].get("signingIdentity"), "-")
        self.assertTrue(tauri_config["bundle"]["macOS"]["hardenedRuntime"])
        policy = {
            "team_identifier": "TEAM123456",
            "developer_id_application_common_name": "Developer ID Application: Example Corp (TEAM123456)",
            "certificate_sha256": "c" * 64,
            "policy_digest": "d" * 64,
        }
        with patch.dict(os.environ, {"APPLE_SIGNING_IDENTITY": "unapproved"}, clear=True):
            self.assertIsNone(module._controlled_build_env(policy))
        with patch.dict(os.environ, {"APPLE_TEAM_ID": "OTHER12345"}, clear=True):
            self.assertIsNone(module._controlled_build_env(policy))
        with patch.dict(os.environ, {"TAURI_CONFIG": "/tmp/attacker.json"}, clear=True):
            controlled = module._controlled_build_env(policy)
            self.assertIsNotNone(controlled)
            self.assertNotIn("TAURI_CONFIG", controlled)
        with patch.object(module.platform, "system", return_value="Darwin"), patch.object(
            module, "_load_release_identity_policy", return_value=policy
        ), patch.object(module, "_repository_clean_and_head", return_value=""):
            self.assertEqual(module.main(), 5)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            node = temp / "node"
            npm_cli = temp / "npm-cli.js"
            node.write_text("node", encoding="utf-8")
            npm_cli.write_text("npm", encoding="utf-8")
            captured = {}

            def execute(command, **kwargs):
                captured["command"] = command
                captured["env"] = kwargs["env"]
                overlay = json.loads(Path(command[-1]).read_text(encoding="utf-8"))
                captured["overlay"] = overlay
                provenance_source = next(iter(overlay["bundle"]["resources"]))
                captured["provenance"] = json.loads(Path(provenance_source).read_text(encoding="utf-8"))
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch.dict(os.environ, {"HOME": str(temp)}, clear=True), patch.object(
                module.platform, "system", return_value="Darwin"
            ), patch.object(module, "_load_release_identity_policy", return_value=policy), patch.object(
                module, "_repository_clean_and_head", return_value="a" * 40
            ), patch.object(
                module,
                "_current_source_binding",
                return_value={
                    "source_archive_sha256": "1" * 64,
                    "build_entry_sha256": "2" * 64,
                    "tauri_config_sha256": "3" * 64,
                },
            ), patch.object(module, "_matching_keychain_identity", return_value=True), patch.object(
                module, "_remove_fixed_old_artifacts", return_value=True
            ), patch.object(module, "SYSTEM_NODE", node), patch.object(
                module, "NPM_CLI", npm_cli
            ), patch.object(module.secrets, "token_bytes", return_value=b"n" * 32), patch.object(
                module.subprocess, "run", side_effect=execute
            ), patch.object(
                module, "_read_embedded_provenance", side_effect=lambda _path: captured["provenance"]
            ), patch.object(
                module, "record_tauri_build_receipt", return_value={"build_executed": True}
            ):
                self.assertEqual(module.main(), 0)
            self.assertEqual(captured["command"][:2], [str(node), str(npm_cli)])
            self.assertEqual(captured["command"][2:6], ["run", "tauri", "--", "build"])
            self.assertTrue(
                captured["env"]["PATH"].startswith(
                    "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:"
                )
            )
            self.assertEqual(
                captured["overlay"]["bundle"]["macOS"]["signingIdentity"],
                policy["developer_id_application_common_name"],
            )
            self.assertEqual(
                next(iter(captured["overlay"]["bundle"]["resources"].values())),
                "production/command-center-build-provenance.json",
            )

    def test_posthoc_receipt_relabel_with_wrong_nonce_is_rejected_without_overwrite(self) -> None:
        module = _load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            project.mkdir()
            root = project / ".stock_ming_3"
            self._write_evidence(module, project, root)
            receipt_path = root / "desktop_runtime/tauri_build_receipt.json"
            before = receipt_path.read_bytes()
            smoke = SimpleNamespace(
                _read_bundle_identity=lambda _path: {
                    "bundle_id": "com.stockming.commandcenter",
                    "version": "3.0.0",
                    "build_version": "3.0.0",
                    "executable_name": module.FIXED_EXECUTABLE_NAME,
                }
            )
            with patch.object(module, "PROJECT_ROOT", project), patch.object(
                module, "_smoke_module", return_value=smoke
            ), patch.object(module, "_git_head_full", return_value="a" * 40), patch.object(
                module, "_load_release_identity_policy", return_value=self.policy
            ), patch.object(
                module, "_current_source_binding", return_value=self.source_binding
            ):
                rejected = module.record_tauri_build_receipt(
                    root,
                    head_full="a" * 40,
                    build_session_nonce=(b"wrong nonce".ljust(32, b"x")).hex(),
                )
            self.assertFalse(rejected["build_executed"])
            self.assertIn("tauri_build_receipt_session_nonce_invalid", rejected["blockers"])
            self.assertEqual(receipt_path.read_bytes(), before)

    def test_production_build_removes_only_fixed_old_targets_and_rejects_alias(self) -> None:
        module = _load_build_script()
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            app = project / module.FIXED_APP_RELATIVE
            dmg = project / module.FIXED_DMG_RELATIVE
            app.mkdir(parents=True)
            (app / "old").write_bytes(b"old")
            dmg.parent.mkdir(parents=True, exist_ok=True)
            dmg.write_bytes(b"old")
            with patch.object(module, "PROJECT_ROOT", project):
                self.assertTrue(module._remove_fixed_old_artifacts())
            self.assertFalse(app.exists())
            self.assertFalse(dmg.exists())

            target = project / "outside.dmg"
            target.write_bytes(b"keep")
            dmg.symlink_to(target)
            with patch.object(module, "PROJECT_ROOT", project):
                self.assertFalse(module._remove_fixed_old_artifacts())
            self.assertTrue(target.is_file())

            project2 = Path(temp_dir) / "project2"
            outside = Path(temp_dir) / "outside"
            project2.mkdir()
            outside_desktop = outside / "desktop"
            outside_app = outside_desktop / module.FIXED_APP_RELATIVE.relative_to("desktop")
            outside_app.mkdir(parents=True)
            (outside_app / "keep").write_bytes(b"keep")
            (project2 / "desktop").symlink_to(outside_desktop)
            with patch.object(module, "PROJECT_ROOT", project2):
                self.assertFalse(module._remove_fixed_old_artifacts())
            self.assertTrue((outside_app / "keep").is_file())

    def test_codesign_identity_requires_exact_team_common_name_and_leaf_fingerprint(self) -> None:
        module = _load_module()
        policy = {
            "team_identifier": "TEAM123456",
            "developer_id_application_common_name": "Developer ID Application: Approved (TEAM123456)",
            "certificate_sha256": "f" * 64,
        }

        def run(command, *, timeout):
            del timeout
            if "--extract-certificates" in command:
                prefix = command[command.index("--extract-certificates") + 1]
                Path(f"{prefix}0").write_bytes(b"wrong certificate")
                return SimpleNamespace(
                    returncode=0,
                    stdout="",
                    stderr=(
                        "Authority=Developer ID Application: Other (OTHER12345)\n"
                        "TeamIdentifier=OTHER12345\nflags=0x10000(runtime)\n"
                    ),
                )
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch.object(module, "_run_distribution_check", side_effect=run):
            observed = module._codesign_identity_observation(
                Path("Example.app"), policy=policy, require_hardened_runtime=True
            )
        self.assertTrue(observed["codesign_verified"])
        self.assertFalse(observed["common_name_matches_policy"])
        self.assertFalse(observed["team_identifier_matches_policy"])
        self.assertFalse(observed["certificate_fingerprint_matches_policy"])
        self.assertTrue(observed["hardened_runtime_verified"])

    def test_outer_app_and_dmg_both_require_the_same_approved_identity(self) -> None:
        module = _load_module()
        seen = []

        def identity(path, **_kwargs):
            seen.append(str(path))
            return {
                "codesign_verified": True,
                "common_name_matches_policy": True,
                "team_identifier_matches_policy": True,
                "certificate_fingerprint_matches_policy": True,
                "hardened_runtime_verified": True,
            }

        measured = {
            "artifact_set_sha256": "1" * 64,
            "app_bundle_sha256": "2" * 64,
            "app_executable_sha256": "3" * 64,
            "dmg_sha256": "4" * 64,
            "bundle_identifier": "com.stockming.commandcenter",
            "bundle_version": "3.0.0",
        }
        passed = SimpleNamespace(
            returncode=0,
            stdout="accepted\nsource=Notarized Developer ID\n",
            stderr="",
        )
        with patch.object(module.sys, "platform", "darwin"), patch.object(
            module, "_codesign_identity_observation", side_effect=identity
        ), patch.object(module, "_run_distribution_check", return_value=passed), patch.object(
            module, "_verify_mounted_dmg_payload", return_value={"payload_ready": True, "blockers": []}
        ):
            result = module._macos_distribution_verification(
                app_path=Path("Exact.app"),
                dmg_path=Path("Exact.dmg"),
                head_full="a" * 40,
                measured=measured,
                provenance_digest="5" * 64,
                policy={"policy_digest": "6" * 64},
            )
        self.assertEqual(seen, ["Exact.app", "Exact.dmg"])
        self.assertTrue(result["developer_id_signing_verified"])

    def test_v1_signing_fact_rejects_self_claimed_online_smoke(self) -> None:
        from server.services import v1_closeout_service

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "evidence"
            package_root = root / "desktop_runtime"
            package_root.mkdir(parents=True)
            (package_root / "tauri_packaged_runtime_online_smoke.json").write_text(
                json.dumps(
                    {
                        "developer_id_signing_verified": True,
                        "notarization_ticket_detected": True,
                    }
                ),
                encoding="utf-8",
            )
            blocked = {
                "production_package_complete": False,
                "developer_id_signing_verified": False,
                "notarization_ticket_detected": False,
                "app_gatekeeper_accepted": False,
                "dmg_gatekeeper_accepted": False,
            }
            with patch.object(
                v1_closeout_service,
                "validate_tauri_production_package",
                return_value=blocked,
            ):
                _rows, facts, _context = v1_closeout_service._build_version_rows(
                    root,
                    expected_head_full="a" * 40,
                )
            self.assertFalse(facts["desktop_production_package"])
            self.assertFalse(facts["developer_signing_notarization"])


if __name__ == "__main__":
    unittest.main()
