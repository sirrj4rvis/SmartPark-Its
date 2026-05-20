pipeline {
    agent any

    environment {
        DOCKER_IMAGE = "sirrj4rvis/smart-parking"
    }

    stages {

        stage('Clone Repository') {
            steps {
                git branch: 'main',
                credentialsId: 'github-token',
                url: 'https://github.com/sirrj4rvis/smart-parking.git'
            }
        }

        stage('Install Python Dependencies') {
            steps {
                bat 'pip install -r requirements.txt'
            }
        }

        stage('SonarCloud Analysis') {
            steps {
                script {

                    def scannerHome = tool 'sonar-scanner'

                    withSonarQubeEnv('sonar-server') {

                        bat """
                        ${scannerHome}\\bin\\sonar-scanner.bat ^
                        -Dsonar.projectKey=sirrj4rvis_smart-parking ^
                        -Dsonar.organization=sirrj4rvis ^
                        -Dsonar.sources=. ^
                        -Dsonar.host.url=https://sonarcloud.io
                        """
                    }
                }
            }
        }

        stage('Trivy Scan') {
            steps {
                bat '"C:\\Trivy\\trivy.exe" fs . > trivy-report.txt'
            }
        }

        stage('Check Docker') {
            steps {
                bat '"C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe" --version'
            }
        }

        stage('Build Docker Image') {
            steps {
                bat '"C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe" build -t sirrj4rvis/smart-parking .'
            }
        }

        stage('Push Docker Image') {
            steps {

                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
        )]) {

            bat '"C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe" login -u %DOCKER_USER% -p %DOCKER_PASS%'
            bat '"C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe" push %DOCKER_IMAGE%'
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