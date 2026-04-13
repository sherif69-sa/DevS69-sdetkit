from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _bool_score(value: bool) -> int:
    return 25 if value else 0


def _build_scorecard(golden: dict[str, Any] | None, drift: dict[str, Any] | None, legacy: dict[str, Any] | None) -> dict[str, Any]:
    onboarding_ok = bool(golden and golden.get("overall_ok") is True)
    release_ok = bool(
        golden
        and isinstance(golden.get("checks"), dict)
        and isinstance(golden["checks"].get("gate_release"), dict)
        and golden["checks"]["gate_release"].get("ok") is True
    )
    quality_ok = bool(drift and drift.get("overall_ok") is True)
    ops_ok = bool(legacy and legacy.get("overall_ok") is True)

    dimensions = {
        "onboarding": _bool_score(onboarding_ok),
        "quality": _bool_score(quality_ok),
        "release": _bool_score(release_ok),
        "ops": _bool_score(ops_ok),
    }
    total = sum(dimensions.values())
    if total >= 90:
        band = "excellent"
    elif total >= 70:
        band = "strong"
    elif total >= 40:
        band = "developing"
    else:
        band = "early"
    return {
        "schema_version": "1",
        "score": total,
        "band": band,
        "dimensions": dimensions,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/adoption_scorecard.py")
    parser.add_argument("--golden", default=".sdetkit/out/golden-path-health.json")
    parser.add_argument("--drift", default=".sdetkit/out/canonical-path-drift.json")
    parser.add_argument("--legacy", default=".sdetkit/out/legacy-command-analyzer.json")
    parser.add_argument("--out", default=".sdetkit/out/adoption-scorecard.json")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(argv)

    scorecard = _build_scorecard(
        _load_json(Path(ns.golden)),
        _load_json(Path(ns.drift)),
        _load_json(Path(ns.legacy)),
    )
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scorecard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if ns.format == "json":
        print(json.dumps(scorecard, sort_keys=True))
    else:
        print(f"adoption-scorecard: score={scorecard['score']} band={scorecard['band']}")
        for k, v in scorecard["dimensions"].items():
            print(f"- {k}: {v}/25")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
