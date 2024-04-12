from dataclasses import replace

import boa

from ...conftest_base import (
    ZERO_ADDRESS,
    Listing,
    Rental,
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


def test_delegate_to_wallet(
    renting_contract, nft_contract, ape_contract, nft_owner, renter, owner, delegation_registry_warm_contract
):
    token_id = 1
    delegate = boa.env.generate_address("delegate")

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == ZERO_ADDRESS

    token_context = TokenContext(token_id, nft_owner, Rental())
    renting_contract.delegate_to_wallet([token_context.to_tuple()], delegate, sender=nft_owner)

    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate

    event = get_last_event(renting_contract, "DelegatedToWallet")

    assert event.owner == nft_owner
    assert event.delegate == delegate
    assert event.nft_contract == nft_contract.address
    assert len(event.vaults) == 1

    vault_log = VaultLog(*event.vaults[0])
    assert vault_log.vault == vault_addr
    assert vault_log.token_id == token_id


def test_delegate_to_wallet_batch(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    renter,
    owner,
    delegation_registry_warm_contract,
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]

    token_contexts = [TokenContext(token_id, nft_owner, Rental()).to_tuple() for token_id in token_ids]
    vaults = {}
    delegate = boa.env.generate_address("delegate")

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        vaults[token_id] = vault_addr

    renting_contract.deposit(token_ids, ZERO_ADDRESS, sender=nft_owner)

    renting_contract.delegate_to_wallet(token_contexts, delegate, sender=nft_owner)

    for token_id in token_ids:
        assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate

    event = get_last_event(renting_contract, "DelegatedToWallet")

    assert event.owner == nft_owner
    assert event.delegate == delegate
    assert event.nft_contract == nft_contract.address
    assert len(event.vaults) == token_id_qty

    for token_id, vault_log in zip(token_ids, event.vaults):
        vault_log = VaultLog(*vault_log)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate
        assert vault_log.vault == vault_addr
        assert vault_log.token_id == token_id


def test_delegate_to_wallet_reverts_if_invalid_context(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    renter,
    owner,
    delegation_registry_warm_contract,
):
    token_id = 1
    delegate = boa.env.generate_address("delegate")

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    with boa.reverts():
        renting_contract.delegate_to_wallet([TokenContext(0, nft_owner, Rental()).to_tuple()], delegate, sender=nft_owner)

    with boa.reverts():
        renting_contract.delegate_to_wallet(
            [TokenContext(token_id, ZERO_ADDRESS, Rental()).to_tuple()], delegate, sender=nft_owner
        )

    with boa.reverts():
        renting_contract.delegate_to_wallet(
            [TokenContext(token_id, nft_owner, Rental(token_id=2)).to_tuple()], delegate, sender=nft_owner
        )

    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == ZERO_ADDRESS


def test_delegate_to_wallet_reverts_if_not_nft_owner(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    renter,
    owner,
    delegation_registry_warm_contract,
):
    token_id = 1
    delegate = boa.env.generate_address("delegate")

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    with boa.reverts():
        renting_contract.delegate_to_wallet([TokenContext(token_id, nft_owner, Rental()).to_tuple()], delegate, sender=renter)

    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == ZERO_ADDRESS


def test_delegate_to_wallet_reverts_if_rental_active(
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
    start_time = boa.eval("block.timestamp")
    delegate = boa.env.generate_address("delegate")
    rental_delegate = boa.env.generate_address("rental_delegate")
    amount = int(1e18)

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(renting_contract, amount, sender=renter)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    listing = Listing(token_id, amount, 0, 0, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())
    print(f"token_context: {token_context}")

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing, 1).to_tuple()], rental_delegate, start_time, sender=renter
    )
    event = get_last_event(renting_contract, "RentalStarted")
    rental = RentalLog(*event.rentals[0]).to_rental(renter=renter, delegate=rental_delegate)

    token_context = TokenContext(token_id, nft_owner, rental)
    print(f"token_context: {token_context}")

    with boa.reverts("active rental"):
        renting_contract.delegate_to_wallet([token_context.to_tuple()], delegate, sender=nft_owner)

    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == rental_delegate


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
