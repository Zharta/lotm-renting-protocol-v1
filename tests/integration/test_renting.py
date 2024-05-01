from dataclasses import replace

import boa
import pytest

from ..conftest_base import (
    ZERO_ADDRESS,
    ZERO_BYTES32,
    Listing,
    Rental,
    RentalExtensionLog,
    RentalLog,
    RewardLog,
    TokenContext,
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
    return [0, 1, 2]


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


def test_deposit(
    contracts_config, renting_contract, nft_contract, nft_owner, vault_contract, delegation_registry_warm_contract
):
    token_id = 1

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)
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


def test_withdraw(contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter, protocol_fee):
    token_id = 1

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    renting_contract.withdraw([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=nft_owner)

    event = get_last_event(renting_contract, "NftsWithdrawn")

    withdrawal_log = WithdrawalLog(*event.withdrawals[0])
    assert withdrawal_log.vault == renting_contract.tokenid_to_vault(token_id)
    assert withdrawal_log.token_id == token_id

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.total_rewards == 0

    assert renting_contract.rental_states(token_id) == ZERO_BYTES32
    assert nft_contract.ownerOf(token_id) == nft_owner


def test_start_rental(
    contracts_config,
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    renter,
    protocol_wallet,
    protocol_fee,
    nft_owner_key,
    owner_key,
):
    token_id = 1
    min_duration = 0
    max_duration = 0

    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    duration = 10
    expiration = start_time + duration * 3600
    rental_amount = duration * price
    renter_delegate = boa.env.generate_address("delegate")

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    ape_contract.approve(renting_contract, rental_amount, sender=renter)

    assert ape_contract.balanceOf(renter) >= rental_amount

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        renter_delegate,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")

    assert rental_started_event.renter == renter
    assert rental_started_event.delegate == renter_delegate
    assert rental_started_event.nft_contract == nft_contract.address
    assert len(rental_started_event.rentals) == 1

    event_rental = RentalLog(*rental_started_event.rentals[0])
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


def test_close_rental(
    contracts_config,
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    renter,
    protocol_wallet,
    protocol_fee,
    nft_owner_key,
    owner_key,
):
    token_id = 1
    min_duration = 0
    max_duration = 0

    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price
    renter_delegate = boa.env.generate_address("delegate")

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    ape_contract.approve(renting_contract, rental_amount, sender=renter)

    assert ape_contract.balanceOf(renter) >= rental_amount

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        renter_delegate,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    event_rental = RentalLog(*rental_started_event.rentals[0])

    started_rental = event_rental.to_rental(renter=renter, delegate=renter_delegate)
    token_context = TokenContext(token_id, nft_owner, started_rental)

    real_duration = 3
    real_expiration = start_time + real_duration * 3600
    real_rental_amount = max(real_duration, min_duration) * price
    boa.env.time_travel(seconds=real_duration * 3600)

    renting_contract.close_rentals([token_context.to_tuple()], sender=renter)

    rental_closed_event = get_last_event(renting_contract, "RentalClosed")

    assert rental_closed_event.renter == renter
    assert rental_closed_event.nft_contract == nft_contract.address
    assert len(rental_closed_event.rentals) == 1

    event_rental = RentalLog(*rental_closed_event.rentals[0])
    assert event_rental.vault == renting_contract.tokenid_to_vault(token_id)
    assert event_rental.owner == nft_owner
    assert event_rental.token_id == token_id
    assert event_rental.start == start_time
    assert event_rental.min_expiration == start_time
    assert event_rental.expiration == real_expiration
    assert event_rental.amount == real_rental_amount
    assert event_rental.protocol_fee == protocol_fee

    assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, Rental())


def test_extend_rental(
    contracts_config,
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    renter,
    protocol_wallet,
    protocol_fee,
    nft_owner_key,
    owner_key,
    delegation_registry_warm_contract,
):
    token_id = 1
    min_duration = 0
    max_duration = 0

    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price
    renter_delegate = boa.env.generate_address("delegate")

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    ape_contract.approve(renting_contract, rental_amount, sender=renter)

    assert ape_contract.balanceOf(renter) >= rental_amount

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        renter_delegate,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    event_rental = RentalLog(*rental_started_event.rentals[0])

    started_rental = event_rental.to_rental(renter=renter, delegate=renter_delegate)
    token_context = TokenContext(token_id, nft_owner, started_rental)

    real_duration = 3
    boa.env.time_travel(seconds=real_duration * 3600)
    extend_timestamp = boa.eval("block.timestamp")

    signed_listing = sign_listing(listing, nft_owner_key, owner_key, extend_timestamp, renting_contract.address)

    ape_contract.approve(renting_contract, rental_amount, sender=renter)

    renting_contract.extend_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()], extend_timestamp, sender=renter
    )

    rental_extended_event = get_last_event(renting_contract, "RentalExtended")

    event_rental = RentalExtensionLog(*rental_extended_event.rentals[0])
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    assert event_rental.vault == vault_addr
    assert event_rental.owner == nft_owner
    assert event_rental.token_id == token_id
    assert event_rental.start == extend_timestamp
    assert event_rental.min_expiration == extend_timestamp
    assert event_rental.expiration == extend_timestamp + duration * 3600
    assert event_rental.amount_settled == rental_amount * real_duration // duration
    assert event_rental.extension_amount == rental_amount

    time_passed = (duration - real_duration) * 3600 + 1
    boa.env.time_travel(seconds=time_passed)

    assert delegation_registry_warm_contract.getHotWalletLink(vault_addr)[0] == renter_delegate
    assert delegation_registry_warm_contract.getHotWalletLink(vault_addr)[1] == extend_timestamp + duration * 3600


def test_claim(
    contracts_config,
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    renter,
    protocol_fee,
    protocol_wallet,
    nft_owner_key,
    owner_key,
):
    token_id = 1
    min_duration = 0
    max_duration = 0

    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price
    renter_delegate = boa.env.generate_address("delegate")

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    ape_contract.approve(renting_contract, rental_amount, sender=renter)

    assert ape_contract.balanceOf(renter) >= rental_amount

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        renter_delegate,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    event_rental = RentalLog(*rental_started_event.rentals[0])

    started_rental = event_rental.to_rental(renter=renter, delegate=renter_delegate)
    token_context = TokenContext(token_id, nft_owner, started_rental)

    boa.env.time_travel(duration * 3600 + 1)

    total_fees = rental_amount * protocol_fee // 10000
    total_rewards = rental_amount - total_fees
    nft_owner_balance = ape_contract.balanceOf(nft_owner)
    protocol_wallet_balance = ape_contract.balanceOf(protocol_wallet)

    renting_contract.claim([token_context.to_tuple()], sender=nft_owner)

    claim_event = get_last_event(renting_contract, "RewardsClaimed")
    assert claim_event.owner == nft_owner
    assert claim_event.amount == total_rewards
    assert claim_event.protocol_fee_amount == total_fees
    assert len(claim_event.rewards) == 1

    reward = RewardLog(*claim_event.rewards[0])
    assert reward.token_id == token_id
    assert reward.active_rental_amount == 0

    assert renting_contract.eval(f"self.unclaimed_rewards[{nft_owner}]") == 0
    assert renting_contract.eval("self.protocol_fees_amount") == total_fees

    assert ape_contract.balanceOf(nft_owner) == nft_owner_balance + total_rewards
    assert ape_contract.balanceOf(protocol_wallet) == protocol_wallet_balance

    claimed_rental = replace(started_rental, amount=0)
    assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, claimed_rental)
