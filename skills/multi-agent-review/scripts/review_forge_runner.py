#!/usr/bin/env python3
"""Local runner for the multi-agent-review skill."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


CONFIG_DIR = ".review-forge"
CONFIG_FILE = "config.local.yaml"
ARTIFACT_DIR = f"{CONFIG_DIR}/artifacts"
REVIEW_SCOPE_FILE = "review-scope.txt"
DEFAULT_TIMEOUT_SECONDS = 1800
MAX_UNTRACKED_FILE_BYTES = 200_000


def main() -> int:
    parser = argparse.ArgumentParser(description="Run multi-agent code review workflow.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create local config template.")
    sub.add_parser("check-config", help="Smoke test configured CLI/model entries without requiring config_ready.")

    review = sub.add_parser("review", help="Run independent review agents.")
    add_feature_arg(review)
    scope = review.add_mutually_exclusive_group()
    scope.add_argument("--scope", choices=["working"], help="Review uncommitted working tree diff.")
    scope.add_argument("--base", help="Review branch diff against this base ref, plus working tree diff.")

    synthesize = sub.add_parser("synthesize", help="Synthesize review reports.")
    add_feature_arg(synthesize)

    fix = sub.add_parser("fix", help="Fix selected summary items.")
    add_feature_arg(fix)

    verify = sub.add_parser("verify", help="Verify fixes independently.")
    add_feature_arg(verify)

    args = parser.parse_args()
    repo = Path.cwd()

    if args.command == "init":
        init_config(repo)
        return 0

    if args.command == "check-config":
        config = load_config(repo, require_ready=False)
        run_check_config(repo, config)
        return 0

    config = load_config(repo)
    if args.command == "review":
        run_review(repo, config, args.feature, args.scope, args.base)
    elif args.command == "synthesize":
        run_synthesize(repo, config, args.feature)
    elif args.command == "fix":
        run_fix(repo, config, args.feature)
    elif args.command == "verify":
        run_verify(repo, config, args.feature)
    return 0


def add_feature_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--feature", required=True, help="Feature name for .review-forge/artifacts/<feature> artifacts.")


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def init_config(repo: Path) -> None:
    cfg_dir = repo / CONFIG_DIR
    cfg_dir.mkdir(exist_ok=True)
    cfg_path = cfg_dir / CONFIG_FILE
    if not cfg_path.exists():
        cfg_path.write_text(default_config_template(), encoding="utf-8")
        print(f"Created {cfg_path}")
    else:
        print(f"Exists {cfg_path}")
    ensure_local_ignore(repo)


def default_config_template() -> str:
    return """# 配置确认开关：确认下面的 CLI、模型名、环境变量和测试命令都可用后，才改成 true。
config_ready: false

# Review 阶段使用的模型 ID 列表：runner 会取前三个模型并行独立审查 diff。
review_models:
  - reviewer-claude
  - reviewer-codex
  - reviewer-claude-2

# 汇总阶段使用的模型 ID：负责把多份 review 报告合并成 summary.md。
synthesize_model: reviewer-codex

# 修复阶段使用的模型 ID：会直接修改当前工作区，建议配置成能力最强、最稳定的模型。
fix_model: fixer-claude

# 验证阶段使用的模型 ID：应不同于 fix_model，用来独立检查修复是否完成。
verify_model: verifier-codex

# 单个 CLI agent 最长运行时间，单位秒。
timeout_seconds: 1800

# 修复和验证阶段要运行的测试命令；不知道时可留空，由 agent 自行选择最小相关测试。
test_command:

# 模型定义表：上面的 review_models / synthesize_model / fix_model / verify_model 都必须引用这里的某个 ID。
models:
  # reviewer-claude：示例 Claude Code reviewer。cli 只能是 claude 或 codex。
  reviewer-claude:
    # cli：调用哪个本地命令，目前支持 claude 和 codex。
    cli: claude
    # model：传给对应 CLI 的模型名；可用值取决于你本机 CLI 和账号/provider 配置。
    model: sonnet
    # env：可选。只对这个模型调用生效。下面是 Claude Anthropic-compatible 第三方 API 示例，按需取消注释。
    # env:
    #   ANTHROPIC_BASE_URL: https://api.deepseek.com/anthropic
    #   ANTHROPIC_AUTH_TOKEN: ${DEEPSEEK_API_KEY}
    #   ANTHROPIC_MODEL: deepseek-v4-pro

  # reviewer-codex：示例 Codex reviewer。
  reviewer-codex:
    cli: codex
    model: gpt-5.5
    # env：可选。Codex 走本机登录态时通常不需要；如需自定义 provider，可在这里补 CLI 支持的环境变量。
    # env:
    #   OPENAI_API_KEY: ${OPENAI_API_KEY}

  # reviewer-claude-2：第三个 reviewer 示例；建议实际使用时换成不同模型或不同 provider。
  reviewer-claude-2:
    cli: claude
    model: sonnet

  # fixer-claude：修复模型示例。dangerous=true 会给 fix 阶段更高权限，允许自动改文件和跑命令。
  fixer-claude:
    cli: claude
    model: sonnet
    # dangerous：仅建议给 fix_model 开启；review/synthesize/verify 默认不需要。
    dangerous: true

  # verifier-codex：验证模型示例。默认不要开启 dangerous，避免验证阶段悄悄改代码。
  verifier-codex:
    cli: codex
    model: gpt-5.5
"""


def ensure_local_ignore(repo: Path) -> None:
    entries = [f"{CONFIG_DIR}/"]
    result = git(repo, ["rev-parse", "--git-path", "info/exclude"], check=False)
    if result.returncode == 0 and result.stdout.strip():
        ignore_path = Path(result.stdout.strip())
        if not ignore_path.is_absolute():
            ignore_path = repo / ignore_path
    else:
        ignore_path = repo / ".gitignore"
    existing = ignore_path.read_text(encoding="utf-8") if ignore_path.exists() else ""
    lines = [line.strip() for line in existing.splitlines()]
    missing = [entry for entry in entries if entry not in lines]
    if missing:
        ignore_path.parent.mkdir(parents=True, exist_ok=True)
        with ignore_path.open("a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            for entry in missing:
                f.write(f"{entry}\n")
                print(f"Added {entry} to {ignore_path}")


def load_config(repo: Path, require_ready: bool = True) -> dict[str, Any]:
    path = repo / CONFIG_DIR / CONFIG_FILE
    if not path.exists():
        fail(f"Missing {path}. Run `review_forge_runner.py init` first.")
    config = parse_simple_yaml(path.read_text(encoding="utf-8"))
    validate_config(config, require_ready=require_ready)
    warn_plaintext_secrets(config)
    return config


def validate_config(config: dict[str, Any], require_ready: bool = True) -> None:
    if require_ready and config.get("config_ready") is not True:
        fail("Config is not confirmed. Edit .review-forge/config.local.yaml, verify model settings, then set `config_ready: true`.")
    models = config.get("models")
    if not isinstance(models, dict) or not models:
        fail("Config must define models.")
    review_models = config.get("review_models")
    if not isinstance(review_models, list) or len(review_models) < 1:
        fail("Config must define at least one review_models entry.")
    for key in ["fix_model", "verify_model"]:
        if not config.get(key):
            fail(f"Config must define {key}.")
    for model_id in set(configured_role_model_ids(config)):
        if model_id not in models:
            fail(f"Model `{model_id}` is referenced but not defined in models.")
        cli = models[model_id].get("cli")
        if cli not in {"claude", "codex"}:
            fail(f"Model `{model_id}` uses unsupported cli `{cli}`. Supported: claude, codex.")


def warn_plaintext_secrets(config: dict[str, Any]) -> None:
    secret_names = ("KEY", "TOKEN", "SECRET", "PASSWORD")
    for model_id, model in config.get("models", {}).items():
        for key, value in (model.get("env") or {}).items():
            if any(name in key.upper() for name in secret_names):
                text = str(value)
                if text and not text.startswith("${"):
                    print(f"Warning: {model_id}.{key} appears to contain a plaintext secret. Keep config.local.yaml out of git.", file=sys.stderr)


def configured_role_model_ids(config: dict[str, Any]) -> list[str]:
    review_models = config["review_models"][:3]
    return review_models + [
        config.get("synthesize_model") or review_models[0],
        config["fix_model"],
        config["verify_model"],
    ]


def configured_role_map(config: dict[str, Any]) -> dict[str, list[str]]:
    review_models = config["review_models"][:3]
    pairs = [(f"review[{index + 1}]", model_id) for index, model_id in enumerate(review_models)]
    pairs.extend([
        ("synthesize", config.get("synthesize_model") or review_models[0]),
        ("fix", config["fix_model"]),
        ("verify", config["verify_model"]),
    ])
    role_map: dict[str, list[str]] = {}
    for role, model_id in pairs:
        role_map.setdefault(model_id, []).append(role)
    return role_map


def run_check_config(repo: Path, config: dict[str, Any]) -> None:
    feature_dir = make_feature_dirs(repo, "config-check")
    prompt = "这是 multi-agent-review 的配置连通性测试。请不要读写文件、不要运行命令，只输出 OK。"
    timeout = int(config.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)
    success_count = 0
    role_map = configured_role_map(config)
    for model_id, roles in role_map.items():
        result = run_model(
            repo,
            config,
            model_id,
            prompt,
            "check-config",
            timeout,
            use_config_dangerous=False,
        )
        write_log(feature_dir, model_id, "check-config", result)
        roles_text = ", ".join(roles)
        if result.returncode == 0:
            success_count += 1
            print(f"{model_id} ({roles_text}): OK")
        else:
            print(f"{model_id} ({roles_text}): FAIL exit {result.returncode}")
    if success_count != len(role_map):
        fail(f"{len(role_map) - success_count} configured model(s) failed. See {feature_dir / 'logs'}.")
    print("Config check passed. If these are the intended models, set `config_ready: true`.")


def run_review(repo: Path, config: dict[str, Any], feature: str, scope: str | None, base: str | None) -> None:
    feature_dir = make_feature_dirs(repo, feature)
    scope, base = resolve_review_scope(repo, scope, base)
    diff, scope_description = collect_review_diff(repo, scope, base)
    if not diff.strip():
        fail("Selected diff is empty.")
    write_review_scope(feature_dir, scope, base)

    prompt_template = read_prompt("review.md")
    review_models = config["review_models"][:3]
    timeout = int(config.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)

    print(f"Running {len(review_models)} review agent(s)...")
    success_count = 0
    with ThreadPoolExecutor(max_workers=len(review_models)) as executor:
        futures = {}
        for model_id in review_models:
            prompt = render(prompt_template, {
                "feature": feature,
                "scope_description": scope_description,
                "repo_root": str(repo),
                "diff": diff,
            })
            futures[executor.submit(run_model, repo, config, model_id, prompt, "review", timeout)] = model_id
        for future in as_completed(futures):
            model_id = futures[future]
            result = future.result()
            write_agent_result(feature_dir, "reviews", model_id, result)
            if result.returncode == 0:
                success_count += 1
            print(f"{model_id}: exit {result.returncode}")
    if success_count == 0:
        fail("All review agents failed. See .review-forge/artifacts logs.")


def resolve_review_scope(repo: Path, scope: str | None, base: str | None) -> tuple[str | None, str | None]:
    if scope or base:
        return scope, base
    branch = current_branch(repo)
    if not branch or branch in {"main", "master"}:
        return "working", None
    detected_base = detect_base_ref(repo)
    if not detected_base:
        fail("Cannot infer review base. Pass --scope working or --base <ref> explicitly.")
    return None, detected_base


def current_branch(repo: Path) -> str:
    result = git(repo, ["branch", "--show-current"], check=False)
    return result.stdout.strip() if result.returncode == 0 else ""


def detect_base_ref(repo: Path) -> str | None:
    for candidate in ["origin/main", "origin/master", "main", "master"]:
        result = git(repo, ["rev-parse", "--verify", "--quiet", candidate], check=False)
        if result.returncode == 0:
            return candidate
    return None


def run_synthesize(repo: Path, config: dict[str, Any], feature: str) -> None:
    feature_dir = make_feature_dirs(repo, feature)
    reports = collect_reports(feature_dir)
    if not reports.strip():
        fail("No review reports found. Run review first.")
    model_id = config.get("synthesize_model") or config["review_models"][0]
    prompt = render(read_prompt("synthesize.md"), {
        "feature": feature,
        "reports": reports,
    })
    result = run_model(repo, config, model_id, prompt, "synthesize", int(config.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS))
    write_log(feature_dir, model_id, "synthesize", result)
    if result.returncode != 0:
        fail(f"Synthesize model `{model_id}` failed. See logs.")
    (feature_dir / "summary.md").write_text(clean_final_output(result.stdout), encoding="utf-8")
    print(f"Wrote {feature_dir / 'summary.md'}")


def run_fix(repo: Path, config: dict[str, Any], feature: str) -> None:
    feature_dir = make_feature_dirs(repo, feature)
    summary = read_required(feature_dir / "summary.md")
    selected = selected_summary_items(summary)
    if not selected.strip():
        fail("No checked summary items found. Edit summary.md and check items to fix.")
    scope, base = read_review_scope(feature_dir)
    pre_fix, _ = collect_review_diff(repo, scope, base)
    (feature_dir / "pre-fix.diff").write_text(pre_fix, encoding="utf-8")
    model_id = config["fix_model"]
    prompt = render(read_prompt("fix.md"), {
        "feature": feature,
        "repo_root": str(repo),
        "test_command": str(config.get("test_command") or "not configured"),
        "selected_items": selected,
        "summary": summary,
    })
    result = run_model(repo, config, model_id, prompt, "fix", int(config.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS), force_dangerous=True)
    write_log(feature_dir, model_id, "fix", result)
    if result.returncode != 0:
        fail(f"Fix model `{model_id}` failed. See logs.")
    append_status(feature_dir, "fix", model_id, result.stdout)
    print(f"Fix completed with {model_id}. Review {feature_dir / 'status.md'}")


def run_verify(repo: Path, config: dict[str, Any], feature: str) -> None:
    feature_dir = make_feature_dirs(repo, feature)
    summary = read_required(feature_dir / "summary.md")
    selected = selected_summary_items(summary)
    if not selected.strip():
        fail("No checked summary items found. Nothing to verify.")
    status = (feature_dir / "status.md").read_text(encoding="utf-8") if (feature_dir / "status.md").exists() else ""
    scope, base = read_review_scope(feature_dir)
    diff, _ = collect_review_diff(repo, scope, base)
    model_id = config["verify_model"]
    prompt = render(read_prompt("verify.md"), {
        "feature": feature,
        "repo_root": str(repo),
        "test_command": str(config.get("test_command") or "not configured"),
        "selected_items": selected,
        "status": status,
        "diff": diff,
    })
    result = run_model(repo, config, model_id, prompt, "verify", int(config.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS))
    write_log(feature_dir, model_id, "verify", result)
    if result.returncode != 0:
        fail(f"Verify model `{model_id}` failed. See logs.")
    (feature_dir / "verify.md").write_text(clean_final_output(result.stdout), encoding="utf-8")
    append_status(feature_dir, "verify", model_id, result.stdout)
    print(f"Wrote {feature_dir / 'verify.md'}")


def collect_review_diff(repo: Path, scope: str | None, base: str | None) -> tuple[str, str]:
    if scope == "working":
        diff = collect_tracked_working_diff(repo)
        untracked = collect_untracked_files(repo)
        if untracked:
            diff = join_diff_parts([diff, untracked])
        return diff, "working tree diff including staged, unstaged, and untracked files"
    if base:
        committed = git(repo, ["diff", f"{base}...HEAD"], check=True).stdout
        working = collect_tracked_working_diff(repo)
        untracked = collect_untracked_files(repo)
        parts = []
        if committed.strip():
            parts.append(f"# Diff against {base}\n{committed}")
        if working.strip():
            parts.append(f"# Uncommitted working tree diff\n{working}")
        if untracked.strip():
            parts.append(untracked)
        return "\n\n".join(parts), f"{base}...HEAD plus working tree diff"
    fail("Internal error: missing scope.")


def collect_tracked_working_diff(repo: Path) -> str:
    result = git(repo, ["diff", "HEAD"], check=False)
    if result.returncode == 0:
        return result.stdout
    cached = git(repo, ["diff", "--cached"], check=True).stdout
    unstaged = git(repo, ["diff"], check=True).stdout
    return join_diff_parts([cached, unstaged])


def write_review_scope(feature_dir: Path, scope: str | None, base: str | None) -> None:
    value = f"base={base}\n" if base else f"scope={scope or 'working'}\n"
    (feature_dir / REVIEW_SCOPE_FILE).write_text(value, encoding="utf-8")


def read_review_scope(feature_dir: Path) -> tuple[str | None, str | None]:
    path = feature_dir / REVIEW_SCOPE_FILE
    if not path.exists():
        return "working", None
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    if values.get("base"):
        return None, values["base"]
    return values.get("scope") or "working", None


def join_diff_parts(parts: list[str]) -> str:
    return "\n\n".join(part for part in parts if part and part.strip())


def collect_untracked_files(repo: Path) -> str:
    result = git(repo, ["ls-files", "--others", "--exclude-standard"], check=True)
    paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not paths:
        return ""
    chunks = []
    repo_root = repo.resolve()
    for rel in paths:
        if rel == CONFIG_DIR or rel.startswith(f"{CONFIG_DIR}/"):
            continue
        path = repo / rel
        if path.is_symlink():
            chunks.append(f"## {rel}\nSkipped: symlink.")
            continue
        try:
            resolved = path.resolve()
            resolved.relative_to(repo_root)
        except ValueError:
            chunks.append(f"## {rel}\nSkipped: path is outside repository.")
            continue
        if not path.is_file():
            chunks.append(f"## {rel}\nSkipped: not a regular file.")
            continue
        size = path.stat().st_size
        if size > MAX_UNTRACKED_FILE_BYTES:
            chunks.append(f"## {rel}\nSkipped: file is {size} bytes, above {MAX_UNTRACKED_FILE_BYTES} byte limit.")
            continue
        data = path.read_bytes()
        if b"\x00" in data:
            chunks.append(f"## {rel}\nSkipped: binary file.")
            continue
        text = data.decode("utf-8", errors="replace")
        chunks.append(f"## {rel}\n\n```text\n{text}\n```")
    if not chunks:
        return ""
    return "# Untracked files\n\n" + "\n\n".join(chunks)


def run_model(
    repo: Path,
    config: dict[str, Any],
    model_id: str,
    prompt: str,
    stage: str,
    timeout: int,
    force_dangerous: bool = False,
    use_config_dangerous: bool = True,
) -> "RunResult":
    model = config["models"][model_id]
    env = os.environ.copy()
    for key, value in (model.get("env") or {}).items():
        env[key] = expand_env(str(value))
    cli = model["cli"]
    executable = shutil.which(cli, path=env.get("PATH"))
    if not executable:
        return RunResult(model_id, stage, 127, "", f"CLI not found: {cli}", cli)
    dangerous = (bool(model.get("dangerous")) if use_config_dangerous else False) or force_dangerous
    extra_args = model.get("args") or []
    if isinstance(extra_args, str):
        extra_args = [extra_args]
    prompt_file = write_runtime_prompt(repo, model_id, stage, prompt)
    prompt_arg = f"Read the full task prompt from {prompt_file} and follow it exactly. Return only the requested final output."

    if cli == "claude":
        cmd = [executable, "-p", prompt_arg, "--output-format", "text"]
        if model.get("model"):
            cmd.extend(["--model", str(model["model"])])
        if dangerous:
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(map(str, extra_args))
    elif cli == "codex":
        cmd = [executable, "exec", "--cd", str(repo)]
        if model.get("model"):
            cmd.extend(["--model", str(model["model"])])
        if dangerous:
            cmd.append("--dangerously-bypass-approvals-and-sandbox")
        cmd.extend(map(str, extra_args))
        cmd.append(prompt_arg)
    else:
        fail(f"Unsupported cli `{cli}`.")

    try:
        completed = subprocess.run(
            cmd,
            cwd=repo,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return RunResult(model_id, stage, completed.returncode, completed.stdout, completed.stderr, cmd_for_log(cmd))
    except FileNotFoundError:
        return RunResult(model_id, stage, 127, "", f"CLI not found: {cli}", cmd_for_log(cmd))
    except OSError as exc:
        return RunResult(model_id, stage, 126, "", f"CLI failed to start: {exc}", cmd_for_log(cmd))
    except subprocess.TimeoutExpired as exc:
        return RunResult(model_id, stage, 124, exc.stdout or "", exc.stderr or f"Timed out after {timeout}s", cmd_for_log(cmd))


def write_runtime_prompt(repo: Path, model_id: str, stage: str, prompt: str) -> Path:
    runtime_dir = repo / CONFIG_DIR / "runs"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    pid = os.getpid()
    path = runtime_dir / f"{safe_name(stage)}-{safe_name(model_id)}-{pid}.md"
    path.write_text(prompt, encoding="utf-8")
    return path


def make_feature_dirs(repo: Path, feature: str) -> Path:
    if not re.match(r"^[A-Za-z0-9._-]+$", feature):
        fail("Feature may only contain letters, numbers, dot, underscore, and dash.")
    feature_dir = repo / ARTIFACT_DIR / feature
    (feature_dir / "reviews").mkdir(parents=True, exist_ok=True)
    (feature_dir / "logs").mkdir(parents=True, exist_ok=True)
    return feature_dir


def write_agent_result(feature_dir: Path, subdir: str, model_id: str, result: "RunResult") -> None:
    safe = safe_name(model_id)
    write_log(feature_dir, model_id, result.stage, result)
    out_path = feature_dir / subdir / f"{safe}.md"
    if result.returncode == 0:
        out_path.write_text(clean_final_output(result.stdout), encoding="utf-8")
    else:
        out_path.write_text(f"# Review Failed\n\nModel: {model_id}\nExit: {result.returncode}\n\nSee logs/{safe}-{result.stage}.log\n", encoding="utf-8")


def write_log(feature_dir: Path, model_id: str, stage: str, result: "RunResult") -> None:
    safe = safe_name(model_id)
    path = feature_dir / "logs" / f"{safe}-{stage}.log"
    body = [
        f"model: {model_id}",
        f"stage: {stage}",
        f"exit: {result.returncode}",
        f"command: {result.command}",
        "",
        "STDERR:",
        result.stderr,
        "",
        "STDOUT:",
        result.stdout,
    ]
    path.write_text("\n".join(body), encoding="utf-8")


def append_status(feature_dir: Path, stage: str, model_id: str, stdout: str) -> None:
    status = feature_dir / "status.md"
    with status.open("a", encoding="utf-8") as f:
        f.write(f"\n\n## {stage.title()} - {model_id}\n\n")
        f.write(clean_final_output(stdout))
        f.write("\n")


def collect_reports(feature_dir: Path) -> str:
    chunks = []
    for path in sorted((feature_dir / "reviews").glob("*.md")):
        content = path.read_text(encoding="utf-8")
        if content.lstrip().startswith("# Review Failed"):
            print(f"Skipping failed review report: {path}")
            continue
        chunks.append(f"## {path.stem}\n\n{content}")
    return "\n\n".join(chunks)


def selected_summary_items(summary: str) -> str:
    lines = summary.splitlines()
    selected: list[str] = []
    current: list[str] = []
    capture = False
    for line in lines:
        if re.match(r"^\s*-\s*\[[xX]\]\s+", line):
            if current and capture:
                selected.extend(current)
                selected.append("")
            current = [line]
            capture = True
        elif re.match(r"^\s*-\s*\[ \]\s+", line):
            if current and capture:
                selected.extend(current)
                selected.append("")
            current = [line]
            capture = False
        elif current:
            current.append(line)
    if current and capture:
        selected.extend(current)
    return "\n".join(selected).strip()


def read_prompt(name: str) -> str:
    return (skill_root() / "prompts" / name).read_text(encoding="utf-8")


def read_required(path: Path) -> str:
    if not path.exists():
        fail(f"Missing required file: {path}")
    return path.read_text(encoding="utf-8")


def render(template: str, values: dict[str, str]) -> str:
    output = template
    for key, value in values.items():
        output = output.replace("{{" + key + "}}", value)
    return output


def git(repo: Path, args: list[str], check: bool) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", "--no-pager", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and completed.returncode != 0:
        fail(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed


def clean_final_output(text: str) -> str:
    return text.strip() + "\n"


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def expand_env(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return os.environ.get(match.group(1), "")
    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", replace, value)


def cmd_for_log(cmd: list[str]) -> str:
    redacted = []
    skip_next = False
    for item in cmd:
        if skip_next:
            redacted.append("<prompt>")
            skip_next = False
            continue
        redacted.append(item)
        if item in {"-p"}:
            skip_next = True
    if len(redacted) > 0 and redacted[-1].startswith("You "):
        redacted[-1] = "<prompt>"
    return " ".join(redacted)


class RunResult:
    def __init__(self, model_id: str, stage: str, returncode: int, stdout: str, stderr: str, command: str) -> None:
        self.model_id = model_id
        self.stage = stage
        self.returncode = returncode
        self.stdout = stdout or ""
        self.stderr = stderr or ""
        self.command = command


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the small YAML subset used by config.local.yaml.

    Supports nested mappings, lists of scalars, booleans, nulls, and strings.
    Use PyYAML if available; this fallback keeps the runner dependency-light.
    """
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(text)
        return loaded or {}
    except Exception:
        pass

    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    last_key_at_indent: dict[int, tuple[dict[str, Any], str]] = {}

    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()

        if line.startswith("- "):
            while stack and indent < stack[-1][0]:
                stack.pop()
            parent = stack[-1][1]
            value = parse_scalar(line[2:].strip())
            if not isinstance(parent, list):
                holder = last_key_at_indent.get(indent)
                if not holder:
                    raise ValueError(f"List item without key: {raw}")
                mapping, key = holder
                existing = mapping.get(key)
                if isinstance(existing, list):
                    parent = existing
                else:
                    mapping[key] = []
                    parent = mapping[key]
                if stack[-1][1] is not parent:
                    stack.append((indent, parent))
            parent.append(value)
            continue

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if ":" not in line:
            raise ValueError(f"Invalid config line: {raw}")
        key, value_text = line.split(":", 1)
        key = key.strip()
        value_text = value_text.strip()
        if not isinstance(parent, dict):
            raise ValueError(f"Mapping under non-mapping: {raw}")
        if value_text == "":
            parent[key] = {}
            last_key_at_indent[indent + 2] = (parent, key)
            stack.append((indent, parent[key]))
        else:
            parent[key] = parse_scalar(value_text)
            last_key_at_indent[indent + 2] = (parent, key)
    return root


def parse_scalar(value: str) -> Any:
    if value in {"", "null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    raise SystemExit(main())
