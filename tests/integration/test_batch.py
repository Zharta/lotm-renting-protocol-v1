import boa
import pytest

from ..conftest_base import (
    ZERO_ADDRESS,
    ZERO_BYTES32,
    Listing,
    Rental,
    RentalLog,
    RewardLog,
    StakingLog,
    TokenContext,
    TokenContextAndAmount,
    TokenContextAndListing,
    VaultLog,
    WithdrawalLog,
    compute_state_hash,
    get_last_event,
    sign_listing,
)


@pytest.fixture(scope="module")
def token_ids():
    # cherrypicked token ids not matching staked baycs or maycs
    return [
        0,
        1,
        2,
        5,
        7,
        8,
        12,
        14,
        15,
        16,
        17,
        22,
        23,
        25,
        29,
        30,
        35,
        38,
        41,
        45,
        49,
        52,
        53,
        54,
        55,
        65,
        67,
        73,
        74,
        78,
        79,
        84,
    ]


@pytest.fixture(autouse=True)
def tokens_config(
    token_ids, nft_owner, owner, renter, nft_contract, ape_contract, bayc_contract, mayc_contract, ape_staking_contract
):
    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        bayc_contract.transferFrom(
            bayc_contract.ownerOf(token_id), nft_owner, token_id, sender=bayc_contract.ownerOf(token_id)
        )
        mayc_contract.transferFrom(
            mayc_contract.ownerOf(token_id), nft_owner, token_id, sender=mayc_contract.ownerOf(token_id)
        )


def test_initial_state(
    vault_contract,
    renting_contract,
    nft_contract,
    ape_contract,
    delegation_registry_warm_contract,
    ape_staking_contract,
    renting_erc721_contract,
    protocol_wallet,
    protocol_fee,
    owner,
):
    assert renting_contract.vault_impl_addr() == vault_contract.address
    assert renting_contract.payment_token() == ape_contract.address
    assert renting_contract.nft_contract_addr() == nft_contract.address
    assert renting_contract.delegation_registry_addr() == delegation_registry_warm_contract.address
    assert renting_contract.staking_addr() == ape_staking_contract.address
    assert renting_contract.renting_erc721() == renting_erc721_contract.address
    assert renting_contract.max_protocol_fee() == protocol_fee
    assert renting_contract.protocol_fee() == protocol_fee
    assert renting_contract.protocol_wallet() == protocol_wallet
    assert renting_contract.protocol_admin() == owner


def test_initial_state_bayc(
    vault_contract_bayc,
    renting_contract_bayc,
    bayc_contract,
    ape_contract,
    delegation_registry_warm_contract,
    ape_staking_contract,
    renting_erc721_contract,
    protocol_wallet,
    protocol_fee,
    owner,
):
    assert renting_contract_bayc.vault_impl_addr() == vault_contract_bayc.address
    assert renting_contract_bayc.payment_token() == ape_contract.address
    assert renting_contract_bayc.nft_contract_addr() == bayc_contract.address
    assert renting_contract_bayc.delegation_registry_addr() == delegation_registry_warm_contract.address
    assert renting_contract_bayc.staking_addr() == ape_staking_contract.address
    assert renting_contract_bayc.renting_erc721() == renting_erc721_contract.address
    assert renting_contract_bayc.max_protocol_fee() == protocol_fee
    assert renting_contract_bayc.protocol_fee() == protocol_fee
    assert renting_contract_bayc.protocol_wallet() == protocol_wallet
    assert renting_contract_bayc.protocol_admin() == owner


def test_initial_state_mayc(
    vault_contract_mayc,
    renting_contract_mayc,
    mayc_contract,
    ape_contract,
    delegation_registry_warm_contract,
    ape_staking_contract,
    renting_erc721_contract,
    protocol_wallet,
    protocol_fee,
    owner,
):
    assert renting_contract_mayc.vault_impl_addr() == vault_contract_mayc.address
    assert renting_contract_mayc.payment_token() == ape_contract.address
    assert renting_contract_mayc.nft_contract_addr() == mayc_contract.address
    assert renting_contract_mayc.delegation_registry_addr() == delegation_registry_warm_contract.address
    assert renting_contract_mayc.staking_addr() == ape_staking_contract.address
    assert renting_contract_mayc.renting_erc721() == renting_erc721_contract.address
    assert renting_contract_mayc.max_protocol_fee() == protocol_fee
    assert renting_contract_mayc.protocol_fee() == protocol_fee
    assert renting_contract_mayc.protocol_wallet() == protocol_wallet
    assert renting_contract_mayc.protocol_admin() == owner


@pytest.mark.profile
def test_deposit_and_withdraw_batch(
    renting_contract, nft_contract, nft_owner, protocol_wallet, delegation_registry_warm_contract, owner, token_ids
):
    for token_id in token_ids:
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    # deposit
    renting_contract.deposit(token_ids, ZERO_ADDRESS, sender=nft_owner)
    event = get_last_event(renting_contract, "NftsDeposited")

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.delegate == ZERO_ADDRESS

    vault_log = VaultLog(*event.vaults[-1])
    assert vault_log.vault == vault_addr
    assert vault_log.token_id == token_id

    assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, Rental())
    assert nft_contract.ownerOf(token_id) == vault_addr
    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == ZERO_ADDRESS

    # withdraw
    renting_contract.withdraw(
        [TokenContext(token_id, nft_owner, Rental()).to_tuple() for token_id in token_ids], sender=nft_owner
    )

    event = get_last_event(renting_contract, "NftsWithdrawn")

    for token_id, withdrawal_log in zip(token_ids, event.withdrawals):
        withdrawal_log = WithdrawalLog(*withdrawal_log)
        assert withdrawal_log.vault == renting_contract.tokenid_to_vault(token_id)
        assert withdrawal_log.token_id == token_id

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.total_rewards == 0

    for token_id in token_ids:
        assert renting_contract.rental_states(token_id) == ZERO_BYTES32
        assert nft_contract.ownerOf(token_id) == nft_owner


@pytest.mark.profile
def test_start_and_close_rentals_batch(
    contracts_config,
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    owner,
    owner_key,
    protocol_wallet,
    protocol_fee,
    token_ids,
):
    token_id_qty = len(token_ids)
    min_duration = 0
    max_duration = 0

    token_id = 1
    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    duration = 10
    expiration = start_time + duration * 3600
    rental_amount = duration * price
    renter_delegate = boa.env.generate_address("delegate")

    for token_id in token_ids:
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    # deposit
    renting_contract.deposit(token_ids, nft_owner, sender=nft_owner)

    listings = [Listing(token_id, price, min_duration, max_duration, start_time) for token_id in token_ids]
    signed_listings = [
        sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address) for listing in listings
    ]
    token_contexts = [TokenContext(token_id, nft_owner, Rental()) for token_id in token_ids]

    ape_contract.approve(renting_contract, rental_amount * token_id_qty, sender=renter)

    assert ape_contract.balanceOf(renter) >= rental_amount * token_id_qty

    # start rentals

    renting_contract.start_rentals(
        [
            TokenContextAndListing(token_context, signed_listing, duration).to_tuple()
            for token_context, signed_listing in zip(token_contexts, signed_listings)
        ],
        renter_delegate,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")

    assert rental_started_event.renter == renter
    assert rental_started_event.delegate == renter_delegate
    assert rental_started_event.nft_contract == nft_contract.address
    assert len(rental_started_event.rentals) == token_id_qty

    for token_id, event_rental in zip(token_ids, rental_started_event.rentals):
        event_rental = RentalLog(*event_rental)
        print(f"{event_rental=}")
        assert event_rental.vault == renting_contract.tokenid_to_vault(token_id)
        assert event_rental.owner == nft_owner
        assert event_rental.token_id == token_id
        assert event_rental.start == start_time
        assert event_rental.min_expiration == min_expiration
        assert event_rental.expiration == expiration
        assert event_rental.amount == rental_amount
        assert event_rental.protocol_fee == protocol_fee

        rental = Rental(
            event_rental.id,
            nft_owner,
            renter,
            renter_delegate,
            token_id,
            start_time,
            min_expiration,
            expiration,
            rental_amount,
            protocol_fee,
        )
        assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, rental)

    started_rentals = [
        RentalLog(*rental).to_rental(renter=renter, delegate=renter_delegate) for rental in rental_started_event.rentals
    ]
    token_contexts = [TokenContext(token_id, nft_owner, rental) for token_id, rental in zip(token_ids, started_rentals)]

    real_duration = 3
    boa.env.time_travel(seconds=real_duration * 3600)

    # close rentals

    renting_contract.close_rentals([c.to_tuple() for c in token_contexts], sender=renter)

    for token_id in token_ids:
        assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, Rental())

    # withdraw

    renting_contract.withdraw(
        [TokenContext(token_id, nft_owner, Rental()).to_tuple() for token_id in token_ids], sender=nft_owner
    )


@pytest.mark.profile
def test_claim_batch(
    contracts_config,
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    owner,
    owner_key,
    protocol_wallet,
    protocol_fee,
    token_ids,
):
    token_id_qty = len(token_ids)
    min_duration = 0
    max_duration = 0

    token_id = 1
    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    for token_id in token_ids:
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    # deposit
    renting_contract.deposit(token_ids, nft_owner, sender=nft_owner)

    listings = [Listing(token_id, price, min_duration, max_duration, start_time) for token_id in token_ids]
    signed_listings = [
        sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address) for listing in listings
    ]
    token_contexts = [TokenContext(token_id, nft_owner, Rental()) for token_id in token_ids]

    ape_contract.approve(renting_contract, rental_amount * token_id_qty, sender=renter)

    assert ape_contract.balanceOf(renter) >= rental_amount * token_id_qty

    # start rentals

    renting_contract.start_rentals(
        [
            TokenContextAndListing(token_context, signed_listing, duration).to_tuple()
            for token_context, signed_listing in zip(token_contexts, signed_listings)
        ],
        ZERO_ADDRESS,
        start_time,
        sender=renter,
    )

    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rentals = [RentalLog(*rental).to_rental(renter=renter) for rental in rental_started_event.rentals]
    token_contexts = [TokenContext(token_id, nft_owner, rental) for token_id, rental in zip(token_ids, started_rentals)]

    boa.env.time_travel(duration * 3600 + 1)

    total_fees = rental_amount * token_id_qty * protocol_fee // 10000
    total_rewards = rental_amount * token_id_qty - total_fees
    nft_owner_balance = ape_contract.balanceOf(nft_owner)
    protocol_wallet_balance = ape_contract.balanceOf(protocol_wallet)

    renting_contract.claim([c.to_tuple() for c in token_contexts], sender=nft_owner)

    claim_event = get_last_event(renting_contract, "RewardsClaimed")
    assert claim_event.owner == nft_owner
    assert claim_event.amount == total_rewards
    assert claim_event.protocol_fee_amount == total_fees
    assert len(claim_event.rewards) == token_id_qty

    for token_id, reward in zip(token_ids, claim_event.rewards):
        reward = RewardLog(*reward)
        assert reward.token_id == token_id
        assert reward.active_rental_amount == 0

    assert renting_contract.eval(f"self.unclaimed_rewards[{nft_owner}]") == 0
    assert renting_contract.eval("self.protocol_fees_amount") == total_fees

    assert ape_contract.balanceOf(nft_owner) == nft_owner_balance + total_rewards
    assert ape_contract.balanceOf(protocol_wallet) == protocol_wallet_balance


@pytest.mark.profile
def test_stake_deposit_and_withdraw_batch(
    contracts_config,
    renting_contract_bayc,
    nft_owner,
    renter,
    bayc_contract,
    ape_contract,
    owner,
    ape_staking_contract,
    token_ids,
):
    token_id_qty = len(token_ids)
    vault_addrs = [renting_contract_bayc.tokenid_to_vault(token_id) for token_id in token_ids]
    pool_id = 1
    nft_owner_balance = ape_contract.balanceOf(nft_owner)
    ape_staking_balance = ape_contract.balanceOf(ape_staking_contract)

    for token_id in token_ids:
        vault_addr = renting_contract_bayc.tokenid_to_vault(token_id)
        bayc_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract_bayc.deposit(token_ids, ZERO_ADDRESS, sender=nft_owner)
    amounts = [int(1e18) for _ in range(token_id_qty)]
    ape_contract.approve(renting_contract_bayc, sum(amounts), sender=nft_owner)
    assert nft_owner_balance >= sum(amounts)

    renting_contract_bayc.stake_deposit(
        [
            TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), amount).to_tuple()
            for token_id, amount in zip(token_ids, amounts)
        ],
        sender=nft_owner,
    )
    deposit_nft_event = get_last_event(renting_contract_bayc, "DepositNft")
    print(f"{deposit_nft_event=}")
    deposit_event = get_last_event(renting_contract_bayc, "StakingDeposit")
    assert deposit_event.owner == nft_owner
    assert deposit_event.nft_contract == bayc_contract.address
    assert len(deposit_event.tokens) == token_id_qty

    for token_id, amount, staking_log in zip(token_ids, amounts, deposit_event.tokens):
        staking_log = StakingLog(*staking_log)
        assert staking_log.token_id == token_id
        assert staking_log.amount == amount

    for token_id, amount, vault_addr in zip(token_ids, amounts, vault_addrs):
        assert ape_staking_contract.nftPosition(pool_id, token_id)[0] == amount
        assert ape_contract.balanceOf(vault_addr) == 0
        assert bayc_contract.ownerOf(token_id) == vault_addr

    assert ape_contract.balanceOf(ape_staking_contract) == ape_staking_balance + sum(amounts)

    renting_contract_bayc.stake_withdraw(
        [
            TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), amount).to_tuple()
            for token_id, amount in zip(token_ids, amounts)
        ],
        nft_owner,
        sender=nft_owner,
    )

    assert ape_contract.balanceOf(nft_owner) == nft_owner_balance
    for token_id, vault_addr in zip(token_ids, vault_addrs):
        assert ape_staking_contract.nftPosition(pool_id, token_id) == (0, 0)
        assert ape_contract.balanceOf(vault_addr) == 0
        assert bayc_contract.ownerOf(token_id) == vault_addr


@pytest.mark.profile
def test_stake_claim_batch(
    contracts_config,
    renting_contract_bayc,
    nft_owner,
    renter,
    bayc_contract,
    ape_contract,
    owner,
    ape_staking_contract,
    token_ids,
):
    token_id_qty = len(token_ids)
    vault_addrs = [renting_contract_bayc.tokenid_to_vault(token_id) for token_id in token_ids]
    pool_id = 1
    nft_owner_balance = ape_contract.balanceOf(nft_owner)
    ape_staking_balance = ape_contract.balanceOf(ape_staking_contract)
    staking_duration = 7 * 24 * 3600

    for token_id in token_ids:
        vault_addr = renting_contract_bayc.tokenid_to_vault(token_id)
        bayc_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract_bayc.deposit(token_ids, ZERO_ADDRESS, sender=nft_owner)
    amounts = [int(1e18) for _ in range(token_id_qty)]
    ape_contract.approve(renting_contract_bayc, sum(amounts), sender=nft_owner)
    assert nft_owner_balance >= sum(amounts)

    renting_contract_bayc.stake_deposit(
        [
            TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), amount).to_tuple()
            for token_id, amount in zip(token_ids, amounts)
        ],
        sender=nft_owner,
    )

    boa.env.time_travel(seconds=staking_duration)

    claimable_amounts = [ape_staking_contract.pendingRewards(pool_id, ZERO_ADDRESS, token_id) for token_id in token_ids]

    for token_id, amount, vault_addr in zip(token_ids, amounts, vault_addrs):
        assert ape_staking_contract.nftPosition(pool_id, token_id)[0] == amount
        assert ape_contract.balanceOf(vault_addr) == 0
        assert bayc_contract.ownerOf(token_id) == vault_addr

    renting_contract_bayc.stake_claim(
        [TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), 0).to_tuple() for token_id in token_ids],
        nft_owner,
        sender=nft_owner,
    )

    assert sum(claimable_amounts) > 0
    assert ape_contract.balanceOf(ape_staking_contract) == ape_staking_balance + sum(amounts) - sum(claimable_amounts)
    for token_id, vault_addr, amount in zip(token_ids, vault_addrs, amounts):
        assert ape_staking_contract.nftPosition(pool_id, token_id)[0] == amount
        assert ape_contract.balanceOf(vault_addr) == 0
        assert bayc_contract.ownerOf(token_id) == vault_addr


@pytest.mark.profile
def test_stake_claim_compound(
    contracts_config,
    renting_contract_bayc,
    nft_owner,
    renter,
    bayc_contract,
    ape_contract,
    owner,
    ape_staking_contract,
    token_ids,
):
    token_id_qty = len(token_ids)
    vault_addrs = [renting_contract_bayc.tokenid_to_vault(token_id) for token_id in token_ids]
    pool_id = 1
    nft_owner_balance = ape_contract.balanceOf(nft_owner)
    ape_staking_balance = ape_contract.balanceOf(ape_staking_contract)
    staking_duration = 90 * 24 * 3600

    for token_id in token_ids:
        vault_addr = renting_contract_bayc.tokenid_to_vault(token_id)
        bayc_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract_bayc.deposit(token_ids, ZERO_ADDRESS, sender=nft_owner)
    amounts = [int(10e18) for _ in range(token_id_qty)]
    ape_contract.approve(renting_contract_bayc, sum(amounts), sender=nft_owner)
    assert nft_owner_balance >= sum(amounts)

    renting_contract_bayc.stake_deposit(
        [
            TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), amount).to_tuple()
            for token_id, amount in zip(token_ids, amounts)
        ],
        sender=nft_owner,
    )

    boa.env.time_travel(seconds=staking_duration)

    claimable_amounts = [ape_staking_contract.pendingRewards(pool_id, ZERO_ADDRESS, token_id) for token_id in token_ids]
    for claimable_amount in claimable_amounts:
        assert claimable_amount > int(1e18)

    for token_id, amount, vault_addr in zip(token_ids, amounts, vault_addrs):
        assert ape_staking_contract.nftPosition(pool_id, token_id)[0] == amount
        assert ape_contract.balanceOf(vault_addr) == 0
        assert bayc_contract.ownerOf(token_id) == vault_addr

    renting_contract_bayc.stake_compound(
        [TokenContextAndAmount(TokenContext(token_id, nft_owner, Rental()), 0).to_tuple() for token_id in token_ids],
        sender=nft_owner,
    )

    assert sum(claimable_amounts) > 0
    assert ape_contract.balanceOf(ape_staking_contract) == ape_staking_balance + sum(amounts)
    for token_id, vault_addr, amount, reward in zip(token_ids, vault_addrs, amounts, claimable_amounts):
        assert ape_staking_contract.nftPosition(pool_id, token_id)[0] == amount + reward
        assert ape_contract.balanceOf(vault_addr) == 0
        assert bayc_contract.ownerOf(token_id) == vault_addr
