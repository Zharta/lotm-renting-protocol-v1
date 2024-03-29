from dataclasses import dataclass

from ape import project

from .basetypes import ContractConfig


@dataclass
class VaultImplContract(ContractConfig):
    def __init__(
        self,
        *,
        key: str,
        version: str | None = None,
        abi_key: str,
        payment_token_key: str,
        nft_contract_key: str,
        delegation_registry_key: str,
        address: str | None = None,
    ):
        super().__init__(
            key,
            None,
            project.Vault,
            version=version,
            abi_key=abi_key,
            container_name="Vault",
            deployment_deps=[payment_token_key, nft_contract_key, delegation_registry_key],
            deployment_args=[payment_token_key, nft_contract_key, delegation_registry_key],
        )
        if address:
            self.load_contract(address)


@dataclass
class ERC20Contract(ContractConfig):
    def __init__(
        self,
        *,
        key: str,
        version: str | None = None,
        abi_key: str,
        name: str,
        symbol: str,
        decimals: int,
        supply: int,
        address: str | None = None,
    ):
        super().__init__(
            key,
            None,
            project.ERC20,
            version=version,
            abi_key=abi_key,
            container_name="ERC20",
            deployment_args=[name, symbol, int(decimals), int(supply)],
        )
        if address:
            self.load_contract(address)


@dataclass
class ERC721Contract(ContractConfig):
    def __init__(self, *, key: str, version: str | None = None, abi_key: str, address: str | None = None):
        super().__init__(key, None, project.ERC721, version=version, abi_key=abi_key, container_name="ERC721")
        if address:
            self.load_contract(address)


@dataclass
class WarmDelegationContract(ContractConfig):
    def __init__(self, *, key: str, version: str | None = None, abi_key: str, address: str | None = None):
        super().__init__(key, None, project.HotWalletMock, version=version, abi_key=abi_key, container_name="HotWalletMock")
        if address:
            self.load_contract(address)


@dataclass
class RentingContract(ContractConfig):
    def __init__(
        self,
        *,
        key: str,
        version: str | None = None,
        abi_key: str,
        vault_impl_key: str,
        payment_token_key: str,
        nft_contract_key: str,
        delegation_registry_key: str,
        max_protocol_fee: int | None = None,
        protocol_fee: int | None = None,
        protocol_wallet: str | None = None,
        protocol_admin: str | None = None,
        address: str | None = None,
    ):
        super().__init__(
            key,
            None,
            project.Renting,
            version=version,
            abi_key=abi_key,
            container_name="Renting",
            deployment_deps=[vault_impl_key, payment_token_key, nft_contract_key, delegation_registry_key],
            deployment_args=[
                vault_impl_key,
                payment_token_key,
                nft_contract_key,
                delegation_registry_key,
                max_protocol_fee,
                protocol_fee,
                protocol_wallet,
                protocol_admin,
            ],
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
