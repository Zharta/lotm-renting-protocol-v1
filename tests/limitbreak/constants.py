from pathlib import Path

from eth_utils import keccak

ROOT = Path(__file__).parents[2]
PROD_CONFIG = ROOT / "configs/prod/ethereum/renting.json"
SNAPSHOT_FILE = Path(__file__).parent / "vaults_snapshot.json"

# mainnet block after the collections moved to the LimitBreak validator and before the extension is registered
BLOCK = 26228732

VALIDATOR = "0x721C008fdff27BF06E7E123956E2Fe03B63342e3"
RULESET_WHITELIST = "0x00721CE73fDE1e57A9048E0e19B7ee7c8D3F10E3"
LIST_ID = 13
LIST_OWNER = "0x7D79Bd0E4B3dC90665A3ed30Aa6C6c06c89D224E"
LIST_TYPE_WHITELIST_EXTENSION = 3

# Chimpers whitelist extension registered in list 13, used to find a third party collection sharing the list
POUCH_WHITELIST_EXTENSION = "0x44a60AF9354dAe6F073AeAf8Ff3EDb60953082b5"

LB_ERRORS = {
    keccak(text=f"CreatorTokenTransferValidator__{name}()")[:4]: name
    for name in [
        "CallerDoesNotOwnList",
        "CallerOrFromMustBeWhitelisted",
        "OTCNotAllowedForSmartWallets",
    ]
}
