import os

import boa
import pytest
from boa.environment import Env
from eth_account import Account

DELEGATION_REGISTRY_ADDRESS = "0xC3AA9bc72Bd623168860a1e5c6a4530d3D80456c"
APE_STAKING_ADDRESS = "0x5954aB967Bc958940b7EB73ee84797Dc8a2AFbb9"
BAYC_ADDRESS = "0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D"
MAYC_ADDRESS = "0x60E4d786628Fea6478F785A6d7e704777c86a7c6"
APECOIN_ADDRESS = "0x4d224452801ACEd8B2F0aebE155379bb5D594381"


@pytest.fixture(scope="session", autouse=True)
def forked_env():
    old_env = boa.env
    new_env = Env()
    new_env._cached_call_profiles = old_env._cached_call_profiles
    new_env._cached_line_profiles = old_env._cached_line_profiles
    new_env._profiled_contracts = old_env._profiled_contracts

    with boa.swap_env(new_env):
        fork_uri = os.environ["BOA_FORK_RPC_URL"]
        disable_cache = os.environ.get("BOA_FORK_NO_CACHE")
        kw = {"cache_file": None} if disable_cache else {}
        blkid = 19261895
        boa.env.fork(fork_uri, block_identifier=blkid, **kw)
        yield

        old_env._cached_call_profiles = new_env._cached_call_profiles
        old_env._cached_line_profiles = new_env._cached_line_profiles
        old_env._profiled_contracts = new_env._profiled_contracts


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


@pytest.fixture(scope="session", autouse=True)
def renter():
    acc = Account.create()
    boa.env.set_balance(acc.address, 10**21)
    return acc.address


@pytest.fixture(scope="session", autouse=True)
def protocol_wallet():
    acc = Account.create()
    boa.env.set_balance(acc.address, 10**21)
    return acc.address


@pytest.fixture(scope="session")
def erc721_def():
    return boa.load_partial("contracts/auxiliary/ERC721.vy")


@pytest.fixture
def nft_contract(owner, forked_env, erc721_def):
    return erc721_def.deploy()


@pytest.fixture
def bayc_contract(owner, forked_env, erc721_def):
    return erc721_def.at(BAYC_ADDRESS)


@pytest.fixture
def mayc_contract(owner, forked_env, erc721_def):
    return erc721_def.at(MAYC_ADDRESS)


@pytest.fixture(scope="session")
def ape_contract_def(owner, forked_env):
    return boa.load_partial("contracts/auxiliary/ERC20.vy")


@pytest.fixture
def ape_contract(owner, forked_env, ape_contract_def):
    return ape_contract_def.at(APECOIN_ADDRESS)


@pytest.fixture
def delegation_registry_warm_contract(forked_env):
    partial_contract = boa.load_partial("tests/stubs/DelegationRegistry.vy")
    return partial_contract.at(DELEGATION_REGISTRY_ADDRESS)


@pytest.fixture
def ape_staking_contract(nft_contract, ape_contract):
    return boa.load_partial("tests/stubs/ApeStaking.vy").at(APE_STAKING_ADDRESS)


@pytest.fixture
def vault_contract(forked_env, nft_contract, ape_contract, delegation_registry_warm_contract, ape_staking_contract):
    return boa.load("contracts/VaultV3.vy", ape_contract, nft_contract, delegation_registry_warm_contract)


@pytest.fixture
def vault_contract_bayc(forked_env, bayc_contract, ape_contract, delegation_registry_warm_contract, ape_staking_contract):
    return boa.load("contracts/VaultV3.vy", ape_contract, bayc_contract, delegation_registry_warm_contract)


@pytest.fixture
def vault_contract_mayc(forked_env, mayc_contract, ape_contract, delegation_registry_warm_contract, ape_staking_contract):
    return boa.load("contracts/VaultV3.vy", ape_contract, mayc_contract, delegation_registry_warm_contract)


@pytest.fixture
def renting_erc721_contract():
    return boa.load("contracts/RentingERC721V3.vy", "", "", "", "")


@pytest.fixture(scope="session")
def protocol_fee():
    return 500


@pytest.fixture
def renting_contract(
    vault_contract,
    ape_contract,
    nft_contract,
    delegation_registry_warm_contract,
    protocol_wallet,
    protocol_fee,
    renting_erc721_contract,
    ape_staking_contract,
    owner,
):
    return boa.load(
        "contracts/RentingV3.vy",
        vault_contract,
        ape_contract,
        nft_contract,
        delegation_registry_warm_contract,
        renting_erc721_contract,
        ape_staking_contract,
        protocol_fee,
        protocol_fee,
        protocol_wallet,
        owner,
    )


@pytest.fixture
def renting_contract_bayc(
    vault_contract_bayc,
    ape_contract,
    bayc_contract,
    delegation_registry_warm_contract,
    protocol_wallet,
    protocol_fee,
    renting_erc721_contract,
    ape_staking_contract,
    owner,
):
    return boa.load(
        "contracts/RentingV3.vy",
        vault_contract_bayc,
        ape_contract,
        bayc_contract,
        delegation_registry_warm_contract,
        renting_erc721_contract,
        ape_staking_contract,
        protocol_fee,
        protocol_fee,
        protocol_wallet,
        owner,
    )


@pytest.fixture
def renting_contract_mayc(
    vault_contract_mayc,
    ape_contract,
    mayc_contract,
    delegation_registry_warm_contract,
    protocol_wallet,
    protocol_fee,
    renting_erc721_contract,
    ape_staking_contract,
    owner,
):
    return boa.load(
        "contracts/RentingV3.vy",
        vault_contract_mayc,
        ape_contract,
        mayc_contract,
        delegation_registry_warm_contract,
        renting_erc721_contract,
        ape_staking_contract,
        protocol_fee,
        protocol_fee,
        protocol_wallet,
        owner,
    )


@pytest.fixture
def renting_contract_no_fee(
    vault_contract,
    ape_contract,
    nft_contract,
    delegation_registry_warm_contract,
    protocol_wallet,
    renting_erc721_contract,
    ape_staking_contract,
):
    return boa.load(
        "contracts/Renting.vy",
        vault_contract,
        ape_contract,
        nft_contract,
        delegation_registry_warm_contract,
        renting_erc721_contract,
        ape_staking_contract,
        0,
        protocol_wallet,
        protocol_wallet,
    )


@pytest.fixture
def contracts_config(nft_owner, owner, renter, nft_contract, ape_contract):
    with boa.env.anchor():
        ape_contract.transfer(renter, int(40000 * 1e18), sender=ape_contract.address)
        ape_contract.transfer(nft_owner, int(10000 * 1e18), sender=ape_contract.address)
        yield
