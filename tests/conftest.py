import boa
from eth_account import Account

import pytest


DELEGATION_REGISTRY_ADDRESS = "0xC3AA9bc72Bd623168860a1e5c6a4530d3D80456c"


@pytest.fixture(scope="session")
def accounts():
    _accounts = [boa.env.generate_address() for _ in range(10)]
    for account in _accounts:
        boa.env.set_balance(account, 10**21)
    return _accounts


@pytest.fixture(scope="session", autouse=True)
def owner():
    acc = Account.create()
    boa.env.eoa = acc.address
    boa.env.set_balance(acc.address, 10**21)
    return acc.address


@pytest.fixture(scope="session", autouse=True)
def nft_owner():
    acc = Account.create()
    boa.env.set_balance(acc.address, 10**21)
    return acc.address


@pytest.fixture(scope="session", autouse=True)
def renter():
    acc = Account.create()
    boa.env.set_balance(acc.address, 10**21)
    return acc.address


# Temp account
@pytest.fixture(scope="session", autouse=True)
def lotm_renting_contract():
    acc = Account.create()
    return acc.address


@pytest.fixture(scope="session")
def nft_contract(owner):
    return boa.load("tests/auxiliary/ERC721.vy")


@pytest.fixture(scope="session")
def ape_contract(owner):
    return boa.load("tests/auxiliary/ERC20.vy", "APE", "APE", 18, 0)


@pytest.fixture(scope="session")
def delegation_registry_warm_contract():
    abi = boa.load_abi("tests/auxiliary/delegation_registry_warm_abi.json")
    return abi.at("0xC3AA9bc72Bd623168860a1e5c6a4530d3D80456c")


@pytest.fixture(scope="session")
def vault_contract():
    return boa.load("contracts/Vault.vy")


@pytest.fixture(scope="module")
def contracts_config(
    nft_owner,
    owner,
    renter,
    lotm_renting_contract,
    vault_contract,
    nft_contract,
    ape_contract,
    delegation_registry_warm_contract,
):
    with boa.env.anchor():
        vault_contract.initialise(
            nft_owner,
            lotm_renting_contract,
            ape_contract,
            nft_contract,
            delegation_registry_warm_contract,
            sender=lotm_renting_contract,
        )
        nft_contract.mint(nft_owner, 1, sender=owner)
        ape_contract.mint(renter, int(1000 * 1e18), sender=owner)
        yield
