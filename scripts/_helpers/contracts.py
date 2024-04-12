import json
from dataclasses import dataclass

from ape import project
from ape.contracts.base import ContractContainer, ContractType
from hexbytes import HexBytes

from .basetypes import ContractConfig

ZERO_ADDRESS = "0x" + "00" * 20


@dataclass
class VaultImplV1Contract(ContractConfig):
    def __init__(
        self,
        *,
        key: str,
        version: str | None = None,
        abi_key: str,
        address: str | None = None,
    ):
        super().__init__(
            key,
            None,
            project.VaultV1,
            version=version,
            abi_key=abi_key,
            container_name="VaultV1",
            deployment_deps=[],
            deployment_args=[],
        )
        if address:
            self.load_contract(address)


@dataclass
class VaultImplV2Contract(ContractConfig):
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
            project.VaultV2,
            version=version,
            abi_key=abi_key,
            container_name="VaultV2",
            deployment_deps=[payment_token_key, nft_contract_key, delegation_registry_key],
            deployment_args=[payment_token_key, nft_contract_key, delegation_registry_key],
        )
        if address:
            self.load_contract(address)


@dataclass
class VaultImplV3Contract(ContractConfig):
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
            project.VaultV3,
            version=version,
            abi_key=abi_key,
            container_name="VaultV3",
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
class RentingV1Contract(ContractConfig):
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
        address: str | None = None,
    ):
        super().__init__(
            key,
            None,
            project.RentingV1,
            version=version,
            abi_key=abi_key,
            container_name="RentingV1",
            deployment_deps=[vault_impl_key, payment_token_key, nft_contract_key, delegation_registry_key],
            deployment_args=[vault_impl_key, payment_token_key, nft_contract_key, delegation_registry_key],
        )
        if address:
            self.load_contract(address)


@dataclass
class RentingV2Contract(ContractConfig):
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
            project.RentingV2,
            version=version,
            abi_key=abi_key,
            container_name="RentingV2",
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


@dataclass
class RentingV3Contract(ContractConfig):
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
        renting_erc721_contract_key: str,
        staking_contract_key: str | None = None,
        max_protocol_fee: int | None = None,
        protocol_fee: int | None = None,
        protocol_wallet: str | None = None,
        protocol_admin: str | None = None,
        address: str | None = None,
    ):
        staking_deps = [staking_contract_key] if staking_contract_key else []
        super().__init__(
            key,
            None,
            project.RentingV3,
            version=version,
            abi_key=abi_key,
            container_name="RentingV3",
            deployment_deps=[
                vault_impl_key,
                payment_token_key,
                nft_contract_key,
                delegation_registry_key,
                renting_erc721_contract_key,
            ]
            + staking_deps,
            deployment_args=[
                vault_impl_key,
                payment_token_key,
                nft_contract_key,
                delegation_registry_key,
                renting_erc721_contract_key,
                staking_contract_key or ZERO_ADDRESS,
                max_protocol_fee,
                protocol_fee,
                protocol_wallet,
                protocol_admin,
            ],
        )
        if address:
            self.load_contract(address)


@dataclass
class RentingERC721V3Contract(ContractConfig):
    def __init__(
        self,
        *,
        key: str,
        version: str | None = None,
        abi_key: str,
        name: str | None = None,
        symbol: str | None = None,
        base_url: str | None = None,
        contract_uri: str | None = None,
        address: str | None = None,
    ):
        super().__init__(
            key,
            None,
            project.RentingERC721V3,
            version=version,
            abi_key=abi_key,
            container_name="RentingERC721V3",
            deployment_deps=[],
            deployment_args=[name, symbol, base_url, contract_uri],
        )
        if address:
            self.load_contract(address)


@dataclass
class StakingContract(ContractConfig):
    def __init__(
        self,
        *,
        key: str,
        version: str | None = None,
        abi_key: str,
        apecoin_contract_key: str,
        bayc_contract_key: str,
        mayc_contract_key: str,
        bakc_contract_key: str,
        address: str | None = None,
    ):
        container = StakingContractContainer()
        super().__init__(
            key,
            None,
            container,
            version=version,
            abi_key=abi_key,
            container_name="Staking",
            deployment_deps=[apecoin_contract_key, bayc_contract_key, mayc_contract_key, bakc_contract_key],
            deployment_args=[apecoin_contract_key, bayc_contract_key, mayc_contract_key, bakc_contract_key],
        )
        if address:
            self.load_contract(address)


class StakingContractContainer(ContractContainer):
    def __init__(self):
        with open("contracts/auxiliary/ApeCoinStaking_abi.json", "r") as f:
            abi = json.load(f)
        with open("contracts/auxiliary/ApeCoinStaking_deployment.hex", "r") as f:
            deployment_bytecode = HexBytes(f.read().strip())
        with open("contracts/auxiliary/ApeCoinStaking_runtime.hex", "r") as f:
            runtime_bytecode = HexBytes(f.read().strip())
        contract = ContractType(
            contractName="Staking",
            abi=abi,
            deploymentBytecode=deployment_bytecode,
            runtimeBytecode=runtime_bytecode,
        )
        super().__init__(contract)


contract_map = {
    k.__name__: k
    for k in [
        ERC20Contract,
        ERC721Contract,
        RentingERC721V3Contract,
        RentingV1Contract,
        RentingV2Contract,
        RentingV3Contract,
        StakingContract,
        VaultImplV1Contract,
        VaultImplV2Contract,
        VaultImplV3Contract,
        WarmDelegationContract,
    ]
}
