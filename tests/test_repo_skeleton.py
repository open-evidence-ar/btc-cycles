"""I-00 validation gate: repo skeleton builds cleanly."""

import platform
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_required_files_exist():
    required = [
        "_config.yml",
        "Gemfile",
        "index.md",
        "_layouts/default.html",
        ".github/workflows/deploy.yml",
        "AGENTS.md",
        "README.md",
    ]
    for rel in required:
        assert (ROOT / rel).is_file(), f"Missing required file: {rel}"


def test_stub_directories_exist():
    dirs = [
        "sections",
        "_data",
        "_includes",
        "data/raw",
        "data/processed",
        "scripts",
        "notebooks",
        "assets/charts",
        "assets/css",
    ]
    for rel in dirs:
        assert (ROOT / rel).is_dir(), f"Missing required directory: {rel}"


def test_jekyll_build_succeeds():
    bundle = shutil.which("bundle")
    assert bundle is not None, "bundle not found on PATH; run `bundle install` first"
    use_shell = platform.system() == "Windows"
    result = subprocess.run(
        "bundle exec jekyll build" if use_shell else [bundle, "exec", "jekyll", "build"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        shell=use_shell,
    )
    assert result.returncode == 0, f"jekyll build failed:\n{result.stderr}"


def test_deploy_workflow_valid_yaml():
    deploy = ROOT / ".github" / "workflows" / "deploy.yml"
    content = deploy.read_text(encoding="utf-8")
    assert "jekyll build" in content
    assert "deploy-pages" in content
