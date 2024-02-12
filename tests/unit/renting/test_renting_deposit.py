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
    assert renting_contract.ownerOf(token_id) == nft_owner

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.delegate == ZERO_ADDRESS

    vault_log = VaultLog(*event.vaults[-1])
    assert vault_log.vault == vault_addr
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
    assert renting_contract.ownerOf(token_id) == nft_owner

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
    assert renting_contract.ownerOf(token_id) == nft_owner

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


def test_withdraw_logs_nfts_withdrawn(
    renting_contract, nft_contract, nft_owner, vault_contract_def, protocol_wallet, delegation_registry_warm_contract
):
    token_id = 1

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    renting_contract.withdraw([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=nft_owner)
    event = get_last_event(renting_contract, "NftsWithdrawn")

    withdrawal_log = WithdrawalLog(*event.withdrawals[0])
    assert withdrawal_log.vault == vault_addr
    assert withdrawal_log.token_id == token_id
    assert withdrawal_log.rewards == 0
    assert withdrawal_log.protocol_fee_amount == 0

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


def test_withdraw_burns_renting_token(
    renting_contract, nft_contract, nft_owner, vault_contract_def, protocol_wallet, delegation_registry_warm_contract
):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    renting_contract.withdraw([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=nft_owner)
    event = get_events(renting_contract, "Transfer")[0]

    assert event.sender == nft_owner
    assert event.receiver == ZERO_ADDRESS
    assert event.tokenId == token_id

    with boa.reverts():
        assert renting_contract.ownerOf(token_id) == nft_owner


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
