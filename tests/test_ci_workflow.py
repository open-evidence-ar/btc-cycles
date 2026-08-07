"""I-15 validation gate: CI workflow orchestrates data + chart + site rebuild.

Validates `.github/workflows/ci.yml` structurally via substring checks (mirrors
the style of `test_repo_skeleton::test_deploy_workflow_valid_yaml`). No PyYAML
dependency is required so the gate runs in any clean Python environment.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"


def _read_ci() -> str:
    assert CI_YML.is_file(), f"Missing CI workflow: {CI_YML}"
    return CI_YML.read_text(encoding="utf-8")


def test_ci_workflow_exists():
    assert CI_YML.is_file(), f"Missing CI workflow: {CI_YML}"
    content = _read_ci()
    assert content.startswith("name: CI")


def test_ci_triggers_on_push_and_pr():
    content = _read_ci()
    assert "push:" in content, "CI must trigger on push"
    assert "pull_request:" in content, "CI must trigger on pull_request"


def test_ci_sets_up_python_and_ruby():
    content = _read_ci()
    assert "setup-python" in content, "CI must set up Python"
    assert "setup-ruby" in content, "CI must set up Ruby for Jekyll"


def test_ci_runs_pytest_gate_suite():
    content = _read_ci()
    assert "pytest" in content, "CI must run pytest"
    assert "tests/" in content, "pytest must target tests/"


def test_ci_reruns_all_build_scripts():
    """CI must re-run every build_*.py + align_to_halving.py to prove
    that all artifacts downstream of I-05 are reproducible from I-02..I-04 raw.
    Includes I-17 alt-timing scripts (post-v1 extension)."""
    content = _read_ci()
    expected_scripts = [
        "build_cycle_metrics.py",
        "align_to_halving.py",
        "build_correlations_phase.py",
        "build_rolling_corr.py",
        "build_forward_ranges.py",
        "build_next_cycle_zones.py",
        "build_backtest.py",
        "build_regime_robustness.py",
        "build_alt_cycle_metrics.py",
        "build_alt_forward_ranges.py",
        "build_alt_next_cycle_zones.py",
        "build_charts.py",
    ]
    missing = [s for s in expected_scripts if s not in content]
    assert not missing, f"CI missing re-run steps for: {missing}"


def test_ci_builds_jekyll_site():
    content = _read_ci()
    assert "jekyll build" in content, "CI must build the Jekyll site"


def test_ci_generates_integrity_hash():
    content = _read_ci()
    assert "sha256sum" in content, "CI must compute SHA-256 integrity"
    assert "integrity" in content.lower(), "CI must write integrity file"


def test_ci_caches_raw_data_by_manifest():
    content = _read_ci()
    assert "actions/cache" in content, "CI must use actions/cache"
    assert "data/raw" in content, "cache path must be data/raw"
    assert "manifest.txt" in content, "cache key must depend on manifest SHA"


def test_ci_has_timeout_minutes():
    lines = _read_ci().splitlines()
    timeout_lines = [ln for ln in lines if "timeout-minutes" in ln]
    assert len(timeout_lines) >= 1, "CI jobs must declare timeout-minutes"


def test_requirements_complete():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    for pkg in ["pandas", "numpy", "plotly", "kaleido", "pytest", "requests"]:
        assert pkg in req, f"requirements.txt missing {pkg}"


def test_increments_data_file_present():
    yml = ROOT / "_data" / "increments.yml"
    assert yml.is_file(), "_data/increments.yml required by DESIGN.md §10.3 status board"
    text = yml.read_text(encoding="utf-8")
    for i in range(17):
        assert f"I-{i:02d}" in text, f"increments.yml missing I-{i:02d}"


def test_ci_reverifies_gates_after_regen():
    """After regenerating artifacts, CI must re-run the pytest gate suite to
    prove reproducibility (bit-identical output re-passes the same gates)."""
    content = _read_ci()
    pytest_runs = content.count("pytest")
    assert pytest_runs >= 2, (
        f"CI must run pytest at least twice (pre+post regen); found {pytest_runs}"
    )
