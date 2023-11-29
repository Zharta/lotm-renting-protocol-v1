from decimal import Decimal
from textwrap import dedent

import boa
import pytest

from ...conftest_base import (
    ZERO_ADDRESS,
    ZERO_BYTES32,
    Listing,
    Rental,
    VaultState,
    compute_state_hash,
)

FOREVER = 2**256 - 1
PROTOCOL_FEE = 500


@pytest.fixture(scope="module")
def renting_contract(empty_contract_def):
    return empty_contract_def.deploy()


@pytest.fixture(scope="module")
def vault_contract(
    nft_owner,
    renting_contract,
    vault_contract_def,
    nft_contract,
    ape_contract,
    delegation_registry_warm_contract,
):
    contract = vault_contract_def.deploy(ape_contract, nft_contract, delegation_registry_warm_contract)
    contract.initialise(
        nft_owner,
        sender=renting_contract.address,
    )
    return contract


@pytest.fixture(autouse=True)
def mint(nft_owner, owner, renter, nft_contract, ape_contract):
    with boa.env.anchor():
        nft_contract.mint(nft_owner, 1, sender=owner)
        ape_contract.mint(renter, int(1000 * 1e18), sender=owner)
        yield


@pytest.fixture(scope="module")
def erc20_not_reverting():
    return boa.loads(
        dedent(
            """
        @external
        def transfer(dst: address, wallet: uint256) -> bool:
            return False

        @external
        def transferFrom(src: address, dst: address, wallet: uint256) -> bool:
            return False

        @external
        def allowance(src: address, dst: address) -> uint256:
            return max_value(uint256)

             """
        )
    )


def test_initial_state(vault_contract, nft_owner, renting_contract, nft_contract, ape_contract):
    assert vault_contract.owner() == nft_owner
    assert vault_contract.caller() == renting_contract.address
    assert vault_contract.is_initialised()
    assert vault_contract.nft_contract_addr() == nft_contract.address
    assert vault_contract.payment_token_addr() == ape_contract.address


def test_initialise_twice(vault_contract, renting_contract, nft_owner):
    with boa.reverts("already initialised"):
        vault_contract.initialise(
            nft_owner,
            sender=renting_contract.address,
        )


def test_deposit_not_caller(vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.deposit(1, 1, 1, 1, ZERO_ADDRESS, sender=nft_owner)


def test_deposit_not_min_duration_higher_than_max(vault_contract, renting_contract, nft_contract, nft_owner):
    token_id = 1
    price = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)

    with boa.reverts("min duration > max duration"):
        vault_contract.deposit(token_id, price, 2, 1, ZERO_ADDRESS, sender=renting_contract.address)


def test_deposit(vault_contract, nft_owner, renting_contract, nft_contract, delegation_registry_warm_contract):
    token_id = 1
    price = 1
    min_duration = 0
    max_duration = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    listing = Listing(token_id, price, min_duration, max_duration)
    active_rental = Rental()

    assert nft_contract.ownerOf(token_id) == vault_contract.address
    assert vault_contract.state() == compute_state_hash(active_rental, listing)

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == ZERO_ADDRESS


def test_deposit_self_delegate(vault_contract, nft_owner, renting_contract, nft_contract, delegation_registry_warm_contract):
    token_id = 1
    price = 1
    min_duration = 0
    max_duration = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, nft_owner, sender=renting_contract.address)

    assert nft_contract.ownerOf(token_id) == vault_contract.address
    assert vault_contract.state() == compute_state_hash(Rental(), Listing(token_id, price, min_duration, max_duration))

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == nft_owner
    assert delegation_registry_warm_contract.eval(f"self.exp[{vault_contract.address}]") == FOREVER


def test_deposit_twice(vault_contract, nft_owner, renting_contract, nft_contract, delegation_registry_warm_contract):
    token_id = 1
    price = 1
    min_duration = 0
    max_duration = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, nft_owner, sender=renting_contract.address)

    with boa.reverts("invalid state"):
        vault_contract.deposit(token_id, price, min_duration, max_duration, nft_owner, sender=renting_contract.address)


def test_deposit_overrides_delegation(
    vault_contract,
    nft_owner,
    renting_contract,
    nft_contract,
    delegation_registry_warm_contract,
    protocol_wallet,
):
    token_id = 1
    price = 1
    min_duration = 0
    max_duration = 0
    second_owner = boa.env.generate_address("second_owner")

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, nft_owner, sender=renting_contract.address)

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == nft_owner

    listing = Listing(token_id, price, min_duration, max_duration)
    active_rental = Rental()
    vault_state = VaultState(active_rental, listing)

    vault_contract.withdraw(vault_state.to_tuple(), nft_owner, sender=renting_contract.address)
    nft_contract.transferFrom(nft_owner, second_owner, token_id, sender=nft_owner)

    nft_contract.approve(vault_contract, token_id, sender=second_owner)

    vault_contract.initialise(second_owner, sender=renting_contract.address)
    vault_contract.deposit(token_id, price, min_duration, max_duration, second_owner, sender=renting_contract.address)

    listing = Listing(token_id, price, min_duration, max_duration)
    active_rental = Rental()

    assert nft_contract.ownerOf(token_id) == vault_contract.address
    assert vault_contract.state() == compute_state_hash(active_rental, listing)

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == second_owner
    assert delegation_registry_warm_contract.eval(f"self.exp[{vault_contract.address}]") == FOREVER


def test_set_listing_not_caller(vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.set_listing(VaultState().to_tuple(), 1, nft_owner, 1, 0, 1, ZERO_ADDRESS, sender=nft_owner)


def test_set_listing_min_higher_than_max(vault_contract, renting_contract, nft_contract, nft_owner):
    token_id = 1
    price = 1
    min_duration = 0
    max_duration = 0
    new_min_duration = 2
    new_max_duration = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    listing = Listing(token_id, price, min_duration, max_duration)

    with boa.reverts("min duration > max duration"):
        vault_contract.set_listing(
            VaultState(listing=listing).to_tuple(),
            token_id,
            nft_owner,
            price,
            new_min_duration,
            new_max_duration,
            ZERO_ADDRESS,
            sender=renting_contract.address,
        )


def test_set_listing(vault_contract, renting_contract, nft_contract, nft_owner):
    token_id = 1
    price = 1
    new_price = 2
    min_duration = 0
    max_duration = 0
    new_min_duration = 1
    new_max_duration = 2

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    listing = Listing(token_id, price, min_duration, max_duration)
    new_listing = Listing(token_id, new_price, new_min_duration, new_max_duration)

    assert vault_contract.state() == compute_state_hash(Rental(), listing)

    vault_contract.set_listing(
        VaultState(listing=listing).to_tuple(),
        token_id,
        nft_owner,
        new_price,
        new_min_duration,
        new_max_duration,
        ZERO_ADDRESS,
        sender=renting_contract.address,
    )

    assert vault_contract.state() == compute_state_hash(Rental(), new_listing)


def test_set_listing_invalid_token_id(vault_contract, renting_contract, nft_contract, nft_owner):
    token_id = 1
    price = 1
    min_duration = 0
    max_duration = 0

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    listing = Listing(token_id, price, min_duration, max_duration)

    with boa.reverts("invalid token_id"):
        vault_contract.set_listing(
            VaultState(listing=listing).to_tuple(), 2, nft_owner, 1, 0, 1, ZERO_ADDRESS, sender=renting_contract.address
        )


def test_set_listing_invalid_state(vault_contract, renting_contract, nft_contract, nft_owner):
    token_id = 1
    price = 1
    min_duration = 0
    max_duration = 0

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    listing = Listing(token_id, price + 1, min_duration, max_duration)

    with boa.reverts("invalid state"):
        vault_contract.set_listing(
            VaultState(listing=listing).to_tuple(), 1, nft_owner, 1, 0, 1, ZERO_ADDRESS, sender=renting_contract.address
        )


def test_set_listing_and_delegate_to_wallet(
    vault_contract, renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract
):
    token_id = 1
    price = 1
    new_price = 2
    min_duration = 0
    max_duration = 0
    new_min_duration = 1
    new_max_duration = 2
    delegate = boa.env.generate_address("delegate")

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == ZERO_ADDRESS

    listing = Listing(token_id, price, min_duration, max_duration)
    vault_state = VaultState(listing=listing)
    vault_contract.set_listing(
        vault_state.to_tuple(),
        token_id,
        nft_owner,
        new_price,
        new_min_duration,
        new_max_duration,
        delegate,
        sender=renting_contract.address,
    )

    new_listing = Listing(token_id, new_price, new_min_duration, new_max_duration)
    assert vault_contract.state() == compute_state_hash(Rental(), new_listing)

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == delegate
    assert delegation_registry_warm_contract.eval(f"self.exp[{vault_contract.address}]") == FOREVER


def test_cancel_listing_not_caller(vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.set_listing(VaultState().to_tuple(), 0, nft_owner, 0, 0, 0, ZERO_ADDRESS, sender=nft_owner)


def test_cancel_listing(vault_contract, renting_contract, nft_contract, nft_owner):
    token_id = 1
    price = 1
    min_duration = 0
    max_duration = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    listing = Listing(token_id, price, min_duration, max_duration)
    vault_contract.set_listing(
        VaultState(listing=listing).to_tuple(), token_id, nft_owner, 0, 0, 0, ZERO_ADDRESS, sender=renting_contract.address
    )

    new_listing = Listing(token_id, 0, 0, 0)
    assert vault_contract.state() == compute_state_hash(Rental(), new_listing)


def test_start_rental_not_caller(vault_contract, nft_owner, renter, protocol_wallet):
    with boa.reverts("not caller"):
        vault_contract.start_rental(
            VaultState().to_tuple(), renter, 1, renter, PROTOCOL_FEE, protocol_wallet, sender=nft_owner
        )


def test_start_rental_no_listing(vault_contract, renting_contract, renter, protocol_wallet):
    with boa.reverts("listing does not exist"):
        vault_contract.start_rental(
            VaultState().to_tuple(), renter, 1, renter, PROTOCOL_FEE, protocol_wallet, sender=renting_contract.address
        )


def test_start_rental_empty_delegate(vault_contract, renting_contract, renter, nft_contract, nft_owner, protocol_wallet):
    token_id = 1
    price = 1
    expiration = boa.eval("block.timestamp") + 3600
    min_duration = 0
    max_duration = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    listing = Listing(token_id, price, min_duration, max_duration)
    with boa.reverts("delegate is zero address"):
        vault_contract.start_rental(
            VaultState(listing=listing).to_tuple(),
            renter,
            expiration,
            ZERO_ADDRESS,
            PROTOCOL_FEE,
            protocol_wallet,
            sender=renting_contract.address,
        )


def test_start_rental_invalid_state(vault_contract, renting_contract, nft_contract, nft_owner, renter, protocol_wallet):
    token_id = 1
    price = 1
    expiration = boa.eval("block.timestamp") + 3600
    min_duration = 0
    max_duration = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    listing = Listing(token_id, price + 1, min_duration, max_duration)
    with boa.reverts("invalid state"):
        vault_contract.start_rental(
            VaultState(listing=listing).to_tuple(),
            renter,
            expiration,
            renter,
            PROTOCOL_FEE,
            protocol_wallet,
            sender=renting_contract.address,
        )


def test_start_rental_active_rental_ongoing(
    vault_contract, renting_contract, nft_contract, nft_owner, renter, protocol_wallet
):
    token_id = 1
    price = 1
    expiration = boa.eval("block.timestamp") + 86400
    min_duration = 0
    max_duration = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    listing = Listing(token_id, price, min_duration, max_duration)
    with boa.reverts("active rental ongoing"):
        vault_contract.start_rental(
            VaultState(Rental(expiration=expiration), listing).to_tuple(),
            renter,
            expiration,
            renter,
            PROTOCOL_FEE,
            protocol_wallet,
            sender=renting_contract.address,
        )


def test_start_rental_min_duration_not_respected(
    vault_contract, renting_contract, nft_contract, nft_owner, renter, protocol_wallet
):
    token_id = 1
    price = 1
    expiration = boa.eval("block.timestamp") + 86400
    min_duration = expiration + 1
    max_duration = 0

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    listing = Listing(token_id, price, min_duration, max_duration)
    with boa.reverts("duration not respected"):
        vault_contract.start_rental(
            VaultState(listing=listing).to_tuple(),
            renter,
            expiration,
            renter,
            PROTOCOL_FEE,
            protocol_wallet,
            sender=renting_contract.address,
        )


def test_start_rental_exceed_max_duration(vault_contract, renting_contract, nft_contract, nft_owner, renter, protocol_wallet):
    token_id = 1
    price = 1
    expiration = boa.eval("block.timestamp") + 86400
    min_duration = 0
    max_duration = 1

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    listing = Listing(token_id, price, min_duration, max_duration)
    with boa.reverts("duration not respected"):
        vault_contract.start_rental(
            VaultState(listing=listing).to_tuple(),
            renter,
            expiration,
            renter,
            PROTOCOL_FEE,
            protocol_wallet,
            sender=renting_contract.address,
        )


def test_start_rental(
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
    delegation_registry_warm_contract,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    expiration = boa.eval("block.timestamp") + 86400
    min_duration = 0
    max_duration = 0

    renter_delegate = boa.env.generate_address("renter delegate")

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) * Decimal(price) / Decimal(3600))

    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    listing = Listing(token_id, price, min_duration, max_duration)
    active_rental_raw = vault_contract.start_rental(
        VaultState(listing=listing).to_tuple(),
        renter,
        expiration,
        renter_delegate,
        PROTOCOL_FEE,
        protocol_wallet,
        sender=renting_contract.address,
    )

    active_rental = Rental(*active_rental_raw)
    assert active_rental.owner == nft_owner
    assert active_rental.renter == renter
    assert active_rental.delegate == renter_delegate
    assert active_rental.token_id == token_id
    assert active_rental.amount == rental_amount
    assert active_rental.protocol_fee == PROTOCOL_FEE
    assert active_rental.protocol_wallet == protocol_wallet

    assert vault_contract.state() == compute_state_hash(active_rental, listing)

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == renter_delegate
    assert delegation_registry_warm_contract.eval(f"self.exp[{vault_contract.address}]") == expiration


def test_start_rental_with_existing_delegation(
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
    delegation_registry_warm_contract,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    expiration = boa.eval("block.timestamp") + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) * Decimal(price) / Decimal(3600))

    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    delegation_registry_warm_contract.setHotWallet(renter, expiration - 1, False, sender=vault_contract.address)
    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == renter

    listing = Listing(token_id, price, min_duration, max_duration)
    vault_contract.start_rental(
        VaultState(listing=listing).to_tuple(),
        renter,
        expiration,
        renter,
        PROTOCOL_FEE,
        protocol_wallet,
        sender=renting_contract.address,
    )

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == renter
    assert delegation_registry_warm_contract.eval(f"self.exp[{vault_contract.address}]") == expiration


def test_close_rental_not_caller(vault_contract, nft_owner, renter):
    with boa.reverts("not caller"):
        vault_contract.close_rental(VaultState().to_tuple(), renter, sender=nft_owner)


def test_close_rental_invalid_state(vault_contract, renting_contract, renter):
    with boa.reverts("invalid state"):
        vault_contract.close_rental(
            VaultState(Rental(), Listing(token_id=1)).to_tuple(), renter, sender=renting_contract.address
        )


def test_close_rental_no_active_rental(vault_contract, renting_contract, renter):
    boa.env.time_travel(seconds=1)
    with boa.reverts("active rental does not exist"):
        vault_contract.close_rental(VaultState().to_tuple(), renter, sender=renting_contract.address)


def test_close_rental(
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
    delegation_registry_warm_contract,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    expiration = boa.eval("block.timestamp") + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) / Decimal(3600) * Decimal(price))
    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    listing = Listing(token_id, price, min_duration, max_duration)

    active_rental_raw = vault_contract.start_rental(
        VaultState(listing=listing).to_tuple(),
        renter,
        expiration,
        renter,
        PROTOCOL_FEE,
        protocol_wallet,
        sender=renting_contract.address,
    )
    active_rental = Rental(*active_rental_raw)

    time_passed = 43200
    boa.env.time_travel(seconds=time_passed)
    real_rental_amount = int(Decimal(rental_amount) / Decimal(2))
    protocol_fee_amount = int(real_rental_amount * PROTOCOL_FEE / 10000)

    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == 0

    vault_state = VaultState(active_rental, listing)

    tx_real_rental_amount = vault_contract.close_rental(vault_state.to_tuple(), renter, sender=renting_contract.address)

    assert tx_real_rental_amount == real_rental_amount

    assert vault_contract.state() == compute_state_hash(Rental(), listing)
    assert vault_contract.claimable_rewards(Rental().to_tuple()) == real_rental_amount - protocol_fee_amount
    assert vault_contract.unclaimed_rewards() == real_rental_amount - protocol_fee_amount
    assert vault_contract.unclaimed_protocol_fee() == 0

    assert ape_contract.balanceOf(protocol_wallet) == protocol_fee_amount

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == ZERO_ADDRESS


def test_close_rental_no_protocol_fee(
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
    delegation_registry_warm_contract,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    expiration = boa.eval("block.timestamp") + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, False, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) / Decimal(3600) * Decimal(price))
    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    listing = Listing(token_id, price, min_duration, max_duration)

    active_rental_raw = vault_contract.start_rental(
        VaultState(listing=listing).to_tuple(),
        renter,
        expiration,
        0,
        protocol_wallet,
        sender=renting_contract.address,
    )
    active_rental = Rental(*active_rental_raw)

    time_passed = 43200
    boa.env.time_travel(seconds=time_passed)
    real_rental_amount = int(Decimal(rental_amount) / Decimal(2))
    protocol_fee_amount = 0

    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == 0

    vault_state = VaultState(active_rental, listing)

    tx_real_rental_amount = vault_contract.close_rental(vault_state.to_tuple(), renter, sender=renting_contract.address)

    assert tx_real_rental_amount == real_rental_amount

    assert vault_contract.state() == compute_state_hash(Rental(), listing)
    assert vault_contract.claimable_rewards(Rental().to_tuple()) == real_rental_amount - protocol_fee_amount
    assert vault_contract.unclaimed_rewards() == real_rental_amount - protocol_fee_amount
    assert vault_contract.unclaimed_protocol_fee() == 0

    assert ape_contract.balanceOf(protocol_wallet) == protocol_fee_amount

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == ZERO_ADDRESS


def test_close_rental_no_protocol_fee(
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
    delegation_registry_warm_contract,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    expiration = boa.eval("block.timestamp") + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, False, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) / Decimal(3600) * Decimal(price))
    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    listing = Listing(token_id, price, min_duration, max_duration)

    active_rental_raw = vault_contract.start_rental(
        VaultState(listing=listing).to_tuple(),
        renter,
        expiration,
        0,
        protocol_wallet,
        sender=renting_contract.address,
    )
    active_rental = Rental(*active_rental_raw)

    time_passed = 43200
    boa.env.time_travel(seconds=time_passed)
    real_rental_amount = int(Decimal(rental_amount) / Decimal(2))
    protocol_fee_amount = 0

    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == 0

    vault_state = VaultState(active_rental, listing)

    tx_real_rental_amount = vault_contract.close_rental(vault_state.to_tuple(), renter, sender=renting_contract.address)

    assert tx_real_rental_amount == real_rental_amount

    assert vault_contract.state() == compute_state_hash(Rental(), listing)
    assert vault_contract.claimable_rewards(Rental().to_tuple()) == real_rental_amount - protocol_fee_amount
    assert vault_contract.unclaimed_rewards() == real_rental_amount - protocol_fee_amount
    assert vault_contract.unclaimed_protocol_fee() == 0

    assert ape_contract.balanceOf(protocol_wallet) == protocol_fee_amount

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == ZERO_ADDRESS


def test_close_rental_no_protocol_fee(
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
    delegation_registry_warm_contract,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    expiration = boa.eval("block.timestamp") + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, False, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) / Decimal(3600) * Decimal(price))
    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    listing = Listing(token_id, price, min_duration, max_duration)

    active_rental_raw = vault_contract.start_rental(
        VaultState(listing=listing).to_tuple(),
        renter,
        expiration,
        0,
        protocol_wallet,
        sender=renting_contract.address,
    )
    active_rental = Rental(*active_rental_raw)

    time_passed = 43200
    boa.env.time_travel(seconds=time_passed)
    real_rental_amount = int(Decimal(rental_amount) / Decimal(2))
    protocol_fee_amount = 0

    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == 0

    vault_state = VaultState(active_rental, listing)

    tx_real_rental_amount = vault_contract.close_rental(vault_state.to_tuple(), renter, sender=renting_contract.address)

    assert tx_real_rental_amount == real_rental_amount

    assert vault_contract.state() == compute_state_hash(Rental(), listing)
    assert vault_contract.claimable_rewards(Rental().to_tuple()) == real_rental_amount - protocol_fee_amount
    assert vault_contract.unclaimed_rewards() == real_rental_amount - protocol_fee_amount
    assert vault_contract.unclaimed_protocol_fee() == 0

    assert ape_contract.balanceOf(protocol_wallet) == protocol_fee_amount

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == ZERO_ADDRESS


def test_close_rental_no_protocol_fee(
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
    delegation_registry_warm_contract,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    expiration = boa.eval("block.timestamp") + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, False, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) / Decimal(3600) * Decimal(price))
    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    listing = Listing(token_id, price, min_duration, max_duration)

    active_rental_raw = vault_contract.start_rental(
        VaultState(listing=listing).to_tuple(),
        renter,
        expiration,
        0,
        protocol_wallet,
        sender=renting_contract.address,
    )
    active_rental = Rental(*active_rental_raw)

    time_passed = 43200
    boa.env.time_travel(seconds=time_passed)
    real_rental_amount = int(Decimal(rental_amount) / Decimal(2))
    protocol_fee_amount = 0

    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == 0

    vault_state = VaultState(active_rental, listing)

    tx_real_rental_amount = vault_contract.close_rental(vault_state.to_tuple(), renter, sender=renting_contract.address)

    assert tx_real_rental_amount == real_rental_amount

    assert vault_contract.state() == compute_state_hash(Rental(), listing)
    assert vault_contract.claimable_rewards(Rental().to_tuple()) == real_rental_amount - protocol_fee_amount
    assert vault_contract.unclaimed_rewards() == real_rental_amount - protocol_fee_amount
    assert vault_contract.unclaimed_protocol_fee() == 0

    assert ape_contract.balanceOf(protocol_wallet) == protocol_fee_amount

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == ZERO_ADDRESS


def test_claim_not_caller(vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.claim(VaultState().to_tuple(), nft_owner, sender=nft_owner)


def test_claim_not_owner(vault_contract, renting_contract, renter):
    with boa.reverts("not owner of vault"):
        vault_contract.claim(VaultState().to_tuple(), renter, sender=renting_contract.address)


def test_claim_invalid_state(vault_contract, renting_contract, nft_owner):
    with boa.reverts("invalid state"):
        vault_contract.claim(VaultState(listing=Listing(price=1)).to_tuple(), nft_owner, sender=renting_contract.address)


def test_claim_no_rewards(vault_contract, renting_contract, nft_owner):
    with boa.reverts("no rewards to claim"):
        vault_contract.claim(VaultState().to_tuple(), nft_owner, sender=renting_contract.address)


def test_claim(
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    expiration = boa.eval("block.timestamp") + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) / Decimal(3600) * Decimal(price))
    protocol_fee_amount = int(rental_amount * PROTOCOL_FEE / 10000)
    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    listing = Listing(token_id, price, min_duration, max_duration)

    active_rental_raw = vault_contract.start_rental(
        VaultState(listing=listing).to_tuple(),
        renter,
        expiration,
        renter,
        PROTOCOL_FEE,
        protocol_wallet,
        sender=renting_contract.address,
    )
    active_rental = Rental(*active_rental_raw)

    boa.env.time_travel(seconds=86401)

    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == rental_amount - protocol_fee_amount
    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.unclaimed_protocol_fee() == 0

    _, tx_rewards, tx_protocol_fee_amount = vault_contract.claim(
        VaultState(active_rental, listing).to_tuple(), nft_owner, sender=renting_contract.address
    )

    active_rental.amount = 0

    assert tx_rewards == rental_amount - protocol_fee_amount
    assert tx_protocol_fee_amount == protocol_fee_amount

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == 0
    assert vault_contract.unclaimed_protocol_fee() == 0

    assert vault_contract.state() == compute_state_hash(active_rental, listing)

    assert ape_contract.balanceOf(protocol_wallet) == protocol_fee_amount


def test_claim_no_protocol_fee(
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    expiration = boa.eval("block.timestamp") + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, False, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) / Decimal(3600) * Decimal(price))
    protocol_fee_amount = 0
    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    listing = Listing(token_id, price, min_duration, max_duration)

    active_rental_raw = vault_contract.start_rental(
        VaultState(listing=listing).to_tuple(),
        renter,
        expiration,
        renter,
        0,
        protocol_wallet,
        sender=renting_contract.address,
    )
    active_rental = Rental(*active_rental_raw)

    boa.env.time_travel(seconds=86401)

    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == rental_amount - protocol_fee_amount
    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.unclaimed_protocol_fee() == 0

    _, tx_rewards, tx_protocol_fee_amount = vault_contract.claim(
        VaultState(active_rental, listing).to_tuple(), nft_owner, sender=renting_contract.address
    )

    active_rental.amount = 0

    assert tx_rewards == rental_amount - protocol_fee_amount
    assert tx_protocol_fee_amount == protocol_fee_amount

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == 0
    assert vault_contract.unclaimed_protocol_fee() == 0

    assert vault_contract.state() == compute_state_hash(active_rental, listing)

    assert ape_contract.balanceOf(protocol_wallet) == protocol_fee_amount


def test_claim_no_protocol_fee(
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    expiration = boa.eval("block.timestamp") + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) / Decimal(3600) * Decimal(price))
    protocol_fee_amount = 0
    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    listing = Listing(token_id, price, min_duration, max_duration)

    active_rental_raw = vault_contract.start_rental(
        VaultState(listing=listing).to_tuple(),
        renter,
        expiration,
        renter,
        0,
        protocol_wallet,
        sender=renting_contract.address,
    )
    active_rental = Rental(*active_rental_raw)

    boa.env.time_travel(seconds=86401)

    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == rental_amount - protocol_fee_amount
    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.unclaimed_protocol_fee() == 0

    _, tx_rewards, tx_protocol_fee_amount = vault_contract.claim(
        VaultState(active_rental, listing).to_tuple(), nft_owner, sender=renting_contract.address
    )

    active_rental.amount = 0

    assert tx_rewards == rental_amount - protocol_fee_amount
    assert tx_protocol_fee_amount == protocol_fee_amount

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == 0
    assert vault_contract.unclaimed_protocol_fee() == 0

    assert vault_contract.state() == compute_state_hash(active_rental, listing)

    assert ape_contract.balanceOf(protocol_wallet) == protocol_fee_amount


def test_claim2(vault_contract, renting_contract, nft_contract, nft_owner, renter, ape_contract, protocol_wallet):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    expiration = boa.eval("block.timestamp") + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, False, sender=renting_contract.address)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) / Decimal(3600) * Decimal(price))
    protocol_fee_amount = int(rental_amount * PROTOCOL_FEE / 10000)
    ape_contract.approve(vault_contract, rental_amount, sender=renter)

    listing = Listing(token_id, price, min_duration, max_duration)

    active_rental_raw = vault_contract.start_rental(
        VaultState(listing=listing).to_tuple(),
        renter,
        expiration,
        renter,
        PROTOCOL_FEE,
        protocol_wallet,
        sender=renting_contract.address,
    )
    active_rental = Rental(*active_rental_raw)

    boa.env.time_travel(seconds=86401)

    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == rental_amount - protocol_fee_amount

    ape_contract.approve(vault_contract, rental_amount, sender=renter)
    active_rental_raw2 = vault_contract.start_rental(
        VaultState(active_rental, listing).to_tuple(),
        renter,
        int(boa.eval("block.timestamp")) + 86400,
        renter,
        PROTOCOL_FEE,
        protocol_wallet,
        sender=renting_contract.address,
    )
    active_rental2 = Rental(*active_rental_raw2)

    assert vault_contract.unclaimed_rewards() == rental_amount - protocol_fee_amount
    assert vault_contract.unclaimed_protocol_fee() == protocol_fee_amount

    boa.env.time_travel(seconds=86401)

    assert vault_contract.claimable_rewards(active_rental2.to_tuple()) == (rental_amount - protocol_fee_amount) * 2

    vault_contract.claim(VaultState(active_rental2, listing).to_tuple(), nft_owner, sender=renting_contract.address)

    active_rental2.amount = 0

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.claimable_rewards(active_rental2.to_tuple()) == 0
    assert vault_contract.unclaimed_protocol_fee() == 0

    assert vault_contract.state() == compute_state_hash(active_rental2, listing)

    assert ape_contract.balanceOf(protocol_wallet) == protocol_fee_amount * 2


def test_withdraw_not_caller(vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.withdraw(VaultState().to_tuple(), nft_owner, sender=nft_owner)


def test_withdraw_rental_ongoing(
    vault_contract, renting_contract, nft_contract, nft_owner, renter, ape_contract, protocol_wallet
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    expiration = boa.eval("block.timestamp") + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    listing = Listing(token_id, price, min_duration, max_duration)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) / Decimal(3600) * Decimal(price))
    ape_contract.approve(vault_contract, rental_amount, sender=renter)
    vault_contract.start_rental(
        VaultState(listing=listing).to_tuple(),
        renter,
        expiration,
        renter,
        PROTOCOL_FEE,
        protocol_wallet,
        sender=renting_contract.address,
    )

    with boa.reverts("active rental ongoing"):
        vault_contract.withdraw(
            VaultState(Rental(expiration=expiration), listing).to_tuple(), nft_owner, sender=renting_contract.address
        )


def test_withdraw(vault_contract, renting_contract, nft_contract, nft_owner, renter, ape_contract, protocol_wallet):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    expiration = boa.eval("block.timestamp") + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    listing = Listing(token_id, price, min_duration, max_duration)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) / Decimal(3600) * Decimal(price))
    protocol_fee_amount = int(rental_amount * PROTOCOL_FEE / 10000)
    ape_contract.approve(vault_contract, rental_amount, sender=renter)
    active_rental_raw = vault_contract.start_rental(
        VaultState(listing=listing).to_tuple(),
        renter,
        expiration,
        renter,
        PROTOCOL_FEE,
        protocol_wallet,
        sender=renting_contract.address,
    )
    active_rental = Rental(*active_rental_raw)

    boa.env.time_travel(seconds=86401)

    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == rental_amount - protocol_fee_amount

    vault_contract.withdraw(VaultState(active_rental, listing).to_tuple(), nft_owner, sender=renting_contract.address)

    active_rental.amount = 0

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.unclaimed_protocol_fee() == 0
    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == 0

    assert vault_contract.state() == ZERO_BYTES32

    assert not vault_contract.is_initialised()
    assert vault_contract.owner() == ZERO_ADDRESS

    assert nft_contract.ownerOf(token_id) == nft_owner
    assert ape_contract.balanceOf(renting_contract.address) == 0
    assert ape_contract.balanceOf(nft_owner) == rental_amount - protocol_fee_amount
    assert ape_contract.balanceOf(protocol_wallet) == protocol_fee_amount


def test_withdraw_no_protocol_fee(
    vault_contract, renting_contract, nft_contract, nft_owner, renter, ape_contract, protocol_wallet
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    expiration = boa.eval("block.timestamp") + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, False, sender=renting_contract.address)

    listing = Listing(token_id, price, min_duration, max_duration)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) / Decimal(3600) * Decimal(price))
    protocol_fee_amount = 0
    ape_contract.approve(vault_contract, rental_amount, sender=renter)
    active_rental_raw = vault_contract.start_rental(
        VaultState(listing=listing).to_tuple(),
        renter,
        expiration,
        renter,
        0,
        protocol_wallet,
        sender=renting_contract.address,
    )
    active_rental = Rental(*active_rental_raw)

    boa.env.time_travel(seconds=86401)

    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == rental_amount - protocol_fee_amount

    vault_contract.withdraw(VaultState(active_rental, listing).to_tuple(), nft_owner, sender=renting_contract.address)

    active_rental.amount = 0

    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.unclaimed_protocol_fee() == 0
    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == 0

    assert vault_contract.state() == ZERO_BYTES32

    assert not vault_contract.is_initialised()
    assert vault_contract.owner() == ZERO_ADDRESS

    assert nft_contract.ownerOf(token_id) == nft_owner
    assert ape_contract.balanceOf(renting_contract.address) == 0
    assert ape_contract.balanceOf(nft_owner) == rental_amount - protocol_fee_amount
    assert ape_contract.balanceOf(protocol_wallet) == protocol_fee_amount


def test_initialise_after_withdraw(
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    expiration = boa.eval("block.timestamp") + 86400

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    listing = Listing(token_id, price, min_duration, max_duration)

    start_time = boa.eval("block.timestamp")
    rental_amount = int(Decimal(expiration - start_time) / Decimal(3600) * Decimal(price))
    ape_contract.approve(vault_contract, rental_amount, sender=renter)
    active_rental_raw = vault_contract.start_rental(
        VaultState(listing=listing).to_tuple(),
        renter,
        expiration,
        renter,
        PROTOCOL_FEE,
        protocol_wallet,
        sender=renting_contract.address,
    )
    active_rental = Rental(*active_rental_raw)

    boa.env.time_travel(seconds=86401)

    vault_contract.withdraw(VaultState(active_rental, listing).to_tuple(), nft_owner, sender=renting_contract.address)

    assert not vault_contract.is_initialised()
    assert vault_contract.owner() == ZERO_ADDRESS
    assert vault_contract.caller() == renting_contract.address

    other_user = boa.env.generate_address("other_user")
    with boa.reverts("not caller"):
        vault_contract.initialise(
            other_user,
            sender=other_user,
        )

    vault_contract.initialise(
        other_user,
        sender=renting_contract.address,
    )


def test_delegate_to_wallet(
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    delegation_registry_warm_contract,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    delegate = boa.env.generate_address("delegate")

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, ZERO_ADDRESS, sender=renting_contract.address)

    listing = Listing(token_id, price, min_duration, max_duration)

    delegation_registry_warm_contract.setHotWallet(ZERO_ADDRESS, 0, False, sender=vault_contract.address)

    vault_contract.delegate_to_wallet(
        VaultState(listing=listing).to_tuple(), nft_owner, delegate, sender=renting_contract.address
    )
    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == delegate
    assert delegation_registry_warm_contract.eval(f"self.exp[{vault_contract.address}]") == FOREVER


def test_delegate_to_wallet_active_rental(
    vault_contract,
    renting_contract,
    nft_contract,
    nft_owner,
    renter,
    ape_contract,
    delegation_registry_warm_contract,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    delegate = boa.env.generate_address("delegate")

    start_time = boa.eval("block.timestamp")
    duration = 24
    expiration = start_time + duration * 3600

    nft_contract.approve(vault_contract, token_id, sender=nft_owner)
    vault_contract.deposit(token_id, price, min_duration, max_duration, nft_owner, sender=renting_contract.address)

    listing = Listing(token_id, price, min_duration, max_duration)

    rental_amount = duration * price
    ape_contract.approve(vault_contract, rental_amount, sender=renter)
    active_rental_raw = vault_contract.start_rental(
        VaultState(listing=listing).to_tuple(),
        renter,
        expiration,
        renter,
        PROTOCOL_FEE,
        protocol_wallet,
        sender=renting_contract.address,
    )
    active_rental = Rental(*active_rental_raw)

    with boa.reverts("active rental ongoing"):
        vault_contract.delegate_to_wallet(
            VaultState(active_rental, listing).to_tuple(), nft_owner, delegate, sender=renting_contract.address
        )

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == renter


def test_delegate_to_wallet_not_caller(vault_contract, nft_owner):
    with boa.reverts("not caller"):
        vault_contract.delegate_to_wallet(VaultState().to_tuple(), nft_owner, nft_owner, sender=nft_owner)


def test_delegate_to_wallet_not_owner(vault_contract, renting_contract):
    wallet = boa.env.generate_address("some dude")
    delegate = boa.env.generate_address("delegate")
    with boa.reverts("not owner of vault"):
        vault_contract.delegate_to_wallet(VaultState().to_tuple(), wallet, delegate, sender=renting_contract.address)
