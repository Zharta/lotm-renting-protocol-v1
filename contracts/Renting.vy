# @version 0.3.9

# Interfaces

interface IVault:
    def initialise(owner: address, caller: address, payment_token_addr: address, nft_contract_addr: address, delegation_registry_addr: address): nonpayable
    def deposit(token_id: uint256): nonpayable
    def create_listing(sender: address, price: uint256): nonpayable
    def change_listing_price(sender: address, price: uint256): nonpayable
    def cancel_listing(sender: address): nonpayable
    def start_rental(renter: address, expiration: uint256) -> Rental: nonpayable
    def close_rental(sender: address) -> Rental: nonpayable
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

event NFTWithdrawn:
    vault: address
    owner: address
    nft_contract: address
    token_id: uint256
    claimed_rewards: uint256

event ListingCreated:
    vault: address
    owner: address
    nft_contract: address
    token_id: uint256
    price: uint256

event ListingPriceChanged:
    vault: address
    owner: address
    nft_contract: address
    token_id: uint256
    price: uint256

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

event RentalClosedPrematurely:
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

vault_impl_addr: public(address)
payment_token_addr: immutable(address)
nft_contract_addr: immutable(address)
delegation_registry_addr: immutable(address)

active_vaults: public(HashMap[uint256, address]) # token_id -> vault
available_vaults: public(DynArray[address, 2**15]) # one vault per Koda


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
def create_vault_and_deposit(token_id: uint256):
    assert self.active_vaults[token_id] == empty(address), "vault exists for token_id"
    assert len(self.available_vaults) == 0, "no available vaults"

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
    IVault(vault).deposit(token_id)

    log NFTDeposited(
        vault,
        msg.sender,
        nft_contract_addr,
        token_id
    )


@external
def deposit(token_id: uint256):    
    vault: address = self.active_vaults[token_id]
    
    if vault == empty(address):
        if len(self.available_vaults) == 0:
            raise "no available vaults"
        else:
            vault = self.available_vaults.pop()
            self.active_vaults[token_id] = vault
            
            IVault(vault).initialise(
                msg.sender,
                self,
                payment_token_addr,
                nft_contract_addr,
                delegation_registry_addr
            )

    IVault(vault).deposit(token_id)

    log NFTDeposited(
        vault,
        msg.sender,
        nft_contract_addr,
        token_id
    )


@external
def create_listing(token_id: uint256, price: uint256):
    assert self.active_vaults[token_id] != empty(address), "no vault exists for token_id"

    IVault(self.active_vaults[token_id]).create_listing(msg.sender, price)

    log ListingCreated(
        self.active_vaults[token_id],
        msg.sender,
        nft_contract_addr,
        token_id,
        price
    )


@external
def change_listing_price(token_id:uint256, price: uint256):
    assert self.active_vaults[token_id] != empty(address), "no vault exists for token_id"

    IVault(self.active_vaults[token_id]).change_listing_price(msg.sender, price)

    log ListingPriceChanged(
        self.active_vaults[token_id],
        msg.sender,
        nft_contract_addr,
        token_id,
        price
    )


@external
def cancel_listing(token_id: uint256):
    assert self.active_vaults[token_id] != empty(address), "no vault exists for token_id"

    IVault(self.active_vaults[token_id]).cancel_listing(msg.sender)

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

    rental: Rental = IVault(self.active_vaults[token_id]).close_rental(msg.sender)

    log RentalClosedPrematurely(
        rental.id,
        self.active_vaults[token_id],
        rental.owner,
        msg.sender,
        nft_contract_addr,
        token_id,
        rental.start,
        block.timestamp,
        rental.amount
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
    
    self.available_vaults.append(vault)
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

@internal
@pure
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


@internal
@pure
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
def get_vault_to_approve(token_id: uint256) -> address:
    if self.active_vaults[token_id] != empty(address):
        return self.active_vaults[token_id]
    elif len(self.available_vaults) > 0:
        return self.available_vaults[len(self.available_vaults) - 1]
    else:
        deployment_code: bytes9 = 0x602D3D8160093D39F3
        pre: bytes10 = 0x363d3d373d3d3d363d73
        post: bytes15 = 0x5af43d82803e903d91602b57fd5bf3
        return self._compute_address(
            convert(token_id, bytes32),
            keccak256(concat(
                deployment_code,
                pre,
                convert(self.vault_impl_addr, bytes20),
                post
            )),
            self
        )


@view
@external
def get_available_vaults() -> DynArray[address, 2**15]:
    return self.available_vaults


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
