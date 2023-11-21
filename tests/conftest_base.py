from dataclasses import dataclass
from functools import cached_property
from textwrap import dedent

import boa
import vyper
from web3 import Web3

ZERO_ADDRESS = boa.eval("empty(address)")
ZERO_BYTES32 = boa.eval("empty(bytes32)")


def get_last_event(contract: boa.vyper.contract.VyperContract, name: str = None):
    print("CONTRACT LOGS", contract.get_logs())
    print("\n\n\n")
    matching_events = [
        e for e in contract.get_logs() if isinstance(e, boa.vyper.event.Event) and (name is None or name == e.event_type.name)
    ]
    return EventWrapper(matching_events[-1])


def get_events(contract: boa.vyper.contract.VyperContract, name: str = None):
    return [
        EventWrapper(e)
        for e in contract.get_logs()
        if isinstance(e, boa.vyper.event.Event) and (name is None or name == e.event_type.name)
    ]


class EventWrapper:
    def __init__(self, event: boa.vyper.event.Event):
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


@dataclass
class Rental:
    id: bytes = ZERO_BYTES32
    owner: str = ZERO_ADDRESS
    renter: str = ZERO_ADDRESS
    token_id: int = 0
    start: int = 0
    min_expiration: int = 0
    expiration: int = 0
    amount: int = 0

    def to_tuple(self):
        return (self.id, self.owner, self.renter, self.token_id, self.start, self.min_expiration, self.expiration, self.amount)


@dataclass
class Listing:
    token_id: int = 0
    price: int = 0
    min_duration: int = 0
    max_duration: int = 0

    def to_tuple(self):
        return (self.token_id, self.price, self.min_duration, self.max_duration)


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


@dataclass
class RewardLog:
    vault: str
    token_id: int
    amount: int


@dataclass
class WithdrawalLog:
    vault: str
    token_id: int
    rewards: int


@dataclass
class TokenContext:
    token_id: int
    active_rental: Rental
    listing: Listing

    def to_tuple(self):
        return (self.token_id, self.active_rental.to_tuple(), self.listing.to_tuple())


@dataclass
class VaultState:
    active_rental: Rental
    listing: Listing

    def to_tuple(self):
        return (self.active_rental.to_tuple(), self.listing.to_tuple())


def compute_state_hash(rental: Rental, listing: Listing):
    return boa.eval(
        dedent(f"""keccak256(
            concat(
                {rental.id},
                convert({rental.owner}, bytes32),
                convert({rental.renter}, bytes32),
                convert({rental.token_id}, bytes32),
                convert({rental.start}, bytes32),
                convert({rental.min_expiration}, bytes32),
                convert({rental.expiration}, bytes32),
                convert({rental.amount}, bytes32),
                convert({listing.token_id}, bytes32),
                convert({listing.price}, bytes32),
                convert({listing.min_duration}, bytes32),
                convert({listing.max_duration}, bytes32)
            ))"""
        )
    )