import boa

from ...conftest_base import (
    ZERO_ADDRESS,
    Listing,
    Rental,
    RentalLog,
    RewardLog,
    TokenContext,
    TokenContextAndListing,
    get_last_event,
    sign_listing,
)

FOREVER = 2**256 - 1
PROTOCOL_FEE = 500


def test_claim(
    renting_contract, nft_owner, nft_owner_key, renter, nft_contract, ape_contract, owner, owner_key, protocol_wallet
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]
    min_duration = 0
    max_duration = 0

    token_id = 1
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
            TokenContextAndListing(token_context, signed_listing).to_tuple()
            for token_context, signed_listing in zip(token_contexts, signed_listings)
        ],
        duration,
        ZERO_ADDRESS,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rentals = [RentalLog(*rental).to_rental(renter=renter) for rental in rental_started_event.rentals]
    token_contexts = [TokenContext(token_id, nft_owner, rental) for token_id, rental in zip(token_ids, started_rentals)]

    boa.env.time_travel(duration * 3600 + 1)

    total_fees = rental_amount * token_id_qty * PROTOCOL_FEE // 10000
    total_rewards = rental_amount * token_id_qty - total_fees
    nft_owner_balance = ape_contract.balanceOf(nft_owner)

    renting_contract.claim([c.to_tuple() for c in token_contexts], sender=nft_owner)

    assert renting_contract.unclaimed_rewards(nft_owner) == 0
    assert renting_contract.protocol_fees_amount() == total_fees

    assert ape_contract.balanceOf(nft_owner) == nft_owner_balance + total_rewards


def test_claim_logs_rewards_claimed(
    renting_contract, nft_owner, nft_owner_key, renter, nft_contract, ape_contract, owner, owner_key, protocol_wallet
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]
    min_duration = 0
    max_duration = 0

    token_id = 1
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
            TokenContextAndListing(token_context, signed_listing).to_tuple()
            for token_context, signed_listing in zip(token_contexts, signed_listings)
        ],
        duration,
        ZERO_ADDRESS,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rentals = [RentalLog(*rental).to_rental(renter=renter) for rental in rental_started_event.rentals]
    token_contexts = [TokenContext(token_id, nft_owner, rental) for token_id, rental in zip(token_ids, started_rentals)]

    boa.env.time_travel(duration * 3600 + 1)

    total_fees = rental_amount * token_id_qty * PROTOCOL_FEE // 10000
    total_rewards = rental_amount * token_id_qty - total_fees

    renting_contract.claim([c.to_tuple() for c in token_contexts], sender=nft_owner)

    claim_event = get_last_event(renting_contract, "RewardsClaimed")
    assert claim_event.owner == nft_owner
    assert claim_event.amount == total_rewards
    assert claim_event.protocol_fee_amount == total_fees
    assert len(claim_event.rewards) == token_id_qty

    for token_id, reward in zip(token_ids, claim_event.rewards):
        reward = RewardLog(*reward)
        assert reward.token_id == token_id
        assert reward.active_rental_amount == 0


def test_claim_pays_unclaimed_rewards(renting_contract, nft_owner, renter, nft_contract, ape_contract, owner, protocol_wallet):
    unclaimed_rewards = 100
    protocol_fees_amount = 50
    nft_owner_balance = ape_contract.balanceOf(nft_owner)

    ape_contract.mint(renting_contract, unclaimed_rewards + protocol_fees_amount, sender=owner)
    renting_contract.eval(f"self.unclaimed_rewards[{nft_owner}] = {unclaimed_rewards}")
    renting_contract.eval(f"self.protocol_fees_amount = {protocol_fees_amount}")

    renting_contract.claim([], sender=nft_owner)

    assert renting_contract.unclaimed_rewards(nft_owner) == 0
    assert renting_contract.protocol_fees_amount() == protocol_fees_amount
    assert ape_contract.balanceOf(nft_owner) == nft_owner_balance + unclaimed_rewards


def test_claim_reverts_if_invalid_context(renting_contract, nft_owner, renter, nft_contract, ape_contract, owner):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    invalid_contexts = [
        TokenContext(0, nft_owner, Rental()),
        TokenContext(token_id, ZERO_ADDRESS, Rental()),
        TokenContext(token_id, nft_owner, Rental(id=b"01")),
        TokenContext(token_id, nft_owner, Rental(owner=nft_owner)),
        TokenContext(token_id, nft_owner, Rental(renter=nft_owner)),
        TokenContext(token_id, nft_owner, Rental(token_id=1)),
        TokenContext(token_id, nft_owner, Rental(start=1)),
        TokenContext(token_id, nft_owner, Rental(min_expiration=1)),
        TokenContext(token_id, nft_owner, Rental(expiration=1)),
        TokenContext(token_id, nft_owner, Rental(amount=1)),
        TokenContext(token_id, nft_owner, Rental(protocol_fee=1)),
        TokenContext(token_id, nft_owner, Rental(delegate=nft_owner)),
    ]

    for invalid_context in invalid_contexts:
        print(f"invalid_context: {invalid_context}")
        with boa.reverts("invalid context"):
            renting_contract.claim([invalid_context.to_tuple()], sender=nft_owner)


def test_claim_reverts_if_not_owner(renting_contract, nft_owner, renter, nft_contract, ape_contract, owner):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    token_context = TokenContext(token_id, nft_owner, Rental())

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    with boa.reverts("not owner"):
        renting_contract.claim([token_context.to_tuple()], sender=renter)


def test_claim_reverts_if_no_rewards_to_claim(renting_contract, nft_owner, renter, nft_contract, ape_contract, owner):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    token_context = TokenContext(token_id, nft_owner, Rental())

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    with boa.reverts("no rewards to claim"):
        renting_contract.claim([token_context.to_tuple()], sender=nft_owner)


def test_claim_fees(renting_contract, protocol_wallet, owner, ape_contract):
    protocol_fees_amount = 100
    protocol_wallet_balance = ape_contract.balanceOf(protocol_wallet)

    ape_contract.mint(renting_contract, protocol_fees_amount, sender=owner)
    renting_contract.eval(f"self.protocol_fees_amount = {protocol_fees_amount}")

    renting_contract.claim_fees(sender=owner)

    assert renting_contract.eval("self.protocol_fees_amount") == 0
    assert ape_contract.balanceOf(protocol_wallet) == protocol_wallet_balance + protocol_fees_amount


def test_claim_fees_reverts_if_not_admin(renting_contract, protocol_wallet, owner, ape_contract):
    with boa.reverts("not admin"):
        renting_contract.claim_fees(sender=protocol_wallet)


def test_claimable_rewards(
    renting_contract, nft_owner, nft_owner_key, renter, nft_contract, ape_contract, owner, owner_key, protocol_wallet
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]
    min_duration = 0
    max_duration = 0

    token_id = 1
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
            TokenContextAndListing(token_context, signed_listing).to_tuple()
            for token_context, signed_listing in zip(token_contexts, signed_listings)
        ],
        duration,
        ZERO_ADDRESS,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    started_rentals = [RentalLog(*rental).to_rental(renter=renter) for rental in rental_started_event.rentals]
    token_contexts = [TokenContext(token_id, nft_owner, rental) for token_id, rental in zip(token_ids, started_rentals)]

    boa.env.time_travel(duration * 3600 + 1)

    assert renting_contract.unclaimed_rewards(nft_owner) == 0

    total_fees = rental_amount * token_id_qty * PROTOCOL_FEE // 10000
    total_rewards = rental_amount * token_id_qty - total_fees
    nft_owner_balance = ape_contract.balanceOf(nft_owner)

    claimable_rewards = renting_contract.claimable_rewards(nft_owner, [c.to_tuple() for c in token_contexts], sender=nft_owner)

    assert claimable_rewards == total_rewards
    assert renting_contract.unclaimed_rewards(nft_owner) == 0
    assert ape_contract.balanceOf(nft_owner) == nft_owner_balance
