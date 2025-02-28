from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from ..models import Project
from django.utils import timezone
from django.http import HttpResponseNotAllowed
from ..forms import ProjectForm
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
import pymysql
from time import sleep
import jenkins
import requests
import json

token = "eyJhbGciOiJSUzI1NiIsImtpZCI6Ii1TYnB6THpzRnJMWTZGN3NZOHRsVjBMY1l4aFE0WWZOV3BLTnFMcDcxcTgifQ.eyJpc3MiOiJrdWJlcm5ldGVzL3NlcnZpY2VhY2NvdW50Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9uYW1lc3BhY2UiOiJkZWZhdWx0Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9zZWNyZXQubmFtZSI6ImRlZmF1bHQtdG9rZW4tNXA1Z3EiLCJrdWJlcm5ldGVzLmlvL3NlcnZpY2VhY2NvdW50L3NlcnZpY2UtYWNjb3VudC5uYW1lIjoiZGVmYXVsdCIsImt1YmVybmV0ZXMuaW8vc2VydmljZWFjY291bnQvc2VydmljZS1hY2NvdW50LnVpZCI6ImYwZDgxN2MzLWZhNDUtNGVlNy1iMmU3LTg1YTM2NTliNWE5OCIsInN1YiI6InN5c3RlbTpzZXJ2aWNlYWNjb3VudDpkZWZhdWx0OmRlZmF1bHQifQ.J8cDAoqSEO1hlLtf58AC-aV-w0CMQA9oxNFm1KZp5B-p6fGJqCluv6EiOVcZaGklzr4nbrvgzWJVItUv3MrougFnTIX_JT82LKHD2BHY9tyWKLgUrjot69QM07jEnBykmzAi87WoUqzYcA14xFFHI48HJDaanFTzgt-1d_kwT2Em74DYWQXNU-Pz-zuOW-Vct9zv8squOiyTeTpiN3q2-Np7TVnarJXaBxqVWV79y5Ou6RA_ku83P6bMWeUK1lSj2hkL-mdhD4uj9RA70LAt21Y8KMVL8KNgfNeZKLhNE4q3bTnm0-H549wXImnY6fFfWm4L-JlJABimty-hh6SVGQ"
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

host = "http://192.168.160.244:8080"
username = "admin" #jenkins username here
password = "admin" # Jenkins user password / api token here
server = jenkins.Jenkins(host, username=username, password=password)

argo_host = "http://argocd.xyz/"
admin = "admin"
request_url1 = """{}api/v1/session""".format(argo_host)
data1 = {'username':'admin','password':'python3.10'}
api_response = requests.post(request_url1, data=json.dumps(data1))
argocd_accesstoken = api_response.json()['token']

def project(request):
    project = Project.objects.all()
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            if request.POST['KIND'] == 'GitHub App' and request.POST['GITTOKEN'] == '':
                context = {'project': project, 'state' : 'Git Hub Token을 입력하지 않았습니다.'}
                return render(request, 'pybo/mainpage.html', context)
            if request.POST['KIND'] == 'Custom App' and request.POST['GIT'] == '':
                context = {'project': project, 'state' : 'Git 주소를 입력하지 않았습니다.'}
                return render(request, 'pybo/mainpage.html', context)
            Gitappurl = request.POST['GIT']
            if request.POST['KIND'] == 'GitHub App':
                # Git 레포 생성
                try:
                    data = {
                        "name": "{}".format(request.POST['NAME']),
                        "description": "This Is Your First Repo",
                        "auto_init": True,
                    }
                    request_url = "https://api.github.com/user/repos"
                    headers = {"Authorization": "Bearer {}".format(request.POST['GITTOKEN']), "Accept": "application/vnd.github+json"}
                    api_response = requests.post(request_url, data=json.dumps(data), headers=headers)
                    api_json = api_response.json()
                    try:
                        error = api_json['errors'][0]['message']
                        context = {'project': project, 'state' : error}
                        return render(request, 'pybo/mainpage.html', context)
                    except:
                        userid = api_json['owner']['login']
                except:
                    context = {'project': project, 'state' : '4 : Git Hub Token이 잘못 되었습니다.'}
                    return render(request, 'pybo/mainpage.html', context)

                Gitappurl = 'https://github.com/' + f'{userid}' + '/' f'{request.POST["NAME"]}' + '.git'

            # jenkins project 생성
            if request.POST['KIND'] != 'App' and request.POST['KIND'] != '0':
                init = open('./init_conf', 'r')
                f = init.read()
                if server.job_exists(request.POST["NAME"]) is not True:
                    server.create_job(request.POST["NAME"], f)
                    myConfig = server.get_job_config(request.POST["NAME"])
                    # github 주소가 등록되어 있지 않으면
                    if "<url>https://github.com/</url>" in myConfig:
                        new = myConfig.replace('<url>https://github.com/</url>', '<url>%s</url>' %(Gitappurl))
                        server.reconfig_job(request.POST["NAME"], new)
                init.close()

                if request.POST['KIND'] == 'GitHub App':
                    # sonarqube token 생성
                    request_url = "http://192.168.160.244:9000/api/user_tokens/generate"
                    user = ("admin", "admin123")
                    data = {"name": request.POST["NAME"]}
                    api_response = requests.post(request_url, data=data, auth=user)
                    api_json = api_response.json()
                    sonar_token = api_json['token']
                    print(sonar_token)

                    # sonarqube project 생성
                    request_url = "http://192.168.160.244:9000/api/projects/create"
                    user = ("admin", "admin123")
                    data = {
                        "name": request.POST["NAME"],
                        "project": request.POST["NAME"],
                    }
                    api_response = requests.post(request_url, data=data, auth=user)
            pj = form.save(commit=False)
            if request.POST['KIND'] == 'GitHub App':
                pj.GIT = Gitappurl
                pj.SONARTOKEN = sonar_token
            pj.save()
            
            # ArgoCD Project 생성

            try:              
                data = {
                    "project": {
                        "metadata": { 
                            "name": f"{request.POST['NAME']}" 
                        },
                        "spec": {
                            "destinations": [
                                {
                                "server": "https://kubernetes.default.svc",
                                "namespace": f"{request.POST['NAME']}"
                                }
                            ],
                            "clusterResourceWhitelist": [
                                {
                                    "group": "*",
                                    "kind": "*"
                                }
                            ],
                            "sourceRepos": ["*"]
                        }
                    }
                }
                request_url = """{}api/v1/projects""".format(argo_host)
                headers = {"Authorization": "Bearer {}".format(argocd_accesstoken)}
                api_response = requests.post(request_url, data=json.dumps(data), headers=headers)
            except:
                context = {'project': project, 'state' : 'Argo CD Project 생성 실패'}
                return render(request, 'pybo/mainpage.html', context)

            try:
                request_url = "https://10.0.0.79:6443/api/v1/namespaces/"
                headers = {"Authorization": "Bearer {}".format(token)}
                data = {
                    "apiVersion": "v1",
                    "kind": "Namespace",
                    "metadata": { 
                            "name": "{}".format(request.POST['NAME']) 
                    },
                }
                api_response = requests.post(request_url, headers=headers, data=json.dumps(data), verify=False)
                api_json = api_response.json()
            except:
                context = {'project': project, 'state' : 'Kubernetes Project 생성 실패'}
                return render(request, 'pybo/mainpage.html', context)

            context = {'project' : project}
            return redirect('pybo:detail', project_id=pj.id)
    else:
        form = ProjectForm()
    context = {'form' : form, 'state' : True}
    return render(request, 'pybo/project.html', context)


def project_delete(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    
    if project.KIND == 'GitHub App':

        # Git hub userid 가져오기
        request_url = "https://api.github.com/user"
        headers = {"Accept": "application/vnd.github+json", "Authorization": "Bearer {}".format(project.GITTOKEN)}
        api_response = requests.get(request_url, headers=headers)
        api_json = api_response.json()
        userid = api_json['login']

        # Git hub 삭제
        request_url = "https://api.github.com/repos/{}/{}".format(userid, project.NAME)
        headers = {"Authorization": "Bearer {}".format(project.GITTOKEN), "Accept": "application/vnd.github+json"}
        api_response = requests.delete(request_url, headers=headers)
        print(api_response)
        
    # Jenkins Pipeline 삭제
    if project.KIND != 'App':
        if server.job_exists(project.NAME):
            server.delete_job(project.NAME)

    #sonarqube 삭제
    if project.KIND == 'GitHub App':
        request_url = "http://192.168.160.244:9000/api/projects/delete"
        user = ("admin", "admin123")
        data = {"project": project.NAME}
        api_response = requests.post(request_url, data=data, auth=user)

        request_url = "http://192.168.160.244:9000/api/user_tokens/revoke"
        user = ("admin", "admin123")
        data = {"name": project.NAME}
        api_response = requests.post(request_url, data=data, auth=user)

    # ArgoCD Project 삭제
    argo_host = "http://argocd.xyz/"
    request_url = """{}api/v1/projects/{}""".format(argo_host, project.NAME)
    headers = {"Authorization": "Bearer {}".format(argocd_accesstoken)}
    api_response = requests.delete(request_url, headers=headers)
    print(api_response)

    # Namespace 삭제
    request_url = "https://10.0.0.79:6443/api/v1/namespaces/{}/".format(project.NAME)
    headers = {"Authorization": "Bearer {}".format(token)}
    api_response = requests.delete(request_url, headers=headers, verify=False)
    api_json = api_response.json()
    
    project.delete()
    return redirect('pybo:index')

