import os

import web3

from scripts.deployment import DeploymentManager, Ecosystem, Environment

ENV = Environment[os.environ.get("ENV", "local")]


def inject_poa(w3):
    w3.middleware_onion.inject(web3.middleware.geth_poa_middleware, layer=0)
    return w3


def ape_init_extras(network):
    ECOSYSTEM = Ecosystem[os.environ.get("ECOSYSTEM")]
    print(f"Connected to {network} {ENV=} {ECOSYSTEM=}")
    dm = DeploymentManager(ENV, ECOSYSTEM)

    return {
        "dm": dm,
        "owner": dm.owner,
    } | {
        k.replace(".", "_").replace("-", "_"): v.contract
        for k, v in list(dm.context.contracts.items()) + list(dm.context.config.items())
    }
