import boa

from ...conftest_base import (
    ZERO_ADDRESS,
    ZERO_BYTES32,
    Listing,
    Rental,
    RentalLog,
    TokenContext,
    TokenContextAndListing,
    VaultLog,
    WithdrawalLog,
    compute_state_hash,
    get_events,
    get_last_event,
    sign_listing,
)

FOREVER = 2**256 - 1
PROTOCOL_FEE = 500


def test_deposit(renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract):
    token_id = 1

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)
    event = get_last_event(renting_contract, "NftsDeposited")

    assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, Rental())
    assert nft_contract.ownerOf(token_id) == vault_addr
    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == ZERO_ADDRESS

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.delegate == ZERO_ADDRESS

    vault_log = VaultLog(*event.vaults[-1])
    assert vault_log.vault == vault_addr
    assert vault_log.token_id == token_id


def test_deposit_batch(renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract, owner):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit(token_ids, ZERO_ADDRESS, sender=nft_owner)

    event = get_last_event(renting_contract, "NftsDeposited")

    for token_id in token_ids:
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, Rental())
        assert nft_contract.ownerOf(token_id) == vault_addr
        assert delegation_registry_warm_contract.getHotWallet(vault_addr) == ZERO_ADDRESS

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.delegate == ZERO_ADDRESS

    for token_id, vault_log in zip(token_ids, event.vaults):
        vault_log = VaultLog(*vault_log)
        assert vault_log.vault == renting_contract.tokenid_to_vault(token_id)
        assert vault_log.token_id == token_id


def test_deposit_with_delegate(renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract):
    token_id = 1
    delegate = boa.env.generate_address("delegate")

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit([token_id], delegate, sender=nft_owner)
    event = get_last_event(renting_contract, "NftsDeposited")

    assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, Rental())
    assert nft_contract.ownerOf(token_id) == vault_addr
    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.delegate == delegate

    vault_log = VaultLog(*event.vaults[-1])
    assert vault_log.vault == vault_addr
    assert vault_log.token_id == token_id


def test_deposit_after_withdraw(renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract):
    token_id = 1
    delegate = boa.env.generate_address("delegate")

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], delegate, sender=nft_owner)
    renting_contract.withdraw([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=nft_owner)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], delegate, sender=nft_owner)
    event = get_last_event(renting_contract, "NftsDeposited")

    assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, Rental())
    assert nft_contract.ownerOf(token_id) == vault_addr
    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.delegate == delegate

    vault_log = VaultLog(*event.vaults[-1])
    assert vault_log.vault == vault_addr
    assert vault_log.token_id == token_id


def test_withdraw(
    renting_contract, nft_contract, nft_owner, vault_contract_def, protocol_wallet, delegation_registry_warm_contract
):
    token_id = 1

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    renting_contract.withdraw([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=nft_owner)

    assert renting_contract.rental_states(token_id) == ZERO_BYTES32
    assert nft_contract.ownerOf(token_id) == nft_owner


def test_withdraw_batch(
    renting_contract, nft_contract, nft_owner, vault_contract_def, protocol_wallet, delegation_registry_warm_contract, owner
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit(token_ids, ZERO_ADDRESS, sender=nft_owner)
    renting_contract.withdraw(
        [TokenContext(token_id, nft_owner, Rental()).to_tuple() for token_id in token_ids], sender=nft_owner
    )

    for token_id in token_ids:
        assert renting_contract.rental_states(token_id) == ZERO_BYTES32
        assert nft_contract.ownerOf(token_id) == nft_owner


def test_withdraw_logs_nfts_withdrawn(renting_contract, nft_contract, nft_owner, vault_contract_def, protocol_wallet, owner):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit(token_ids, ZERO_ADDRESS, sender=nft_owner)
    renting_contract.withdraw(
        [TokenContext(token_id, nft_owner, Rental()).to_tuple() for token_id in token_ids], sender=nft_owner
    )
    event = get_last_event(renting_contract, "NftsWithdrawn")

    for token_id, withdrawal_log in zip(token_ids, event.withdrawals):
        withdrawal_log = WithdrawalLog(*withdrawal_log)
        assert withdrawal_log.vault == renting_contract.tokenid_to_vault(token_id)
        assert withdrawal_log.token_id == token_id

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.total_rewards == 0


def test_withdraw_removes_delegation(
    renting_contract, nft_contract, nft_owner, vault_contract_def, protocol_wallet, delegation_registry_warm_contract
):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    renting_contract.withdraw([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=nft_owner)

    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == ZERO_ADDRESS


def test_withdraw_reverts_if_not_owner(
    renting_contract, nft_contract, nft_owner, vault_contract_def, protocol_wallet, delegation_registry_warm_contract
):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    with boa.reverts():
        renting_contract.withdraw([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=protocol_wallet)


def test_withdraw_reverts_if_active_rental(
    renting_contract,
    nft_contract,
    ape_contract,
    nft_owner,
    nft_owner_key,
    owner_key,
    renter,
    vault_contract_def,
    protocol_wallet,
    delegation_registry_warm_contract,
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
        [TokenContextAndListing(token_context, signed_listing).to_tuple()],
        duration,
        renter_delegate,
        start_time,
        sender=renter,
    )
    event = get_last_event(renting_contract, "RentalStarted")
    event_rental = RentalLog(*event.rentals[0])

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

    with boa.reverts("active rental"):
        renting_contract.withdraw([TokenContext(token_id, nft_owner, rental).to_tuple()], sender=nft_owner)


def test_withdraw_reverts_if_invalid_context(
    renting_contract, nft_contract, nft_owner, vault_contract_def, protocol_wallet, delegation_registry_warm_contract
):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)

    with boa.reverts():
        renting_contract.withdraw([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=nft_owner)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    with boa.reverts():
        renting_contract.withdraw([TokenContext(0, nft_owner, Rental()).to_tuple()], sender=nft_owner)

    with boa.reverts():
        renting_contract.withdraw([TokenContext(token_id, ZERO_ADDRESS, Rental()).to_tuple()], sender=nft_owner)

    with boa.reverts():
        renting_contract.withdraw([TokenContext(token_id, nft_owner, Rental(token_id=2)).to_tuple()], sender=nft_owner)


def test_withdraw_burns_renting_token_if_minted(renting_contract, renting721_contract, nft_contract, nft_owner):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    token_context = TokenContext(token_id, nft_owner, Rental()).to_tuple()
    renting_contract.mint([token_context], sender=nft_owner)

    renting_contract.withdraw([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=nft_owner)
    _, event = get_events(renting_contract, "Transfer")

    assert event.sender == nft_owner
    assert event.receiver == ZERO_ADDRESS
    assert event.tokenId == token_id

    assert renting721_contract.balanceOf(nft_owner) == 0
    assert nft_contract.ownerOf(token_id) == nft_owner
    with boa.reverts():
        renting721_contract.ownerOf(token_id)


def test_mint(renting_contract, nft_contract, nft_owner, renting721_contract):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)
    token_context = TokenContext(token_id, nft_owner, Rental()).to_tuple()
    renting_contract.mint([token_context], sender=nft_owner)

    event = get_last_event(renting_contract, "Transfer")

    assert event.sender == ZERO_ADDRESS
    assert event.receiver == nft_owner
    assert event.tokenId == token_id

    assert nft_contract.ownerOf(token_id) == vault_addr
    assert renting721_contract.ownerOf(token_id) == nft_owner
    assert renting721_contract.balanceOf(nft_owner) == 1


def test_mint_batch(renting_contract, nft_contract, nft_owner, renting721_contract, owner):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit(token_ids, ZERO_ADDRESS, sender=nft_owner)
    token_contexts = [TokenContext(token_id, nft_owner, Rental()).to_tuple() for token_id in token_ids]
    renting_contract.mint(token_contexts, sender=nft_owner)
    events = get_events(renting_contract, "Transfer")

    for token_id, event in zip(token_ids, events):
        assert event.sender == ZERO_ADDRESS
        assert event.receiver == nft_owner
        assert event.tokenId == token_id

        assert nft_contract.ownerOf(token_id) == renting_contract.tokenid_to_vault(token_id)
        assert renting721_contract.ownerOf(token_id) == nft_owner

    assert renting721_contract.balanceOf(nft_owner) == token_id_qty


def test_mint_reverts_if_invalid_context(renting_contract, nft_owner, nft_contract, renter):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    invalid_contexts = [
        TokenContext(0, nft_owner, Rental()),
        TokenContext(token_id, ZERO_ADDRESS, Rental()),
        TokenContext(token_id, nft_owner, Rental(id=b"12")),
        TokenContext(token_id, nft_owner, Rental(owner=renter)),
        TokenContext(token_id, nft_owner, Rental(renter=renter)),
        TokenContext(token_id, nft_owner, Rental(token_id=1)),
        TokenContext(token_id, nft_owner, Rental(start=1)),
        TokenContext(token_id, nft_owner, Rental(min_expiration=1)),
        TokenContext(token_id, nft_owner, Rental(expiration=1)),
        TokenContext(token_id, nft_owner, Rental(amount=1)),
        TokenContext(token_id, nft_owner, Rental(protocol_fee=1)),
        TokenContext(token_id, nft_owner, Rental(delegate=renter)),
    ]

    for invalid_context in invalid_contexts:
        print(f"invalid_context: {invalid_context}")
        with boa.reverts():
            renting_contract.mint([invalid_context.to_tuple()], sender=renter)


def test_mint_reverts_if_not_deposited(renting_contract, nft_owner, nft_contract, renter):
    token_id = 1
    token_context = TokenContext(token_id, nft_owner, Rental()).to_tuple()
    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    with boa.reverts("invalid context"):
        renting_contract.mint([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=nft_owner)

    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)
    renting_contract.mint([token_context], sender=nft_owner)
    renting_contract.withdraw([token_context], sender=nft_owner)

    with boa.reverts("invalid context"):
        renting_contract.mint([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=nft_owner)
