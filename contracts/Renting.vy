# @version 0.3.9

# Interfaces

interface ISelf:
    def tokenid_to_vault(token_id: uint256) -> address: view
    def is_vault_available(token_id: uint256) -> bool: view


interface IVault:
    def is_initialised() -> bool: view
    def initialise(owner: address, caller: address, payment_token_addr: address, nft_contract_addr: address, delegation_registry_addr: address): nonpayable
    def deposit(token_id: uint256, price: uint256, max_duration: uint256): nonpayable
    def set_listing_price(sender: address, price: uint256, max_duration: uint256): nonpayable
    def start_rental(renter: address, expiration: uint256) -> Rental: nonpayable
    def close_rental(sender: address) -> (Rental, uint256): nonpayable
    def claim(sender: address) -> uint256: nonpayable
    def withdraw(sender: address) -> uint256: nonpayable
    def owner() -> address: view


# Structs

struct Rental:
    id: bytes32 # keccak256 of the renter, token_id, start and expiration
    owner: address
    renter: address
    token_id: uint256
    start: uint256
    expiration: uint256
    amount: uint256


# Events

event VaultCreated:
    vault: address
    owner: address
    nft_contract: address
    token_id: uint256

event NFTDeposited:
    vault: address
    owner: address
    nft_contract: address
    token_id: uint256
    max_duration: uint256

event NFTWithdrawn:
    vault: address
    owner: address
    nft_contract: address
    token_id: uint256
    claimed_rewards: uint256

event ListingPriceChanged:
    vault: address
    owner: address
    nft_contract: address
    token_id: uint256
    price: uint256
    max_duration: uint256

event ListingCancelled:
    vault: address
    owner: address
    nft_contract: address
    token_id: uint256

event RentalStarted:
    id: bytes32
    vault: address
    owner: address
    renter: address
    nft_contract: address
    token_id: uint256
    start: uint256
    expiration: uint256
    amount: uint256

event RentalClosed:
    id: bytes32
    vault: address
    owner: address
    renter: address
    nft_contract: address
    token_id: uint256
    start: uint256
    expiration: uint256
    amount: uint256

event RewardsClaimed:
    vault: address
    owner: address
    nft_contract: address
    token_id: uint256
    amount: uint256


# Global Variables

_COLLISION_OFFSET: constant(bytes1) = 0xFF
_DEPLOYMENT_CODE: constant(bytes9) = 0x602D3D8160093D39F3
_PRE: constant(bytes10) = 0x363d3d373d3d3d363d73
_POST: constant(bytes15) = 0x5af43d82803e903d91602b57fd5bf3

vault_impl_addr: public(address)
payment_token_addr: immutable(address)
nft_contract_addr: immutable(address)
delegation_registry_addr: immutable(address)

active_vaults: public(HashMap[uint256, address]) # token_id -> vault


##### EXTERNAL METHODS - WRITE #####

@external
def __init__(
    vault_impl_addr: address,
    _payment_token_addr: address,
    _nft_contract_addr: address,
    _delegation_registry_addr: address
):
    self.vault_impl_addr = vault_impl_addr
    payment_token_addr = _payment_token_addr
    nft_contract_addr = _nft_contract_addr
    delegation_registry_addr = _delegation_registry_addr


@external
def create_vault_and_deposit(token_id: uint256, price: uint256, max_duration: uint256):
    assert self.active_vaults[token_id] == empty(address), "vault exists for token_id"

    vault: address = create_minimal_proxy_to(self.vault_impl_addr, salt=convert(token_id, bytes32))
    
    log VaultCreated(
        vault,
        msg.sender,
        nft_contract_addr,
        token_id
    )

    self.active_vaults[token_id] = vault

    IVault(vault).initialise(
        msg.sender,
        self,
        payment_token_addr,
        nft_contract_addr,
        delegation_registry_addr
    )
    IVault(vault).deposit(token_id, price, max_duration)

    log NFTDeposited(
        vault,
        msg.sender,
        nft_contract_addr,
        token_id,
        max_duration
    )


@external
def deposit(token_id: uint256, price: uint256, max_duration: uint256):
    assert ISelf(self).is_vault_available(token_id), "vault is not available"

    vault: address = ISelf(self).tokenid_to_vault(token_id)
    self.active_vaults[token_id] = vault
    
    IVault(vault).initialise(
        msg.sender,
        self,
        payment_token_addr,
        nft_contract_addr,
        delegation_registry_addr
    )

    IVault(vault).deposit(token_id, price, max_duration)

    log NFTDeposited(
        vault,
        msg.sender,
        nft_contract_addr,
        token_id,
        max_duration
    )


@external
def set_listing_price(token_id:uint256, price: uint256, max_duration: uint256):
    vault_address: address = self.active_vaults[token_id]
    assert vault_address != empty(address), "no vault exists for token_id"

    IVault(vault_address).set_listing_price(msg.sender, price, max_duration)

    log ListingPriceChanged(
        self.active_vaults[token_id],
        msg.sender,
        nft_contract_addr,
        token_id,
        price,
        max_duration
    )


@external
def cancel_listing(token_id: uint256):
    vault_address: address = self.active_vaults[token_id]
    assert vault_address != empty(address), "no vault exists for token_id"

    IVault(vault_address).set_listing_price(msg.sender, 0, 0)

    log ListingCancelled(
        self.active_vaults[token_id],
        msg.sender,
        nft_contract_addr,
        token_id
    )


@external
def start_rental(token_id: uint256, expiration: uint256):
    assert self.active_vaults[token_id] != empty(address), "no vault exists for token_id"

    rental: Rental = IVault(self.active_vaults[token_id]).start_rental(msg.sender, expiration)

    log RentalStarted(
        rental.id,
        self.active_vaults[token_id],
        rental.owner,
        msg.sender,
        nft_contract_addr,
        token_id,
        rental.start,
        expiration,
        rental.amount
    )


@external
def close_rental(token_id: uint256):
    assert self.active_vaults[token_id] != empty(address), "no vault exists for token_id"

    amount: uint256 = 0
    rental: Rental = empty(Rental)
    rental, amount = IVault(self.active_vaults[token_id]).close_rental(msg.sender)

    log RentalClosed(
        rental.id,
        self.active_vaults[token_id],
        rental.owner,
        msg.sender,
        nft_contract_addr,
        token_id,
        rental.start,
        block.timestamp,
        amount
    )


@external
def claim(token_id: uint256):
    assert self.active_vaults[token_id] != empty(address), "no vault exists for token_id"

    rewards: uint256 = IVault(self.active_vaults[token_id]).claim(msg.sender)

    log RewardsClaimed(
        self.active_vaults[token_id],
        msg.sender,
        nft_contract_addr,
        token_id,
        rewards
    )


@external
def withdraw(token_id: uint256):
    assert self.active_vaults[token_id] != empty(address), "no vault exists for token_id"

    vault: address = self.active_vaults[token_id]

    self.active_vaults[token_id] = empty(address)

    rewards: uint256 = IVault(vault).withdraw(msg.sender)

    log NFTWithdrawn(
        vault,
        msg.sender,
        nft_contract_addr,
        token_id,
        rewards
    )


##### INTERNAL METHODS #####

@pure
@internal
def _compute_address(salt: bytes32, bytecode_hash: bytes32, deployer: address) -> address:
    """
    @dev An `internal` helper function that returns the address
         where a contract will be stored if deployed via `deployer`
         using the `CREATE2` opcode. Any change in the `bytecode_hash`
         or `salt` values will result in a new destination address.
    @param salt The 32-byte random value used to create the contract
           address.
    @param bytecode_hash The 32-byte bytecode digest of the contract
           creation bytecode.
    @param deployer The 20-byte deployer address.
    @return address The 20-byte address where a contract will be stored.
    """
    data: bytes32 = keccak256(concat(_COLLISION_OFFSET, convert(deployer, bytes20), salt, bytecode_hash))
    return self._convert_keccak256_2_address(data)


@pure
@internal
def _convert_keccak256_2_address(digest: bytes32) -> address:
    """
    @dev Converts a 32-byte keccak256 digest to an address.
    @param digest The 32-byte keccak256 digest.
    @return address The converted 20-byte address.
    """
    return convert(convert(digest, uint256) & convert(max_value(uint160), uint256), address)


##### EXTERNAL METHODS - VIEW #####

@view
@external
def is_vault_available(token_id: uint256) -> bool:
    vault: address = ISelf(self).tokenid_to_vault(token_id)
    return self.active_vaults[token_id] == empty(address) and vault.is_contract and not IVault(vault).is_initialised()


@view
@external
def tokenid_to_vault(token_id: uint256) -> address:
    return self._compute_address(
        convert(token_id, bytes32),
        keccak256(concat(
            _DEPLOYMENT_CODE,
            _PRE,
            convert(self.vault_impl_addr, bytes20),
            _POST
        )),
        self
    )


@view
@external
def get_nft_contract() -> address:
    return nft_contract_addr


@view
@external
def get_payment_token() -> address:
    return payment_token_addr


@view
@external
def get_delegation_registry() -> address:
    return delegation_registry_addr
