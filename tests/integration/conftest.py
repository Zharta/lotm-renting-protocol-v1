import os

import boa
import pytest
from boa.environment import Env
from eth_account import Account

DELEGATION_REGISTRY_ADDRESS = "0xC3AA9bc72Bd623168860a1e5c6a4530d3D80456c"


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
        blkid = 17614000
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


@pytest.fixture(scope="session")
def nft_contract(owner, forked_env):
    return boa.load("contracts/auxiliary/ERC721.vy")


@pytest.fixture(scope="session")
def ape_contract(owner, forked_env):
    return boa.load("contracts/auxiliary/ERC20.vy", "APE", "APE", 18, 0)


@pytest.fixture(scope="session")
def delegation_registry_warm_contract(forked_env):
    partial_contract = boa.load_partial("tests/stubs/DelegationRegistry.vy")
    return partial_contract.at(DELEGATION_REGISTRY_ADDRESS)


@pytest.fixture(scope="session")
def vault_contract(forked_env, nft_contract, ape_contract, delegation_registry_warm_contract):
    return boa.load("contracts/Vault.vy", ape_contract, nft_contract, delegation_registry_warm_contract)


@pytest.fixture(scope="session")
def renting_contract(vault_contract, ape_contract, nft_contract, delegation_registry_warm_contract):
    return boa.load("contracts/Renting.vy", vault_contract, ape_contract, nft_contract, delegation_registry_warm_contract)


@pytest.fixture(scope="module")
def contracts_config(
    nft_owner,
    owner,
    renter,
    renting_contract,
    vault_contract,
    nft_contract,
    ape_contract,
    delegation_registry_warm_contract,
):
    with boa.env.anchor():
        vault_contract.initialise(
            nft_owner,
            sender=renting_contract.address,
        )
        for i in range(32):
            nft_contract.mint(nft_owner, i, sender=owner)
        ape_contract.mint(renter, int(1000 * 1e18), sender=owner)
        yield
