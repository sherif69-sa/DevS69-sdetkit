from __future__ import annotations

import datetime as dt
import hashlib
import io
import os
import re
import shlex
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sdetkit import repo
from sdetkit.atomicio import atomic_write_text, canonical_json_bytes, canonical_json_dumps
from sdetkit.report import build_dashboard


class TemplateValidationError(ValueError):
    pass


@dataclass(frozen=True)
class TemplateInput:
    name: str
    default: Any
    description: str


@dataclass(frozen=True)
class TemplateStep:
    step_id: str
    action: str
    params: dict[str, Any]


@dataclass(frozen=True)
class AutomationTemplate:
    metadata: dict[str, str]
    inputs: dict[str, TemplateInput]
    workflow: list[TemplateStep]
    source: Path


_YAML_LINE = re.compile(r"^(?P<indent>\s*)(?P<body>.*)$")
_INTERPOLATION = re.compile(r"\$\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")


def _parse_scalar(raw: str) -> Any:
    text = raw.strip()
    if text in {"", "null", "~"}:
        return None
    if text in {"true", "false"}:
        return text == "true"
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        return text[1:-1]
    return text


def _tokenize_yaml(path: Path) -> list[tuple[int, str, int]]:
    out: list[tuple[int, str, int]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        match = _YAML_LINE.match(raw)
        if match is None:
            continue
        indent = len(match.group("indent"))
        if indent % 2 != 0:
            raise TemplateValidationError(
                f"{path.as_posix()}:{line_no}: indentation must use multiples of 2 spaces"
            )
        out.append((indent, match.group("body").rstrip(), line_no))
    return out


def _parse_block(tokens: list[tuple[int, str, int]], idx: int, indent: int) -> tuple[Any, int]:
    if idx >= len(tokens):
        return {}, idx
    tok_indent, body, line_no = tokens[idx]
    if tok_indent < indent:
        return {}, idx
    if tok_indent > indent:
        raise TemplateValidationError(f"line {line_no}: unexpected indentation")

    if body.startswith("- "):
        items: list[Any] = []
        while idx < len(tokens):
            tok_indent, body, line_no = tokens[idx]
            if tok_indent < indent:
                break
            if tok_indent != indent:
                raise TemplateValidationError(f"line {line_no}: invalid list indentation")
            if not body.startswith("- "):
                raise TemplateValidationError(f"line {line_no}: expected list item")
            rest = body[2:].strip()
            idx += 1
            if not rest:
                value, idx = _parse_block(tokens, idx, indent + 2)
                items.append(value)
                continue
            if ":" in rest:
                key, rhs = rest.split(":", 1)
                item: dict[str, Any] = {key.strip(): _parse_scalar(rhs)} if rhs.strip() else {}
                if not rhs.strip():
                    nested, idx = _parse_block(tokens, idx, indent + 2)
                    item[key.strip()] = nested
                while idx < len(tokens):
                    n_indent, n_body, _ = tokens[idx]
                    if n_indent < indent + 2:
                        break
                    if n_indent != indent + 2:
                        raise TemplateValidationError(
                            f"line {tokens[idx][2]}: invalid nested map indentation"
                        )
                    if n_body.startswith("- "):
                        break
                    if ":" not in n_body:
                        raise TemplateValidationError(f"line {tokens[idx][2]}: expected key: value")
                    n_key, n_rhs = n_body.split(":", 1)
                    idx += 1
                    if n_rhs.strip():
                        item[n_key.strip()] = _parse_scalar(n_rhs)
                    else:
                        nested, idx = _parse_block(tokens, idx, indent + 4)
                        item[n_key.strip()] = nested
                items.append(item)
                continue
            items.append(_parse_scalar(rest))
        return items, idx

    mapping: dict[str, Any] = {}
    while idx < len(tokens):
        tok_indent, body, line_no = tokens[idx]
        if tok_indent < indent:
            break
        if tok_indent != indent:
            raise TemplateValidationError(f"line {line_no}: invalid mapping indentation")
        if ":" not in body:
            raise TemplateValidationError(f"line {line_no}: expected key: value")
        key, rhs = body.split(":", 1)
        idx += 1
        if rhs.strip():
            mapping[key.strip()] = _parse_scalar(rhs)
            continue
        nested, idx = _parse_block(tokens, idx, indent + 2)
        mapping[key.strip()] = nested
    return mapping, idx


def parse_template(path: Path) -> AutomationTemplate:
    tokens = _tokenize_yaml(path)
    parsed, idx = _parse_block(tokens, 0, 0)
    if idx != len(tokens):
        line_no = tokens[idx][2]
        raise TemplateValidationError(f"line {line_no}: unexpected content after document end")
    if not isinstance(parsed, dict):
        raise TemplateValidationError("template root must be a mapping")
    return validate_template(parsed, source=path)


def validate_template(raw: dict[str, Any], *, source: Path) -> AutomationTemplate:
    metadata = raw.get("metadata")
    inputs_raw = raw.get("inputs", {})
    workflow_raw = raw.get("workflow")
    if not isinstance(metadata, dict):
        raise TemplateValidationError(f"{source.as_posix()}: metadata must be a mapping")
    required = ("id", "title", "version", "description")
    missing = [
        item for item in required if not isinstance(metadata.get(item), str) or not metadata[item]
    ]
    if missing:
        raise TemplateValidationError(
            f"{source.as_posix()}: metadata missing required fields: {', '.join(missing)}"
        )
    if not isinstance(inputs_raw, dict):
        raise TemplateValidationError(f"{source.as_posix()}: inputs must be a mapping")
    if not isinstance(workflow_raw, list) or not workflow_raw:
        raise TemplateValidationError(f"{source.as_posix()}: workflow must be a non-empty list")

    inputs: dict[str, TemplateInput] = {}
    for name, payload in inputs_raw.items():
        if not isinstance(name, str):
            raise TemplateValidationError(f"{source.as_posix()}: input names must be strings")
        if isinstance(payload, dict):
            default = payload.get("default")
            description = str(payload.get("description", ""))
        else:
            default = payload
            description = ""
        inputs[name] = TemplateInput(name=name, default=default, description=description)

    workflow: list[TemplateStep] = []
    for index, item in enumerate(workflow_raw, start=1):
        if not isinstance(item, dict):
            raise TemplateValidationError(
                f"{source.as_posix()}: workflow step {index} must be a mapping"
            )
        action = item.get("action")
        if not isinstance(action, str) or not action:
            raise TemplateValidationError(
                f"{source.as_posix()}: workflow step {index} missing non-empty action"
            )
        params = item.get("with", {})
        if not isinstance(params, dict):
            raise TemplateValidationError(
                f"{source.as_posix()}: workflow step {index} field 'with' must be mapping"
            )
        step_id = str(item.get("id", f"step-{index}"))
        workflow.append(TemplateStep(step_id=step_id, action=action, params=params))

    return AutomationTemplate(
        metadata={key: str(metadata[key]) for key in required},
        inputs=inputs,
        workflow=workflow,
        source=source,
    )


def _safe_lookup(context: dict[str, Any], expr: str) -> Any:
    current: Any = context
    for part in expr.split("."):
        if not isinstance(current, dict) or part not in current:
            raise TemplateValidationError(f"unknown interpolation variable '{expr}'")
        current = current[part]
    return current


def interpolate_value(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        matches = list(_INTERPOLATION.finditer(value))
        if not matches:
            return value
        if len(matches) == 1 and matches[0].span() == (0, len(value)):
            return _safe_lookup(context, matches[0].group(1))

        def repl(match: re.Match[str]) -> str:
            resolved = _safe_lookup(context, match.group(1))
            return str(resolved)

        return _INTERPOLATION.sub(repl, value)
    if isinstance(value, dict):
        return {k: interpolate_value(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [interpolate_value(item, context) for item in value]
    return value


def discover_templates(root: Path) -> list[AutomationTemplate]:
    directory = root / "templates" / "automations"
    if not directory.exists():
        return []
    templates = [parse_template(path) for path in sorted(directory.glob("*.yaml"))]
    ids = [item.metadata["id"] for item in templates]
    duplicates = {item for item in ids if ids.count(item) > 1}
    if duplicates:
        dup_csv = ", ".join(sorted(duplicates))
        raise TemplateValidationError(f"duplicate template ids found: {dup_csv}")
    return templates


def template_by_id(root: Path, template_id: str) -> AutomationTemplate:
    for item in discover_templates(root):
        if item.metadata["id"] == template_id:
            return item
    raise TemplateValidationError(f"template '{template_id}' not found")


def _captured_at() -> str:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        return dt.datetime.fromtimestamp(int(epoch), tz=dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt.datetime.now(tz=dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_shell(cmd: str, cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(shlex.split(cmd), cwd=cwd, capture_output=True, text=True, check=False)
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "ok": proc.returncode == 0,
    }


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return bool(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, canonical_json_dumps(payload))


def _atomic_tar_write(target: Path, write_cb: Any) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=target.name + ".", dir=str(target.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        write_cb(tmp_path)
        os.replace(tmp_path, target)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def run_template(
    root: Path,
    *,
    template: AutomationTemplate,
    set_values: dict[str, str],
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_inputs: dict[str, Any] = {name: spec.default for name, spec in template.inputs.items()}
    for key, value in set_values.items():
        if key not in resolved_inputs:
            raise TemplateValidationError(
                f"unknown input '{key}' for template '{template.metadata['id']}'"
            )
        resolved_inputs[key] = value

    artifacts: list[str] = []
    step_records: list[dict[str, Any]] = []
    context: dict[str, Any] = {
        "inputs": resolved_inputs,
        "template": template.metadata,
        "run": {"output_dir": output_dir.as_posix()},
    }

    for index, step in enumerate(template.workflow, start=1):
        params = interpolate_value(step.params, context)
        payload: dict[str, Any]
        ok = True
        if step.action == "repo.audit":
            profile = str(params.get("profile", "default"))
            changed_only = _as_bool(params.get("changed_only", False))
            audit = repo.run_repo_audit(root, profile=profile, changed_only=changed_only)
            payload = {
                "profile": profile,
                "changed_only": changed_only,
                "findings": len(audit.get("findings", [])),
                "checks": len(audit.get("checks", [])),
            }
            if isinstance(params.get("output_json"), str):
                target = Path(str(params["output_json"]))
                _write_json(target, audit)
                artifacts.append(target.as_posix())
            if isinstance(params.get("output_sarif"), str):
                target = Path(str(params["output_sarif"]))
                _write_json(target, repo._to_sarif(audit))
                artifacts.append(target.as_posix())
        elif step.action == "report.build":
            fmt = str(params.get("format", "html"))
            output = Path(str(params.get("output", output_dir / "dashboard.html")))
            build_dashboard(
                history_dir=root / ".sdetkit" / "history", output=output, fmt=fmt, since=None
            )
            payload = {"output": output.as_posix(), "format": fmt}
            artifacts.append(output.as_posix())
        elif step.action == "fs.write":
            target = Path(str(params.get("path")))
            content = str(params.get("content", ""))
            atomic_write_text(target, content)
            payload = {"path": target.as_posix(), "bytes": len(content.encode("utf-8"))}
            artifacts.append(target.as_posix())
        elif step.action == "shell.run":
            cmd = str(params.get("cmd", ""))
            shell_res = _run_shell(cmd, cwd=root)
            payload = shell_res
            ok = bool(shell_res.get("ok"))
            if isinstance(params.get("save_stdout"), str):
                stdout_path = Path(str(params["save_stdout"]))
                atomic_write_text(stdout_path, str(shell_res.get("stdout", "")))
                artifacts.append(stdout_path.as_posix())
        elif step.action == "artifacts.bundle":
            source_dir = Path(str(params.get("source_dir", output_dir)))
            target = Path(str(params.get("output", output_dir / "bundle.tar")))

            def _write_bundle(
                tmp_target: Path, *, source_dir: Path = source_dir, target: Path = target
            ) -> None:
                with tarfile.open(tmp_target, mode="w") as tf:
                    for path in sorted(source_dir.rglob("*")):
                        if path.is_dir() or path == target:
                            continue
                        rel = path.relative_to(source_dir).as_posix()
                        info = tarfile.TarInfo(name=rel)
                        data = path.read_bytes()
                        info.size = len(data)
                        info.uid = 0
                        info.gid = 0
                        info.uname = ""
                        info.gname = ""
                        info.mtime = 0
                        info.mode = 0o644
                        tf.addfile(info, io.BytesIO(data))

            _atomic_tar_write(target, _write_bundle)
            payload = {"output": target.as_posix()}
            artifacts.append(target.as_posix())
        else:
            payload = {"error": f"unsupported action '{step.action}'"}
            ok = False

        step_records.append(
            {
                "index": index,
                "id": step.step_id,
                "action": step.action,
                "params": params,
                "ok": ok,
                "payload": payload,
            }
        )
        if not ok:
            break

    status = "ok" if all(item["ok"] for item in step_records) else "error"
    record = {
        "captured_at": _captured_at(),
        "template": template.metadata,
        "inputs": resolved_inputs,
        "status": status,
        "steps": step_records,
        "artifacts": sorted(set(artifacts)),
    }
    digest = hashlib.sha256(canonical_json_bytes(record)).hexdigest()
    record["hash"] = digest
    record_path = output_dir / "run-record.json"
    _write_json(record_path, record)
    return record


def parse_set_values(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise TemplateValidationError(f"invalid --set value '{item}', expected key=value")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise TemplateValidationError(f"invalid --set value '{item}', missing key")
        parsed[key] = value
    return parsed


def pack_templates(root: Path, *, output: Path) -> dict[str, Any]:
    templates_dir = root / "templates" / "automations"
    files = sorted(path for path in templates_dir.glob("*.yaml") if path.is_file())

    def _write_pack(tmp_output: Path) -> None:
        with tarfile.open(tmp_output, mode="w") as tf:
            for path in files:
                rel = path.relative_to(root).as_posix()
                payload = path.read_bytes()
                info = tarfile.TarInfo(name=rel)
                info.size = len(payload)
                info.mtime = 0
                info.uid = 0
                info.gid = 0
                info.mode = 0o644
                info.uname = ""
                info.gname = ""
                tf.addfile(info, io.BytesIO(payload))

    _atomic_tar_write(output, _write_pack)
    return {
        "output": output.as_posix(),
        "count": len(files),
        "files": [p.relative_to(root).as_posix() for p in files],
    }
