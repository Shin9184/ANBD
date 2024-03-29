from github import Github
from slack import Slack
from gradle import Gradle
from sonarqube import Sonarqube
from dockerhub import Dockerhub
from dependency import Dependency
from anchore import Anchore
from argocd import Argocd
from variable import Variable
import yaml
from jenkinsapi.jenkins import Jenkins
import urllib.parse
import requests
import base64
from xml.etree.ElementTree import parse
import sys
import os

def stringToBase64(s):
        return base64.b64encode(s.encode('utf-8'))

def xml_modify(filename, **kargs):
    tree = parse(filename)
    root = tree.getroot()
    for tag, value in kargs.items():
        for i in root.iter(tag):
            i.text = value
    tree.write(filename, encoding='UTF-8', xml_declaration=True)


if sys.argv[1] == "start":

    var = Variable(sys.argv[2])
    toolList = var.getToolList()
    pluginList = var.getPluginList()
    stages = []

    if "jenkins" not in toolList:
        print("Not exist jenkins tool in your yaml!")
        exit()

    # 0. Jenkins
    jenkins_url = "http://{}".format(var.getJenkinsData()['url'])
    jenkins = Jenkins(jenkins_url, username=var.getJenkinsData()['username'], password=var.getJenkinsData()['password'], useCrumb=True)
    print("jenkins plugin installing...")
    jenkins.install_plugins(pluginList)
    print("Done...")

    # 1. Github
    # 1-1. Github webhook configuration
    if "github" in toolList:
        github_apiurl = "https://api.github.com/repos/{0}/{1}/hooks".format(var.getGithubData()['username'], var.getGithubData()['reponame'])
        github_body = {
            "name": "web",
            "events": var.getGithubWebhook()['events'],
            "active": var.getGithubWebhook()['active'],
            "config": {
                "url": "http://{}/github-webhook/".format(var.getJenkinsData()['url']),
                "content_type": var.getGithubWebhook()['contenttype']
            }
        }
        github = Github(jenkins, token=var.getGithubData()['token'], cred_id=var.getGithubCred()['id'], cred_description=var.getGithubCred()['description'], url=var.getGithubData()['url'])
        response = github.call_api("POST", github_apiurl, github_body)
        if response.status_code == 201:
            print("Created webhook in Github repository")
        else:
            print("Already exists webhook in github repository")

    # 1-2. Create github credential in jenkins server
        github.createCredential()

    # 1-3. Github configuration in jenkins server
        github.githubConfigure()
        stages.append(github.__dict__['stage'])
        print("Complete Github Configuration")
    else:
        print("not exist github tool in yaml!")
        
    # 2. Slack
    def request_test(url, username, password):
        # Build the Jenkins crumb issuer URL
        parsed_url = urllib.parse.urlparse(url)
        crumb_issuer_url = urllib.parse.urlunparse((parsed_url.scheme,
                                                parsed_url.netloc,
                                                'crumbIssuer/api/json',
                                                '', '', ''))
        # Use the same session for all requests
        session = requests.session()

        # GET the Jenkins crumb
        auth = requests.auth.HTTPBasicAuth(username, password)
        r = session.get(crumb_issuer_url, auth=auth)
        json = r.json()
        crumb = {json['crumbRequestField']: json['crumb']}

        # POST to the specified URL
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        headers.update(crumb)
        r = session.post(url, headers=headers, data=payload, auth=auth)

    if "slack" in toolList:
        slack = Slack(jenkins, token=var.getSlackData()['token'], subdomain=var.getSlackData()['subdomain'], channel=var.getSlackData()['channel'], cred_id=var.getSlackCred()['id'], cred_description=var.getSlackCred()['description'])

        # 2-1. Create slack credential in jenkins server
        slack.createCredential()
        stages.append(slack.__dict__['stage'])

        # 2-2. Slack configuration in jenkins server
        slack.slackConfigure()

        # 2-3. Slack Notification Test
        payload = {"room": var.getSlackData()['channel'], 
                    # "sendAsText": "true", 
                    "teamDomain": var.getSlackData()['subdomain'], 
                    "tokenCredentialId": var.getSlackCred()['id']}
        slacktest_url = jenkins_url + '/descriptorByName/jenkins.plugins.slack.SlackNotifier/testConnectionGlobal'
        request_test(slacktest_url, var.getJenkinsData()['username'], var.getJenkinsData()['password'])
        print("Complete Slack Configuration")
    else:
        print("not exist slack tool in yaml!")



    # 3. Gradle
    if "gradle" in toolList:
        gradle_jenkins_configname = "gradle"
        gradle_version = "6.9.1"
        # 3-1. Gradle configuration in jenkins server
        gradle = Gradle()
        gradle.gradleConfigure(gradle_jenkins_configname, gradle_version)
        stages.append(gradle.__dict__['stage'])
        print("Complete Gradle Configuration")
    else:
        print("not exist gradle in yaml!")    




    # 4. Sonarqube (with Gradle build)
    if "sonarqube" in toolList and "gradle" in toolList:
        # Add the following to your build.gradle file
        """
        plugins {
            id "org.sonarqube" version "3.3"
        }
        sonarqube {
            properties {
                property "sonar.projectKey", "sonar_projectname"
            }
        }
        """

        sonar_serverurl = "http://{}".format(var.getSonarqubeData()['url'])
        sonar_servername = "SonarServer"
        sonar_scanner_name = "SonarScanner"
        sonar_scanner_version = "4.6.2.2472"

        # 4-1. Create sonarqube credential in jenkins server
        sonarqube = Sonarqube(jenkins, token=var.getSonarqubeData()['token'], cred_id=var.getSonarqubeCred()['id'], cred_description=var.getSonarqubeCred()['description'], url=sonar_serverurl)
        sonarqube.createCredential()

        # 4-2. Sonarserver and Sonarscanner configuration in jenkins server
        sonarqube.sonarqubeConfigure(sonar_servername, sonar_scanner_name, sonar_scanner_version)
        
        stages.append(sonarqube.__dict__['stage'])
        print("Complete Sonarqube Configuration")

    elif "sonarqube" in tooList:
        print("나중에 구현")
    else:
        print("not exist sonarqube in yaml!")


    # Dependency
    if "dependency" in toolList:
        dependency_jenkins_configname = "dependency"
        dependency_version = "6.3.1"
        dependency = Dependency()
        dependency.dependencyConfigure(dependency_jenkins_configname, dependency_version)
        stages.append(dependency.__dict__['stage'])
        print("Complete Dependency Configuration")
    else:
        print("not exists dependency in yaml!")

        
    # 5 Dockerhub

    # 5-1. Create dockerhub credential with username, password
    if "dockerhub" in toolList:
        dockerhub = Dockerhub(jenkins, cred_id=var.getDockerhubCred()['id'], cred_description=var.getDockerhubCred()['description'], username=var.getDockerhubData()['username'], password=var.getDockerhubData()['password'], image=var.getDockerhubData()['image'])
        dockerhub.createCredential()

        # 5-2. Create Dockerfile in git repository for docker image build. (You can fix it as you want.)
        # It's based on jdk version 11.
        # If spring boot version 2.5 or higher, add the following content to the build.gradle file.
        # This prevents creating a plane.jar file.
        """
        jar {
            enabled = false
        } 
        """

        dockerfile = """FROM openjdk:11-jdk-slim
        ARG JAR_FILE=build/libs/*.jar
        COPY ${JAR_FILE} myspring.jar
        ENTRYPOINT ["java", "-jar", "/myspring.jar"]"""

        content = stringToBase64(dockerfile)

        github_requesturl = "https://api.github.com/repos/{}/{}/contents/Dockerfile".format(var.getGithubData()['username'], var.getGithubData()['reponame'])
        body = {
            "message": "create a default dockerfile",
            "content": content
        }
        github = Github(jenkins, token=var.getGithubData()['token'], cred_id=var.getGithubCred()['id'], cred_description=var.getGithubCred()['description'], url=var.getGithubData()['url'])
        response = github.call_api("PUT", github_requesturl, body)
        if response.status_code == 201:
            print("Created dockerfile in Github repository")
        else:
            print("Already exists dockerfile in github repository")
        stages.append(dockerhub.__dict__['stage'])
        print("Complete Dockerhub Configuration")

    else:
        print("not exist dockerhub in yaml!!")



    # Anchore
    if "anchore" in toolList:
        anchore_url = "http://{}".format(var.getAnchoreData()['url'])
        anchore = Anchore(jenkins, cred_id=var.getAnchoreCred()['id'], cred_description=var.getAnchoreCred()['description'], url=anchore_url, username=var.getAnchoreData()['username'], password=var.getAnchoreData()['password'], image=var.getAnchoreData()['image'])
        anchore.anchoreConfigure()
        anchore.createCredential()
        stages.append(anchore.__dict__['stage'])
        print("Complete Anchore Configuration")
    else:
        print("not exits anchore in yaml!")



    # 6. ArgoCD
    if "argocd" in toolList:

        # 6-1. Create ArgoCD credential with SSH key
        argocd = Argocd(jenkins, cred_id=var.getArgocdCred()['id'], cred_description=var.getArgocdCred()['description'], cred_sshkey=var.getArgocdData()['ssh_key'], cred_username=var.getArgocdData()['username'], masternode_url=var.getArgocdData()['url'], github_url=var.getGithubData()['url'])
        argocd.createCredential()

        # 6-2. Create ArgoCD config yaml in git repository
        argocd_yamldir = "templates"
        argocd_deployments_yaml = """apiVersion: apps/v1
    kind: Deployment
    metadata:
    name: test
    labels:
        app: test
    spec:
    replicas: 1
    selector:
        matchLabels:
        app: test
    template:
        metadata:
        labels:
            app: test
        spec:
        containers:
            - name: test
            image: {}:latest
            ports:
                - containerPort: 80""".format(var.getDockerhubData()['image'])

        argocd_svc_yaml = """apiVersion: v1
    kind: Service
    metadata:
    name: test
    spec:
    type: LoadBalancer
    selector:
        app: test
    ports:
        - port: 80
        targetPort: 8080"""

        deployments = stringToBase64(argocd_deployments_yaml)
        svc = stringToBase64(argocd_svc_yaml)

        github_requesturl_argocd_deployments = "https://api.github.com/repos/{}/{}/contents/{}/deployments.yaml".format(var.getGithubData()['username'], var.getGithubData()['reponame'], argocd_yamldir)
        body1 = {
            "message": "create a default deployments yaml",
            "content": deployments
        }
        github_requesturl_argocd_svc = "https://api.github.com/repos/{}/{}/contents/{}/svc.yaml".format(var.getGithubData()['username'], var.getGithubData()['reponame'], argocd_yamldir)
        body2 = {
            "message": "create a default svc yaml",
            "content": svc
        }
        github = Github(jenkins, token=var.getGithubData()['token'], cred_id=var.getGithubCred()['id'], cred_description=var.getGithubCred()['description'], url=var.getGithubData()['url'])
        response1 = github.call_api("PUT", github_requesturl_argocd_deployments, body1)
        if response1.status_code == 201:
            print("Created argocd deployment.yaml in Github repository")
        else:
            print("Already exists argocd deployment.yaml in github repository")
        response2 = github.call_api("PUT", github_requesturl_argocd_svc, body2)
        if response2.status_code == 201:
            print("Created argocd svc.yaml in Github repository")
        else:
            print("Already exists argocd svc.yaml in github repository")

        stages.append(argocd.__dict__['stage'])
        print("Complete Argocd Configuration")
    else:
        print("not exist argocd in yaml!")

    # 7. Pipeline
    # 7-1. Create pipeline script in github repository.
    if len(toolList) > 0:
        print("jenkins server restarting.......")
        try:
            jenkins.safe_restart()
        except Exception as e:
            pass
        print("Completed jenkins server restarting!")

        pipelineScript = "jenkinsfile"
        pipelineName = "ANBD"
        stages = '\n\t'.join(stages)
        jenkinsfile = """pipeline {
            agent any
            stages {
                %s
            }
        }"""%(stages)

        jenkinsfile = stringToBase64(jenkinsfile)
        github_requesturl_pipeline_script = "https://api.github.com/repos/{}/{}/contents/{}".format(var.getGithubData()['username'], var.getGithubData()['reponame'], pipelineScript)
        body = {
            "message": "create a pipeline script",
            "content": jenkinsfile
        }
        github = Github(jenkins, token=var.getGithubData()['token'], cred_id=var.getGithubCred()['id'], cred_description=var.getGithubCred()['description'], url=var.getGithubData()['url'])
        response = github.call_api("PUT", github_requesturl_pipeline_script, body)
        if response.status_code == 201:
            print("Created jenkinsfile in Github repository")
        else:
            print("Already exists jenkinsfile in github repository")

        # 7-2. Create jenkins pipeline
        xml_modify("pipelineConfig.xml", url=var.getGithubData()['url'], scriptPath=pipelineScript)
        with open("pipelineConfig.xml", 'r') as xml:
            pipeline_configXml = xml.read()
        
        try:
            jenkins.create_multibranch_pipeline_job(jobname=pipelineName, xml=pipeline_configXml)
        except Exception as e:
            pass
        print("--------------The End--------------")

elif sys.argv[1] == "reset":
    print("reset")
else:
    print("Invalid format, \"start\" or \"reset\" needed")
