import contextlib
import json
import os
from itertools import groupby
from operator import itemgetter

import boa
import pytest
from boa.contracts.base_evm_contract import BoaError
from boa.environment import Env
from eth_abi import decode
from eth_utils import keccak
from vyper.compiler import compile_code

from ..conftest_base import Rental, TokenContext
from .constants import (
    BLOCK,
    LB_ERRORS,
    LIST_ID,
    LIST_OWNER,
    LIST_TYPE_WHITELIST_EXTENSION,
    PROD_CONFIG,
    ROOT,
    SNAPSHOT_FILE,
    VALIDATOR,
)

ERROR_STRING_SELECTOR = keccak(text="Error(string)")[:4]
EIP7702_PREFIX = bytes.fromhex("ef0100")

SNAPSHOT = json.loads(SNAPSHOT_FILE.read_text())
assert SNAPSHOT["block"] == BLOCK, "snapshot generated for another block, run `python -m tests.limitbreak.snapshot`"


@pytest.fixture(scope="session", autouse=True)
def forked_env():
    new_env = Env()

    with boa.swap_env(new_env):
        fork_uri = os.environ["BOA_FORK_RPC_URL"]
        boa.env.fork(fork_uri, block_identifier=BLOCK)
        yield


@pytest.fixture(autouse=True)
def isolation(forked_env):
    with boa.env.anchor():
        yield


def revert_reason(output: bytes) -> str:
    if output[:4] == ERROR_STRING_SELECTOR:
        return decode(["string"], output[4:])[0]
    return LB_ERRORS.get(output[:4], output.hex())


@contextlib.contextmanager
def reverts_with(reason: str):
    with pytest.raises(BoaError) as error:
        yield
    assert revert_reason(bytes(error.value.call_trace.output)) == reason


def abi_factory(path: str, name: str):
    abi = compile_code((ROOT / path).read_text(), contract_path=path, output_formats=["abi"])["abi"]
    return boa.loads_abi(json.dumps(abi), name=name)


def is_eoa(address: str) -> bool:
    return len(boa.env.get_code(address)) == 0


def emulate_eip7702(account: str) -> str:
    # The pinned py-evm predates EIP-7702 and executes the delegation designator as code. For accounts receiving NFTs,
    # run the delegate code in the account, which is what the EVM does since Prague for calls into delegated EOAs.
    code = boa.env.get_code(account)
    if code[:3] == EIP7702_PREFIX and len(code) == 23:
        boa.env.set_code(account, boa.env.get_code("0x" + code[3:].hex()))
    return account


def is_locked(nft, token_id: int) -> bool:
    try:
        return nft.isLocked(token_id)
    except BoaError:
        return False


@pytest.fixture(scope="session")
def prod_config():
    return json.loads(PROD_CONFIG.read_text())


@pytest.fixture(scope="session")
def nft_factory():
    return abi_factory("tests/limitbreak/interfaces/ICreatorToken.vyi", "CreatorToken")


@pytest.fixture(scope="session")
def renting_v2_factory():
    return abi_factory("tests/limitbreak/interfaces/IRentingV2.vyi", "RentingV2")


@pytest.fixture(scope="session")
def vault_v2_factory():
    return abi_factory("tests/limitbreak/interfaces/IVaultV2.vyi", "VaultV2")


@pytest.fixture(scope="session")
def renting_v3_factory():
    return abi_factory("contracts/RentingV3.vy", "RentingV3")


@pytest.fixture(scope="session")
def renting_erc721_factory():
    return abi_factory("contracts/RentingERC721V3.vy", "RentingERC721V3")


@pytest.fixture(scope="session")
def vault_v3_factory():
    return abi_factory("contracts/VaultV3.vy", "VaultV3")


@pytest.fixture(scope="session")
def validator():
    return abi_factory("tests/limitbreak/interfaces/ITransferValidator.vyi", "TransferValidator").at(VALIDATOR)


@pytest.fixture(scope="session")
def markets(prod_config):
    # markets of the vault whitelist extension as configured for deployment, with keys resolved to addresses

    def address(key):
        scope, name = key.split(".")
        return prod_config[scope][name]["address"]

    markets = []
    for renting_key in prod_config["common"]["vault_whitelist_extension"]["properties"]["renting_keys"]:
        renting = prod_config["renting"][renting_key.split(".")[1]]
        collection_key = renting["properties"]["nft_contract_key"]
        markets.append(
            {
                "collection_name": collection_key.split(".")[1],
                "collection": address(collection_key),
                "renting": renting["address"],
                "vault_impl": address(renting["properties"]["vault_impl_key"]),
                "version": int(renting["version"]),
            }
        )
    return markets


@pytest.fixture(scope="session")
def market_by(markets):
    def _market_by(collection_name: str, version: int) -> dict:
        return next(m for m in markets if m["collection_name"] == collection_name and m["version"] == version)

    return _market_by


@pytest.fixture(scope="session")
def collections(markets, nft_factory):
    return {m["collection_name"]: nft_factory.at(m["collection"]) for m in markets}


@pytest.fixture(scope="session")
def extension(forked_env, markets):
    return boa.load("contracts/VaultWhitelistExtension.vy", [m["renting"] for m in markets])


@pytest.fixture
def register_extension(validator, extension):
    def _register():
        validator.addAccountsToList(LIST_ID, LIST_TYPE_WHITELIST_EXTENSION, [extension.address], sender=LIST_OWNER)

    return _register


@pytest.fixture
def register_vaults(extension):
    def _register(entries: list[dict]):
        for renting, group in groupby(sorted(entries, key=itemgetter("renting")), key=itemgetter("renting")):
            extension.register_vaults(renting, [e["token_id"] for e in group], sender=boa.env.generate_address())

    return _register


@pytest.fixture
def registered(register_extension, register_vaults, snapshot_entries):
    # the extension is registered in the validator list and the vaults holding NFTs are registered in the extension
    register_extension()
    register_vaults(snapshot_entries)


@pytest.fixture(scope="session")
def snapshot_entries():
    return SNAPSHOT["v2"] + SNAPSHOT["v3"]


@pytest.fixture(scope="session")
def find_eoa_held_token(forked_env, collections):
    # finds a token of each collection held by an EOA (with no code), at the fork block, before any test changes state
    found = {}
    for collection_name, nft in collections.items():
        for token_id in range(1, 1000):
            try:
                holder = nft.ownerOf(token_id)
            except BoaError:
                continue
            if is_eoa(holder) and not is_locked(nft, token_id):
                found[collection_name] = (token_id, holder)
                break

    def _find(collection_name: str) -> tuple[int, str]:
        return found[collection_name]

    return _find


def v3_context(entry: dict) -> TokenContext:
    rental = entry["active_rental"]
    return TokenContext(
        token_id=entry["token_id"],
        nft_owner=entry["nft_owner"],
        active_rental=Rental(**(rental | {"id": bytes.fromhex(rental["id"][2:])})),
    )


def v2_context(entry: dict) -> tuple:
    rental = entry["active_rental"]
    listing = entry["listing"]
    return (
        entry["token_id"],
        (
            bytes.fromhex(rental["id"][2:]),
            rental["owner"],
            rental["renter"],
            rental["delegate"],
            rental["token_id"],
            rental["start"],
            rental["min_expiration"],
            rental["expiration"],
            rental["amount"],
            rental["protocol_fee"],
            rental["protocol_wallet"],
        ),
        (listing["token_id"], listing["price"], listing["min_duration"], listing["max_duration"]),
    )
