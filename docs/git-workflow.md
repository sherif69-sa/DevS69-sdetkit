# Git workflow: branch tracking health

This quick reference keeps branch tracking deterministic so ahead/behind status is always visible.

## 1) Set the remote (if missing)

Check remotes:

```bash
git remote -v
```

If `origin` is missing, add it:

```bash
git remote add origin <git@github.com:ORG/REPO.git>
# or
git remote add origin <https://github.com/ORG/REPO.git>
```

Verify:

```bash
git remote -v
```

## 2) Set upstream for the current branch

For the current branch (first push):

```bash
git push -u origin "$(git branch --show-current)"
```

If branch already exists remotely, set tracking without pushing:

```bash
git branch --set-upstream-to "origin/$(git branch --show-current)"
```

## 3) Verify tracking branch

```bash
git status -sb
git rev-parse --abbrev-ref --symbolic-full-name @{u}
```

Expected:
- `git status -sb` shows `## <branch>...origin/<branch>`.
- `git rev-parse ... @{u}` prints the upstream ref (for example `origin/main`).

## 4) Read ahead/behind output

Use either built-in status or helper script:

```bash
git status -sb
bash scripts/dev.sh git-health
```

Interpretation:
- `ahead N`: local branch has `N` commits not on upstream.
- `behind N`: upstream has `N` commits not in local.
- both can be non-zero when branch histories diverge.

## 5) Troubleshooting

### `NO_UPSTREAM`

Symptoms:
- helper script prints `NO_UPSTREAM`
- `git rev-parse --abbrev-ref --symbolic-full-name @{u}` fails

Fix:

```bash
git push -u origin "$(git branch --show-current)"
# or
git branch --set-upstream-to "origin/$(git branch --show-current)"
```

### Detached `HEAD`

Symptoms:
- `git branch --show-current` is empty
- helper script reports detached `HEAD`

Fix:

```bash
git switch -c <new-branch-name>
# then set upstream
git push -u origin <new-branch-name>
```

## Daily check (copy/paste)

```bash
bash scripts/dev.sh git-health
git status -sb
```

Safety: these commands are non-destructive and do not use force push.
