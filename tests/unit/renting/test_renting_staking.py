from dataclasses import replace

import boa
import pytest

from ...conftest_base import (
    ZERO_ADDRESS,
    Rental,
    StakingLog,
    TokenContext,
    TokenContextAndAmount,
    get_last_event,
)

FOREVER = 2**256 - 1
PROTOCOL_FEE = 500


@pytest.fixture(scope="module")
def ape_staking_contract(ape_staking_contract_def, nft_contract, ape_contract):
    return ape_staking_contract_def.deploy(ape_contract, nft_contract, nft_contract)


@pytest.fixture(scope="module")
def vault_contract(vault_contract_def, ape_contract, nft_contract, delegation_registry_warm_contract, ape_staking_contract):
    return vault_contract_def.deploy(ape_contract, nft_contract, delegation_registry_warm_contract, ape_staking_contract)


@pytest.fixture(scope="module")
def renting_contract(
    renting_contract_def,
    renting721_contract,
    vault_contract,
    ape_contract,
    nft_contract,
    delegation_registry_warm_contract,
    ape_staking_contract,
    protocol_wallet,
    owner,
):
    return renting_contract_def.deploy(
        vault_contract,
        ape_contract,
        nft_contract,
        delegation_registry_warm_contract,
        renting721_contract,
        ape_staking_contract,
        1,
        PROTOCOL_FEE,
        PROTOCOL_FEE,
        protocol_wallet,
        owner,
    )


@pytest.fixture(scope="module")
def renting_contract_no_staking(
    renting_contract_def,
    renting_erc721_contract_def,
    vault_contract_def,
    ape_contract,
    nft_contract,
    delegation_registry_warm_contract,
    protocol_wallet,
    owner,
):
    return renting_contract_def.deploy(
        vault_contract_def.deploy(ape_contract, nft_contract, delegation_registry_warm_contract, ZERO_ADDRESS),
        ape_contract,
        nft_contract,
        delegation_registry_warm_contract,
        renting_erc721_contract_def.deploy(),
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
        ape_contract.mint(nft_owner, int(10000 * 1e18), sender=owner)
        yield


def get_rewards(amount):
    return amount // 100


def test_stake_deposit(
    renting_contract, nft_owner, renter, nft_contract, ape_contract, owner, ape_staking_contract, vault_contract_def
):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    token_context = TokenContext(token_id, nft_owner, Rental())
    pool_id = renting_contract.staking_pool_id()

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    amount = int(1e18)
    ape_contract.approve(renting_contract, amount, sender=nft_owner)

    renting_contract.stake_deposit([TokenContextAndAmount(token_context, amount).to_tuple()], sender=nft_owner)

    assert vault_contract_def.at(vault_addr).staking_pool_id() == pool_id
    assert vault_contract_def.at(vault_addr).staking_addr() == ape_staking_contract.address
    assert ape_staking_contract.staked_nfts(pool_id, token_id) == amount
    assert ape_contract.balanceOf(ape_staking_contract) == amount
    assert ape_contract.balanceOf(vault_addr) == 0
    assert nft_contract.ownerOf(token_id) == vault_addr


def test_stake_deposit_batch(
    renting_contract, nft_owner, renter, nft_contract, ape_contract, owner, ape_staking_contract, vault_contract_def
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]
    vault_addrs = [renting_contract.tokenid_to_vault(token_id) for token_id in token_ids]
    pool_id = renting_contract.staking_pool_id()

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    amounts = [int(1e18) for _ in range(token_id_qty)]
    ape_contract.approve(renting_contract, sum(amounts), sender=nft_owner)

    renting_contract.stake_deposit(
        [
            TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), amount).to_tuple()
            for token_id, amount in zip(token_ids, amounts)
        ],
        sender=nft_owner,
    )

    for token_id, amount, vault_addr in zip(token_ids, amounts, vault_addrs):
        assert vault_contract_def.at(vault_addr).staking_pool_id() == pool_id
        assert vault_contract_def.at(vault_addr).staking_addr() == ape_staking_contract.address
        assert ape_staking_contract.staked_nfts(pool_id, token_id) == amount
        assert ape_contract.balanceOf(vault_addr) == 0
        assert nft_contract.ownerOf(token_id) == vault_addr
    assert ape_contract.balanceOf(ape_staking_contract) == sum(amounts)


def test_staking_deposit_logs_staking_deposit(
    renting_contract, nft_owner, renter, nft_contract, ape_contract, owner, ape_staking_contract, vault_contract_def
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    amounts = [int(1e18) for _ in range(token_id_qty)]
    ape_contract.approve(renting_contract, sum(amounts), sender=nft_owner)

    renting_contract.stake_deposit(
        [
            TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), amount).to_tuple()
            for token_id, amount in zip(token_ids, amounts)
        ],
        sender=nft_owner,
    )

    deposit_event = get_last_event(renting_contract, "StakingDeposit")
    assert deposit_event.owner == nft_owner
    assert deposit_event.nft_contract == nft_contract.address
    assert len(deposit_event.tokens) == token_id_qty

    for token_id, amount, staking_log in zip(token_ids, amounts, deposit_event.tokens):
        staking_log = StakingLog(*staking_log)
        assert staking_log.token_id == token_id
        assert staking_log.amount == amount


def test_stake_deposit_reverts_if_invalid_context(renting_contract, nft_owner, renter, nft_contract, ape_contract, owner):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    invalid_contexts = [
        TokenContext(0, nft_owner, Rental()),
        TokenContext(token_id, nft_owner, Rental(id=b"01")),
        TokenContext(token_id, nft_owner, Rental(owner=nft_owner)),
        TokenContext(token_id, nft_owner, Rental(renter=nft_owner)),
        TokenContext(token_id, nft_owner, Rental(token_id=1)),
        TokenContext(token_id, nft_owner, Rental(start=1)),
        TokenContext(token_id, nft_owner, Rental(min_expiration=1)),
        TokenContext(token_id, nft_owner, Rental(expiration=1)),
        TokenContext(token_id, nft_owner, Rental(amount=1)),
        TokenContext(token_id, nft_owner, Rental(protocol_fee=1)),
        TokenContext(token_id, nft_owner, Rental(delegate=nft_owner)),
    ]

    for invalid_context in invalid_contexts:
        print(f"invalid_context: {invalid_context}")
        with boa.reverts("invalid context"):
            renting_contract.stake_deposit([TokenContextAndAmount(invalid_context, 1).to_tuple()], sender=nft_owner)


def test_stake_deposit_reverts_if_not_owner(renting_contract, nft_owner, renter, nft_contract, ape_contract, owner):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    token_context = TokenContext(token_id, owner, Rental())

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    with boa.reverts("not owner"):
        renting_contract.stake_deposit([TokenContextAndAmount(token_context, 1).to_tuple()], sender=nft_owner)


def test_stake_deposit_reverts_if_insufficient_allowance(
    renting_contract, nft_owner, renter, nft_contract, ape_contract, owner
):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    token_context = TokenContext(token_id, nft_owner, Rental())
    amount = int(1e18)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)
    ape_contract.approve(renting_contract, amount - 1, sender=nft_owner)

    with boa.reverts("insufficient allowance"):
        renting_contract.stake_deposit([TokenContextAndAmount(token_context, amount).to_tuple()], sender=nft_owner)


def test_staking_deposit_reverts_if_staking_disabled(
    renting_contract_no_staking, nft_owner, renter, nft_contract, ape_contract, owner
):
    token_id = 1
    vault_addr = renting_contract_no_staking.tokenid_to_vault(token_id)
    token_context = TokenContext(token_id, nft_owner, Rental())

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract_no_staking.deposit([token_id], nft_owner, sender=nft_owner)

    with boa.reverts("staking not supported"):
        renting_contract_no_staking.stake_deposit([TokenContextAndAmount(token_context, 1).to_tuple()], sender=nft_owner)


def test_stake_withdraw(
    renting_contract, nft_owner, renter, nft_contract, ape_contract, owner, ape_staking_contract, vault_contract_def
):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    token_context = TokenContext(token_id, nft_owner, Rental())
    pool_id = renting_contract.staking_pool_id()
    nft_owner_balance = ape_contract.balanceOf(nft_owner)
    amount = int(1e18)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    ape_contract.approve(renting_contract, amount, sender=nft_owner)
    renting_contract.stake_deposit([TokenContextAndAmount(token_context, amount).to_tuple()], sender=nft_owner)

    renting_contract.stake_withdraw([TokenContextAndAmount(token_context, amount).to_tuple()], nft_owner, sender=nft_owner)

    assert ape_staking_contract.staked_nfts(pool_id, token_id) == 0
    assert ape_contract.balanceOf(ape_staking_contract) == 0
    assert ape_contract.balanceOf(nft_owner) == nft_owner_balance
    assert nft_contract.ownerOf(token_id) == vault_addr


def test_stake_withdraw_batch(
    renting_contract, nft_owner, renter, nft_contract, ape_contract, owner, ape_staking_contract, vault_contract_def
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]
    vault_addrs = [renting_contract.tokenid_to_vault(token_id) for token_id in token_ids]
    pool_id = renting_contract.staking_pool_id()
    nft_owner_balance = ape_contract.balanceOf(nft_owner)

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    amounts = [int(1e18) for _ in range(token_id_qty)]
    ape_contract.approve(renting_contract, sum(amounts), sender=nft_owner)

    renting_contract.stake_deposit(
        [
            TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), amount).to_tuple()
            for token_id, amount in zip(token_ids, amounts)
        ],
        sender=nft_owner,
    )

    renting_contract.stake_withdraw(
        [
            TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), amount).to_tuple()
            for token_id, amount in zip(token_ids, amounts)
        ],
        nft_owner,
        sender=nft_owner,
    )

    assert ape_contract.balanceOf(nft_owner) == nft_owner_balance
    for token_id, vault_addr in zip(token_ids, vault_addrs):
        assert ape_staking_contract.staked_nfts(pool_id, token_id) == 0
        assert ape_contract.balanceOf(vault_addr) == 0
        assert nft_contract.ownerOf(token_id) == vault_addr


def test_staking_withdraw_logs_staking_withdraw(
    renting_contract, nft_owner, renter, nft_contract, ape_contract, owner, ape_staking_contract, vault_contract_def
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    amounts = [int(1e18) for _ in range(token_id_qty)]
    ape_contract.approve(renting_contract, sum(amounts), sender=nft_owner)

    renting_contract.stake_deposit(
        [
            TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), amount).to_tuple()
            for token_id, amount in zip(token_ids, amounts)
        ],
        sender=nft_owner,
    )

    renting_contract.stake_withdraw(
        [
            TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), amount).to_tuple()
            for token_id, amount in zip(token_ids, amounts)
        ],
        nft_owner,
        sender=nft_owner,
    )

    withdraw_event = get_last_event(renting_contract, "StakingWithdraw")
    assert withdraw_event.owner == nft_owner
    assert withdraw_event.nft_contract == nft_contract.address
    assert withdraw_event.recipient == nft_owner
    assert len(withdraw_event.tokens) == token_id_qty

    for token_id, amount, staking_log in zip(token_ids, amounts, withdraw_event.tokens):
        staking_log = StakingLog(*staking_log)
        assert staking_log.token_id == token_id
        assert staking_log.amount == amount


def test_stake_withdraw_reverts_if_invalid_context(renting_contract, nft_owner, renter, nft_contract, ape_contract, owner):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    token_context = TokenContext(token_id, nft_owner, Rental())
    amount = int(1e18)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    ape_contract.approve(renting_contract, amount, sender=nft_owner)
    renting_contract.stake_deposit([TokenContextAndAmount(token_context, amount).to_tuple()], sender=nft_owner)

    invalid_contexts = [
        TokenContext(0, nft_owner, Rental()),
        TokenContext(token_id, nft_owner, Rental(id=b"01")),
        TokenContext(token_id, nft_owner, Rental(owner=nft_owner)),
        TokenContext(token_id, nft_owner, Rental(renter=nft_owner)),
        TokenContext(token_id, nft_owner, Rental(token_id=1)),
        TokenContext(token_id, nft_owner, Rental(start=1)),
        TokenContext(token_id, nft_owner, Rental(min_expiration=1)),
        TokenContext(token_id, nft_owner, Rental(expiration=1)),
        TokenContext(token_id, nft_owner, Rental(amount=1)),
        TokenContext(token_id, nft_owner, Rental(protocol_fee=1)),
        TokenContext(token_id, nft_owner, Rental(delegate=nft_owner)),
    ]

    for invalid_context in invalid_contexts:
        with boa.reverts("invalid context"):
            renting_contract.stake_withdraw(
                [TokenContextAndAmount(invalid_context, 1).to_tuple()], nft_owner, sender=nft_owner
            )


def test_stake_withdraw_reverts_if_not_owner(renting_contract, nft_owner, renter, nft_contract, ape_contract, owner):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    token_context = TokenContext(token_id, nft_owner, Rental())
    amount = int(1e18)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    ape_contract.approve(renting_contract, amount, sender=nft_owner)
    renting_contract.stake_deposit([TokenContextAndAmount(token_context, amount).to_tuple()], sender=nft_owner)

    with boa.reverts("not owner"):
        renting_contract.stake_withdraw(
            [TokenContextAndAmount(replace(token_context, nft_owner=owner), amount).to_tuple()], nft_owner, sender=nft_owner
        )


def test_stake_withdraw_reverts_if_amount_exceeds_balance(
    renting_contract, nft_owner, renter, nft_contract, ape_contract, owner
):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    token_context = TokenContext(token_id, nft_owner, Rental())
    amount = int(1e18)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    ape_contract.approve(renting_contract, amount, sender=nft_owner)
    renting_contract.stake_deposit([TokenContextAndAmount(token_context, amount).to_tuple()], sender=nft_owner)

    with boa.reverts("not enough staked"):
        renting_contract.stake_withdraw(
            [TokenContextAndAmount(token_context, amount + 1).to_tuple()], nft_owner, sender=nft_owner
        )


def test_stake_claim(
    renting_contract, nft_owner, renter, nft_contract, ape_contract, owner, ape_staking_contract, vault_contract_def
):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    token_context = TokenContext(token_id, nft_owner, Rental())
    pool_id = renting_contract.staking_pool_id()
    nft_owner_balance = ape_contract.balanceOf(nft_owner)
    amount = int(1e18)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    ape_contract.approve(renting_contract, amount, sender=nft_owner)
    renting_contract.stake_deposit([TokenContextAndAmount(token_context, amount).to_tuple()], sender=nft_owner)

    renting_contract.stake_claim([TokenContextAndAmount(token_context, amount).to_tuple()], nft_owner, sender=nft_owner)

    assert ape_staking_contract.staked_nfts(pool_id, token_id) == amount
    assert ape_contract.balanceOf(ape_staking_contract) == amount - get_rewards(amount)
    assert ape_contract.balanceOf(nft_owner) == nft_owner_balance - amount + get_rewards(amount)
    assert nft_contract.ownerOf(token_id) == vault_addr


def test_stake_claim_batch(
    renting_contract, nft_owner, renter, nft_contract, ape_contract, owner, ape_staking_contract, vault_contract_def
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]
    vault_addrs = [renting_contract.tokenid_to_vault(token_id) for token_id in token_ids]
    pool_id = renting_contract.staking_pool_id()
    nft_owner_balance = ape_contract.balanceOf(nft_owner)

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    amounts = [int(1e18) for _ in range(token_id_qty)]
    ape_contract.approve(renting_contract, sum(amounts), sender=nft_owner)

    renting_contract.stake_deposit(
        [
            TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), amount).to_tuple()
            for token_id, amount in zip(token_ids, amounts)
        ],
        sender=nft_owner,
    )

    renting_contract.stake_claim(
        [
            TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), amount).to_tuple()
            for token_id, amount in zip(token_ids, amounts)
        ],
        nft_owner,
        sender=nft_owner,
    )

    rewards = [get_rewards(amount) for amount in amounts]
    assert ape_contract.balanceOf(nft_owner) == nft_owner_balance - sum(amounts) + sum(rewards)
    for token_id, vault_addr, amount in zip(token_ids, vault_addrs, amounts):
        assert ape_staking_contract.staked_nfts(pool_id, token_id) == amount
        assert ape_contract.balanceOf(vault_addr) == 0
        assert nft_contract.ownerOf(token_id) == vault_addr


def test_staking_claim_logs_staking_claim(
    renting_contract, nft_owner, renter, nft_contract, ape_contract, owner, ape_staking_contract, vault_contract_def
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    amounts = [int(1e18) for _ in range(token_id_qty)]
    ape_contract.approve(renting_contract, sum(amounts), sender=nft_owner)

    renting_contract.stake_deposit(
        [
            TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), amount).to_tuple()
            for token_id, amount in zip(token_ids, amounts)
        ],
        sender=nft_owner,
    )

    renting_contract.stake_claim(
        [
            TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), amount).to_tuple()
            for token_id, amount in zip(token_ids, amounts)
        ],
        nft_owner,
        sender=nft_owner,
    )

    claim_event = get_last_event(renting_contract, "StakingClaim")
    assert claim_event.owner == nft_owner
    assert claim_event.nft_contract == nft_contract.address
    assert claim_event.recipient == nft_owner
    assert len(claim_event.tokens) == token_id_qty

    for token_id, staking_log_token_id in zip(token_ids, claim_event.tokens):
        assert staking_log_token_id == token_id


def test_stake_claim_reverts_if_invalid_context(renting_contract, nft_owner, renter, nft_contract, ape_contract, owner):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    token_context = TokenContext(token_id, nft_owner, Rental())
    amount = int(1e18)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    ape_contract.approve(renting_contract, amount, sender=nft_owner)
    renting_contract.stake_deposit([TokenContextAndAmount(token_context, amount).to_tuple()], sender=nft_owner)

    invalid_contexts = [
        TokenContext(0, nft_owner, Rental()),
        TokenContext(token_id, nft_owner, Rental(id=b"01")),
        TokenContext(token_id, nft_owner, Rental(owner=nft_owner)),
        TokenContext(token_id, nft_owner, Rental(renter=nft_owner)),
        TokenContext(token_id, nft_owner, Rental(token_id=1)),
        TokenContext(token_id, nft_owner, Rental(start=1)),
        TokenContext(token_id, nft_owner, Rental(min_expiration=1)),
        TokenContext(token_id, nft_owner, Rental(expiration=1)),
        TokenContext(token_id, nft_owner, Rental(amount=1)),
        TokenContext(token_id, nft_owner, Rental(protocol_fee=1)),
        TokenContext(token_id, nft_owner, Rental(delegate=nft_owner)),
    ]

    for invalid_context in invalid_contexts:
        with boa.reverts("invalid context"):
            renting_contract.stake_claim([TokenContextAndAmount(invalid_context, 1).to_tuple()], nft_owner, sender=nft_owner)


def test_stake_claim_reverts_if_not_owner(renting_contract, nft_owner, renter, nft_contract, ape_contract, owner):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    token_context = TokenContext(token_id, nft_owner, Rental())
    amount = int(1e18)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    ape_contract.approve(renting_contract, amount, sender=nft_owner)
    renting_contract.stake_deposit([TokenContextAndAmount(token_context, amount).to_tuple()], sender=nft_owner)

    with boa.reverts("not owner"):
        renting_contract.stake_claim(
            [TokenContextAndAmount(replace(token_context, nft_owner=owner), amount).to_tuple()], nft_owner, sender=nft_owner
        )


def test_stake_compound(
    renting_contract, nft_owner, renter, nft_contract, ape_contract, owner, ape_staking_contract, vault_contract_def
):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    token_context = TokenContext(token_id, nft_owner, Rental())
    pool_id = renting_contract.staking_pool_id()
    nft_owner_balance = ape_contract.balanceOf(nft_owner)
    amount = int(100e18)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    ape_contract.approve(renting_contract, amount, sender=nft_owner)
    renting_contract.stake_deposit([TokenContextAndAmount(token_context, amount).to_tuple()], sender=nft_owner)

    renting_contract.stake_compound([TokenContextAndAmount(token_context, amount).to_tuple()], sender=nft_owner)

    assert ape_staking_contract.staked_nfts(pool_id, token_id) == amount + get_rewards(amount)
    assert ape_contract.balanceOf(ape_staking_contract) == amount
    assert ape_contract.balanceOf(nft_owner) == nft_owner_balance - amount
    assert nft_contract.ownerOf(token_id) == vault_addr


def test_stake_compound_batch(
    renting_contract, nft_owner, renter, nft_contract, ape_contract, owner, ape_staking_contract, vault_contract_def
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]
    vault_addrs = [renting_contract.tokenid_to_vault(token_id) for token_id in token_ids]
    pool_id = renting_contract.staking_pool_id()
    nft_owner_balance = ape_contract.balanceOf(nft_owner)

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    amounts = [int(100e18) for _ in range(token_id_qty)]
    ape_contract.approve(renting_contract, sum(amounts), sender=nft_owner)

    renting_contract.stake_deposit(
        [
            TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), amount).to_tuple()
            for token_id, amount in zip(token_ids, amounts)
        ],
        sender=nft_owner,
    )

    renting_contract.stake_compound(
        [
            TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), amount).to_tuple()
            for token_id, amount in zip(token_ids, amounts)
        ],
        sender=nft_owner,
    )

    rewards = [get_rewards(amount) for amount in amounts]
    assert ape_contract.balanceOf(nft_owner) == nft_owner_balance - sum(amounts)
    for token_id, vault_addr, amount, rewards in zip(token_ids, vault_addrs, amounts, rewards):
        assert ape_staking_contract.staked_nfts(pool_id, token_id) == amount + rewards
        assert ape_contract.balanceOf(vault_addr) == 0
        assert nft_contract.ownerOf(token_id) == vault_addr


def test_staking_compound_logs_staking_compound(
    renting_contract, nft_owner, renter, nft_contract, ape_contract, owner, ape_staking_contract, vault_contract_def
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    amounts = [int(100e18) for _ in range(token_id_qty)]
    ape_contract.approve(renting_contract, sum(amounts), sender=nft_owner)

    renting_contract.stake_deposit(
        [
            TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), amount).to_tuple()
            for token_id, amount in zip(token_ids, amounts)
        ],
        sender=nft_owner,
    )

    renting_contract.stake_compound(
        [
            TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), amount).to_tuple()
            for token_id, amount in zip(token_ids, amounts)
        ],
        sender=nft_owner,
    )

    compound_event = get_last_event(renting_contract, "StakingCompound")
    assert compound_event.owner == nft_owner
    assert compound_event.nft_contract == nft_contract.address
    assert len(compound_event.tokens) == token_id_qty

    for token_id, staking_log_token_id in zip(token_ids, compound_event.tokens):
        assert staking_log_token_id == token_id


def test_stake_compound_reverts_if_invalid_context(renting_contract, nft_owner, renter, nft_contract, ape_contract, owner):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    token_context = TokenContext(token_id, nft_owner, Rental())
    amount = int(1e18)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    ape_contract.approve(renting_contract, amount, sender=nft_owner)
    renting_contract.stake_deposit([TokenContextAndAmount(token_context, amount).to_tuple()], sender=nft_owner)

    invalid_contexts = [
        TokenContext(0, nft_owner, Rental()),
        TokenContext(token_id, nft_owner, Rental(id=b"01")),
        TokenContext(token_id, nft_owner, Rental(owner=nft_owner)),
        TokenContext(token_id, nft_owner, Rental(renter=nft_owner)),
        TokenContext(token_id, nft_owner, Rental(token_id=1)),
        TokenContext(token_id, nft_owner, Rental(start=1)),
        TokenContext(token_id, nft_owner, Rental(min_expiration=1)),
        TokenContext(token_id, nft_owner, Rental(expiration=1)),
        TokenContext(token_id, nft_owner, Rental(amount=1)),
        TokenContext(token_id, nft_owner, Rental(protocol_fee=1)),
        TokenContext(token_id, nft_owner, Rental(delegate=nft_owner)),
    ]

    for invalid_context in invalid_contexts:
        with boa.reverts("invalid context"):
            renting_contract.stake_compound([TokenContextAndAmount(invalid_context, 1).to_tuple()], sender=nft_owner)


def test_stake_compound_reverts_if_not_owner(renting_contract, nft_owner, renter, nft_contract, ape_contract, owner):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    token_context = TokenContext(token_id, nft_owner, Rental())
    amount = int(1e18)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    ape_contract.approve(renting_contract, amount, sender=nft_owner)
    renting_contract.stake_deposit([TokenContextAndAmount(token_context, amount).to_tuple()], sender=nft_owner)

    with boa.reverts("not owner"):
        renting_contract.stake_compound(
            [TokenContextAndAmount(replace(token_context, nft_owner=owner), amount).to_tuple()], sender=nft_owner
        )
