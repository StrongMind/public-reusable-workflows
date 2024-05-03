import subprocess
import pulumi_aws as aws
import pulumi

def get_code_owner_team_name()-> str:
    """
    Gets the code owner from the repositories CODEOWNERS file
    """
    path = subprocess.check_output(['git', 'rev-parse', '--show-toplevel']).decode('utf-8').strip()
    file_path = f"{path}/CODEOWNERS"
    with open(file_path, 'r') as file:
        owning_team = [line.strip().split('@')[-1] for line in file if '@' in line][-1].split('/')[1]
    return owning_team

def get_opsgenie_sns_topic_arn()-> str:
    """
    The SNS topic name is coupled to the name in the CODEOWNERS file.
    The format is <arn_root>:<owning_team>-opsgenie.
    ex: arn:aws:sns:us-west-2:123456789012:thebestteam-opsgenie
    """
    owning_team = get_code_owner_team_name()

    region = aws.get_region().name
    account_id = aws.get_caller_identity().account_id
    return f"arn:aws:sns:{region}:{account_id}:{owning_team}-opsgenie"

def get_opsgenie_metric_alarm_config() -> dict:
    """
    Returns a dictionary of configuration valid for a pulumi_aws.cloudwatch.MetricAlarm constructor.
    Specifically:
        actions_enabled: boolean
        alarm_actions: [str] # SNS Topic ARN for the specific team
        ok_actions: [str] # SNS Topic ARN for the specific team
    
    Example:
        from strongmind_deployment import operations 
        opsgenie_configs = operations.get_opsgenie_metric_alarm_config()

        aws.cloudwatch.MetricAlarm(
            f"{self.name}-{metric_name}",
            ...
            metric_name=metric_name,
            namespace="AWS/ECS",
            **opsgenie_configs,
        )

    """
    enable_opsgenie = pulumi.Config().get_bool("enable_opsgenie", False)
    opsgenie_configs = {}
    if enable_opsgenie:
        opsgenie_topic = get_opsgenie_sns_topic_arn()
        opsgenie_configs = {
            "actions_enabled":True,
            "alarm_actions":[opsgenie_topic],
            "ok_actions":[opsgenie_topic],
        }
    return opsgenie_configs
