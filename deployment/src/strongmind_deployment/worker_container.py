import os

from strongmind_deployment.autoscale import WorkerInstJobsAutoscaleComponent
from strongmind_deployment.container import ContainerComponent


def inst_jobs_present():  # pragma: no cover
    return os.path.exists('../Gemfile') and 'inst-jobs' in open('../Gemfile').read()


class WorkerContainerComponent(ContainerComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.setup_worker()

    def setup_worker(self):
        if inst_jobs_present():
            self.command = ["sh", "-c", "/usr/src/worker.sh"]
            self.worker_autoscaling = WorkerInstJobsAutoscaleComponent("worker",
                                                                       worker_autoscale_threshold=30)


