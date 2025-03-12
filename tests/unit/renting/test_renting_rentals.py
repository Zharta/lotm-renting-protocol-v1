from dataclasses import replace

import boa

from ...conftest_base import (
    ZERO_ADDRESS,
    Listing,
    Rental,
    RentalExtensionLog,
    RentalLog,
    TokenContext,
    TokenContextAndListing,
    VaultLog,
    compute_state_hash,
    get_last_event,
    sign_listing,
)

FOREVER = 2**256 - 1
PROTOCOL_FEE = 500


def test_start_rentals(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    vault_contract_def,
    owner,
    owner_key,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    renter_delegate = boa.env.generate_address("delegate")
    start_time = boa.eval("block.timestamp")
    min_expiration = start_time
    duration = 10
    expiration = start_time + duration * 3600
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        renter_delegate,
        start_time,
        sender=renter,
    )
    event = get_last_event(renting_contract, "RentalStarted")

    assert event.renter == renter
    assert event.delegate == renter_delegate
    assert event.nft_contract == nft_contract.address

    event_rental = RentalLog(*event.rentals[0])
    assert event_rental.vault == vault_addr
    assert event_rental.owner == nft_owner
    assert event_rental.token_id == token_id
    assert event_rental.start == start_time
    assert event_rental.min_expiration == min_expiration
    assert event_rental.expiration == expiration
    assert event_rental.amount == rental_amount
    assert event_rental.protocol_fee == PROTOCOL_FEE

    rental = Rental(
        event_rental.id,
        nft_owner,
        renter,
        renter_delegate,
        token_id,
        start_time,
        min_expiration,
        expiration,
        rental_amount,
        PROTOCOL_FEE,
    )
    assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, rental)


def test_start_rentals_after_previous_expiration(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price
    second_renter = boa.env.generate_address("second_renter")

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        ZERO_ADDRESS,
        start_time,
        sender=renter,
    )

    event = get_last_event(renting_contract, "RentalStarted")
    rental = RentalLog(*event.rentals[0]).to_rental(renter=renter)

    boa.env.time_travel(seconds=duration * 3600)

    second_start_time = boa.eval("block.timestamp")
    ape_contract.mint(second_renter, rental_amount, sender=owner)
    ape_contract.approve(renting_contract, rental_amount, sender=second_renter)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, second_start_time, renting_contract.address)

    renting_contract.start_rentals(
        [TokenContextAndListing(TokenContext(token_id, nft_owner, rental), signed_listing, duration).to_tuple()],
        ZERO_ADDRESS,
        second_start_time,
        sender=second_renter,
    )

    event = get_last_event(renting_contract, "RentalStarted")
    rental = RentalLog(*event.rentals[0]).to_rental(renter=second_renter)
    assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, rental)


def test_start_rentals_batch(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    vault_contract_def,
    owner,
    owner_key,
    protocol_wallet,
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]
    min_duration = 0
    max_duration = 0

    token_id = 1
    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    duration = 10
    expiration = start_time + duration * 3600
    rental_amount = duration * price
    renter_delegate = boa.env.generate_address("delegate")

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit(token_ids, nft_owner, sender=nft_owner)

    listings = [Listing(token_id, price, min_duration, max_duration, start_time) for token_id in token_ids]
    signed_listings = [
        sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address) for listing in listings
    ]
    token_contexts = [TokenContext(token_id, nft_owner, Rental()) for token_id in token_ids]

    ape_contract.approve(renting_contract, rental_amount * token_id_qty, sender=renter)

    renting_contract.start_rentals(
        [
            TokenContextAndListing(token_context, signed_listing, duration).to_tuple()
            for token_context, signed_listing in zip(token_contexts, signed_listings)
        ],
        renter_delegate,
        start_time,
        sender=renter,
    )
    event = get_last_event(renting_contract, "RentalStarted")

    assert event.renter == renter
    assert event.delegate == renter_delegate
    assert event.nft_contract == nft_contract.address
    assert len(event.rentals) == token_id_qty

    for token_id, event_rental in zip(token_ids, event.rentals):
        event_rental = RentalLog(*event_rental)
        print(f"{event_rental=}")
        assert event_rental.vault == renting_contract.tokenid_to_vault(token_id)
        assert event_rental.owner == nft_owner
        assert event_rental.token_id == token_id
        assert event_rental.start == start_time
        assert event_rental.min_expiration == min_expiration
        assert event_rental.expiration == expiration
        assert event_rental.amount == rental_amount
        assert event_rental.protocol_fee == PROTOCOL_FEE

        rental = Rental(
            event_rental.id,
            nft_owner,
            renter,
            renter_delegate,
            token_id,
            start_time,
            min_expiration,
            expiration,
            rental_amount,
            PROTOCOL_FEE,
        )
        assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, rental)


def test_start_rentals_transfers_amounts(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    vault_contract_def,
    owner,
    owner_key,
    protocol_wallet,
    delegation_registry_warm_contract,
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]
    min_duration = 0
    max_duration = 0

    base_price = int(1e18)
    start_time = boa.eval("block.timestamp")
    duration = 10

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit(token_ids, nft_owner, sender=nft_owner)

    listings = [Listing(token_id, base_price * token_id, min_duration, max_duration, start_time) for token_id in token_ids]
    signed_listings = [
        sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address) for listing in listings
    ]
    token_contexts = [TokenContext(token_id, nft_owner, Rental()) for token_id in token_ids]
    rental_amount = sum(listing.price * duration for listing in listings)

    ape_contract.mint(renter, rental_amount, sender=owner)
    renter_initial_balance = ape_contract.balanceOf(renter)
    renting_contract_initial_balance = ape_contract.balanceOf(renting_contract)

    ape_contract.approve(renting_contract, rental_amount, sender=renter)

    renting_contract.start_rentals(
        [
            TokenContextAndListing(token_context, signed_listing, duration).to_tuple()
            for token_context, signed_listing in zip(token_contexts, signed_listings)
        ],
        nft_owner,
        start_time,
        sender=renter,
    )

    assert ape_contract.balanceOf(renter) == renter_initial_balance - rental_amount
    assert ape_contract.balanceOf(renting_contract) == renting_contract_initial_balance + rental_amount


def test_starts_rentals_creates_delegation(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    vault_contract_def,
    owner,
    owner_key,
    protocol_wallet,
    delegation_registry_warm_contract,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    renter_delegate = boa.env.generate_address("delegate")
    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        renter_delegate,
        start_time,
        sender=renter,
    )

    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == renter_delegate


def test_start_rentals_reverts_if_contract_paused(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    vault_contract_def,
    owner,
    owner_key,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.set_paused(True, sender=owner)

    with boa.reverts("paused"):
        renting_contract.start_rentals(
            [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
            ZERO_ADDRESS,
            start_time,
            sender=renter,
        )


def test_start_rentals_reverts_if_invalid_signature(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    vault_contract_def,
    owner,
    owner_key,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    token_context = TokenContext(token_id, nft_owner, Rental())
    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    invalid_signed_listings = [
        replace(signed_listing, owner_signature=replace(signed_listing.owner_signature, v=0)),
        replace(signed_listing, owner_signature=replace(signed_listing.owner_signature, r=0)),
        replace(signed_listing, owner_signature=replace(signed_listing.owner_signature, s=0)),
        replace(signed_listing, admin_signature=replace(signed_listing.admin_signature, v=0)),
        replace(signed_listing, admin_signature=replace(signed_listing.admin_signature, r=0)),
        replace(signed_listing, admin_signature=replace(signed_listing.admin_signature, s=0)),
        replace(signed_listing, listing=replace(listing, token_id=token_id + 1)),
        replace(signed_listing, listing=replace(listing, price=price + 1)),
        replace(signed_listing, listing=replace(listing, min_duration=min_duration + 1)),
        replace(signed_listing, listing=replace(listing, max_duration=max_duration + 1)),
        replace(signed_listing, listing=replace(listing, timestamp=0)),
    ]

    for invalid_signed_listing in invalid_signed_listings:
        print(f"{invalid_signed_listing=}")
        with boa.reverts():
            renting_contract.start_rentals(
                [TokenContextAndListing(token_context, invalid_signed_listing, duration).to_tuple()],
                ZERO_ADDRESS,
                start_time,
                sender=renter,
            )


def test_start_rentals_reverts_if_invalid_listing_signature_params(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    owner_key,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    token_context = TokenContext(token_id, nft_owner, Rental())
    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    invalid_listing_sig_params = [
        (listing, nft_owner_key, owner_key, start_time, boa.env.generate_address("invalid")),
        (listing, nft_owner_key, nft_owner_key, start_time, renting_contract.address),
        (listing, owner_key, owner_key, start_time, renting_contract.address),
    ]

    for invalid_params in invalid_listing_sig_params:
        print(f"{invalid_params=}")
        invalid_signed_listing = sign_listing(*invalid_params)

        with boa.reverts():
            renting_contract.start_rentals(
                [TokenContextAndListing(token_context, invalid_signed_listing, duration).to_tuple()],
                ZERO_ADDRESS,
                start_time,
                sender=renter,
            )


def test_start_rentals_reverts_if_invalid_signature_timestamp(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    vault_contract_def,
    owner,
    owner_key,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    token_context = TokenContext(token_id, nft_owner, Rental())
    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    invalid_timestamp = start_time - 120 - 1
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, invalid_timestamp, renting_contract.address)

    with boa.reverts():
        renting_contract.start_rentals(
            [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
            ZERO_ADDRESS,
            invalid_timestamp,
            sender=renter,
        )


def test_start_rentals_reverts_if_invalid_context(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    vault_contract_def,
    owner,
    owner_key,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    invalid_contexts = [
        TokenContext(0, nft_owner, Rental()),
        TokenContext(token_id, ZERO_ADDRESS, Rental()),
        TokenContext(token_id, nft_owner, Rental(token_id=2)),
    ]

    for invalid_context in invalid_contexts:
        with boa.reverts():
            renting_contract.start_rentals(
                [TokenContextAndListing(invalid_context, signed_listing, duration).to_tuple()],
                ZERO_ADDRESS,
                start_time,
                sender=renter,
            )


def test_start_rentals_reverts_if_misses_listing_conditions(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    vault_contract_def,
    owner,
    owner_key,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    invalid_listings = [
        replace(listing, token_id=token_id + 1),
        replace(listing, min_duration=duration + 1),
        replace(listing, max_duration=duration - 1),
        replace(listing, price=0),
    ]

    for invalid_listing in invalid_listings:
        print(f"{invalid_listing=}")
        with boa.reverts():
            renting_contract.start_rentals(
                [
                    TokenContextAndListing(
                        TokenContext(token_id, nft_owner, Rental()),
                        sign_listing(invalid_listing, nft_owner_key, owner_key, start_time, renting_contract.address),
                        duration,
                    ).to_tuple()
                ],
                ZERO_ADDRESS,
                start_time,
                sender=renter,
            )


def test_start_rentals_reverts_if_listing_is_revoked(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    vault_contract_def,
    owner,
    owner_key,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    token_context = TokenContext(token_id, nft_owner, Rental())
    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)

    renting_contract.revoke_listing([token_context.to_tuple()], sender=nft_owner)

    with boa.reverts():
        renting_contract.start_rentals(
            [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
            ZERO_ADDRESS,
            start_time,
            sender=renter,
        )


def test_start_rentals_reverts_if_nft_not_deposited(
    renting_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    owner,
    owner_key,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    ape_contract.approve(renting_contract, rental_amount, sender=renter)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    with boa.reverts():
        renting_contract.start_rentals(
            [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
            ZERO_ADDRESS,
            start_time,
            sender=renter,
        )


def test_start_rentals_reverts_if_payment_token_not_approved(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    vault_contract_def,
    owner,
    owner_key,
    protocol_wallet,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    with boa.reverts():
        renting_contract.start_rentals(
            [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
            ZERO_ADDRESS,
            start_time,
            sender=renter,
        )


def test_start_rentals_reverts_if_rental_active(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner_key
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        ZERO_ADDRESS,
        start_time,
        sender=renter,
    )

    with boa.reverts():
        renting_contract.start_rentals(
            [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
            ZERO_ADDRESS,
            start_time,
            sender=renter,
        )


def test_revoke(renting_contract, nft_contract, nft_owner, nft_owner_key, protocol_wallet):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    timestamp = boa.eval("block.timestamp")

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.revoke_listing([token_context.to_tuple()], sender=nft_owner)

    assert renting_contract.listing_revocations(token_id) == timestamp


def test_revoke_reverts_if_not_owner(renting_contract, nft_contract, nft_owner, protocol_wallet):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)
    token_context = TokenContext(token_id, nft_owner, Rental())

    with boa.reverts():
        renting_contract.revoke_listing([token_context.to_tuple()], sender=protocol_wallet)


def test_close_rentals(renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner_key):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        ZERO_ADDRESS,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter)

    real_duration = 3
    boa.env.time_travel(seconds=real_duration * 3600)
    real_rental_amount = rental_amount * max(min_duration, real_duration) // duration
    fee_amount = real_rental_amount * PROTOCOL_FEE // 10000

    token_context = TokenContext(token_id, nft_owner, started_rental)

    renting_contract.close_rentals([token_context.to_tuple()], sender=renter)

    assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, Rental())
    assert renting_contract.unclaimed_rewards(nft_owner) == real_rental_amount - fee_amount
    assert renting_contract.protocol_fees_amount() == fee_amount


def test_close_rentals_before_min_duration(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner_key
):
    token_id = 1
    price = int(1e18)
    min_duration = 5
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        ZERO_ADDRESS,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter)

    real_duration = 3
    boa.env.time_travel(seconds=real_duration * 3600)

    real_expiration = int(boa.eval("block.timestamp"))
    real_rental_amount = rental_amount * max(min_duration, real_duration) // duration
    fee_amount = real_rental_amount * PROTOCOL_FEE // 10000

    token_context = TokenContext(token_id, nft_owner, started_rental)
    renting_contract.close_rentals([token_context.to_tuple()], sender=renter)
    rental_closed_event = get_last_event(renting_contract, "RentalClosed")
    event_rental = RentalLog(*rental_closed_event.rentals[0])

    assert event_rental.vault == renting_contract.tokenid_to_vault(token_id)
    assert event_rental.owner == nft_owner
    assert event_rental.token_id == token_id
    assert event_rental.start == start_time
    assert event_rental.min_expiration == start_time + min_duration * 3600
    assert event_rental.expiration == real_expiration
    assert event_rental.amount == real_rental_amount
    assert event_rental.protocol_fee == PROTOCOL_FEE
    assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, Rental())

    assert renting_contract.unclaimed_rewards(nft_owner) == real_rental_amount - fee_amount
    assert renting_contract.protocol_fees_amount() == fee_amount


def test_close_rentals_batch(renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]
    min_duration = 0
    max_duration = 0

    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit(token_ids, nft_owner, sender=nft_owner)

    listings = [Listing(token_id, price, min_duration, max_duration, start_time) for token_id in token_ids]
    signed_listings = [
        sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address) for listing in listings
    ]
    token_contexts = [TokenContext(token_id, nft_owner, Rental()) for token_id in token_ids]

    ape_contract.approve(renting_contract, rental_amount * token_id_qty, sender=renter)

    renting_contract.start_rentals(
        [
            TokenContextAndListing(token_context, signed_listing, duration).to_tuple()
            for token_context, signed_listing in zip(token_contexts, signed_listings)
        ],
        ZERO_ADDRESS,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rentals = [RentalLog(*rental).to_rental(renter=renter) for rental in rental_started_event.rentals]
    token_contexts = [TokenContext(token_id, nft_owner, rental) for token_id, rental in zip(token_ids, started_rentals)]

    real_duration = 3
    boa.env.time_travel(seconds=real_duration * 3600)

    renting_contract.close_rentals([c.to_tuple() for c in token_contexts], sender=renter)

    for token_id in token_ids:
        assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, Rental())


def test_close_rentals_logs_rental_closed(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]
    min_duration = 0
    max_duration = 0

    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit(token_ids, nft_owner, sender=nft_owner)

    listings = [Listing(token_id, price, min_duration, max_duration, start_time) for token_id in token_ids]
    signed_listings = [
        sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address) for listing in listings
    ]
    token_contexts = [TokenContext(token_id, nft_owner, Rental()) for token_id in token_ids]

    ape_contract.approve(renting_contract, rental_amount * token_id_qty, sender=renter)

    renting_contract.start_rentals(
        [
            TokenContextAndListing(token_context, signed_listing, duration).to_tuple()
            for token_context, signed_listing in zip(token_contexts, signed_listings)
        ],
        ZERO_ADDRESS,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rentals = [RentalLog(*rental).to_rental(renter=renter) for rental in rental_started_event.rentals]
    token_contexts = [TokenContext(token_id, nft_owner, rental) for token_id, rental in zip(token_ids, started_rentals)]

    real_duration = 3
    boa.env.time_travel(seconds=real_duration * 3600)
    real_expiration = int(boa.eval("block.timestamp"))
    real_rental_amount = rental_amount * real_duration // duration

    renting_contract.close_rentals([c.to_tuple() for c in token_contexts], sender=renter)
    rental_closed_event = get_last_event(renting_contract, "RentalClosed")

    assert rental_closed_event.renter == renter
    assert rental_closed_event.nft_contract == nft_contract.address
    assert len(rental_closed_event.rentals) == token_id_qty

    for token_id, event_rental in zip(token_ids, rental_closed_event.rentals):
        event_rental = RentalLog(*event_rental)
        assert event_rental.vault == renting_contract.tokenid_to_vault(token_id)
        assert event_rental.owner == nft_owner
        assert event_rental.token_id == token_id
        assert event_rental.start == start_time
        assert event_rental.min_expiration == start_time
        assert event_rental.expiration == real_expiration
        assert event_rental.amount == real_rental_amount
        assert event_rental.protocol_fee == PROTOCOL_FEE


def test_close_rentals_removes_delegation(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    owner,
    owner_key,
    delegation_registry_warm_contract,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    delegate = boa.env.generate_address("delegate")

    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        delegate,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter, delegate=delegate)

    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate

    real_duration = 3
    boa.env.time_travel(seconds=real_duration * 3600)
    token_context = TokenContext(token_id, nft_owner, started_rental)

    renting_contract.close_rentals([token_context.to_tuple()], sender=renter)

    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == ZERO_ADDRESS


def test_close_rentals_reverts_if_invalid_context(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        ZERO_ADDRESS,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter)

    real_duration = 3
    boa.env.time_travel(seconds=real_duration * 3600)
    token_context = TokenContext(token_id, nft_owner, started_rental)

    invalid_contexts = [
        TokenContext(0, nft_owner, Rental()),
        TokenContext(token_id, ZERO_ADDRESS, Rental()),
        TokenContext(token_id, nft_owner, Rental(token_id=2)),
    ]

    for invalid_context in invalid_contexts:
        with boa.reverts():
            renting_contract.close_rentals([invalid_context.to_tuple()], sender=renter)


def test_close_rentals_reverts_if_rental_not_active(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key, protocol_wallet
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    with boa.reverts("active rental does not exist"):
        renting_contract.close_rentals([token_context.to_tuple()], sender=nft_owner)

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        ZERO_ADDRESS,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter)

    real_duration = duration + 1
    boa.env.time_travel(seconds=real_duration * 3600)
    token_context = TokenContext(token_id, nft_owner, started_rental)

    with boa.reverts("active rental does not exist"):
        renting_contract.close_rentals([token_context.to_tuple()], sender=nft_owner)


def test_close_rentals_reverts_if_not_renter(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key, protocol_wallet
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        ZERO_ADDRESS,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter)

    real_duration = 3
    boa.env.time_travel(seconds=real_duration * 3600)
    token_context = TokenContext(token_id, nft_owner, started_rental)

    with boa.reverts("not renter of active rental"):
        renting_contract.close_rentals([token_context.to_tuple()], sender=nft_owner)


def test_renter_delegate_to_wallet(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    owner,
    owner_key,
    delegation_registry_warm_contract,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    delegate = boa.env.generate_address("delegate")

    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        ZERO_ADDRESS,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter)
    token_context = TokenContext(token_id, nft_owner, started_rental)

    renting_contract.renter_delegate_to_wallet([token_context.to_tuple()], delegate, sender=renter)

    active_rental = replace(started_rental, delegate=delegate)
    assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, active_rental)
    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate


def test_renting_delegate_to_wallet_batch(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    owner,
    owner_key,
    delegation_registry_warm_contract,
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]
    min_duration = 0
    max_duration = 0
    delegate = boa.env.generate_address("delegate")

    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit(token_ids, nft_owner, sender=nft_owner)

    listings = [Listing(token_id, price, min_duration, max_duration, start_time) for token_id in token_ids]
    signed_listings = [
        sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address) for listing in listings
    ]
    token_contexts = [TokenContext(token_id, nft_owner, Rental()) for token_id in token_ids]

    ape_contract.approve(renting_contract, rental_amount * token_id_qty, sender=renter)

    renting_contract.start_rentals(
        [
            TokenContextAndListing(token_context, signed_listing, duration).to_tuple()
            for token_context, signed_listing in zip(token_contexts, signed_listings)
        ],
        ZERO_ADDRESS,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rentals = [RentalLog(*rental).to_rental(renter=renter) for rental in rental_started_event.rentals]
    token_contexts = [TokenContext(token_id, nft_owner, rental) for token_id, rental in zip(token_ids, started_rentals)]

    renting_contract.renter_delegate_to_wallet([c.to_tuple() for c in token_contexts], delegate, sender=renter)

    for token_context in token_contexts:
        token_id = token_context.token_id
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        active_rental = replace(token_context.active_rental, delegate=delegate)
        assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, active_rental)
        assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate


def test_renting_delegate_to_wallet_logs_renter_delegated_to_wallet(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    owner,
    owner_key,
    delegation_registry_warm_contract,
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]
    min_duration = 0
    max_duration = 0
    delegate = boa.env.generate_address("delegate")

    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit(token_ids, nft_owner, sender=nft_owner)

    listings = [Listing(token_id, price, min_duration, max_duration, start_time) for token_id in token_ids]
    signed_listings = [
        sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address) for listing in listings
    ]
    token_contexts = [TokenContext(token_id, nft_owner, Rental()) for token_id in token_ids]

    ape_contract.approve(renting_contract, rental_amount * token_id_qty, sender=renter)

    renting_contract.start_rentals(
        [
            TokenContextAndListing(token_context, signed_listing, duration).to_tuple()
            for token_context, signed_listing in zip(token_contexts, signed_listings)
        ],
        ZERO_ADDRESS,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rentals = [RentalLog(*rental).to_rental(renter=renter) for rental in rental_started_event.rentals]
    token_contexts = [TokenContext(token_id, nft_owner, rental) for token_id, rental in zip(token_ids, started_rentals)]

    renting_contract.renter_delegate_to_wallet([c.to_tuple() for c in token_contexts], delegate, sender=renter)

    delegated_event = get_last_event(renting_contract, "RenterDelegatedToWallet")

    assert delegated_event.renter == renter
    assert delegated_event.delegate == delegate
    assert delegated_event.nft_contract == nft_contract.address
    assert len(delegated_event.vaults) == token_id_qty

    for token_id, vault_addr in zip(token_ids, delegated_event.vaults):
        vault = VaultLog(*vault_addr)
        assert renting_contract.tokenid_to_vault(token_id) == vault.vault
        assert token_id == vault.token_id


def test_renting_delegate_to_wallet_reverts_if_invalid_context(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    delegate = boa.env.generate_address("delegate")

    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        ZERO_ADDRESS,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter)

    invalid_contexts = [
        TokenContext(0, nft_owner, started_rental),
        TokenContext(token_id, ZERO_ADDRESS, started_rental),
        TokenContext(token_id, nft_owner, replace(started_rental, id=b"")),
        TokenContext(token_id, nft_owner, replace(started_rental, owner=ZERO_ADDRESS)),
        TokenContext(token_id, nft_owner, replace(started_rental, renter=ZERO_ADDRESS)),
        TokenContext(token_id, nft_owner, replace(started_rental, token_id=0)),
        TokenContext(token_id, nft_owner, replace(started_rental, start=0)),
        TokenContext(token_id, nft_owner, replace(started_rental, min_expiration=0)),
        TokenContext(token_id, nft_owner, replace(started_rental, expiration=0)),
        TokenContext(token_id, nft_owner, replace(started_rental, amount=0)),
        TokenContext(token_id, nft_owner, replace(started_rental, protocol_fee=0)),
        TokenContext(token_id, nft_owner, replace(started_rental, delegate=nft_owner)),
    ]

    for invalid_context in invalid_contexts:
        print(f"invalid_context: {invalid_context}")
        with boa.reverts():
            renting_contract.renter_delegate_to_wallet([invalid_context.to_tuple()], delegate, sender=renter)


def test_renting_delegate_to_wallet_reverts_if_rental_not_active(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    delegate = boa.env.generate_address("delegate")

    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    with boa.reverts("no active rental"):
        renting_contract.renter_delegate_to_wallet([token_context.to_tuple()], delegate, sender=nft_owner)

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()], ZERO_ADDRESS, start_time, sender=renter
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter)

    real_duration = duration + 1
    boa.env.time_travel(seconds=real_duration * 3600)
    token_context = TokenContext(token_id, nft_owner, started_rental)

    with boa.reverts("no active rental"):
        renting_contract.renter_delegate_to_wallet([token_context.to_tuple()], delegate, sender=nft_owner)


def test_renting_delegate_to_wallet_reverts_if_not_renter(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    delegate = boa.env.generate_address("delegate")

    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()], ZERO_ADDRESS, start_time, sender=renter
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter)
    token_context = TokenContext(token_id, nft_owner, started_rental)

    with boa.reverts("not renter"):
        renting_contract.renter_delegate_to_wallet([token_context.to_tuple()], delegate, sender=nft_owner)


def test_extend_rentals(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key, protocol_wallet
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    renter_delegate = boa.env.generate_address("delegate")
    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        renter_delegate,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")

    real_duration = 3
    time_passed = real_duration * 3600
    boa.env.time_travel(seconds=time_passed)
    extend_timestamp = boa.eval("block.timestamp")
    real_rental_amount = rental_amount * max(min_duration, real_duration) // duration
    fee_amount = real_rental_amount * PROTOCOL_FEE // 10000

    active_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter, delegate=renter_delegate)
    token_context = TokenContext(token_id, nft_owner, active_rental)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, extend_timestamp, renting_contract.address)

    ape_contract.approve(renting_contract, rental_amount, sender=renter)

    renting_contract.extend_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()], extend_timestamp, sender=renter
    )
    rental_extended_event = get_last_event(renting_contract, "RentalExtended")
    extended_rental = RentalExtensionLog(*rental_extended_event.rentals[0]).to_rental(renter=renter, delegate=renter_delegate)

    assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, extended_rental)
    assert renting_contract.unclaimed_rewards(nft_owner) == real_rental_amount - fee_amount
    assert renting_contract.protocol_fees_amount() == fee_amount


def test_extend_rentals_extends_delegation(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    renter,
    owner,
    owner_key,
    protocol_wallet,
    delegation_registry_warm_contract,
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    renter_delegate = boa.env.generate_address("delegate")
    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        renter_delegate,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")

    real_duration = 3
    time_passed = real_duration * 3600
    boa.env.time_travel(seconds=time_passed)
    extend_timestamp = boa.eval("block.timestamp")

    active_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter, delegate=renter_delegate)
    token_context = TokenContext(token_id, nft_owner, active_rental)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, extend_timestamp, renting_contract.address)

    ape_contract.approve(renting_contract, rental_amount, sender=renter)

    renting_contract.extend_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()], extend_timestamp, sender=renter
    )

    time_passed = (duration - real_duration) * 3600 + 1
    boa.env.time_travel(seconds=time_passed)

    assert delegation_registry_warm_contract.getHotWalletLink(vault_addr)[0] == renter_delegate
    assert delegation_registry_warm_contract.getHotWalletLink(vault_addr)[1] == extend_timestamp + duration * 3600


def test_extend_rentals_before_min_duration(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key, protocol_wallet
):
    token_id = 1
    price = int(1e18)
    min_duration = 5
    max_duration = 0

    renter_delegate = boa.env.generate_address("delegate")
    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        renter_delegate,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")

    real_duration = 3
    time_passed = real_duration * 3600
    boa.env.time_travel(seconds=time_passed)
    extend_timestamp = boa.eval("block.timestamp")
    real_rental_amount = rental_amount * max(min_duration, real_duration) // duration
    fee_amount = real_rental_amount * PROTOCOL_FEE // 10000

    active_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter, delegate=renter_delegate)
    token_context = TokenContext(token_id, nft_owner, active_rental)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, extend_timestamp, renting_contract.address)

    ape_contract.approve(renting_contract, rental_amount, sender=renter)

    renting_contract.extend_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()], extend_timestamp, sender=renter
    )
    rental_extended_event = get_last_event(renting_contract, "RentalExtended")
    extended_rental = RentalExtensionLog(*rental_extended_event.rentals[0]).to_rental(renter=renter, delegate=renter_delegate)

    assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, extended_rental)
    assert renting_contract.unclaimed_rewards(nft_owner) == real_rental_amount - fee_amount
    assert renting_contract.protocol_fees_amount() == fee_amount


def test_extend_rentals_payback(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key, protocol_wallet
):
    token_id = 1
    price = int(1e18)
    extension_price = int(0.2 * 1e18)
    min_duration = 5
    max_duration = 0

    renter_delegate = boa.env.generate_address("delegate")
    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * price
    extension_amount = extension_price * duration

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, rental_amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        renter_delegate,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")

    real_duration = 3
    time_passed = real_duration * 3600
    boa.env.time_travel(seconds=time_passed)
    extend_timestamp = boa.eval("block.timestamp")
    real_rental_amount = rental_amount * max(min_duration, real_duration) // duration
    fee_amount = real_rental_amount * PROTOCOL_FEE // 10000

    active_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter, delegate=renter_delegate)
    token_context = TokenContext(token_id, nft_owner, active_rental)
    new_listing = Listing(token_id, extension_price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(new_listing, nft_owner_key, owner_key, extend_timestamp, renting_contract.address)

    renter_balance = ape_contract.balanceOf(renter)

    renting_contract.extend_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()], extend_timestamp, sender=renter
    )
    rental_extended_event = get_last_event(renting_contract, "RentalExtended")
    extended_rental = RentalExtensionLog(*rental_extended_event.rentals[0]).to_rental(renter=renter, delegate=renter_delegate)

    assert ape_contract.balanceOf(renter) - renter_balance == rental_amount - real_rental_amount - extension_amount
    assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, extended_rental)
    assert renting_contract.unclaimed_rewards(nft_owner) == real_rental_amount - fee_amount
    assert renting_contract.protocol_fees_amount() == fee_amount


def test_extend_rentals_batch(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key, protocol_wallet
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]
    min_duration = 0
    max_duration = 0

    renter_delegate = boa.env.generate_address("delegate")
    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * int(1e18)

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit(token_ids, nft_owner, sender=nft_owner)

    listings = [Listing(token_id, int(1e18), min_duration, max_duration, start_time) for token_id in token_ids]
    signed_listings = [
        sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address) for listing in listings
    ]
    token_contexts = [TokenContext(token_id, nft_owner, Rental()) for token_id in token_ids]

    ape_contract.approve(renting_contract, rental_amount * token_id_qty, sender=renter)

    renting_contract.start_rentals(
        [
            TokenContextAndListing(token_context, signed_listing, duration).to_tuple()
            for token_context, signed_listing in zip(token_contexts, signed_listings)
        ],
        renter_delegate,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rentals = [
        RentalLog(*rental).to_rental(renter=renter, delegate=renter_delegate) for rental in rental_started_event.rentals
    ]
    token_contexts = [TokenContext(token_id, nft_owner, rental) for token_id, rental in zip(token_ids, started_rentals)]

    real_duration = 3
    time_passed = real_duration * 3600
    extend_timestamp = start_time + time_passed
    boa.env.time_travel(seconds=time_passed)

    signed_listings = [
        sign_listing(listing, nft_owner_key, owner_key, extend_timestamp, renting_contract.address) for listing in listings
    ]
    ape_contract.approve(renting_contract, rental_amount * token_id_qty, sender=renter)

    renting_contract.extend_rentals(
        [
            TokenContextAndListing(token_context, signed_listing, duration).to_tuple()
            for token_context, signed_listing in zip(token_contexts, signed_listings)
        ],
        extend_timestamp,
        sender=renter,
    )
    rental_extended_event = get_last_event(renting_contract, "RentalExtended")

    for token_id, rental in zip(token_ids, rental_extended_event.rentals):
        extended_rental = RentalExtensionLog(*rental).to_rental(renter=renter, delegate=renter_delegate)
        assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, extended_rental)


def test_extend_rentals_logs_rental_extended(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key, protocol_wallet
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]
    min_duration = 0
    max_duration = 0

    renter_delegate = boa.env.generate_address("delegate")
    start_time = boa.eval("block.timestamp")
    duration = 10
    rental_amount = duration * int(1e18)

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit(token_ids, nft_owner, sender=nft_owner)

    listings = [Listing(token_id, int(1e18), min_duration, max_duration, start_time) for token_id in token_ids]
    signed_listings = [
        sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address) for listing in listings
    ]
    token_contexts = [TokenContext(token_id, nft_owner, Rental()) for token_id in token_ids]

    ape_contract.approve(renting_contract, rental_amount * token_id_qty, sender=renter)

    renting_contract.start_rentals(
        [
            TokenContextAndListing(token_context, signed_listing, duration).to_tuple()
            for token_context, signed_listing in zip(token_contexts, signed_listings)
        ],
        renter_delegate,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rentals = [
        RentalLog(*rental).to_rental(renter=renter, delegate=renter_delegate) for rental in rental_started_event.rentals
    ]
    token_contexts = [TokenContext(token_id, nft_owner, rental) for token_id, rental in zip(token_ids, started_rentals)]

    real_duration = 3
    time_passed = real_duration * 3600
    extend_timestamp = start_time + time_passed
    boa.env.time_travel(seconds=time_passed)

    signed_listings = [
        sign_listing(listing, nft_owner_key, owner_key, extend_timestamp, renting_contract.address) for listing in listings
    ]
    ape_contract.approve(renting_contract, rental_amount * token_id_qty, sender=renter)

    renting_contract.extend_rentals(
        [
            TokenContextAndListing(token_context, signed_listing, duration).to_tuple()
            for token_context, signed_listing in zip(token_contexts, signed_listings)
        ],
        extend_timestamp,
        sender=renter,
    )
    rental_extended_event = get_last_event(renting_contract, "RentalExtended")

    assert rental_extended_event.renter == renter
    assert rental_extended_event.nft_contract == nft_contract.address
    assert len(rental_extended_event.rentals) == token_id_qty

    for token_id, rental in zip(token_ids, rental_extended_event.rentals):
        event_rental = RentalExtensionLog(*rental)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        assert event_rental.vault == vault_addr
        assert event_rental.owner == nft_owner
        assert event_rental.token_id == token_id
        assert event_rental.start == extend_timestamp
        assert event_rental.min_expiration == extend_timestamp
        assert event_rental.expiration == extend_timestamp + duration * 3600
        assert event_rental.amount_settled == rental_amount * real_duration // duration
        assert event_rental.extension_amount == rental_amount


def test_extend_rentals_reverts_if_invalid_context(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
        ZERO_ADDRESS,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter)

    real_duration = 3
    time_passed = real_duration * 3600
    boa.env.time_travel(seconds=time_passed)
    extend_timestamp = boa.eval("block.timestamp")
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, extend_timestamp, renting_contract.address)
    ape_contract.approve(renting_contract, amount, sender=renter)

    invalid_contexts = [
        TokenContext(0, nft_owner, started_rental),
        TokenContext(token_id, ZERO_ADDRESS, started_rental),
        TokenContext(token_id, nft_owner, replace(started_rental, id=b"")),
        TokenContext(token_id, nft_owner, replace(started_rental, owner=ZERO_ADDRESS)),
        TokenContext(token_id, nft_owner, replace(started_rental, renter=ZERO_ADDRESS)),
        TokenContext(token_id, nft_owner, replace(started_rental, token_id=0)),
        TokenContext(token_id, nft_owner, replace(started_rental, start=0)),
        TokenContext(token_id, nft_owner, replace(started_rental, min_expiration=0)),
        TokenContext(token_id, nft_owner, replace(started_rental, expiration=0)),
        TokenContext(token_id, nft_owner, replace(started_rental, amount=0)),
        TokenContext(token_id, nft_owner, replace(started_rental, protocol_fee=0)),
        TokenContext(token_id, nft_owner, replace(started_rental, delegate=nft_owner)),
    ]

    for invalid_context in invalid_contexts:
        print(f"invalid_context: {invalid_context}")
        with boa.reverts():
            renting_contract.extend_rentals(
                [TokenContextAndListing(invalid_context, signed_listing, duration).to_tuple()], extend_timestamp, sender=renter
            )


def test_extend_rentals_reverts_if_rental_not_active(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    with boa.reverts("no active rental"):
        renting_contract.extend_rentals(
            [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()], start_time, sender=renter
        )

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()], ZERO_ADDRESS, start_time, sender=renter
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter)

    real_duration = duration + 1
    time_passed = real_duration * 3600
    boa.env.time_travel(seconds=time_passed)
    extend_timestamp = boa.eval("block.timestamp")
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, extend_timestamp, renting_contract.address)
    ape_contract.approve(renting_contract, amount, sender=renter)

    token_context = TokenContext(token_id, nft_owner, started_rental)
    with boa.reverts("no active rental"):
        renting_contract.extend_rentals(
            [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()], extend_timestamp, sender=renter
        )


def test_extend_rentals_reverts_if_not_renter(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()], ZERO_ADDRESS, start_time, sender=renter
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter)

    real_duration = 3
    time_passed = real_duration * 3600
    extend_timestamp = start_time + time_passed
    boa.env.time_travel(seconds=time_passed)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, extend_timestamp, renting_contract.address)

    ape_contract.approve(renting_contract, amount, sender=nft_owner)

    token_context = TokenContext(token_id, nft_owner, started_rental)
    with boa.reverts("not renter of active rental"):
        renting_contract.extend_rentals(
            [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()], extend_timestamp, sender=nft_owner
        )


def test_extend_rentals_reverts_if_misses_listing_conditions(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()], ZERO_ADDRESS, start_time, sender=renter
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter)
    token_context = TokenContext(token_id, nft_owner, started_rental)

    real_duration = 3
    time_passed = real_duration * 3600
    extend_timestamp = start_time + time_passed
    boa.env.time_travel(seconds=time_passed)

    ape_contract.approve(renting_contract, amount, sender=renter)

    invalid_listings = [
        replace(listing, token_id=token_id + 1),
        replace(listing, min_duration=duration + 1),
        replace(listing, max_duration=duration - 1),
        replace(listing, price=0),
    ]

    for invalid_listing in invalid_listings:
        print(f"{invalid_listing=}")
        signed_listing = sign_listing(invalid_listing, nft_owner_key, owner_key, extend_timestamp, renting_contract.address)
        with boa.reverts():
            renting_contract.extend_rentals(
                [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
                extend_timestamp,
                sender=renter,
            )


def test_extend_rentals_reverts_if_invalid_signature(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()], ZERO_ADDRESS, start_time, sender=renter
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter)
    token_context = TokenContext(token_id, nft_owner, started_rental)

    real_duration = 3
    time_passed = real_duration * 3600
    extend_timestamp = start_time + time_passed
    boa.env.time_travel(seconds=time_passed)

    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    invalid_signed_listings = [
        replace(signed_listing, owner_signature=replace(signed_listing.owner_signature, v=0)),
        replace(signed_listing, owner_signature=replace(signed_listing.owner_signature, r=0)),
        replace(signed_listing, owner_signature=replace(signed_listing.owner_signature, s=0)),
        replace(signed_listing, admin_signature=replace(signed_listing.admin_signature, v=0)),
        replace(signed_listing, admin_signature=replace(signed_listing.admin_signature, r=0)),
        replace(signed_listing, admin_signature=replace(signed_listing.admin_signature, s=0)),
        replace(signed_listing, listing=replace(listing, token_id=token_id + 1)),
        replace(signed_listing, listing=replace(listing, price=price + 1)),
        replace(signed_listing, listing=replace(listing, min_duration=min_duration + 1)),
        replace(signed_listing, listing=replace(listing, max_duration=max_duration + 1)),
        replace(signed_listing, listing=replace(listing, timestamp=0)),
    ]

    for invalid_signed_listing in invalid_signed_listings:
        print(f"{invalid_signed_listing=}")
        with boa.reverts():
            renting_contract.extend_rentals(
                [TokenContextAndListing(token_context, invalid_signed_listing, duration).to_tuple()],
                extend_timestamp,
                sender=renter,
            )


def test_extend_rentals_reverts_if_insufficient_allowance(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()], ZERO_ADDRESS, start_time, sender=renter
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter)
    token_context = TokenContext(token_id, nft_owner, started_rental)

    real_duration = 3
    time_passed = real_duration * 3600
    extend_timestamp = start_time + time_passed
    extension_amount = amount * real_duration // duration
    boa.env.time_travel(seconds=time_passed)

    ape_contract.approve(renting_contract, extension_amount - 1, sender=renter)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, extend_timestamp, renting_contract.address)

    with boa.reverts():
        renting_contract.extend_rentals(
            [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
            extend_timestamp,
            sender=renter,
        )


def test_extend_rentals_reverts_if_listing_not_active(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()], ZERO_ADDRESS, start_time, sender=renter
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter)
    token_context = TokenContext(token_id, nft_owner, started_rental)

    real_duration = 3
    time_passed = real_duration * 3600
    extend_timestamp = start_time + time_passed
    boa.env.time_travel(seconds=time_passed)

    ape_contract.approve(renting_contract, amount, sender=renter)
    signed_listing = sign_listing(
        replace(listing, price=0), nft_owner_key, owner_key, extend_timestamp, renting_contract.address
    )

    with boa.reverts("listing not active"):
        renting_contract.extend_rentals(
            [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
            extend_timestamp,
            sender=renter,
        )


def test_extend_rentals_reverts_if_listing_is_revoked(
    renting_contract, nft_contract, ape_contract, nft_owner, nft_owner_key, renter, owner, owner_key
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    duration = 10
    amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, amount, sender=renter)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()], ZERO_ADDRESS, start_time, sender=renter
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter)
    token_context = TokenContext(token_id, nft_owner, started_rental)

    renting_contract.revoke_listing([token_context.to_tuple()], sender=nft_owner)

    real_duration = 3
    time_passed = real_duration * 3600
    extend_timestamp = start_time + time_passed
    boa.env.time_travel(seconds=time_passed)

    ape_contract.approve(renting_contract, amount, sender=renter)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, extend_timestamp, renting_contract.address)

    with boa.reverts("listing revoked"):
        renting_contract.extend_rentals(
            [TokenContextAndListing(token_context, signed_listing, duration).to_tuple()],
            extend_timestamp,
            sender=renter,
        )
