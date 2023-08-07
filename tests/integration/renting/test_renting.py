import boa
import pytest

from decimal import Decimal
from ...conftest_base import ZERO_ADDRESS, get_last_event, get_vault_from_proxy, Listing, Rental, VaultLog, RentalLog, RewardLog, WithdrawalLog


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


def test_create_vaults_and_deposit_not_approved(
    contracts_config, renting_contract, nft_owner
):
    token_id = 1
    price = 1
    with boa.reverts("not approved for token"):
        renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, sender=nft_owner)


def test_create_vaults_and_deposit(
    contracts_config, renting_contract, nft_contract, nft_owner, vault_contract
):
    token_id = 1
    price = 1
    
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, sender=nft_owner)
    event = get_last_event(renting_contract, "VaultsCreated")

    assert renting_contract.active_vaults(token_id) == vault_addr 

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.min_duration == 0
    assert event.max_duration == 0
    vault_log = VaultLog(*event.vaults[-1])
    assert vault_log.vault == vault_addr
    assert vault_log.token_id == token_id


@pytest.mark.profile
def test_create_vaults_and_deposit_limits(contracts_config, renting_contract, nft_contract, nft_owner, vault_contract):
    token_ids = list(range(32))
    price = 1

    vaults = {}

    for token_id in token_ids:
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

        vaults[token_id] = vault_addr

    renting_contract.create_vaults_and_deposit(token_ids, price, 0, 0, sender=nft_owner)
    event = get_last_event(renting_contract, "VaultsCreated")

    for token_id, vault_addr in vaults.items():
        assert renting_contract.active_vaults(token_id) == vault_addr

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.min_duration == 0
    assert event.max_duration == 0
    for idx, entry in enumerate(vaults.items()):
        vault_log = VaultLog(*event.vaults[idx])
        assert vault_log.vault == entry[1]
        assert vault_log.token_id == entry[0]


def test_change_listings_price(
    contracts_config, renting_contract, nft_contract, nft_owner
):
    token_id = 1
    price = int(1e18)
    new_price = int(2e18)
    min_duration = 1
    max_duration = 2
    
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, sender=nft_owner)
    vault = get_vault_from_proxy(vault_addr)

    listing = Listing(*vault.listing())
    assert listing.token_id == token_id
    assert listing.price == price
    assert listing.min_duration == 0
    assert listing.max_duration == 0

    renting_contract.set_listings_prices([token_id], new_price, min_duration, max_duration, sender=nft_owner)
    event = get_last_event(renting_contract, "ListingsPricesChanged")

    vault = get_vault_from_proxy(vault_addr)
    listing = Listing(*vault.listing())
    assert listing.token_id == token_id
    assert listing.price == new_price
    assert listing.min_duration == min_duration
    assert listing.max_duration == max_duration

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

    renting_contract.create_vaults_and_deposit(token_ids, price, 0, 0, sender=nft_owner)

    for token_id, vault_addr in vaults.items():
        vault = get_vault_from_proxy(vault_addr)
        listing = Listing(*vault.listing())
        assert listing.token_id == token_id
        assert listing.price == price
        assert listing.min_duration == 0
        assert listing.max_duration == 0

    renting_contract.set_listings_prices(token_ids, new_price, min_duration, max_duration, sender=nft_owner)
    event = get_last_event(renting_contract, "ListingsPricesChanged")

    for token_id, vault_addr in vaults.items():
        vault = get_vault_from_proxy(vault_addr)
        listing = Listing(*vault.listing())
        assert listing.token_id == token_id
        assert listing.price == new_price
        assert listing.min_duration == min_duration
        assert listing.max_duration == max_duration

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

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, sender=nft_owner)

    renting_contract.cancel_listings([token_id], sender=nft_owner)
    event = get_last_event(renting_contract, "ListingsCancelled")
    
    vault = get_vault_from_proxy(vault_addr)
    listing = Listing(*vault.listing())
    assert listing.token_id == token_id
    assert listing.price == 0
    assert listing.min_duration == 0
    assert listing.max_duration == 0

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
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

        vaults[token_id] = vault_addr

    renting_contract.create_vaults_and_deposit(token_ids, price, 0, 0, sender=nft_owner)

    renting_contract.cancel_listings(token_ids, sender=nft_owner)
    event = get_last_event(renting_contract, "ListingsCancelled")

    for token_id, vault_addr in vaults.items():
        vault = get_vault_from_proxy(vault_addr)
        listing = Listing(*vault.listing())
        assert listing.token_id == token_id
        assert listing.price == 0
        assert listing.min_duration == 0
        assert listing.max_duration == 0

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
    expiration = start_time + 10
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, sender=nft_owner)
    vault_contract = get_vault_from_proxy(vault_addr)

    renting_contract.start_rentals([token_id], expiration, sender=renter)

    event = get_last_event(renting_contract, "RentalStarted")
    assert event.renter == renter
    assert event.nft_contract == nft_contract.address

    rental_log = RentalLog(*event.rentals[-1])
    assert rental_log.token_id == token_id
    assert rental_log.vault == vault_addr
    assert rental_log.owner == nft_owner
    assert rental_log.start == start_time
    assert rental_log.min_expiration == min_expiration
    assert rental_log.expiration == expiration
    assert rental_log.amount == rental_amount

    active_rental = Rental(*vault_contract.active_rental())
    assert active_rental.owner == nft_owner
    assert active_rental.renter == renter
    assert active_rental.token_id == token_id
    assert active_rental.start == start_time
    assert active_rental.min_expiration == min_expiration
    assert active_rental.expiration == expiration
    assert active_rental.amount == rental_amount


def test_close_rental(
    contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter
):
    token_id = 1
    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    expiration = start_time + 60
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, sender=nft_owner)
    vault_contract = get_vault_from_proxy(vault_addr)

    renting_contract.start_rentals([token_id], expiration, sender=renter)

    active_rental = Rental(*vault_contract.active_rental())
    assert active_rental.owner == nft_owner
    assert active_rental.renter == renter
    assert active_rental.token_id == token_id
    assert active_rental.start == start_time
    assert active_rental.min_expiration == min_expiration
    assert active_rental.expiration == expiration
    assert active_rental.amount == rental_amount

    time_passed = 30
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
    start_time = boa.eval("block.timestamp")
    expiration = start_time + 60
    rental_amount = (expiration - start_time) * price // 3600

    for token_id in token_ids:
        vault_addr = renting_contract.tokenid_to_vault(token_id)

        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit(token_ids, price, 0, 0, sender=nft_owner)

    renting_contract.start_rentals(token_ids, expiration, sender=renter)

    time_passed = 30
    boa.env.time_travel(seconds=time_passed)

    renting_contract.close_rentals(token_ids, sender=renter)
    event = get_last_event(renting_contract, "RentalClosed")
    assert event.renter == renter
    assert event.nft_contract == nft_contract.address
    assert len(event.rentals) == bulk_size

    renting_contract.claim(token_ids, sender=nft_owner)
    event = get_last_event(renting_contract, "RewardsClaimed")
    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert len(event.rewards) == bulk_size


def test_claim(
    contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter
):
    token_id = 1
    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    expiration = start_time + 60
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, sender=nft_owner)
    vault_contract = get_vault_from_proxy(vault_addr)

    renting_contract.start_rentals([token_id], expiration, sender=renter)

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.claimable_rewards() == 0

    time_passed = 61
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

    event_reward = RewardLog(*event.rewards[0])
    assert event_reward.vault == vault_addr
    assert event_reward.token_id == token_id
    assert event_reward.amount == rental_amount
    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address

    active_rental = Rental(*vault_contract.active_rental())
    assert active_rental.amount == 0
    assert vault_contract.claimable_rewards() == 0
    assert vault_contract.unclaimed_rewards() == 0


def test_withdraw(
    contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter
):
    token_id = 1
    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    expiration = start_time + 60
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, sender=nft_owner)
    renting_contract.start_rentals([token_id], expiration, sender=renter)

    time_passed = 61
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


@pytest.mark.profile
def test_withdraw_limits(contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter):
    token_ids = list(range(32))
    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    expiration = start_time + 60
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    vaults = {}

    for token_id in token_ids:
        vault_addr = renting_contract.tokenid_to_vault(token_id)

        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        ape_contract.approve(vault_addr, rental_amount, sender=renter)

        vaults[token_id] = vault_addr

    renting_contract.create_vaults_and_deposit(token_ids, price, 0, 0, sender=nft_owner)
    renting_contract.start_rentals(token_ids, expiration, sender=renter)

    time_passed = 61
    boa.env.time_travel(seconds=time_passed)

    renting_contract.withdraw(token_ids, sender=nft_owner)
    event = get_last_event(renting_contract, "NftsWithdrawn")

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


def test_deposit_no_vaults(
    contracts_config, renting_contract, nft_contract, nft_owner, renter
):
    token_id = 1
    price = 1

    with boa.reverts("vault is not available"):
        renting_contract.deposit([token_id], price, 0, 0, sender=nft_owner)


def test_deposit_already_deposited(
    contracts_config, renting_contract, nft_contract, nft_owner, renter
):
    token_id = 1
    price = 1

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, sender=nft_owner)

    with boa.reverts("vault is not available"):
        renting_contract.deposit([token_id], price, 0, 0, sender=nft_owner)


def test_deposit(
    contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    start_time = boa.eval("block.timestamp")
    expiration = start_time + 60
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, min_duration, max_duration, sender=nft_owner)

    assert nft_contract.ownerOf(token_id) == vault_addr
    renting_contract.start_rentals([token_id], expiration, sender=renter)

    time_passed = 61
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
    vault_log = VaultLog(*event.vaults[-1])
    assert vault_log.vault == vault_addr
    assert vault_log.token_id == token_id


@pytest.mark.profile
def test_deposit_limits(contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter):
    token_ids = list(range(32))
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    start_time = boa.eval("block.timestamp")
    expiration = start_time + 60
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    vaults = {}

    for token_id in token_ids:
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        ape_contract.approve(vault_addr, rental_amount, sender=renter)

        vaults[token_id] = vault_addr

    renting_contract.create_vaults_and_deposit(token_ids, price, min_duration, max_duration, sender=nft_owner)

    for token_id, vault_addr in vaults.items():
        assert nft_contract.ownerOf(token_id) == vault_addr

    renting_contract.start_rentals(token_ids, expiration, sender=renter)

    time_passed = 61
    boa.env.time_travel(seconds=time_passed)

    renting_contract.withdraw(token_ids, sender=nft_owner)

    for token_id, vault_addr in vaults.items():
        assert renting_contract.active_vaults(token_id) == ZERO_ADDRESS
        assert renting_contract.tokenid_to_vault(token_id) == vault_addr
        assert renting_contract.is_vault_available(token_id)
        assert nft_contract.ownerOf(token_id) == nft_owner

        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit(token_ids, price, min_duration, max_duration, sender=nft_owner)
    event = get_last_event(renting_contract, "NftsDeposited")

    for token_id, vault_addr in vaults.items():
        assert renting_contract.active_vaults(token_id) == vault_addr
        assert not renting_contract.is_vault_available(token_id)
        assert nft_contract.ownerOf(token_id) == vault_addr

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.min_duration == min_duration
    assert event.max_duration == max_duration
    for idx, entry in enumerate(vaults.items()):
        vault_log = VaultLog(*event.vaults[idx])
        assert vault_log.vault == entry[1]
        assert vault_log.token_id == entry[0]
