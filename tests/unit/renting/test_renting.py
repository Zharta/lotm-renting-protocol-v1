import boa
import pytest

from decimal import Decimal
from ...conftest_base import ZERO_ADDRESS, get_last_event, Rental


@pytest.fixture(scope="module")
def vault_contract(vault_contract_def):
    return vault_contract_def.deploy()


@pytest.fixture(scope="module")
def renting_contract(renting_contract_def, vault_contract, ape_contract, nft_contract, delegation_registry_warm_contract):
    return renting_contract_def.deploy(vault_contract, ape_contract, nft_contract, delegation_registry_warm_contract)


@pytest.fixture(autouse=True)
def mint(nft_owner, owner, renter, renting_contract, vault_contract, nft_contract, ape_contract, delegation_registry_warm_contract):
    with boa.env.anchor():
        nft_contract.mint(nft_owner, 1, sender=owner)
        ape_contract.mint(renter, int(1000 * 1e18), sender=owner)
        yield


def test_initial_state(vault_contract, renting_contract, nft_contract, ape_contract, delegation_registry_warm_contract):
    assert renting_contract.vault_impl_addr() == vault_contract.address
    assert renting_contract.get_payment_token() == ape_contract.address
    assert renting_contract.get_nft_contract() == nft_contract.address
    assert renting_contract.get_delegation_registry() == delegation_registry_warm_contract.address


def test_create_vault_and_deposit_not_approved(renting_contract, nft_owner):
    token_id = 1
    price = 1
    with boa.reverts("not approved for token"):
        renting_contract.create_vault_and_deposit(token_id, price, sender=nft_owner)


def test_create_vault_and_deposit(renting_contract, nft_contract, nft_owner, vault_contract):
    token_id = 1
    price = 1

    assert renting_contract.active_vaults(token_id) == ZERO_ADDRESS

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vault_and_deposit(token_id, price, sender=nft_owner)
    event_vault_created = get_last_event(renting_contract, "VaultCreated")
    event_nft_deposited = get_last_event(renting_contract, "NFTDeposited")

    assert renting_contract.active_vaults(token_id) == vault_addr

    assert event_vault_created.vault == vault_addr
    assert event_vault_created.owner == nft_owner
    assert event_vault_created.nft_contract == nft_contract.address
    assert event_vault_created.token_id == token_id

    assert event_nft_deposited.vault == vault_addr
    assert event_nft_deposited.owner == nft_owner
    assert event_nft_deposited.nft_contract == nft_contract.address
    assert event_nft_deposited.token_id == token_id


# def test_create_listing(renting_contract, nft_contract, nft_owner):
#     token_id = 1
#     price = int(1e18)

#     vault_addr = renting_contract.tokenid_to_vault(token_id)

#     nft_contract.approve(vault_addr, token_id, sender=nft_owner)

#     renting_contract.create_vault_and_deposit(token_id, sender=nft_owner)
#     vault_contract = vault_contract_def.at(vault_addr)

#     renting_contract.create_listing(token_id, int(1e18), sender=nft_owner)
#     event = get_last_event(renting_contract, "ListingCreated")

#     assert renting_contract.active_vaults(token_id) == vault_addr
#     assert vault_contract.listing() == (token_id, price, True)

#     assert event.vault == vault_addr
#     assert event.owner == nft_owner
#     assert event.nft_contract == nft_contract.address
#     assert event.token_id == token_id
#     assert event.price == price


def test_change_listing_price(renting_contract, nft_contract, nft_owner, vault_contract_def):
    token_id = 1
    price = int(1e18)
    new_price = int(2e18)

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vault_and_deposit(token_id, price, sender=nft_owner)
    vault_contract = vault_contract_def.at(vault_addr)

    # renting_contract.create_listing(token_id, price, sender=nft_owner)
    # assert vault_contract.listing() == (token_id, price, True)
    assert vault_contract.listing() == (token_id, price)

    renting_contract.set_listing_price(token_id, new_price, sender=nft_owner)
    event = get_last_event(renting_contract, "ListingPriceChanged")

    # assert vault_contract.listing() == (token_id, new_price, True)
    assert vault_contract.listing() == (token_id, new_price)

    assert event.vault == vault_addr
    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.token_id == token_id
    assert event.price == new_price


def test_cancel_listing(renting_contract, nft_contract, nft_owner, vault_contract_def):
    token_id = 1
    price = int(1e18)

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vault_and_deposit(token_id, price, sender=nft_owner)
    vault_contract = vault_contract_def.at(vault_addr)

    # renting_contract.create_listing(token_id, price, sender=nft_owner)
    # assert vault_contract.listing() == (token_id, price, True)
    assert vault_contract.listing() == (token_id, price)

    renting_contract.cancel_listing(token_id, sender=nft_owner)
    event = get_last_event(renting_contract, "ListingCancelled")
    
    # assert vault_contract.listing() == (0, 0, False)
    assert vault_contract.listing() == (token_id, 0)

    assert event.vault == vault_addr
    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.token_id == token_id


def test_start_rental(renting_contract, nft_contract, ape_contract, nft_owner, renter, vault_contract_def):
    token_id = 1
    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    expiration = start_time + 10
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vault_and_deposit(token_id, price, sender=nft_owner)
    vault_contract = vault_contract_def.at(vault_addr)

    # renting_contract.create_listing(token_id, price, sender=nft_owner)
    # assert vault_contract.listing() == (token_id, price, True)

    renting_contract.start_rental(token_id, expiration, sender=renter)
    event = get_last_event(renting_contract, "RentalStarted")

    active_rental = Rental(*vault_contract.active_rental())
    assert active_rental.owner == nft_owner
    assert active_rental.renter == renter
    assert active_rental.token_id == token_id
    assert active_rental.start == start_time
    assert active_rental.expiration == expiration
    assert active_rental.amount == rental_amount

    assert event.vault == vault_addr
    assert event.owner == nft_owner
    assert event.renter == renter
    assert event.nft_contract == nft_contract.address
    assert event.token_id == token_id
    assert event.start == start_time
    assert event.expiration == expiration
    assert event.amount == rental_amount


def test_close_rental(renting_contract, nft_contract, ape_contract, nft_owner, renter, vault_contract_def):
    token_id = 1
    price = int(1e18)
    start_time = int(boa.eval("block.timestamp"))
    expiration = start_time + 60
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vault_and_deposit(token_id, price, sender=nft_owner)
    vault_contract = vault_contract_def.at(vault_addr)

    # renting_contract.create_listing(token_id, price, sender=nft_owner)
    # assert vault_contract.listing() == (token_id, price, True)

    renting_contract.start_rental(token_id, expiration, sender=renter)

    active_rental = Rental(*vault_contract.active_rental())
    assert active_rental.owner == nft_owner
    assert active_rental.renter == renter
    assert active_rental.token_id == token_id
    assert active_rental.start == start_time
    assert active_rental.expiration == expiration
    assert active_rental.amount == rental_amount

    time_passed = 30
    boa.env.time_travel(seconds=time_passed)
    real_expiration = int(boa.eval("block.timestamp"))
    real_rental_amount = int(Decimal(rental_amount) / Decimal(2))

    renting_contract.close_rental(token_id, sender=renter)
    event = get_last_event(renting_contract, "RentalClosedPrematurely")

    active_rental = Rental(*vault_contract.active_rental())
    assert active_rental.owner == nft_owner
    assert active_rental.renter == renter
    assert active_rental.token_id == token_id
    assert active_rental.start == start_time
    assert active_rental.expiration == real_expiration
    assert active_rental.amount == 0

    assert vault_contract.unclaimed_rewards() == real_rental_amount
    assert vault_contract.claimable_rewards() == real_rental_amount

    assert event.vault == vault_addr
    assert event.owner == nft_owner
    assert event.renter == renter
    assert event.nft_contract == nft_contract.address
    assert event.token_id == token_id
    assert event.start == start_time
    assert event.expiration == real_expiration
    assert event.amount == real_rental_amount


def test_claim(renting_contract, nft_contract, ape_contract, nft_owner, renter, vault_contract_def):
    token_id = 1
    price = int(1e18)
    start_time = int(boa.eval("block.timestamp"))
    expiration = start_time + 60
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vault_and_deposit(token_id, price, sender=nft_owner)
    vault_contract = vault_contract_def.at(vault_addr)

    # renting_contract.create_listing(token_id, price, sender=nft_owner)
    # assert vault_contract.listing() == (token_id, price, True)

    renting_contract.start_rental(token_id, expiration, sender=renter)

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.claimable_rewards() == 0

    time_passed = 61
    boa.env.time_travel(seconds=time_passed)

    active_rental = Rental(*vault_contract.active_rental())
    assert active_rental.owner == nft_owner
    assert active_rental.renter == renter
    assert active_rental.token_id == token_id
    assert active_rental.start == start_time
    assert active_rental.expiration == expiration
    assert active_rental.amount == rental_amount

    assert vault_contract.claimable_rewards() == rental_amount
    assert vault_contract.unclaimed_rewards() == 0

    renting_contract.claim(token_id, sender=nft_owner)
    event = get_last_event(renting_contract, "RewardsClaimed")

    active_rental = Rental(*vault_contract.active_rental())
    assert active_rental.amount == 0
    assert vault_contract.claimable_rewards() == 0
    assert vault_contract.unclaimed_rewards() == 0

    assert event.vault == vault_addr
    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.token_id == token_id
    assert event.amount == rental_amount


def test_withdraw(renting_contract, nft_contract, ape_contract, nft_owner, renter):
    token_id = 1
    price = int(1e18)
    start_time = int(boa.eval("block.timestamp"))
    expiration = start_time + 60
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vault_and_deposit(token_id, price, sender=nft_owner)
    # renting_contract.create_listing(token_id, price, sender=nft_owner)
    renting_contract.start_rental(token_id, expiration, sender=renter)

    time_passed = 61
    boa.env.time_travel(seconds=time_passed)

    renting_contract.withdraw(token_id, sender=nft_owner)
    event = get_last_event(renting_contract, "NFTWithdrawn")

    assert renting_contract.active_vaults(token_id) == ZERO_ADDRESS
    # assert renting_contract.available_vaults(0) == vault_addr

    assert event.vault == vault_addr
    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.token_id == token_id
    assert event.claimed_rewards == rental_amount


def test_deposit_no_vaults(renting_contract, nft_contract, nft_owner, renter):
    token_id = 1
    price = 1

    with boa.reverts("vault is not available"):
        renting_contract.deposit(token_id, price, sender=nft_owner)


def test_deposit_already_deposited(renting_contract, nft_contract, nft_owner, renter):
    token_id = 1
    price = 1

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vault_and_deposit(token_id, price, sender=nft_owner)

    with boa.reverts("vault is not available"):
        renting_contract.deposit(token_id, price, sender=nft_owner)


def test_deposit(renting_contract, nft_contract, ape_contract, nft_owner, renter):
    token_id = 1
    price = int(1e18)
    start_time = int(boa.eval("block.timestamp"))
    expiration = start_time + 60
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vault_and_deposit(token_id, price, sender=nft_owner)

    assert nft_contract.ownerOf(token_id) == vault_addr

    renting_contract.start_rental(token_id, expiration, sender=renter)

    time_passed = 61
    boa.env.time_travel(seconds=time_passed)

    renting_contract.withdraw(token_id, sender=nft_owner)

    assert renting_contract.active_vaults(token_id) == ZERO_ADDRESS
    assert renting_contract.tokenid_to_vault(token_id) == vault_addr
    assert renting_contract.is_vault_available(token_id)
    assert nft_contract.ownerOf(token_id) == nft_owner

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit(token_id, price, sender=nft_owner)

    assert renting_contract.active_vaults(token_id) == vault_addr
    assert not renting_contract.is_vault_available(token_id)
    assert nft_contract.ownerOf(token_id) == vault_addr