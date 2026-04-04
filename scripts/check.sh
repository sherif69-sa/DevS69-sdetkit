#!/usr/bin/env bash

set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

if [ -d ".venv/bin" ]; then
  PATH="$root/.venv/bin:$PATH"
  export PATH
fi

mode=${1:-}

case "$mode" in
  fmt)
    shift || true
    ruff format "${@:-.}"
    ;;
  lint)
    ruff format --check .
    ruff check .
    ;;
  types)
    mypy src
    ;;
  tests)
    pytest
    ;;
  coverage)
    pytest --cov=src/sdetkit --cov-report=term-missing --cov-report=xml
    ;;
  docs)
    mkdocs build
    python scripts/check_onboarding_contract.py
    python scripts/check_proof_contract_3.py
    python scripts/check_skills_contract_4.py
    python scripts/check_github_actions_onboarding_contract.py
    python scripts/check_gitlab_ci_onboarding_contract.py
    python scripts/check_reliability_evidence_pack_contract.py
    python scripts/check_release_communications_contract.py
    ;;
  onboarding)
    python scripts/check_onboarding_contract.py
    ;;
  cycle3-proof)
    python scripts/check_proof_contract_3.py
    ;;
  cycle4-skills)
    python scripts/check_skills_contract_4.py
    ;;
  # Legacy aliases retained for compatibility with transition-era lanes.
  day3)
    python scripts/check_proof_contract_3.py
    ;;
  day4)
    python scripts/check_skills_contract_4.py
    ;;
  github-actions-onboarding)
    python scripts/check_github_actions_onboarding_contract.py
    ;;
  gitlab-ci-onboarding)
    python scripts/check_gitlab_ci_onboarding_contract.py
    python scripts/check_reliability_evidence_pack_contract.py
    ;;
  # Legacy aliases retained for compatibility with transition-era lanes.
  day15)
    python scripts/check_github_actions_onboarding_contract.py
    ;;
  day16)
    python scripts/check_gitlab_ci_onboarding_contract.py
    python scripts/check_reliability_evidence_pack_contract.py
    ;;
  release-readiness)
    python scripts/check_release_readiness_contract.py --skip-evidence
    ;;
  release-communications)
    python scripts/check_release_communications_contract.py
    ;;
  all)
    ruff format --check .
    ruff check .
    mypy src
    pytest
    pytest --cov=src/sdetkit --cov-report=term-missing --cov-report=xml
    mkdocs build
    python scripts/check_onboarding_contract.py
    python scripts/check_proof_contract_3.py
    python scripts/check_skills_contract_4.py
    python scripts/check_github_actions_onboarding_contract.py
    python scripts/check_gitlab_ci_onboarding_contract.py
    python scripts/check_reliability_evidence_pack_contract.py
    python scripts/check_release_communications_contract.py
    ;;
  *)
    echo "Usage: bash scripts/check.sh {fmt|lint|types|tests|coverage|docs|onboarding|cycle3-proof|cycle4-skills|github-actions-onboarding|gitlab-ci-onboarding|release-readiness|release-communications|all}" >&2
    exit 2
    ;;
esac

echo "check.sh: $mode checks passed."
