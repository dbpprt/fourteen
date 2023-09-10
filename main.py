import os
from argparse import ArgumentParser

from omegaconf import DictConfig, ListConfig, OmegaConf

from lib.utils.instantiate import instantiate


def main(config: ListConfig | DictConfig) -> None:
    for integration in config.integrations:
        integration = integration(scheduler=config.scheduler, config=config)

    print("Press Ctrl+{0} to exit".format("Break" if os.name == "nt" else "C"))

    try:
        config.scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass


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
    config = instantiate(config)

    return config


if __name__ == "__main__":
    config = parse_config()
    main(config)
