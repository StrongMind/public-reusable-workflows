# Deploying a Rails App

## Enable Docker

Create a Dockerfile in your root folder that includes an entrypoint.

Example --
```
# syntax=docker/dockerfile:1
FROM ruby:3.2.1
WORKDIR /myapp
ADD . /myapp

RUN bundle install

EXPOSE 3000

ENTRYPOINT ["sh", "-c", "rails db:prepare db:migrate db:seed && rails assets:precompile && rails server -b 0.0.0.0"]
```


## Setup GitHub Actions
1. Open your rails app.
1. Create the following file as `.github/workflows/build.yml`:
```yaml
name: Build

on:
  workflow_dispatch:

  push:
    branches: main
  
  pull_request:
    branches: main

jobs:
  build:
    name: Build Docker image
    uses: strongmind/public-reusable-workflows/.github/workflows/docker-build.yml@main
    secrets: inherit
```

3. Create the following file as `.github/workflows/deploy-stage.yml`:
```yaml
name: Deploy to stage

on:
  workflow_run:
    workflows: [Build]
    branches: [main]
    types: [completed]

jobs:
  deploy:
    name: Deploy Rails to ECS
    if: ${{ github.event.workflow_run.conclusion == 'success' || github.event_name == 'workflow_dispatch' }}
    uses: strongmind/public-reusable-workflows/.github/workflows/rails-deploy.yml@main
    with:
      environment-name: stage
    secrets: inherit
```

4. Create the following file as `.github/workflows/deploy-prod.yml`:
```yaml
name: Deploy to production

on: 
  workflow_dispatch:
    inputs:
      jira-ticket:
        type: string

jobs:
  deploy:
    name: Deploy Rails to ECS
    uses: strongmind/public-reusable-workflows/.github/workflows/rails-deploy.yml@main
    with:
      environment-name: prod
    secrets: inherit

  notify:
    name: Notify Slack
    needs: deploy
    uses: strongmind/public-reusable-workflows/.github/workflows/notify-slack.yml@main
    secrets: inherit
    with:
      jira-ticket: ${{ github.event.inputs.jira-ticket }}
```

## Setup Pulumi
Note: Belding plans to automate these steps soon.
1. Create the following file as `infrastructure/requirements.txt`:
```txt
pulumi>=3.0.0,<4.0.0
pulumi-aws>=5.10.0,<6.0.0
pulumi-awsx>=1.0.0,<2.0.0
pulumi-cloudflare
strongmind-deployment
```
2. Create the following file as `infrastructure/Pulumi.yaml`:
```yaml
name: YOUR-APP-NAME-HERE
runtime:
  name: python
  options:
    virtualenv: venv
description: A Python program to deploy a containerized service on AWS
```
3. Create the following file as `infrastructure/__main__.py`:
```python
from strongmind_deployment.rails import RailsComponent
component = RailsComponent("rails")
```

## Check Deployment
1. Push or merge your changes to the main branch.
2. Go to the `Actions` tab in the GitHub repo.
3. Look for the `Deploy to stage` or `Deploy to production` workflow and click on it.
4. Click on the workflow run.
5. Click on the `Deploy Rails to ECS` job.
6. Click on the `Deploy with Pulumi` step.
7. Scroll to the bottom.
8. Under `Outputs` locate the `url` output.
9. Click on the link to see your deployed app which will be located at the following URLs:
- `https://stage-[repo-name-here].strongmind.com`
- `https://[repo-name-here].strongmind.com`
