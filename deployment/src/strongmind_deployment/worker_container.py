import os

import pulumi

from strongmind_deployment.util import qualify_component_name
from strongmind_deployment.worker_autoscale import WorkerInstJobsAutoscaleComponent
from strongmind_deployment.container import ContainerComponent


def inst_jobs_present():  # pragma: no cover
    return os.path.exists('../canvas-lms/Gemfile.d')

class WorkerContainerComponent(ContainerComponent):
    def __init__(self, name, opts=None, **kwargs):
        super().__init__(name, opts, **kwargs)

    def setup_autoscale(self):
        if inst_jobs_present():
            self.command = ["sh", "-c", "/usr/src/worker.sh"]
            self.worker_autoscaling = WorkerInstJobsAutoscaleComponent(
                qualify_component_name("worker-autoscale", self.kwargs),
                fargate_service=self.fargate_service,
                opts=pulumi.ResourceOptions(
                    parent=self,
                    depends_on=[self.fargate_service]
                ),
                worker_autoscale_threshold=30)
