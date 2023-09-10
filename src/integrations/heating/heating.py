from apscheduler.schedulers.background import BackgroundScheduler
from omegaconf import DictConfig

from src.integrations.base.integration import Integration


class HeatingIntegration(Integration):
    def __init__(self, scheduler: BackgroundScheduler, config: DictConfig):
        super().__init__(config)
        self.scheduler = scheduler

        scheduler.add_job(self.refresh, "interval", seconds=1)
        # self.heating = Heating(config.heating)

    def refresh(self):
        pass
