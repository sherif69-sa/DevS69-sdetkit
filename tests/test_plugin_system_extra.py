from __future__ import annotations

from pathlib import Path

from sdetkit import plugin_system as ps


class _EP:
    def __init__(self, name, value, boom=False):
        self.name = name
        self._value = value
        self._boom = boom

    def load(self):
        if self._boom:
            raise RuntimeError("bad")
        return self._value


class _EPSet(list):
    def select(self, *, group: str):
        return self


def test_load_ref_and_registry_entries(tmp_path: Path) -> None:
    f = ps._load_ref("json:loads")
    assert f('{"a":1}')["a"] == 1

    cfg = tmp_path / ".sdetkit/plugins.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        """
[plugins]
ok = "json:loads"
bad = "oops"
num = 1
""".strip()
        + "\n",
        encoding="utf-8",
    )
    entries = ps._registry_entries(tmp_path, "plugins")
    assert [e.name for e in entries] == ["ok"]


def test_discover_entrypoints_and_registry_dedupe(monkeypatch, tmp_path: Path) -> None:
    eps = _EPSet(
        [
            _EP("a", lambda: "entry-a"),
            _EP("b", 7),
            _EP("z", None, boom=True),
        ]
    )
    monkeypatch.setattr(ps.metadata, "entry_points", lambda: eps)

    cfg = tmp_path / ".sdetkit/plugins.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text('[plugins]\na = "json:loads"\nc = "json:dumps"\n', encoding="utf-8")

    records = ps.discover("g", "plugins", root=tmp_path)
    names = [r.name for r in records]
    assert names == ["a", "b", "c"]
    # registry dedupe should override entrypoint for same name "a"
    assert records[0].source == "registry"
