# Deploying a Rails App

## Setup GitHub Actions
1. Open your rails app.
1. Create the following file as `.github/workflows/deploy-stage.yml`:
```yaml
name: Build and Deploy to Stage

on:
  workflow_dispatch:

jobs:
  build:
    name: Build Docker image
    uses: strongmind/public-reusable-workflows/.github/workflows/docker-build.yml@main
    secrets: inherit

  deploy:
    name: Deploy Rails to ECS
    needs: build
    uses: strongmind/public-reusable-workflows/.github/workflows/rails-deploy.yml@main
    with:
      environment-name: stage
      container-image: ${{ needs.build.outputs.container-image }}
    secrets: inherit
```
3. Create the following file as `.github/workflows/deploy-prod.yml`:
```yaml
name: Deploy to production

on: workflow_dispatch

jobs:
  build:
    name: Build Docker image
    uses: strongmind/public-reusable-workflows/.github/workflows/docker-build.yml@main
    secrets: inherit

  deploy:
    name: Deploy Rails to ECS
    needs: build
    uses: strongmind/public-reusable-workflows/.github/workflows/rails-deploy.yml@main
    with:
      environment-name: prod
      container-image: ${{ needs.build.outputs.container-image }}
    secrets: inherit
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
