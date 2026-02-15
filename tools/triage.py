import argparse
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Issue:
    kind: str
    path: str
    line: int | None = None
    col: int | None = None
    message: str = ""


def _iter_py_files(root: Path, targets: list[str]) -> list[Path]:
    out: list[Path] = []
    for t in targets:
        p = root / t
        if p.is_file() and p.suffix == ".py":
            out.append(p)
        elif p.is_dir():
            out.extend(list(p.rglob("*.py")))
    out.sort(key=lambda x: x.as_posix())
    return out


def _context(path: Path, line: int | None, radius: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    if not line or line < 1:
        lo = 1
        hi = min(len(lines), 1 + 2 * radius)
    else:
        lo = max(1, line - radius)
        hi = min(len(lines), line + radius)
    buf: list[str] = []
    for i in range(lo, hi + 1):
        buf.append(f"{i:5d}: {lines[i - 1]}")
    return "\n".join(buf)


def _has_nul(path: Path) -> bool:
    try:
        b = path.read_bytes()
    except OSError:
        return False
    return b"\x00" in b


def _maybe_fix_nul(root: Path, rel: str) -> bool:
    if not (root / ".git").exists():
        return False
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "checkout", "--", rel],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return False
    return proc.returncode == 0


def _compile_check(
    root: Path, targets: list[str], fix_nul: bool, radius: int
) -> tuple[int, list[Issue]]:
    issues: list[Issue] = []
    for fp in _iter_py_files(root, targets):
        rel = fp.relative_to(root).as_posix()
        if _has_nul(fp):
            fixed = False
            if fix_nul:
                fixed = _maybe_fix_nul(root, rel)
            if not fixed:
                issues.append(Issue(kind="nul", path=rel, message="file contains NUL bytes"))
                continue
        try:
            src = tokenize.open(fp).read()
        except Exception as e:
            issues.append(Issue(kind="decode", path=rel, message=str(e)))
            continue
        try:
            compile(src, str(fp), "exec")
        except SyntaxError as e:
            issues.append(
                Issue(
                    kind="syntax",
                    path=rel,
                    line=int(e.lineno) if e.lineno else None,
                    col=int(e.offset) if e.offset else None,
                    message=str(e.msg or "SyntaxError"),
                )
            )
        except Exception as e:
            issues.append(Issue(kind="compile", path=rel, message=str(e)))

    rc = 0 if not issues else 1

    if issues:
        print("triage: compile issues found")
        for it in sorted(issues, key=lambda x: (x.path, x.line or 0, x.col or 0, x.kind)):
            loc = ""
            if it.line:
                loc = f":{it.line}"
                if it.col:
                    loc += f":{it.col}"
            print(f"- {it.kind}: {it.path}{loc}: {it.message}")
            if it.kind in {"syntax", "compile", "decode"}:
                ctx = _context(root / it.path, it.line, radius)
                if ctx:
                    print(ctx)
        print("")
        print("suggested commands:")
        for it in sorted(issues, key=lambda x: (x.path, x.line or 0, x.kind)):
            if it.line:
                lo = max(1, it.line - radius)
                hi = it.line + radius
                print(f"  nl -ba {it.path} | sed -n '{lo},{hi}p'")
            else:
                print(f"  python3 -m compileall -q {it.path}")
        if fix_nul and any(i.kind == "nul" for i in issues):
            print("")
            print(
                "note: --fix-nul can restore tracked files with NUL bytes via git checkout -- <file>"
            )

    return rc, issues


def _parse_pytest_log(text: str) -> tuple[list[str], list[tuple[str, int]]]:
    nodeids: set[str] = set()
    files: set[tuple[str, int]] = set()

    for line in text.splitlines():
        if line.startswith("FAILED "):
            rest = line[len("FAILED ") :].strip()
            node = rest.split(" - ", 1)[0].strip()
            if node:
                nodeids.add(node)

    for line in text.splitlines():
        line = line.strip()
        if line.startswith('File "') and '", line ' in line:
            try:
                left = line.split('File "', 1)[1]
                path_s, right = left.split('", line ', 1)
                n_s = ""
                for ch in right:
                    if ch.isdigit():
                        n_s += ch
                    else:
                        break
                if path_s and n_s:
                    files.add((path_s, int(n_s)))
            except Exception:
                continue

    return sorted(nodeids), sorted(files, key=lambda x: (x[0], x[1]))


def _print_pytest_suggestions(nodeids: list[str], files: list[tuple[str, int]], radius: int) -> int:
    if not nodeids and not files:
        print("triage: no recognizable pytest failures found in log")
        return 1

    print("triage: pytest log hints")
    if nodeids:
        print("failed nodeids:")
        for n in nodeids:
            print(f"- {n}")
    if files:
        print("file locations:")
        for f, ln in files:
            print(f"- {f}:{ln}")

    print("")
    print("suggested commands:")
    for n in nodeids:
        print(f"  pytest -q {n}")
    for f, ln in files:
        lo = max(1, ln - radius)
        hi = ln + radius
        print(f"  nl -ba {f} | sed -n '{lo},{hi}p'")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="triage.py")
    parser.add_argument("--path", default=".", help="Repo root (default: .)")
    parser.add_argument("--targets", default="src,tools,tests")
    parser.add_argument("--mode", choices=["compile", "pytest", "both"], default="both")
    parser.add_argument("--radius", type=int, default=20)
    parser.add_argument("--fix-nul", action="store_true")
    parser.add_argument("--parse-pytest-log", default=None)

    args, rest = parser.parse_known_args(argv)

    root = Path(args.path).resolve()
    targets = [x.strip() for x in str(args.targets).split(",") if x.strip()]
    radius = int(args.radius)

    if args.parse_pytest_log:
        logp = Path(args.parse_pytest_log)
        text = logp.read_text(encoding="utf-8", errors="replace")
        nodeids, files = _parse_pytest_log(text)
        return _print_pytest_suggestions(nodeids, files, radius)

    rc = 0

    if args.mode in {"compile", "both"}:
        rc_compile, _ = _compile_check(root, targets, bool(args.fix_nul), radius)
        rc = max(rc, rc_compile)

    if args.mode in {"pytest", "both"}:
        cmd = [sys.executable, "-m", "pytest", "-q", *rest]
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        out = proc.stdout or ""
        if proc.returncode == 0:
            print("triage: pytest ok")
        else:
            nodeids, files = _parse_pytest_log(out)
            _print_pytest_suggestions(nodeids, files, radius)
        rc = max(rc, 0 if proc.returncode == 0 else 1)

    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
