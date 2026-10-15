# Tool server

`python -m sdetkit ops serve` starts a local HTTP/JSON server that runs SDETKit actions and workflows on request.

```bash
python -m sdetkit ops serve --port 8765
# sdetkit ops serve listening on http://127.0.0.1:8765
# bearer token: <token>
curl -H "Authorization: Bearer <token>" http://127.0.0.1:8765/actions
```

## Endpoints

- `GET /health` (no token needed)
- `GET /actions`
- `POST /run-action`
- `POST /run-workflow`
- `GET /runs`
- `GET /runs/<id>`

## Safety model

- **Every request except `/health` needs the bearer token.** The server prints a fresh token at start-up. To choose it yourself, set `SDETKIT_SERVER_TOKEN` before starting the server; the token is then not printed. Without the token, a web page open in your browser could otherwise send the server requests.
- **Loopback only by default.** The server binds to `127.0.0.1`. While it does, it refuses requests addressed to any other host name, which stops DNS-rebinding pages. Listening on another interface needs `--allow-remote`. The server speaks plain HTTP, so put it behind TLS if you do that.
- **Paths stay in the working directory.** For `/run-action`, the `root`, `repo_root` and `output` inputs must resolve inside the directory the server was started in. `/run-workflow` runs only workflow files in that directory, writes artifacts under `artifacts/`, and follows the workflow's policy (for example `allow_shell`).
- Invalid run IDs and path traversal are rejected.
