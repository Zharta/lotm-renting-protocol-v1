from textwrap import dedent

import boa
import pytest

from ...conftest_base import ZERO_ADDRESS

FOREVER = 2**256 - 1


@pytest.fixture(scope="module")
def renting_contract(empty_contract_def):
    return empty_contract_def.deploy()


@pytest.fixture(scope="module")
def vault_contract(
    nft_owner,
    renting_contract,
    vault_contract_def,
    nft_contract,
    ape_contract,
    delegation_registry_warm_contract,
):
    contract = vault_contract_def.deploy(ape_contract, nft_contract, delegation_registry_warm_contract, ZERO_ADDRESS)
    contract.initialise(0, sender=renting_contract.address)
    return contract


@pytest.fixture(autouse=True)
def mint(nft_owner, owner, renter, nft_contract, ape_contract):
    with boa.env.anchor():
        nft_contract.mint(nft_owner, 1, sender=owner)
        ape_contract.mint(renter, int(1000 * 1e18), sender=owner)
        yield


@pytest.fixture(scope="module")
def erc20_not_reverting():
    return boa.loads(
        dedent(
            """
        @external
        def transfer(dst: address, wallet: uint256) -> bool:
            return False

        @external
        def transferFrom(src: address, dst: address, wallet: uint256) -> bool:
            return False

        @external
        def allowance(src: address, dst: address) -> uint256:
            return max_value(uint256)

             """
        )
    )


def test_initial_state(vault_contract, nft_owner, renting_contract, nft_contract, ape_contract):
    assert vault_contract.caller() == renting_contract.address
    assert vault_contract.nft_contract() == nft_contract.address
    assert vault_contract.payment_token() == ape_contract.address
    assert vault_contract.staking_addr() == ZERO_ADDRESS


def test_initialise(vault_contract_def, renting_contract, ape_contract, nft_contract, delegation_registry_warm_contract):
    vault_contract = vault_contract_def.deploy(ape_contract, nft_contract, delegation_registry_warm_contract, ZERO_ADDRESS)
    staking_pool_id = 1

    assert vault_contract.caller() == ZERO_ADDRESS
    assert vault_contract.staking_pool_id() == 0

    vault_contract.initialise(staking_pool_id, sender=renting_contract.address)

    assert vault_contract.caller() == renting_contract.address
    assert vault_contract.staking_pool_id() == staking_pool_id


def test_initialise_already_initialised(vault_contract, renting_contract):
    staking_pool_id = 1

    with boa.reverts("already initialised"):
        vault_contract.initialise(staking_pool_id, sender=renting_contract.address)


def test_initialise_invalid_staking_pool_id(
    vault_contract_def, renting_contract, ape_contract, nft_contract, delegation_registry_warm_contract
):
    vault_contract = vault_contract_def.deploy(ape_contract, nft_contract, delegation_registry_warm_contract, ZERO_ADDRESS)
    staking_pool_id = 3

    with boa.reverts("invalid staking pool id"):
        vault_contract.initialise(staking_pool_id, sender=renting_contract.address)


def test_delegate_to_wallet_not_caller(vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.delegate_to_wallet(nft_owner, 0, sender=nft_owner)


def test_delegate_to_wallet(vault_contract, renting_contract, delegation_registry_warm_contract):
    delegate = boa.env.generate_address("delegate")
    expiration = boa.eval("block.timestamp") + 3600

    delegation_registry_warm_contract.setHotWallet(ZERO_ADDRESS, 0, False, sender=vault_contract.address)

    vault_contract.delegate_to_wallet(delegate, expiration, sender=renting_contract.address)

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == delegate
    assert delegation_registry_warm_contract.eval(f"self.exp[{vault_contract.address}]") == expiration


def test_deposit(vault_contract, renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract):
    token_id = 1
    delegate = boa.env.generate_address("delegate")
    print(f"delegate: {delegate}")

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, nft_owner, delegate, sender=renting_contract.address)

    assert nft_contract.ownerOf(token_id) == vault_contract.address
    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == delegate
    assert delegation_registry_warm_contract.eval(f"self.exp[{vault_contract.address}]") == FOREVER


def test_deposit_no_delegate(vault_contract, renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract):
    token_id = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, nft_owner, ZERO_ADDRESS, sender=renting_contract.address)

    assert nft_contract.ownerOf(token_id) == vault_contract.address
    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == ZERO_ADDRESS


def test_deposit_not_caller(vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.deposit(1, nft_owner, ZERO_ADDRESS, sender=nft_owner)


def test_deposit_not_approved(vault_contract, renting_contract, nft_contract, nft_owner):
    with boa.reverts():
        vault_contract.deposit(1, nft_owner, ZERO_ADDRESS, sender=renting_contract.address)


def test_deposit_twice(vault_contract, renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract):
    token_id = 1
    delegate = boa.env.generate_address("delegate")

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, nft_owner, delegate, sender=renting_contract.address)

    with boa.reverts():
        vault_contract.deposit(token_id, nft_owner, delegate, sender=renting_contract.address)


def test_withdraw_not_caller(vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.withdraw(1, nft_owner, sender=nft_owner)


def test_withdraw(vault_contract, renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract):
    token_id = 1
    delegate = boa.env.generate_address("delegate")

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, nft_owner, delegate, sender=renting_contract.address)

    vault_contract.withdraw(token_id, nft_owner, sender=renting_contract.address)

    assert nft_contract.ownerOf(token_id) == nft_owner
    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == ZERO_ADDRESS


def test_withdraw_not_deposited(vault_contract, renting_contract, nft_contract, nft_owner):
    with boa.reverts():
        vault_contract.withdraw(1, nft_owner, sender=renting_contract.address)


def test_withdraw_twice(vault_contract, renting_contract, nft_contract, nft_owner):
    token_id = 1
    delegate = boa.env.generate_address("delegate")

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, nft_owner, delegate, sender=renting_contract.address)

    vault_contract.withdraw(token_id, nft_owner, sender=renting_contract.address)

    with boa.reverts():
        vault_contract.withdraw(token_id, nft_owner, sender=renting_contract.address)
