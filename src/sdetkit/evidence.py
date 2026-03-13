from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.evidence.v2"
EXIT_OK = 0
EXIT_INVALID = 2


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2) + "\n"


def _zip_deterministic(output: Path, files: list[Path], base: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fp in sorted(files, key=lambda p: p.as_posix()):
            rel = fp.relative_to(base).as_posix()
            info = zipfile.ZipInfo(rel)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, fp.read_bytes())


def _load_manifest_from_zip(pack: Path) -> dict[str, Any]:
    with zipfile.ZipFile(pack, "r") as zf:
        payload = zf.read("manifest.json").decode("utf-8")
    loaded: Any = json.loads(payload)
    if not isinstance(loaded, dict):
        return {}
    return loaded


def _pack(output: Path, *, redacted: bool) -> int:
    out_dir = Path(".sdetkit/out")
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in [
        "doctor.txt",
        "repo-audit.json",
        "security.sarif",
        "sbom.cdx.json",
        "policy-snapshot.json",
        "policy-diff.json",
        "manifest.json",
        "evidence-errors.log",
    ]:
        target = out_dir / name
        if target.exists():
            target.unlink()

    commands = [
        (
            ["python3", "-m", "sdetkit", "doctor", "--ascii", "--format", "json"],
            out_dir / "doctor.txt",
        ),
        (
            [
                "python3",
                "-m",
                "sdetkit",
                "repo",
                "audit",
                ".",
                "--format",
                "json",
                "--fail-on",
                "none",
                "--output",
                str(out_dir / "repo-audit.json"),
            ],
            None,
        ),
        (
            [
                "python3",
                "-m",
                "sdetkit",
                "security",
                "scan",
                "--fail-on",
                "none",
                "--format",
                "sarif",
                "--output",
                str(out_dir / "security.sarif"),
                "--sbom-output",
                str(out_dir / "sbom.cdx.json"),
            ],
            None,
        ),
        (
            [
                "python3",
                "-m",
                "sdetkit",
                "policy",
                "snapshot",
                "--output",
                str(out_dir / "policy-snapshot.json"),
            ],
            None,
        ),
    ]

    for cmd, capture_path in commands:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if capture_path is not None:
            capture_path.write_text((proc.stdout or "") + (proc.stderr or ""), encoding="utf-8")
        if proc.returncode != 0:
            err_log = out_dir / "evidence-errors.log"
            prefix = err_log.read_text(encoding="utf-8") if err_log.exists() else ""
            err_log.write_text(prefix + f"failed: {' '.join(cmd)}\n", encoding="utf-8")

    baseline = Path(".sdetkit/policies/baseline.json")
    if baseline.is_file():
        proc = subprocess.run(
            [
                "python3",
                "-m",
                "sdetkit",
                "policy",
                "diff",
                "--baseline",
                str(baseline),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        (out_dir / "policy-diff.json").write_text(proc.stdout, encoding="utf-8")

    files = [
        p
        for p in out_dir.iterdir()
        if p.is_file() and p.name != "manifest.json" and p.name != output.name
    ]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "version": 2,
        "redacted": redacted,
        "files": [{"path": p.name, "sha256": _sha(p)} for p in sorted(files, key=lambda i: i.name)],
    }
    (out_dir / "manifest.json").write_text(_stable_json(manifest), encoding="utf-8")
    files.append(out_dir / "manifest.json")

    _zip_deterministic(output, files, out_dir)
    sys.stdout.write(output.as_posix() + "\n")
    return EXIT_OK


def _validate(pack: Path, *, format: str) -> int:
    if not pack.is_file():
        payload = {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "error": {"code": "pack_missing", "message": str(pack)},
        }
        if format == "json":
            sys.stdout.write(_stable_json(payload))
        else:
            sys.stdout.write(f"pack not found: {pack}\n")
        return EXIT_INVALID

    manifest = _load_manifest_from_zip(pack)
    failures: list[dict[str, str]] = []
    with zipfile.ZipFile(pack, "r") as zf:
        names = sorted(zf.namelist())
        for item in manifest.get("files", []):
            p = item["path"]
            if p not in names:
                failures.append({"path": p, "code": "missing_file"})
                continue
            actual = hashlib.sha256(zf.read(p)).hexdigest()
            if actual != item.get("sha256"):
                failures.append({"path": p, "code": "checksum_mismatch"})

    payload = {
        "schema_version": SCHEMA_VERSION,
        "ok": not failures,
        "pack": pack.as_posix(),
        "failures": failures,
    }
    if format == "json":
        sys.stdout.write(_stable_json(payload))
    else:
        if failures:
            for f in failures:
                sys.stdout.write(f"FAIL {f['code']}: {f['path']}\n")
        else:
            sys.stdout.write("OK evidence pack validated\n")
    return EXIT_OK if not failures else EXIT_INVALID


def _compare(left: Path, right: Path, *, format: str) -> int:
    lmf = _load_manifest_from_zip(left)
    rmf = _load_manifest_from_zip(right)
    lmap = {i["path"]: i["sha256"] for i in lmf.get("files", [])}
    rmap = {i["path"]: i["sha256"] for i in rmf.get("files", [])}
    added = sorted(set(rmap) - set(lmap))
    removed = sorted(set(lmap) - set(rmap))
    changed = sorted(p for p in (set(lmap) & set(rmap)) if lmap[p] != rmap[p])
    payload = {
        "schema_version": SCHEMA_VERSION,
        "left": left.as_posix(),
        "right": right.as_posix(),
        "added": added,
        "removed": removed,
        "changed": changed,
        "ok": not (added or removed or changed),
    }
    if format == "json":
        sys.stdout.write(_stable_json(payload))
    else:
        sys.stdout.write(f"added={len(added)} removed={len(removed)} changed={len(changed)}\n")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sdetkit evidence")
    sub = p.add_subparsers(dest="cmd", required=True)

    pack = sub.add_parser("pack")
    pack.add_argument("--output", default=".sdetkit/out/evidence.zip")
    pack.add_argument(
        "--redacted",
        action="store_true",
        help="Mark pack as redacted in manifest provenance metadata.",
    )

    validate = sub.add_parser("validate")
    validate.add_argument("pack")
    validate.add_argument("--format", choices=["text", "json"], default="text")

    compare = sub.add_parser("compare")
    compare.add_argument("left")
    compare.add_argument("right")
    compare.add_argument("--format", choices=["text", "json"], default="text")

    ns = p.parse_args(argv)
    if ns.cmd == "pack":
        return _pack(Path(ns.output), redacted=bool(ns.redacted))
    if ns.cmd == "validate":
        return _validate(Path(ns.pack), format=ns.format)
    return _compare(Path(ns.left), Path(ns.right), format=ns.format)


if __name__ == "__main__":
    raise SystemExit(main())
