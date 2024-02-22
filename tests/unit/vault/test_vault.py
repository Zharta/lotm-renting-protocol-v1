from textwrap import dedent

import boa
import pytest

from ...conftest_base import ZERO_ADDRESS

FOREVER = 2**256 - 1
POOL_BAYC = 1
POOL_MAYC = 2


@pytest.fixture(scope="module")
def renting_contract(empty_contract_def):
    return empty_contract_def.deploy()


@pytest.fixture(scope="module")
def ape_staking_contract(ape_staking_contract_def, nft_contract, ape_contract):
    return ape_staking_contract_def.deploy(ape_contract, nft_contract, nft_contract)


@pytest.fixture(scope="module")
def vault_contract(
    nft_owner,
    renting_contract,
    vault_contract_def,
    nft_contract,
    ape_contract,
    delegation_registry_warm_contract,
    ape_staking_contract,
):
    contract = vault_contract_def.deploy(ape_contract, nft_contract, delegation_registry_warm_contract, ape_staking_contract)
    contract.initialise(1, sender=renting_contract.address)
    return contract


@pytest.fixture(scope="module")
def vault_contract_pool_bayc(
    nft_owner,
    renting_contract,
    vault_contract_def,
    nft_contract,
    ape_contract,
    delegation_registry_warm_contract,
    ape_staking_contract,
):
    contract = vault_contract_def.deploy(ape_contract, nft_contract, delegation_registry_warm_contract, ape_staking_contract)
    contract.initialise(POOL_BAYC, sender=renting_contract.address)
    return contract


@pytest.fixture(scope="module")
def vault_contract_pool_mayc(
    nft_owner,
    renting_contract,
    vault_contract_def,
    nft_contract,
    ape_contract,
    delegation_registry_warm_contract,
    ape_staking_contract,
):
    contract = vault_contract_def.deploy(ape_contract, nft_contract, delegation_registry_warm_contract, ape_staking_contract)
    contract.initialise(POOL_MAYC, sender=renting_contract.address)
    return contract


@pytest.fixture(autouse=True)
def mint(nft_owner, owner, renter, nft_contract, ape_contract):
    with boa.env.anchor():
        nft_contract.mint(nft_owner, 1, sender=owner)
        ape_contract.mint(renter, int(1000 * 1e18), sender=owner)
        ape_contract.mint(nft_owner, int(1000 * 1e18), sender=owner)
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


def test_initial_state(
    vault_contract,
    nft_owner,
    renting_contract,
    nft_contract,
    ape_contract,
    ape_staking_contract,
    delegation_registry_warm_contract,
):
    assert vault_contract.caller() == renting_contract.address
    assert vault_contract.nft_contract() == nft_contract.address
    assert vault_contract.payment_token() == ape_contract.address
    assert vault_contract.staking_addr() == ape_staking_contract.address
    assert vault_contract.delegation_registry() == delegation_registry_warm_contract.address


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
    staking_contract = boa.env.generate_address("staking_contract")
    vault_contract = vault_contract_def.deploy(ape_contract, nft_contract, delegation_registry_warm_contract, staking_contract)
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


def test_staking_deposit_bayc(
    owner, nft_owner, vault_contract_pool_bayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(1e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_bayc, token_id, sender=nft_owner)
    vault_contract_pool_bayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_bayc.address, amount, sender=nft_owner)
    vault_contract_pool_bayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    assert ape_staking_contract.staked_nfts(POOL_BAYC, token_id) == amount


def test_staking_deposit_mayc(
    owner, nft_owner, vault_contract_pool_mayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(1e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_mayc, token_id, sender=nft_owner)
    vault_contract_pool_mayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_mayc.address, amount, sender=nft_owner)
    vault_contract_pool_mayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    assert ape_staking_contract.staked_nfts(POOL_MAYC, token_id) == amount


def test_staking_deposit_not_caller(
    owner, nft_owner, vault_contract_pool_bayc, renting_contract, ape_staking_contract, ape_contract
):
    amount = int(1e18)
    token_id = 1

    ape_contract.transfer(vault_contract_pool_bayc.address, amount, sender=nft_owner)

    with boa.reverts("not caller"):
        vault_contract_pool_bayc.staking_deposit(nft_owner, amount, token_id, sender=nft_owner)


def test_staking_deposit_not_approved(
    owner, nft_owner, vault_contract_pool_bayc, renting_contract, ape_staking_contract, ape_contract
):
    amount = int(1e18)
    token_id = 1

    with boa.reverts():
        vault_contract_pool_bayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)
    assert ape_staking_contract.staked_ape(vault_contract_pool_bayc.address) == 0


def test_staking_deposit_bayc_not_deposited(
    owner, nft_owner, vault_contract_pool_bayc, renting_contract, ape_staking_contract, ape_contract
):
    amount = int(1e18)
    token_id = 1
    ape_contract.transfer(vault_contract_pool_bayc.address, amount, sender=nft_owner)

    with boa.reverts():
        vault_contract_pool_bayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)
    assert ape_staking_contract.staked_nfts(POOL_BAYC, token_id) == 0


def test_staking_deposit_mayc_not_deposited(
    owner, nft_owner, vault_contract_pool_mayc, renting_contract, ape_staking_contract, ape_contract
):
    amount = int(1e18)
    token_id = 1
    ape_contract.transfer(vault_contract_pool_mayc.address, amount, sender=nft_owner)

    with boa.reverts():
        vault_contract_pool_mayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)
    assert ape_staking_contract.staked_nfts(POOL_MAYC, token_id) == 0


def test_staking_deposit_low_amount(owner, nft_owner, vault_contract, renting_contract, ape_staking_contract, ape_contract):
    amount = int(1e18) - 1
    token_id = 1

    ape_contract.transfer(vault_contract.address, amount, sender=nft_owner)

    with boa.reverts():
        vault_contract.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)
    assert ape_staking_contract.staked_ape(vault_contract.address) == 0


def test_staking_withdraw_not_deposited(
    owner, nft_owner, vault_contract, renting_contract, ape_staking_contract, ape_contract
):
    amount = int(1e18)
    token_id = 1

    with boa.reverts():
        vault_contract.staking_withdraw(nft_owner, amount, token_id, sender=renting_contract.address)
    assert ape_staking_contract.staked_ape(vault_contract.address) == 0


def test_staking_withdraw_bayc(
    owner, nft_owner, vault_contract_pool_bayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(1e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_bayc, token_id, sender=nft_owner)
    vault_contract_pool_bayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_bayc.address, amount, sender=nft_owner)
    vault_contract_pool_bayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    vault_contract_pool_bayc.staking_withdraw(nft_owner, amount, token_id, sender=renting_contract.address)
    assert ape_staking_contract.staked_nfts(POOL_BAYC, token_id) == 0


def test_staking_withdraw_bayc_withdrawn(
    owner, nft_owner, vault_contract_pool_bayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(1e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_bayc, token_id, sender=nft_owner)
    vault_contract_pool_bayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_bayc.address, amount, sender=nft_owner)
    vault_contract_pool_bayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    vault_contract_pool_bayc.withdraw(token_id, nft_owner, sender=renting_contract.address)

    nft_owner_ape = ape_contract.balanceOf(nft_owner)
    ape_staking_contract.withdrawBAYC([(token_id, amount)], nft_owner, sender=nft_owner)
    assert ape_staking_contract.staked_nfts(POOL_BAYC, token_id) == 0
    assert ape_contract.balanceOf(nft_owner) == nft_owner_ape + amount


def test_staking_withdraw_bayc_not_caller(
    owner, nft_owner, vault_contract_pool_bayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(1e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_bayc, token_id, sender=nft_owner)
    vault_contract_pool_bayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_bayc.address, amount, sender=nft_owner)
    vault_contract_pool_bayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    with boa.reverts("not caller"):
        vault_contract_pool_bayc.staking_withdraw(nft_owner, amount, token_id, sender=nft_owner)
    assert ape_staking_contract.staked_nfts(POOL_BAYC, token_id) == amount


def test_staking_withdraw_bayc_not_enough_staked(
    owner, nft_owner, vault_contract_pool_bayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(1e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_bayc, token_id, sender=nft_owner)
    vault_contract_pool_bayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_bayc.address, amount, sender=nft_owner)
    vault_contract_pool_bayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    with boa.reverts():
        vault_contract_pool_bayc.staking_withdraw(nft_owner, amount + 1, token_id, sender=renting_contract.address)
    assert ape_staking_contract.staked_nfts(POOL_BAYC, token_id) == amount


def test_staking_withdraw_mayc(
    owner, nft_owner, vault_contract_pool_mayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(1e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_mayc, token_id, sender=nft_owner)
    vault_contract_pool_mayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_mayc.address, amount, sender=nft_owner)
    vault_contract_pool_mayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    vault_contract_pool_mayc.staking_withdraw(nft_owner, amount, token_id, sender=renting_contract.address)
    assert ape_staking_contract.staked_nfts(POOL_MAYC, token_id) == 0


def test_staking_withdraw_mayc_withdrawn(
    owner, nft_owner, vault_contract_pool_mayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(1e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_mayc, token_id, sender=nft_owner)
    vault_contract_pool_mayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_mayc.address, amount, sender=nft_owner)
    vault_contract_pool_mayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    vault_contract_pool_mayc.withdraw(token_id, nft_owner, sender=renting_contract.address)

    nft_owner_ape = ape_contract.balanceOf(nft_owner)
    ape_staking_contract.withdrawMAYC([(token_id, amount)], nft_owner, sender=nft_owner)
    assert ape_staking_contract.staked_nfts(POOL_MAYC, token_id) == 0
    assert ape_contract.balanceOf(nft_owner) == nft_owner_ape + amount


def test_staking_withdraw_mayc_not_caller(
    owner, nft_owner, vault_contract_pool_mayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(1e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_mayc, token_id, sender=nft_owner)
    vault_contract_pool_mayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_mayc.address, amount, sender=nft_owner)
    vault_contract_pool_mayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    with boa.reverts("not caller"):
        vault_contract_pool_mayc.staking_withdraw(nft_owner, amount, token_id, sender=nft_owner)
    assert ape_staking_contract.staked_nfts(POOL_MAYC, token_id) == amount


def test_staking_withdraw_mayc_not_enough_staked(
    owner, nft_owner, vault_contract_pool_mayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(1e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_mayc, token_id, sender=nft_owner)
    vault_contract_pool_mayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_mayc.address, amount, sender=nft_owner)
    vault_contract_pool_mayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    with boa.reverts():
        vault_contract_pool_mayc.staking_withdraw(nft_owner, amount + 1, token_id, sender=renting_contract.address)
    assert ape_staking_contract.staked_nfts(POOL_MAYC, token_id) == amount


def test_staking_claim_bayc(
    owner, nft_owner, vault_contract_pool_bayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(1e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_bayc, token_id, sender=nft_owner)
    vault_contract_pool_bayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_bayc.address, amount, sender=nft_owner)
    vault_contract_pool_bayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    nft_owner_ape = ape_contract.balanceOf(nft_owner)
    vault_contract_pool_bayc.staking_claim(nft_owner, token_id, sender=renting_contract.address)
    assert ape_staking_contract.staked_nfts(POOL_BAYC, token_id) == amount
    assert ape_contract.balanceOf(nft_owner) == nft_owner_ape + amount // 100


def test_staking_claim_bayc_other_recepient(
    owner, nft_owner, vault_contract_pool_bayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(1e18)
    token_id = 1
    recepient = boa.env.generate_address("recepient")

    nft_contract.approve(vault_contract_pool_bayc, token_id, sender=nft_owner)
    vault_contract_pool_bayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_bayc.address, amount, sender=nft_owner)
    vault_contract_pool_bayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    vault_contract_pool_bayc.staking_claim(recepient, token_id, sender=renting_contract.address)
    assert ape_staking_contract.staked_nfts(POOL_BAYC, token_id) == amount
    assert ape_contract.balanceOf(recepient) == amount // 100


def test_staking_claim_bayc_not_caller(
    owner, nft_owner, vault_contract_pool_bayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(1e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_bayc, token_id, sender=nft_owner)
    vault_contract_pool_bayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_bayc.address, amount, sender=nft_owner)
    vault_contract_pool_bayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    with boa.reverts("not caller"):
        vault_contract_pool_bayc.staking_claim(nft_owner, token_id, sender=nft_owner)
    assert ape_staking_contract.staked_nfts(POOL_BAYC, token_id) == amount


def test_staking_claim_mayc(
    owner, nft_owner, vault_contract_pool_mayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(1e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_mayc, token_id, sender=nft_owner)
    vault_contract_pool_mayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_mayc.address, amount, sender=nft_owner)
    vault_contract_pool_mayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    nft_owner_ape = ape_contract.balanceOf(nft_owner)
    vault_contract_pool_mayc.staking_claim(nft_owner, token_id, sender=renting_contract.address)
    assert ape_staking_contract.staked_nfts(POOL_MAYC, token_id) == amount
    assert ape_contract.balanceOf(nft_owner) == nft_owner_ape + amount // 100


def test_staking_claim_mayc_other_recepient(
    owner, nft_owner, vault_contract_pool_mayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(1e18)
    token_id = 1
    recepient = boa.env.generate_address("recepient")

    nft_contract.approve(vault_contract_pool_mayc, token_id, sender=nft_owner)
    vault_contract_pool_mayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_mayc.address, amount, sender=nft_owner)
    vault_contract_pool_mayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    vault_contract_pool_mayc.staking_claim(recepient, token_id, sender=renting_contract.address)
    assert ape_staking_contract.staked_nfts(POOL_MAYC, token_id) == amount
    assert ape_contract.balanceOf(recepient) == amount // 100


def test_staking_claim_mayc_not_caller(
    owner, nft_owner, vault_contract_pool_mayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(1e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_mayc, token_id, sender=nft_owner)
    vault_contract_pool_mayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_mayc.address, amount, sender=nft_owner)
    vault_contract_pool_mayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    with boa.reverts("not caller"):
        vault_contract_pool_mayc.staking_claim(nft_owner, token_id, sender=nft_owner)
    assert ape_staking_contract.staked_nfts(POOL_MAYC, token_id) == amount


def test_staking_compound_bayc(
    owner, nft_owner, vault_contract_pool_bayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(100e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_bayc, token_id, sender=nft_owner)
    vault_contract_pool_bayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_bayc.address, amount, sender=nft_owner)
    vault_contract_pool_bayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    vault_contract_pool_bayc.staking_compound(token_id, sender=renting_contract.address)
    assert ape_staking_contract.staked_nfts(POOL_BAYC, token_id) == int(amount * 1.01)


def test_staking_compound_bayc_withdrawn(
    owner, nft_owner, vault_contract_pool_bayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(100e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_bayc, token_id, sender=nft_owner)
    vault_contract_pool_bayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_bayc.address, amount, sender=nft_owner)
    vault_contract_pool_bayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    vault_contract_pool_bayc.withdraw(token_id, nft_owner, sender=renting_contract.address)

    with boa.reverts():
        vault_contract_pool_bayc.staking_compound(token_id, sender=renting_contract.address)
    assert ape_staking_contract.staked_nfts(POOL_BAYC, token_id) == amount


def test_staking_compound_bayc_not_caller(
    owner, nft_owner, vault_contract_pool_bayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(100e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_bayc, token_id, sender=nft_owner)
    vault_contract_pool_bayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_bayc.address, amount, sender=nft_owner)
    vault_contract_pool_bayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    with boa.reverts("not caller"):
        vault_contract_pool_bayc.staking_compound(token_id, sender=nft_owner)
    assert ape_staking_contract.staked_nfts(POOL_BAYC, token_id) == amount


def test_staking_compound_bayc_not_enough_staked(
    owner, nft_owner, vault_contract_pool_bayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(99e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_bayc, token_id, sender=nft_owner)
    vault_contract_pool_bayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_bayc.address, amount, sender=nft_owner)
    vault_contract_pool_bayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    with boa.reverts():
        vault_contract_pool_bayc.staking_compound(token_id, sender=renting_contract.address)
    assert ape_staking_contract.staked_nfts(POOL_BAYC, token_id) == amount


def test_staking_compound_mayc(
    owner, nft_owner, vault_contract_pool_mayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(100e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_mayc, token_id, sender=nft_owner)
    vault_contract_pool_mayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_mayc.address, amount, sender=nft_owner)
    vault_contract_pool_mayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    vault_contract_pool_mayc.staking_compound(token_id, sender=renting_contract.address)
    assert ape_staking_contract.staked_nfts(POOL_MAYC, token_id) == int(amount * 1.01)


def test_staking_compound_mayc_withdrawn(
    owner, nft_owner, vault_contract_pool_mayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(100e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_mayc, token_id, sender=nft_owner)
    vault_contract_pool_mayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_mayc.address, amount, sender=nft_owner)
    vault_contract_pool_mayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    vault_contract_pool_mayc.withdraw(token_id, nft_owner, sender=renting_contract.address)

    with boa.reverts():
        vault_contract_pool_mayc.staking_compound(token_id, sender=renting_contract.address)
    assert ape_staking_contract.staked_nfts(POOL_MAYC, token_id) == amount


def test_staking_compound_mayc_not_caller(
    owner, nft_owner, vault_contract_pool_mayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(100e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_mayc, token_id, sender=nft_owner)
    vault_contract_pool_mayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_mayc.address, amount, sender=nft_owner)
    vault_contract_pool_mayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    with boa.reverts("not caller"):
        vault_contract_pool_mayc.staking_compound(token_id, sender=nft_owner)
    assert ape_staking_contract.staked_nfts(POOL_MAYC, token_id) == amount


def test_staking_compound_mayc_not_enough_staked(
    owner, nft_owner, vault_contract_pool_mayc, renting_contract, ape_staking_contract, ape_contract, nft_contract
):
    amount = int(99e18)
    token_id = 1

    nft_contract.approve(vault_contract_pool_mayc, token_id, sender=nft_owner)
    vault_contract_pool_mayc.deposit(token_id, nft_owner, nft_owner, sender=renting_contract.address)

    ape_contract.transfer(vault_contract_pool_mayc.address, amount, sender=nft_owner)
    vault_contract_pool_mayc.staking_deposit(nft_owner, amount, token_id, sender=renting_contract.address)

    with boa.reverts():
        vault_contract_pool_mayc.staking_compound(token_id, sender=renting_contract.address)
    assert ape_staking_contract.staked_nfts(POOL_MAYC, token_id) == amount
