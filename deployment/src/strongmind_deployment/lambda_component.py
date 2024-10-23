import pulumi
import pulumi_aws as aws
import os
import json
from typing import Optional, List, Dict

from strongmind_deployment.operations import get_code_owner_team_name


# lambda_component.py

class LambdaArgs:
    """
    Encapsulates configuration parameters for the Lambda function.
    """

    def __init__(
            self,
            handler: str,
            runtime: str = "python3.11",
            timeout: int = 60,
            memory_size: int = 1024,
            layers: Optional[List[str]] = None
    ):
        self.handler = handler
        self.runtime = runtime
        self.timeout = timeout
        self.memory_size = memory_size
        self.layers = layers or []

        self.validate()

    def validate(self):
        # Validate runtime
        valid_runtimes = [
            "python3.9",
            "python3.10",
            "python3.11",
        ]
        if self.runtime not in valid_runtimes:
            raise ValueError(f"Unsupported runtime: {self.runtime}")

        if not isinstance(self.timeout, int) or self.timeout <= 0:
            raise ValueError("Timeout must be a positive integer")

        if not isinstance(self.memory_size, int) or self.memory_size <= 0:
            raise ValueError("Memory size must be a positive integer")

        if self.layers:
            if not isinstance(self.layers, list):
                raise ValueError("Layers must be a list of ARN strings")
            for layer in self.layers:
                if not isinstance(layer, str):
                    raise ValueError("Each layer ARN must be a string")


class LambdaEnvVariables:
    """
    Manages environment variables for the Lambda function.
    """

    def __init__(self, variables: Optional[Dict[str, str]] = None):
        self.variables = variables or {}
        self.validate()

    def validate(self):
        if not isinstance(self.variables, dict):
            raise ValueError("Environment variables must be provided as a dictionary")
        for key, value in self.variables.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("Environment variable keys and values must be strings")


class LambdaComponent(pulumi.ComponentResource):
    """
    A Pulumi component resource that encapsulates the creation and management of an AWS Lambda function,
    its IAM role, and associated resources.
    """

    def __init__(self,
                 name,
                 lambda_args: Optional[LambdaArgs] = None,
                 lambda_env_variables: Optional[LambdaEnvVariables] = None,
                 opts: Optional[pulumi.ResourceOptions] = None,
                 **kwargs
                 ):
        super().__init__('strongmind:global_build:commons:lambda', name, None, opts)
        stack = pulumi.get_stack()
        project = pulumi.get_project()
        self.name = name
        self.namespace = kwargs.get('namespace', f"{project}-{stack}")
        self.env_name = os.environ.get('ENVIRONMENT_NAME', 'stage')
        self.lambda_args = lambda_args or LambdaArgs()
        self.owning_team = get_code_owner_team_name()
        self.tags = {
            "product": project,
            "repository": project,
            "service": project,
            "environment": self.env_name,
            "owner": self.owning_team,
        }

        self.lambda_args = lambda_args
        self.lambda_env_variables = lambda_env_variables or LambdaEnvVariables()
        self.timeout = self.lambda_args.timeout
        self.runtime = self.lambda_args.runtime
        self.memory_size = self.lambda_args.memory_size

        self.lambda_role = aws.iam.Role(
            f"{self.name}-lambda-role",
            name=f"{self.name}-lambda-role",
            assume_role_policy=json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": "sts:AssumeRole",
                        "Principal": {
                            "Service": "lambda.amazonaws.com"
                        },
                        "Effect": "Allow",
                        "Sid": ""
                    }
                ]
            }),
            tags=self.tags
        )

        self.execution_policy_attachment = aws.iam.RolePolicyAttachment(
            f"{self.name}-lambda-policy-attachment",
            policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            role=self.lambda_role.name
        )

        self.lambda_layer = aws.lambda_.LayerVersion(
            f"{self.name}-layer",
            layer_name=f"{self.name}-layer",
            code=pulumi.FileArchive("../lambda_layer.zip"),
            compatible_runtimes=[self.lambda_args.runtime],
        )

        self.lambda_function = aws.lambda_.Function(
            f"{self.name}",
            name=f"{self.name}",
            code=pulumi.FileArchive("../lambda.zip"),
            role=self.lambda_role.arn,
            handler=self.lambda_args.handler,
            runtime=self.runtime,
            layers=[self.lambda_layer.arn],
            memory_size=self.memory_size,
            timeout=self.timeout,
            environment={
                "variables": self.lambda_env_variables.variables
            },
            tags=self.tags
        )

