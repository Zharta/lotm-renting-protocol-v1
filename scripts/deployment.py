import logging
import os
import warnings

import click
from ape import convert
from ape.cli import ConnectedProviderCommand, network_option

from ._helpers.deployment import DeploymentManager, Environment

ENV = Environment[os.environ.get("ENV", "local")]
CHAIN = os.environ.get("CHAIN", "nochain")

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
warnings.filterwarnings("ignore")


def gas_cost(context):
    return {"gas_price": convert("10 gwei", int)}


@click.command(cls=ConnectedProviderCommand)
@network_option()
def cli(network):
    print(f"Connected to {network}")

    dm = DeploymentManager(ENV, CHAIN)
    dm.context.gas_func = gas_cost

    changes = set()
    # changes |= {"common.vault_impl_otherdeed_ape_v3", "common.renting_erc721_otherdeed_v3", "renting.otherdeed_v3"}
    dm.deploy(changes, dryrun=True)

    print("Done")
    return 0
