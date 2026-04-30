# Plugins

sdetkit supports plugin discovery from both entry points and `.sdetkit/plugins.toml`.

```toml
[notify]
my_stdout = "my_pkg.notify:factory"

[ops_tasks]
my_task = "my_pkg.ops:task_factory"
```

Built-in notifier: `sdetkit notify stdout --message "hello"`.

Optional adapters are soft dependencies with friendly configuration errors:

- `telegram`: gated live-send support is available only with explicit credentials and `--real-send`.
- `whatsapp`: incubator/config-probe only; the optional extra installs the dependency boundary, but live real-send is not implemented.
