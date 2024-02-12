import contextlib
from collections import namedtuple
from dataclasses import dataclass, field
from functools import cached_property
from textwrap import dedent

import boa
import vyper
from boa.contracts.vyper.event import Event
from boa.contracts.vyper.vyper_contract import VyperContract
from eth.exceptions import Revert
from eth_abi import encode
from eth_account import Account
from eth_account.messages import encode_intended_validator, encode_structured_data
from eth_utils import encode_hex, keccak
from web3 import Web3

ZERO_ADDRESS = boa.eval("empty(address)")
ZERO_BYTES32 = boa.eval("empty(bytes32)")


def get_last_event(contract: VyperContract, name: str = None):
    print("CONTRACT LOGS", contract.get_logs())
    print("\n\n\n")
    matching_events = [e for e in contract.get_logs() if isinstance(e, Event) and (name is None or name == e.event_type.name)]
    return EventWrapper(matching_events[-1])


def get_events(contract: VyperContract, name: str = None):
    return [
        EventWrapper(e) for e in contract.get_logs() if isinstance(e, Event) and (name is None or name == e.event_type.name)
    ]


class EventWrapper:
    def __init__(self, event: Event):
        self.event = event
        self.event_name = event.event_type.name

    def __getattr__(self, name):
        print(f"getattr {self=} {name=}")
        if name in self.args_dict:
            return self.args_dict[name]
        else:
            raise AttributeError(f"No attr {name} in {self.event_name}. Event data is {self.event}")

    @cached_property
    def args_dict(self):
        print(f"{self.event=} {self.event.event_type.arguments=}")
        args = self.event.event_type.arguments.keys()
        indexed = self.event.event_type.indexed
        topic_values = (v for v in self.event.topics)
        args_values = (v for v in self.event.args)
        _args = [(arg, next(topic_values) if indexed[i] else next(args_values)) for i, arg in enumerate(args)]

        return {k: self._format_value(v, self.event.event_type.arguments[k]) for k, v in _args}

    def _format_value(self, v, _type):
        print(f"_format_value {v=} {_type=} {type(v).__name__=} {type(_type)=}")
        if isinstance(_type, vyper.semantics.types.primitives.AddressT):
            return Web3.to_checksum_address(v)
        # elif isinstance(_type, vyper.semantics.types.value.bytes_fixed.Bytes32Definition):
        elif isinstance(_type, vyper.semantics.types.primitives.BytesT):
            return f"0x{v.hex()}"
        return v


# TODO: find a better way to do this. also would be useful to get structs attrs by name
def checksummed(obj, vyper_type=None):
    if vyper_type is None and hasattr(obj, "_vyper_type"):
        vyper_type = obj._vyper_type
    print(f"checksummed {obj=} {vyper_type=} {type(obj).__name__=} {type(vyper_type)=}")

    if isinstance(vyper_type, vyper.codegen.types.types.DArrayType):
        return list(checksummed(x, vyper_type.subtype) for x in obj)

    elif isinstance(vyper_type, vyper.codegen.types.types.StructType):
        return tuple(checksummed(*arg) for arg in zip(obj, vyper_type.tuple_members()))

    elif isinstance(vyper_type, vyper.codegen.types.types.BaseType):
        if vyper_type.typ == "address":
            return Web3.toChecksumAddress(obj)
        elif vyper_type.typ == "bytes32":
            return f"0x{obj.hex()}"

    return obj


def get_vault_from_proxy(proxy_addr):
    deployer = boa.load_partial("contracts/Vault.vy")
    return deployer.at(proxy_addr)


@contextlib.contextmanager
def deploy_reverts():
    try:
        yield
        raise ValueError("Did not revert")
    except Revert:
        ...


@dataclass
class Rental:
    id: bytes = ZERO_BYTES32
    owner: str = ZERO_ADDRESS
    renter: str = ZERO_ADDRESS
    delegate: str = ZERO_ADDRESS
    token_id: int = 0
    start: int = 0
    min_expiration: int = 0
    expiration: int = 0
    amount: int = 0
    protocol_fee: int = 0

    def to_tuple(self):
        return (
            self.id,
            self.owner,
            self.renter,
            self.delegate,
            self.token_id,
            self.start,
            self.min_expiration,
            self.expiration,
            self.amount,
            self.protocol_fee,
        )


@dataclass
class Listing:
    token_id: int = 0
    price: int = 0
    min_duration: int = 0
    max_duration: int = 0
    timestamp: int = 0

    def to_tuple(self):
        return (self.token_id, self.price, self.min_duration, self.max_duration, self.timestamp)


@dataclass
class VaultLog:
    vault: str
    token_id: int


@dataclass
class RentalLog:
    id: bytes
    vault: str
    owner: str
    token_id: int
    start: int
    min_expiration: int
    expiration: int
    amount: int
    protocol_fee: int = 0

    def to_rental(self, renter: str = ZERO_ADDRESS, delegate: str = ZERO_ADDRESS):
        return Rental(
            self.id,
            self.owner,
            renter,
            delegate,
            self.token_id,
            self.start,
            self.min_expiration,
            self.expiration,
            self.amount,
            self.protocol_fee,
        )


@dataclass
class RentalExtensionLog:
    id: bytes
    vault: str
    owner: str
    token_id: int
    start: int
    min_expiration: int
    expiration: int
    amount_settled: int
    extension_amount: int
    protocol_fee: int = 0

    def to_rental(self, renter: str = ZERO_ADDRESS, delegate: str = ZERO_ADDRESS):
        return Rental(
            self.id,
            self.owner,
            renter,
            delegate,
            self.token_id,
            self.start,
            self.min_expiration,
            self.expiration,
            self.extension_amount,
            self.protocol_fee,
        )


@dataclass
class RewardLog:
    # vault: str
    token_id: int
    # amount: int
    # protocol_fee_amount: int
    active_rental_amount: int


@dataclass
class WithdrawalLog:
    vault: str
    token_id: int
    rewards: int
    protocol_fee_amount: int


@dataclass
class TokenContext:
    token_id: int = 0
    nft_owner: str = ZERO_ADDRESS
    active_rental: Rental = field(default_factory=Rental)

    def to_tuple(self):
        return (self.token_id, self.nft_owner, self.active_rental.to_tuple())


TokenAndWallet = namedtuple("TokenAndWallet", ["token_id", "wallet"], defaults=[0, ZERO_ADDRESS])


@dataclass
class VaultState:
    active_rental: Rental = field(default_factory=Rental)
    listing: Listing = field(default_factory=Listing)

    def to_tuple(self):
        return (self.active_rental.to_tuple(), self.listing.to_tuple())


@dataclass
class Signature:
    v: int
    r: int
    s: int

    def to_tuple(self):
        return (self.v, self.r, self.s)


@dataclass
class SignedListing:
    listing: Listing
    owner_signature: Signature
    admin_signature: Signature

    def to_tuple(self):
        return (self.listing.to_tuple(), self.owner_signature.to_tuple(), self.admin_signature.to_tuple())


@dataclass
class TokenContextAndListing:
    token_context: TokenContext
    signed_listing: SignedListing

    def to_tuple(self):
        return (self.token_context.to_tuple(), self.signed_listing.to_tuple())


def compute_state_hash(token_id: int, nft_owner: str, rental: Rental):
    return boa.eval(
        dedent(
            f"""keccak256(
            concat(
                convert({token_id}, bytes32),
                convert({nft_owner}, bytes32),
                {rental.id},
                convert({rental.owner}, bytes32),
                convert({rental.renter}, bytes32),
                convert({rental.delegate}, bytes32),
                convert({rental.token_id}, bytes32),
                convert({rental.start}, bytes32),
                convert({rental.min_expiration}, bytes32),
                convert({rental.expiration}, bytes32),
                convert({rental.amount}, bytes32),
                convert({rental.protocol_fee}, bytes32),
            ))"""
        )
    )


def sign_listing(listing: Listing, owner_key: str, admin_key: str, timestamp: int, verifying_contract: str) -> SignedListing:
    typed_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Listing": [
                {"name": "token_id", "type": "uint256"},
                {"name": "price", "type": "uint256"},
                {"name": "min_duration", "type": "uint256"},
                {"name": "max_duration", "type": "uint256"},
                {"name": "timestamp", "type": "uint256"},
            ],
        },
        "primaryType": "Listing",
        "domain": {
            "name": "Zharta",
            "version": "1",
            "chainId": boa.eval("chain.id"),
            "verifyingContract": verifying_contract,
        },
        "message": vars(listing),
    }
    signable_msg = encode_structured_data(typed_data)
    signed_msg = Account.from_key(owner_key).sign_message(signable_msg)
    owner_signature = Signature(signed_msg.v, signed_msg.r, signed_msg.s)

    encoded_owner_sig = encode(("(uint256,uint256,uint256)",), (owner_signature.to_tuple(),))
    encoded_timestamp = encode(("uint256",), (timestamp,))
    hash = keccak(primitive=encoded_owner_sig)

    signable_msg = encode_intended_validator(verifying_contract, hexstr=encode_hex(hash + encoded_timestamp))
    signed_msg = Account.from_key(admin_key).sign_message(signable_msg)
    admin_signature = Signature(signed_msg.v, signed_msg.r, signed_msg.s)

    return SignedListing(listing, owner_signature, admin_signature)
