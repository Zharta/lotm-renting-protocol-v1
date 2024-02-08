from decimal import Decimal

import boa
import pytest

from ...conftest_base import (
    ZERO_ADDRESS,
    ZERO_BYTES32,
    Listing,
    Rental,
    Signature,
    SignedListing,
    RentalLog,
    RewardLog,
    TokenContext,
    TokenContextAndListing,
    VaultLog,
    WithdrawalLog,
    compute_state_hash,
    deploy_reverts,
    get_events,
    get_last_event,
    sign_listing,
    sign_listings,
)

FOREVER = 2**256 - 1
PROTOCOL_FEE = 500


@pytest.fixture(scope="module")
def vault_contract(vault_contract_def, ape_contract, nft_contract, delegation_registry_warm_contract):
    return vault_contract_def.deploy(ape_contract, nft_contract, delegation_registry_warm_contract, ZERO_ADDRESS)


@pytest.fixture(scope="module")
def renting_contract(
    renting_contract_def, vault_contract, ape_contract, nft_contract, delegation_registry_warm_contract, protocol_wallet, owner
):
    return renting_contract_def.deploy(
        vault_contract,
        ape_contract,
        nft_contract,
        delegation_registry_warm_contract,
        ZERO_ADDRESS,
        0,
        PROTOCOL_FEE,
        PROTOCOL_FEE,
        protocol_wallet,
        owner,
    )


@pytest.fixture(scope="module")
def renting_contract_no_fee(
    renting_contract_def, vault_contract, ape_contract, nft_contract, delegation_registry_warm_contract, protocol_wallet
):
    return renting_contract_def.deploy(
        vault_contract,
        ape_contract,
        nft_contract,
        delegation_registry_warm_contract,
        ZERO_ADDRESS,
        0,
        0,
        0,
        protocol_wallet,
        protocol_wallet,
    )


@pytest.fixture(autouse=True)
def mint(nft_owner, owner, renter, nft_contract, ape_contract):
    with boa.env.anchor():
        nft_contract.mint(nft_owner, 1, sender=owner)
        ape_contract.mint(renter, int(1000 * 1e18), sender=owner)
        yield


def test_deploy_validation(
    renting_contract_def, vault_contract, ape_contract, nft_contract, delegation_registry_warm_contract, protocol_wallet
):
    with deploy_reverts():
        renting_contract_def.deploy(
            vault_contract,
            ape_contract,
            nft_contract,
            delegation_registry_warm_contract,
            ZERO_ADDRESS,
            0,
            0,
            0,
            ZERO_ADDRESS,
            protocol_wallet
        )

    with deploy_reverts():
        renting_contract_def.deploy(
            vault_contract,
            ape_contract,
            nft_contract,
            delegation_registry_warm_contract,
            ZERO_ADDRESS,
            0,
            0,
            0,
            protocol_wallet,
            ZERO_ADDRESS
        )
    with deploy_reverts():
        renting_contract_def.deploy(
            vault_contract,
            ape_contract,
            nft_contract,
            delegation_registry_warm_contract,
            ZERO_ADDRESS,
            0,
            10001,
            0,
            protocol_wallet,
            protocol_wallet
        )

    with deploy_reverts():
        renting_contract_def.deploy(
            vault_contract,
            ape_contract,
            nft_contract,
            delegation_registry_warm_contract,
            ZERO_ADDRESS,
            0,
            0,
            1,
            protocol_wallet,
            protocol_wallet
        )

    with deploy_reverts():
        renting_contract_def.deploy(
            ZERO_ADDRESS,
            ZERO_ADDRESS,
            ZERO_ADDRESS,
            ZERO_ADDRESS,
            ZERO_ADDRESS,
            0,
            0,
            1,
            protocol_wallet,
            protocol_wallet
        )


def test_initial_state(
    vault_contract, renting_contract, nft_contract, ape_contract, delegation_registry_warm_contract, protocol_wallet, owner
):
    assert renting_contract.vault_impl_addr() == vault_contract.address
    assert renting_contract.payment_token() == ape_contract.address
    assert renting_contract.nft_contract_addr() == nft_contract.address
    assert renting_contract.delegation_registry_addr() == delegation_registry_warm_contract.address
    assert renting_contract.staking_addr() == ZERO_ADDRESS
    assert renting_contract.protocol_admin() == owner
    assert renting_contract.protocol_wallet() == protocol_wallet
    assert renting_contract.max_protocol_fee() == PROTOCOL_FEE
    assert renting_contract.protocol_fee() == PROTOCOL_FEE


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
    renting_contract,
    nft_contract,
    nft_owner,
    vault_contract_def,
    protocol_wallet,
    delegation_registry_warm_contract
):
    token_id = 1

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    renting_contract.withdraw([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=nft_owner)

    assert renting_contract.rental_states(token_id) == ZERO_BYTES32
    assert nft_contract.ownerOf(token_id) == nft_owner



def test_withdraw_logs_nfts_withdrawn(
    renting_contract,
    nft_contract,
    nft_owner,
    vault_contract_def,
    protocol_wallet,
    delegation_registry_warm_contract
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
    renting_contract,
    nft_contract,
    nft_owner,
    vault_contract_def,
    protocol_wallet,
    delegation_registry_warm_contract
):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    renting_contract.withdraw([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=nft_owner)

    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == ZERO_ADDRESS


def test_withdraw_burns_renting_token(
    renting_contract,
    nft_contract,
    nft_owner,
    vault_contract_def,
    protocol_wallet,
    delegation_registry_warm_contract
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
    renting_contract,
    nft_contract,
    nft_owner,
    vault_contract_def,
    protocol_wallet,
    delegation_registry_warm_contract
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
    nft_owner,
    vault_contract_def,
    protocol_wallet,
    delegation_registry_warm_contract
):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    renting_contract.start_rentals([TokenContext(token_id, Rental(), Listing(token_id, 1, 0, 0)).to_tuple()], 1, ZERO_ADDRESS, sender=nft_owner)

    with boa.reverts():
        renting_contract.withdraw([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=nft_owner)


def test_withdraw_reverts_if_invalid_context(
    renting_contract,
    nft_contract,
    nft_owner,
    vault_contract_def,
    protocol_wallet,
    delegation_registry_warm_contract
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

# @external
# def start_rentals(
#     token_contexts: DynArray[TokenContextAndListing, 32],
#     duration: uint256,
#     delegate: address,
#     signature: Signature,
#     signature_timestamp: uint256
# ):

#     signed_listings: DynArray[SignedListing, 32] = empty(DynArray[SignedListing, 32])
#     for context in token_contexts:
#         signed_listings.append(context.signed_listing)
#     assert self._are_listings_signed_by(signed_listings, signature, signature_timestamp, self.protocol_admin), "invalid signature"

#     rental_logs: DynArray[RentalLog, 32] = []
#     expiration: uint256 = block.timestamp + duration * 3600

#     for context in token_contexts:
#         vault: IVault = self._get_vault(context.token_context.token_id)
#         assert self._is_context_valid(context.token_context), "invalid context"
#         assert not self._is_rental_active(context.token_context.active_rental), "active rental"
#         assert self._is_listing_signed_by(context.signed_listing, context.token_context.nft_owner), "invalid signature"
#         assert context.signed_listing.listing.timestamp > self.listing_revocations[context.token_context.token_id], "listing revoked"

#         rental_amount: uint256 = self._compute_rental_amount(block.timestamp, expiration, context.signed_listing.listing.price)
#         self._transfer_erc20(msg.sender, self, rental_amount)

#         vault.delegate_to_wallet(delegate, expiration)

#         # store unclaimed rewards
#         self._consolidate_claims(context.token_context.token_id, context.token_context.nft_owner, context.token_context.active_rental)

#         # create rental
#         rental_id: bytes32 = self._compute_rental_id(msg.sender, context.token_context.token_id, block.timestamp, expiration)

#         new_rental: Rental = Rental({
#             id: rental_id,
#             owner: context.token_context.nft_owner,
#             renter: msg.sender,
#             delegate: delegate,
#             token_id: context.token_context.token_id,
#             start: block.timestamp,
#             min_expiration: block.timestamp + context.signed_listing.listing.min_duration * 3600,
#             expiration: expiration,
#             amount: rental_amount,
#             protocol_fee: self.protocol_fee,
#         })

#         self._store_token_state(context.token_context.token_id, context.token_context.nft_owner, new_rental)

#         rental_logs.append(RentalLog({
#             id: rental_id,
#             vault: self._tokenid_to_vault(context.token_context.token_id),
#             owner: context.token_context.nft_owner,
#             token_id: context.token_context.token_id,
#             start: block.timestamp,
#             min_expiration: new_rental.min_expiration,
#             expiration: expiration,
#             amount: rental_amount,
#             protocol_fee: new_rental.protocol_fee,
#         }))

#     log RentalStarted(msg.sender, delegate, nft_contract_addr, rental_logs)


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
    protocol_wallet
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
    signed_listing = sign_listing(listing, nft_owner_key, renting_contract.address)
    owner_sig = sign_listings([signed_listing], start_time, owner_key, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing).to_tuple()],
        duration,
        renter_delegate,
        owner_sig.to_tuple(),
        start_time,
        sender=renter
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
        renter,
        token_id,
        start_time,
        min_expiration,
        expiration,
        rental_amount,
        PROTOCOL_FEE,
    )
    assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, nft_owner, rental)


def test_cancel_listings(renting_contract, nft_contract, nft_owner, vault_contract_def):
    token_id = 1
    price = int(1e18)
    min_duration = 1
    max_duration = 2

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vaults_and_deposit([token_id], price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner)
    vault_contract = vault_contract_def.at(vault_addr)

    listing = Listing(token_id, price, min_duration, max_duration)
    assert vault_contract.state() == compute_state_hash(Rental(), listing)

    renting_contract.cancel_listings(
        [TokenContext(token_id=token_id, listing=listing).to_tuple()], ZERO_ADDRESS, sender=nft_owner
    )
    event = get_last_event(renting_contract, "ListingsCancelled")

    assert vault_contract.state() == compute_state_hash(Rental(), Listing(token_id=token_id))

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.delegate == ZERO_ADDRESS

    vault_log = VaultLog(*event.vaults[-1])
    assert vault_log.vault == vault_addr
    assert vault_log.token_id == token_id


def test_cancel_listings_and_delegate_to_wallet(
    renting_contract, nft_contract, nft_owner, vault_contract_def, delegation_registry_warm_contract
):
    token_id = 1
    price = int(1e18)
    min_duration = 1
    max_duration = 2

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    delegate = boa.env.generate_address("delegate")

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vaults_and_deposit([token_id], price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner)
    vault_contract = vault_contract_def.at(vault_addr)

    listing = Listing(token_id, price, min_duration, max_duration)
    assert vault_contract.state() == compute_state_hash(Rental(), listing)

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == ZERO_ADDRESS

    renting_contract.cancel_listings([TokenContext(token_id=token_id, listing=listing).to_tuple()], delegate, sender=nft_owner)
    event = get_last_event(renting_contract, "ListingsCancelled")

    assert vault_contract.state() == compute_state_hash(Rental(), Listing(token_id=token_id))

    assert delegation_registry_warm_contract.getHotWallet(vault_contract) == delegate
    assert delegation_registry_warm_contract.eval(f"self.exp[{vault_contract.address}]") == FOREVER

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.delegate == delegate

    vault_log = VaultLog(*event.vaults[-1])
    assert vault_log.vault == vault_addr
    assert vault_log.token_id == token_id


def test_start_rental(renting_contract, nft_contract, ape_contract, nft_owner, renter, vault_contract_def, protocol_wallet):
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
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner)
    vault_contract = vault_contract_def.at(vault_addr)

    listing = Listing(token_id, price, min_duration, max_duration)

    renting_contract.start_rentals(
        [TokenContext(token_id, Rental(), listing).to_tuple()], duration, renter_delegate, sender=renter
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
    assert event_rental.protocol_wallet == protocol_wallet

    rental = Rental(
        event_rental.id,
        nft_owner,
        renter,
        renter,
        token_id,
        start_time,
        min_expiration,
        expiration,
        rental_amount,
        PROTOCOL_FEE,
        protocol_wallet,
    )
    assert vault_contract.state() == compute_state_hash(rental, listing)


# def test_start_rentals(
#     renting_contract, nft_contract, ape_contract, nft_owner, renter, vault_contract_def, owner, protocol_wallet
# ):
#     token_id_base = 10
#     token_id_qty = 32
#     token_ids = [token_id_base + i for i in range(token_id_qty)]
#     min_duration = 0
#     max_duration = 0

#     token_id = 1
#     price = int(1e18)
#     start_time = boa.eval("block.timestamp")
#     min_expiration = boa.eval("block.timestamp")
#     duration = 10
#     expiration = start_time + duration * 3600
#     rental_amount = duration * price

#     for token_id in token_ids:
#         nft_contract.mint(nft_owner, token_id, sender=owner)
#         vault_addr = renting_contract.tokenid_to_vault(token_id)
#         nft_contract.approve(vault_addr, token_id, sender=nft_owner)
#         ape_contract.approve(vault_addr, rental_amount, sender=renter)

#     renting_contract.create_vaults_and_deposit(token_ids, price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner)

#     listings = [Listing(token_id, price, min_duration, max_duration) for token_id in token_ids]
#     token_contexts = [
#         TokenContext(token_id=token_id, listing=listing).to_tuple() for token_id, listing in zip(token_ids, listings)
#     ]
#     renting_contract.start_rentals(token_contexts, duration, renter, sender=renter)
#     event = get_last_event(renting_contract, "RentalStarted")

#     assert event.renter == renter
#     assert event.nft_contract == nft_contract.address

#     for token_id, event_rental, listing in zip(token_ids, event.rentals, listings):
#         vault_addr = renting_contract.tokenid_to_vault(token_id)
#         vault_contract = vault_contract_def.at(vault_addr)

#         event_log = RentalLog(*event_rental)
#         assert event_log.vault == vault_addr
#         assert event_log.owner == nft_owner
#         assert event_log.token_id == token_id
#         assert event_log.start == start_time
#         assert event_log.min_expiration == min_expiration
#         assert event_log.expiration == expiration
#         assert event_log.amount == rental_amount
#         assert event_log.protocol_fee == PROTOCOL_FEE
#         assert event_log.protocol_wallet == protocol_wallet

#         rental = Rental(
#             event_log.id,
#             nft_owner,
#             renter,
#             renter,
#             token_id,
#             start_time,
#             min_expiration,
#             expiration,
#             rental_amount,
#             PROTOCOL_FEE,
#             protocol_wallet,
#         )
#         assert vault_contract.state() == compute_state_hash(rental, listing)


def test_start_rental_fee_disabled(
    renting_contract_no_fee, nft_contract, ape_contract, nft_owner, renter, vault_contract_def, protocol_wallet
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    min_expiration = start_time
    duration = 10
    expiration = start_time + duration * 3600
    rental_amount = duration * price

    vault_addr = renting_contract_no_fee.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract_no_fee.create_vaults_and_deposit(
        [token_id], price, min_duration, max_duration, nft_owner, sender=nft_owner
    )
    vault_contract = vault_contract_def.at(vault_addr)

    listing = Listing(token_id, price, min_duration, max_duration)

    renting_contract_no_fee.start_rentals(
        [TokenContext(token_id, Rental(), listing).to_tuple()], duration, renter, sender=renter
    )
    event = get_last_event(renting_contract_no_fee, "RentalStarted")

    assert event.renter == renter
    assert event.nft_contract == nft_contract.address

    event_rental = RentalLog(*event.rentals[0])
    assert event_rental.vault == vault_addr
    assert event_rental.owner == nft_owner
    assert event_rental.token_id == token_id
    assert event_rental.start == start_time
    assert event_rental.min_expiration == min_expiration
    assert event_rental.expiration == expiration
    assert event_rental.amount == rental_amount
    assert event_rental.protocol_fee == 0
    assert event_rental.protocol_wallet == protocol_wallet

    rental = Rental(
        event_rental.id,
        nft_owner,
        renter,
        renter,
        token_id,
        start_time,
        min_expiration,
        expiration,
        rental_amount,
        0,
        protocol_wallet,
    )
    assert vault_contract.state() == compute_state_hash(rental, listing)


def test_start_rentals_fee_disabled(
    renting_contract_no_fee, nft_contract, ape_contract, nft_owner, renter, vault_contract_def, owner, protocol_wallet
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

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract_no_fee.tokenid_to_vault(token_id)
        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract_no_fee.create_vaults_and_deposit(
        token_ids, price, min_duration, max_duration, nft_owner, sender=nft_owner
    )

    listings = [Listing(token_id, price, min_duration, max_duration) for token_id in token_ids]
    token_contexts = [
        TokenContext(token_id=token_id, listing=listing).to_tuple() for token_id, listing in zip(token_ids, listings)
    ]
    renting_contract_no_fee.start_rentals(token_contexts, duration, renter, sender=renter)
    event = get_last_event(renting_contract_no_fee, "RentalStarted")

    assert event.renter == renter
    assert event.nft_contract == nft_contract.address

    for token_id, event_rental, listing in zip(token_ids, event.rentals, listings):
        vault_addr = renting_contract_no_fee.tokenid_to_vault(token_id)
        vault_contract = vault_contract_def.at(vault_addr)

        event_log = RentalLog(*event_rental)
        assert event_log.vault == vault_addr
        assert event_log.owner == nft_owner
        assert event_log.token_id == token_id
        assert event_log.start == start_time
        assert event_log.min_expiration == min_expiration
        assert event_log.expiration == expiration
        assert event_log.amount == rental_amount
        assert event_log.protocol_fee == 0
        assert event_log.protocol_wallet == protocol_wallet

        rental = Rental(
            event_log.id,
            nft_owner,
            renter,
            renter,
            token_id,
            start_time,
            min_expiration,
            expiration,
            rental_amount,
            0,
            protocol_wallet,
        )
        assert vault_contract.state() == compute_state_hash(rental, listing)


def test_close_rental(renting_contract, nft_contract, ape_contract, nft_owner, renter, protocol_wallet):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    duration = 6
    expiration = start_time + duration * 3600
    rental_amount = duration * price

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration)

    renting_contract.start_rentals(
        [TokenContext(token_id=token_id, listing=listing).to_tuple()], duration, renter, sender=renter
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")

    time_passed = 3 * 3600
    boa.env.time_travel(seconds=time_passed)
    real_expiration = int(boa.eval("block.timestamp"))
    real_rental_amount = int(Decimal(rental_amount) / Decimal(2))

    active_rental = Rental(
        RentalLog(*rental_started_event.rentals[0]).id,
        nft_owner,
        renter,
        renter,
        token_id,
        start_time,
        min_expiration,
        expiration,
        rental_amount,
        PROTOCOL_FEE,
        protocol_wallet,
    )

    renting_contract.close_rentals([TokenContext(token_id, active_rental, listing).to_tuple()], sender=renter)
    rental_closed_event = get_last_event(renting_contract, "RentalClosed")

    assert rental_closed_event.renter == renter
    assert rental_closed_event.nft_contract == nft_contract.address

    event_rental = RentalLog(*rental_closed_event.rentals[0])
    assert event_rental.vault == vault_addr
    assert event_rental.owner == nft_owner
    assert event_rental.token_id == token_id
    assert event_rental.start == start_time
    assert event_rental.min_expiration == min_expiration
    assert event_rental.expiration == real_expiration
    assert event_rental.amount == real_rental_amount
    assert event_rental.protocol_fee == PROTOCOL_FEE
    assert event_rental.protocol_wallet == protocol_wallet

    assert ape_contract.balanceOf(nft_owner) == 0
    assert ape_contract.balanceOf(protocol_wallet) == real_rental_amount * PROTOCOL_FEE // 10000


def test_close_rental_no_fee(renting_contract_no_fee, nft_contract, ape_contract, nft_owner, renter, protocol_wallet):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    duration = 6
    expiration = start_time + duration * 3600
    rental_amount = duration * price

    vault_addr = renting_contract_no_fee.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract_no_fee.create_vaults_and_deposit(
        [token_id], price, min_duration, max_duration, nft_owner, sender=nft_owner
    )

    listing = Listing(token_id, price, min_duration, max_duration)

    renting_contract_no_fee.start_rentals(
        [TokenContext(token_id=token_id, listing=listing).to_tuple()], duration, renter, sender=renter
    )
    rental_started_event = get_last_event(renting_contract_no_fee, "RentalStarted")

    time_passed = 3 * 3600
    boa.env.time_travel(seconds=time_passed)
    real_expiration = int(boa.eval("block.timestamp"))
    real_rental_amount = int(Decimal(rental_amount) / Decimal(2))

    active_rental = Rental(
        RentalLog(*rental_started_event.rentals[0]).id,
        nft_owner,
        renter,
        renter,
        token_id,
        start_time,
        min_expiration,
        expiration,
        rental_amount,
        0,
        protocol_wallet,
    )

    renting_contract_no_fee.close_rentals([TokenContext(token_id, active_rental, listing).to_tuple()], sender=renter)
    rental_closed_event = get_last_event(renting_contract_no_fee, "RentalClosed")

    assert rental_closed_event.renter == renter
    assert rental_closed_event.nft_contract == nft_contract.address

    event_rental = RentalLog(*rental_closed_event.rentals[0])
    assert event_rental.vault == vault_addr
    assert event_rental.owner == nft_owner
    assert event_rental.token_id == token_id
    assert event_rental.start == start_time
    assert event_rental.min_expiration == min_expiration
    assert event_rental.expiration == real_expiration
    assert event_rental.amount == real_rental_amount
    assert event_rental.protocol_fee == 0
    assert event_rental.protocol_wallet == protocol_wallet

    assert ape_contract.balanceOf(nft_owner) == 0
    assert ape_contract.balanceOf(protocol_wallet) == 0


def test_close_rental_before_min_duration(renting_contract, nft_contract, ape_contract, nft_owner, renter, protocol_wallet):
    token_id = 1
    price = int(1e18)
    start_time = boa.eval("block.timestamp")
    min_duration = 2
    max_duration = 0
    min_expiration = start_time + min_duration * 3600
    expiration = min_expiration
    rental_amount = (expiration - start_time) * price // 3600

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration)

    renting_contract.start_rentals(
        [TokenContext(token_id=token_id, listing=listing).to_tuple()], min_duration, renter, sender=renter
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")

    time_passed = 3600
    boa.env.time_travel(seconds=time_passed)
    real_expiration = int(boa.eval("block.timestamp"))

    active_rental = Rental(
        RentalLog(*rental_started_event.rentals[0]).id,
        nft_owner,
        renter,
        renter,
        token_id,
        start_time,
        min_expiration,
        expiration,
        rental_amount,
        PROTOCOL_FEE,
        protocol_wallet,
    )

    renting_contract.close_rentals([TokenContext(token_id, active_rental, listing).to_tuple()], sender=renter)
    event = get_last_event(renting_contract, "RentalClosed")

    assert event.renter == renter
    assert event.nft_contract == nft_contract.address

    event_rental = RentalLog(*event.rentals[0])
    assert event_rental.vault == vault_addr
    assert event_rental.owner == nft_owner
    assert event_rental.token_id == token_id
    assert event_rental.start == start_time
    assert event_rental.min_expiration == min_expiration
    assert event_rental.expiration == real_expiration
    assert event_rental.amount == rental_amount
    assert event_rental.protocol_fee == PROTOCOL_FEE
    assert event_rental.protocol_wallet == protocol_wallet


def test_close_rental_with_changed_list_price(
    renting_contract, nft_contract, ape_contract, nft_owner, renter, protocol_wallet
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    changed_price = 3 * price
    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    duration = 10
    expiration = start_time + duration * 3600
    rental_amount = (expiration - start_time) * price // 3600

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner)

    listing = Listing(token_id, price, min_duration, max_duration)

    token_context = TokenContext(token_id=token_id, listing=listing).to_tuple()
    renting_contract.start_rentals([token_context], duration, renter, sender=renter)
    rental_started_event = get_last_event(renting_contract, "RentalStarted")

    active_rental = Rental(
        RentalLog(*rental_started_event.rentals[0]).id,
        nft_owner,
        renter,
        renter,
        token_id,
        start_time,
        min_expiration,
        expiration,
        rental_amount,
        PROTOCOL_FEE,
        protocol_wallet,
    )

    token_context = TokenContext(token_id, active_rental, listing).to_tuple()
    renting_contract.set_listings([token_context], changed_price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner)

    time_passed = 3600
    boa.env.time_travel(seconds=time_passed)
    real_expiration = int(boa.eval("block.timestamp"))
    real_rental_amount = (real_expiration - start_time) * price // 3600

    new_listing = Listing(token_id, changed_price, min_duration, max_duration)
    token_context = TokenContext(token_id, active_rental, new_listing)

    renting_contract.close_rentals([token_context.to_tuple()], sender=renter)
    rental_close_event = get_last_event(renting_contract, "RentalClosed")

    assert rental_close_event.renter == renter
    assert rental_close_event.nft_contract == nft_contract.address

    event_rental = RentalLog(*rental_close_event.rentals[0])
    assert event_rental.vault == vault_addr
    assert event_rental.owner == nft_owner
    assert event_rental.token_id == token_id
    assert event_rental.start == start_time
    assert event_rental.min_expiration == start_time
    assert event_rental.expiration == real_expiration
    assert event_rental.amount == real_rental_amount
    assert event_rental.protocol_fee == PROTOCOL_FEE
    assert event_rental.protocol_wallet == protocol_wallet


def test_close_rentals(
    renting_contract, nft_contract, ape_contract, nft_owner, renter, vault_contract_def, owner, protocol_wallet
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    duration = 6
    expiration = start_time + duration * 3600
    rental_amount = duration * price

    vaults = {}

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)

        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        ape_contract.approve(vault_addr, rental_amount, sender=renter)

        vaults[token_id] = vault_addr

    renting_contract.create_vaults_and_deposit(token_ids, price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner)

    listings = [Listing(token_id, price, min_duration, max_duration) for token_id in token_ids]
    token_contexts = [
        TokenContext(token_id=token_id, listing=listing).to_tuple() for token_id, listing in zip(token_ids, listings)
    ]
    renting_contract.start_rentals(token_contexts, duration, renter, sender=renter)
    rentals_started_event = get_last_event(renting_contract, "RentalStarted")

    active_rentals = [
        Rental(
            RentalLog(*event_log).id,
            nft_owner,
            renter,
            renter,
            token_id,
            start_time,
            min_expiration,
            expiration,
            rental_amount,
            PROTOCOL_FEE,
            protocol_wallet,
        )
        for token_id, event_log in zip(token_ids, rentals_started_event.rentals)
    ]

    time_passed = 3 * 3600
    boa.env.time_travel(seconds=time_passed)
    real_expiration = int(boa.eval("block.timestamp"))
    real_rental_amount = int(Decimal(rental_amount) / Decimal(2))

    token_contexts_close = [
        TokenContext(token_id, active_rental, listing).to_tuple()
        for token_id, active_rental, listing in zip(token_ids, active_rentals, listings)
    ]
    renting_contract.close_rentals(token_contexts_close, sender=renter)
    rentals_close_event = get_last_event(renting_contract, "RentalClosed")

    assert rentals_close_event.renter == renter
    assert rentals_close_event.nft_contract == nft_contract.address

    for token_id, event_rental, listing in zip(token_ids, rentals_close_event.rentals, listings):
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        vault_contract = vault_contract_def.at(vault_addr)

        event_log = RentalLog(*event_rental)
        assert event_log.vault == vault_addr
        assert event_log.owner == nft_owner
        assert event_log.token_id == token_id
        assert event_log.start == start_time
        assert event_log.min_expiration == min_expiration
        assert event_log.expiration == real_expiration
        assert event_log.amount == real_rental_amount
        assert event_log.protocol_fee == PROTOCOL_FEE
        assert event_log.protocol_wallet == protocol_wallet

        assert vault_contract.state() == compute_state_hash(Rental(), listing)


def test_claim(renting_contract, nft_contract, ape_contract, nft_owner, renter, vault_contract_def, protocol_wallet):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    duration = 6
    expiration = start_time + duration * 3600
    rental_amount = duration * price
    protocol_fee_amount = rental_amount * PROTOCOL_FEE // 10000

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract.create_vaults_and_deposit([token_id], price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner)
    vault_contract = vault_contract_def.at(vault_addr)

    listing = Listing(token_id, price, min_duration, max_duration)

    renting_contract.start_rentals(
        [TokenContext(token_id=token_id, listing=listing).to_tuple()], duration, renter, sender=renter
    )
    rental_start_event = get_last_event(renting_contract, "RentalStarted")

    time_passed = duration * 3600 + 1
    boa.env.time_travel(seconds=time_passed)

    active_rental = Rental(
        RentalLog(*rental_start_event.rentals[0]).id,
        nft_owner,
        renter,
        renter,
        token_id,
        start_time,
        min_expiration,
        expiration,
        rental_amount,
        PROTOCOL_FEE,
        protocol_wallet,
    )

    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == rental_amount - protocol_fee_amount
    assert vault_contract.unclaimed_rewards() == 0

    renting_contract.claim([TokenContext(token_id, active_rental, listing).to_tuple()], sender=nft_owner)
    event = get_last_event(renting_contract, "RewardsClaimed")

    active_rental.amount = 0
    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == 0
    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.unclaimed_protocol_fee() == 0

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address

    event_reward = RewardLog(*event.rewards[0])
    assert event_reward.vault == vault_addr
    assert event_reward.token_id == token_id
    assert event_reward.amount == rental_amount - protocol_fee_amount
    assert event_reward.protocol_fee_amount == protocol_fee_amount
    assert event_reward.active_rental_amount == 0

    assert ape_contract.balanceOf(nft_owner) == rental_amount - protocol_fee_amount
    assert ape_contract.balanceOf(protocol_wallet) == protocol_fee_amount


def test_claim_multiple(
    renting_contract, nft_contract, ape_contract, nft_owner, renter, vault_contract_def, owner, protocol_wallet
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]

    price = int(1e18)
    min_duration = 0
    max_duration = 0
    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    duration = 6
    expiration = start_time + duration * 3600
    rental_amount = duration * price
    protocol_fee_amount = rental_amount * PROTOCOL_FEE // 10000

    vaults = {}

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)

        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        ape_contract.approve(vault_addr, rental_amount, sender=renter)

        vaults[token_id] = vault_addr

    renting_contract.create_vaults_and_deposit(token_ids, price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner)

    listings = [Listing(token_id, price, min_duration, max_duration) for token_id in token_ids]
    token_contexts_start = [
        TokenContext(token_id=token_id, listing=listing).to_tuple() for token_id, listing in zip(token_ids, listings)
    ]

    renting_contract.start_rentals(token_contexts_start, duration, renter, sender=renter)
    rental_start_event = get_last_event(renting_contract, "RentalStarted")

    time_passed = duration * 3600 + 1
    boa.env.time_travel(seconds=time_passed)

    active_rentals = [
        Rental(
            RentalLog(*event_log).id,
            nft_owner,
            renter,
            renter,
            token_id,
            start_time,
            min_expiration,
            expiration,
            rental_amount,
            PROTOCOL_FEE,
            protocol_wallet,
        )
        for token_id, event_log in zip(token_ids, rental_start_event.rentals)
    ]
    token_contexts_claim = [
        TokenContext(token_id, active_rental, listing).to_tuple()
        for token_id, active_rental, listing in zip(token_ids, active_rentals, listings)
    ]

    renting_contract.claim(token_contexts_claim, sender=nft_owner)
    rewards_claimed_event = get_last_event(renting_contract, "RewardsClaimed")

    assert rewards_claimed_event.owner == nft_owner
    assert rewards_claimed_event.nft_contract == nft_contract.address

    for token_id, active_rental, event_reward in zip(token_ids, active_rentals, rewards_claimed_event.rewards):
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        vault_contract = vault_contract_def.at(vault_addr)

        active_rental.amount = 0
        assert vault_contract.claimable_rewards(active_rental.to_tuple()) == 0
        assert vault_contract.unclaimed_rewards() == 0
        assert vault_contract.unclaimed_protocol_fee() == 0

        reward_log = RewardLog(*event_reward)
        assert reward_log.vault == vault_addr
        assert reward_log.token_id == token_id
        assert reward_log.amount == rental_amount - protocol_fee_amount
        assert reward_log.protocol_fee_amount == protocol_fee_amount
        assert reward_log.active_rental_amount == 0

    assert ape_contract.balanceOf(nft_owner) == (rental_amount - protocol_fee_amount) * token_id_qty
    assert ape_contract.balanceOf(protocol_wallet) == protocol_fee_amount * token_id_qty


def test_claim_no_fee(
    renting_contract_no_fee, nft_contract, ape_contract, nft_owner, renter, vault_contract_def, protocol_wallet
):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0

    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    duration = 6
    expiration = start_time + duration * 3600
    rental_amount = duration * price

    vault_addr = renting_contract_no_fee.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract_no_fee.create_vaults_and_deposit(
        [token_id], price, min_duration, max_duration, nft_owner, sender=nft_owner
    )
    vault_contract = vault_contract_def.at(vault_addr)

    listing = Listing(token_id, price, min_duration, max_duration)

    renting_contract_no_fee.start_rentals(
        [TokenContext(token_id=token_id, listing=listing).to_tuple()], duration, renter, sender=renter
    )
    rental_start_event = get_last_event(renting_contract_no_fee, "RentalStarted")

    time_passed = duration * 3600 + 1
    boa.env.time_travel(seconds=time_passed)

    active_rental = Rental(
        RentalLog(*rental_start_event.rentals[0]).id,
        nft_owner,
        renter,
        renter,
        token_id,
        start_time,
        min_expiration,
        expiration,
        rental_amount,
        0,
        protocol_wallet,
    )

    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == rental_amount
    assert vault_contract.unclaimed_rewards() == 0

    renting_contract_no_fee.claim([TokenContext(token_id, active_rental, listing).to_tuple()], sender=nft_owner)
    event = get_last_event(renting_contract_no_fee, "RewardsClaimed")

    active_rental.amount = 0
    assert vault_contract.claimable_rewards(active_rental.to_tuple()) == 0
    assert vault_contract.unclaimed_rewards() == 0
    assert vault_contract.unclaimed_protocol_fee() == 0

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address

    event_reward = RewardLog(*event.rewards[0])
    assert event_reward.vault == vault_addr
    assert event_reward.token_id == token_id
    assert event_reward.amount == rental_amount
    assert event_reward.protocol_fee_amount == 0
    assert event_reward.active_rental_amount == 0

    assert ape_contract.balanceOf(nft_owner) == rental_amount
    assert ape_contract.balanceOf(protocol_wallet) == 0


def test_claim_multiple_no_fee(
    renting_contract_no_fee, nft_contract, ape_contract, nft_owner, renter, vault_contract_def, owner, protocol_wallet
):
    token_id_base = 10
    token_id_qty = 32
    token_ids = [token_id_base + i for i in range(token_id_qty)]

    price = int(1e18)
    min_duration = 0
    max_duration = 0
    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    duration = 6
    expiration = start_time + duration * 3600
    rental_amount = duration * price

    vaults = {}

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract_no_fee.tokenid_to_vault(token_id)

        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        ape_contract.approve(vault_addr, rental_amount, sender=renter)

        vaults[token_id] = vault_addr

    renting_contract_no_fee.create_vaults_and_deposit(
        token_ids, price, min_duration, max_duration, nft_owner, sender=nft_owner
    )

    listings = [Listing(token_id, price, min_duration, max_duration) for token_id in token_ids]
    token_contexts_start = [
        TokenContext(token_id=token_id, listing=listing).to_tuple() for token_id, listing in zip(token_ids, listings)
    ]

    renting_contract_no_fee.start_rentals(token_contexts_start, duration, renter, sender=renter)
    rental_start_event = get_last_event(renting_contract_no_fee, "RentalStarted")

    time_passed = duration * 3600 + 1
    boa.env.time_travel(seconds=time_passed)

    active_rentals = [
        Rental(
            RentalLog(*event_log).id,
            nft_owner,
            renter,
            renter,
            token_id,
            start_time,
            min_expiration,
            expiration,
            rental_amount,
            0,
            protocol_wallet,
        )
        for token_id, event_log in zip(token_ids, rental_start_event.rentals)
    ]
    token_contexts_claim = [
        TokenContext(token_id, active_rental, listing).to_tuple()
        for token_id, active_rental, listing in zip(token_ids, active_rentals, listings)
    ]

    renting_contract_no_fee.claim(token_contexts_claim, sender=nft_owner)
    rewards_claimed_event = get_last_event(renting_contract_no_fee, "RewardsClaimed")

    assert rewards_claimed_event.owner == nft_owner
    assert rewards_claimed_event.nft_contract == nft_contract.address

    for token_id, active_rental, event_reward in zip(token_ids, active_rentals, rewards_claimed_event.rewards):
        vault_addr = renting_contract_no_fee.tokenid_to_vault(token_id)
        vault_contract = vault_contract_def.at(vault_addr)

        active_rental.amount = 0
        assert vault_contract.claimable_rewards(active_rental.to_tuple()) == 0
        assert vault_contract.unclaimed_rewards() == 0
        assert vault_contract.unclaimed_protocol_fee() == 0

        reward_log = RewardLog(*event_reward)
        assert reward_log.vault == vault_addr
        assert reward_log.token_id == token_id
        assert reward_log.amount == rental_amount
        assert reward_log.protocol_fee_amount == 0
        assert reward_log.active_rental_amount == 0

    assert ape_contract.balanceOf(nft_owner) == rental_amount * token_id_qty
    assert ape_contract.balanceOf(protocol_wallet) == 0


# def test_withdraw(renting_contract, nft_contract, ape_contract, nft_owner, renter, protocol_wallet):
#     token_id = 1
#     price = int(1e18)
#     min_duration = 0
#     max_duration = 0
#     start_time = boa.eval("block.timestamp")
#     min_expiration = boa.eval("block.timestamp")
#     duration = 6
#     expiration = start_time + duration * 3600
#     rental_amount = int(Decimal(expiration - start_time) * Decimal(price) / Decimal(3600))
#     protocol_fee_amount = rental_amount * PROTOCOL_FEE // 10000

#     vault_addr = renting_contract.tokenid_to_vault(token_id)

#     nft_contract.approve(vault_addr, token_id, sender=nft_owner)
#     ape_contract.approve(vault_addr, rental_amount, sender=renter)

#     renting_contract.create_vaults_and_deposit([token_id], price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner)

#     listing = Listing(token_id, price, min_duration, max_duration)

#     renting_contract.start_rentals(
#         [TokenContext(token_id=token_id, listing=listing).to_tuple()], duration, renter, sender=renter
#     )
#     start_rental_event = get_last_event(renting_contract, "RentalStarted")

#     time_passed = duration * 3600 + 1
#     boa.env.time_travel(seconds=time_passed)

#     active_rental = Rental(
#         RentalLog(*start_rental_event.rentals[0]).id,
#         nft_owner,
#         renter,
#         renter,
#         token_id,
#         start_time,
#         min_expiration,
#         expiration,
#         rental_amount,
#         PROTOCOL_FEE,
#         protocol_wallet,
#     )

#     renting_contract.withdraw([TokenContext(token_id, active_rental, listing).to_tuple()], sender=nft_owner)
#     event = get_last_event(renting_contract, "NftsWithdrawn")

#     assert renting_contract.active_vaults(token_id) == ZERO_ADDRESS

#     assert event.owner == nft_owner
#     assert event.nft_contract == nft_contract.address
#     assert event.total_rewards == rental_amount - protocol_fee_amount

#     withdrawal_log = WithdrawalLog(*event.withdrawals[-1])
#     assert withdrawal_log.vault == vault_addr
#     assert withdrawal_log.token_id == token_id
#     assert withdrawal_log.rewards == rental_amount - protocol_fee_amount
#     assert withdrawal_log.protocol_fee_amount == protocol_fee_amount

#     assert ape_contract.balanceOf(nft_owner) == rental_amount - protocol_fee_amount
#     assert ape_contract.balanceOf(protocol_wallet) == protocol_fee_amount


def test_withdraw_no_fee(renting_contract_no_fee, nft_contract, ape_contract, nft_owner, renter, protocol_wallet):
    token_id = 1
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    start_time = boa.eval("block.timestamp")
    min_expiration = boa.eval("block.timestamp")
    duration = 6
    expiration = start_time + duration * 3600
    rental_amount = int(Decimal(expiration - start_time) * Decimal(price) / Decimal(3600))

    vault_addr = renting_contract_no_fee.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    ape_contract.approve(vault_addr, rental_amount, sender=renter)

    renting_contract_no_fee.create_vaults_and_deposit(
        [token_id], price, min_duration, max_duration, nft_owner, sender=nft_owner
    )

    listing = Listing(token_id, price, min_duration, max_duration)

    renting_contract_no_fee.start_rentals(
        [TokenContext(token_id=token_id, listing=listing).to_tuple()], duration, renter, sender=renter
    )
    start_rental_event = get_last_event(renting_contract_no_fee, "RentalStarted")

    time_passed = duration * 3600 + 1
    boa.env.time_travel(seconds=time_passed)

    active_rental = Rental(
        RentalLog(*start_rental_event.rentals[0]).id,
        nft_owner,
        renter,
        renter,
        token_id,
        start_time,
        min_expiration,
        expiration,
        rental_amount,
        0,
        protocol_wallet,
    )

    renting_contract_no_fee.withdraw([TokenContext(token_id, active_rental, listing).to_tuple()], sender=nft_owner)
    event = get_last_event(renting_contract_no_fee, "NftsWithdrawn")

    assert renting_contract_no_fee.active_vaults(token_id) == ZERO_ADDRESS

    assert event.owner == nft_owner
    assert event.nft_contract == nft_contract.address
    assert event.total_rewards == rental_amount

    withdrawal_log = WithdrawalLog(*event.withdrawals[-1])
    assert withdrawal_log.vault == vault_addr
    assert withdrawal_log.token_id == token_id
    assert withdrawal_log.rewards == rental_amount
    assert withdrawal_log.protocol_fee_amount == 0

    assert ape_contract.balanceOf(nft_owner) == rental_amount
    assert ape_contract.balanceOf(protocol_wallet) == 0


def test_deposit_no_vaults(renting_contract, nft_owner):
    with boa.reverts("vault is not available"):
        renting_contract.deposit([1], 1, 0, 0, ZERO_ADDRESS, sender=nft_owner)


def test_deposit_already_deposited(renting_contract, nft_contract, nft_owner, renter):
    token_id = 1
    price = 1

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.create_vaults_and_deposit([token_id], price, 0, 0, ZERO_ADDRESS, sender=nft_owner)

    with boa.reverts("vault is not available"):
        renting_contract.deposit([token_id], price, 0, 0, ZERO_ADDRESS, sender=nft_owner)


# def test_deposit(renting_contract, nft_contract, ape_contract, nft_owner, renter, protocol_wallet):
#     token_id = 1
#     price = int(1e18)
#     min_duration = 0
#     max_duration = 0
#     start_time = boa.eval("block.timestamp")
#     min_expiration = boa.eval("block.timestamp")
#     duration = 6
#     expiration = start_time + duration * 3600
#     rental_amount = duration * price

#     vault_addr = renting_contract.tokenid_to_vault(token_id)

#     nft_contract.approve(vault_addr, token_id, sender=nft_owner)
#     ape_contract.approve(vault_addr, rental_amount, sender=renter)

#     renting_contract.create_vaults_and_deposit([token_id], price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner)

#     assert nft_contract.ownerOf(token_id) == vault_addr

#     listing = Listing(token_id, price, min_duration, max_duration)

#     renting_contract.start_rentals(
#         [TokenContext(token_id=token_id, listing=listing).to_tuple()], duration, renter, sender=renter
#     )
#     start_rental_event = get_last_event(renting_contract, "RentalStarted")

#     time_passed = duration * 3600 + 1
#     boa.env.time_travel(seconds=time_passed)

#     active_rental = Rental(
#         RentalLog(*start_rental_event.rentals[0]).id,
#         nft_owner,
#         renter,
#         renter,
#         token_id,
#         start_time,
#         min_expiration,
#         expiration,
#         rental_amount,
#         PROTOCOL_FEE,
#         protocol_wallet,
#     )

#     renting_contract.withdraw([TokenContext(token_id, active_rental, listing).to_tuple()], sender=nft_owner)

#     assert renting_contract.active_vaults(token_id) == ZERO_ADDRESS
#     assert renting_contract.tokenid_to_vault(token_id) == vault_addr
#     assert renting_contract.is_vault_available(token_id)
#     assert nft_contract.ownerOf(token_id) == nft_owner

#     nft_contract.approve(vault_addr, token_id, sender=nft_owner)
#     renting_contract.deposit([token_id], price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner)
#     event = get_last_event(renting_contract, "NftsDeposited")

#     assert renting_contract.active_vaults(token_id) == vault_addr
#     assert not renting_contract.is_vault_available(token_id)
#     assert nft_contract.ownerOf(token_id) == vault_addr

#     assert event.owner == nft_owner
#     assert event.nft_contract == nft_contract.address
#     assert event.min_duration == min_duration
#     assert event.max_duration == max_duration
#     assert event.price == price
#     assert event.delegate == ZERO_ADDRESS

#     vault_log = VaultLog(*event.vaults[-1])
#     assert vault_log.vault == vault_addr
#     assert vault_log.token_id == token_id


def test_delegate_to_wallet(
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
    price = int(1e18)
    min_duration = 0
    max_duration = 0
    duration = 6
    rental_amount = duration * price

    vaults = {}
    delegate = boa.env.generate_address("delegate")

    for token_id in token_ids:
        nft_contract.mint(nft_owner, token_id, sender=owner)
        vault_addr = renting_contract.tokenid_to_vault(token_id)

        nft_contract.approve(vault_addr, token_id, sender=nft_owner)
        ape_contract.approve(vault_addr, rental_amount, sender=renter)

        vaults[token_id] = vault_addr

    renting_contract.create_vaults_and_deposit(token_ids, price, min_duration, max_duration, ZERO_ADDRESS, sender=nft_owner)

    listings = [Listing(token_id, price, min_duration, max_duration) for token_id in token_ids]
    token_contexts = [
        TokenContext(token_id=token_id, listing=listing).to_tuple() for token_id, listing in zip(token_ids, listings)
    ]
    renting_contract.delegate_to_wallet(token_contexts, delegate, sender=nft_owner)
    event = get_last_event(renting_contract, "DelegatedToWallet")

    assert event.owner == nft_owner
    assert event.delegate == delegate
    assert event.nft_contract == nft_contract.address
    assert len(token_ids) == len(event.vaults)

    for token_id, vault_log in zip(token_ids, event.vaults):
        vault_addr = renting_contract.tokenid_to_vault(token_id)
        assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate
        assert VaultLog(*vault_log).token_id == token_id


def test_change_protocol_fee_wrong_caller(
    renting_contract,
    renter,
):
    with boa.reverts("not protocol admin"):
        renting_contract.set_protocol_fee(0, sender=renter)


def test_change_protocol_fee_higher_than_max(
    renting_contract,
    protocol_wallet,
):
    with boa.reverts("protocol fee > max fee"):
        renting_contract.set_protocol_fee(PROTOCOL_FEE * 2, sender=protocol_wallet)


def test_change_protocol_fee_same_value(
    renting_contract,
    protocol_wallet,
):
    with boa.reverts("protocol fee is the same"):
        renting_contract.set_protocol_fee(PROTOCOL_FEE, sender=protocol_wallet)


def test_change_protocol_fee(
    renting_contract,
    protocol_wallet,
):
    renting_contract.set_protocol_fee(0, sender=protocol_wallet)
    event = get_last_event(renting_contract, "ProtocolFeeSet")

    assert renting_contract.protocol_fee() == 0

    assert event.old_fee == PROTOCOL_FEE
    assert event.new_fee == 0
    assert event.fee_wallet == protocol_wallet


def test_change_protocol_wallet_wrong_caller(
    renting_contract,
    renter,
):
    with boa.reverts("not protocol admin"):
        renting_contract.change_protocol_wallet(renter, sender=renter)


def test_change_protocol_wallet_zero_address(
    renting_contract,
    protocol_wallet,
):
    with boa.reverts("wallet is the zero address"):
        renting_contract.change_protocol_wallet(ZERO_ADDRESS, sender=protocol_wallet)


def test_change_protocol_wallet(
    renting_contract,
    protocol_wallet,
    nft_owner,
):
    renting_contract.change_protocol_wallet(nft_owner, sender=protocol_wallet)
    event = get_last_event(renting_contract, "ProtocolWalletChanged")

    assert renting_contract.protocol_wallet() == nft_owner

    assert event.old_wallet == protocol_wallet
    assert event.new_wallet == nft_owner


def test_propose_admin_wrong_caller(
    renting_contract,
    renter,
):
    with boa.reverts("not the admin"):
        renting_contract.propose_admin(ZERO_ADDRESS, sender=renter)


def test_propose_admin_zero_address(renting_contract, protocol_wallet):
    with boa.reverts("_address is the zero address"):
        renting_contract.propose_admin(ZERO_ADDRESS, sender=protocol_wallet)


def test_propose_admin_same_address_as_admin(
    renting_contract,
    protocol_wallet,
):
    with boa.reverts("proposed admin addr is the admin"):
        renting_contract.propose_admin(protocol_wallet, sender=protocol_wallet)


def test_propose_admin(
    renting_contract,
    protocol_wallet,
    nft_owner,
):
    renting_contract.propose_admin(nft_owner, sender=protocol_wallet)
    event = get_last_event(renting_contract, "AdminProposed")

    assert renting_contract.proposed_admin() == nft_owner

    assert event.admin == protocol_wallet
    assert event.proposed_admin == nft_owner


def test_propose_admin_same_address_as_proposed(
    renting_contract,
    protocol_wallet,
    nft_owner,
):
    renting_contract.propose_admin(nft_owner, sender=protocol_wallet)

    with boa.reverts("proposed admin addr is the same"):
        renting_contract.propose_admin(nft_owner, sender=protocol_wallet)


def test_claim_ownership_wrong_caller(
    renting_contract,
    protocol_wallet,
    nft_owner,
):
    renting_contract.propose_admin(nft_owner, sender=protocol_wallet)

    with boa.reverts("not the proposed"):
        renting_contract.claim_ownership(sender=protocol_wallet)


def test_claim_ownership(
    renting_contract,
    protocol_wallet,
    nft_owner,
):
    renting_contract.propose_admin(nft_owner, sender=protocol_wallet)

    renting_contract.claim_ownership(sender=nft_owner)
    event = get_last_event(renting_contract, "OwnershipTransferred")

    assert renting_contract.proposed_admin() == ZERO_ADDRESS
    assert renting_contract.protocol_admin() == nft_owner

    assert event.old_admin == protocol_wallet
    assert event.new_admin == nft_owner
