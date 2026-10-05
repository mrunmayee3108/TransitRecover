pipeline {
    agent any

    triggers {
        githubPush()
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Docker Build Verification') {
            steps {
                sh 'docker build .'
            }
        }
    }

    post {
        success {
            echo 'Docker image built successfully without errors.'
        }
        failure {
            echo 'Docker build failed.'
        }
    }
}
