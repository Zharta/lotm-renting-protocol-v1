"""
Builds the snapshot of NFTs held by Zharta vaults of LimitBreak gated collections, used by the fork tests.

For each market of the vault whitelist extension (prod config), replays the renting contract events up to the
snapshot block, keeps the tokens whose `ownerOf` is the vault and reconstructs their state (token context), which is
then validated against the on-chain state hash. Also lists the V1 tokens held by vaults (expected none) and some V1
vaults, which are not covered by the extension.

Usage: BOA_FORK_RPC_URL=<archive rpc> python -m tests.limitbreak.snapshot
The RPC must support `eth_getLogs` over the full block range for a single address (e.g. Alchemy).
"""

import json
import os
import urllib.request
from pathlib import Path

from eth_abi import decode
from eth_utils import keccak, to_checksum_address

from .constants import BLOCK, PROD_CONFIG, SNAPSHOT_FILE

ZERO_ADDRESS = "0x" + "00" * 20
ZERO_BYTES32 = "0x" + "00" * 32
V1_RENTING_KEYS = ["renting.koda", "renting.mara"]

RENTAL_LOG_V2 = "(bytes32,address,address,uint256,uint256,uint256,uint256,uint256,uint256,address)"
RENTAL_LOG_V3 = "(bytes32,address,address,uint256,uint256,uint256,uint256,uint256,uint256)"
RENTAL_EXTENSION_LOG_V3 = "(bytes32,address,address,uint256,uint256,uint256,uint256,uint256,uint256,uint256)"
VAULT_LOGS = "(address,uint256)[]"

EVENTS = {
    "v1": {
        f"VaultsCreated(address,address,uint256,uint256,uint256,{VAULT_LOGS})": "deposit_v1",
        f"NftsDeposited(address,address,uint256,uint256,uint256,{VAULT_LOGS})": "deposit_v1",
    },
    "v2": {
        f"VaultsCreated(address,address,uint256,uint256,uint256,{VAULT_LOGS},address)": "deposit_v2",
        f"NftsDeposited(address,address,uint256,uint256,uint256,{VAULT_LOGS},address)": "deposit_v2",
        f"ListingsChanged(address,address,uint256,uint256,uint256,{VAULT_LOGS},address)": "listing_v2",
        f"ListingsCancelled(address,address,{VAULT_LOGS},address)": "cancel_v2",
        f"RentalStarted(address,address,address,{RENTAL_LOG_V2}[])": "rental_started_v2",
        f"RentalClosed(address,address,{RENTAL_LOG_V2}[])": "rental_closed_v2",
        "RewardsClaimed(address,address,(address,uint256,uint256,uint256,uint256)[])": "rewards_v2",
        "NftsWithdrawn(address,address,uint256,(address,uint256,uint256,uint256)[])": "withdrawn_v2",
    },
    "v3": {
        f"NftsDeposited(address,address,{VAULT_LOGS},address)": "deposit_v3",
        "NftsWithdrawn(address,address,uint256,(address,uint256)[])": "withdrawn_v3",
        f"RentalStarted(address,address,address,{RENTAL_LOG_V3}[])": "rental_started_v3",
        f"RentalClosed(address,address,{RENTAL_LOG_V3}[])": "rental_closed_v3",
        f"RentalExtended(address,address,{RENTAL_EXTENSION_LOG_V3}[])": "rental_extended_v3",
        f"RenterDelegatedToWallet(address,address,address,{VAULT_LOGS})": "renter_delegated_v3",
        "RewardsClaimed(address,address,uint256,uint256,(uint256,uint256)[])": "rewards_v3",
        "TokenOwnershipChanged(address,address,uint256[])": "ownership_v3",
        "ProtocolFeeSet(uint256,uint256,address)": "protocol_fee_v3",
    },
}


def event_types(signature: str) -> list[str]:
    args = signature[signature.index("(") + 1 : -1]
    types, depth, current = [], 0, ""
    for char in args:
        if char == "," and depth == 0:
            types.append(current)
            current = ""
            continue
        depth += {"(": 1, ")": -1}.get(char, 0)
        current += char
    return [*types, current]


class Rpc:
    def __init__(self, url: str, block: int):
        self.url = url
        self.block = hex(block)

    def request(self, method: str, params: list):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
        request = urllib.request.Request(self.url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read())
        if "error" in result:
            raise RuntimeError(f"{method} failed: {result['error']}")
        return result["result"]

    def call(self, to: str, signature: str, args: bytes = b"") -> bytes:
        data = "0x" + (keccak(text=signature)[:4] + args).hex()
        return bytes.fromhex(self.request("eth_call", [{"to": to, "data": data}, self.block])[2:])

    def logs(self, address: str) -> list[dict]:
        logs = self.request("eth_getLogs", [{"address": address, "fromBlock": "0x0", "toBlock": self.block}])
        return sorted(logs, key=lambda log: (int(log["blockNumber"], 16), int(log["logIndex"], 16)))

    def owner_of(self, nft: str, token_id: int) -> str | None:
        # None for tokens that don't exist (e.g. Maras burned to mint Kodamaras)
        try:
            return to_checksum_address(self.call(nft, "ownerOf(uint256)", token_id.to_bytes(32, "big"))[-20:])
        except RuntimeError as error:
            if "execution reverted" in str(error):
                return None
            raise


def empty_rental(*, with_protocol_wallet: bool) -> dict:
    rental = {
        "id": ZERO_BYTES32,
        "owner": ZERO_ADDRESS,
        "renter": ZERO_ADDRESS,
        "delegate": ZERO_ADDRESS,
        "token_id": 0,
        "start": 0,
        "min_expiration": 0,
        "expiration": 0,
        "amount": 0,
        "protocol_fee": 0,
    }
    return rental | {"protocol_wallet": ZERO_ADDRESS} if with_protocol_wallet else rental


def rental_from_log(renter, delegate, rental_id, owner, token_id, start, min_expiration, expiration, amount, fee) -> dict:
    return {
        "id": "0x" + rental_id.hex(),
        "owner": to_checksum_address(owner),
        "renter": to_checksum_address(renter),
        "delegate": to_checksum_address(delegate),
        "token_id": token_id,
        "start": start,
        "min_expiration": min_expiration,
        "expiration": expiration,
        "amount": amount,
        "protocol_fee": fee,
    }


class Replay:
    """Rebuilds the state of each token held by the renting contract vaults from its events"""

    def __init__(self):
        self.state: dict[int, dict] = {}
        self.protocol_fee = None

    def deposit_v1(self, data):
        for vault, token_id in data[5]:
            self.state[token_id] = {"vault": to_checksum_address(vault)}

    def deposit_v2(self, data):
        for vault, token_id in data[5]:
            self.state[token_id] = {
                "vault": to_checksum_address(vault),
                "active_rental": empty_rental(with_protocol_wallet=True),
            }
        self.listing_v2(data)

    def listing_v2(self, data):
        for _, token_id in data[5]:
            listing = {"token_id": token_id, "price": data[4], "min_duration": data[2], "max_duration": data[3]}
            self.state[token_id]["listing"] = listing

    def cancel_v2(self, data):
        for _, token_id in data[2]:
            self.state[token_id]["listing"] = {"token_id": token_id, "price": 0, "min_duration": 0, "max_duration": 0}

    def rental_started_v2(self, data):
        for *fields, protocol_wallet in data[3]:
            rental_id, _, owner, token_id, *values = fields
            self.state[token_id]["active_rental"] = rental_from_log(data[0], data[1], rental_id, owner, token_id, *values) | {
                "protocol_wallet": to_checksum_address(protocol_wallet)
            }

    def rental_closed_v2(self, data):
        for log in data[2]:
            self.state[log[3]]["active_rental"] = empty_rental(with_protocol_wallet=True)

    def rewards_v2(self, data):
        for _, token_id, _, _, active_rental_amount in data[2]:
            self.state[token_id]["active_rental"]["amount"] = active_rental_amount

    def withdrawn_v2(self, data):
        for _, token_id, _, _ in data[3]:
            self.state.pop(token_id, None)

    def deposit_v3(self, data):
        for vault, token_id in data[2]:
            self.state[token_id] = {
                "vault": to_checksum_address(vault),
                "nft_owner": to_checksum_address(data[0]),
                "active_rental": empty_rental(with_protocol_wallet=False),
            }

    def withdrawn_v3(self, data):
        for _, token_id in data[3]:
            self.state.pop(token_id, None)

    def rental_started_v3(self, data):
        for rental_id, _, owner, token_id, *values in data[3]:
            self.state[token_id]["active_rental"] = rental_from_log(data[0], data[1], rental_id, owner, token_id, *values)

    def rental_closed_v3(self, data):
        for log in data[2]:
            self.state[log[3]]["active_rental"] = empty_rental(with_protocol_wallet=False)

    def rental_extended_v3(self, data):
        # the extended rental keeps the delegate, is owned by the nft owner and uses the current protocol fee
        for rental_id, _, _, token_id, start, min_expiration, expiration, _, extension_amount, fee in data[2]:
            token = self.state[token_id]
            delegate = token["active_rental"]["delegate"]
            fee = fee if self.protocol_fee is None else self.protocol_fee
            values = [start, min_expiration, expiration, extension_amount, fee]
            token["active_rental"] = rental_from_log(data[0], delegate, rental_id, token["nft_owner"], token_id, *values)

    def renter_delegated_v3(self, data):
        for _, token_id in data[3]:
            self.state[token_id]["active_rental"]["delegate"] = to_checksum_address(data[1])

    def rewards_v3(self, data):
        for token_id, active_rental_amount in data[4]:
            self.state[token_id]["active_rental"]["amount"] = active_rental_amount

    def ownership_v3(self, data):
        for token_id in data[2]:
            self.state[token_id]["nft_owner"] = to_checksum_address(data[0])

    def protocol_fee_v3(self, data):
        self.protocol_fee = data[1]


def replay(rpc: Rpc, renting: str, version: str) -> dict[int, dict]:
    topics = {
        "0x" + keccak(text=signature).hex(): (handler, event_types(signature))
        for signature, handler in EVENTS[version].items()
    }
    events = Replay()
    for log in rpc.logs(renting):
        if log["topics"] and log["topics"][0] in topics:
            handler, types = topics[log["topics"][0]]
            getattr(events, handler)(decode(types, bytes.fromhex(log["data"][2:])))
    return events.state


def address_word(address: str) -> bytes:
    return bytes.fromhex(address[2:].rjust(64, "0"))


def rental_words(rental: dict, *, with_delegate: bool) -> bytes:
    words = bytes.fromhex(rental["id"][2:]) + address_word(rental["owner"]) + address_word(rental["renter"])
    if with_delegate:
        words += address_word(rental["delegate"])
    for field in ["token_id", "start", "min_expiration", "expiration", "amount", "protocol_fee"]:
        words += rental[field].to_bytes(32, "big")
    return words


def state_hash_v2(entry: dict) -> bytes:
    listing = entry["listing"]
    words = rental_words(entry["active_rental"], with_delegate=False) + address_word(entry["active_rental"]["protocol_wallet"])
    for field in ["token_id", "price", "min_duration", "max_duration"]:
        words += listing[field].to_bytes(32, "big")
    return keccak(words)


def state_hash_v3(token_id: int, entry: dict) -> bytes:
    words = token_id.to_bytes(32, "big") + address_word(entry["nft_owner"])
    return keccak(words + rental_words(entry["active_rental"], with_delegate=True))


def collection_of(config: dict, renting_name: str) -> tuple[str, str]:
    collection_name = config["renting"][renting_name]["properties"]["nft_contract_key"].split(".")[1]
    return collection_name, config["common"][collection_name]["address"]


def build_snapshot(rpc: Rpc, config: dict, block: int) -> dict:
    snapshot = {"block": block, "v2": [], "v3": [], "v1_vaults": [], "v1_held": []}
    for renting_key in config["common"]["vault_whitelist_extension"]["properties"]["renting_keys"]:
        renting_name = renting_key.split(".")[1]
        collection_name, collection = collection_of(config, renting_name)
        renting = config["renting"][renting_name]["address"]
        version = "v" + config["renting"][renting_name]["version"]
        for token_id, entry in sorted(replay(rpc, renting, version).items()):
            if rpc.owner_of(collection, token_id) != entry["vault"]:
                continue
            item = {"collection": collection_name, "renting": renting, "token_id": token_id} | entry
            if version == "v2":
                item["owner"] = to_checksum_address(rpc.call(entry["vault"], "owner()")[-20:])
                if rpc.call(entry["vault"], "state()") != state_hash_v2(entry):
                    raise RuntimeError(f"state mismatch {renting_name} {token_id}")
            elif rpc.call(renting, "rental_states(uint256)", token_id.to_bytes(32, "big")) != state_hash_v3(token_id, entry):
                raise RuntimeError(f"state mismatch {renting_name} {token_id}")
            snapshot[version].append(item)

    # V1 vaults are not covered by the extension, so they must not hold any NFT
    for renting_key in V1_RENTING_KEYS:
        renting_name = renting_key.split(".")[1]
        _, collection = collection_of(config, renting_name)
        deposits = replay(rpc, config["renting"][renting_name]["address"], "v1")
        held = [
            token_id for token_id, entry in sorted(deposits.items()) if rpc.owner_of(collection, token_id) == entry["vault"]
        ]
        snapshot["v1_held"] += [{"renting_key": renting_key, "token_id": token_id} for token_id in held]
        vaults = sorted({entry["vault"] for entry in deposits.values()})
        snapshot["v1_vaults"] += [{"renting_key": renting_key, "vault": vault} for vault in vaults[:3]]
    return snapshot


def main():
    config = json.loads(Path(PROD_CONFIG).read_text(encoding="utf-8"))
    rpc = Rpc(os.environ["BOA_FORK_RPC_URL"], BLOCK)
    snapshot = build_snapshot(rpc, config, BLOCK)
    Path(SNAPSHOT_FILE).write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"{len(snapshot['v2'])} v2 and {len(snapshot['v3'])} v3 tokens held by vaults at block {BLOCK}")


if __name__ == "__main__":
    main()
