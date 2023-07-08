import boa

from datetime import datetime as dt
from decimal import Decimal
from ..conftest_base import ZERO_ADDRESS, Rental


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
    nft_contract,
    ape_contract,
):
    with boa.reverts("already initialised"):
        vault_contract.initialise(
            nft_owner,
            renting_contract.address,
            ape_contract,
            nft_contract,
            ZERO_ADDRESS,
            sender=renting_contract.address,
        )


def test_deposit_not_caller(contracts_config, vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.deposit(1, sender=nft_owner)


def test_deposit_not_owner(
    contracts_config,
    vault_contract,
    renting_contract,
    nft_contract,
    owner,
    nft_owner,
):
    nft_contract.mint(renting_contract.address, 2, sender=owner)
    with boa.reverts("not owner of token"):
        vault_contract.deposit(2, sender=renting_contract.address)


def test_deposit_not_approved(contracts_config, vault_contract, renting_contract):
    with boa.reverts("not approved for token"):
        vault_contract.deposit(1, sender=renting_contract.address)


def test_deposit(
    contracts_config, vault_contract, nft_owner, renting_contract, nft_contract
):
    token_id = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, sender=renting_contract.address)

    assert nft_contract.ownerOf(token_id) == vault_contract.address
    assert vault_contract.listing() == (token_id, 0, False)


def test_create_listing_not_caller(contracts_config, vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.create_listing(nft_owner, 1, sender=nft_owner)


def test_create_listing_not_owner(
    contracts_config, vault_contract, renting_contract, nft_owner
):
    with boa.reverts("not owner of vault"):
        vault_contract.create_listing(
            renting_contract.address, 1, sender=renting_contract.address
        )


def test_create_listing_zero_price(
    contracts_config, vault_contract, renting_contract, nft_owner
):
    with boa.reverts("price must be greater than 0"):
        vault_contract.create_listing(nft_owner, 0, sender=renting_contract.address)


def test_create_listing(
    contracts_config, vault_contract, renting_contract, nft_contract, nft_owner
):
    token_id = 1
    price = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, sender=renting_contract.address)

    vault_contract.create_listing(nft_owner, price, sender=renting_contract.address)

    assert vault_contract.listing() == (1, price, True)


def test_create_listing_twice(
    contracts_config, vault_contract, renting_contract, nft_contract, nft_owner
):
    token_id = 1
    price = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, sender=renting_contract.address)

    vault_contract.create_listing(nft_owner, price, sender=renting_contract.address)
    with boa.reverts("listing already exists"):
        vault_contract.create_listing(nft_owner, price, sender=renting_contract.address)


def test_change_listing_price_not_caller(contracts_config, vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.change_listing_price(nft_owner, 1, sender=nft_owner)


def test_change_listing_price_zero_price(
    contracts_config, vault_contract, renting_contract, nft_owner
):
    with boa.reverts("price must be greater than 0"):
        vault_contract.change_listing_price(
            nft_owner, 0, sender=renting_contract.address
        )


def test_change_listing_price_no_listing(
    contracts_config, vault_contract, renting_contract, nft_owner
):
    with boa.reverts("listing does not exist"):
        vault_contract.change_listing_price(
            nft_owner, 1, sender=renting_contract.address
        )


def test_change_listing_price(
    contracts_config, vault_contract, renting_contract, nft_contract, nft_owner
):
    token_id = 1
    price = 1
    new_price = 2

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, sender=renting_contract.address)
    vault_contract.create_listing(nft_owner, price, sender=renting_contract.address)

    vault_contract.change_listing_price(
        nft_owner, new_price, sender=renting_contract.address
    )

    assert vault_contract.listing() == (1, new_price, True)



def test_cancel_listing_not_caller(contracts_config, vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.cancel_listing(nft_owner, sender=nft_owner)


def test_cancel_listing_no_listing(
    contracts_config, vault_contract, renting_contract, nft_owner
):
    with boa.reverts("listing does not exist"):
        vault_contract.cancel_listing(nft_owner, sender=renting_contract.address)


def test_cancel_listing(
    contracts_config, vault_contract, renting_contract, nft_contract, nft_owner
):
    token_id = 1
    price = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, sender=renting_contract.address)
    vault_contract.create_listing(nft_owner, price, sender=renting_contract.address)

    vault_contract.cancel_listing(nft_owner, sender=renting_contract.address)

    assert vault_contract.listing() == (0, 0, False)


def test_start_rental_not_caller(contracts_config, vault_contract, nft_owner, renter):
    with boa.reverts("not caller"):
        vault_contract.start_rental(renter, 1, sender=nft_owner)


def test_start_rental_no_listing(
    contracts_config, vault_contract, renting_contract, renter
):
    with boa.reverts("listing does not exist"):
        vault_contract.start_rental(renter, 1, sender=renting_contract.address)


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
    vault_contract.deposit(token_id, sender=renting_contract.address)
    vault_contract.create_listing(nft_owner, price, sender=renting_contract.address)

    with boa.reverts("insufficient allowance"):
        vault_contract.start_rental(renter, expiration, sender=renting_contract.address)


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
    vault_contract.deposit(token_id, sender=renting_contract.address)
    vault_contract.create_listing(nft_owner, price, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    vault_contract.start_rental(renter, expiration, sender=renting_contract.address)

    active_rental = Rental(*vault_contract.active_rental()[1:])
    assert active_rental.owner == nft_owner
    assert active_rental.renter == renter
    assert active_rental.token_id == token_id
    assert active_rental.start == start_time
    assert active_rental.expiration == expiration
    assert active_rental.amount == rental_amount

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
    vault_contract.deposit(token_id, sender=renting_contract.address)
    vault_contract.create_listing(nft_owner, price, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    vault_contract.start_rental(renter, expiration, sender=renting_contract.address)
    with boa.reverts("active rental ongoing"):
        vault_contract.start_rental(renter, expiration, sender=renting_contract.address)


def test_close_rental_not_caller(contracts_config, vault_contract, nft_owner, renter):
    with boa.reverts("not caller"):
        vault_contract.close_rental(renter, sender=nft_owner)


def test_close_rental_no_active_rental(
    contracts_config, vault_contract, renting_contract, renter
):
    boa.env.time_travel(seconds=1)
    with boa.reverts("active rental does not exist"):
        vault_contract.close_rental(renter, sender=renting_contract.address)


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
    vault_contract.deposit(token_id, sender=renting_contract.address)
    vault_contract.create_listing(nft_owner, price, sender=renting_contract.address)

    start_time = int(boa.eval("block.timestamp"))
    rental_amount = int(
        Decimal(expiration - start_time) / Decimal(3600) * Decimal(price)
    )
    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    vault_contract.start_rental(renter, expiration, sender=renting_contract.address)

    time_passed = 43200
    boa.env.time_travel(seconds=time_passed)
    real_expiration = boa.eval("block.timestamp")
    real_rental_amount = int(Decimal(rental_amount) / Decimal(2))

    vault_contract.close_rental(renter, sender=renting_contract.address)

    active_rental = Rental(*vault_contract.active_rental()[1:])
    assert active_rental.owner == nft_owner
    assert active_rental.renter == renter
    assert active_rental.token_id == token_id
    assert active_rental.start == start_time
    assert active_rental.expiration == real_expiration
    assert active_rental.amount == real_rental_amount

    assert vault_contract.claimable_rewards() == int(
        Decimal(rental_amount) / Decimal(2)
    )


def test_claim_not_caller(contracts_config, vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.claim(nft_owner, sender=nft_owner)


def test_claim_no_rewards(
    contracts_config, vault_contract, renting_contract, nft_owner
):
    with boa.reverts("no rewards to claim"):
        vault_contract.claim(nft_owner, sender=renting_contract.address)


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
    vault_contract.deposit(token_id, sender=renting_contract.address)
    vault_contract.create_listing(nft_owner, price, sender=renting_contract.address)

    start_time = int(boa.eval("block.timestamp"))
    rental_amount = int(
        Decimal(expiration - start_time) / Decimal(3600) * Decimal(price)
    )
    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    vault_contract.start_rental(renter, expiration, sender=renting_contract.address)

    boa.env.time_travel(seconds=86401)

    assert vault_contract.claimable_rewards() == rental_amount

    vault_contract.claim(nft_owner, sender=renting_contract.address)

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.claimable_rewards() == 0


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
    vault_contract.deposit(token_id, sender=renting_contract.address)
    vault_contract.create_listing(nft_owner, price, sender=renting_contract.address)

    start_time = int(boa.eval("block.timestamp"))
    rental_amount = int(
        Decimal(expiration - start_time) / Decimal(3600) * Decimal(price)
    )
    ape_contract.approve(vault_contract, rental_amount, sender=renter)
    vault_contract.start_rental(renter, expiration, sender=renting_contract.address)

    boa.env.time_travel(seconds=86401)

    assert vault_contract.claimable_rewards() == rental_amount

    ape_contract.approve(vault_contract, rental_amount, sender=renter)
    vault_contract.start_rental(
        renter,
        int(boa.eval("block.timestamp")) + 86400,
        sender=renting_contract.address,
    )

    assert vault_contract.unclaimed_rewards() == rental_amount

    boa.env.time_travel(seconds=86401)

    assert vault_contract.claimable_rewards() == rental_amount * 2

    vault_contract.claim(nft_owner, sender=renting_contract.address)

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.claimable_rewards() == 0


def test_withdraw_not_caller(contracts_config, vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.withdraw(nft_owner, sender=nft_owner)


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
    vault_contract.deposit(token_id, sender=renting_contract.address)
    vault_contract.create_listing(nft_owner, price, sender=renting_contract.address)

    start_time = int(boa.eval("block.timestamp"))
    rental_amount = int(
        Decimal(expiration - start_time) / Decimal(3600) * Decimal(price)
    )
    ape_contract.approve(vault_contract, rental_amount, sender=renter)
    vault_contract.start_rental(renter, expiration, sender=renting_contract.address)

    with boa.reverts("active rental ongoing"):
        vault_contract.withdraw(nft_owner, sender=renting_contract.address)


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
    vault_contract.deposit(token_id, sender=renting_contract.address)
    vault_contract.create_listing(nft_owner, price, sender=renting_contract.address)

    start_time = int(boa.eval("block.timestamp"))
    rental_amount = int(
        Decimal(expiration - start_time) / Decimal(3600) * Decimal(price)
    )
    ape_contract.approve(vault_contract, rental_amount, sender=renter)
    vault_contract.start_rental(renter, expiration, sender=renting_contract.address)

    boa.env.time_travel(seconds=86401)

    assert vault_contract.claimable_rewards() == rental_amount

    vault_contract.withdraw(nft_owner, sender=renting_contract.address)

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.claimable_rewards() == 0
    assert vault_contract.listing() == (0, 0, False)

    active_rental = Rental(*vault_contract.active_rental()[1:])
    assert active_rental.owner == ZERO_ADDRESS
    assert active_rental.renter == ZERO_ADDRESS
    assert active_rental.token_id == 0
    assert active_rental.start == 0
    assert active_rental.expiration == 0
    assert active_rental.amount == 0

    assert not vault_contract.is_initialised()
    assert vault_contract.owner() == ZERO_ADDRESS

    assert nft_contract.ownerOf(token_id) == nft_owner
    assert ape_contract.balanceOf(renting_contract.address) == 0
    assert ape_contract.balanceOf(nft_owner) == rental_amount
