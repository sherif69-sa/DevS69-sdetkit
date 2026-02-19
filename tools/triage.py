import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Issue:
    kind: str
    path: str
    line: int | None = None
    col: int | None = None
    message: str = ""


def _safe_user_path(root: Path, value: str) -> Path:
    if "\x00" in value:
        raise ValueError("path contains NUL byte")
    raw = Path(value)
    if any(part == ".." for part in raw.parts):
        raise ValueError("path traversal is not allowed")
    candidate = (
        raw.resolve(strict=False) if raw.is_absolute() else (root / raw).resolve(strict=False)
    )
    resolved_root = root.resolve(strict=True)
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ValueError("path must stay under --path root")
    return candidate


def _iter_py_files(root: Path, targets: list[str]) -> list[Path]:
    out: list[Path] = []
    for t in targets:
        p = root / t
        if p.is_file() and p.suffix == ".py":
            out.append(p)
        elif p.is_dir():
            out.extend(sorted(p.rglob("*.py")))
    seen: set[Path] = set()
    uniq: list[Path] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def _read_text_best_effort(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _compile_check(root: Path, targets: list[str], fix_nul: bool, radius: int) -> int:
    issues: list[Issue] = []
    marker_re = re.compile(r"(?m)^[ \t]*(<<<<<<<|=======|>>>>>>>)")

    for fp in _iter_py_files(root, targets):
        rel = fp.relative_to(root).as_posix()

        try:
            raw = fp.read_bytes()
        except OSError as e:
            issues.append(Issue("read-error", rel, message=str(e)))
            continue

        if b"\x00" in raw:
            if fix_nul:
                raw2 = raw.replace(b"\x00", b"")
                try:
                    fp.write_bytes(raw2)
                except OSError as e:
                    issues.append(Issue("nul-bytes", rel, message=str(e)))
                else:
                    raw = raw2
            else:
                issues.append(Issue("nul-bytes", rel, message="NUL byte found"))
                continue

        text = raw.decode("utf-8", errors="replace")
        if marker_re.search(text):
            issues.append(Issue("conflict-marker", rel, message="git conflict marker lines found"))

        try:
            _ = compile(text, rel, "exec")
        except (SyntaxError, IndentationError) as e:
            ln = getattr(e, "lineno", None)
            col = getattr(e, "offset", None)
            msg = getattr(e, "msg", "") or str(e)
            issues.append(Issue("syntax-error", rel, line=ln, col=col, message=msg))

    if not issues:
        return 0

    print(f"triage: compile failures: {len(issues)}")
    for it in issues:
        where = it.path
        if it.line is not None:
            where += f":{it.line}"
            if it.col is not None:
                where += f":{it.col}"
        print(f"- {it.kind} {where}: {it.message}")

        if it.kind == "syntax-error" and it.line is not None:
            fp = root / it.path
            src = _read_text_best_effort(fp).splitlines()
            lo = it.line - radius
            if lo < 1:
                lo = 1
            hi = it.line + radius
            if hi > len(src):
                hi = len(src)
            for i in range(lo, hi + 1):
                line = src[i - 1] if 0 <= i - 1 < len(src) else ""
                print(f"  {i:>6}  {line}")
    return 1


def _parse_pytest_log(text: str) -> tuple[list[str], list[tuple[str, int]], list[str]]:
    nodeids: list[str] = []
    locs: list[tuple[str, int]] = []
    e_lines: list[str] = []

    for line in text.splitlines():
        m = re.match(r"^(FAILED|ERROR)\s+(\S+)", line)
        if m:
            nodeids.append(m.group(2))

        m2 = re.match(r'^\s*File\s+"([^"]+)",\s+line\s+(\d+),', line)
        if m2:
            locs.append((m2.group(1), int(m2.group(2))))

        if line.startswith("E   "):
            e = line[4:].strip()
            if e:
                e_lines.append(e)

    return nodeids, locs, e_lines


def _print_pytest_summary(
    nodeids: list[str], locs: list[tuple[str, int]], radius: int, max_items: int
) -> tuple[list[str], list[tuple[str, int]]]:
    n = sorted(set(nodeids))
    f = sorted(set(locs), key=lambda t: (t[0], t[1]))

    counts: dict[str, int] = {}
    for path, _ln in f:
        counts[path] = counts.get(path, 0) + 1
    buckets = sorted(counts.items(), key=lambda t: (-t[1], t[0]))

    print("triage: failure summary")
    print(f"failed nodeids: {len(n)}")
    print(f"file locations: {len(f)}")
    if buckets:
        top = ", ".join([f"{k}={c}" for k, c in buckets[: min(5, len(buckets))]])
        print(f"top files: {top}")

    if n:
        print("top nodeids:")
        for x in n[:max_items]:
            print(f"- {x}")

    if f:
        print("top locations:")
        for path, ln in f[:max_items]:
            print(f"- {path}:{ln}")

    if n:
        print("suggested reruns:")
        for x in n[:max_items]:
            print(f"  pytest -q {x}")

    if f:
        print("suggested context views:")
        for path, ln in f[:max_items]:
            lo = ln - radius
            if lo < 1:
                lo = 1
            hi = ln + radius
            print(f"  nl -ba {path} | sed -n '{lo},{hi}p'")

    return n, f


def _default_grep_terms(nodeids: list[str], e_lines: list[str]) -> list[str]:
    out: list[str] = []
    for e in e_lines:
        out.append(e)
    for n in nodeids:
        base = n.split("::", 1)[0]
        if base and base.endswith(".py"):
            out.append(base)
    seen: set[str] = set()
    uniq: list[str] = []
    for t in out:
        t2 = t.strip()
        if not t2:
            continue
        if t2 in seen:
            continue
        seen.add(t2)
        uniq.append(t2)
    return uniq


def _grep_repo(root: Path, targets: list[str], terms: list[str], limit: int) -> None:
    if not terms:
        return

    files = _iter_py_files(root, targets)
    hits = 0
    print("triage: grep hits")
    for term in terms:
        term_hits = 0
        for fp in files:
            if term_hits >= limit:
                break
            rel = fp.relative_to(root).as_posix()
            text = _read_text_best_effort(fp)
            if not text:
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                if term in line:
                    print(f"- {term}  {rel}:{i}: {line.strip()}")
                    term_hits += 1
                    hits += 1
                    if term_hits >= limit:
                        break
        if term_hits == 0:
            print(f"- {term}  (no hits)")
    if hits == 0:
        print("triage: grep found no matches")


def _parse_security_text_log(text: str) -> tuple[list[Issue], dict[str, int]]:
    issues: list[Issue] = []
    counts = {"error": 0, "warn": 0, "info": 0}
    for line in text.splitlines():
        m = re.match(r"^- \[(error|warn|info)\]\s+(\S+)\s+(\S+):(\d+)\s+(.*)$", line.strip())
        if not m:
            continue
        sev, rule_id, path, line_no, msg = m.groups()
        counts[sev] = counts.get(sev, 0) + 1
        issues.append(
            Issue(kind=f"security:{sev}:{rule_id}", path=path, line=int(line_no), message=msg)
        )
    return issues, counts


def _parse_security_json_log(
    text: str, *, prefer_new_findings: bool = False
) -> tuple[list[Issue], dict[str, int]]:
    try:
        payload = json.loads(text)
    except ValueError:
        return [], {"error": 0, "warn": 0, "info": 0}
    if not isinstance(payload, dict):
        return [], {"error": 0, "warn": 0, "info": 0}
    findings = payload.get("findings", [])
    if prefer_new_findings and isinstance(payload.get("new_findings"), list):
        findings = payload.get("new_findings", [])
    issues: list[Issue] = []
    counts = {"error": 0, "warn": 0, "info": 0}
    if not isinstance(findings, list):
        return issues, counts
    for item in findings:
        if not isinstance(item, dict):
            continue
        sev = str(item.get("severity", "info")).lower()
        if sev not in counts:
            sev = "info"
        counts[sev] += 1
        issues.append(
            Issue(
                kind=f"security:{sev}:{item.get('rule_id', '')}",
                path=str(item.get("path", "")),
                line=int(item.get("line", 0) or 0) or None,
                col=int(item.get("column", 0) or 0) or None,
                message=str(item.get("message", "")),
            )
        )
    return issues, counts


def _print_security_summary(issues: list[Issue], counts: dict[str, int], max_items: int) -> int:
    if not issues:
        print("triage: no security findings found in log")
        return 0
    print("triage: security summary")
    print(
        f"counts: error={counts.get('error', 0)} warn={counts.get('warn', 0)} info={counts.get('info', 0)} total={len(issues)}"
    )
    by_rule: dict[str, int] = {}
    for item in issues:
        parts = item.kind.split(":", 2)
        rule = parts[2] if len(parts) == 3 else item.kind
        by_rule[rule] = by_rule.get(rule, 0) + 1
    top_rules = sorted(by_rule.items(), key=lambda x: (-x[1], x[0]))
    if top_rules:
        print("top rules:")
        for rule, count in top_rules[:max_items]:
            print(f"- {rule}: {count}")
    print("top findings:")
    for item in issues[:max_items]:
        where = item.path
        if item.line is not None:
            where += f":{item.line}"
        print(f"- {item.kind} {where}: {item.message}")
    return 1 if counts.get("error", 0) or counts.get("warn", 0) else 0


def _run_security_check(args: argparse.Namespace, root: Path) -> tuple[int, str]:
    cmd = [
        sys.executable,
        "-m",
        "sdetkit",
        "security",
        "check",
        "--root",
        str(root),
        "--format",
        "json",
        "--fail-on",
        "none",
    ]
    if args.security_baseline:
        cmd.extend(["--baseline", str(args.security_baseline)])
    if args.security_fail_on:
        cmd.extend(["--fail-on", str(args.security_fail_on)])
    proc = subprocess.run(
        cmd,
        check=False,
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    out = proc.stdout or ""
    if args.tee:
        try:
            tee_path = _safe_user_path(root, str(args.tee))
            tee_path.write_text(out, encoding="utf-8")
        except (OSError, ValueError) as exc:
            print(f"triage: failed to write tee output to {args.tee!r}: {exc}", file=sys.stderr)
    return int(proc.returncode), out


def _run_pytest(args: argparse.Namespace, root: Path) -> tuple[int, str]:
    extra = list(args.pytest_args) if args.pytest_args else ["-q"]
    cmd = ["pytest"] + extra
    proc = subprocess.run(
        cmd,
        check=False,
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    out = proc.stdout or ""
    if args.tee:
        try:
            tee_path = _safe_user_path(root, str(args.tee))
            tee_path.write_text(out, encoding="utf-8")
        except (OSError, ValueError) as exc:
            # Best-effort: failing to tee output should not be fatal, but log for visibility.
            print(f"triage: failed to write tee output to {args.tee!r}: {exc}", file=sys.stderr)
    return int(proc.returncode), out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="triage")
    parser.add_argument("--path", default="")
    parser.add_argument("--targets", nargs="*", dest="targets_opt", default=None)
    parser.add_argument("--mode", choices=["compile", "pytest", "security", "both"], default="both")
    parser.add_argument("--radius", type=int, default=3)
    parser.add_argument("--fix-nul", action="store_true")
    parser.add_argument("--tee", default="")
    parser.add_argument("--max-items", type=int, default=25)
    parser.add_argument("--parse-pytest-log", default="")
    parser.add_argument("--parse-security-log", default="")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--run-security", action="store_true")
    parser.add_argument("--security-baseline", default="")
    parser.add_argument("--security-fail-on", default="")
    parser.add_argument("--rerun", action="store_true")
    parser.add_argument("--grep", action="store_true")
    parser.add_argument("--grep-term", action="append", dest="grep_terms", default=[])
    parser.add_argument("--grep-limit", type=int, default=5)
    parser.add_argument("--pytest-args", nargs=argparse.REMAINDER, default=[])
    parser.add_argument("targets", nargs="*", default=["src", "tools", "tests"])
    args = parser.parse_args(argv)

    root = Path(args.path) if args.path else Path.cwd()
    targets = (
        list(args.targets_opt)
        if args.targets_opt is not None and len(args.targets_opt)
        else list(args.targets)
    )
    radius = int(args.radius)
    max_items = int(args.max_items)

    if args.mode in {"compile", "both"}:
        rc_compile = _compile_check(root, targets, bool(args.fix_nul), radius)
        if rc_compile == 0:
            print("triage: compile ok")
        else:
            return rc_compile

    if args.parse_security_log:
        try:
            logp = _safe_user_path(root, str(args.parse_security_log))
        except ValueError as exc:
            print(f"triage: invalid security log path: {exc}")
            return 2
        try:
            text = logp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            print(f"triage: security log file not found: {logp}")
            return 2
        issues, counts = _parse_security_json_log(text)
        if not issues:
            issues, counts = _parse_security_text_log(text)
        return _print_security_summary(issues, counts, max_items)

    if args.mode in {"pytest", "both"}:
        text = ""

        if args.parse_pytest_log:
            try:
                logp = _safe_user_path(root, str(args.parse_pytest_log))
            except ValueError as exc:
                print(f"triage: invalid pytest log path: {exc}")
                return 2
            try:
                text = logp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                print(f"triage: log file not found: {logp}")
                print("suggested command:")
                print(f"  pytest -q 2>&1 | tee {logp}")
                return 2

        run_now = bool(args.run) or (not args.parse_pytest_log and (bool(args.tee) or True))
        if not args.parse_pytest_log and run_now:
            rc, text = _run_pytest(args, root)
            if rc == 0:
                print("triage: pytest ok")
                return 0

        nodeids, locs, e_lines = _parse_pytest_log(text)
        if not nodeids and not locs:
            print("triage: no failures found in log")
            return 0

        nodeids2, locs2 = _print_pytest_summary(nodeids, locs, radius, max_items)

        if args.grep:
            terms = (
                list(args.grep_terms) if args.grep_terms else _default_grep_terms(nodeids2, e_lines)
            )
            _grep_repo(root, targets, terms, int(args.grep_limit))

        if args.rerun and nodeids2:
            top = nodeids2[: min(3, len(nodeids2))]
            cmd = ["pytest", "-q"] + top
            proc = subprocess.run(
                cmd,
                check=False,
                cwd=str(root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            print("\n=== triage rerun ===\n")
            sys.stdout.write(proc.stdout or "")
            return int(proc.returncode)

        return 1

    if args.mode in {"security", "both"} and args.run_security:
        _rc, out = _run_security_check(args, root)
        issues, counts = _parse_security_json_log(
            out, prefer_new_findings=bool(args.security_baseline)
        )
        if not issues:
            issues, counts = _parse_security_text_log(out)
        return _print_security_summary(issues, counts, max_items)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
