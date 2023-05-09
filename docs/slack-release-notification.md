# Slack Release Notification

## Overview
Use these instructions to add a step to your production release workflow that notifies #release-notifications of the release.

## Steps

1. Open the workflow file for your production deployment.
2. Add the following input to the workflow-dispatch:
```yaml
  on: 
    workflow_dispatch:
      inputs:
        jira-ticket:
          type: string
```
3. Add the following job after the job that deploys to production:

> **_NOTE:_** `deploy-prod` in the sample below needs to match the name of the job that deploys to production.

```yaml
  notify:
    name: Notify Slack
    needs: deploy-prod
    uses: strongmind/public-reusable-workflows/.github/workflows/notify-slack.yml@main
    secrets: inherit
    with:
      jira-ticket: ${{ github.event.inputs.jira-ticket }}
```

4. Commit and push your changes to the workflow file.

## Verify
1. Open the Actions tab in your repository.
2. Click the workflow that deploys to production.
3. Click Run workflow.
4. Enter the Jira ticket number for the release.
5. Click Run workflow.
6. Check #release-notifications for the notification.
