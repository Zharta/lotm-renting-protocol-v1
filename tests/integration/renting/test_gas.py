import boa

from ...conftest_base import (
    ZERO_ADDRESS,
    Listing,
    Rental,
    RentalLog,
    TokenContext,
    VaultLog,
    get_last_event,
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


def test_deposit_without_delegation(contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter):
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

    renting_contract.create_vaults_and_deposit([token_id], price, min_duration, max_duration, False, sender=nft_owner)

    assert nft_contract.ownerOf(token_id) == vault_addr
    renting_contract.start_rentals([token_context.to_tuple()], duration, sender=renter)

    event = get_last_event(renting_contract, "RentalStarted")
    rental_log = RentalLog(*event.rentals[0])

    token_context.active_rental = Rental(
        rental_log.id,
        nft_owner,
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

    renting_contract.deposit([token_id], price, min_duration, max_duration, False, sender=nft_owner)
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


def test_deposit_with_delegation(contracts_config, renting_contract, nft_contract, ape_contract, nft_owner, renter):
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

    renting_contract.create_vaults_and_deposit([token_id], price, min_duration, max_duration, False, sender=nft_owner)

    assert nft_contract.ownerOf(token_id) == vault_addr
    renting_contract.start_rentals([token_context.to_tuple()], duration, sender=renter)

    event = get_last_event(renting_contract, "RentalStarted")
    rental_log = RentalLog(*event.rentals[0])

    token_context.active_rental = Rental(
        rental_log.id,
        nft_owner,
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

    renting_contract.deposit([token_id], price, min_duration, max_duration, True, sender=nft_owner)
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
