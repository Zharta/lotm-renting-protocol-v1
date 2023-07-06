# @version 0.3.9

# Interfaces

interface IVault:
    def initialise(owner: address, caller: address, payment_token_addr: address, nft_contract_addr: address, delegation_registry_addr: address): nonpayable
    def deposit(token_id: uint256): nonpayable
    def create_listing(sender: address, price: uint256): nonpayable
    def change_listing_price(sender: address, price: uint256): nonpayable
    def cancel_listing(sender: address): nonpayable
    def start_rental(renter: address, expiration: uint256): nonpayable
    def close_rental(sender: address): nonpayable
    def claim(sender: address): nonpayable
    def withdraw(sender: address): nonpayable


# Structs


# Events


# Global Variables

_COLLISION_OFFSET: constant(bytes1) = 0xFF

vault_impl_addr: public(address)
payment_token_addr: public(address)
nft_contract_addr: public(address)
delegation_registry_addr: public(address)

active_vaults: public(HashMap[uint256, address]) # token_id -> vault
available_vaults: public(DynArray[address, 2**15]) # one vault per Koda


##### EXTERNAL METHODS - WRITE #####

@external
def __init__(
    vault_impl_addr: address,
    payment_token_addr: address,
    nft_contract_addr: address,
    delegation_registry_addr: address
):
    self.vault_impl_addr = vault_impl_addr
    self.payment_token_addr = payment_token_addr
    self.nft_contract_addr = nft_contract_addr
    self.delegation_registry_addr = delegation_registry_addr


@external
def create_vault_and_deposit(token_id: uint256):
    assert self.active_vaults[token_id] == empty(address), "vault exists for token_id"

    vault: address = create_minimal_proxy_to(self.vault_impl_addr, salt=convert(token_id, bytes32))
    
    self.active_vaults[token_id] = vault

    IVault(vault).initialise(
        msg.sender,
        self,
        self.payment_token_addr,
        self.nft_contract_addr,
        self.delegation_registry_addr
    )
    IVault(vault).deposit(token_id)


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
                self.payment_token_addr,
                self.nft_contract_addr,
                self.delegation_registry_addr
            )

    IVault(vault).deposit(token_id)


@external
def create_listing(token_id: uint256, price: uint256):
    assert self.active_vaults[token_id] != empty(address), "no vault exists for token_id"

    IVault(self.active_vaults[token_id]).create_listing(msg.sender, price)


@external
def change_listing_price(token_id:uint256, price: uint256):
    assert self.active_vaults[token_id] != empty(address), "no vault exists for token_id"

    IVault(self.active_vaults[token_id]).change_listing_price(msg.sender, price)


@external
def cancel_listing(token_id: uint256):
    assert self.active_vaults[token_id] != empty(address), "no vault exists for token_id"

    IVault(self.active_vaults[token_id]).cancel_listing(msg.sender)


@external
def start_rental(token_id: uint256, expiration: uint256):
    assert self.active_vaults[token_id] != empty(address), "no vault exists for token_id"

    IVault(self.active_vaults[token_id]).start_rental(msg.sender, expiration)


@external
def close_rental(token_id: uint256):
    assert self.active_vaults[token_id] != empty(address), "no vault exists for token_id"

    IVault(self.active_vaults[token_id]).close_rental(msg.sender)


@external
def claim(token_id: uint256):
    assert self.active_vaults[token_id] != empty(address), "no vault exists for token_id"

    IVault(self.active_vaults[token_id]).claim(msg.sender)


@external
def withdraw(token_id: uint256):
    assert self.active_vaults[token_id] != empty(address), "no vault exists for token_id"

    vault: address = self.active_vaults[token_id]
    
    self.available_vaults.append(vault)
    self.active_vaults[token_id] = empty(address)

    IVault(vault).withdraw(msg.sender)


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
