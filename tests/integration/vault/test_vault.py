from decimal import Decimal

import boa

from ...conftest_base import (
    ZERO_ADDRESS,
    ZERO_BYTES32,
    Listing,
    Rental,
    VaultState,
    compute_state_hash,
)


def test_initial_state(
    contracts_config,
    vault_contract,
    nft_owner,
    renting_contract,
    nft_contract,
    ape_contract,
):
    assert vault_contract.owner() == nft_owner
    assert vault_contract.caller() == renting_contract.address
    assert vault_contract.is_initialised()
    assert vault_contract.nft_contract_addr() == nft_contract.address
    assert vault_contract.payment_token_addr() == ape_contract.address


def test_initialise_twice(
    contracts_config,
    vault_contract,
    renting_contract,
    nft_owner,
):
    with boa.reverts("already initialised"):
        vault_contract.initialise(nft_owner, sender=renting_contract.address)


def test_deposit_not_caller(contracts_config, vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.deposit(1, 1, 0, 0, ZERO_ADDRESS, sender=nft_owner)


def test_deposit_not_owner(
    contracts_config,
    vault_contract,
    renting_contract,
    nft_contract,
    owner,
    nft_owner,
):
    nft_contract.mint(renting_contract.address, 100, sender=owner)
    with boa.reverts():
        vault_contract.deposit(100, 1, 0, 0, ZERO_ADDRESS, sender=renting_contract.address)


def test_deposit_not_approved(contracts_config, vault_contract, renting_contract):
    with boa.reverts():
        vault_contract.deposit(1, 1, 0, 0, ZERO_ADDRESS, sender=renting_contract.address)


def test_deposit_without_delegation(
    contracts_config, vault_contract, nft_owner, renting_contract, nft_contract, delegation_registry_warm_contract
):
    token_id = 1
    price = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, 0, 0, ZERO_ADDRESS, sender=renting_contract.address)

    assert nft_contract.ownerOf(token_id) == vault_contract.address

    assert vault_contract.state() == compute_state_hash(Rental(), Listing(token_id, price, 0, 0))
    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == ZERO_ADDRESS


def test_deposit_with_delegation(
    contracts_config, vault_contract, nft_owner, renting_contract, nft_contract, delegation_registry_warm_contract
):
    token_id = 1
    price = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, 0, 0, nft_owner, sender=renting_contract.address)

    assert nft_contract.ownerOf(token_id) == vault_contract.address

    assert vault_contract.state() == compute_state_hash(Rental(), Listing(token_id, price, 0, 0))
    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == nft_owner


def test_set_listing_not_caller(contracts_config, vault_contract, nft_owner):
    vault_state = VaultState(Rental(), Listing())

    with boa.reverts("not caller"):
        vault_contract.set_listing(vault_state.to_tuple(), 0, nft_owner, 1, 0, 0, ZERO_ADDRESS, sender=nft_owner)


def test_change_listing(contracts_config, vault_contract, renting_contract, nft_contract, nft_owner):
    token_id = 1
    price = 1
    new_price = 2
    min_duration = 0
    max_duration = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, 0, 0, ZERO_ADDRESS, sender=renting_contract.address)

    state_listing = Listing(token_id, price, 0, 0)
    vault_state = VaultState(Rental(), state_listing)

    vault_contract.set_listing(
        vault_state.to_tuple(),
        token_id,
        nft_owner,
        new_price,
        min_duration,
        max_duration,
        ZERO_ADDRESS,
        sender=renting_contract.address,
    )

    assert vault_contract.state() == compute_state_hash(Rental(), Listing(token_id, new_price, min_duration, max_duration))


def test_set_listing_and_delegate_to_wallet(
    contracts_config, vault_contract, renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract
):
    token_id = 1
    price = 1
    new_price = 2
    min_duration = 0
    max_duration = 1

    delegate = boa.env.generate_address("delegate")

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, 0, 0, nft_owner, sender=renting_contract.address)

    state_listing = Listing(token_id, price, 0, 0)
    vault_state = VaultState(Rental(), state_listing)

    delegation_registry_warm_contract.setHotWallet(ZERO_ADDRESS, 0, False, sender=vault_contract.address)

    vault_contract.set_listing(
        vault_state.to_tuple(), token_id, nft_owner, new_price, 0, 0, ZERO_ADDRESS, sender=renting_contract.address
    )
    vault_state.listing.price = new_price

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == ZERO_ADDRESS

    vault_contract.set_listing(
        vault_state.to_tuple(),
        token_id,
        nft_owner,
        new_price,
        min_duration,
        max_duration,
        delegate,
        sender=renting_contract.address,
    )

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == delegate
    assert vault_contract.state() == compute_state_hash(Rental(), Listing(token_id, new_price, min_duration, max_duration))


def test_cancel_listing_not_caller(contracts_config, vault_contract, nft_owner):
    vault_state = VaultState(Rental(), Listing())

    with boa.reverts("not caller"):
        vault_contract.set_listing(vault_state.to_tuple(), 0, nft_owner, 0, 0, 0, ZERO_ADDRESS, sender=nft_owner)


def test_cancel_listing(contracts_config, vault_contract, renting_contract, nft_contract, nft_owner):
    token_id = 1
    price = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, 0, 0, ZERO_ADDRESS, sender=renting_contract.address)

    state_listing = Listing(token_id, price, 0, 0)
    vault_state = VaultState(Rental(), state_listing)

    vault_contract.set_listing(
        vault_state.to_tuple(), token_id, nft_owner, 0, 0, 0, ZERO_ADDRESS, sender=renting_contract.address
    )

    assert vault_contract.state() == compute_state_hash(Rental(), Listing(token_id, 0, 0, 0))


def test_start_rental_not_caller(contracts_config, vault_contract, nft_owner, renter):
    vault_state = VaultState(Rental(), Listing())
    with boa.reverts("not caller"):
        vault_contract.start_rental(vault_state.to_tuple(), renter, 1, renter, sender=nft_owner)


def test_start_rental_no_listing(contracts_config, vault_contract, renting_contract, renter):
    vault_state = VaultState(Rental(), Listing())
    with boa.reverts("listing does not exist"):
        vault_contract.start_rental(vault_state.to_tuple(), renter, 1, renter, sender=renting_contract.address)


def test_start_rental_invalid_state(
    contracts_config,
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
):
    token_id = 1
    price = 1
    expiration = int(boa.eval("block.timestamp")) + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, 0, 0, ZERO_ADDRESS, sender=renting_contract.address)

    state_listing = Listing(token_id, price * 2, 0, 0)
    vault_state = VaultState(Rental(), state_listing)

    with boa.reverts("invalid state"):
        vault_contract.start_rental(vault_state.to_tuple(), renter, expiration, renter, sender=renting_contract.address)


def test_start_rental_insufficient_allowance(
    contracts_config,
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
):
    token_id = 1
    price = 1
    expiration = int(boa.eval("block.timestamp")) + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, 0, 0, ZERO_ADDRESS, sender=renting_contract.address)

    state_listing = Listing(token_id, price, 0, 0)
    vault_state = VaultState(Rental(), state_listing)

    with boa.reverts("insufficient allowance"):
        vault_contract.start_rental(vault_state.to_tuple(), renter, expiration, renter, sender=renting_contract.address)


def test_start_rental(
    contracts_config,
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
    delegation_registry_warm_contract,
):
    token_id = 1
    price = int(1e18)
    expiration = int(boa.eval("block.timestamp")) + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, 0, 0, ZERO_ADDRESS, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) * Decimal(price) / Decimal(3600))

    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    state_listing = Listing(token_id, price, 0, 0)
    vault_state = VaultState(Rental(), state_listing)

    active_rental = vault_contract.start_rental(
        vault_state.to_tuple(), renter, expiration, renter, sender=renting_contract.address
    )
    vault_state.active_rental = Rental(*active_rental)

    assert vault_contract.state() == compute_state_hash(vault_state.active_rental, vault_state.listing)
    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == renter


def test_start_rental_ongoing(
    contracts_config,
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
):
    token_id = 1
    price = int(1e18)
    expiration = int(boa.eval("block.timestamp")) + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, 0, 0, ZERO_ADDRESS, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) * Decimal(price) / Decimal(3600))

    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    state_listing = Listing(token_id, price, 0, 0)
    vault_state = VaultState(Rental(), state_listing)

    active_rental = vault_contract.start_rental(
        vault_state.to_tuple(), renter, expiration, renter, sender=renting_contract.address
    )
    vault_state.active_rental = Rental(*active_rental)

    with boa.reverts("active rental ongoing"):
        vault_contract.start_rental(vault_state.to_tuple(), renter, expiration, renter, sender=renting_contract.address)


def test_close_rental_not_caller(contracts_config, vault_contract, nft_owner, renter):
    vault_state = VaultState(Rental(), Listing())

    with boa.reverts("not caller"):
        vault_contract.close_rental(vault_state.to_tuple(), renter, sender=nft_owner)


def test_close_rental_no_active_rental(contracts_config, vault_contract, renting_contract, renter):
    boa.env.time_travel(seconds=1)
    vault_state = VaultState(Rental(), Listing())
    with boa.reverts("active rental does not exist"):
        vault_contract.close_rental(vault_state.to_tuple(), renter, sender=renting_contract.address)


def test_close_rental(
    contracts_config,
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
):
    token_id = 1
    price = int(1e18)
    expiration = int(boa.eval("block.timestamp")) + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, 0, 0, ZERO_ADDRESS, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) / Decimal(3600) * Decimal(price))
    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    state_listing = Listing(token_id, price, 0, 0)
    vault_state = VaultState(Rental(), state_listing)

    active_rental = vault_contract.start_rental(
        vault_state.to_tuple(), renter, expiration, renter, sender=renting_contract.address
    )
    vault_state.active_rental = Rental(*active_rental)

    time_passed = 43200
    boa.env.time_travel(seconds=time_passed)
    real_rental_amount = int(Decimal(rental_amount) / Decimal(2))

    vault_state.listing = Listing(token_id, price, 0, 0)

    vault_contract.close_rental(vault_state.to_tuple(), renter, sender=renting_contract.address)

    assert vault_contract.state() == compute_state_hash(Rental(), Listing(token_id, price, 0, 0))

    assert vault_contract.claimable_rewards(Rental().to_tuple()) == real_rental_amount


def test_claim_not_caller(contracts_config, vault_contract, nft_owner):
    state_listing = Listing(1, 1, 0, 0)
    vault_state = VaultState(Rental(), state_listing)

    with boa.reverts("not caller"):
        vault_contract.claim(vault_state.to_tuple(), nft_owner, sender=nft_owner)


def test_claim_no_rewards(contracts_config, vault_contract, renting_contract, nft_owner):
    state_listing = Listing(0, 0, 0, 0)
    vault_state = VaultState(Rental(), state_listing)

    with boa.reverts("no rewards to claim"):
        vault_contract.claim(vault_state.to_tuple(), nft_owner, sender=renting_contract.address)


def test_claim(
    contracts_config,
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
):
    token_id = 1
    price = int(1e18)
    expiration = int(boa.eval("block.timestamp")) + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, 0, 0, ZERO_ADDRESS, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) / Decimal(3600) * Decimal(price))
    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    state_listing = Listing(token_id, price, 0, 0)
    vault_state = VaultState(Rental(), state_listing)

    active_rental = vault_contract.start_rental(
        vault_state.to_tuple(), renter, expiration, renter, sender=renting_contract.address
    )
    vault_state.active_rental = Rental(*active_rental)

    boa.env.time_travel(seconds=86401)

    assert vault_contract.claimable_rewards(active_rental) == rental_amount

    vault_contract.claim(vault_state.to_tuple(), nft_owner, sender=renting_contract.address)

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.claimable_rewards(Rental().to_tuple()) == 0


def test_claim2(
    contracts_config,
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
):
    token_id = 1
    price = int(1e18)
    expiration = int(boa.eval("block.timestamp")) + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, 0, 0, ZERO_ADDRESS, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) / Decimal(3600) * Decimal(price))
    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    state_listing = Listing(token_id, price, 0, 0)
    vault_state = VaultState(Rental(), state_listing)

    active_rental = vault_contract.start_rental(
        vault_state.to_tuple(), renter, expiration, renter, sender=renting_contract.address
    )
    vault_state.active_rental = Rental(*active_rental)

    boa.env.time_travel(seconds=86401)

    assert vault_contract.claimable_rewards(active_rental) == rental_amount

    ape_contract.approve(vault_contract, rental_amount, sender=renter)
    active_rental = vault_contract.start_rental(
        vault_state.to_tuple(),
        renter,
        int(boa.eval("block.timestamp")) + 86400,
        renter,
        sender=renting_contract.address,
    )
    vault_state.active_rental = Rental(*active_rental)

    assert vault_contract.unclaimed_rewards() == rental_amount

    boa.env.time_travel(seconds=86401)

    assert vault_contract.claimable_rewards(active_rental) == rental_amount * 2

    active_rental, rewards_to_claim = vault_contract.claim(vault_state.to_tuple(), nft_owner, sender=renting_contract.address)

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.claimable_rewards(active_rental) == 0
    assert rewards_to_claim == rental_amount * 2


def test_withdraw_not_caller(contracts_config, vault_contract, nft_owner):
    vault_state = VaultState(Rental(), Listing())

    with boa.reverts("not caller"):
        vault_contract.withdraw(vault_state.to_tuple(), nft_owner, sender=nft_owner)


def test_withdraw_rental_ongoing(
    contracts_config,
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
):
    token_id = 1
    price = int(1e18)
    expiration = int(boa.eval("block.timestamp")) + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, 0, 0, ZERO_ADDRESS, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) / Decimal(3600) * Decimal(price))
    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    state_listing = Listing(token_id, price, 0, 0)
    vault_state = VaultState(Rental(), state_listing)

    active_rental = vault_contract.start_rental(
        vault_state.to_tuple(), renter, expiration, renter, sender=renting_contract.address
    )
    vault_state.active_rental = Rental(*active_rental)

    with boa.reverts("active rental ongoing"):
        vault_contract.withdraw(vault_state.to_tuple(), nft_owner, sender=renting_contract.address)


def test_withdraw(
    contracts_config,
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
):
    token_id = 1
    price = int(1e18)
    expiration = int(boa.eval("block.timestamp")) + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, 0, 0, ZERO_ADDRESS, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) / Decimal(3600) * Decimal(price))
    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    state_listing = Listing(token_id, price, 0, 0)
    vault_state = VaultState(Rental(), state_listing)

    active_rental = vault_contract.start_rental(
        vault_state.to_tuple(), renter, expiration, renter, sender=renting_contract.address
    )
    vault_state.active_rental = Rental(*active_rental)

    boa.env.time_travel(seconds=86401)

    assert vault_contract.claimable_rewards(active_rental) == rental_amount

    vault_contract.withdraw(vault_state.to_tuple(), nft_owner, sender=renting_contract.address)

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.claimable_rewards(Rental().to_tuple()) == 0

    assert vault_contract.state() == ZERO_BYTES32

    assert not vault_contract.is_initialised()
    assert vault_contract.owner() == ZERO_ADDRESS

    assert nft_contract.ownerOf(token_id) == nft_owner
    assert ape_contract.balanceOf(renting_contract.address) == 0
    assert ape_contract.balanceOf(nft_owner) == rental_amount
