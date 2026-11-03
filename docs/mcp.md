# Coding agents (MCP)

`sdetkit mcp` serves SDETKit to coding agents over the [Model Context Protocol](https://modelcontextprotocol.io/), so an agent can check its own work before it commits or opens a pull request: did the change pass the repository's tests, without weakening them?

It is a stdio server with two tools and no extra dependencies.

## Add it to an agent

Claude Code:

```bash
claude mcp add sdetkit -- python -m sdetkit mcp
```

Any client that reads an MCP server list (Cursor, VS Code, Codex and others) takes the same command:

```json
{
  "mcpServers": {
    "sdetkit": {
      "command": "python",
      "args": ["-m", "sdetkit", "mcp"]
    }
  }
}
```

Use the interpreter SDETKit is installed in. The tools run in the folder the agent starts the server in, unless a call names `repo_root`.

## Tools

### `verify_change`

Runs [`sdetkit verify change`](verify-change.md). With no arguments it verifies the agent's uncommitted work against `HEAD`: modified files, staged files and new untracked files, built through a throwaway git index, so the repository's own index and working tree are not touched. Pass `head` (and `base`) to verify commits instead, or `patch` for a diff file.

| Argument | What it does |
| --- | --- |
| `repo_root` | Repository to check |
| `base`, `head` | Commits to compare, instead of the uncommitted work |
| `patch` | A diff file to verify on top of `base` |
| `pytest_args` | Arguments for the test runner, such as test paths |
| `runner` | `auto` (default), `pytest`, `vitest`, `jest`, `node` or `go`; see [JavaScript and TypeScript](verify-change.md#javascript-and-typescript) and [Go](verify-change.md#go) |

The result text is the same summary the [verify-change action](verify-change.md#in-github-actions) posts on a pull request. The structured result carries `status` (`VERIFIED`, `REVIEW`, `FAILED`, `NOT_RUN`), `verdict`, `reasons`, `next_action`, `findings` and `proving_tests`, the change's tests that fail without it.

### `gate_fast`

Runs [`sdetkit gate fast`](gate-action.md) (the repository's lint, format, types and tests) and returns the verdict (`SHIP`, `REVIEW`, `NOT_RUN`, `NO_SHIP`), its reasons, the first failure with the command to run next, and the failed steps. `only` limits it to some steps, such as `ruff,pytest`.

## What to tell the agent

The server's instructions already ask agents to call `verify_change` before committing. To make it a rule, add a line to the agent's instructions file (`CLAUDE.md`, `AGENTS.md`):

```markdown
Before you commit or open a pull request, call the sdetkit `verify_change` tool and do not
proceed unless it reports VERIFIED, or explain each REVIEW finding.
```

## Boundaries

- The tools run the repository's own tests and tools, as the agent's own commands would. Each runs in a subprocess, so nothing they print reaches the protocol stream.
- Nothing is committed, pushed, applied or merged. A tool call can take as long as the test suite; `--timeout-seconds` (default 1800) caps it.
