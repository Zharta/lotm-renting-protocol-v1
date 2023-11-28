from decimal import Decimal

import boa
import pytest

from ...conftest_base import (
    ZERO_ADDRESS,
    ZERO_BYTES32,
    Listing,
    Rental,
    RentalLog,
    RewardLog,
    TokenContext,
    VaultLog,
    WithdrawalLog,
    compute_state_hash,
    get_last_event,
    get_vault_from_proxy,
)


def test_initial_state(
    vault_contract,
    renting_contract,
    nft_contract,
    ape_contract,
    delegation_registry_warm_contract,
):
    assert renting_contract.vault_impl_addr() == vault_contract.address
    assert renting_contract.get_payment_token() == ape_contract.address
    assert renting_contract.get_nft_contract() == nft_contract.address
    assert renting_contract.get_delegation_registry() == delegation_registry_warm_contract.address


def test_create_vaults_and_deposit_not_approved(contracts_config, renting_contract, nft_owner):
    token_id = 1
    price = 1
    with boa.reverts():
        renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, ZERO_ADDRESS, sender=nft_owner)


def test_create_vaults_and_deposit(
    contracts_config, renting_contract, nft_contract, nft_owner, vault_contract, delegation_registry_warm_contract
):
    token_id = 1
    price = 1

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, nft_owner, sender=nft_owner)
    event = get_last_event(renting_contract, "VaultsCreated")

    assert renting_contract.active_vaults(token_id) == vault_addr

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.min_duration == 0
    assert event.max_duration == 0
    assert event.price == price
    vault_log = VaultLog(*event.vaults[-1])
    assert vault_log.vault == vault_addr
    assert vault_log.token_id == token_id

    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == nft_owner


@pytest.mark.profile
def test_create_vaults_and_deposit_limits(contracts_config, renting_contract, nft_contract, nft_owner, vault_contract):
    token_ids = list(range(32))
    price = 1

    vaults = {}

    for token_id in token_ids:
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

        vaults[token_id] = vault_addr

    renting_contract.create_vaults_and_deposit(token_ids, price, 0, 0, ZERO_ADDRESS, sender=nft_owner)
    event = get_last_event(renting_contract, "VaultsCreated")

    for token_id, vault_addr in vaults.items():
        assert renting_contract.active_vaults(token_id) == vault_addr

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.min_duration == 0
    assert event.max_duration == 0
    assert event.price == price
    for idx, entry in enumerate(vaults.items()):
        vault_log = VaultLog(*event.vaults[idx])
        assert vault_log.vault == entry[1]
        assert vault_log.token_id == entry[0]


def test_change_listings_price(contracts_config, renting_contract, nft_contract, nft_owner):
    token_id = 1
    price = int(1e18)
    new_price = int(2e18)
    min_duration = 1
    max_duration = 2

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, ZERO_ADDRESS, sender=nft_owner)
    vault = get_vault_from_proxy(vault_addr)

    token_context = TokenContext(token_id, Rental(), Listing(token_id, price, 0, 0))
    assert vault.state() == compute_state_hash(token_context.active_rental, token_context.listing)

    renting_contract.set_listings(
        [token_context.to_tuple()], new_price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner
    )
    event = get_last_event(renting_contract, "ListingsChanged")

    vault = get_vault_from_proxy(vault_addr)
    assert vault.state() == compute_state_hash(Rental(), Listing(token_id, new_price, min_duration, max_duration))

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.price == new_price
    vault_log = VaultLog(*event.vaults[-1])
    assert vault_log.vault == vault_addr
    assert vault_log.token_id == token_id


@pytest.mark.profile
def test_change_listings_price_limits(contracts_config, renting_contract, nft_contract, nft_owner):
    token_ids = list(range(32))
    price = int(1e18)
    new_price = int(2e18)
    min_duration = 1
    max_duration = 2

    vaults = {}

    for token_id in token_ids:
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

        vaults[token_id] = vault_addr

    renting_contract.create_vaults_and_deposit(token_ids, price, 0, 0, ZERO_ADDRESS, sender=nft_owner)

    for token_id, vault_addr in vaults.items():
        vault = get_vault_from_proxy(vault_addr)
        assert vault.state() == compute_state_hash(Rental(), Listing(token_id, price, 0, 0))

    token_contexts = [TokenContext(token_id, Rental(), Listing(token_id, price, 0, 0)) for token_id in token_ids]

    renting_contract.set_listings(
        [c.to_tuple() for c in token_contexts], new_price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner
    )
    event = get_last_event(renting_contract, "ListingsChanged")

    for token_id, vault_addr in vaults.items():
        vault = get_vault_from_proxy(vault_addr)
        assert vault.state() == compute_state_hash(Rental(), Listing(token_id, new_price, min_duration, max_duration))

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.price == new_price
    for idx, entry in enumerate(vaults.items()):
        vault_log = VaultLog(*event.vaults[idx])
        assert vault_log.vault == entry[1]
        assert vault_log.token_id == entry[0]


def test_cancel_listings(contracts_config, renting_contract, nft_contract, nft_owner):
    token_id = 1
    price = int(1e18)

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, ZERO_ADDRESS, sender=nft_owner)

    token_context = TokenContext(token_id, Rental(), Listing(token_id, price, 0, 0))
    renting_contract.cancel_listings([token_context.to_tuple()], ZERO_ADDRESS, sender=nft_owner)

    event = get_last_event(renting_contract, "ListingsCancelled")

    vault = get_vault_from_proxy(vault_addr)
    assert vault.state() == compute_state_hash(Rental(), Listing(token_id, 0, 0, 0))

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    vault_log = VaultLog(*event.vaults[-1])
    assert vault_log.vault == vault_addr
    assert vault_log.token_id == token_id


@pytest.mark.profile
def test_cancel_listings_limits(contracts_config, renting_contract, nft_contract, nft_owner):
    token_ids = list(range(32))
    price = int(1e18)

    vaults = {}

    for token_id in token_ids:
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        vaults[token_id] = vault_addr
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vaults_and_deposit(token_ids, price, 0, 0, ZERO_ADDRESS, sender=nft_owner)

    token_contexts = [TokenContext(token_id, Rental(), Listing(token_id, price, 0, 0)) for token_id in token_ids]

    renting_contract.cancel_listings([c.to_tuple() for c in token_contexts], ZERO_ADDRESS, sender=nft_owner)
    event = get_last_event(renting_contract, "ListingsCancelled")

    for token_id, vault_addr in vaults.items():
        vault = get_vault_from_proxy(vault_addr)
        assert vault.state() == compute_state_hash(Rental(), Listing(token_id, 0, 0, 0))

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    for idx, entry in enumerate(vaults.items()):
        vault_log = VaultLog(*event.vaults[idx])
        assert vault_log.vault == entry[1]
        assert vault_log.token_id == entry[0]


def test_start_rental(contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter):
    token_id = 1
    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    duration = 10
    expiration = start_time + duration * 3600
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, ZERO_ADDRESS, sender=nft_owner)
    vault_contract = get_vault_from_proxy(vault_addr)

    token_context = TokenContext(token_id, Rental(), Listing(token_id, price, 0, 0))
    renting_contract.start_rentals([token_context.to_tuple()], duration, renter, sender=renter)

    event = get_last_event(renting_contract, "RentalStarted")
    assert event.renter == renter
    assert event.nft_contract == nft_contract.address

    token_context.active_rental = RentalLog(*event.rentals[0]).to_rental(renter)
    assert vault_contract.state() == compute_state_hash(token_context.active_rental, token_context.listing)

    rental_log = RentalLog(*event.rentals[-1])
    assert rental_log.token_id == token_id
    assert rental_log.vault == vault_addr
    assert rental_log.owner == nft_owner
    assert rental_log.start == start_time
    assert rental_log.min_expiration == min_expiration
    assert rental_log.expiration == expiration
    assert rental_log.amount == rental_amount


def test_close_rental(contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter):
    token_id = 1
    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    duration = 6
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, ZERO_ADDRESS, sender=nft_owner)
    vault_contract = get_vault_from_proxy(vault_addr)

    token_context = TokenContext(token_id, Rental(), Listing(token_id, price, 0, 0))
    renting_contract.start_rentals([token_context.to_tuple()], duration, renter, sender=renter)
    event = get_last_event(renting_contract, "RentalStarted")

    token_context.active_rental = RentalLog(*event.rentals[0]).to_rental(renter)
    assert vault_contract.state() == compute_state_hash(token_context.active_rental, Listing(token_id, price, 0, 0))

    time_passed = duration * 3600 // 2
    boa.env.time_travel(seconds=time_passed)
    real_expiration = int(boa.eval("block.timestamp"))
    real_rental_amount = int(Decimal(rental_amount) / Decimal(2))

    renting_contract.close_rentals([token_context.to_tuple()], sender=renter)
    event = get_last_event(renting_contract, "RentalClosed")

    token_context.active_rental = RentalLog(*event.rentals[0]).to_rental(renter)
    assert vault_contract.state() == compute_state_hash(Rental(), Listing(token_id, price, 0, 0))

    assert vault_contract.unclaimed_rewards() == real_rental_amount
    assert vault_contract.claimable_rewards(Rental().to_tuple()) == real_rental_amount

    rental_log = RentalLog(*event.rentals[-1])
    assert rental_log.token_id == token_id
    assert rental_log.vault == vault_addr
    assert rental_log.owner == nft_owner
    assert rental_log.start == start_time
    assert rental_log.min_expiration == min_expiration
    assert rental_log.expiration == real_expiration
    assert rental_log.amount == real_rental_amount

    assert event.nft_contract == nft_contract.address
    assert event.renter == renter


@pytest.mark.profile
def test_bulk_rentals_limits(contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter):
    bulk_size = 32
    token_ids = [token_id for token_id in range(bulk_size)]
    price = int(1e18)
    duration = 6
    rental_amount = duration * price

    vaults = {}

    for token_id in token_ids:
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        vaults[token_id] = vault_addr
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit(token_ids, price, 0, 0, ZERO_ADDRESS, sender=nft_owner)

    token_contexts = [TokenContext(token_id, Rental(), Listing(token_id, price, 0, 0)) for token_id in token_ids]

    renting_contract.start_rentals([c.to_tuple() for c in token_contexts], duration, renter, sender=renter)
    event = get_last_event(renting_contract, "RentalStarted")

    rental_logs = [RentalLog(*rental) for rental in event.rentals]

    for token_context, rental_log in zip(token_contexts, rental_logs):
        token_context.active_rental = rental_log.to_rental(renter)
        vault = get_vault_from_proxy(vaults[token_context.token_id])
        assert vault.state() == compute_state_hash(token_context.active_rental, token_context.listing)

    time_passed = duration * 3600 // 2
    boa.env.time_travel(seconds=time_passed)

    renting_contract.close_rentals([c.to_tuple() for c in token_contexts], sender=renter)
    event = get_last_event(renting_contract, "RentalClosed")
    assert event.renter == renter
    assert event.nft_contract == nft_contract.address
    assert len(event.rentals) == bulk_size

    for token_context, rental_log in zip(token_contexts, rental_logs):
        token_context.active_rental = Rental()
        vault = get_vault_from_proxy(vaults[token_context.token_id])
        assert vault.state() == compute_state_hash(token_context.active_rental, token_context.listing)

    renting_contract.claim([c.to_tuple() for c in token_contexts], sender=nft_owner)
    event = get_last_event(renting_contract, "RewardsClaimed")
    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert len(event.rewards) == bulk_size


def test_claim(contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter):
    token_id = 1
    price = int(1e18)
    duration = 6
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, ZERO_ADDRESS, sender=nft_owner)
    vault_contract = get_vault_from_proxy(vault_addr)

    token_context = TokenContext(token_id, Rental(), Listing(token_id, price, 0, 0))
    renting_contract.start_rentals([token_context.to_tuple()], duration, renter, sender=renter)
    event = get_last_event(renting_contract, "RentalStarted")

    token_context.active_rental = RentalLog(*event.rentals[0]).to_rental(renter)
    assert vault_contract.state() == compute_state_hash(token_context.active_rental, token_context.listing)

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.claimable_rewards(token_context.active_rental.to_tuple()) == 0

    time_passed = duration * 3600 + 1
    boa.env.time_travel(seconds=time_passed)

    assert vault_contract.claimable_rewards(token_context.active_rental.to_tuple()) == rental_amount
    assert vault_contract.unclaimed_rewards() == 0

    renting_contract.claim([token_context.to_tuple()], sender=nft_owner)
    event = get_last_event(renting_contract, "RewardsClaimed")

    event_reward = RewardLog(*event.rewards[0])
    assert event_reward.vault == vault_addr
    assert event_reward.token_id == token_id
    assert event_reward.amount == rental_amount
    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address

    token_context.active_rental.amount = 0
    assert vault_contract.state() == compute_state_hash(token_context.active_rental, token_context.listing)


def test_withdraw(contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter):
    token_id = 1
    price = int(1e18)
    duration = 6
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, ZERO_ADDRESS, sender=nft_owner)

    token_context = TokenContext(token_id, Rental(), Listing(token_id, price, 0, 0))
    renting_contract.start_rentals([token_context.to_tuple()], duration, renter, sender=renter)

    time_passed = duration * 3600 + 1
    boa.env.time_travel(seconds=time_passed)

    event = get_last_event(renting_contract, "RentalStarted")
    token_context.active_rental = RentalLog(*event.rentals[0]).to_rental(renter)

    renting_contract.withdraw([token_context.to_tuple()], sender=nft_owner)
    event = get_last_event(renting_contract, "NftsWithdrawn")

    assert renting_contract.active_vaults(token_id) == ZERO_ADDRESS

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.total_rewards == rental_amount
    withdrawal_log = WithdrawalLog(*event.withdrawals[-1])
    assert withdrawal_log.vault == vault_addr
    assert withdrawal_log.token_id == token_id
    assert withdrawal_log.rewards == rental_amount


@pytest.mark.profile
def test_withdraw_limits(contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter):
    token_ids = list(range(32))
    price = int(1e18)
    duration = 6
    rental_amount = duration * price

    vaults = {}

    for token_id in token_ids:
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        vaults[token_id] = vault_addr

        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit(token_ids, price, 0, 0, ZERO_ADDRESS, sender=nft_owner)

    token_contexts = [TokenContext(token_id, Rental(), Listing(token_id, price, 0, 0)) for token_id in token_ids]

    renting_contract.start_rentals([c.to_tuple() for c in token_contexts], duration, renter, sender=renter)
    event = get_last_event(renting_contract, "RentalStarted")

    rental_logs = [RentalLog(*rental) for rental in event.rentals]

    for token_context, rental_log in zip(token_contexts, rental_logs):
        token_context.active_rental = rental_log.to_rental(renter)
        vault = get_vault_from_proxy(vaults[token_context.token_id])
        print(f"{token_id=} {token_context=}")
        assert vault.state() == compute_state_hash(token_context.active_rental, token_context.listing)

    time_passed = duration * 3600 + 1
    boa.env.time_travel(seconds=time_passed)

    renting_contract.withdraw([c.to_tuple() for c in token_contexts], sender=nft_owner)
    event = get_last_event(renting_contract, "NftsWithdrawn")

    for token_context, rental_log in zip(token_contexts, rental_logs):
        vault = get_vault_from_proxy(vaults[token_context.token_id])
        assert vault.state() == ZERO_BYTES32

    assert renting_contract.active_vaults(token_id) == ZERO_ADDRESS

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.total_rewards == rental_amount * len(token_ids)
    for idx, entry in enumerate(vaults.items()):
        withdrawal_log = WithdrawalLog(*event.withdrawals[idx])
        assert withdrawal_log.vault == entry[1]
        assert withdrawal_log.token_id == entry[0]
        assert withdrawal_log.rewards == rental_amount
    assert len(event.withdrawals) == len(token_ids)


def test_deposit_no_vaults(contracts_config, renting_contract, nft_contract, nft_owner, renter):
    token_id = 1
    price = 1

    with boa.reverts("vault is not available"):
        renting_contract.deposit([token_id], price, 0, 0, ZERO_ADDRESS, sender=nft_owner)


def test_deposit_already_deposited(contracts_config, renting_contract, nft_contract, nft_owner, renter):
    token_id = 1
    price = 1

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, ZERO_ADDRESS, sender=nft_owner)

    with boa.reverts("vault is not available"):
        renting_contract.deposit([token_id], price, 0, 0, ZERO_ADDRESS, sender=nft_owner)


def test_deposit(contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    duration = 6
    rental_amount = duration * price

    active_rental = Rental()
    listing = Listing(token_id, price, min_duration, max_duration)
    token_context = TokenContext(token_id, active_rental, listing)

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner)

    assert nft_contract.ownerOf(token_id) == vault_addr
    renting_contract.start_rentals([token_context.to_tuple()], duration, renter, sender=renter)

    event = get_last_event(renting_contract, "RentalStarted")
    rental_log = RentalLog(*event.rentals[0])

    token_context.active_rental = Rental(
        rental_log.id,
        nft_owner,
        renter,
        renter,
        token_id,
        rental_log.start,
        rental_log.min_expiration,
        rental_log.expiration,
        rental_log.amount,
    )

    time_passed = duration * 3600 + 1
    boa.env.time_travel(seconds=time_passed)

    renting_contract.withdraw([token_context.to_tuple()], sender=nft_owner)

    assert renting_contract.active_vaults(token_id) == ZERO_ADDRESS
    assert renting_contract.tokenid_to_vault(token_id) == vault_addr
    assert renting_contract.is_vault_available(token_id)
    assert nft_contract.ownerOf(token_id) == nft_owner

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit([token_id], price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner)
    event = get_last_event(renting_contract, "NftsDeposited")

    assert renting_contract.active_vaults(token_id) == vault_addr
    assert not renting_contract.is_vault_available(token_id)
    assert nft_contract.ownerOf(token_id) == vault_addr

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.min_duration == min_duration
    assert event.max_duration == max_duration
    assert event.price == price
    vault_log = VaultLog(*event.vaults[-1])
    assert vault_log.vault == vault_addr
    assert vault_log.token_id == token_id


@pytest.mark.profile
def test_deposit_limits(contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter):
    token_ids = list(range(32))
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    duration = 6
    rental_amount = duration * price

    vaults = {}

    no_rental = Rental()
    token_contexts = [
        TokenContext(token_id, no_rental, Listing(token_id, price, min_duration, max_duration)) for token_id in token_ids
    ]

    for token_id in token_ids:
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        ape_contract.approve(vault_addr, rental_amount, sender=renter)

        vaults[token_id] = vault_addr

    renting_contract.create_vaults_and_deposit(token_ids, price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner)

    for token_id, vault_addr in vaults.items():
        assert nft_contract.ownerOf(token_id) == vault_addr

    renting_contract.start_rentals([c.to_tuple() for c in token_contexts], duration, renter, sender=renter)

    event = get_last_event(renting_contract, "RentalStarted")
    rental_logs = [RentalLog(*rental) for rental in event.rentals]

    for token_context, rental_log in zip(token_contexts, rental_logs):
        token_context.active_rental = Rental(
            rental_log.id,
            nft_owner,
            renter,
            renter,
            token_context.token_id,
            rental_log.start,
            rental_log.min_expiration,
            rental_log.expiration,
            rental_log.amount,
        )

    time_passed = duration * 3600 + 1
    boa.env.time_travel(seconds=time_passed)

    renting_contract.withdraw([c.to_tuple() for c in token_contexts], sender=nft_owner)

    for token_id, vault_addr in vaults.items():
        assert renting_contract.active_vaults(token_id) == ZERO_ADDRESS
        assert renting_contract.tokenid_to_vault(token_id) == vault_addr
        assert renting_contract.is_vault_available(token_id)
        assert nft_contract.ownerOf(token_id) == nft_owner

        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit(token_ids, price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner)
    event = get_last_event(renting_contract, "NftsDeposited")

    for token_id, vault_addr in vaults.items():
        assert renting_contract.active_vaults(token_id) == vault_addr
        assert not renting_contract.is_vault_available(token_id)
        assert nft_contract.ownerOf(token_id) == vault_addr

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.min_duration == min_duration
    assert event.max_duration == max_duration
    assert event.price == price
    for idx, entry in enumerate(vaults.items()):
        vault_log = VaultLog(*event.vaults[idx])
        assert vault_log.vault == entry[1]
        assert vault_log.token_id == entry[0]


def test_delegation(contracts_config, renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract):
    token_id = 1
    price = int(1e18)

    delegate = boa.env.generate_address("delegate")
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    # create_vaults_and_deposit creates self delegation
    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, delegate, sender=nft_owner)
    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate
    delegation_registry_warm_contract.setHotWallet(ZERO_ADDRESS, 0, False, sender=vault_addr)

    # cancel_listings does not creates self delegation
    token_context = TokenContext(token_id, Rental(), Listing(token_id, price, 0, 0))
    renting_contract.cancel_listings([token_context.to_tuple()], ZERO_ADDRESS, sender=nft_owner)
    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == ZERO_ADDRESS

    # set_listings does not creates self delegation
    token_context.listing = Listing(token_id, 0, 0, 0)
    renting_contract.set_listings([token_context.to_tuple()], price, 0, 0, ZERO_ADDRESS, sender=nft_owner)
    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == ZERO_ADDRESS

    # cancel_listings_and_delegate_to_owner creates self delegation
    token_context.listing = Listing(token_id, price, 0, 0)
    renting_contract.cancel_listings([token_context.to_tuple()], delegate, sender=nft_owner)
    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate
    delegation_registry_warm_contract.setHotWallet(ZERO_ADDRESS, 0, False, sender=vault_addr)

    # set_listings_and_delegate_to_owner creates self delegation
    token_context.listing = Listing(token_id, 0, 0, 0)
    renting_contract.set_listings([token_context.to_tuple()], price, 0, 0, delegate, sender=nft_owner)
    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate
    delegation_registry_warm_contract.setHotWallet(ZERO_ADDRESS, 0, False, sender=vault_addr)

    # delegate_to_owner creates self delegation
    token_context.listing = Listing(token_id, price, 0, 0)
    renting_contract.delegate_to_wallet([token_context.to_tuple()], delegate, sender=nft_owner)
    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate
