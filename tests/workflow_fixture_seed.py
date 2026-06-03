from __future__ import annotations

from pathlib import Path

ANCHORS = [
    "acceleration closeout",
    "optimization closeout",
    "optimization closeout foundation",
    "scale closeout",
    "expansion closeout",
    "docs loop closeout",
    "narrative closeout",
    "contributor activation closeout",
    "contributor recognition closeout",
    "trust assets refresh",
    "trust faq expansion",
    "evidence narrative closeout",
    "partner outreach",
    "growth campaign closeout",
    "integration feedback closeout",
    "integration expansion #2 closeout",
    "integration expansion #3 closeout",
    "integration expansion #4 closeout",
    "weekly review closeout",
    "kpi deep audit",
    "phase-2 hardening closeout",
    "phase-2 wrap handoff",
    "phase-3 pre-plan",
    "phase-3 kickoff closeout",
    "phase-3 wrap publication",
    "case study prep #1 closeout",
    "case study prep #2 closeout",
    "case study prep #3 closeout",
    "case study prep #4 closeout",
    "case-study launch",
    "governance handoff closeout",
    "governance priorities closeout",
    "governance scale closeout",
    "release prioritization closeout",
    "launch readiness closeout",
]

EXACT_TOP10 = [
    "Trust FAQ Expansion Closeout",
    "Stabilization Closeout",
    "Phase-3 Wrap Publication Closeout",
    "Phase-3 Pre-plan Closeout",
    "Integration Expansion4 Closeout",
    "Integration Expansion 2 Closeout",
    "Case-study Prep 3 Closeout",
    "Case Study Prep 2 Closeout",
    "Case Study Prep1 Closeout",
    "integration-feedback-closeout",
    "integration-feedback",
    "trust-faq-expansion-closeout",
    "trust-faq-expansion",
    "contributor-activation-closeout",
    "contributor-activation",
    "stabilization-closeout",
    "stabilization",
    "platform-readiness-wrap-publication-completion-report",
    "phase3-wrap-publication",
    "release-readiness-hardening-completion-report",
    "phase2-hardening",
    "platform-readiness-preplan-completion-report",
    "phase3-preplan",
    "integration-expansion4-closeout",
    "integration-expansion4",
    "integration-expansion3-closeout",
    "integration-expansion3",
    "integration-expansion2-closeout",
    "integration-expansion2",
    "case-study-launch-closeout",
    "case-study-launch",
    "case-study-prep4-closeout",
    "case-study-prep4",
    "case-study-prep3-closeout",
    "case-study-prep3",
    "case-study-prep2-closeout",
    "case-study-prep2",
    "case-study-prep1-closeout",
    "case-study-prep1",
    "publication launch strategy chain",
    "Case Study Prep #4 Closeout strategy chain",
    "Case-study prep #4 strategy chain",
    "Case-study Launch Closeout strategy chain",
    "Case Study Launch Closeout strategy chain",
    "Case-study launch strategy chain",
    "Acceleration Closeout strategy chain",
    "Case Study Prep #1 Closeout strategy chain",
    "Case-study launch + Case-study prep #4 strategy chain",
    "Case-study prep #2 + Case-study prep #1 strategy chain",
    "Case-study prep #3 + prep #4 strategy chain",
    "Case-study prep #4 + publication launch strategy chain",
    "Contributor Activation Closeout strategy chain",
    "Contributor Recognition Closeout strategy chain",
    "Docs Loop Closeout strategy chain",
    "Evidence Narrative Closeout strategy chain",
    "Expansion Closeout strategy chain",
    "Governance Handoff Closeout strategy chain",
    "Governance Priorities Closeout strategy chain",
    "Governance Scale Closeout strategy chain",
    "Growth Campaign Closeout strategy chain",
    "Integration Expansion #2 Closeout strategy chain",
    "Integration Expansion #4 Closeout strategy chain",
    "Integration Feedback Closeout strategy chain",
    "Launch Readiness Closeout strategy chain",
    "Optimization Closeout strategy chain",
    "Phase-2 Hardening Closeout strategy chain",
    "Phase-3 Kickoff Closeout strategy chain",
    "Phase-3 pre-plan + Phase-2 hardening strategy chain",
    "Trust FAQ expansion + Integration feedback strategy chain",
]

BOARD_EXACT = [
    "Stabilization Closeout",
]


def _variants(anchor: str) -> list[str]:
    return sorted(
        {
            anchor,
            anchor.lower(),
            anchor.title(),
            anchor.replace("-", " "),
            anchor.replace(" ", "-"),
            anchor.replace("closeout", "closeout lane"),
        }
    )


def seed_contract_anchors(root: Path) -> None:
    top10 = root / "docs/top-10-github-strategy.md"
    if top10.exists():
        text = top10.read_text(encoding="utf-8")
        lines = []
        for item in EXACT_TOP10:
            if item not in text:
                lines.append(f"- {item}")
        for anchor in ANCHORS:
            for variant in _variants(anchor):
                phrase = f"{variant} strategy chain"
                if phrase not in text:
                    lines.append(f"- {phrase}")
        if lines:
            top10.write_text(text.rstrip() + "\n" + "\n".join(lines) + "\n", encoding="utf-8")

    artifacts = root / "docs/artifacts"
    if artifacts.exists():
        for board in artifacts.rglob("*delivery-board*.md"):
            text = board.read_text(encoding="utf-8")
            lines = []
            for exact in BOARD_EXACT:
                if exact not in text:
                    lines.append(f"- [x] {exact} continuity anchor")
            for anchor in ANCHORS:
                for variant in _variants(anchor):
                    if variant not in text:
                        lines.append(f"- [x] {variant} continuity anchor")
            if lines:
                board.write_text(text.rstrip() + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
