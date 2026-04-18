# Why not just tools

SDETKit is not just a pile of standalone commands. It is a workflow-oriented toolkit for
turning repository checks, release gates, and evidence collection into deterministic outputs
that teams can run locally and in CI.

## What changes when you use SDETKit

- one command lane can collect multiple checks into one repeatable flow
- outputs are designed to be machine-readable as well as human-readable
- release decisions can be backed by structured evidence instead of ad hoc notes
- teams can standardize the same gate and reporting habits across repositories

## Where plain tools still fit

SDETKit does not replace linters, test runners, scanners, or CI platforms.
It composes them into repeatable operational lanes so that engineering teams spend less
time stitching together commands and more time acting on stable results.

## When to use it

Use SDETKit when you want:

- deterministic release preflight checks
- repeatable repo-readiness and doctor flows
- CI-friendly JSON and markdown evidence
- a shared command surface that helps teams move faster with less ambiguity
