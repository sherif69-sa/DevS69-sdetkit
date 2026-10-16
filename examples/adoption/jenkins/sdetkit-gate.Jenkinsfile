// SDETKit gate for Jenkins: runs `sdetkit gate fast`, fails the build unless the gate
// passes, and archives the report. Copy it into your Jenkinsfile, or add its stages to
// your pipeline. Needs python3 on the agent (or use `agent { docker { image 'python:3.12' } }`).
// Guide: https://sherif69-sa.github.io/DevS69-sdetkit/integrations/jenkins-reference-pack/
pipeline {
  agent any

  environment {
    // What pip installs; a version pin, or a git URL to try an unreleased change.
    SDETKIT_PACKAGE = 'sdetkit==2.0.0'
    // Extra `gate fast` options, separated by spaces, for example '--skip mypy'.
    SDETKIT_ARGS = ''
  }

  stages {
    stage('Set up the project') {
      steps {
        // Your project and its test dependencies. The gate runs ruff, mypy and pytest in
        // the repository's .venv; replace this with `uv sync`, `poetry install` or your own.
        sh '''
          python3 -m venv .venv
          if [ -f pyproject.toml ] || [ -f setup.py ]; then .venv/bin/python -m pip install -e ".[test]"; fi
        '''
      }
    }

    stage('SDETKit gate') {
      steps {
        // SDETKit gets an environment of its own, so it never changes the project's. The
        // checks run in the repository's .venv, venv, Poetry or Pipenv environment when it
        // has one, else in the agent's python3.
        sh '''
          SDETKIT_VENV="$(mktemp -d)/sdetkit"
          python3 -m venv "$SDETKIT_VENV"
          "$SDETKIT_VENV/bin/python" -m pip install --quiet --disable-pip-version-check "$SDETKIT_PACKAGE"
          PYTHON_ARGS=""
          if [ ! -d .venv ] && [ ! -d venv ] && [ ! -f poetry.lock ] && [ ! -f Pipfile.lock ]; then PYTHON_ARGS="--python $(command -v python3)"; fi
          mkdir -p build/sdetkit
          "$SDETKIT_VENV/bin/python" -m sdetkit gate fast $PYTHON_ARGS $SDETKIT_ARGS --format json --stable-json --out build/sdetkit/gate.json --summary-out build/sdetkit/gate.md
        '''
      }
    }
  }

  post {
    always {
      sh 'cat build/sdetkit/gate.md 2>/dev/null || true'
      archiveArtifacts artifacts: 'build/sdetkit/**', allowEmptyArchive: true
    }
  }
}
