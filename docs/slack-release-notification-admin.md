# Release Notification Administration

## Modifying Slack Message
The Slack message is determined by a Slack Workflow called "Release Notifications."
Follow these steps to modify the message:
1. Open Slack.
2. Click on StrongMind.
3. Click Tools.
4. Click Workflow Builder.
5. Click Release Notifications.
6. There are two steps in the workflow.
    - Inputs
    - Message
7. The first step determines the variable inputs. Example:
```json
{
  "repository_url": "Example text",
  "repository_name": "Example text",
  "repository_owner": "Example text",
  "commit_sha": "Example text",
  "commit_url": "Example text",
  "commit_message": "Example text",
  "actor": "Example text",
  "actor_url": "Example text",
  "actor_avatar": "Example text",
  "workflow_url": "Example text",
  "workflow_name": "Example text",
  "jira_ticket": "Example text"
}
```
8. The second step determines the channel and message:

![slack_message_editor.png](slack_message_editor.png)

9. Make sure to publish the workflow after making changes.