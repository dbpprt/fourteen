import asyncio
import logging
import os
from argparse import ArgumentParser
from logging import Logger
from typing import List

from omegaconf import DictConfig, ListConfig, OmegaConf
from rich.logging import RichHandler

from src.utils.instantiate import instantiate


async def main(config: ListConfig | DictConfig, logger: Logger) -> None:
    config.scheduler.start()

    integrations: List = []
    for integration in config.integrations:
        integration = integration(
            scheduler=config.scheduler,
            config=config,
            logger=logger,
            integrations=integrations,
        )
        integrations.append(integration)

    print("Press Ctrl+{0} to exit".format("Break" if os.name == "nt" else "C"))

    # # TODO: Does this really work on Linux?
    # def shutdown(sig: signal.Signals) -> None:
    #     logger.warning(f"Received exit signal {sig.name}")

    #     for integration in config.integrations:
    #         asyncio.run(integration.shutdown())

    # async def loop():
    #     running_loop = asyncio.get_running_loop()

    #     if os.name != "nt":
    #         for sig in (signal.SIGTERM, signal.SIGINT):  # signal.SIGHUP,
    #             running_loop.add_signal_handler(sig, shutdown, sig)

    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    parser = ArgumentParser()

    parser.add_argument(
        "--debug",
        action="store_true",
        help="set logging level to debug",
    )
    parser.add_argument(
        "--config_file",
        type=str,
        default="config/config.yaml",
        help="configuration file",
    )
    parser.add_argument(
        "--secrets_file",
        type=str,
        default="config/_secrets.yaml",
        help="secrets file",
    )
    params = parser.parse_args()

    logging.basicConfig(
        level="NOTSET" if params.debug else "WARNING",
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )

    logger = logging.getLogger("rich")

    secrets = OmegaConf.load(params.secrets_file)
    OmegaConf.register_new_resolver("secret", lambda name: secrets[name])
    OmegaConf.register_new_resolver("logger", lambda: logger)

    config = OmegaConf.load(params.config_file)
    cli_config = OmegaConf.from_cli()
    config = OmegaConf.merge(config, cli_config)
    config = instantiate(config, logger=logger)

    try:
        asyncio.run(main(config=config, logger=logger))
    except (KeyboardInterrupt, SystemExit):
        logger.exception("Scheduler stopped")
