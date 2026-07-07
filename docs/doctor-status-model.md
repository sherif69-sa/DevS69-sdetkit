# Doctor status model

This guide explains how to read the status values in the Doctor report contract.

## Status values

`green` means the current Doctor payload did not report active findings.

`review_required` means the report found information that should be inspected before the next repository action.

A stop-state means the report found a condition that should pause the current workflow until the condition is understood.

## Confidence values

`low` means the report has limited input.

`medium` means the report has enough input to guide a focused check.

`high` means the report has direct finding or bundle input.

## Summary fields

The `summary` object gives a compact view of the report. It should be stable enough for logs and dashboards, but the full report should still be read before acting.

## Roadmap alignment

The `roadmap_alignment` object groups the report into lanes. This helps keep Doctor output connected to repository reliability work instead of making the report a disconnected status page.

## Practical reading order

Read the report in this order:

1. `status`
2. `primary_finding`
3. `summary`
4. `findings`
5. `roadmap_alignment`
6. `proof_commands`
