import subprocess
import re
from pathlib import Path

SECTIONS_DIR = Path('_sections')
CHARTS_DIR = Path('assets/charts')


def test_jekyll_build():
    """Jekyll build should succeed (skipped if bundle not available)."""
    try:
        result = subprocess.run(
            ['bundle', 'exec', 'jekyll', 'build'],
            capture_output=True, text=True, timeout=120,
        )
    except (FileNotFoundError, OSError):
        return  # skip — Ruby/Jekyll not installed on this system
    assert result.returncode == 0, f"Jekyll build failed:\n{result.stderr}"


def test_sections_exist():
    """All expected section files should exist."""
    expected = [
        'methodology.md',
        'cycle-anatomy.md',
        'cross-asset.md',
        'predictive-ranges.md',
        'validation.md',
    ]
    for name in expected:
        path = SECTIONS_DIR / name
        assert path.exists(), f"Missing section: {path}"


def test_sections_have_chart_references():
    """Each section (except non-chart pages) should have at least one chart reference."""
    skip = {'methodology.md', 'release-checklist.md', 'theory.md', 'validation.md', 'cycle-anatomy.md'}
    for path in SECTIONS_DIR.glob('*.md'):
        if path.name in skip:
            continue
        content = path.read_text(encoding='utf-8')
        has_chart = 'chart.html' in content
        assert has_chart, f"{path.name} has no chart references"


def test_chart_refs_resolve():
    """Chart references in sections should resolve to existing files."""
    for path in SECTIONS_DIR.glob('*.md'):
        content = path.read_text(encoding='utf-8')
        chart_ids = re.findall(r'id="C(\d)"', content)
        for cid in chart_ids:
            html = CHARTS_DIR / f'C{cid}.html'
            assert html.exists(), f"{path.name} references C{cid} but {html} not found"


def test_provenance_footer_present():
    """Each section should have a provenance or data-source footer line."""
    for path in SECTIONS_DIR.glob('*.md'):
        content = path.read_text(encoding='utf-8')
        has_footer = ('manifest.txt' in content or
                      'data/processed' in content or
                      'data/raw' in content)
        assert has_footer, f"{path.name} missing provenance footer"


def test_no_broken_internal_links():
    """No broken internal links (basic check)."""
    for path in SECTIONS_DIR.glob('*.md'):
        content = path.read_text(encoding='utf-8')
        # Check for empty hrefs
        assert 'href=""' not in content, f"{path.name} has empty href"
        assert 'href=""' not in content, f"{path.name} has empty href"


if __name__ == '__main__':
    test_sections_exist()
    print("PASS: test_sections_exist")
    test_sections_have_chart_references()
    print("PASS: test_sections_have_chart_references")
    test_chart_refs_resolve()
    print("PASS: test_chart_refs_resolve")
    test_provenance_footer_present()
    print("PASS: test_provenance_footer_present")
    test_no_broken_internal_links()
    print("PASS: test_no_broken_internal_links")
    test_jekyll_build()
    print("PASS: test_jekyll_build")
    print("\nALL TESTS PASSED!")
