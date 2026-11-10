"""
End to end tests of the vault whitelist extension on a mainnet fork.

The fork block is after Koda, Mara and Otherdeed Expanded moved to the LimitBreak transfer validator (whitelist ruleset,
list 13), which blocks every transfer performed by Zharta vaults. Registering the extension in the list requires the
list owner, which is impersonated. The extension only enables withdrawals: deposits must remain blocked.
"""

import os

import boa
import pytest
from boa.environment import Env

from ..conftest_base import ZERO_ADDRESS, ZERO_BYTES32, deploy_minimal_proxy, minimal_proxy_runtime
from .conftest import SNAPSHOT, abi_factory, emulate_eip7702, is_eoa, reverts_with, v2_context, v3_context
from .constants import (
    BLOCK,
    LB_ERRORS,
    LIST_ID,
    LIST_OWNER,
    LIST_TYPE_WHITELIST_EXTENSION,
    POUCH_WHITELIST_EXTENSION,
    RULESET_WHITELIST,
    VALIDATOR,
)
from .snapshot import state_hash_v2, state_hash_v3

GATED_COLLECTIONS = ["koda", "mara", "otherdeed"]
LB_ERROR_SELECTORS = {name: selector for selector, name in LB_ERRORS.items()}
NO_ERROR = b"\x00" * 4


def entry_id(entry: dict) -> str:
    return f"{entry['collection']}-{entry['token_id']}"


def is_rental_active(entry: dict) -> bool:
    return entry["active_rental"]["expiration"] > boa.env.timestamp


def first_entry(version: str, collection_name: str | None = None) -> dict:
    # first stuck token of a gated collection (or of the given collection) without an active rental
    return next(
        e
        for e in SNAPSHOT[version]
        if (e["collection"] == collection_name if collection_name else e["collection"] in GATED_COLLECTIONS)
        and not is_rental_active(e)
    )


@pytest.fixture(scope="session")
def chimpers():
    pouch = abi_factory("tests/limitbreak/interfaces/IPouchWhitelistExtension.vyi", "Pouch").at(POUCH_WHITELIST_EXTENSION)
    return pouch.chimpers()


@pytest.fixture
def v3_withdrawer(renting_v3_factory, renting_erc721_factory):
    # account allowed to withdraw a V3 token: the receipt (renting ERC721) holder if minted, the NFT owner otherwise
    def _withdrawer(entry: dict) -> str:
        renting = renting_v3_factory.at(entry["renting"])
        receipt_holder = renting_erc721_factory.at(renting.renting_erc721()).owner_of(entry["token_id"])
        return emulate_eip7702(entry["nft_owner"] if receipt_holder == ZERO_ADDRESS else receipt_holder)

    return _withdrawer


@pytest.fixture
def withdraw(renting_v2_factory, renting_v3_factory, v3_withdrawer):
    # withdraws a stuck token, returning the account receiving it
    def _withdraw(entry: dict) -> str:
        if "nft_owner" in entry:
            withdrawer = v3_withdrawer(entry)
            renting_v3_factory.at(entry["renting"]).withdraw([v3_context(entry).to_tuple()], sender=withdrawer)
        else:
            withdrawer = emulate_eip7702(entry["owner"])
            renting_v2_factory.at(entry["renting"]).withdraw([v2_context(entry)], sender=withdrawer)
        return withdrawer

    return _withdraw


@pytest.fixture
def pause_v3_markets(markets, renting_v3_factory):
    # production state: V3 markets are paused before the extension is activated
    def _pause():
        for market in markets:
            if market["version"] == 3:
                renting = renting_v3_factory.at(market["renting"])
                renting.set_paused(True, sender=renting.protocol_admin())
                assert renting.paused()

    return _pause


@pytest.fixture
def deposit_v3(collections, renting_v3_factory, market_by):
    def _deposit(collection_name: str, token_id: int, owner: str):
        renting = renting_v3_factory.at(market_by(collection_name, 3)["renting"])
        collections[collection_name].approve(renting.tokenid_to_vault(token_id), token_id, sender=owner)
        renting.deposit([token_id], ZERO_ADDRESS, sender=owner)

    return _deposit


@pytest.fixture
def deposit_v2(collections, renting_v2_factory, market_by):
    def _deposit(collection_name: str, token_id: int, owner: str):
        renting = renting_v2_factory.at(market_by(collection_name, 2)["renting"])
        vault = renting.tokenid_to_vault(token_id)
        collections[collection_name].approve(vault, token_id, sender=owner)
        if is_eoa(vault):
            renting.create_vaults_and_deposit([token_id], 10**17, 1, 0, ZERO_ADDRESS, sender=owner)
        else:
            renting.deposit([token_id], 10**17, 1, 0, ZERO_ADDRESS, sender=owner)

    return _deposit


# Snapshot and configuration integrity


@pytest.mark.parametrize("entry", SNAPSHOT["v3"], ids=entry_id)
def test_v3_snapshot_matches_chain(entry, collections, renting_v3_factory, renting_erc721_factory):
    renting = renting_v3_factory.at(entry["renting"])
    assert collections[entry["collection"]].ownerOf(entry["token_id"]) == entry["vault"]
    assert renting.tokenid_to_vault(entry["token_id"]) == entry["vault"]
    assert renting.rental_states(entry["token_id"]) == state_hash_v3(entry["token_id"], entry)
    # no receipts were minted, so the stuck tokens can only be withdrawn by their depositors
    assert renting_erc721_factory.at(renting.renting_erc721()).owner_of(entry["token_id"]) == ZERO_ADDRESS


@pytest.mark.parametrize("entry", SNAPSHOT["v2"], ids=entry_id)
def test_v2_snapshot_matches_chain(entry, collections, renting_v2_factory, vault_v2_factory):
    renting = renting_v2_factory.at(entry["renting"])
    vault = vault_v2_factory.at(entry["vault"])
    assert collections[entry["collection"]].ownerOf(entry["token_id"]) == entry["vault"]
    assert renting.active_vaults(entry["token_id"]) == entry["vault"]
    assert renting.tokenid_to_vault(entry["token_id"]) == entry["vault"]
    assert vault.owner() == entry["owner"]
    assert vault.state() == state_hash_v2(entry)


def test_v1_vaults_hold_no_nfts():
    # V1 vaults are not covered by the extension
    assert SNAPSHOT["v1_vaults"]
    assert SNAPSHOT["v1_held"] == []


def test_markets_match_config_and_chain(extension, markets, renting_v2_factory, renting_v3_factory):
    for index, market in enumerate(markets):
        renting = (renting_v3_factory if market["version"] == 3 else renting_v2_factory).at(market["renting"])
        assert renting.nft_contract_addr() == market["collection"]
        assert renting.vault_impl_addr() == market["vault_impl"]
        assert extension.markets(index) == (market["collection"], market["renting"])

    with boa.reverts():
        extension.markets(len(markets))


def test_registered_vaults_match_renting_vaults(extension, markets, register_vaults, snapshot_entries):
    register_vaults(snapshot_entries)
    market_ids = {m["renting"]: index + 1 for index, m in enumerate(markets)}

    for entry in snapshot_entries:
        assert extension.vaults(entry["vault"]) == (market_ids[entry["renting"]], entry["token_id"])


def test_v3_markets_have_no_staking_addr(markets, renting_v3_factory):
    # staking functions remain available when paused, and call the staking contract from the vaults
    for market in markets:
        if market["version"] == 3:
            assert renting_v3_factory.at(market["renting"]).staking_addr() == ZERO_ADDRESS


@pytest.mark.parametrize("collection_name", GATED_COLLECTIONS)
def test_collections_are_gated_by_list_13(collection_name, collections, validator):
    policy = validator.getCollectionSecurityPolicy(collections[collection_name].address)
    assert collections[collection_name].getTransferValidator() == VALIDATOR
    assert policy.listId == LIST_ID
    assert validator.boundRuleset(policy.rulesetId) == RULESET_WHITELIST


# Today: vault transfers of the gated collections are blocked by the validator


@pytest.mark.parametrize("entry", SNAPSHOT["v3"], ids=entry_id)
def test_v3_withdraw_without_extension(entry, collections, renting_v3_factory, v3_withdrawer):
    renting = renting_v3_factory.at(entry["renting"])
    withdrawer = v3_withdrawer(entry)
    context = v3_context(entry).to_tuple()

    if is_rental_active(entry):
        with reverts_with("active rental"):
            renting.withdraw([context], sender=withdrawer)
    elif entry["collection"] in GATED_COLLECTIONS:
        with reverts_with("OTCNotAllowedForSmartWallets"):
            renting.withdraw([context], sender=withdrawer)
    else:
        # kodamara is not gated by the LimitBreak validator
        renting.withdraw([context], sender=withdrawer)
        assert collections[entry["collection"]].ownerOf(entry["token_id"]) == withdrawer


@pytest.mark.parametrize("entry", SNAPSHOT["v2"], ids=entry_id)
def test_v2_withdraw_without_extension(entry, renting_v2_factory):
    with reverts_with("OTCNotAllowedForSmartWallets"):
        renting_v2_factory.at(entry["renting"]).withdraw([v2_context(entry)], sender=entry["owner"])


@pytest.mark.parametrize("collection_name", GATED_COLLECTIONS)
def test_deposit_without_extension(collection_name, find_eoa_held_token, deposit_v2, deposit_v3):
    token_id, holder = find_eoa_held_token(collection_name)
    with reverts_with("CallerOrFromMustBeWhitelisted"):
        deposit_v3(collection_name, token_id, holder)
    with reverts_with("CallerOrFromMustBeWhitelisted"):
        deposit_v2(collection_name, token_id, holder)


# Registration


def test_only_list_owner_can_register_extension(validator, extension):
    with reverts_with("CallerDoesNotOwnList"):
        validator.addAccountsToList(
            LIST_ID, LIST_TYPE_WHITELIST_EXTENSION, [extension.address], sender=boa.env.generate_address()
        )

    assert validator.listOwners(LIST_ID) == LIST_OWNER
    validator.addAccountsToList(LIST_ID, LIST_TYPE_WHITELIST_EXTENSION, [extension.address], sender=LIST_OWNER)
    assert extension.address in validator.getListAccounts(LIST_ID, LIST_TYPE_WHITELIST_EXTENSION)


def test_register_vaults_of_unknown_renting(extension, prod_config):
    for renting in [prod_config["renting"]["koda"]["address"], prod_config["renting"]["bayc_v3"]["address"], ZERO_ADDRESS]:
        with boa.reverts("unknown renting"):
            extension.register_vaults(renting, [1])


# With the extension and the vaults registered: stuck NFTs can be withdrawn


@pytest.mark.parametrize("entry", SNAPSHOT["v3"], ids=entry_id)
def test_v3_withdraw_with_extension(entry, registered, extension, collections, renting_v3_factory, v3_withdrawer):
    renting = renting_v3_factory.at(entry["renting"])
    nft = collections[entry["collection"]]
    withdrawer = v3_withdrawer(entry)
    context = v3_context(entry).to_tuple()

    if is_rental_active(entry):
        with reverts_with("active rental"):
            renting.withdraw([context], sender=withdrawer)
        boa.env.time_travel(seconds=entry["active_rental"]["expiration"] - boa.env.timestamp + 1)

    renting.withdraw([context], sender=withdrawer)

    assert nft.ownerOf(entry["token_id"]) == withdrawer
    assert renting.rental_states(entry["token_id"]) == ZERO_BYTES32
    assert not extension.isWhitelisted(nft.address, entry["vault"])


@pytest.mark.parametrize("entry", SNAPSHOT["v3"], ids=entry_id)
def test_v3_withdraw_with_extension_and_paused_markets(entry, registered, pause_v3_markets, collections, withdraw):
    pause_v3_markets()
    if is_rental_active(entry):
        boa.env.time_travel(seconds=entry["active_rental"]["expiration"] - boa.env.timestamp + 1)

    withdrawer = withdraw(entry)
    assert collections[entry["collection"]].ownerOf(entry["token_id"]) == withdrawer


@pytest.mark.parametrize("collection_name", GATED_COLLECTIONS)
def test_v3_deposit_with_paused_markets(collection_name, registered, pause_v3_markets, find_eoa_held_token, deposit_v3):
    pause_v3_markets()
    token_id, holder = find_eoa_held_token(collection_name)
    with reverts_with("paused"):
        deposit_v3(collection_name, token_id, holder)


@pytest.mark.parametrize("entry", SNAPSHOT["v2"], ids=entry_id)
def test_v2_withdraw_with_extension(entry, registered, extension, collections, renting_v2_factory, withdraw):
    nft = collections[entry["collection"]]

    withdraw(entry)

    assert nft.ownerOf(entry["token_id"]) == entry["owner"]
    assert renting_v2_factory.at(entry["renting"]).active_vaults(entry["token_id"]) == ZERO_ADDRESS
    assert not extension.isWhitelisted(nft.address, entry["vault"])


@pytest.mark.parametrize("version", ["v2", "v3"])
def test_withdraw_requires_vault_registration(version, register_extension, withdraw):
    register_extension()
    with reverts_with("OTCNotAllowedForSmartWallets"):
        withdraw(first_entry(version))


@pytest.mark.parametrize("version", ["v2", "v3"])
def test_withdraw_requires_extension_registration(version, register_vaults, withdraw):
    entry = first_entry(version)
    register_vaults([entry])
    with reverts_with("OTCNotAllowedForSmartWallets"):
        withdraw(entry)


@pytest.mark.parametrize("version", ["v2", "v3"])
def test_withdraw_by_non_owner_still_reverts(version, registered, renting_v2_factory, renting_v3_factory):
    entry = first_entry(version)
    stranger = boa.env.generate_address()

    if version == "v3":
        with reverts_with("not owner"):
            renting_v3_factory.at(entry["renting"]).withdraw([v3_context(entry).to_tuple()], sender=stranger)
    else:
        with reverts_with("not owner of vault"):
            renting_v2_factory.at(entry["renting"]).withdraw([v2_context(entry)], sender=stranger)


def test_v3_withdraw_with_invalid_context_still_reverts(registered, renting_v3_factory, v3_withdrawer):
    entry = first_entry("v3")
    context = v3_context(entry)
    context.nft_owner = boa.env.generate_address()

    with reverts_with("invalid context"):
        renting_v3_factory.at(entry["renting"]).withdraw([context.to_tuple()], sender=v3_withdrawer(entry))


@pytest.mark.parametrize("paused", [False, True])
def test_v3_receipt_holder_withdraws_stuck_nft(
    paused, registered, pause_v3_markets, collections, renting_v3_factory, renting_erc721_factory
):
    # the transferable deposit receipt (renting ERC721) gives its holder the right to withdraw the NFT
    if paused:
        pause_v3_markets()
    entry = first_entry("v3", "koda")
    renting = renting_v3_factory.at(entry["renting"])
    receipt = renting_erc721_factory.at(renting.renting_erc721())
    context = v3_context(entry).to_tuple()
    buyer = boa.env.generate_address()
    assert receipt.owner_of(entry["token_id"]) == ZERO_ADDRESS

    renting.mint([context], sender=entry["nft_owner"])
    receipt.transferFrom(entry["nft_owner"], buyer, entry["token_id"], sender=entry["nft_owner"])
    with reverts_with("not owner"):
        renting.withdraw([context], sender=entry["nft_owner"])

    renting.withdraw([context], sender=buyer)
    assert collections["koda"].ownerOf(entry["token_id"]) == buyer


# With the extension and the vaults registered: deposits remain blocked


@pytest.mark.parametrize("collection_name", GATED_COLLECTIONS)
def test_deposit_with_extension_still_reverts(
    collection_name, registered, extension, market_by, find_eoa_held_token, deposit_v2, deposit_v3
):
    token_id, holder = find_eoa_held_token(collection_name)
    for version in [2, 3]:
        extension.register_vaults(market_by(collection_name, version)["renting"], [token_id])

    with reverts_with("CallerOrFromMustBeWhitelisted"):
        deposit_v3(collection_name, token_id, holder)
    with reverts_with("CallerOrFromMustBeWhitelisted"):
        deposit_v2(collection_name, token_id, holder)


@pytest.mark.parametrize("version", ["v2", "v3"])
def test_redeposit_after_withdraw_reverts(version, registered, extension, withdraw, deposit_v2, deposit_v3):
    # the vault stays registered after the withdrawal, but is no longer whitelisted
    entry = first_entry(version)
    owner = withdraw(entry)

    with reverts_with("CallerOrFromMustBeWhitelisted"):
        (deposit_v3 if version == "v3" else deposit_v2)(entry["collection"], entry["token_id"], owner)


def test_vault_owning_its_token_and_another(
    registered, extension, collections, validator, renting_v3_factory, withdraw, find_eoa_held_token
):
    # while a vault owns its token it is whitelisted for any transfer, but the protocol only moves its own token
    entry = first_entry("v3", "koda")
    nft = collections["koda"]
    renting = renting_v3_factory.at(entry["renting"])
    token_id, holder = find_eoa_held_token("koda")
    nft.transferFrom(holder, entry["vault"], token_id, sender=holder)

    assert extension.isWhitelisted(nft.address, entry["vault"])
    assert validator.validateTransferSim(nft.address, entry["vault"], entry["vault"], holder, token_id) == (True, NO_ERROR)
    with reverts_with("invalid context"):
        renting.withdraw([(token_id, holder, v3_context(entry).to_tuple()[2])], sender=holder)

    withdrawer = withdraw(entry)
    assert nft.ownerOf(entry["token_id"]) == withdrawer
    assert nft.ownerOf(token_id) == entry["vault"]
    assert not extension.isWhitelisted(nft.address, entry["vault"])


def test_vault_holding_other_token_not_whitelisted(
    registered, extension, collections, validator, withdraw, find_eoa_held_token
):
    entry = first_entry("v3", "koda")
    nft = collections["koda"]
    withdraw(entry)

    # anyone can send a token to a vault, which is only whitelisted while it owns its own token
    token_id, holder = find_eoa_held_token("koda")
    nft.transferFrom(holder, entry["vault"], token_id, sender=holder)

    assert not extension.isWhitelisted(nft.address, entry["vault"])
    assert validator.validateTransferSim(nft.address, entry["vault"], entry["vault"], holder, token_id) == (
        False,
        LB_ERROR_SELECTORS["OTCNotAllowedForSmartWallets"],
    )


# With the extension and the vaults registered: anything else is still blocked


@pytest.mark.parametrize(("collection_name", "version"), [(c, v) for c in GATED_COLLECTIONS for v in [2, 3]])
def test_vault_lookalike_not_whitelisted(
    collection_name,
    version,
    registered,
    extension,
    collections,
    market_by,
    vault_v2_factory,
    vault_v3_factory,
    validator,
    find_eoa_held_token,
):
    # a contract with the vault code, initialised by the renting contract and owning a token is still not a vault
    market = market_by(collection_name, version)
    nft = collections[collection_name]
    lookalike = deploy_minimal_proxy(market["vault_impl"], boa.env.generate_address())
    if version == 3:
        vault_v3_factory.at(lookalike).initialise(sender=market["renting"])
    else:
        vault_v2_factory.at(lookalike).initialise(boa.env.generate_address(), sender=market["renting"])
    assert boa.env.get_code(lookalike) == minimal_proxy_runtime(market["vault_impl"])
    assert vault_v2_factory.at(lookalike).caller() == market["renting"]

    token_id, holder = find_eoa_held_token(collection_name)
    nft.transferFrom(holder, lookalike, token_id, sender=holder)
    extension.register_vaults(market["renting"], [token_id])

    assert extension.vaults(lookalike) == (0, 0)
    assert not extension.isWhitelisted(nft.address, lookalike)
    operator, receiver = boa.env.generate_address(), boa.env.generate_address()
    assert validator.validateTransferSim(nft.address, lookalike, lookalike, receiver, token_id) == (
        False,
        LB_ERROR_SELECTORS["OTCNotAllowedForSmartWallets"],
    )
    assert validator.validateTransferSim(nft.address, operator, lookalike, receiver, token_id) == (
        False,
        LB_ERROR_SELECTORS["CallerOrFromMustBeWhitelisted"],
    )


def test_vaults_only_whitelisted_for_their_collection(registered, extension, collections, chimpers):
    for entry in SNAPSHOT["v2"] + SNAPSHOT["v3"]:
        for name, nft in collections.items():
            assert extension.isWhitelisted(nft.address, entry["vault"]) == (name == entry["collection"])
        for address in [chimpers, ZERO_ADDRESS, VALIDATOR]:
            assert not extension.isWhitelisted(address, entry["vault"])


def test_v1_vaults_not_whitelisted(registered, extension, collections, prod_config):
    for item in SNAPSHOT["v1_vaults"]:
        collection_key = prod_config["renting"][item["renting_key"].split(".")[1]]["properties"]["nft_contract_key"]
        assert not extension.isWhitelisted(collections[collection_key.split(".")[1]].address, item["vault"])


@pytest.mark.parametrize(
    "account",
    [ZERO_ADDRESS, *[f"0x{i:040x}" for i in range(1, 11)], VALIDATOR, LIST_OWNER, POUCH_WHITELIST_EXTENSION],
)
def test_non_vault_accounts_not_whitelisted(account, registered, extension, markets):
    for market in markets:
        for address in [account, market["renting"], market["vault_impl"], market["collection"]]:
            assert not extension.isWhitelisted(market["collection"], address)


def test_third_party_collection_on_shared_list_unaffected(registered, validator, chimpers):
    vault = SNAPSHOT["v3"][0]["vault"]
    holder, receiver = boa.env.generate_address(), boa.env.generate_address()
    assert validator.getCollectionSecurityPolicy(chimpers).listId == LIST_ID

    # a Zharta vault is still a non whitelisted smart wallet for other collections in the list
    assert validator.validateTransferSim(chimpers, vault, vault, receiver, 1) == (
        False,
        LB_ERROR_SELECTORS["OTCNotAllowedForSmartWallets"],
    )
    assert validator.validateTransferSim(chimpers, holder, holder, receiver, 1) == (True, NO_ERROR)


@pytest.mark.parametrize("collection_name", GATED_COLLECTIONS)
def test_validator_accepts_registered_vaults(collection_name, register_extension, register_vaults, validator, collections):
    entry = next(e for e in SNAPSHOT["v3"] if e["collection"] == collection_name)
    collection, vault, receiver = collections[collection_name].address, entry["vault"], boa.env.generate_address()
    blocked = (False, LB_ERROR_SELECTORS["OTCNotAllowedForSmartWallets"])

    assert validator.validateTransferSim(collection, vault, vault, receiver, entry["token_id"]) == blocked
    register_extension()
    assert validator.validateTransferSim(collection, vault, vault, receiver, entry["token_id"]) == blocked
    register_vaults([entry])
    assert validator.validateTransferSim(collection, vault, vault, receiver, entry["token_id"]) == (True, NO_ERROR)


@pytest.fixture
def fresh_fork():
    # a new fork, where the first calls to the collections are cold
    with boa.swap_env(Env()):
        boa.env.fork(os.environ["BOA_FORK_RPC_URL"], block_identifier=BLOCK)
        yield


@pytest.mark.parametrize("collection_name", GATED_COLLECTIONS)
def test_owner_of_gas_limit_covers_cold_lookup(collection_name, fresh_fork, markets):
    entry = first_entry("v3", collection_name)
    extension = boa.load("contracts/VaultWhitelistExtension.vy", [m["renting"] for m in markets])
    extension.register_vaults(entry["renting"], [entry["token_id"]])
    collection = next(m["collection"] for m in markets if m["collection_name"] == collection_name)

    assert extension.isWhitelisted(collection, entry["vault"])
    cold_gas_used = extension._computation.get_gas_used()
    assert extension.OWNER_OF_GAS() >= 4 * cold_gas_used


def test_extension_gas(registered, extension, collections, chimpers):
    # regression bounds with warm accesses, as during a transfer (cold costs are measured in the unit tests)
    def gas_used(collection, account):
        extension.isWhitelisted(collection, account)
        return extension._computation.get_gas_used()

    # what other collections sharing the list pay per lookup
    assert gas_used(chimpers, boa.env.generate_address()) < 5_000
    for entry in SNAPSHOT["v2"] + SNAPSHOT["v3"]:
        assert gas_used(chimpers, entry["vault"]) < 5_000

    # lookups for the gated collections
    for name in GATED_COLLECTIONS:
        entry = next(e for e in SNAPSHOT["v3"] if e["collection"] == name)
        other = next(e for e in SNAPSHOT["v3"] if e["collection"] != name)
        assert gas_used(collections[name].address, other["vault"]) < 5_000
        assert gas_used(collections[name].address, entry["vault"]) < 20_000
