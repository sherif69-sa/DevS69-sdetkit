from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

_ISO_TS = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\b")


def _run(tool_root: Path, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tool_root / "src")
    env["PYTHONHASHSEED"] = "0"
    return subprocess.run(
        [sys.executable, "-m", "sdetkit", "repo", *args],
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
    )


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, text=True, capture_output=True)


def _mk_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "toy_repo"
    repo.mkdir()

    (repo / "requirements.txt").write_text("requests>=2\n", encoding="utf-8")
    (repo / "README.md").write_text("# toy\n", encoding="utf-8")

    _git(repo, "init")
    _git(repo, "add", ".")
    subprocess.run(
        ["git", "-c", "user.name=toy", "-c", "user.email=toy@example.com", "commit", "-m", "init"],
        cwd=str(repo),
        check=True,
        text=True,
        capture_output=True,
    )
    return repo


def _norm_text(s: str, root: Path) -> str:
    x = s.replace(str(root), "<ROOT>")
    x = re.sub(r"<ROOT>/+", "<ROOT>/", x)
    x = _ISO_TS.sub("<TIME>", x)
    return x


def _scrub_obj(obj, *, drop_stats: bool, _path: tuple[str, ...] = ()):
    if isinstance(obj, dict):
        out: dict = {}
        for k, v in obj.items():
            ks = str(k)

            kl = ks.lower().replace("-", "_")
            if kl in {"generated_at", "created_at", "updated_at", "timestamp"}:
                out[ks] = "<TIME>"
                continue

            if drop_stats:
                if _path == () and kl == "cache_stats":
                    continue
                if _path == ("summary",) and kl in {"cache", "incremental"}:
                    continue

            out[ks] = _scrub_obj(v, drop_stats=drop_stats, _path=_path + (kl,))
        return out

    if isinstance(obj, list):
        return [_scrub_obj(x, drop_stats=drop_stats, _path=_path) for x in obj]

    if isinstance(obj, str):
        if _ISO_TS.search(obj):
            return _ISO_TS.sub("<TIME>", obj)
        return obj

    return obj


def _parse_json(proc: subprocess.CompletedProcess[str]) -> dict:
    assert proc.stdout.strip(), "expected stdout"
    return json.loads(proc.stdout)


def _cache_totals(payload: dict) -> tuple[int, int]:
    if isinstance(payload.get("cache_stats"), dict):
        rules = payload["cache_stats"].get("rules") or {}
        hit = sum(int(v.get("hit", 0)) for v in rules.values() if isinstance(v, dict))
        miss = sum(int(v.get("miss", 0)) for v in rules.values() if isinstance(v, dict))
        return hit, miss

    summ = payload.get("summary") or {}
    cache = summ.get("cache") or {}
    hits = cache.get("hits") or {}
    misses = cache.get("misses") or {}
    hit = sum(int(v) for v in hits.values() if isinstance(v, int))
    miss = sum(int(v) for v in misses.values() if isinstance(v, int))
    return hit, miss


def test_repo_audit_changed_only_cache_hit_and_invalidation(tmp_path: Path) -> None:
    tool_root = Path(__file__).resolve().parents[1]
    repo = _mk_repo(tmp_path)

    p1 = _run(
        tool_root,
        repo,
        "audit",
        ".",
        "--profile",
        "enterprise",
        "--format",
        "json",
        "--changed-only",
        "--cache-stats",
        "--fail-on",
        "none",
    )
    assert p1.returncode == 0, p1.stderr
    j1 = _parse_json(p1)
    h1, m1 = _cache_totals(j1)
    assert m1 >= 0

    p2 = _run(
        tool_root,
        repo,
        "audit",
        ".",
        "--profile",
        "enterprise",
        "--format",
        "json",
        "--changed-only",
        "--cache-stats",
        "--fail-on",
        "none",
    )
    assert p2.returncode == 0, p2.stderr
    j2 = _parse_json(p2)
    h2, m2 = _cache_totals(j2)

    assert h2 >= h1
    assert m2 <= m1

    (repo / "requirements.txt").write_text("requests==2.0.0\n", encoding="utf-8")

    p3 = _run(
        tool_root,
        repo,
        "audit",
        ".",
        "--profile",
        "enterprise",
        "--format",
        "json",
        "--changed-only",
        "--cache-stats",
        "--fail-on",
        "none",
    )
    assert p3.returncode == 0, p3.stderr
    j3 = _parse_json(p3)
    h3, m3 = _cache_totals(j3)

    assert m3 >= m2
    assert h3 <= h2


def test_repo_check_export_formats_are_stable(tmp_path: Path) -> None:
    tool_root = Path(__file__).resolve().parents[1]
    repo = _mk_repo(tmp_path)

    for fmt in ["json", "sarif", "md", "html"]:
        p1 = _run(tool_root, repo, "check", ".", "--profile", "enterprise", "--format", fmt)
        p2 = _run(tool_root, repo, "check", ".", "--profile", "enterprise", "--format", fmt)

        assert p1.returncode in (0, 1), p1.stderr
        assert p2.returncode in (0, 1), p2.stderr

        if fmt in ("json", "sarif"):
            j1 = _scrub_obj(json.loads(p1.stdout), drop_stats=True)
            j2 = _scrub_obj(json.loads(p2.stdout), drop_stats=True)
            t1 = _norm_text(json.dumps(j1, sort_keys=True), repo)
            t2 = _norm_text(json.dumps(j2, sort_keys=True), repo)
            assert t1 == t2
        else:
            t1 = _norm_text(p1.stdout, repo)
            t2 = _norm_text(p2.stdout, repo)
            assert t1 == t2
            if fmt == "html":
                assert "<html" in t1.lower()


def test_repo_audit_export_formats_are_stable(tmp_path: Path) -> None:
    tool_root = Path(__file__).resolve().parents[1]
    repo = _mk_repo(tmp_path)

    for fmt in ["json", "sarif", "md", "html"]:
        p1 = _run(
            tool_root,
            repo,
            "audit",
            ".",
            "--profile",
            "enterprise",
            "--format",
            fmt,
            "--changed-only",
            "--fail-on",
            "none",
        )
        p2 = _run(
            tool_root,
            repo,
            "audit",
            ".",
            "--profile",
            "enterprise",
            "--format",
            fmt,
            "--changed-only",
            "--fail-on",
            "none",
        )

        assert p1.returncode == 0, p1.stderr
        assert p2.returncode == 0, p2.stderr

        if fmt in ("json", "sarif"):
            j1 = _scrub_obj(json.loads(p1.stdout), drop_stats=True)
            j2 = _scrub_obj(json.loads(p2.stdout), drop_stats=True)
            t1 = _norm_text(json.dumps(j1, sort_keys=True), repo)
            t2 = _norm_text(json.dumps(j2, sort_keys=True), repo)
            assert t1 == t2
        else:
            t1 = _norm_text(p1.stdout, repo)
            t2 = _norm_text(p2.stdout, repo)
            assert t1 == t2
            if fmt == "html":
                assert "<html" in t1.lower()
