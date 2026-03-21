from __future__ import annotations

from pathlib import Path

import pytest

import sdetkit.projects as projects
from sdetkit.projects import discover_projects


def _w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_discover_projects_empty_repo_returns_none_and_empty(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    source, items = discover_projects(repo)
    assert source is None
    assert items == []


def test_autodiscover_skips_invalid_metadata_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    _w(
        repo / "packages" / "good" / "pyproject.toml",
        '[project]\nname = "good-pkg"\nversion = "0.0.0"\n',
    )

    bad = repo / "packages" / "bad"
    _w(bad / "pyproject.toml", "not toml\n")
    _w(bad / "package.json", "{")
    _w(bad / "Cargo.toml", "not = toml =\n")

    _, items = discover_projects(repo, sort=True)
    assert [(p.name, p.root) for p in items] == [("good-pkg", "packages/good")]


def test_autodiscover_go_mod_skips_comments_and_breaks_on_non_module(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    ok = repo / "apps" / "ok"
    _w(
        ok / "go.mod",
        "// c\n\nmodule example.com/ok\n\ngo 1.22\n",
    )

    nope = repo / "apps" / "nope"
    _w(
        nope / "go.mod",
        "// c\n\ngo 1.22\nmodule example.com/late\n",
    )

    _, items = discover_projects(repo, sort=True)
    assert [(p.name, p.root) for p in items] == [("example.com/ok", "apps/ok")]


def test_autodiscover_gradle_ignores_comments_and_requires_match(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    bad = repo / "apps" / "gradle-bad"
    _w(bad / "settings.gradle", "// c\ninclude('x')\n")

    source, items = discover_projects(repo, sort=True)
    assert source is None
    assert items == []


def test_autodiscover_hatch_metadata_name_is_detected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    hatch = repo / "packages" / "hatchy"
    _w(
        hatch / "pyproject.toml",
        "[tool.hatch.metadata]\nname = 'hatch-name'\n",
    )

    _, items = discover_projects(repo, sort=True)
    assert [(p.name, p.root) for p in items] == [("hatch-name", "packages/hatchy")]


def test_projects_toml_empty_manifest_returns_source_empty_list(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    _w(repo / ".sdetkit" / "projects.toml", "autodiscover = false\n")

    source, items = discover_projects(repo, sort=True)
    assert source == ".sdetkit/projects.toml"
    assert items == []


def test_projects_toml_project_field_requires_array_of_tables(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    _w(repo / ".sdetkit" / "projects.toml", "project = 'x'\n")

    with pytest.raises(ValueError, match="\\[\\[project\\]\\]"):
        discover_projects(repo)


def test_projects_toml_requires_name_and_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    _w(
        repo / ".sdetkit" / "projects.toml",
        "[[project]]\nname = 'x'\n",
    )

    with pytest.raises(ValueError, match="require 'name' and 'root'"):
        discover_projects(repo)


def test_projects_toml_duplicate_name_is_rejected(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    _w(
        repo / ".sdetkit" / "projects.toml",
        "[[project]]\nname='x'\nroot='a'\n\n[[project]]\nname='x'\nroot='b'\n",
    )

    with pytest.raises(ValueError, match="duplicate project name: x"):
        discover_projects(repo)


def test_projects_toml_profile_must_be_string(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    _w(
        repo / ".sdetkit" / "projects.toml",
        "[[project]]\nname='x'\nroot='a'\nprofile=1\n",
    )

    with pytest.raises(ValueError, match="must be a string"):
        discover_projects(repo)


def test_projects_toml_packs_must_be_list_or_csv(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    _w(
        repo / ".sdetkit" / "projects.toml",
        "[[project]]\nname='x'\nroot='a'\npacks=1\n",
    )

    with pytest.raises(ValueError, match="list of strings or csv"):
        discover_projects(repo)


@pytest.mark.parametrize(
    "root_value, msg",
    [
        ("/abs", "must be relative"),
        ("../x", "cannot contain traversal"),
    ],
)
def test_projects_toml_root_validation_relative_and_no_traversal(
    tmp_path: Path, root_value: str, msg: str
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    _w(
        repo / ".sdetkit" / "projects.toml",
        f"[[project]]\nname='x'\nroot='{root_value}'\n",
    )

    with pytest.raises(ValueError, match=msg):
        discover_projects(repo)


def test_projects_toml_packs_csv_and_sort_true_sorts_by_name(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    _w(
        repo / ".sdetkit" / "projects.toml",
        "[[project]]\nname='b'\nroot='services/b'\npacks=' security,quality '\n\n"
        "[[project]]\nname='a'\nroot='services/a'\n",
    )

    source, items = discover_projects(repo, sort=True)
    assert source == ".sdetkit/projects.toml"
    assert [p.name for p in items] == ["a", "b"]
    assert items[1].packs == ("security", "quality")


def test_autodiscover_xml_parsers_execute_when_safe_et_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import xml.etree.ElementTree as et

    monkeypatch.setattr(projects, "_safe_et", et)
    monkeypatch.setattr(projects, "_XML_PARSE_ERRORS", (et.ParseError, AttributeError, ValueError))

    repo = tmp_path / "repo"
    repo.mkdir()

    _w(
        repo / "services" / "billing" / "pom.xml",
        "<project><artifactId>billing-svc</artifactId></project>\n",
    )
    _w(
        repo / "libs" / "payments" / "Payments.csproj",
        "<Project><PropertyGroup><AssemblyName>Acme.Payments</AssemblyName></PropertyGroup></Project>\n",
    )

    source, items = discover_projects(repo, sort=True)
    assert source == "autodiscover"
    assert [(p.name, p.root) for p in items] == [
        ("Acme.Payments", "libs/payments"),
        ("billing-svc", "services/billing"),
    ]


def test_infer_project_kind_ignores_disappearing_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    project_dir = repo / "services" / "api"
    project_dir.mkdir(parents=True)

    original_exists = Path.exists
    original_iterdir = Path.iterdir
    seen_iterdir = False

    def fake_iterdir(self: Path):
        nonlocal seen_iterdir
        if self == project_dir and not seen_iterdir:
            seen_iterdir = True
            raise FileNotFoundError("directory disappeared during scan")
        return original_iterdir(self)

    def fake_exists(self: Path) -> bool:
        if self == project_dir and seen_iterdir:
            return False
        return original_exists(self)

    monkeypatch.setattr(Path, "iterdir", fake_iterdir)
    monkeypatch.setattr(Path, "exists", fake_exists)

    assert projects._infer_project_kind(repo, "services/api", None) is None
