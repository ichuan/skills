from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "skills" / "iterative-code-review" / "scripts" / "prepare_review.py"
SKILL_PATH = ROOT / "skills" / "iterative-code-review" / "SKILL.md"


def load_prepare_review_module():
    if not SCRIPT_PATH.exists():
        raise AssertionError(f"missing review preparation script: {SCRIPT_PATH}")
    spec = importlib.util.spec_from_file_location("prepare_review", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def git_output(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def valid_scope(repo: Path | str = "/tmp/repo", **overrides: object) -> dict[str, object]:
    scope: dict[str, object] = {
        "repo": str(repo),
        "branch": "main",
        "run_id": "test-run",
        "iteration": 1,
        "mode": "review-only",
        "verification_policy": "sandboxed",
        "approved_commands": [],
        "base": None,
        "includes": ["committed", "staged", "unstaged", "untracked"],
        "untracked_count": 0,
        "committed_branch_diff_verified": False,
        "scope_limitation": None,
        "scope_limitations": [],
        "scope_complete": True,
        "scope_fingerprint": "0" * 64,
    }
    scope.update(overrides)
    return scope


class IterativeCodeReviewSkillTests(unittest.TestCase):
    def test_prepare_review_artifacts_are_private_under_permissive_umask(self) -> None:
        module = load_prepare_review_module()

        previous_umask = os.umask(0o002)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp) / "repo"
                repo.mkdir()
                git(repo, "init")
                git(repo, "config", "user.email", "test@example.com")
                git(repo, "config", "user.name", "Test")
                (repo / "README.md").write_text("fixture\n", encoding="utf-8")
                git(repo, "add", ".")
                git(repo, "commit", "-m", "base")

                source = repo / "nested" / "untracked.txt"
                source.parent.mkdir()
                source.write_text("private snapshot\n", encoding="utf-8")
                source.chmod(0o664)

                artifact_root = module.artifact_root(repo)
                artifact_root.mkdir()
                artifact_root.chmod(0o777)
                other_run = artifact_root / "other-run"
                other_run.mkdir()
                other_file = other_run / "keep-mode.txt"
                other_file.write_text("unrelated\n", encoding="utf-8")
                other_run.chmod(0o775)
                other_file.chmod(0o664)

                run_root = artifact_root / "private-run"
                existing_artifact_dir = run_root / "iteration-1"
                for directory in (
                    run_root,
                    existing_artifact_dir,
                    existing_artifact_dir / "prompts",
                    existing_artifact_dir / "results",
                    existing_artifact_dir / "logs",
                ):
                    directory.mkdir()
                    directory.chmod(0o775)
                existing_approval = existing_artifact_dir / "approved-high-impact.json"
                existing_approval.write_text('["stale"]\n', encoding="utf-8")
                existing_approval.chmod(0o664)

                repo_mode = repo.stat().st_mode & 0o777
                git_mode = (repo / ".git").stat().st_mode & 0o777

                results = [
                    module.prepare_review(
                        repo=repo,
                        run_id="private-run",
                        iteration=iteration,
                        base=None,
                        mode="review-only",
                        task_contract="",
                    )
                    for iteration in (1, 2)
                ]

                self.assertEqual(run_root.stat().st_mode & 0o777, 0o700)
                self.assertEqual(artifact_root.stat().st_mode & 0o777, 0o700)
                for result in results:
                    artifact_dir = Path(result["artifact_dir"])
                    for directory in (path for path in artifact_dir.rglob("*") if path.is_dir()):
                        self.assertEqual(directory.stat().st_mode & 0o777, 0o700, directory)
                    self.assertEqual(artifact_dir.stat().st_mode & 0o777, 0o700)
                    for artifact_file in (path for path in artifact_dir.rglob("*") if path.is_file()):
                        self.assertEqual(artifact_file.stat().st_mode & 0o777, 0o600, artifact_file)

                self.assertEqual(source.stat().st_mode & 0o777, 0o664)
                self.assertEqual(repo.stat().st_mode & 0o777, repo_mode)
                self.assertEqual((repo / ".git").stat().st_mode & 0o777, git_mode)
                self.assertEqual(other_run.stat().st_mode & 0o777, 0o775)
                self.assertEqual(other_file.stat().st_mode & 0o777, 0o664)
        finally:
            os.umask(previous_umask)

    def test_prepare_review_rejects_artifact_root_symlink_and_file(self) -> None:
        module = load_prepare_review_module()

        for root_kind in ("symlink", "file"):
            with self.subTest(root_kind=root_kind), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp) / "repo"
                repo.mkdir()
                git(repo, "init")
                git(repo, "config", "user.email", "test@example.com")
                git(repo, "config", "user.name", "Test")
                (repo / "README.md").write_text("fixture\n", encoding="utf-8")
                git(repo, "add", ".")
                git(repo, "commit", "-m", "base")

                root = module.artifact_root(repo)
                if root_kind == "symlink":
                    target = Path(tmp) / "outside"
                    target.mkdir()
                    target.chmod(0o777)
                    root.symlink_to(target, target_is_directory=True)
                else:
                    root.write_text("not a directory\n", encoding="utf-8")
                    root.chmod(0o666)

                git_mode = (repo / ".git").stat().st_mode & 0o777
                with self.assertRaises(ValueError):
                    module.prepare_review(
                        repo=repo,
                        run_id="unsafe-root",
                        iteration=1,
                        base=None,
                        mode="review-only",
                        task_contract="",
                    )
                self.assertEqual((repo / ".git").stat().st_mode & 0o777, git_mode)
                if root_kind == "symlink":
                    self.assertEqual(target.stat().st_mode & 0o777, 0o777)
                else:
                    self.assertEqual(root.stat().st_mode & 0o777, 0o666)

    def test_approve_high_impact_tightens_existing_approval_artifact(self) -> None:
        module = load_prepare_review_module()

        previous_umask = os.umask(0o002)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                artifact_dir = Path(tmp)
                (artifact_dir / "summary.json").write_text(
                    json.dumps(
                        {
                            "high_impact_confirmation_required": [
                                {
                                    "id": "F-1",
                                    "behavior_impact": "changes public API",
                                    "proposed_fix": "update callers",
                                }
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                approval = artifact_dir / "approved-high-impact.json"
                approval.write_text("[]\n", encoding="utf-8")
                approval.chmod(0o664)

                module.approve_high_impact(artifact_dir, ["F-1"])

                self.assertEqual(approval.stat().st_mode & 0o777, 0o600)
        finally:
            os.umask(previous_umask)

    def test_prepare_review_does_not_execute_textconv(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            marker = repo / ".git" / "textconv.marker"
            textconv = repo / ".git" / "textconv.py"
            textconv.write_text(
                "import pathlib, sys\n"
                f"pathlib.Path({str(marker)!r}).touch()\n"
                "sys.stdout.buffer.write(pathlib.Path(sys.argv[1]).read_bytes())\n",
                encoding="utf-8",
            )
            git(repo, "config", "diff.marker.textconv", f"python3 {textconv}")
            (repo / ".gitattributes").write_text("*.txt diff=marker\n", encoding="utf-8")
            (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "base")
            git(repo, "branch", "-M", "main")
            git(repo, "switch", "-c", "feature")
            (repo / "tracked.txt").write_text("committed\n", encoding="utf-8")
            git(repo, "add", "tracked.txt")
            git(repo, "commit", "-m", "feature")
            (repo / "tracked.txt").write_text("staged\n", encoding="utf-8")
            git(repo, "add", "tracked.txt")
            (repo / "tracked.txt").write_text("unstaged\n", encoding="utf-8")

            module.prepare_review(
                repo=repo,
                run_id="no-textconv",
                iteration=1,
                base="main",
                mode="review-only",
                task_contract="",
            )

            self.assertFalse(marker.exists())

    def test_prepare_review_freezes_committed_and_working_tree_scope(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "committed.txt").write_text("base\n", encoding="utf-8")
            (repo / "staged.txt").write_text("base\n", encoding="utf-8")
            (repo / "unstaged.txt").write_text("base\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "base")
            git(repo, "branch", "-M", "main")
            git(repo, "switch", "-c", "feature")

            (repo / "committed.txt").write_text("feature commit\n", encoding="utf-8")
            git(repo, "add", "committed.txt")
            git(repo, "commit", "-m", "feature")
            (repo / "staged.txt").write_text("staged change\n", encoding="utf-8")
            git(repo, "add", "staged.txt")
            (repo / "unstaged.txt").write_text("unstaged change\n", encoding="utf-8")
            (repo / "untracked.txt").write_text("untracked change\n", encoding="utf-8")

            result = module.prepare_review(
                repo=repo,
                run_id="test-run",
                iteration=1,
                base=None,
                mode="review-and-fix",
                task_contract="Normalize the changed behavior.",
            )

            artifact_dir = Path(result["artifact_dir"])
            self.assertEqual(result["base"], "main")
            self.assertIn("feature commit", (artifact_dir / "committed.diff").read_text(encoding="utf-8"))
            self.assertIn("staged change", (artifact_dir / "staged.diff").read_text(encoding="utf-8"))
            self.assertIn("unstaged change", (artifact_dir / "unstaged.diff").read_text(encoding="utf-8"))
            untracked = json.loads((artifact_dir / "untracked.json").read_text(encoding="utf-8"))
            self.assertEqual(untracked[0]["path"], "untracked.txt")
            snapshot = artifact_dir / untracked[0]["snapshot"]
            self.assertEqual(snapshot.read_text(encoding="utf-8"), "untracked change\n")
            self.assertNotIn("feature commit", json.dumps(result))

    def test_prepare_review_supports_unborn_head_via_function_and_cli(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init")
            (repo / "staged.txt").write_text("staged content\n", encoding="utf-8")
            (repo / "mixed.txt").write_text("indexed content\n", encoding="utf-8")
            git(repo, "add", "staged.txt", "mixed.txt")
            (repo / "mixed.txt").write_text("worktree content\n", encoding="utf-8")
            (repo / "untracked.txt").write_text("untracked content\n", encoding="utf-8")

            direct_result = module.prepare_review(
                repo=repo,
                run_id="unborn-direct",
                iteration=1,
                base=None,
                mode="review-only",
                task_contract="",
            )

            direct_artifact_dir = Path(direct_result["artifact_dir"])
            self.assertEqual((direct_artifact_dir / "committed.diff").read_text(encoding="utf-8"), "")
            self.assertIn("staged content", (direct_artifact_dir / "staged.diff").read_text(encoding="utf-8"))
            self.assertIn("indexed content", (direct_artifact_dir / "staged.diff").read_text(encoding="utf-8"))
            unstaged = (direct_artifact_dir / "unstaged.diff").read_text(encoding="utf-8")
            self.assertIn("indexed content", unstaged)
            self.assertIn("worktree content", unstaged)
            untracked = json.loads((direct_artifact_dir / "untracked.json").read_text(encoding="utf-8"))
            self.assertEqual(untracked[0]["path"], "untracked.txt")
            self.assertEqual(
                (direct_artifact_dir / untracked[0]["snapshot"]).read_text(encoding="utf-8"),
                "untracked content\n",
            )
            scope = json.loads((direct_artifact_dir / "scope.json").read_text(encoding="utf-8"))
            self.assertIsNone(scope["base"])
            self.assertFalse(scope["committed_branch_diff_verified"])
            self.assertFalse(scope["scope_complete"])
            self.assertIn("HEAD", scope["scope_limitation"])
            self.assertTrue(module.validate_artifacts(direct_artifact_dir, "scope")["valid"])
            self.assertEqual(module.scope_fingerprint(repo, None), module.scope_fingerprint(repo, None))

            cli = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--repo",
                    str(repo),
                    "--run-id",
                    "unborn-cli",
                    "--mode",
                    "review-only",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            cli_result = json.loads(cli.stdout)

            for result in (direct_result, cli_result):
                paths = [
                    Path(result["artifact_dir"]),
                    *(Path(path) for path in result["reviewer_prompts"]),
                    Path(result["synthesis_prompt"]),
                    Path(result["fix_prompt"]),
                    Path(result["verify_prompt"]),
                    Path(result["report_prompt"]),
                    Path(result["approved_high_impact"]),
                ]
                self.assertTrue(all(path.exists() for path in paths))

    def test_generated_prompts_keep_detailed_results_out_of_main_session(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "base")
            git(repo, "branch", "-M", "main")

            result = module.prepare_review(
                repo=repo,
                run_id="test-prompts",
                iteration=1,
                base=None,
                mode="review-only",
                task_contract="",
            )

            prompt_text = "\n".join(
                Path(path).read_text(encoding="utf-8") for path in result["reviewer_prompts"]
            )
            for dimension in ("需求完整性", "逻辑正确性", "边界情况", "代码质量", "测试覆盖", "实际运行结果"):
                self.assertIn(dimension, prompt_text)
            self.assertIn("详细结果写入", prompt_text)
            self.assertIn("最终响应只能输出", prompt_text)
            self.assertIn("无法验证", prompt_text)
            self.assertIn("不得因此停止其他维度", prompt_text)
            self.assertIn("不可信数据", prompt_text)
            self.assertIn("requirements_matrix", prompt_text)
            self.assertIn("behavior_test_matrix", prompt_text)
            for prompt_key in ("synthesis_prompt", "fix_prompt", "verify_prompt", "report_prompt"):
                downstream_prompt = Path(result[prompt_key]).read_text(encoding="utf-8")
                self.assertIn("不可信数据", downstream_prompt)
            verify_prompt = Path(result["verify_prompt"]).read_text(encoding="utf-8")
            self.assertIn("commands 和 skipped 每项必须包含布尔 required(true|false)", verify_prompt)

    def test_verification_policy_defaults_to_trusted_full_access_and_keeps_no_exec_fallback(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "base")

            result = module.prepare_review(
                repo=repo,
                run_id="trusted-full-access-default",
                iteration=1,
                base=None,
                mode="review-only",
                task_contract="",
            )

            scope = json.loads((Path(result["artifact_dir"]) / "scope.json").read_text(encoding="utf-8"))
            prompt = Path(result["verify_prompt"]).read_text(encoding="utf-8")
            self.assertEqual(result["verification_policy"], "trusted-full-access")
            self.assertEqual(scope["verification_policy"], "trusted-full-access")
            self.assertEqual(scope["approved_commands"], [])
            self.assertIn("无需逐条确认", prompt)
            self.assertIn("继承宿主提供的 full access", prompt)
            self.assertIn("不得把该模式描述为沙箱", prompt)

            no_exec_result = module.prepare_review(
                repo=repo,
                run_id="explicit-no-exec",
                iteration=1,
                base=None,
                mode="review-only",
                task_contract="",
                verification_policy="no-exec",
            )
            prompt = Path(no_exec_result["verify_prompt"]).read_text(encoding="utf-8")
            self.assertIn("不得执行任何仓库或项目命令", prompt)
            self.assertIn("全部发现的命令写入 skipped", prompt)
            self.assertIn("overall 不得为 green", prompt)

    def test_verification_policy_validates_direct_and_repeatable_cli_inputs(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "base")

            invalid_inputs = (
                {"verification_policy": "unknown", "approved_commands": []},
                {"verification_policy": "approved", "approved_commands": []},
                {"verification_policy": "no-exec", "approved_commands": ["python -m unittest"]},
                {"verification_policy": "sandboxed", "approved_commands": ["python -m unittest"]},
                {
                    "verification_policy": "trusted-full-access",
                    "approved_commands": ["python -m unittest"],
                },
            )
            for index, overrides in enumerate(invalid_inputs):
                with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                    module.prepare_review(
                        repo=repo,
                        run_id=f"invalid-policy-{index}",
                        iteration=1,
                        base=None,
                        mode="review-only",
                        task_contract="",
                        **overrides,
                    )

            commands = ["python -m unittest tests.test_app", "npm test -- --runInBand"]
            cli = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--repo",
                    str(repo),
                    "--run-id",
                    "approved-cli",
                    "--mode",
                    "review-only",
                    "--verification-policy",
                    "approved",
                    "--approved-command",
                    commands[0],
                    "--approved-command",
                    commands[1],
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            result = json.loads(cli.stdout)
            scope = json.loads((Path(result["artifact_dir"]) / "scope.json").read_text(encoding="utf-8"))
            prompt = Path(result["verify_prompt"]).read_text(encoding="utf-8")
            self.assertEqual(result["verification_policy"], "approved")
            self.assertEqual(scope["approved_commands"], commands)
            self.assertIn(json.dumps(commands, ensure_ascii=False), prompt)
            self.assertIn("完全一致", prompt)
            self.assertIn("其余命令写入 skipped", prompt)

            rejected = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--repo",
                    str(repo),
                    "--run-id",
                    "approved-without-command",
                    "--mode",
                    "review-only",
                    "--verification-policy",
                    "approved",
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(rejected.returncode, 0)

    def test_sandboxed_verifier_prompt_requires_host_attestation_and_retains_restrictions(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "base")

            result = module.prepare_review(
                repo=repo,
                run_id="sandboxed-policy",
                iteration=1,
                base=None,
                mode="review-only",
                task_contract="",
                verification_policy="sandboxed",
            )

            prompt = Path(result["verify_prompt"]).read_text(encoding="utf-8")
            self.assertIn("宿主已明确证明当前环境是真实沙箱", prompt)
            self.assertIn("只能在该沙箱内执行项目命令", prompt)
            self.assertIn("禁止任何网络访问", prompt)
            self.assertIn("只有能在安全临时副本中执行时才允许", prompt)
            self.assertIn("否则写入 skipped", prompt)
            for restriction in ("联网", "凭证", "破坏性命令", "未经授权的外部写入"):
                self.assertIn(restriction, prompt)

    def test_verification_validation_enforces_scope_execution_policy(self) -> None:
        module = load_prepare_review_module()
        command = {
            "command": "python -m unittest",
            "exit_code": 0,
            "status": "passed",
            "evidence": "passed",
            "required": True,
        }

        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            verification_path = artifact_dir / "verification.json"
            scope_path = artifact_dir / "scope.json"
            verification_path.write_text(
                json.dumps({"overall": "green", "commands": [command], "skipped": []}),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                module.validate_artifacts(artifact_dir, "verification")

            scope_path.write_text(
                json.dumps(valid_scope(verification_policy="no-exec")),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                module.validate_artifacts(artifact_dir, "verification")

            verification_path.write_text(
                json.dumps(
                    {
                        "overall": "blocked",
                        "commands": [],
                        "skipped": [
                            {
                                "command": command["command"],
                                "reason": "execution disabled by policy",
                                "required": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertTrue(module.validate_artifacts(artifact_dir, "verification")["valid"])

            verification_path.write_text(
                json.dumps({"overall": "green", "commands": [command], "skipped": []}),
                encoding="utf-8",
            )

            scope_path.write_text(
                json.dumps(
                    valid_scope(
                        verification_policy="approved",
                        approved_commands=["python -m unittest tests.test_app"],
                    )
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                module.validate_artifacts(artifact_dir, "verification")

            scope_path.write_text(
                json.dumps(
                    valid_scope(
                        verification_policy="approved",
                        approved_commands=[command["command"]],
                    )
                ),
                encoding="utf-8",
            )
            result = module.validate_artifacts(artifact_dir, "verification")
            self.assertTrue(result["valid"])
            self.assertEqual(result["checked"], [str(scope_path), str(verification_path)])

            scope_path.write_text(
                json.dumps(valid_scope(verification_policy="trusted-full-access")),
                encoding="utf-8",
            )
            self.assertTrue(module.validate_artifacts(artifact_dir, "verification")["valid"])

    def test_main_branch_uses_remote_tracking_base_for_unpushed_commits(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "base")
            git(repo, "branch", "-M", "main")
            git(repo, "update-ref", "refs/remotes/origin/main", git_output(repo, "rev-parse", "HEAD"))
            (repo / "tracked.txt").write_text("unpushed\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "unpushed")

            result = module.prepare_review(
                repo=repo,
                run_id="main-ahead",
                iteration=1,
                base=None,
                mode="review-only",
                task_contract="",
            )

            self.assertEqual(result["base"], "origin/main")
            committed = (Path(result["artifact_dir"]) / "committed.diff").read_text(encoding="utf-8")
            self.assertIn("unpushed", committed)

    def test_prepare_review_rejects_unsafe_run_id(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "base")

            with self.assertRaises(ValueError):
                module.prepare_review(
                    repo=repo,
                    run_id="../../escape",
                    iteration=1,
                    base=None,
                    mode="review-only",
                    task_contract="",
                )

    def test_missing_base_is_recorded_as_scope_limitation(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "base")
            git(repo, "branch", "-M", "feature")

            result = module.prepare_review(
                repo=repo,
                run_id="missing-base",
                iteration=1,
                base=None,
                mode="review-only",
                task_contract="",
            )

            scope = json.loads((Path(result["artifact_dir"]) / "scope.json").read_text(encoding="utf-8"))
            self.assertFalse(scope["committed_branch_diff_verified"])
            self.assertIn("committed", scope["scope_limitation"])

    def test_scope_validation_rejects_malformed_or_inconsistent_metadata(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "base")
            result = module.prepare_review(
                repo=repo,
                run_id="scope-schema",
                iteration=1,
                base=None,
                mode="review-only",
                task_contract="",
            )
            artifact_dir = Path(result["artifact_dir"])
            scope_path = artifact_dir / "scope.json"
            original = json.loads(scope_path.read_text(encoding="utf-8"))
            cases = {
                "repo type": {"repo": 42},
                "branch type": {"branch": 42},
                "unsafe run id": {"run_id": "../escape"},
                "zero iteration": {"iteration": 0},
                "boolean iteration": {"iteration": True},
                "mode enum": {"mode": "fix-everything"},
                "base type": {"base": 42},
                "scope categories": {"includes": ["committed", "staged"]},
                "negative untracked count": {"untracked_count": -1},
                "boolean untracked count": {"untracked_count": False},
                "committed diff flag": {"committed_branch_diff_verified": 1},
                "scope limitation type": {"scope_limitation": 1},
                "empty scope limitation": {"scope_limitations": [""]},
                "scope complete type": {"scope_complete": 1},
                "uppercase fingerprint": {"scope_fingerprint": "A" * 64},
                "verification policy": {"verification_policy": "unrestricted"},
                "approved commands type": {"approved_commands": "test"},
                "complete with limitations": {
                    "scope_complete": True,
                    "scope_limitation": "incomplete",
                    "scope_limitations": ["incomplete"],
                },
                "primary limitation not listed": {
                    "scope_complete": False,
                    "scope_limitation": "other",
                    "scope_limitations": ["incomplete"],
                },
            }
            for name, overrides in cases.items():
                with self.subTest(name=name):
                    scope_path.write_text(
                        json.dumps({**original, **overrides}), encoding="utf-8"
                    )
                    with self.assertRaises(ValueError):
                        module.validate_artifacts(artifact_dir, "scope")
            for field in ("branch", "base", "scope_limitation"):
                with self.subTest(missing_field=field):
                    malformed = dict(original)
                    del malformed[field]
                    scope_path.write_text(json.dumps(malformed), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        module.validate_artifacts(artifact_dir, "scope")

    def test_scope_schema_is_enforced_by_verification_and_fixes_phases(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()

            verification_dir = root / "verification"
            verification_dir.mkdir()
            (verification_dir / "scope.json").write_text(
                json.dumps({**valid_scope(repo), "repo": 42}), encoding="utf-8"
            )
            (verification_dir / "verification.json").write_text(
                json.dumps(
                    {
                        "overall": "green",
                        "commands": [
                            {
                                "command": "test",
                                "exit_code": 0,
                                "status": "passed",
                                "evidence": "passed",
                                "required": True,
                            }
                        ],
                        "skipped": [],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                module.validate_artifacts(verification_dir, "verification")

            fixes_dir = root / "fixes"
            fixes_dir.mkdir()
            (fixes_dir / "scope.json").write_text(
                json.dumps(valid_scope(repo, verification_policy="unrestricted")),
                encoding="utf-8",
            )
            (fixes_dir / "summary.json").write_text(
                json.dumps({"fix_candidates": []}), encoding="utf-8"
            )
            (fixes_dir / "fixes.json").write_text(
                json.dumps({"fixed": [], "blocked": []}), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                module.validate_artifacts(fixes_dir, "fixes")

    def test_validation_rejects_missing_reviewer_artifacts(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "base")

            result = module.prepare_review(
                repo=repo,
                run_id="validate",
                iteration=1,
                base=None,
                mode="review-only",
                task_contract="",
            )

            with self.assertRaises(ValueError):
                module.validate_artifacts(Path(result["artifact_dir"]), "reviewers")

    def test_scope_validation_detects_worktree_changes_after_freeze(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            tracked = repo / "tracked.txt"
            tracked.write_text("base\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "base")
            tracked.write_text("reviewed\n", encoding="utf-8")
            result = module.prepare_review(
                repo=repo,
                run_id="scope-fingerprint",
                iteration=1,
                base=None,
                mode="review-only",
                task_contract="",
            )
            artifact_dir = Path(result["artifact_dir"])

            self.assertTrue(module.validate_artifacts(artifact_dir, "scope")["valid"])
            tracked.write_text("changed during review\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                module.validate_artifacts(artifact_dir, "scope")

    def test_high_impact_approval_is_limited_to_summary_candidates(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            (artifact_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "high_impact_confirmation_required": [
                            {"id": "F-1", "behavior_impact": "changes public API", "proposed_fix": "update callers"}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (artifact_dir / "approved-high-impact.json").write_text("[]\n", encoding="utf-8")

            approved = module.approve_high_impact(artifact_dir, ["F-1"])
            self.assertEqual(approved["approved"], ["F-1"])
            self.assertTrue(module.validate_approval(artifact_dir, approved["approval_digest"])["valid"])
            (artifact_dir / "approved-high-impact.json").write_text('["F-1", "F-2"]\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                module.validate_approval(artifact_dir, approved["approval_digest"])
            with self.assertRaises(ValueError):
                module.approve_high_impact(artifact_dir, ["UNKNOWN"])

    def test_validation_rejects_malformed_verification_command_items(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            (artifact_dir / "scope.json").write_text(
                json.dumps(valid_scope()),
                encoding="utf-8",
            )
            (artifact_dir / "verification.json").write_text(
                json.dumps({"overall": "green", "commands": [42], "skipped": []}),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                module.validate_artifacts(artifact_dir, "verification")

    def test_validation_rejects_green_with_failed_exit_code(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            (artifact_dir / "scope.json").write_text(
                json.dumps(valid_scope()),
                encoding="utf-8",
            )
            (artifact_dir / "verification.json").write_text(
                json.dumps(
                    {
                        "overall": "green",
                        "commands": [
                            {
                                "command": "test",
                                "exit_code": 1,
                                "status": "passed",
                                "evidence": "failed",
                                "required": True,
                            }
                        ],
                        "skipped": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                module.validate_artifacts(artifact_dir, "verification")

    def test_validation_rejects_boolean_verification_exit_code(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            (artifact_dir / "scope.json").write_text(
                json.dumps(valid_scope()),
                encoding="utf-8",
            )
            (artifact_dir / "verification.json").write_text(
                json.dumps(
                    {
                        "overall": "green",
                        "commands": [
                            {
                                "command": "unit tests",
                                "exit_code": False,
                                "status": "passed",
                                "evidence": "passed",
                                "required": True,
                            }
                        ],
                        "skipped": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                module.validate_artifacts(artifact_dir, "verification")

    def test_validation_rejects_green_with_required_skipped_check(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            (artifact_dir / "scope.json").write_text(
                json.dumps(valid_scope()),
                encoding="utf-8",
            )
            (artifact_dir / "verification.json").write_text(
                json.dumps(
                    {
                        "overall": "green",
                        "commands": [
                            {
                                "command": "unit tests",
                                "exit_code": 0,
                                "status": "passed",
                                "evidence": "passed",
                                "required": True,
                            }
                        ],
                        "skipped": [
                            {
                                "command": "integration tests",
                                "reason": "service unavailable",
                                "required": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                module.validate_artifacts(artifact_dir, "verification")

    def test_validation_rejects_missing_or_non_boolean_required_fields(self) -> None:
        module = load_prepare_review_module()
        valid_command = {
            "command": "unit tests",
            "exit_code": 0,
            "status": "passed",
            "evidence": "passed",
            "required": True,
        }
        valid_skipped = {
            "command": "integration tests",
            "reason": "not configured",
            "required": False,
        }
        cases = {
            "command missing required": ({key: value for key, value in valid_command.items() if key != "required"}, []),
            "command non-boolean required": ({**valid_command, "required": "yes"}, []),
            "skipped missing required": ([], {key: value for key, value in valid_skipped.items() if key != "required"}),
            "skipped non-boolean required": ([], {**valid_skipped, "required": 0}),
        }

        for name, (commands, skipped) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                artifact_dir = Path(tmp)
                (artifact_dir / "scope.json").write_text(
                    json.dumps(valid_scope()),
                    encoding="utf-8",
                )
                (artifact_dir / "verification.json").write_text(
                    json.dumps(
                        {
                            "overall": "blocked",
                            "commands": commands if isinstance(commands, list) else [commands],
                            "skipped": skipped if isinstance(skipped, list) else [skipped],
                        }
                    ),
                    encoding="utf-8",
                )

                with self.assertRaises(ValueError):
                    module.validate_artifacts(artifact_dir, "verification")

    def test_validation_allows_green_with_optional_skipped_check(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            (artifact_dir / "scope.json").write_text(
                json.dumps(valid_scope()),
                encoding="utf-8",
            )
            (artifact_dir / "verification.json").write_text(
                json.dumps(
                    {
                        "overall": "green",
                        "commands": [
                            {
                                "command": "unit tests",
                                "exit_code": 0,
                                "status": "passed",
                                "evidence": "passed",
                                "required": True,
                            }
                        ],
                        "skipped": [
                            {
                                "command": "optional smoke test",
                                "reason": "not configured",
                                "required": False,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            self.assertTrue(module.validate_artifacts(artifact_dir, "verification")["valid"])

    def test_validation_rejects_malformed_fixed_items(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            (artifact_dir / "fixes.json").write_text(
                json.dumps({"fixed": ["F-1"], "blocked": []}), encoding="utf-8"
            )

            with self.assertRaises(ValueError):
                module.validate_artifacts(artifact_dir, "fixes")

    def test_fixes_validation_rejects_unknown_fixed_id(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            artifact_dir = root / "iteration-1"
            artifact_dir.mkdir()
            (artifact_dir / "scope.json").write_text(
                json.dumps(valid_scope(repo)), encoding="utf-8"
            )
            (artifact_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "fix_candidates": [
                            {
                                "id": "F-1",
                                "severity": "High",
                                "confidence": "High",
                                "impact": "Low",
                                "location": "src/app.py:1",
                                "recommended_fix": "fix it",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (artifact_dir / "fixes.json").write_text(
                json.dumps(
                    {
                        "fixed": [
                            {"id": "UNKNOWN", "files": ["src/app.py"], "evidence": "fixed"}
                        ],
                        "blocked": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                module.validate_artifacts(artifact_dir, "fixes")

    def test_fixes_validation_rejects_paths_outside_repository(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            outside = root / "outside"
            outside.mkdir()
            os.symlink(outside, repo / "outside-link")
            artifact_dir = root / "iteration-1"
            artifact_dir.mkdir()
            (artifact_dir / "scope.json").write_text(
                json.dumps(valid_scope(repo)), encoding="utf-8"
            )
            (artifact_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "fix_candidates": [
                            {
                                "id": "F-1",
                                "severity": "Critical",
                                "confidence": "High",
                                "impact": "Medium",
                                "location": "src/app.py:1",
                                "recommended_fix": "fix it",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            for invalid_path in (
                str(root / "absolute.py"),
                "../outside.py",
                "src/../app.py",
                "outside-link/file.py",
            ):
                with self.subTest(path=invalid_path):
                    (artifact_dir / "fixes.json").write_text(
                        json.dumps(
                            {
                                "fixed": [
                                    {"id": "F-1", "files": [invalid_path], "evidence": "fixed"}
                                ],
                                "blocked": [],
                            }
                        ),
                        encoding="utf-8",
                    )

                    with self.assertRaises(ValueError):
                        module.validate_artifacts(artifact_dir, "fixes")

    def test_fixes_validation_rejects_unknown_duplicate_or_overlapping_ids(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            artifact_dir = root / "iteration-1"
            artifact_dir.mkdir()
            (artifact_dir / "scope.json").write_text(
                json.dumps(valid_scope(repo)), encoding="utf-8"
            )
            (artifact_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "fix_candidates": [
                            {
                                "id": "F-1",
                                "severity": "High",
                                "confidence": "High",
                                "impact": "Low",
                                "location": "src/app.py:1",
                                "recommended_fix": "fix it",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            fixed = {"id": "F-1", "files": ["src/app.py"], "evidence": "fixed"}
            blocked = {"id": "F-1", "reason": "not safe"}
            cases = {
                "unknown blocked ID": ([], [{"id": "UNKNOWN", "reason": "not found"}]),
                "duplicate fixed ID": ([fixed, fixed], []),
                "duplicate blocked ID": ([], [blocked, blocked]),
                "fixed and blocked overlap": ([fixed], [blocked]),
            }

            for name, (fixed_items, blocked_items) in cases.items():
                with self.subTest(name=name):
                    (artifact_dir / "fixes.json").write_text(
                        json.dumps({"fixed": fixed_items, "blocked": blocked_items}),
                        encoding="utf-8",
                    )

                    with self.assertRaises(ValueError):
                        module.validate_artifacts(artifact_dir, "fixes")

    def test_fixes_validation_rejects_candidates_not_authorized_for_automatic_fix(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            artifact_dir = root / "iteration-1"
            artifact_dir.mkdir()
            (artifact_dir / "scope.json").write_text(
                json.dumps(valid_scope(repo)), encoding="utf-8"
            )
            base_candidate = {
                "id": "F-1",
                "severity": "High",
                "confidence": "High",
                "impact": "Low",
                "location": "src/app.py:1",
                "recommended_fix": "fix it",
            }
            cases = {
                "medium severity": {"severity": "Medium"},
                "medium confidence": {"confidence": "Medium"},
                "high impact": {"impact": "High"},
            }

            for name, override in cases.items():
                with self.subTest(name=name):
                    (artifact_dir / "summary.json").write_text(
                        json.dumps({"fix_candidates": [{**base_candidate, **override}]}),
                        encoding="utf-8",
                    )
                    (artifact_dir / "fixes.json").write_text(
                        json.dumps(
                            {
                                "fixed": [
                                    {"id": "F-1", "files": ["src/app.py"], "evidence": "fixed"}
                                ],
                                "blocked": [],
                            }
                        ),
                        encoding="utf-8",
                    )

                    with self.assertRaises(ValueError):
                        module.validate_artifacts(artifact_dir, "fixes")

    def test_fixes_validation_accepts_authorized_fix_and_blocked_high_impact_candidate(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            source = repo / "src"
            source.mkdir(parents=True)
            os.symlink(source, repo / "inside-link")
            artifact_dir = root / "iteration-1"
            artifact_dir.mkdir()
            (artifact_dir / "scope.json").write_text(
                json.dumps(valid_scope(repo)), encoding="utf-8"
            )
            (artifact_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "fix_candidates": [
                            {
                                "id": "F-1",
                                "severity": "Critical",
                                "confidence": "High",
                                "impact": "Medium",
                                "location": "src/app.py:1",
                                "recommended_fix": "fix it",
                            },
                            {
                                "id": "F-2",
                                "severity": "Critical",
                                "confidence": "High",
                                "impact": "High",
                                "location": "src/api.py:1",
                                "recommended_fix": "change the API",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (artifact_dir / "fixes.json").write_text(
                json.dumps(
                    {
                        "fixed": [
                            {"id": "F-1", "files": ["inside-link/app.py"], "evidence": "fixed"}
                        ],
                        "blocked": [{"id": "F-2", "reason": "high impact"}],
                    }
                ),
                encoding="utf-8",
            )

            result = module.validate_artifacts(artifact_dir, "fixes")

            self.assertTrue(result["valid"])
            self.assertEqual(
                result["checked"],
                [
                    str(artifact_dir / "scope.json"),
                    str(artifact_dir / "summary.json"),
                    str(artifact_dir / "fixes.json"),
                ],
            )

    def test_validation_rejects_malformed_finding_items(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            results = artifact_dir / "results"
            results.mkdir()
            (results / "requirements-correctness.json").write_text(
                json.dumps({"role": "requirements-correctness", "findings": [], "requirements_status": "unverifiable", "requirements_matrix": []}),
                encoding="utf-8",
            )
            (results / "risk.json").write_text(
                json.dumps({"role": "risk", "findings": [42]}), encoding="utf-8"
            )
            (results / "quality-tests.json").write_text(
                json.dumps({"role": "quality-tests", "findings": [], "behavior_test_matrix": []}),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                module.validate_artifacts(artifact_dir, "reviewers")

    def test_reviewer_validation_rejects_invalid_requirements_matrix_items(self) -> None:
        module = load_prepare_review_module()
        valid_item = {
            "source": "task contract",
            "requirement": "preserve behavior",
            "implementation_evidence": "src/app.py:10",
            "test_evidence": "tests/test_app.py:20",
            "status": "verified",
        }
        invalid_items = [("non-object", 42), ("invalid-status", {**valid_item, "status": "unknown"})]
        invalid_items.extend(
            (f"blank-{field}", {**valid_item, field: " "})
            for field in (
                "source",
                "requirement",
                "implementation_evidence",
                "test_evidence",
            )
        )

        for label, invalid_item in invalid_items:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                artifact_dir = Path(tmp)
                results = artifact_dir / "results"
                results.mkdir()
                (results / "requirements-correctness.json").write_text(
                    json.dumps(
                        {
                            "role": "requirements-correctness",
                            "findings": [],
                            "requirements_status": "verified",
                            "requirements_matrix": [invalid_item],
                        }
                    ),
                    encoding="utf-8",
                )
                (results / "risk.json").write_text(
                    json.dumps({"role": "risk", "findings": []}), encoding="utf-8"
                )
                (results / "quality-tests.json").write_text(
                    json.dumps(
                        {"role": "quality-tests", "findings": [], "behavior_test_matrix": []}
                    ),
                    encoding="utf-8",
                )

                with self.assertRaises(ValueError):
                    module.validate_artifacts(artifact_dir, "reviewers")

    def test_reviewer_validation_rejects_invalid_behavior_test_matrix_items(self) -> None:
        module = load_prepare_review_module()
        valid_item = {
            "behavior": "returns the saved value",
            "test": "tests/test_app.py::test_saved_value",
            "assertion_or_gap": "assert result == saved",
            "status": "verified",
        }
        invalid_items = [("non-object", 42), ("invalid-status", {**valid_item, "status": "unknown"})]
        invalid_items.extend(
            (f"blank-{field}", {**valid_item, field: " "})
            for field in ("behavior", "test", "assertion_or_gap")
        )

        for label, invalid_item in invalid_items:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                artifact_dir = Path(tmp)
                results = artifact_dir / "results"
                results.mkdir()
                (results / "requirements-correctness.json").write_text(
                    json.dumps(
                        {
                            "role": "requirements-correctness",
                            "findings": [],
                            "requirements_status": "unverifiable",
                            "requirements_matrix": [],
                        }
                    ),
                    encoding="utf-8",
                )
                (results / "risk.json").write_text(
                    json.dumps({"role": "risk", "findings": []}), encoding="utf-8"
                )
                (results / "quality-tests.json").write_text(
                    json.dumps(
                        {
                            "role": "quality-tests",
                            "findings": [],
                            "behavior_test_matrix": [invalid_item],
                        }
                    ),
                    encoding="utf-8",
                )

                with self.assertRaises(ValueError):
                    module.validate_artifacts(artifact_dir, "reviewers")

    def test_synthesis_validation_rejects_invalid_evidence_matrix_items(self) -> None:
        module = load_prepare_review_module()
        invalid_matrices = (
            (
                "requirements_matrix",
                {
                    "source": "task contract",
                    "requirement": "preserve behavior",
                    "implementation_evidence": "src/app.py:10",
                    "test_evidence": "tests/test_app.py:20",
                    "status": "unknown",
                },
            ),
            (
                "behavior_test_matrix",
                {
                    "behavior": "returns the saved value",
                    "test": "tests/test_app.py::test_saved_value",
                    "assertion_or_gap": " ",
                    "status": "verified",
                },
            ),
        )

        for matrix_name, invalid_item in invalid_matrices:
            with self.subTest(matrix_name=matrix_name), tempfile.TemporaryDirectory() as tmp:
                artifact_dir = Path(tmp)
                summary = {
                    "requirements_status": "verified",
                    "requirements_matrix": [],
                    "behavior_test_matrix": [],
                    "blockers": [],
                    "warnings": [],
                    "fix_candidates": [],
                    "high_impact_confirmation_required": [],
                }
                summary[matrix_name] = [invalid_item]
                (artifact_dir / "summary.json").write_text(
                    json.dumps(summary), encoding="utf-8"
                )

                with self.assertRaises(ValueError):
                    module.validate_artifacts(artifact_dir, "synthesis")

    def test_synthesis_validation_requires_valid_requirements_status(self) -> None:
        module = load_prepare_review_module()

        for requirements_status in (None, "unknown"):
            with self.subTest(requirements_status=requirements_status), tempfile.TemporaryDirectory() as tmp:
                artifact_dir = Path(tmp)
                summary = {
                    "requirements_matrix": [],
                    "behavior_test_matrix": [],
                    "blockers": [],
                    "warnings": [],
                    "fix_candidates": [],
                    "high_impact_confirmation_required": [],
                }
                if requirements_status is not None:
                    summary["requirements_status"] = requirements_status
                (artifact_dir / "summary.json").write_text(
                    json.dumps(summary), encoding="utf-8"
                )

                with self.assertRaises(ValueError):
                    module.validate_artifacts(artifact_dir, "synthesis")

    def test_synthesis_validation_rejects_non_string_requirements_status(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            (artifact_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "requirements_status": [],
                        "requirements_matrix": [],
                        "behavior_test_matrix": [],
                        "blockers": [],
                        "warnings": [],
                        "fix_candidates": [],
                        "high_impact_confirmation_required": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                module.validate_artifacts(artifact_dir, "synthesis")

    def test_validation_accepts_empty_evidence_matrices(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            results = artifact_dir / "results"
            results.mkdir()
            (results / "requirements-correctness.json").write_text(
                json.dumps(
                    {
                        "role": "requirements-correctness",
                        "findings": [],
                        "requirements_status": "unverifiable",
                        "requirements_matrix": [],
                    }
                ),
                encoding="utf-8",
            )
            (results / "risk.json").write_text(
                json.dumps({"role": "risk", "findings": []}), encoding="utf-8"
            )
            (results / "quality-tests.json").write_text(
                json.dumps({"role": "quality-tests", "findings": [], "behavior_test_matrix": []}),
                encoding="utf-8",
            )
            self.assertTrue(module.validate_artifacts(artifact_dir, "reviewers")["valid"])

            (artifact_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "requirements_status": "unverifiable",
                        "requirements_matrix": [],
                        "behavior_test_matrix": [],
                        "blockers": [],
                        "warnings": [],
                        "fix_candidates": [],
                        "high_impact_confirmation_required": [],
                    }
                ),
                encoding="utf-8",
            )
            self.assertTrue(module.validate_artifacts(artifact_dir, "synthesis")["valid"])

    def test_untracked_symlinks_are_recorded_without_following_targets(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            git(repo, "init")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "base")
            outside = root / "outside.txt"
            outside.write_text("secret\n", encoding="utf-8")
            os.symlink("README.md", repo / "inside-link")
            os.symlink(outside, repo / "outside-link")

            result = module.prepare_review(
                repo=repo,
                run_id="symlinks",
                iteration=1,
                base=None,
                mode="review-only",
                task_contract="",
            )

            entries = json.loads((Path(result["artifact_dir"]) / "untracked.json").read_text(encoding="utf-8"))
            by_path = {entry["path"]: entry for entry in entries}
            self.assertEqual(by_path["inside-link"]["type"], "symlink")
            self.assertEqual(by_path["inside-link"]["target"], "README.md")
            self.assertEqual(by_path["outside-link"]["type"], "symlink")
            self.assertIsNone(by_path["outside-link"]["snapshot"])

    def test_unsupported_untracked_directory_is_preserved_as_incomplete_scope(self) -> None:
        module = load_prepare_review_module()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            git(repo, "init")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "README.md").write_text("fixture\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "base")

            baseline_fingerprint = module.scope_fingerprint(repo, "HEAD")
            nested = repo / "nested"
            nested.mkdir()
            git(nested, "init")
            git(nested, "config", "user.email", "test@example.com")
            git(nested, "config", "user.name", "Test")
            nested_file = nested / "nested.txt"
            nested_file.write_text("nested content\n", encoding="utf-8")
            git(nested, "add", ".")
            git(nested, "commit", "-m", "nested")

            self.assertEqual(
                git_output(repo, "ls-files", "--others", "--exclude-standard"), "nested/"
            )
            directory_fingerprint = module.scope_fingerprint(repo, "HEAD")
            self.assertNotEqual(directory_fingerprint, baseline_fingerprint)
            nested_file.write_text("changed nested content\n", encoding="utf-8")
            self.assertEqual(module.scope_fingerprint(repo, "HEAD"), directory_fingerprint)

            result = module.prepare_review(
                repo=repo,
                run_id="nested-directory",
                iteration=1,
                base="HEAD",
                mode="review-only",
                task_contract="",
            )

            artifact_dir = Path(result["artifact_dir"])
            entries = json.loads((artifact_dir / "untracked.json").read_text(encoding="utf-8"))
            self.assertEqual(len(entries), 1)
            entry = entries[0]
            self.assertEqual(entry["path"], "nested/")
            self.assertEqual(entry["type"], "directory")
            self.assertIsNone(entry["snapshot"])
            self.assertTrue(entry["limitation"])
            self.assertFalse((artifact_dir / "untracked-files" / "nested").exists())

            scope = json.loads((artifact_dir / "scope.json").read_text(encoding="utf-8"))
            self.assertFalse(scope["scope_complete"])
            self.assertIn(entry["limitation"], scope["scope_limitations"])
            self.assertIn(entry["limitation"], scope["scope_limitation"])
            report_prompt = Path(result["report_prompt"]).read_text(encoding="utf-8")
            self.assertIn("scope.json", report_prompt)
            self.assertIn("scope_complete=true", report_prompt)

            nested.rename(root / "removed-nested")
            self.assertEqual(module.scope_fingerprint(repo, "HEAD"), baseline_fingerprint)

    def test_skill_defines_thin_portable_orchestration_contract(self) -> None:
        skill = SKILL_PATH.read_text(encoding="utf-8")

        self.assertIn("review-only", skill)
        self.assertIn("review-and-fix", skill)
        self.assertIn("max_iterations", skill)
        self.assertIn("`3`", skill)
        self.assertIn("主 session", skill)
        self.assertIn("不读取完整 diff", skill)
        self.assertIn("动态并发", skill)
        self.assertIn("prepare_review.py", skill)
        self.assertNotIn("runSubagent", skill)
        self.assertNotIn("Confidence 降低 0.15", skill)
        self.assertNotIn("Confidence -= 0.15", skill)

    def test_skill_documents_verification_policy_selection_and_fresh_approval_iteration(self) -> None:
        skill = SKILL_PATH.read_text(encoding="utf-8")

        self.assertIn("verification_policy", skill)
        self.assertIn("宿主明确证明", skill)
        self.assertIn("`sandboxed`", skill)
        self.assertIn("`trusted-full-access`", skill)
        self.assertIn("默认 `trusted-full-access`", skill)
        self.assertIn("无需逐条确认", skill)
        self.assertIn("显式选择 `no-exec`", skill)
        self.assertIn("新的 iteration", skill)
        self.assertIn("--verification-policy approved", skill)
        self.assertIn("--approved-command", skill)


if __name__ == "__main__":
    unittest.main()
