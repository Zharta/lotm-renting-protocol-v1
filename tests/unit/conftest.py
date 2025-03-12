from textwrap import dedent

import boa
import pytest
from boa.vm.py_evm import register_raw_precompile
from eth_account import Account


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
def nft_owner_account():
    return Account.create()


@pytest.fixture(scope="session")
def nft_owner(nft_owner_account):
    boa.env.set_balance(nft_owner_account.address, 10**21)
    return nft_owner_account.address


@pytest.fixture(scope="session")
def nft_owner_key(nft_owner_account):
    return nft_owner_account.key


@pytest.fixture(scope="session")
def renter():
    acc = boa.env.generate_address("renter")
    boa.env.set_balance(acc, 10**21)
    return acc


@pytest.fixture(scope="session")
def protocol_wallet():
    acc = boa.env.generate_address("protocol_owner")
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
def ape_staking_contract_def():
    return boa.load_partial("tests/stubs/ApeStaking.vy")


@pytest.fixture(scope="session")
def vault_contract_def():
    return boa.load_partial("contracts/VaultV3.vy")


@pytest.fixture(scope="session")
def renting_contract_def():
    return boa.load_partial("contracts/RentingV3.vy")


@pytest.fixture(scope="session")
def renting_erc721_contract_def():
    return boa.load_partial("contracts/RentingERC721V3.vy")


@pytest.fixture(scope="module")
def empty_contract_def():
    return boa.loads_partial(
        dedent(
            """
        dummy: uint256
     """
        )
    )


# @boa.precompile("def debug_bytes32(data: bytes32)")
# def debug_bytes32(data: bytes):
#     print(f"DEBUG: {data.hex()}")


# @pytest.fixture(scope="session")
# def debug_precompile():
#     register_raw_precompile("0x00000000000000000000000000000000000000ff", debug_bytes32)
#     yield
