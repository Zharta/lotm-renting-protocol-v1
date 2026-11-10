import os
import warnings

import click
from ape import chain
from ape.cli import ConnectedProviderCommand, network_option
from eth_abi import decode
from eth_utils import keccak

from ._helpers.deployment import DeploymentManager, Environment

ENV = Environment[os.environ.get("ENV", "local")]
CHAIN = os.environ.get("CHAIN", "nochain")
EXTENSION_KEY = "common.vault_whitelist_extension"
MAX_TOKENS = 128  # VaultWhitelistExtension.MAX_TOKENS

# deposit events (no indexed args) and the index of their (vault, token_id)[] arg
DEPOSIT_V2 = ["address", "address", "uint256", "uint256", "uint256", "(address,uint256)[]", "address"]
DEPOSIT_V3 = ["address", "address", "(address,uint256)[]", "address"]
DEPOSIT_EVENTS = {
    "v2": ([f"VaultsCreated({','.join(DEPOSIT_V2)})", f"NftsDeposited({','.join(DEPOSIT_V2)})"], DEPOSIT_V2, 5),
    "v3": ([f"NftsDeposited({','.join(DEPOSIT_V3)})"], DEPOSIT_V3, 2),
}

warnings.filterwarnings("ignore")


def deposited_token_ids(renting: str, version: str) -> set[int]:
    signatures, types, vaults_index = DEPOSIT_EVENTS[version]
    topics = {"0x" + keccak(text=signature).hex() for signature in signatures}
    logs = chain.provider.make_request("eth_getLogs", [{"address": renting, "fromBlock": "0x0", "toBlock": "latest"}])
    token_ids = set()
    for log in logs:
        if log["topics"] and log["topics"][0] in topics:
            data = decode(types, bytes.fromhex(log["data"][2:]))
            token_ids |= {token_id for _, token_id in data[vaults_index]}
    return token_ids


def owner_of(nft, token_id: int) -> str | None:
    # None for tokens that don't exist (e.g. Maras burned to mint Kodamaras)
    try:
        return nft.ownerOf(token_id)
    except Exception:
        return None


@click.command(cls=ConnectedProviderCommand)
@network_option()
@click.option("--dryrun/--no-dryrun", default=True, show_default=True)
def cli(network, dryrun):
    print(f"Connected to {network}, {dryrun=}")

    dm = DeploymentManager(ENV, CHAIN)
    extension_config = dm.context[EXTENSION_KEY]
    extension = extension_config.contract
    if extension is None:
        if not dryrun:
            raise click.ClickException(f"{EXTENSION_KEY} is not deployed")
        print(f"WARNING: {EXTENSION_KEY} is not deployed, not filtering already registered vaults")

    total = 0
    for renting_key in extension_config.renting_keys:
        renting_config = dm.context[renting_key]
        renting = renting_config.contract
        nft = dm.context[renting_config.deployment_args[2]].contract  # nft_contract_key
        version = renting_config.container_name.removeprefix("Renting").lower()  # v2 or v3

        pending = []
        for token_id in sorted(deposited_token_ids(renting.address, version)):
            vault = renting.tokenid_to_vault(token_id)
            if owner_of(nft, token_id) != vault:
                continue
            if extension is not None and extension.vaults(vault).market_id != 0:
                continue
            pending.append(token_id)

        print(f"{renting_key} {renting.address}: {len(pending)} vaults to register")
        for i in range(0, len(pending), MAX_TOKENS):
            token_ids = pending[i : i + MAX_TOKENS]
            print(f"## {EXTENSION_KEY}.register_vaults({renting.address}, {token_ids})")
            if not dryrun:
                extension.register_vaults(renting.address, token_ids, sender=dm.owner)
        total += len(pending)

    print(f"Done, {total} vaults {'to register' if dryrun else 'registered'}")
