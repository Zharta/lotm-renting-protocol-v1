from dataclasses import dataclass
from typing import Any

from ape import project

from .basetypes import ContractConfig, DeploymentContext


@dataclass
class VaultImplContract(ContractConfig):
    def __init__(self, *, key: str, address: str | None = None):
        super().__init__(
            key,
            None,
            project.Vault,
            container_name="Vault",
        )
        if address:
            self.load_contract(address)


@dataclass
class ERC20Contract(ContractConfig):
    def __init__(self, *, key: str, name: str, symbol: str, decimals: int, supply: int, address: str | None = None):
        super().__init__(
            key,
            None,
            project.ERC20,
            container_name="ERC20",
        )
        if address:
            self.load_contract(address)
        self._name = name
        self._symbol = symbol
        self._decimals = decimals
        self._supply = supply

    def deployment_args(self, context: DeploymentContext) -> list[Any]:
        return [self._name, self._symbol, int(self._decimals), int(self._supply)]


@dataclass
class ERC721Contract(ContractConfig):
    def __init__(self, *, key: str, address: str | None = None):
        super().__init__(key, None, project.ERC721, container_name="ERC721")
        if address:
            self.load_contract(address)


@dataclass
class WarmDelegationContract(ContractConfig):
    def __init__(self, *, key: str, address: str | None = None):
        super().__init__(key, None, project.HotWalletMock, container_name="HotWalletMock")
        if address:
            self.load_contract(address)


@dataclass
class RentingContract(ContractConfig):
    def __init__(
        self,
        *,
        key: str,
        vault_impl_key: str,
        payment_token_key: str,
        nft_contract_key: int,
        delegation_registry_key: int,
        address: str | None = None,
    ):
        super().__init__(
            key,
            None,
            project.Renting,
            container_name="Renting",
            deployment_deps=[vault_impl_key, payment_token_key, nft_contract_key, delegation_registry_key],
            deployment_args_contracts=[vault_impl_key, payment_token_key, nft_contract_key, delegation_registry_key],
        )
        if address:
            self.load_contract(address)


contract_map = {
    k.__name__: k
    for k in [
        ERC20Contract,
        ERC721Contract,
        RentingContract,
        VaultImplContract,
        WarmDelegationContract,
    ]
}
