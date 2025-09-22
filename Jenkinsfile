pipeline {
  agent any
  triggers {
    githubPush()
    pollSCM('H H * * *')
  }
  environment {
    MAIL_RECIPIENTS = 'dev+tests-reports@wazo.community'
  }
  options {
    skipStagesAfterUnstable()
    timestamps()
    buildDiscarder(logRotator(numToKeepStr: '10'))
  }
  stages {
    stage('Debian build and deploy') {
      steps {
        build job: 'build-package-no-arch', parameters: [
          string(name: 'PACKAGE', value: "wazo-provd"),
          string(name: "BRANCH", value: "bookworm"),
          string(name: "DISTRIBUTION", value: "wazo-dev-bookworm"),
        ]
      }
    }
    stage('Docker build') {
      steps {
        sh "docker build -t wazoplatform/wazo-provd:bookworm ."
      }
    }
    stage('Docker publish') {
      steps {
        sh "docker push wazoplatform/wazo-provd:bookworm"
      }
    }
  }
  post {
    failure {
      emailext to: "${MAIL_RECIPIENTS}", subject: '${DEFAULT_SUBJECT}', body: '${DEFAULT_CONTENT}'
    }
    fixed {
      emailext to: "${MAIL_RECIPIENTS}", subject: '${DEFAULT_SUBJECT}', body: '${DEFAULT_CONTENT}'
    }
  }
}
