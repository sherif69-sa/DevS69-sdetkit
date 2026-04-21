"""Backward-compatible ops_control module with monkeypatch-friendly hooks."""

from __future__ import annotations

from importlib import import_module as _import_module

_IMPL = _import_module("sdetkit.ops.ops_control")
_ORIG_RUN = _IMPL.run
_ORIG_PLAN = _IMPL.plan
_ORIG_TASK_CATALOG = _IMPL._task_catalog
_ORIG_CLI = _IMPL.cli

_PATCHABLE = [
    "discover",
    "init_layout",
    "_profile_tasks",
    "_inputs_hash",
    "_cache_status",
    "subprocess",
]


def _sync_patchables() -> None:
    for name in _PATCHABLE:
        if name in globals():
            setattr(_IMPL, name, globals()[name])


def _task_catalog():
    _sync_patchables()
    # If caller monkeypatched this symbol on wrapper module, __dict__ will differ.
    if globals().get("_task_catalog") is not _task_catalog:
        return globals()["_task_catalog"]()
    return _ORIG_TASK_CATALOG()


def plan(profile: str, apply: bool, no_cache: bool):
    _sync_patchables()
    if globals().get("plan") is not plan:
        return globals()["plan"](profile, apply, no_cache)
    return _ORIG_PLAN(profile, apply, no_cache)


def run(
    profile: str, jobs: int, apply: bool, no_cache: bool, fail_fast: bool, keep_going: bool
) -> int:
    _sync_patchables()
    if globals().get("run") is not run:
        return int(globals()["run"](profile, jobs, apply, no_cache, fail_fast, keep_going))
    return int(_ORIG_RUN(profile, jobs, apply, no_cache, fail_fast, keep_going))


def cli(argv=None):
    _sync_patchables()
    old_run, old_plan, old_catalog = _IMPL.run, _IMPL.plan, _IMPL._task_catalog
    try:
        _IMPL.run = globals().get("run", run)
        _IMPL.plan = globals().get("plan", plan)
        _IMPL._task_catalog = globals().get("_task_catalog", _task_catalog)
        return int(_ORIG_CLI(argv))
    finally:
        _IMPL.run, _IMPL.plan, _IMPL._task_catalog = old_run, old_plan, old_catalog


def __getattr__(name: str):
    return getattr(_IMPL, name)


for _name in dir(_IMPL):
    if _name.startswith("__") or _name in {"cli", "run", "plan", "_task_catalog"}:
        continue
    globals()[_name] = getattr(_IMPL, _name)

__all__ = [name for name in globals() if not name.startswith("__")]
