// PortfoLive CI/CD:
//   checkout -> unit tests + coverage -> SonarQube + quality gate -> build image
//   -> OWASP ZAP (DAST) against the running container -> push -> blue/green deploy -> Slack
//
// Jenkins credentials required (see docs/SETUP_GUIDE.md, Part 9):
//   dockerhub      Username + password   (Docker Hub user + access token)
//   kubeconfig     Secret file           (ansible/artifacts/k3s.yaml)
//   slack-webhook  Secret text           (Slack or Teams incoming-webhook URL)
//   sonar-token    Secret text           (SonarQube user token)  -> also set up as server "sonarqube"
pipeline {
  agent any
  options { timestamps(); disableConcurrentBuilds(); timeout(time: 40, unit: 'MINUTES') }
  triggers { pollSCM('H/3 * * * *') }   // keeps Jenkins' port closed to the internet; see guide for webhooks
  environment {
    DOCKERHUB  = credentials('dockerhub')       // exposes DOCKERHUB_USR / DOCKERHUB_PSW
    KUBECONFIG = credentials('kubeconfig')
    NET        = "zap-net-${env.BUILD_NUMBER}"
    APP_NAME   = "portfolive-dast-${env.BUILD_NUMBER}"
  }

  stages {
    stage('Prepare') {
      steps {
        script {
          env.SHORT_SHA = sh(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
          env.IMAGE = "${env.DOCKERHUB_USR}/portfolive:${env.SHORT_SHA}"
        }
        sh 'rm -rf reports zap-reports && mkdir -p reports zap-reports && chmod 777 zap-reports'
        script { notify("Build #${env.BUILD_NUMBER} started for `${env.SHORT_SHA}`") }
      }
    }

    stage('Unit tests + coverage') {
      steps {
        // Runs pytest inside the Dockerfile "test" stage and exports coverage.xml. Jenkins needs only Docker.
        sh 'DOCKER_BUILDKIT=1 docker build --target test-report --output type=local,dest=reports .'
        // Make coverage paths relative to the repo root so SonarQube can match them to files
        sh '''
          sed -i 's#filename="#filename="server/app/#; s#<source>.*</source>#<source>.</source>#' reports/coverage.xml
        '''
      }
    }

    stage('SonarQube analysis') {
  steps {
    withSonarQubeEnv('sonarqube') {
      sh '''
        docker run --rm -u $(id -u):$(id -g) \
          -e SONAR_HOST_URL="$SONAR_HOST_URL" -e SONAR_TOKEN="$SONAR_AUTH_TOKEN" \
          -e SONAR_USER_HOME=/tmp/sonar \
          -v "$PWD:/usr/src" -w /usr/src sonarsource/sonar-scanner-cli \
          -Dsonar.working.directory=.scannerwork
      '''
    }
  }
}
    stage('Quality gate') {
      steps { timeout(time: 10, unit: 'MINUTES') { waitForQualityGate abortPipeline: true } }
    }

    stage('Build image') {
      steps { sh 'docker build -t "$IMAGE" .' }
    }

    stage('DAST: OWASP ZAP') {
      steps {
        sh '''
          docker network create "$NET"
          docker run -d --name "$APP_NAME" --network "$NET" --network-alias app \
            -e JWT_SECRET="$(openssl rand -hex 32)" "$IMAGE"
          for i in $(seq 1 30); do
            docker exec "$APP_NAME" python -c "import urllib.request as u; u.urlopen('http://localhost:4000/health')" && break
            sleep 2
          done

          # Exit codes: 0 pass, 1 FAIL-level finding, 2 warnings only, 3 error. Only 1 and 3 fail the build.
          set +e
          docker run --rm --network "$NET" -v "$PWD/zap-reports:/zap/wrk:rw" ghcr.io/zaproxy/zaproxy:stable \
            zap-baseline.py -t http://app:4000 -r zap-baseline.html -J zap-baseline.json
          RC1=$?
          docker run --rm --network "$NET" -v "$PWD/zap-reports:/zap/wrk:rw" ghcr.io/zaproxy/zaproxy:stable \
            zap-api-scan.py -t http://app:4000/openapi.json -f openapi -r zap-api.html -J zap-api.json
          RC2=$?
          set -e
          echo "ZAP baseline rc=$RC1, api-scan rc=$RC2"
          for rc in $RC1 $RC2; do
            if [ "$rc" -eq 1 ] || [ "$rc" -ge 3 ]; then echo "ZAP found FAIL-level issues"; exit 1; fi
          done
        '''
      }
      post {
        always {
          sh 'docker rm -f "$APP_NAME" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true'
          archiveArtifacts artifacts: 'zap-reports/*', allowEmptyArchive: true
        }
      }
    }

    stage('Push image') {
      steps {
        sh '''
          echo "$DOCKERHUB_PSW" | docker login -u "$DOCKERHUB_USR" --password-stdin
          docker push "$IMAGE"
        '''
      }
    }

    stage('Deploy (blue/green)') {
      steps {
        sh '''
          kubectl apply -f k8s/app/pvc.yaml -f k8s/app/service.yaml

          ACTIVE=$(kubectl get svc portfolive -o jsonpath='{.spec.selector.color}')
          [ "$ACTIVE" = "green" ] && NEXT=blue || { ACTIVE=blue; NEXT=green; }
          echo "Live: $ACTIVE  ->  deploying $NEXT"

          # The live color keeps running its CURRENT image; only the idle color gets the new one.
          LIVE_IMAGE=$(kubectl get deploy portfolive-$ACTIVE -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || true)
          [ -n "$LIVE_IMAGE" ] || LIVE_IMAGE="$IMAGE"
          IMAGE="$LIVE_IMAGE" envsubst < k8s/app/deployment-$ACTIVE.yaml | kubectl apply -f -
          IMAGE="$IMAGE"      envsubst < k8s/app/deployment-$NEXT.yaml   | kubectl apply -f -
          kubectl apply -f k8s/app/hpa-blue.yaml -f k8s/app/hpa-green.yaml

          kubectl rollout status deployment/portfolive-$NEXT --timeout=240s
          kubectl patch svc portfolive -p "{\\"spec\\":{\\"selector\\":{\\"app\\":\\"portfolive\\",\\"color\\":\\"$NEXT\\"}}}"
          echo "Traffic now served by $NEXT. Roll back by patching the selector back to $ACTIVE."
        '''
      }
    }
  }

  post {
    success { script { notify(":white_check_mark: *PortfoLive* build #${env.BUILD_NUMBER} deployed `${env.SHORT_SHA}` <${env.BUILD_URL}|open>") } }
    failure { script { notify(":x: *PortfoLive* build #${env.BUILD_NUMBER} FAILED at `${env.STAGE_NAME}`. Live site untouched. <${env.BUILD_URL}console|logs>") } }
    always  { sh 'docker image prune -f >/dev/null 2>&1 || true' }
  }
}

// Works with Slack and Microsoft Teams incoming webhooks. Never fails the build.
def notify(String text) {
  try {
    withCredentials([string(credentialsId: 'slack-webhook', variable: 'HOOK')]) {
      writeFile file: 'notify.json', text: groovy.json.JsonOutput.toJson([text: text])
      sh 'curl -s -m 10 -X POST -H "Content-Type: application/json" --data @notify.json "$HOOK" >/dev/null || true'
    }
  } catch (err) {
    echo "Notification skipped: ${err.message}"
  }
}
