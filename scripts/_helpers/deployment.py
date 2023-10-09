import json
import logging
import os
import warnings
from pathlib import Path
from typing import Any

from ape import accounts

from .basetypes import ContractConfig, DeploymentContext, Environment
from .contracts import contract_map
from .dependency import DependencyManager

ENV = Environment[os.environ.get("ENV", "local")]

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
warnings.filterwarnings("ignore")


def load_contracts(env: Environment) -> list[ContractConfig]:
    config_file = f"{Path.cwd()}/configs/{env.name}/renting.json"
    with open(config_file, "r") as f:
        config = json.load(f)
    contracts = [
        contract_map[c["contract"]](key=f"{scope}.{name}", address=c.get("address"), **c.get("properties", {}))
        for scope in ["common", "renting"]
        for name, c in config[scope].items()
    ]

    # always deploy everything in local
    if env == Environment.local:
        for contract in contracts:
            contract.contract = None

    return contracts


def store_contracts(env: Environment, contracts: list[ContractConfig]):
    config_file = f"{Path.cwd()}/configs/{env.name}/renting.json"
    with open(config_file, "r") as f:
        config = json.load(f)

    contracts_dict = {c.key: c for c in contracts}
    for scope in ["common", "renting"]:
        for name, c in config[scope].items():
            key = f"{scope}.{name}"
            if key in contracts_dict:
                c["address"] = contracts_dict[key].address()
            properties = c.get("properties", {})
            addresses = c.get("properties_addresses", {})
            for prop_key, prop_val in properties.items():
                if prop_key.endswith("_key"):
                    addresses[prop_key[:-4]] = contracts_dict[prop_val].address()
            c["properties_addresses"] = addresses

    with open(config_file, "w") as f:
        f.write(json.dumps(config, indent=4, sort_keys=True))


class DeploymentManager:
    def __init__(self, env: Environment):
        self.env = env
        match env:
            case Environment.local:
                self.owner = accounts[0]
            case Environment.dev:
                self.owner = accounts.load("devacc")
            case Environment.int:
                self.owner = accounts.load("goerliacc")
            case Environment.prod:
                self.owner = accounts.load("prodacc")

        self.context = DeploymentContext(self._get_contracts(), self.env, self.owner, self._get_configs())

    def _get_contracts(self) -> dict[str, ContractConfig]:
        contracts = load_contracts(self.env)
        return {c.key: c for c in contracts}

    def _get_configs(self) -> dict[str, Any]:
        return {}

    def _save_state(self):
        contracts = [c for c in self.context.contracts.values()]
        store_contracts(self.env, contracts)

    def deploy(self, changes: set[str], dryrun=False, save_state=True):
        self.owner.set_autosign(True)
        dependency_manager = DependencyManager(self.context, changes)
        contracts_to_deploy = dependency_manager.build_contract_deploy_set()
        dependencies_tx = dependency_manager.build_transaction_set()

        for contract in contracts_to_deploy:
            if contract.deployable(self.context):
                contract.deploy(self.context, dryrun)

        for dependency_tx in dependencies_tx:
            dependency_tx(self.context, dryrun)

        if save_state and not dryrun:
            self._save_state()

    def deploy_all(self, dryrun=False, save_state=True):
        self.deploy(self.context.contracts.keys(), dryrun=dryrun, save_state=save_state)
