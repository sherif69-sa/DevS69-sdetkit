#!/usr/bin/env bash
set -euo pipefail

ensure_venv() {
  if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    return 0
  fi

  if [[ -f ".venv/bin/activate" ]]; then
    . .venv/bin/activate
    return 0
  fi

  bash scripts/bootstrap.sh
  . .venv/bin/activate
}

ensure_venv
python3 scripts/check_repo_layout.py

mode=${1:-all}
if [[ "$mode" == "-h" || "$mode" == "--help" || "$mode" == "help" ]]; then
  mode=help
fi
# Keep the default gate realistic for full-repo runs, while still allowing
# stricter enforcement in CI/release jobs via COV_FAIL_UNDER=95.
cov_fail_under=${COV_FAIL_UNDER:-80}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 && return 0
  echo "missing tool: $1" >&2
  echo "hint: bash scripts/bootstrap.sh && . .venv/bin/activate" >&2
  exit 127
}

valid_modes=(all ci verify fmt lint type doctor test full-test cov mut muthtml boost help)

usage() {
  cat <<'USAGE' >&2
Usage: bash quality.sh {all|ci|verify|fmt|lint|type|doctor|test|full-test|cov|mut|muthtml|boost}

Profiles:
  quick     Fast local confidence / smoke profile.
  standard  Default repository validation profile.
  strict    Merge/release truth profile.
  adaptive  Planner-selected profile scaffold for future targeted scheduling.

Modes:
  ci         Fast/smoke lane for local confidence; not merge truth.
  verify     Full verification lane before merge (doctor, format, lint, typing, full tests, security scan).
  all        Standard repo validation lane (auto-format, lint, typing, pytest, coverage).
  fmt        Apply Ruff formatting.
  lint       Run Ruff lint checks.
  type       Run mypy typing checks.
  doctor     Run the repo doctor report.
  test       Run the fast smoke gate.
  full-test  Run the full pytest -q suite.
  cov        Run the coverage lane.
  mut        Run mutation testing.
  muthtml    Build mutation HTML output.
  boost      Chain doctor, fast gate, premium fast gate, and optimization summary.
USAGE
}

mode_suggestion() {
  python3 - "$1" "${valid_modes[@]}" <<'PY'
import difflib
import sys

unknown = sys.argv[1]
choices = sys.argv[2:]
match = difflib.get_close_matches(unknown, choices, n=1)
if match:
    print(match[0])
PY
}

run_fmt() { need_cmd ruff; python -m ruff format .; }
run_fmt_check() { need_cmd ruff; python -m ruff format --check .; }
run_lint() { need_cmd ruff; python -m ruff check .; }
run_type() { need_cmd mypy; python -m mypy --config-file pyproject.toml src; }
run_doctor() { python -m sdetkit doctor --dev --ci --deps --repo --upgrade-audit --format md; }
run_gate_fast() { python -m sdetkit gate fast; }
run_premium_autofix() {
  if [[ -f "premium-gate.sh" ]]; then
    python -m sdetkit.premium_gate_engine \
      --out-dir .sdetkit/out \
      --double-check \
      --auto-fix \
      --auto-run-scripts \
      --format markdown
  else
    echo "skip premium auto-fix: premium-gate.sh not found"
  fi
}
run_premium_fast() {
  if [[ -f "premium-gate.sh" ]]; then
    bash premium-gate.sh --mode "${SDETKIT_BOOST_PREMIUM_MODE:-fast}"
  else
    echo "skip premium gate: premium-gate.sh not found"
  fi
}
run_topology_check() {
  local profile="${SDETKIT_BOOST_TOPOLOGY_PROFILE:-examples/kits/integration/heterogeneous-topology.json}"
  if [[ -f "$profile" ]]; then
    python -m sdetkit integration topology-check --profile "$profile"
  else
    echo "skip topology check: $profile not found"
  fi
}
run_optimize_summary() {
  python -m sdetkit kits optimize \
    --goal "${SDETKIT_BOOST_GOAL:-upgrade umbrella architecture with agentos optimization}" \
    --format text
}
run_boost() {
  run_doctor
  run_type
  run_premium_autofix
  run_gate_fast
  run_premium_fast
  run_topology_check
  run_optimize_summary
}
run_full_test() { need_cmd pytest; python -m pytest -q -o addopts=; }
run_test() { need_cmd pytest; python -m pytest; }
run_cov() {
  need_cmd pytest
  # Coverage profiles:
  # - full: complete repository visibility (informational)
  # - core (default): strict gate on critical, stable modules
  cov_scope="${COV_SCOPE:-core}"

  if [[ "$cov_scope" == "full" ]]; then
    python -m pytest --cov=sdetkit --cov-report=term-missing --cov-fail-under="$cov_fail_under"
    return
  fi

  python -m pytest \
    --cov=sdetkit.__main__ \
    --cov=sdetkit._entrypoints \
    --cov=sdetkit._toml \
    --cov=sdetkit.atomicio \
    --cov=sdetkit.report \
    --cov=sdetkit.reliability_evidence_pack \
    --cov=sdetkit.roadmap_manifest \
    --cov=sdetkit.sqlite_scalar \
    --cov=sdetkit.textutil \
    --cov-report=term-missing \
    --cov-fail-under="$cov_fail_under"
}
run_mut() { need_cmd mutmut; mutmut run; }
run_muthtml() { need_cmd mutmut; mutmut html; }

SDETKIT_OUT_DIR="${SDETKIT_OUT_DIR:-.sdetkit/out}"
mkdir -p "$SDETKIT_OUT_DIR"
QUALITY_STEP_RESULTS_NDJSON="$SDETKIT_OUT_DIR/quality-step-results.ndjson"
QUALITY_VERDICT_JSON="$SDETKIT_OUT_DIR/quality-verdict.json"
QUALITY_SUMMARY_MD="$SDETKIT_OUT_DIR/quality-summary.md"
: > "$QUALITY_STEP_RESULTS_NDJSON"

record_check() {
  python3 - "$QUALITY_STEP_RESULTS_NDJSON" "$1" "$2" "$3" "$4" "$5" "$6" "$7" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
entry = {
    "id": sys.argv[2],
    "title": sys.argv[3],
    "status": sys.argv[4],
    "blocking": sys.argv[5] == "1",
    "reason": sys.argv[6],
    "command": sys.argv[7],
    "log_path": sys.argv[8],
}
path.write_text(path.read_text(encoding="utf-8") + json.dumps(entry, sort_keys=True) + "\n", encoding="utf-8")
PY
}

run_tracked() {
  local check_id="$1"
  local title="$2"
  local blocking="$3"
  local command_text="$4"
  local safe_title
  safe_title="$(echo "$check_id" | tr -cd '[:alnum:]_.-')"
  local log_path="$SDETKIT_OUT_DIR/quality.${safe_title}.log"
  echo "[quality] running $check_id :: $title"
  set +e
  eval "$command_text" 2>&1 | tee "$log_path"
  local rc=${PIPESTATUS[0]}
  set -e
  if (( rc == 0 )); then
    record_check "$check_id" "$title" "passed" "$blocking" "" "$command_text" "$log_path"
  else
    record_check "$check_id" "$title" "failed" "$blocking" "command failed (rc=$rc)" "$command_text" "$log_path"
  fi
  return "$rc"
}

skip_tracked() {
  local check_id="$1"
  local title="$2"
  local blocking="$3"
  local reason="$4"
  record_check "$check_id" "$title" "skipped" "$blocking" "$reason" "" ""
}

emit_final_verdict() {
  python3 - "$QUALITY_STEP_RESULTS_NDJSON" "$1" "$2" "$QUALITY_VERDICT_JSON" "$QUALITY_SUMMARY_MD" <<'PY'
import json
import sys
from pathlib import Path

from sdetkit.checks.results import CheckRecord, build_final_verdict

records = []
for raw in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    raw = raw.strip()
    if not raw:
        continue
    item = json.loads(raw)
    records.append(
        CheckRecord(
            id=str(item["id"]),
            title=str(item["title"]),
            status=str(item["status"]),
            blocking=bool(item.get("blocking", True)),
            reason=str(item.get("reason", "")),
            command=str(item.get("command", "")),
            log_path=str(item.get("log_path", "")),
        )
    )

profile = sys.argv[2]
notes = sys.argv[3]
verdict = build_final_verdict(
    profile=profile,
    checks=records,
    profile_notes=notes,
    metadata={"source": "quality.sh", "checks_recorded": len(records)},
)
Path(sys.argv[4]).write_text(verdict.to_json(), encoding="utf-8")
Path(sys.argv[5]).write_text(verdict.to_markdown(), encoding="utf-8")
print(f"[quality] final verdict contract: {verdict.verdict_contract}")
print(f"[quality] profile used: {verdict.profile}")
print(f"[quality] checks run: {len(verdict.checks_run)}")
print(f"[quality] checks skipped: {len(verdict.checks_skipped)}")
if verdict.blocking_failures:
    print("[quality] blocking failures:")
    for item in verdict.blocking_failures:
        print(f"- {item}")
else:
    print("[quality] blocking failures: none")
if verdict.advisory_findings:
    print("[quality] advisory findings:")
    for item in verdict.advisory_findings:
        print(f"- {item}")
else:
    print("[quality] advisory findings: none")
print(f"[quality] confidence level: {verdict.confidence_level}")
print(f"[quality] merge/release recommendation: {verdict.recommendation}")
print(f"[quality] verdict json: {sys.argv[4]}")
print(f"[quality] summary md: {sys.argv[5]}")
PY
}

final_rc=0
profile_used="standard"
profile_notes="Default repository validation profile."

run_required() {
  if ! run_tracked "$1" "$2" "$3" "$4"; then
    final_rc=1
  fi
}

case "$mode" in
  fmt)
    profile_used="standard"
    profile_notes="Single-check maintenance lane for formatting application."
    run_required "format_apply" "Ruff format apply" 0 "run_fmt"
    skip_tracked "lint" "Ruff lint" 1 "not selected in fmt mode"
    skip_tracked "typing" "Mypy typing" 1 "not selected in fmt mode"
    skip_tracked "tests_full" "Full pytest suite" 1 "not selected in fmt mode"
    ;;
  lint)
    profile_used="standard"
    profile_notes="Single-check repository validation lane for lint only."
    run_required "lint" "Ruff lint" 1 "run_lint"
    skip_tracked "format_check" "Ruff format check" 1 "not selected in lint mode"
    skip_tracked "typing" "Mypy typing" 1 "not selected in lint mode"
    skip_tracked "tests_full" "Full pytest suite" 1 "not selected in lint mode"
    ;;
  type)
    profile_used="standard"
    profile_notes="Single-check repository validation lane for typing only."
    run_required "typing" "Mypy typing" 1 "run_type"
    skip_tracked "format_check" "Ruff format check" 1 "not selected in type mode"
    skip_tracked "lint" "Ruff lint" 1 "not selected in type mode"
    skip_tracked "tests_full" "Full pytest suite" 1 "not selected in type mode"
    ;;
  doctor)
    profile_used="standard"
    profile_notes="Advisory repository health report lane."
    run_required "doctor" "Doctor report" 0 "run_doctor"
    skip_tracked "format_check" "Ruff format check" 1 "not selected in doctor mode"
    skip_tracked "lint" "Ruff lint" 1 "not selected in doctor mode"
    skip_tracked "typing" "Mypy typing" 1 "not selected in doctor mode"
    ;;
  test)
    profile_used="quick"
    profile_notes="Smoke-only test lane; passing does not imply merge truth."
    echo "[quality] Fast/smoke lane for local confidence (not full merge verification)."
    run_required "tests_smoke" "Fast/smoke tests" 1 "run_gate_fast"
    skip_tracked "tests_full" "Full pytest suite" 1 "smoke test mode only"
    ;;
  cov)
    profile_used="standard"
    profile_notes="Coverage lane for default repository validation."
    run_required "coverage" "Coverage lane" 1 "run_cov"
    skip_tracked "tests_full" "Full pytest suite" 1 "coverage mode focuses on coverage gate"
    ;;
  full-test)
    profile_used="strict"
    profile_notes="Full test truth lane without the surrounding non-test checks."
    run_required "tests_full" "Full pytest suite" 1 "run_full_test"
    skip_tracked "tests_smoke" "Fast/smoke tests" 1 "full test mode supersedes smoke path"
    ;;
  mut)
    profile_used="standard"
    profile_notes="Mutation analysis lane."
    run_required "mutation" "Mutation testing" 1 "run_mut"
    ;;
  muthtml)
    profile_used="standard"
    profile_notes="Mutation HTML artifact lane."
    run_required "mutation_html" "Mutation HTML output" 0 "run_muthtml"
    ;;
  boost)
    profile_used="adaptive"
    profile_notes="Planner-oriented boost lane that chains multiple platform surfaces."
    run_required "boost" "Boost orchestration" 0 "run_boost"
    ;;
  ci)
    profile_used="quick"
    profile_notes="Fast local confidence / smoke profile. Honest smoke lane only; not merge truth."
    echo "[quality] Fast/smoke lane for local confidence (not full merge verification)."
    python -m sdetkit.checks run       --profile quick       --repo-root .       --out-dir "$SDETKIT_OUT_DIR"       --format text       --json-output "$QUALITY_VERDICT_JSON"       --markdown-output "$QUALITY_SUMMARY_MD"
    exit $? 
    ;;
  verify)
    profile_used="strict"
    profile_notes="Merge/release truth profile. Full verification before merge."
    echo "[quality] Full verification lane before merge (doctor, format, lint, typing, full tests, security scan)."
    python -m sdetkit.checks run       --profile strict       --repo-root .       --out-dir "$SDETKIT_OUT_DIR"       --format text       --json-output "$QUALITY_VERDICT_JSON"       --markdown-output "$QUALITY_SUMMARY_MD"
    exit $? 
    ;;
  all)
    profile_used="standard"
    profile_notes="Default repository validation profile. Broader than smoke, lighter than strict merge truth."
    run_required "format_apply" "Ruff format apply" 0 "run_fmt"
    run_required "lint" "Ruff lint" 1 "run_lint"
    run_required "typing" "Mypy typing" 1 "run_type"
    run_required "tests_standard" "Pytest default suite" 1 "run_test"
    run_required "coverage" "Coverage lane" 0 "run_cov"
    skip_tracked "tests_full" "Full pytest suite" 1 "standard profile is not the merge/release truth path; use verify"
    ;;
  help)
    usage
    exit 0
    ;;
  *)
    usage
    suggestion="$(mode_suggestion "$mode" || true)"
    if [[ -n "$suggestion" ]]; then
      echo "Did you mean: bash quality.sh $suggestion" >&2
    fi
    exit 2
    ;;
esac

emit_final_verdict "$profile_used" "$profile_notes"
exit "$final_rc"
