from __future__ import annotations

import json

from sdetkit import fit


def test_fit_cli_json_output_high_profile(capsys) -> None:
    rc = fit.main(
        [
            "--repo-size",
            "large",
            "--team-size",
            "large",
            "--release-frequency",
            "high",
            "--change-failure-impact",
            "high",
            "--compliance-pressure",
            "high",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["fit"] == "high"
    assert payload["score"] >= 14
