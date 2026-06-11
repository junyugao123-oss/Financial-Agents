from pathlib import Path

from app.settings import ROOT_DIR, Settings, _find_project_root


def test_settings_root_dir_resolves_current_workspace():
    assert ROOT_DIR.exists()
    assert Settings().model_config["env_file"] == ROOT_DIR / ".env"


def test_find_project_root_handles_flat_container_layout(tmp_path):
    api_root = tmp_path / "app"
    package_dir = api_root / "app"
    package_dir.mkdir(parents=True)
    (api_root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    settings_file = package_dir / "settings.py"
    settings_file.write_text("# simulated container path\n", encoding="utf-8")

    assert _find_project_root(settings_file) == api_root


def test_find_project_root_prefers_monorepo_root(tmp_path):
    root = tmp_path / "repo"
    api_root = root / "services" / "api"
    package_dir = api_root / "app"
    package_dir.mkdir(parents=True)
    (root / "package.json").write_text("{}", encoding="utf-8")
    (api_root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

    assert _find_project_root(package_dir / "settings.py") == root
