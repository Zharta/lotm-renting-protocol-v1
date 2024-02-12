import boa
import pytest

from ...conftest_base import ZERO_ADDRESS

PROTOCOL_FEE = 500


@pytest.fixture(scope="module")
def vault_contract(vault_contract_def, ape_contract, nft_contract, delegation_registry_warm_contract):
    return vault_contract_def.deploy(ape_contract, nft_contract, delegation_registry_warm_contract, ZERO_ADDRESS)


@pytest.fixture(scope="module")
def renting_contract(
    renting_contract_def, vault_contract, ape_contract, nft_contract, delegation_registry_warm_contract, protocol_wallet, owner
):
    return renting_contract_def.deploy(
        vault_contract,
        ape_contract,
        nft_contract,
        delegation_registry_warm_contract,
        ZERO_ADDRESS,
        0,
        PROTOCOL_FEE,
        PROTOCOL_FEE,
        protocol_wallet,
        owner,
    )


@pytest.fixture(autouse=True)
def mint(nft_owner, owner, renter, nft_contract, ape_contract):
    with boa.env.anchor():
        nft_contract.mint(nft_owner, 1, sender=owner)
        ape_contract.mint(renter, int(1000 * 1e18), sender=owner)
        yield
