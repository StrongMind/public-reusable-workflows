import pulumi


def get_pulumi_mocks(faker):
    class PulumiMocks(pulumi.runtime.Mocks):
        def new_resource(self, args: pulumi.runtime.MockResourceArgs):
            outputs = args.inputs
            if args.typ == "awsx:ecr:Repository":
                outputs = {
                    **args.inputs,
                    "url": f"{faker.word()}.dkr.ecr.us-west-2.amazonaws.com",
                    "force_delete": args.inputs["forceDelete"],
                }
            if args.typ == "awsx:ecs:FargateService":
                outputs = {
                    **args.inputs,
                    "task_definition_args": args.inputs["taskDefinitionArgs"],
                }
            if args.typ == "aws:rds/cluster:Cluster":
                outputs = {
                    **args.inputs,
                    "endpoint": f"{faker.domain_name()}.cluster-{faker.word()}.us-west-2.rds.amazonaws.com"
                }
            if args.typ == "random:index/randomPassword:RandomPassword":
                length = args.inputs["length"]
                outputs = {
                    **args.inputs,
                    "result": faker.password(length=int(length)),
                    "special": args.inputs["special"],
                }
            return [args.name + '_id', outputs]

        def call(self, args: pulumi.runtime.MockCallArgs):
            return {}

    return PulumiMocks()