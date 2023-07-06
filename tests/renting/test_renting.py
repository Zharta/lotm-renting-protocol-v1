import boa

from datetime import datetime as dt
from decimal import Decimal
from ..conftest_base import ZERO_ADDRESS, get_last_event, get_vault_from_proxy


def test_initial_state(
    vault_contract,
    renting_contract,
    nft_contract,
    ape_contract,
    delegation_registry_warm_contract,
):
    assert renting_contract.vault_impl_addr() == vault_contract.address
    assert renting_contract.payment_token_addr() == ape_contract.address
    assert renting_contract.nft_contract_addr() == nft_contract.address
    assert renting_contract.delegation_registry_addr() == delegation_registry_warm_contract.address


def test_create_vault_and_deposit_not_approved(
    contracts_config, renting_contract, nft_owner
):
    token_id = 1
    with boa.reverts("not approved for token"):
        renting_contract.create_vault_and_deposit(token_id, sender=nft_owner)


def test_create_vault_and_deposit(
    contracts_config, renting_contract, nft_contract, nft_owner, vault_contract
):
    token_id = 1

    assert renting_contract.active_vaults(token_id) == ZERO_ADDRESS

    vault_addr = renting_contract.get_vault_to_approve(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vault_and_deposit(token_id, sender=nft_owner)

    assert renting_contract.active_vaults(token_id) == vault_addr


def test_create_listing(contracts_config, renting_contract, nft_contract, nft_owner):
    token_id = 1
    price = int(1e18)

    vault_addr = renting_contract.get_vault_to_approve(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vault_and_deposit(token_id, sender=nft_owner)
    vault_contract = get_vault_from_proxy(vault_addr)

    renting_contract.create_listing(token_id, int(1e18), sender=nft_owner)

    assert renting_contract.active_vaults(token_id) == vault_addr
    assert vault_contract.listing() == (token_id, price, True)


def test_change_listing_price(
    contracts_config, renting_contract, nft_contract, nft_owner
):
    token_id = 1
    price = int(1e18)
    new_price = int(2e18)

    vault_addr = renting_contract.get_vault_to_approve(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vault_and_deposit(token_id, sender=nft_owner)
    vault_contract = get_vault_from_proxy(vault_addr)

    renting_contract.create_listing(token_id, price, sender=nft_owner)
    assert vault_contract.listing() == (token_id, price, True)

    renting_contract.change_listing_price(token_id, new_price, sender=nft_owner)
    assert vault_contract.listing() == (token_id, new_price, True)


def test_cancel_listing(contracts_config, renting_contract, nft_contract, nft_owner):
    token_id = 1
    price = int(1e18)

    vault_addr = renting_contract.get_vault_to_approve(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vault_and_deposit(token_id, sender=nft_owner)
    vault_contract = get_vault_from_proxy(vault_addr)

    renting_contract.create_listing(token_id, price, sender=nft_owner)
    assert vault_contract.listing() == (token_id, price, True)

    renting_contract.cancel_listing(token_id, sender=nft_owner)
    assert vault_contract.listing() == (0, 0, False)


def test_start_rental(
    contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter
):
    token_id = 1
    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    expiration = start_time + 10
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    vault_addr = renting_contract.get_vault_to_approve(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vault_and_deposit(token_id, sender=nft_owner)
    vault_contract = get_vault_from_proxy(vault_addr)

    renting_contract.create_listing(token_id, price, sender=nft_owner)
    assert vault_contract.listing() == (token_id, price, True)

    renting_contract.start_rental(token_id, expiration, sender=renter)
    assert vault_contract.active_rental()[1:] == (
        renter,
        token_id,
        start_time,
        expiration,
        rental_amount,
    )


def test_close_rental(
    contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter
):
    token_id = 1
    price = int(1e18)
    start_time = int(boa.eval("block.timestamp"))
    expiration = start_time + 60
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    vault_addr = renting_contract.get_vault_to_approve(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vault_and_deposit(token_id, sender=nft_owner)
    vault_contract = get_vault_from_proxy(vault_addr)

    renting_contract.create_listing(token_id, price, sender=nft_owner)
    assert vault_contract.listing() == (token_id, price, True)

    renting_contract.start_rental(token_id, expiration, sender=renter)
    assert vault_contract.active_rental()[1:] == (
        renter,
        token_id,
        start_time,
        expiration,
        rental_amount,
    )

    time_passed = 30
    boa.env.time_travel(seconds=time_passed)

    renting_contract.close_rental(token_id, sender=renter)

    assert vault_contract.active_rental()[1] == renter
    assert vault_contract.active_rental()[2] == token_id
    assert vault_contract.active_rental()[3] == start_time
    assert vault_contract.active_rental()[4] == int(boa.eval("block.timestamp"))
    assert vault_contract.active_rental()[5] == int(Decimal(rental_amount) / Decimal(2))
    assert vault_contract.unclaimed_rewards() == int(
        Decimal(rental_amount) / Decimal(2)
    )
    assert vault_contract.claimable_rewards() == int(
        Decimal(rental_amount) / Decimal(2)
    )


def test_claim(
    contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter
):
    token_id = 1
    price = int(1e18)
    start_time = int(boa.eval("block.timestamp"))
    expiration = start_time + 60
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    vault_addr = renting_contract.get_vault_to_approve(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vault_and_deposit(token_id, sender=nft_owner)
    vault_contract = get_vault_from_proxy(vault_addr)

    renting_contract.create_listing(token_id, price, sender=nft_owner)
    assert vault_contract.listing() == (token_id, price, True)

    renting_contract.start_rental(token_id, expiration, sender=renter)

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.claimable_rewards() == 0

    time_passed = 61
    boa.env.time_travel(seconds=time_passed)

    assert vault_contract.active_rental()[1] == renter
    assert vault_contract.active_rental()[2] == token_id
    assert vault_contract.active_rental()[3] == start_time
    assert vault_contract.active_rental()[4] == expiration
    assert vault_contract.active_rental()[5] == rental_amount
    assert vault_contract.claimable_rewards() == rental_amount
    assert vault_contract.unclaimed_rewards() == 0

    renting_contract.claim(token_id, sender=nft_owner)

    assert vault_contract.active_rental()[5] == 0
    assert vault_contract.claimable_rewards() == 0
    assert vault_contract.unclaimed_rewards() == 0


def test_withdraw(
    contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter
):
    token_id = 1
    price = int(1e18)
    start_time = int(boa.eval("block.timestamp"))
    expiration = start_time + 60
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    vault_addr = renting_contract.get_vault_to_approve(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vault_and_deposit(token_id, sender=nft_owner)
    renting_contract.create_listing(token_id, price, sender=nft_owner)
    renting_contract.start_rental(token_id, expiration, sender=renter)

    time_passed = 61
    boa.env.time_travel(seconds=time_passed)

    renting_contract.withdraw(token_id, sender=nft_owner)

    assert renting_contract.active_vaults(token_id) == ZERO_ADDRESS
    assert renting_contract.available_vaults(0) == vault_addr


def test_deposit_no_vaults(
    contracts_config, renting_contract, nft_contract, nft_owner, renter
):
    token_id = 1

    with boa.reverts("no available vaults"):
        renting_contract.deposit(token_id, sender=nft_owner)


def test_deposit_already_deposited(
    contracts_config, renting_contract, nft_contract, nft_owner, renter
):
    token_id = 1

    vault_addr = renting_contract.get_vault_to_approve(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vault_and_deposit(token_id, sender=nft_owner)

    with boa.reverts("not owner of token"):
        renting_contract.deposit(token_id, sender=nft_owner)


def test_deposit(
    contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter
):
    token_id = 1
    price = int(1e18)
    start_time = int(boa.eval("block.timestamp"))
    expiration = start_time + 60
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    vault_addr = renting_contract.get_vault_to_approve(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vault_and_deposit(token_id, sender=nft_owner)

    assert nft_contract.ownerOf(token_id) == vault_addr

    renting_contract.create_listing(token_id, price, sender=nft_owner)
    renting_contract.start_rental(token_id, expiration, sender=renter)

    time_passed = 61
    boa.env.time_travel(seconds=time_passed)

    renting_contract.withdraw(token_id, sender=nft_owner)

    assert renting_contract.active_vaults(token_id) == ZERO_ADDRESS
    assert renting_contract.available_vaults(0) == vault_addr
    assert renting_contract.get_vault_to_approve(token_id) == vault_addr
    assert nft_contract.ownerOf(token_id) == nft_owner

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit(token_id, sender=nft_owner)

    assert renting_contract.active_vaults(token_id) == vault_addr
    assert renting_contract.get_available_vaults() == []
    assert nft_contract.ownerOf(token_id) == vault_addr
