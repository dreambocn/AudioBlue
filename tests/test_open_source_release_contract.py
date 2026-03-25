"""覆盖开源发布物与仓库元数据的基础契约。"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
LICENSE_PATH = REPO_ROOT / "LICENSE"
DEVELOPMENT_DOC_PATH = REPO_ROOT / "docs" / "DEVELOPMENT.md"
RELEASING_DOC_PATH = REPO_ROOT / "docs" / "RELEASING.md"
PLANS_DIR_PATH = REPO_ROOT / "docs" / "plans"
RELEASE_SCRIPT_PATH = REPO_ROOT / "scripts" / "build-release.ps1"
RELEASE_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "release.yml"


def read_text(path: Path) -> str:
    assert path.exists(), f"Expected file to exist: {path}"
    return path.read_text(encoding="utf-8")


def test_open_source_files_exist_and_internal_plans_are_removed():
    assert LICENSE_PATH.exists()
    assert DEVELOPMENT_DOC_PATH.exists()
    assert RELEASING_DOC_PATH.exists()
    assert not PLANS_DIR_PATH.exists()


def test_license_uses_mit_text():
    content = read_text(LICENSE_PATH)

    assert "MIT License" in content
    assert "Permission is hereby granted, free of charge" in content


def test_readme_uses_github_friendly_open_source_structure():
    content = read_text(README_PATH)

    for expected in (
        "[![License]",
        "[![Release]",
        "[![Platform]",
        "dreambocn/AudioBlue",
        "## Highlights",
        "## Architecture",
        "## Quick Start",
        "## Development",
        "## Packaging & Release",
        "## FAQ",
        "## License",
        "docs/DEVELOPMENT.md",
        "docs/RELEASING.md",
        "ysc3839/AudioPlaybackConnector",
    ):
        assert expected in content


def test_release_script_contains_expected_release_steps():
    content = read_text(RELEASE_SCRIPT_PATH)

    for expected in (
        "param(",
        "uv sync --frozen --all-groups",
        "npm ci",
        "uv run pytest -q",
        "npm test",
        "npm run build",
        "uv run pyinstaller AudioBlue.spec --noconfirm",
        "verify_packaging_assets.py",
        "AudioBlue.iss",
        "AudioBlue-Setup.exe",
        "pyproject.toml",
    ):
        assert expected in content

    assert "SHA256SUMS.txt" not in content


def test_release_workflow_uses_tag_trigger_windows_runner_and_release_upload():
    content = read_text(RELEASE_WORKFLOW_PATH)

    for expected in (
        "push:",
        "tags:",
        "v*",
        "windows-latest",
        "actions/checkout",
        "actions/setup-python",
        "astral-sh/setup-uv",
        "actions/setup-node",
        "choco install innosetup",
        "build-release.ps1",
        "softprops/action-gh-release",
        "contents: write",
    ):
        assert expected in content

    assert "SHA256SUMS.txt" not in content


def test_releasing_doc_describes_installer_only_output():
    content = read_text(RELEASING_DOC_PATH)

    assert "AudioBlue-Setup.exe" in content
    assert "SHA256SUMS.txt" not in content
