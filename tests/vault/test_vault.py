import boa

from datetime import datetime as dt
from decimal import Decimal
from ..conftest_base import ZERO_ADDRESS, get_last_event


# def test_load_contract_configs(contracts_config):
#     pass


def test_initial_state(
    contracts_config, vault_contract, nft_owner, lotm_renting_contract, nft_contract
):
    assert vault_contract.owner() == nft_owner
    assert vault_contract.caller() == lotm_renting_contract
    assert vault_contract.is_initialised()
    assert vault_contract.nft_contract_addr() == nft_contract.address


def test_initialise_twice(
    contracts_config,
    vault_contract,
    lotm_renting_contract,
    nft_owner,
    nft_contract,
    ape_contract,
):
    with boa.reverts("already initialised"):
        vault_contract.initialise(
            nft_owner,
            lotm_renting_contract,
            ape_contract,
            nft_contract,
            ZERO_ADDRESS,
            sender=lotm_renting_contract,
        )


def test_deposit_not_initialised(vault_contract, lotm_renting_contract):
    with boa.reverts("not initialised"):
        vault_contract.deposit(1, sender=lotm_renting_contract)


def test_deposit_not_caller(contracts_config, vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.deposit(1, sender=nft_owner)


def test_deposit_not_owner(
    contracts_config,
    vault_contract,
    lotm_renting_contract,
    nft_contract,
    owner,
    nft_owner,
):
    nft_contract.mint(lotm_renting_contract, 2, sender=owner)
    with boa.reverts("not owner of token"):
        vault_contract.deposit(2, sender=lotm_renting_contract)


def test_deposit_not_approved(contracts_config, vault_contract, lotm_renting_contract):
    with boa.reverts("not approved for token"):
        vault_contract.deposit(1, sender=lotm_renting_contract)


def test_deposit(
    contracts_config, vault_contract, nft_owner, lotm_renting_contract, nft_contract
):
    token_id = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, sender=lotm_renting_contract)
    event = get_last_event(vault_contract, name="NFTDeposited")

    assert nft_contract.ownerOf(token_id) == vault_contract.address
    assert vault_contract.listing() == (token_id, 0, False)

    assert event.owner == nft_owner
    assert event.token_id == token_id


def test_create_listing_not_caller(contracts_config, vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.create_listing(1, sender=nft_owner)


def test_create_listing_zero_price(
    contracts_config, vault_contract, lotm_renting_contract
):
    with boa.reverts("price must be greater than 0"):
        vault_contract.create_listing(0, sender=lotm_renting_contract)


def test_create_listing(
    contracts_config, vault_contract, lotm_renting_contract, nft_contract, nft_owner
):
    token_id = 1
    price = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, sender=lotm_renting_contract)

    vault_contract.create_listing(price, sender=lotm_renting_contract)
    event = get_last_event(vault_contract, name="ListingCreated")

    assert vault_contract.listing() == (1, price, True)

    assert event.owner == nft_owner
    assert event.token_id == token_id
    assert event.price == price


def test_create_listing_twice(
    contracts_config, vault_contract, lotm_renting_contract, nft_contract, nft_owner
):
    token_id = 1
    price = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, sender=lotm_renting_contract)

    vault_contract.create_listing(price, sender=lotm_renting_contract)
    with boa.reverts("listing already exists"):
        vault_contract.create_listing(price, sender=lotm_renting_contract)


def test_change_listing_price_not_caller(contracts_config, vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.change_listing_price(1, sender=nft_owner)


def test_change_listing_price_zero_price(
    contracts_config, vault_contract, lotm_renting_contract
):
    with boa.reverts("price must be greater than 0"):
        vault_contract.change_listing_price(0, sender=lotm_renting_contract)


def test_change_listing_price_no_listing(
    contracts_config, vault_contract, lotm_renting_contract
):
    with boa.reverts("listing does not exist"):
        vault_contract.change_listing_price(1, sender=lotm_renting_contract)


def test_change_listing_price(
    contracts_config, vault_contract, lotm_renting_contract, nft_contract, nft_owner
):
    token_id = 1
    price = 1
    new_price = 2

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, sender=lotm_renting_contract)
    vault_contract.create_listing(price, sender=lotm_renting_contract)

    vault_contract.change_listing_price(new_price, sender=lotm_renting_contract)
    event = get_last_event(vault_contract, name="ListingPriceChanged")

    assert vault_contract.listing() == (1, new_price, True)

    assert event.owner == nft_owner
    assert event.token_id == token_id
    assert event.price == new_price


def test_cancel_listing_not_caller(contracts_config, vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.cancel_listing(sender=nft_owner)


def test_cancel_listing_no_listing(
    contracts_config, vault_contract, lotm_renting_contract
):
    with boa.reverts("listing does not exist"):
        vault_contract.cancel_listing(sender=lotm_renting_contract)


def test_cancel_listing(
    contracts_config, vault_contract, lotm_renting_contract, nft_contract, nft_owner
):
    token_id = 1
    price = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, sender=lotm_renting_contract)
    vault_contract.create_listing(price, sender=lotm_renting_contract)

    vault_contract.cancel_listing(sender=lotm_renting_contract)
    event = get_last_event(vault_contract, name="ListingCancelled")

    assert vault_contract.listing() == (0, 0, False)

    assert event.owner == nft_owner
    assert event.token_id == token_id


def test_start_rental_not_caller(contracts_config, vault_contract, nft_owner, renter):
    with boa.reverts("not caller"):
        vault_contract.start_rental(renter, 1, sender=nft_owner)


def test_start_rental_no_listing(
    contracts_config, vault_contract, lotm_renting_contract, renter
):
    with boa.reverts("listing does not exist"):
        vault_contract.start_rental(renter, 1, sender=lotm_renting_contract)


def test_start_rental_insufficient_allowance(
    contracts_config,
    vault_contract,
    lotm_renting_contract,
    nft_contract,
    nft_owner,
    renter,
):
    token_id = 1
    price = 1
    expiration = int(boa.eval("block.timestamp")) + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, sender=lotm_renting_contract)
    vault_contract.create_listing(price, sender=lotm_renting_contract)

    with boa.reverts("insufficient allowance"):
        vault_contract.start_rental(renter, expiration, sender=lotm_renting_contract)


def test_start_rental(
    contracts_config,
    vault_contract,
    lotm_renting_contract,
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
    vault_contract.deposit(token_id, sender=lotm_renting_contract)
    vault_contract.create_listing(price, sender=lotm_renting_contract)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    vault_contract.start_rental(renter, expiration, sender=lotm_renting_contract)
    event = get_last_event(vault_contract, name="RentalStarted")

    assert vault_contract.active_rental()[1] == renter
    assert vault_contract.active_rental()[2] == token_id
    assert vault_contract.active_rental()[3] == start_time
    assert vault_contract.active_rental()[4] == expiration
    assert vault_contract.active_rental()[5] == rental_amount

    assert event.owner == nft_owner
    assert event.token_id == token_id
    assert event.renter == renter
    assert event.expiration == expiration
    assert event.amount == rental_amount

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == renter


def test_start_rental_ongoing(
    contracts_config,
    vault_contract,
    lotm_renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
):
    token_id = 1
    price = int(1e18)
    expiration = int(boa.eval("block.timestamp")) + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, sender=lotm_renting_contract)
    vault_contract.create_listing(price, sender=lotm_renting_contract)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(
        Decimal(expiration - start_time) * Decimal(price) / Decimal(3600)
    )

    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    vault_contract.start_rental(renter, expiration, sender=lotm_renting_contract)
    with boa.reverts("active rental ongoing"):
        vault_contract.start_rental(renter, expiration, sender=lotm_renting_contract)


def test_close_rental_not_caller(contracts_config, vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.close_rental(sender=nft_owner)


def test_close_rental_no_active_rental(
    contracts_config, vault_contract, lotm_renting_contract
):
    boa.env.time_travel(seconds=1)
    with boa.reverts("active rental does not exist"):
        vault_contract.close_rental(sender=lotm_renting_contract)


def test_close_rental(
    contracts_config,
    vault_contract,
    lotm_renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
):
    token_id = 1
    price = int(1e18)
    expiration = int(boa.eval("block.timestamp")) + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, sender=lotm_renting_contract)
    vault_contract.create_listing(price, sender=lotm_renting_contract)

    start_time = int(boa.eval("block.timestamp"))
    rental_amount = int(
        Decimal(expiration - start_time) / Decimal(3600) * Decimal(price) 
    )
    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    vault_contract.start_rental(renter, expiration, sender=lotm_renting_contract)

    time_passed = 43200
    boa.env.time_travel(seconds=time_passed)

    vault_contract.close_rental(sender=lotm_renting_contract)
    event = get_last_event(vault_contract, name="RentalClosedPrematurely")

    assert vault_contract.active_rental()[1] == renter
    assert vault_contract.active_rental()[2] == token_id
    assert vault_contract.active_rental()[3] == start_time
    assert vault_contract.active_rental()[4] == boa.eval("block.timestamp")
    assert vault_contract.active_rental()[5] == int(Decimal(rental_amount) / Decimal(2))
    assert vault_contract.claimable_rewards() == int(Decimal(rental_amount) / Decimal(2))

    assert event.owner == nft_owner
    assert event.token_id == token_id
    assert event.renter == renter
    assert event.start == start_time
    assert event.expiration == boa.eval("block.timestamp")
    assert event.amount == int(Decimal(rental_amount) / Decimal(2))


def test_claim_not_caller(contracts_config, vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.claim(sender=nft_owner)


def test_claim_no_rewards(contracts_config, vault_contract, lotm_renting_contract):
    with boa.reverts("no rewards to claim"):
        vault_contract.claim(sender=lotm_renting_contract)


def test_claim(
    contracts_config,
    vault_contract,
    lotm_renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
):
    token_id = 1
    price = int(1e18)
    expiration = int(boa.eval("block.timestamp")) + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, sender=lotm_renting_contract)
    vault_contract.create_listing(price, sender=lotm_renting_contract)

    start_time = int(boa.eval("block.timestamp"))
    rental_amount = int(
        Decimal(expiration - start_time) / Decimal(3600) * Decimal(price) 
    )
    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    vault_contract.start_rental(renter, expiration, sender=lotm_renting_contract)

    boa.env.time_travel(seconds=86401)

    assert vault_contract.claimable_rewards() == rental_amount

    vault_contract.claim(sender=lotm_renting_contract)
    event = get_last_event(vault_contract, name="RewardsClaimed")

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.claimable_rewards() == 0

    assert event.owner == nft_owner
    assert event.token_id == token_id
    assert event.amount == rental_amount


def test_claim2(
    contracts_config,
    vault_contract,
    lotm_renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
):
    token_id = 1
    price = int(1e18)
    expiration = int(boa.eval("block.timestamp")) + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, sender=lotm_renting_contract)
    vault_contract.create_listing(price, sender=lotm_renting_contract)

    start_time = int(boa.eval("block.timestamp"))
    rental_amount = int(
        Decimal(expiration - start_time) / Decimal(3600) * Decimal(price) 
    )
    ape_contract.approve(vault_contract, rental_amount, sender=renter)
    vault_contract.start_rental(renter, expiration, sender=lotm_renting_contract)

    boa.env.time_travel(seconds=86401)

    assert vault_contract.claimable_rewards() == rental_amount

    ape_contract.approve(vault_contract, rental_amount, sender=renter)
    vault_contract.start_rental(renter, int(boa.eval("block.timestamp")) + 86400, sender=lotm_renting_contract)

    assert vault_contract.unclaimed_rewards() == rental_amount

    boa.env.time_travel(seconds=86401)

    assert vault_contract.claimable_rewards() == rental_amount * 2

    vault_contract.claim(sender=lotm_renting_contract)
    event = get_last_event(vault_contract, name="RewardsClaimed")

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.claimable_rewards() == 0

    assert event.owner == nft_owner
    assert event.token_id == token_id
    assert event.amount == rental_amount * 2


def test_withdraw_not_caller(contracts_config, vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.withdraw(sender=nft_owner)


def test_withdraw_rental_ongoing(
    contracts_config,
    vault_contract,
    lotm_renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
):
    token_id = 1
    price = int(1e18)
    expiration = int(boa.eval("block.timestamp")) + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, sender=lotm_renting_contract)
    vault_contract.create_listing(price, sender=lotm_renting_contract)

    start_time = int(boa.eval("block.timestamp"))
    rental_amount = int(
        Decimal(expiration - start_time) / Decimal(3600) * Decimal(price) 
    )
    ape_contract.approve(vault_contract, rental_amount, sender=renter)
    vault_contract.start_rental(renter, expiration, sender=lotm_renting_contract)

    with boa.reverts("active rental ongoing"):
        vault_contract.withdraw(sender=lotm_renting_contract)


def test_withdraw(
    contracts_config,
    vault_contract,
    lotm_renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
):
    token_id = 1
    price = int(1e18)
    expiration = int(boa.eval("block.timestamp")) + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, sender=lotm_renting_contract)
    vault_contract.create_listing(price, sender=lotm_renting_contract)

    start_time = int(boa.eval("block.timestamp"))
    rental_amount = int(
        Decimal(expiration - start_time) / Decimal(3600) * Decimal(price) 
    )
    ape_contract.approve(vault_contract, rental_amount, sender=renter)
    vault_contract.start_rental(renter, expiration, sender=lotm_renting_contract)

    boa.env.time_travel(seconds=86401)

    assert vault_contract.claimable_rewards() == rental_amount

    vault_contract.withdraw(sender=lotm_renting_contract)
    event = get_last_event(vault_contract, name="NFTWithdrawn")

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.claimable_rewards() == 0
    assert vault_contract.listing() == (0, 0, False)
    assert vault_contract.active_rental()[1:] == (ZERO_ADDRESS, 0, 0, 0, 0)
    assert not vault_contract.is_initialised()
    assert vault_contract.owner() == ZERO_ADDRESS

    assert event.owner == nft_owner
    assert event.token_id == token_id
    assert event.claimed_rewards == rental_amount

    assert nft_contract.ownerOf(token_id) == nft_owner
    assert ape_contract.balanceOf(lotm_renting_contract) == 0
    assert ape_contract.balanceOf(nft_owner) == rental_amount

