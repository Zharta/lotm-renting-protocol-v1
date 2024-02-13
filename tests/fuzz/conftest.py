from textwrap import dedent

import boa
import pytest
from eth_account import Account

from ..conftest_base import ZERO_ADDRESS


@pytest.fixture(scope="session")
def accounts():
    _accounts = [boa.env.generate_address() for _ in range(10)]
    for account in _accounts:
        boa.env.set_balance(account, 10**21)
    return _accounts


@pytest.fixture(scope="session")
def owner_account():
    return Account.create()


@pytest.fixture(scope="session")
def owner(owner_account):
    # acc = boa.env.generate_address("owner")
    boa.env.eoa = owner_account.address
    boa.env.set_balance(owner_account.address, 10**21)
    return owner_account.address


@pytest.fixture(scope="session")
def owner_key(owner_account):
    return owner_account.key


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
    return boa.load_partial("contracts/VaultV3.vy")


@pytest.fixture(scope="session")
def renting_contract_def():
    return boa.load_partial("contracts/RentingV3.vy")


@pytest.fixture(scope="session")
def renting_erc721_contract_def():
    return boa.load_partial("contracts/RentingERC721V3.vy")


@pytest.fixture(scope="session")
def protocol_fee():
    return 500


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
def vault_contract(vault_contract_def, ape_contract, nft_contract, delegation_registry_warm_contract):
    return vault_contract_def.deploy(ape_contract, nft_contract, delegation_registry_warm_contract, ZERO_ADDRESS)


@pytest.fixture(scope="module")
def renting_erc721_contract(renting_erc721_contract_def):
    return renting_erc721_contract_def.deploy()


@pytest.fixture(scope="module")
def renting_contract(
    renting_contract_def,
    renting_erc721_contract,
    vault_contract,
    ape_contract,
    nft_contract,
    delegation_registry_warm_contract,
    protocol_wallet,
    owner,
    protocol_fee,
):
    return renting_contract_def.deploy(
        vault_contract,
        ape_contract,
        nft_contract,
        delegation_registry_warm_contract,
        renting_erc721_contract,
        ZERO_ADDRESS,
        0,
        protocol_fee,
        protocol_fee,
        protocol_wallet,
        owner,
    )
