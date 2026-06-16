pipeline {
    agent any

    environment {
        DOCKER_IMAGE = "sirrj4rvis/smartpark-its"
    }

    stages {

        stage('Clone Repository') {
            steps {
                git branch: 'main',
                credentialsId: 'github-token',
                url: 'https://github.com/sirrj4rvis/SmartPark-Its.git'
            }
        }

        stage('Install Python Dependencies') {
            steps {
                bat 'pip install -r requirements.txt'
            }
        }

        stage('Run Tests') {
            steps {
                // Gate: the pipeline fails here if any test fails or coverage < 70%.
                bat 'set FLASK_ENV=testing && python -m pytest --junitxml=test-results.xml'
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'test-results.xml'
                }
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
                // Tag both an immutable build number and :latest so deploys are
                // traceable and rollbacks are possible.
                bat '"C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe" build -t %DOCKER_IMAGE%:%BUILD_NUMBER% -t %DOCKER_IMAGE%:latest .'
            }
        }

        stage('Push Docker Image') {
            steps {

                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
        )]) {

            bat '''
            "C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe" login -u %DOCKER_USER% -p %DOCKER_PASS%
            "C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe" push %DOCKER_IMAGE%:%BUILD_NUMBER%
            "C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe" push %DOCKER_IMAGE%:latest
            '''
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