# Deploying a Rails App


## Setup Pulumi

1. Open the `infrastructure/Pulumi.yaml` file.
1. Replace `YOUR-APP-NAME-HERE` with the name of your app.

## Rename your database

1. Open the `config/database.yml` file.
1. Replace `Database: app_development` with `Database: your_app_name_development`.
1. Replace `Database: app_test` with `Database: your_app_name_test`.
1. Replace `Database: app_production` with `Database: your_app_name_production`.

This ensures that your local postgres server will have the correct database names.

## Setup GitHub Secrets
### Rails Master Key
1. Generate your master key.
[![asciicast](https://asciinema.org/a/oo8D2bVtX1UicMS94Qh2hrYei.svg)](https://asciinema.org/a/oo8D2bVtX1UicMS94Qh2hrYei?speed=3)
1. Copy the contents of the `config/master.key` file.
1. Go to the GitHub repo.
1. Click on `Settings`.
1. Click on `Secrets and variables`.
1. Click on `Actions`.
1. Click on `New repository secret`.
1. For the name enter `RAILS_MASTER_KEY`.
1. Paste the contents of the `config/master.key` file into the value field.
1. Click on `Add secret`.

## Turn off autoscaling for first deploy
(Belding plans to fix this soon)
1. Open the `infrastructure/__main__.py` file.
1. Edit the second line to be the following:
```python
component = RailsComponent("rails", autoscale=False)
```
3. Save the file, commit and push.

## Check Deployment
1. Push or merge your changes to the main branch.
1. Go to the `Actions` tab in the GitHub repo.
1. Look for the `Deploy to stage` or `Deploy to production` workflow and click on it.
1. Click on the workflow run.
1. Click on the `Deploy Rails to ECS` job.
1. Click on the `Deploy with Pulumi` step.
1. Scroll to the bottom.
1. Under `Outputs` locate the `url` output.
1. Click on the link to see your deployed app which will be located at the following URLs:
- `https://stage-[repo-name-here].strongmind.com`
- `https://[repo-name-here].strongmind.com`



## Setup AWS Secrets
### Sentry
1. Navigate to https://strongmind-4j.sentry.io/projects
1. Login with your StrongMind AAD account.
1. Search for the project by name.
1. Click on the project.
1. Click on the gear icon at the top right.
1. Click on `Client Keys (DSN)`.
1. Copy the DSN.
1. Navigate to https://strongmind.awsapps.com/start#/
1. Login with your StrongMind AAD account.
1. Click on the Strong Mind account.
1. Navigate to https://us-west-2.console.aws.amazon.com/secretsmanager/listsecrets?region=us-west-2 
1. Search for your app name.
1. Choose the production secret.
1. Click on `Retrieve secret value`.
1. Click on `Edit`.
1. Click on `Add Row`.
1. For the key enter `SENTRY_DSN`.
1. Paste the DSN into the value field.
1. Click `Save`.
1. Redeploy the app to production by performing the following steps.
1. Open the GitHub repo.
1. Click on `Actions`
1. Click on the `Deploy to production` workflow.
1. Click on `Run workflow` on the right.
1. Click on the green `Run workflow` button.

## Autoscaling

Remove `autoscale=false` from the `infrastructure/__main__.py` file and redeploy.