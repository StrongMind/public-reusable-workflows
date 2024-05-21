# StrongMind Deployment

## What?
Deployment scripts for StrongMind, using Pulumi.

## Development
Write pytest tests for functionality you need. When you need to use this with real AWS resources in a development environment, you'll need to follow these steps.

* Log your shell into the AWS account you're test deploying to (If you don't already have access keys set up, you can find how to do this in the [Amazon SSO portal](https://strongmind.awsapps.com/start#/), under "Programmatic Access")
* Find the relevant container image you're deploying [from ECR](https://us-west-2.console.aws.amazon.com/ecr/repositories?region=us-west-2). (Choose the relevant project container, then the image tag, and then copy the URI field).
* Find the Rails Master Key for that project. Usually this is kept in the [github actions secrets](https://github.com/StrongMind/frozen-desserts/settings/secrets/actions) for that project.
* Get the cloudflare API token and pulumi state passwords from bitwarden if you have access, or get this from devops otherwise.
* Use these to construct an environment in your preferred fashion with the following keys
  * CONTAINER_IMAGE
  * RAILS_MASTER_KEY
  * CLOUDFLARE_API_TOKEN
  * PULUMI_CONFIG_PASSPHRASE
* In the project that you are testing with, in the infrastructure directory, there will be a requirements.txt file. In order to use your development code, rather than the published version of this library, you will need to change the line that says "strongmind_deployment" to `-e /path/to/this/directory`, using the directory that this README is located in.
* Reinstall the requirements in your pulumi infrastructure directory. Usually this looks like
```shell
source venv/bin/activate
pip install -r requirements.txt
```

You can now use pulumi commands like `pulumi preview` and `pulumi up` to make changes.

We usually use the [frozen-desserts](https://github.com/StrongMind/frozen-desserts) application to do simple tests of a non-production application.

## Naming Conventions

Naming conventions are important in pulumi.  Logical names of resources are used to generate physical resource names, where we don't supply an explicit name.
This helps in consistency when looking for resources in the AWS Console as well as in Pulumi.
Exports are also important as they are hard to change. Following a convention helps you think about the usefulness and intuitiveness of the name.

### Stack Export Naming


Convention: `<resource_type>_<param_type>_<parameter_name>`

* resource types: queue, lambda, log_group, bucket
* param types: name, arn, url, id
* parameter names: business function of the resource

In the case of a URL that isn't directly referencing Route53, but is concatenating a custom output, more flexibility is granted.

Examples:
```
pulumi.export("url", pulumi.Output.concat("https://", queue_api.url))
pulumi.export("queue_url_export_jobs", queue_api.ingress_queue.url)
pulumi.export("log_group_name_access_logs", access_log_group.name)
pulumi.export("log_group_name_uthorizer_function", "/aws/lambda/" + authorizer_function.name)

```
