# Azure DevOps discovery limitations

The Azure DevOps adapter is intentionally conservative. It reads repository-owned pipeline YAML and reports only simple literal script values. It does not claim to reproduce Azure DevOps compilation, runtime expansion, task semantics, or service behavior.

Review is required when the pipeline contains templates, expressions, variables, matrices, tasks, deployments, service connections, external resources, multiline scripts, or ambiguous pipeline-file selection.
