// SDETKit verify change for Jenkins: on pull request builds (multibranch), runs the change's
// tests before and after it in a temporary clone, checks they were not removed, emptied or
// skipped, and archives the report and the attestation. VERIFIED passes; REVIEW marks the
// build unstable; FAILED and NOT_RUN fail it. Needs python3 and git on the agent.
// Guide: https://sherif69-sa.github.io/DevS69-sdetkit/verify-change/
pipeline {
  agent any

  environment {
    // What pip installs; a version pin, or a git URL to try an unreleased change.
    SDETKIT_PACKAGE = 'sdetkit==2.0.0'
    // Extra `verify change` options, separated by spaces, for example '--mutate'.
    SDETKIT_ARGS = ''
  }

  stages {
    stage('Set up the project') {
      steps {
        // Your project and its test dependencies, in the repository's .venv; replace this
        // with `uv sync`, `poetry install` or your own.
        sh '''
          python3 -m venv .venv
          if [ -f pyproject.toml ] || [ -f setup.py ]; then .venv/bin/python -m pip install -e ".[test]"; fi
        '''
      }
    }

    stage('SDETKit verify change') {
      when { changeRequest() }
      steps {
        script {
          // The pull request's own change: from where it left its target branch to its head.
          def status = sh(returnStatus: true, script: '''
            git fetch --quiet --no-tags origin "+refs/heads/${CHANGE_TARGET}:refs/remotes/origin/${CHANGE_TARGET}"
            BASE="$(git merge-base "origin/${CHANGE_TARGET}" HEAD)"
            SDETKIT_VENV="$(mktemp -d)/sdetkit"
            python3 -m venv "$SDETKIT_VENV"
            "$SDETKIT_VENV/bin/python" -m pip install --quiet --disable-pip-version-check "$SDETKIT_PACKAGE"
            "$SDETKIT_VENV/bin/python" -m sdetkit verify change --base "$BASE" --head HEAD $SDETKIT_ARGS --out-dir build/sdetkit/change-verification --summary-out build/sdetkit/verify-change.md
          ''')
          if (status == 1) {
            unstable('SDETKit verify change: REVIEW')
          } else if (status != 0) {
            error("SDETKit verify change: exit code ${status} (FAILED or NOT_RUN)")
          }
        }
      }
    }
  }

  post {
    always {
      sh 'cat build/sdetkit/verify-change.md 2>/dev/null || true'
      junit allowEmptyResults: true, testResults: 'build/sdetkit/change-verification/tests-head.xml'
      archiveArtifacts artifacts: 'build/sdetkit/**', allowEmptyArchive: true
    }
  }
}
