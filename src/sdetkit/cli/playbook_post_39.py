from __future__ import annotations

from ._legacy_lane import run_lane

_DEFAULT_PAGE_TEMPLATE = "# Playbook post\n\n## Playbook post\n"
_CFG = {
    "name": "playbook-post",
    "page_path": "docs/integrations-playbook-post.md",
    "required_inputs": ["docs/artifacts/distribution-batch-pack/distribution-batch-summary.json"],
    "required_boards": ["docs/artifacts/distribution-batch-pack/delivery-board.md"],
    "summary_json": "playbook-post-summary.json",
    "summary_md": "playbook-post-summary.md",
    "pack_files": [
        "playbook-draft.md",
        "rollout-plan.csv",
        "kpi-scorecard.json",
        "execution-log.md",
        "delivery-board.md",
        "validation-commands.md",
    ],
    "evidence_json": "execution-summary.json",
    "text_output": " playbook post summary",
}


def main(argv: list[str] | None = None) -> int:
    return run_lane(argv, _CFG)
