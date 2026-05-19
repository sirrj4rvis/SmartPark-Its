pipeline {
    agent any

    environment {
        DOCKER_IMAGE = "YOUR_DOCKERHUB_USERNAME/smart-parking"
    }

    tools {
        sonarQubeScanner 'sonar-scanner'
    }

    stages {

        stage('Clone Repository') {
            steps {
                git branch: 'main',
                url: 'https://github.com/sirrj4vis/smart-parking.git'
            }
        }

        stage('SonarCloud Analysis') {
            steps {
                withSonarQubeEnv('sonarcloud') {

                    bat """
                    sonar-scanner ^
                    -Dsonar.projectKey=sirrj4vis_smart-parking ^
                    -Dsonar.organization=sirrj4vis ^
                    -Dsonar.sources=. ^
                    -Dsonar.host.url=https://sonarcloud.io
                    """
                }
            }
        }

        stage('Trivy Scan') {
            steps {
                bat 'trivy fs . > trivy-report.txt'
            }
        }

        stage('Build Docker Image') {
            steps {
                bat 'docker build -t %DOCKER_IMAGE% .'
            }
        }

        stage('Push Docker Image') {
            steps {

                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {

                    bat 'docker login -u %DOCKER_USER% -p %DOCKER_PASS%'
                    bat 'docker push %DOCKER_IMAGE%'
                }
            }
        }

        stage('Deploy') {
            steps {
                echo 'Deployment handled through Render'
            }
        }
    }
}