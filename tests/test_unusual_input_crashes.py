from __future__ import annotations

import json
import sys
from pathlib import Path

from sdetkit import inspect_data
from sdetkit.adoption_surface import core as adoption_core
from sdetkit.gates import gate
from sdetkit.intelligence import review
from sdetkit.maintenance import utils as maintenance_utils

_PRINT_LATIN1 = [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'caf\\xe9')"]


def test_gate_run_tolerates_undecodable_tool_output(tmp_path: Path) -> None:
    result = gate._run(_PRINT_LATIN1, tmp_path)
    assert result["rc"] == 0
    assert result["stdout"].startswith("caf")


def test_maintenance_run_cmd_tolerates_undecodable_tool_output(tmp_path: Path) -> None:
    proc = maintenance_utils.run_cmd(_PRINT_LATIN1, cwd=tmp_path)
    assert proc.returncode == 0
    assert proc.stdout.startswith("caf")


def test_review_json_command_reports_a_missing_interpreter() -> None:
    payload = review._run_json_cmd(["sdetkit-no-such-interpreter", "-m", "sdetkit"])
    assert payload["_diagnostics"]["rc"] == 127


def test_adoption_surface_ignores_a_non_utf8_package_json(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_bytes(b'{"name": "caf\xe9"}')
    assert adoption_core._read_json(tmp_path, "package.json") == {}


def test_inspect_reads_a_csv_row_with_more_fields_than_the_header(tmp_path: Path) -> None:
    csv_path = tmp_path / "ragged.csv"
    csv_path.write_text("id,name\n1,a\n2,b,EXTRA\n", encoding="utf-8")

    rc = inspect_data.main([str(csv_path), "--format", "json", "--out-dir", str(tmp_path / "out")])

    assert rc in {0, 2}
    payload = json.loads((tmp_path / "out" / "inspect.json").read_text(encoding="utf-8"))
    assert payload["summary"]["files_analyzed"] == 1
