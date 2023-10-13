# Deploying a Rails App


## Setup Pulumi

Update the `infrastructure/Pulumi.yaml` file:
Replace `YOUR-APP-NAME-HERE` with the name of your app.

## Setup GitHub Secrets
### Rails Master Key
1. Generate your master key.
[![asciicast](https://asciinema.org/a/oo8D2bVtX1UicMS94Qh2hrYei.svg)](https://asciinema.org/a/oo8D2bVtX1UicMS94Qh2hrYei)
1. Copy the contents of the `config/master.key` file.
1. Go to the GitHub repo.
1. Click on `Settings`.
1. Click on `Secrets and variables`.
1. Click on `Actions`.
1. Click on `New repository secret`.
1. For the name enter `RAILS_MASTER_KEY`.
1. Paste the contents of the `config/master.key` file into the value field.
1. Click on `Add secret`.


## Setup AWS Secrets
* Sentry

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
