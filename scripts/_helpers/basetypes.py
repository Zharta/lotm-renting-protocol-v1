import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from ape.contracts.base import ContractContainer, ContractInstance
from ape_accounts.accounts import KeyfileAccount

Environment = Enum("Environment", ["local", "dev", "int", "prod"])


def abi_key(abi: list) -> str:
    json_dump = json.dumps(abi, sort_keys=True)
    hash = hashlib.sha1(json_dump.encode("utf8"))
    return hash.hexdigest()


@dataclass
class DeploymentContext:
    contracts: dict[str, Any]
    env: Environment
    owner: KeyfileAccount
    config: dict[str, Any] = field(default_factory=dict)
    gas_func: Callable | None = None

    def __getitem__(self, key):
        if key in self.contracts:
            return self.contracts[key]
        else:
            return self.config[key]

    def __contains__(self, key):
        return key in self.contracts or key in self.config

    def keys(self):
        return self.contracts.keys() | self.config.keys()

    def gas_options(self):
        return self.gas_func(self) if self.gas_func is not None else {}


@dataclass
class ContractConfig:
    key: str
    contract: Optional[ContractInstance]
    container: ContractContainer
    container_name: str | None = None
    deployment_deps: set[str] = field(default_factory=set)
    config_deps: dict[str, Callable] = field(default_factory=dict)
    deployment_args: list[Any] = field(default_factory=list)
    abi_key: str | None = None

    def deployable(self, context: DeploymentContext) -> bool:
        return True

    def deployment_dependencies(self, context: DeploymentContext) -> set[str]:
        return self.deployment_deps

    def deployment_args_values(self, context: DeploymentContext) -> list[Any]:
        values = [context[c] if c in context else c for c in self.deployment_args]
        return [v.contract if isinstance(v, ContractConfig) else v for v in values]

    def deployment_args_repr(self, context: DeploymentContext) -> list[Any]:
        return [f"[{c}]" if c in context else c for c in self.deployment_args]

    def deployment_options(self, context: DeploymentContext) -> dict[str, Any]:
        return {"sender": context.owner} | context.gas_options()

    def config_dependencies(self, context: DeploymentContext) -> dict[str, Callable]:
        return self.config_deps

    def address(self):
        return self.contract.address if self.contract else None

    def config_key(self):
        return self.key

    def __str__(self):
        return self.key

    def __repr__(self):
        return f"Contract[key={self.key}, contract={self.contract}, container_name={self.container_name}]"

    def load_contract(self, address: str):
        self.contract = self.container.at(address)

    def deploy(self, context: DeploymentContext, dryrun: bool = False):
        if self.contract is not None:
            print(f"WARNING: Deployment will override contract *{self.key}* at {self.contract}")
        if not self.deployable(context):
            raise Exception(f"Cant deploy contract {self} in current context")
        print_args = self.deployment_args_repr(context)
        kwargs = self.deployment_options(context)
        kwargs_str = ",".join(f"{k}={v}" for k, v in kwargs.items())
        print(f"## {self.key} <- {self.container_name}.deploy({','.join(str(a) for a in print_args)}, {kwargs_str})")
        if not dryrun:
            self.contract = self.container.deploy(*self.deployment_args_values(context), **kwargs)
            self.abi_key = abi_key(self.contract.contract_type.dict()["abi"])
