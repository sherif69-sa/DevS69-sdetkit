# Distribution reproducibility probe

This is a report-only comparison, not a new release gate. Build the same commit twice in clean directories, with the same Python, build tooling, dependency resolution and SOURCE_DATE_EPOCH. Record those versions and the commit with the report. Do not compare a dirty working tree with a clean checkout.

Example from the repository root, using a temporary directory:

```bash
root=$(pwd)
commit=$(git rev-parse HEAD)
export SOURCE_DATE_EPOCH=$(git show -s --format=%ct "$commit")
work=$(mktemp -d)
git clone --no-local "$root" "$work/one"
git clone --no-local "$root" "$work/two"
git -C "$work/one" checkout --detach "$commit"
git -C "$work/two" checkout --detach "$commit"
python -m build "$work/one" --outdir "$work/dist-one"
python -m build "$work/two" --outdir "$work/dist-two"
python scripts/check_build_reproducibility.py \
  --left "$work/dist-one" --right "$work/dist-two" \
  --out build/reproducibility.json
```

The comparison reads archives without extracting them. It reports exact SHA-256 equality separately from member-content equality. Missing artifacts cannot pass. Empty inputs, malformed archives and read errors are tool errors, not evidence of reproducibility. A completed non-identical comparison exits0 because the probe is report-only; inspect `reproducible`, not only the exit code. Tool errors exit1.

## Initial observation

On commit5fd0d11e0096634a8a8c7759e9eeb0908897eaba, two clean local builds with Python3.12 and a fixed SOURCE_DATE_EPOCH produced identical wheels,233 entries, but different source archives with744 entries. Member names and file contents matched. Archive member timestamps differed. A separate repeated build in one directory showed the same wheel/source-archive distinction.

This does not prove cross-platform or dependency-version reproducibility. The build backend and dependency resolution are not fully pinned. A later change should address timestamp normalization deliberately, repeat this probe and preserve the ordinary build, Twine and wheel-content checks. Do not silently rewrite or publish release artifacts as part of this report.
