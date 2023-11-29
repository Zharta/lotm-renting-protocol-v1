from textwrap import dedent

import boa
import pytest


@pytest.fixture(scope="session")
def accounts():
    _accounts = [boa.env.generate_address() for _ in range(10)]
    for account in _accounts:
        boa.env.set_balance(account, 10**21)
    return _accounts


@pytest.fixture(scope="session")
def owner():
    acc = boa.env.generate_address("owner")
    boa.env.eoa = acc
    boa.env.set_balance(acc, 10**21)
    return acc


@pytest.fixture(scope="session")
def nft_owner():
    acc = boa.env.generate_address("nft_owner")
    boa.env.set_balance(acc, 10**21)
    return acc


@pytest.fixture(scope="session")
def renter():
    acc = boa.env.generate_address("renter")
    boa.env.set_balance(acc, 10**21)
    return acc


@pytest.fixture(scope="session")
def protocol_wallet():
    acc = boa.env.generate_address("renter")
    boa.env.set_balance(acc, 10**21)
    return acc


@pytest.fixture(scope="session")
def nft_contract(owner):
    with boa.env.prank(owner):
        return boa.load("contracts/auxiliary/ERC721.vy")


@pytest.fixture(scope="session")
def ape_contract(owner):
    with boa.env.prank(owner):
        return boa.load("contracts/auxiliary/ERC20.vy", "APE", "APE", 18, 0)


@pytest.fixture(scope="session")
def delegation_registry_warm_contract():
    return boa.load("contracts/auxiliary/HotWalletMock.vy")


@pytest.fixture(scope="session")
def vault_contract_def():
    return boa.load_partial("contracts/Vault.vy")


@pytest.fixture(scope="session")
def renting_contract_def():
    return boa.load_partial("contracts/Renting.vy")


@pytest.fixture(scope="session")
def empty_contract_def():
    return boa.loads_partial(
        dedent(
            """
        dummy: uint256
     """
        )
    )


@pytest.fixture(scope="module")
def vault_contract(vault_contract_def, nft_contract, ape_contract, delegation_registry_warm_contract):
    return vault_contract_def.deploy(ape_contract, nft_contract, delegation_registry_warm_contract)


@pytest.fixture(scope="module")
def renting_contract(renting_contract_def, vault_contract, ape_contract, nft_contract, delegation_registry_warm_contract, protocol_wallet):
    return renting_contract_def.deploy(vault_contract, ape_contract, nft_contract, delegation_registry_warm_contract, 0, 0, protocol_wallet, protocol_wallet)
