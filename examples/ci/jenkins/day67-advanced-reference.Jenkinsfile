pipeline {
  agent any

  stages {
    stage('Lint') {
      steps {
        sh '''
          set -euo pipefail
          bash scripts/bootstrap.sh
          . .venv/bin/activate
          ruff check src tests
        '''
      }
    }

    stage('Test Matrix') {
      matrix {
        axes {
          axis {
            name 'PYTHON_VERSION'
            values '3.10', '3.11'
          }
        }
        stages {
          stage('Run Unit Tests') {
            steps {
              sh '''
                set -euo pipefail
                bash scripts/bootstrap.sh
                . .venv/bin/activate
                pytest -q
              '''
            }
          }
        }
      }
    }

    stage('Parallel Governance Checks') {
      parallel {
        stage('Contract') {
          steps {
            sh '''
              set -euo pipefail
              bash scripts/bootstrap.sh
              . .venv/bin/activate
              python scripts/check_day67_integration_expansion3_closeout_contract.py --skip-evidence
            '''
          }
        }
        stage('Security') {
          steps {
            sh '''
              set -euo pipefail
              bash scripts/bootstrap.sh
              . .venv/bin/activate
              ./security.sh
            '''
          }
        }
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'docs/artifacts/day67-integration-expansion3-closeout-pack/**', allowEmptyArchive: true
      archiveArtifacts artifacts: 'build/security.sarif', allowEmptyArchive: true
    }
    unsuccessful {
      echo 'Trigger rollback runbook for Day 67 integration expansion lane.'
    }
  }
}
