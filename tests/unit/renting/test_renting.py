from decimal import Decimal

import boa
import pytest

from ...conftest_base import (
    ZERO_ADDRESS,
    Listing,
    Rental,
    RentalLog,
    RewardLog,
    VaultLog,
    WithdrawalLog,
    get_last_event,
)


@pytest.fixture(scope="module")
def vault_contract(vault_contract_def):
    return vault_contract_def.deploy()


@pytest.fixture(scope="module")
def renting_contract(renting_contract_def, vault_contract, ape_contract, nft_contract, delegation_registry_warm_contract):
    return renting_contract_def.deploy(vault_contract, ape_contract, nft_contract, delegation_registry_warm_contract)


@pytest.fixture(autouse=True)
def mint(
    nft_owner, owner, renter, renting_contract, vault_contract, nft_contract, ape_contract, delegation_registry_warm_contract
):
    with boa.env.anchor():
        nft_contract.mint(nft_owner, 1, sender=owner)
        ape_contract.mint(renter, int(1000 * 1e18), sender=owner)
        yield


def test_initial_state(vault_contract, renting_contract, nft_contract, ape_contract, delegation_registry_warm_contract):
    assert renting_contract.vault_impl_addr() == vault_contract.address
    assert renting_contract.get_payment_token() == ape_contract.address
    assert renting_contract.get_nft_contract() == nft_contract.address
    assert renting_contract.get_delegation_registry() == delegation_registry_warm_contract.address


def test_create_vaults_and_deposit_not_approved(renting_contract, nft_owner):
    token_id = 1
    price = 1
    with boa.reverts("not approved for token"):
        renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, sender=nft_owner)


def test_create_vaults_and_deposit(renting_contract, nft_contract, nft_owner, vault_contract):
    token_id = 1
    price = 1
    min_duration = 0
    max_duration = 1

    assert renting_contract.active_vaults(token_id) == ZERO_ADDRESS

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vaults_and_deposit([token_id], price, min_duration, max_duration, sender=nft_owner)
    event = get_last_event(renting_contract, "VaultsCreated")

    assert renting_contract.active_vaults(token_id) == vault_addr

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.min_duration == min_duration
    assert event.max_duration == max_duration
    assert event.price == price

    vault_log = VaultLog(*event.vaults[-1])
    assert vault_log.vault == vault_addr
    assert vault_log.token_id == token_id


def test_change_listings_prices(renting_contract, nft_contract, nft_owner, vault_contract_def):
    token_id = 1
    price = int(1e18)
    new_price = int(2e18)
    min_duration = 1
    max_duration = 2

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, sender=nft_owner)
    vault_contract = vault_contract_def.at(vault_addr)

    listing = Listing(*vault_contract.listing())
    assert listing.token_id == token_id
    assert listing.price == price
    assert listing.min_duration == 0
    assert listing.max_duration == 0

    renting_contract.set_listings([token_id], new_price, min_duration, max_duration, sender=nft_owner)
    event = get_last_event(renting_contract, "ListingsChanged")

    listing = Listing(*vault_contract.listing())
    assert listing.token_id == token_id
    assert listing.price == new_price
    assert listing.min_duration == min_duration
    assert listing.max_duration == max_duration

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.price == new_price
    assert event.min_duration == min_duration
    assert event.max_duration == max_duration
    vault_log = VaultLog(*event.vaults[-1])
    assert vault_log.vault == vault_addr
    assert vault_log.token_id == token_id


def test_cancel_listings(renting_contract, nft_contract, nft_owner, vault_contract_def):
    token_id = 1
    price = int(1e18)
    min_duration = 1
    max_duration = 2

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vaults_and_deposit([token_id], price, min_duration, max_duration, sender=nft_owner)
    vault_contract = vault_contract_def.at(vault_addr)

    listing = Listing(*vault_contract.listing())
    assert listing.token_id == token_id
    assert listing.price == price
    assert listing.min_duration == min_duration
    assert listing.max_duration == max_duration

    renting_contract.cancel_listings([token_id], sender=nft_owner)
    event = get_last_event(renting_contract, "ListingsCancelled")

    listing = Listing(*vault_contract.listing())
    assert listing.token_id == token_id
    assert listing.price == 0
    assert listing.min_duration == 0
    assert listing.max_duration == 0

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    vault_log = VaultLog(*event.vaults[-1])
    assert vault_log.vault == vault_addr
    assert vault_log.token_id == token_id


def test_start_rental(renting_contract, nft_contract, ape_contract, nft_owner, renter, vault_contract_def):
    token_id = 1
    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    min_expiration = start_time
    duration = 10
    expiration = start_time + duration * 3600
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, sender=nft_owner)
    vault_contract = vault_contract_def.at(vault_addr)

    renting_contract.start_rentals([token_id], duration, sender=renter)
    event = get_last_event(renting_contract, "RentalStarted")

    assert event.renter == renter
    assert event.nft_contract == nft_contract.address
    event_rental = RentalLog(*event.rentals[0])
    assert event_rental.vault == vault_addr
    assert event_rental.owner == nft_owner
    assert event_rental.token_id == token_id
    assert event_rental.start == start_time
    assert event_rental.min_expiration == min_expiration
    assert event_rental.expiration == expiration
    assert event_rental.amount == rental_amount

    active_rental = Rental(*vault_contract.active_rental())
    assert active_rental.owner == nft_owner
    assert active_rental.renter == renter
    assert active_rental.token_id == token_id
    assert active_rental.start == start_time
    assert active_rental.min_expiration == min_expiration
    assert active_rental.expiration == expiration
    assert active_rental.amount == rental_amount


def test_start_rentals(renting_contract, nft_contract, ape_contract, nft_owner, renter, vault_contract_def, owner):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]

    token_id = 1
    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    duration = 10
    expiration = start_time + duration * 3600
    rental_amount = duration * price

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit(token_ids, price, 0, 0, sender=nft_owner)

    renting_contract.start_rentals(token_ids, duration, sender=renter)

    event = get_last_event(renting_contract, "RentalStarted")
    assert event.renter == renter
    assert event.nft_contract == nft_contract.address

    for i, token_id in enumerate(token_ids):
        vault_addr = renting_contract.tokenid_to_vault(token_id)

        event_rental = RentalLog(*event.rentals[i])
        assert event_rental.vault == vault_addr
        assert event_rental.owner == nft_owner
        assert event_rental.token_id == token_id
        assert event_rental.start == start_time
        assert event_rental.min_expiration == min_expiration
        assert event_rental.expiration == expiration
        assert event_rental.amount == rental_amount

        vault_contract = vault_contract_def.at(vault_addr)
        active_rental = Rental(*vault_contract.active_rental())
        assert active_rental.owner == nft_owner
        assert active_rental.renter == renter
        assert active_rental.token_id == token_id
        assert active_rental.start == start_time
        assert active_rental.min_expiration == min_expiration
        assert active_rental.expiration == expiration
        assert active_rental.amount == rental_amount


def test_close_rental(renting_contract, nft_contract, ape_contract, nft_owner, renter, vault_contract_def):
    token_id = 1
    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    duration = 6
    expiration = start_time + duration * 3600
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, sender=nft_owner)
    vault_contract = vault_contract_def.at(vault_addr)

    renting_contract.start_rentals([token_id], duration, sender=renter)

    active_rental = Rental(*vault_contract.active_rental())
    assert active_rental.owner == nft_owner
    assert active_rental.renter == renter
    assert active_rental.token_id == token_id
    assert active_rental.start == start_time
    assert active_rental.min_expiration == min_expiration
    assert active_rental.expiration == expiration
    assert active_rental.amount == rental_amount

    time_passed = 3 * 3600
    boa.env.time_travel(seconds=time_passed)
    real_expiration = int(boa.eval("block.timestamp"))
    real_rental_amount = int(Decimal(rental_amount) / Decimal(2))

    renting_contract.close_rentals([token_id], sender=renter)
    event = get_last_event(renting_contract, "RentalClosed")

    active_rental = Rental(*vault_contract.active_rental())
    assert active_rental.owner == nft_owner
    assert active_rental.renter == renter
    assert active_rental.token_id == token_id
    assert active_rental.start == start_time
    assert active_rental.min_expiration == min_expiration
    assert active_rental.expiration == real_expiration
    assert active_rental.amount == 0

    assert vault_contract.unclaimed_rewards() == real_rental_amount
    assert vault_contract.claimable_rewards() == real_rental_amount

    assert event.renter == renter
    assert event.nft_contract == nft_contract.address
    event_rental = RentalLog(*event.rentals[0])
    assert event_rental.vault == vault_addr
    assert event_rental.owner == nft_owner
    assert event_rental.token_id == token_id
    assert event_rental.start == start_time
    assert event_rental.min_expiration == min_expiration
    assert event_rental.expiration == real_expiration
    assert event_rental.amount == real_rental_amount


def test_close_rental_before_min_duration(renting_contract, nft_contract, ape_contract, nft_owner, renter, vault_contract_def):
    token_id = 1
    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    min_duration = 2
    min_expiration = start_time + min_duration * 3600
    expiration = min_expiration
    rental_amount = (expiration - start_time) * price // 3600

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, min_duration, 0, sender=nft_owner)
    vault_contract = vault_contract_def.at(vault_addr)

    renting_contract.start_rentals([token_id], min_duration, sender=renter)

    time_passed = 3600
    boa.env.time_travel(seconds=time_passed)
    real_expiration = int(boa.eval("block.timestamp"))

    renting_contract.close_rentals([token_id], sender=renter)
    event = get_last_event(renting_contract, "RentalClosed")

    active_rental = Rental(*vault_contract.active_rental())
    assert active_rental.owner == nft_owner
    assert active_rental.renter == renter
    assert active_rental.token_id == token_id
    assert active_rental.start == start_time
    assert active_rental.min_expiration == min_expiration
    assert active_rental.expiration == real_expiration
    assert active_rental.amount == 0

    assert vault_contract.unclaimed_rewards() == rental_amount
    assert vault_contract.claimable_rewards() == rental_amount

    assert event.renter == renter
    assert event.nft_contract == nft_contract.address
    event_rental = RentalLog(*event.rentals[0])
    assert event_rental.vault == vault_addr
    assert event_rental.owner == nft_owner
    assert event_rental.token_id == token_id
    assert event_rental.start == start_time
    assert event_rental.min_expiration == min_expiration
    assert event_rental.expiration == real_expiration
    assert event_rental.amount == rental_amount


def test_close_rental_with_changed_list_price(
    renting_contract, nft_contract, ape_contract, nft_owner, renter, vault_contract_def
):
    token_id = 1
    price = int(1e18)
    changed_price = 3 * price
    start_time = boa.eval("block.timestamp")
    duration = 10
    expiration = start_time + duration * 3600
    rental_amount = (expiration - start_time) * price // 3600

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, sender=nft_owner)
    vault_contract = vault_contract_def.at(vault_addr)

    renting_contract.start_rentals([token_id], duration, sender=renter)

    renting_contract.set_listings([token_id], changed_price, 0, 0, sender=nft_owner)

    time_passed = 3600
    boa.env.time_travel(seconds=time_passed)
    real_expiration = int(boa.eval("block.timestamp"))
    real_rental_amount = (real_expiration - start_time) * price // 3600

    renting_contract.close_rentals([token_id], sender=renter)
    event = get_last_event(renting_contract, "RentalClosed")

    active_rental = Rental(*vault_contract.active_rental())
    assert active_rental.owner == nft_owner
    assert active_rental.renter == renter
    assert active_rental.token_id == token_id
    assert active_rental.start == start_time
    assert active_rental.min_expiration == start_time
    assert active_rental.expiration == real_expiration
    assert active_rental.amount == 0

    assert vault_contract.unclaimed_rewards() == real_rental_amount
    assert vault_contract.claimable_rewards() == real_rental_amount

    assert event.renter == renter
    assert event.nft_contract == nft_contract.address
    event_rental = RentalLog(*event.rentals[0])
    assert event_rental.vault == vault_addr
    assert event_rental.owner == nft_owner
    assert event_rental.token_id == token_id
    assert event_rental.start == start_time
    assert event_rental.min_expiration == start_time
    assert event_rental.expiration == real_expiration
    assert event_rental.amount == real_rental_amount


def test_close_rentals(renting_contract, nft_contract, ape_contract, nft_owner, renter, vault_contract_def, owner):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]
    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    duration = 6
    rental_amount = duration * price

    vaults = {}

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)

        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        ape_contract.approve(vault_addr, rental_amount, sender=renter)

        vaults[token_id] = vault_addr

    renting_contract.create_vaults_and_deposit(token_ids, price, 0, 0, sender=nft_owner)

    renting_contract.start_rentals(token_ids, duration, sender=renter)

    time_passed = 3 * 3600
    boa.env.time_travel(seconds=time_passed)
    real_expiration = int(boa.eval("block.timestamp"))
    real_rental_amount = int(Decimal(rental_amount) / Decimal(2))

    renting_contract.close_rentals(token_ids, sender=renter)
    event = get_last_event(renting_contract, "RentalClosed")
    assert event.renter == renter
    assert event.nft_contract == nft_contract.address

    for i, token_id in enumerate(token_ids):
        vault_addr = renting_contract.tokenid_to_vault(token_id)

        event_rental = RentalLog(*event.rentals[i])
        assert event_rental.vault == vault_addr
        assert event_rental.owner == nft_owner
        assert event_rental.token_id == token_id
        assert event_rental.start == start_time
        assert event_rental.min_expiration == min_expiration
        assert event_rental.expiration == real_expiration
        assert event_rental.amount == real_rental_amount

        vault_contract = vault_contract_def.at(vault_addr)
        active_rental = Rental(*vault_contract.active_rental())
        assert active_rental.owner == nft_owner
        assert active_rental.renter == renter
        assert active_rental.token_id == token_id
        assert active_rental.start == start_time
        assert active_rental.min_expiration == min_expiration
        assert active_rental.expiration == real_expiration
        assert active_rental.amount == 0

        assert vault_contract.unclaimed_rewards() == real_rental_amount
        assert vault_contract.claimable_rewards() == real_rental_amount


def test_claim(renting_contract, nft_contract, ape_contract, nft_owner, renter, vault_contract_def):
    token_id = 1
    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    duration = 6
    expiration = start_time + duration * 3600
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, sender=nft_owner)
    vault_contract = vault_contract_def.at(vault_addr)

    renting_contract.start_rentals([token_id], duration, sender=renter)

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.claimable_rewards() == 0

    time_passed = duration * 3600 + 1
    boa.env.time_travel(seconds=time_passed)

    active_rental = Rental(*vault_contract.active_rental())
    assert active_rental.owner == nft_owner
    assert active_rental.renter == renter
    assert active_rental.token_id == token_id
    assert active_rental.start == start_time
    assert active_rental.min_expiration == min_expiration
    assert active_rental.expiration == expiration
    assert active_rental.amount == rental_amount

    assert vault_contract.claimable_rewards() == rental_amount
    assert vault_contract.unclaimed_rewards() == 0

    renting_contract.claim([token_id], sender=nft_owner)
    event = get_last_event(renting_contract, "RewardsClaimed")

    active_rental = Rental(*vault_contract.active_rental())
    assert active_rental.amount == 0
    assert vault_contract.claimable_rewards() == 0
    assert vault_contract.unclaimed_rewards() == 0

    event_reward = RewardLog(*event.rewards[0])
    assert event_reward.vault == vault_addr
    assert event_reward.token_id == token_id
    assert event_reward.amount == rental_amount
    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address


def test_claim_multiple(renting_contract, nft_contract, ape_contract, nft_owner, renter, vault_contract_def, owner):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]

    price = int(1e18)
    duration = 6
    rental_amount = duration * price

    vaults = {}

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)

        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        ape_contract.approve(vault_addr, rental_amount, sender=renter)

        vaults[token_id] = vault_addr

    renting_contract.create_vaults_and_deposit(token_ids, price, 0, 0, sender=nft_owner)

    renting_contract.start_rentals(token_ids, duration, sender=renter)

    for token_id, vault_addr in vaults.items():
        vault_contract = vault_contract_def.at(vault_addr)
        assert vault_contract.unclaimed_rewards() == 0
        assert vault_contract.claimable_rewards() == 0

    time_passed = duration * 3600 + 1
    boa.env.time_travel(seconds=time_passed)

    renting_contract.claim(token_ids, sender=nft_owner)
    event = get_last_event(renting_contract, "RewardsClaimed")

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address

    for i, token_id in enumerate(token_ids):
        vault_addr = renting_contract.tokenid_to_vault(token_id)

        event_reward = RewardLog(*event.rewards[i])
        assert event_reward.vault == vault_addr
        assert event_reward.token_id == token_id
        assert event_reward.amount == rental_amount


def test_withdraw(renting_contract, nft_contract, ape_contract, nft_owner, renter):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    start_time = boa.eval("block.timestamp")
    duration = 6
    expiration = start_time + duration * 3600
    rental_amount = int(Decimal(expiration - start_time) * Decimal(price) / Decimal(3600))

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, min_duration, max_duration, sender=nft_owner)
    renting_contract.start_rentals([token_id], duration, sender=renter)

    time_passed = duration * 3600 + 1
    boa.env.time_travel(seconds=time_passed)

    renting_contract.withdraw([token_id], sender=nft_owner)
    event = get_last_event(renting_contract, "NftsWithdrawn")

    assert renting_contract.active_vaults(token_id) == ZERO_ADDRESS

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.total_rewards == rental_amount
    withdrawal_log = WithdrawalLog(*event.withdrawals[-1])
    assert withdrawal_log.vault == vault_addr
    assert withdrawal_log.token_id == token_id
    assert withdrawal_log.rewards == rental_amount


def test_deposit_no_vaults(renting_contract, nft_contract, nft_owner, renter):
    token_id = 1
    price = 1

    with boa.reverts("vault is not available"):
        renting_contract.deposit([token_id], price, 0, 0, sender=nft_owner)


def test_deposit_already_deposited(renting_contract, nft_contract, nft_owner, renter):
    token_id = 1
    price = 1

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, sender=nft_owner)

    with boa.reverts("vault is not available"):
        renting_contract.deposit([token_id], price, 0, 0, sender=nft_owner)


def test_deposit(renting_contract, nft_contract, ape_contract, nft_owner, renter):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    duration = 6
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, min_duration, max_duration, sender=nft_owner)

    assert nft_contract.ownerOf(token_id) == vault_addr

    renting_contract.start_rentals([token_id], duration, sender=renter)

    time_passed = duration * 3600 + 1
    boa.env.time_travel(seconds=time_passed)

    renting_contract.withdraw([token_id], sender=nft_owner)

    assert renting_contract.active_vaults(token_id) == ZERO_ADDRESS
    assert renting_contract.tokenid_to_vault(token_id) == vault_addr
    assert renting_contract.is_vault_available(token_id)
    assert nft_contract.ownerOf(token_id) == nft_owner

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], price, min_duration, max_duration, sender=nft_owner)
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
