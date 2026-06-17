from __future__ import annotations

import builtins
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "skills" / "multi-agent-review" / "scripts" / "review_forge_runner.py"
spec = importlib.util.spec_from_file_location("review_forge_runner", SCRIPT_PATH)
runner = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(runner)


class ReviewForgeRunnerTests(unittest.TestCase):
    def test_fallback_yaml_preserves_scalar_list_items(self) -> None:
        real_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "yaml":
                raise ImportError("no yaml")
            return real_import(name, *args, **kwargs)

        config = """review_models:
  - reviewer-claude
  - reviewer-codex
  - reviewer-claude-2
"""
        with patch("builtins.__import__", side_effect=fake_import):
            parsed = runner.parse_simple_yaml(config)

        self.assertEqual(parsed["review_models"], ["reviewer-claude", "reviewer-codex", "reviewer-claude-2"])

    def test_run_verify_does_not_force_dangerous_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            feature_dir = repo / ".review-forge" / "artifacts" / "feature"
            feature_dir.mkdir(parents=True)
            (feature_dir / "summary.md").write_text("- [x] `RF-002`\n", encoding="utf-8")
            config = {
                "verify_model": "verifier",
                "timeout_seconds": 1,
                "models": {"verifier": {"cli": "codex"}},
            }
            calls: list[dict[str, object]] = []

            def fake_run_model(*args: object, **kwargs: object) -> object:
                calls.append(kwargs)
                return runner.RunResult("verifier", "verify", 0, "verified", "", "cmd")

            with patch.object(runner, "collect_review_diff", return_value=("diff", "scope")):
                with patch.object(runner, "read_prompt", return_value="{{diff}}"):
                    with patch.object(runner, "run_model", side_effect=fake_run_model):
                        runner.run_verify(repo, config, "feature")

            self.assertEqual(calls, [{}])
            self.assertEqual((feature_dir / "verify.md").read_text(encoding="utf-8"), "verified\n")

    def test_default_verifier_is_not_dangerous(self) -> None:
        template = runner.default_config_template()
        config = runner.parse_simple_yaml(template)

        self.assertNotIn("dangerous", config["models"]["verifier-codex"])
        self.assertIs(config["config_ready"], False)

    def test_default_config_template_has_chinese_guidance_comments(self) -> None:
        template = runner.default_config_template()

        self.assertIn("# 配置确认开关", template)
        self.assertIn("# Review 阶段使用的模型 ID 列表", template)
        self.assertIn("# 修复阶段使用的模型 ID", template)
        self.assertIn("# 模型定义表", template)
        self.assertIn("# env：可选", template)
        self.assertIn("ANTHROPIC_BASE_URL", template)

    def test_load_config_refuses_unconfirmed_default_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            config_dir = repo / ".review-forge"
            config_dir.mkdir()
            (config_dir / "config.local.yaml").write_text(runner.default_config_template(), encoding="utf-8")

            with self.assertRaises(SystemExit):
                runner.load_config(repo)

    def test_load_config_allows_unconfirmed_config_for_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            config_dir = repo / ".review-forge"
            config_dir.mkdir()
            (config_dir / "config.local.yaml").write_text(runner.default_config_template(), encoding="utf-8")

            config = runner.load_config(repo, require_ready=False)

        self.assertIs(config["config_ready"], False)

    def test_check_config_does_not_use_dangerous_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            config = {
                "config_ready": False,
                "review_models": ["reviewer"],
                "synthesize_model": "reviewer",
                "fix_model": "fixer",
                "verify_model": "reviewer",
                "timeout_seconds": 1,
                "models": {
                    "reviewer": {"cli": "codex"},
                    "fixer": {"cli": "codex", "dangerous": True},
                },
            }
            calls: list[dict[str, object]] = []

            def fake_run_model(*args: object, **kwargs: object) -> object:
                calls.append(kwargs)
                model_id = args[2]
                return runner.RunResult(str(model_id), "check-config", 0, "OK", "", "cmd")

            with patch.object(runner, "run_model", side_effect=fake_run_model):
                runner.run_check_config(repo, config)

        self.assertEqual(len(calls), 2)
        self.assertTrue(all(call.get("use_config_dangerous") is False for call in calls))

    def test_working_scope_includes_staged_tracked_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            tracked = repo / "tracked.txt"
            tracked.write_text("one\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
            tracked.write_text("two\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)

            diff, _ = runner.collect_review_diff(repo, "working", None)

        self.assertIn("+two", diff)

    def test_resolve_review_scope_on_main_uses_working_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            (repo / "tracked.txt").write_text("one\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

            scope, base = runner.resolve_review_scope(repo, None, None)

        self.assertEqual((scope, base), ("working", None))

    def test_resolve_review_scope_on_feature_branch_uses_main_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            (repo / "tracked.txt").write_text("one\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "branch", "-M", "main"], cwd=repo, check=True)
            subprocess.run(["git", "switch", "-c", "feature"], cwd=repo, check=True, capture_output=True)

            scope, base = runner.resolve_review_scope(repo, None, None)

        self.assertEqual((scope, base), (None, "main"))

    def test_explicit_review_scope_is_not_overridden(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            self.assertEqual(runner.resolve_review_scope(repo, "working", None), ("working", None))
            self.assertEqual(runner.resolve_review_scope(repo, None, "origin/main"), (None, "origin/main"))

    def test_collect_untracked_files_rejects_paths_outside_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            outside = root / "outside.txt"
            outside.write_text("secret", encoding="utf-8")

            def fake_git(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
                return subprocess.CompletedProcess(["git"], 0, "../outside.txt\n", "")

            with patch.object(runner, "git", side_effect=fake_git):
                output = runner.collect_untracked_files(repo)

            self.assertNotIn("secret", output)
            self.assertIn("Skipped: path is outside repository.", output)

    def test_ensure_local_ignore_uses_git_exclude_for_worktrees(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            (repo / ".git").write_text("gitdir: ../git/worktrees/repo\n", encoding="utf-8")
            exclude = Path(tmp) / "git" / "worktrees" / "repo" / "info" / "exclude"

            def fake_git(_repo: Path, args: list[str], check: bool) -> subprocess.CompletedProcess[str]:
                self.assertEqual(args, ["rev-parse", "--git-path", "info/exclude"])
                return subprocess.CompletedProcess(["git"], 0, f"{exclude}\n", "")

            with patch.object(runner, "git", side_effect=fake_git):
                runner.ensure_local_ignore(repo)

            self.assertFalse((repo / ".gitignore").exists())
            exclude_text = exclude.read_text(encoding="utf-8")
            self.assertIn(".review-forge/", exclude_text)

    def test_fix_reuses_persisted_review_base_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            feature_dir = repo / ".review-forge" / "artifacts" / "feature"
            feature_dir.mkdir(parents=True)
            (feature_dir / "summary.md").write_text("- [x] `RF-005`\n", encoding="utf-8")
            runner.write_review_scope(feature_dir, None, "main")
            config = {
                "config_ready": True,
                "fix_model": "fixer",
                "timeout_seconds": 1,
                "models": {"fixer": {"cli": "codex", "dangerous": True}},
            }
            calls: list[tuple[object, object]] = []

            def fake_collect(_repo: Path, scope: str | None, base: str | None) -> tuple[str, str]:
                calls.append((scope, base))
                return ("diff", "scope")

            with patch.object(runner, "collect_review_diff", side_effect=fake_collect):
                with patch.object(runner, "read_prompt", return_value="{{selected_items}}"):
                    with patch.object(runner, "run_model", return_value=runner.RunResult("fixer", "fix", 0, "fixed", "", "cmd")):
                        runner.run_fix(repo, config, "feature")

            self.assertEqual(calls, [(None, "main")])

    def test_review_persists_base_scope_for_later_phases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            config = {
                "config_ready": True,
                "review_models": ["reviewer"],
                "timeout_seconds": 1,
                "models": {"reviewer": {"cli": "codex"}},
            }
            with patch.object(runner, "collect_review_diff", return_value=("diff", "main...HEAD plus working tree diff")):
                with patch.object(runner, "read_prompt", return_value="{{diff}}"):
                    with patch.object(runner, "run_model", return_value=runner.RunResult("reviewer", "review", 0, "reviewed", "", "cmd")):
                        runner.run_review(repo, config, "feature", None, "main")

            feature_dir = repo / ".review-forge" / "artifacts" / "feature"
            self.assertEqual(runner.read_review_scope(feature_dir), (None, "main"))


if __name__ == "__main__":
    unittest.main()
