from enum import Enum
from typing import Optional, Callable, Any
from ape_accounts.accounts import KeyfileAccount
from ape.contracts.base import ContractContainer, ContractInstance
from dataclasses import dataclass, field

Environment = Enum('Environment', ['local', 'dev', 'int', 'prod'])


@dataclass
class DeploymentContext():

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

    def keys(self):
        return self.contracts.keys() | self.config.keys()

    def gas_options(self):
        return self.gas_func(self) if self.gas_func is not None else {}


@dataclass
class ContractConfig():

    key: str
    contract: Optional[ContractInstance]
    container: ContractContainer
    container_name: str | None = None
    deployment_deps: set[str] = field(default_factory=set)
    config_deps: dict[str, Callable] = field(default_factory=dict)
    deployment_args_contracts: list[Any] = field(default_factory=list)

    def deployable(self, context: DeploymentContext) -> bool:
        return True

    def deployment_dependencies(self, context: DeploymentContext) -> set[str]:
        return self.deployment_deps

    def deployment_args(self, context: DeploymentContext) -> list[Any]:
        return [context[c].contract for c in self.deployment_args_contracts]

    def deployment_options(self, context: DeploymentContext) -> dict[str, Any]:
        return {'sender': context.owner} | context.gas_options()

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
        print_args = self.deployment_args_contracts
        kwargs = self.deployment_options(context)
        kwargs_str = ",".join(f"{k}={v}" for k, v in kwargs.items())
        print(f"## {self.key} <- {self.container_name}.deploy({','.join(str(a) for a in print_args)}, {kwargs_str})")
        if not dryrun:
            self.contract = self.container.deploy(*self.deployment_args(context), **kwargs)