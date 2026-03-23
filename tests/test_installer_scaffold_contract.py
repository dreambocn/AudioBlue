from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INNO_SCRIPT_PATH = REPO_ROOT / "installer" / "AudioBlue.iss"


def read_inno_script() -> str:
    assert INNO_SCRIPT_PATH.exists(), (
        "Expected installer scaffold at installer/AudioBlue.iss. "
        "Add an Inno Setup script skeleton for packaging verification."
    )
    return INNO_SCRIPT_PATH.read_text(encoding="utf-8")


def test_inno_scaffold_contains_required_sections():
    content = read_inno_script()

    for section in ("[Setup]", "[Tasks]", "[Files]", "[Registry]", "[Icons]", "[Run]"):
        assert section in content


def test_inno_scaffold_declares_expected_tasks_and_defaults():
    content = read_inno_script()

    assert 'Name: "startmenu"' in content
    assert 'Name: "autostart"' in content
    assert 'Name: "desktopicon"' in content
    assert 'Name: "desktopicon";' in content and "Flags: unchecked" in content


def test_inno_scaffold_wires_background_autostart_command():
    content = read_inno_script()

    assert r"Software\Microsoft\Windows\CurrentVersion\Run" in content
    assert "--background" in content
    assert 'Filename: "{app}\\audioblue.exe"' in content


def test_inno_scaffold_uses_repo_root_relative_dist_paths():
    content = read_inno_script()

    assert 'OutputDir=..\\dist\\installer' in content
    assert 'Source: "..\\dist\\AudioBlue\\*"' in content
