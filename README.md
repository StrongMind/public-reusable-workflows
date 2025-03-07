# StrongMind Public Reusable CI/CD Workflows

## What?

Public github actions workflows that are reusable within StrongMind.

## How to deploy a rails app
See [Rails App Deployment](./docs/rails-app-deployment.md)

### Diagram

```mermaid
graph LR

```

## Where?

Code owners can be found in [CODEOWNERS file](./CODEOWNERS)

### How to Bring Down Infrastructure Using Pulumi (Method: GitHub Actions)

1. **Check for Protected Resources**
   - **If There Are Protected Resources:**
     - Either manually delete the protected resources via the AWS Management Console or follow the manual steps from the other method, skipping this method.
     - You need to manually delete a resource in AWS if pulumi asks you to unprotect a resource.

2. **Clone the Repository**
   - Clone the repository for the infrastructure you want to delete.

3. **Locate the Deployment Workflow**
   - Go to the `.github/workflows` folder and find the deployment file for the environment you want to delete.
   - For example, if you are deleting production infrastructure, look for `deploy-prod.yml`.

4. **Modify the GitHub Action Workflow**
   - Open the deployment file (`deploy-prod.yml` or similar).
   - Locate the job that references:
     ```yaml
     uses: strongmind/public-reusable-workflows/.github/workflows/aws-deploy.yml@main
     ```
   - Find or create the `with` section in that job.
   - Add 'pulumi-command: down' environment variable to the `with` section:
     ```yaml
     with:
      pulumi-command: down
     ```

5. **Push Changes and Merge**
   - Push the changes to a new branch.
   - Create a pull request (PR) and merge it into the main branch.

6. **Trigger the GitHub Action**
   - If the GitHub Action doesn't automatically start after merging the PR, manually trigger it:
     - Go to the GitHub Actions tab in the repository.
     - Find and run the `build.yml` workflow from the GitHub Actions web UI.
   - This should bring down the infrastructure as intended.
   - NOTE: You will need to run the `build.yml` workflow everytime pulumi asks you to unprotect/delete something.
     - This needs to happen so that the pulumi state file is refreshed.

### How to Bring Down Infrastructure Using Pulumi (Alternative Method: Manual Process)

1. **Clone the Repository**
   - Clone the repository for the infrastructure you want to delete.

2. **Set Up Your AWS Credentials**
   - Ensure your `~/.aws/credentials` file has a `[default]` profile linked to the AWS account where the infrastructure resides.
   - For example, if the infrastructure is in the StrongMind AWS account, the `[default]` profile should have access to that account.

3. **Set Cloudflare API Token (If Needed)**
   - If a Cloudflare API token is required for the infrastructure, export it as an environment variable:
     ```bash
     export CLOUDFLARE_API_TOKEN="<cloudflare_api_token_from_bitwarden>"
     ```

4. **Set Up Pulumi**
   - Retrieve the Pulumi config passphrase from Bitwarden:
     - Secret Name: "pulumi state pass Devops (and tesla)"
   - Export the Pulumi passphrase:
     ```bash
     export PULUMI_CONFIG_PASSPHRASE="<pulumi_config_passphrase_from_bitwarden>"
     ```

5. **Login to Pulumi**
   - Log in to the Pulumi state file:
     ```bash
     pulumi login s3://pulumi-state-sm/{Repository_name}
     ```
   - Example:
     ```bash
     pulumi login s3://pulumi-state-sm/Helpers
     ```

6. **Navigate to the Infrastructure Directory**
   - Change to the infrastructure directory:
     ```bash
     cd infrastructure
     ```

7. **Create and Activate a Virtual Environment**
   - Create a virtual environment:
     ```bash
     python3 -m venv venv
     ```
   - Activate the virtual environment:
     ```bash
     source venv/bin/activate
     ```
   - Install the required dependencies:
     ```bash
     python3 -m pip install -r requirements.txt
     ```

8. **Select the Stack**
   - Choose the stack you want to bring down:
     ```bash
     pulumi stack select prod
     ```
   - Replace `prod` with the name of the stack you wish to delete.

9. **Bring Down the Infrastructure**
   - Run the following command to destroy the infrastructure:
     ```bash
     pulumi down
     ```
   - **Dealing with Protected Resources:**
     - **If Protected by Pulumi:**
       - Pulumi will provide instructions to unprotect the resource.
       - Run `pulumi down` again after unprotecting the resource.
       - If the issue persists, follow the steps in the "If Protected by AWS" section.
       - **Note:** If there are multiple protected resources, you will need to unprotect them individually.
     - **If Protected by AWS:**
       - Disable protection directly in the AWS Management Console.
       - After doing so, run:
         ```bash
         pulumi refresh
         ```
       - Then, run `pulumi down` again to complete the teardown.


## Chat with AI Assistant (Pulumi King)

You can [chat with Pulumi King](https://chatgpt.com/g/g-67bcb0b91c388191a2812a788901a882-pulumi-king), an AI assistant designed to help with StrongMind infrastructure. Palumi King provides guidance on:

- AWS services and best practices
- Infrastructure as Code using Pulumi
- CI/CD workflows and automation
- Troubleshooting deployment issues
- Security and scaling strategies

### How to Regenerate AI Assistant Documents
To regenerate the AI-generated documentation, follow these steps:

1. **Use Cursor to Run the Following Prompt:**
```
- create a file called notes.md
- go through the files in the and folders and update the notes.md with:
<node_md_content>
* mermaid diagram of the infrastructure
* list of services used
* Description of the services used and interactions with one another
</note_md_content>
- update the notes.md after each file
- go back to previous files if necessary to get a better understanding of the infrastructure
```
2. **Run This Prompt Three Times Using the Following Contexts:**

  * **Deployment** Folder
  * **Docs** Folder
  * **Docs** and **Deployment** folder
3. **Generated Files:**

  * The three generated files will serve as references for the AI assistant to understand and provide insights into the infrastructure.

By following this process, you ensure that the AI assistant stays updated with the latest infrastructure documentation.