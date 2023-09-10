from argparse import ArgumentParser

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from omegaconf import DictConfig, ListConfig, OmegaConf
from pytz import utc

jobstores = {
    "default": MemoryJobStore(),
}
executors = {
    "default": ThreadPoolExecutor(20),
}
job_defaults = {"coalesce": False, "max_instances": 3}


def main(config: ListConfig | DictConfig) -> None:
    _scheduler = BackgroundScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
        timezone=utc,
    )

    print(config)


def parse_config() -> ListConfig | DictConfig:
    parser = ArgumentParser()
    parser.add_argument(
        "--config_file",
        type=str,
        default="config/config.yaml",
        help="configuration file",
    )
    params = parser.parse_args()

    config = OmegaConf.load(params.config_file)
    cli_config = OmegaConf.from_cli()
    config = OmegaConf.merge(config, cli_config)

    return config


if __name__ == "__main__":
    config = parse_config()
    main(config)
