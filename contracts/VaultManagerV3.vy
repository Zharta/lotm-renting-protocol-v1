# @version 0.3.9

# Interfaces

interface ISelf:
    def tokenid_to_vault(token_id: uint256) -> address: view
    def is_vault_available(token_id: uint256) -> bool: view


interface IVault:
    def is_initialised() -> bool: view
    def initialise(owner: address): nonpayable
    def deposit(token_id: uint256, delegate: address): nonpayable
    def withdraw(sender: address) -> (uint256, uint256): nonpayable
    def delegate_to_wallet(sender: address, delegate: address, expiration: uint256): nonpayable
    def stake_deposit(sender: address, amount: uint256): nonpayable
    def stake_withdraw(sender: address, recepient: address, amount: uint256): nonpayable
    def stake_claim(sender: address, recepient: address): nonpayable


# Structs

struct VaultLog:
    vault: address
    token_id: uint256

struct WithdrawalLog:
    vault: address
    token_id: uint256

# Events

event VaultsCreated:
    owner: address
    nft_contract: address
    vaults: DynArray[VaultLog, 32]
    delegate: address

event NftsDeposited:
    owner: address
    nft_contract: address
    vaults: DynArray[VaultLog, 32]
    delegate: address

event NftsWithdrawn:
    owner: address
    nft_contract: address
    total_rewards: uint256
    withdrawals: DynArray[WithdrawalLog, 32]

event DelegatedToWallet:
    owner: address
    delegate: address
    nft_contract: address
    vaults: DynArray[VaultLog, 32]


# Global Variables

_COLLISION_OFFSET: constant(bytes1) = 0xFF
_DEPLOYMENT_CODE: constant(bytes9) = 0x602D3D8160093D39F3
_PRE: constant(bytes10) = 0x363d3d373d3d3d363d73
_POST: constant(bytes15) = 0x5af43d82803e903d91602b57fd5bf3

vault_impl_addr: public(immutable(address))
payment_token_addr: public(immutable(address))
nft_contract_addr: public(immutable(address))
delegation_registry_addr: public(immutable(address))
registry_addr: public(immutable(address))

active_vaults: public(HashMap[uint256, address]) # token_id -> vault

id_to_owner: HashMap[uint256, address]
id_to_approvals: HashMap[uint256, address]
id_to_token_count: HashMap[address, uint256]
ownerToOperators: HashMap[address, HashMap[address, bool]]

SUPPORTED_INTERFACES: constant(bytes4[2]) = [0x01ffc9a7, 0x80ac58cd] # ERC165, ERC721

##### EXTERNAL METHODS - WRITE #####

@external
def __init__(
    _vault_impl_addr: address,
    _payment_token_addr: address,
    _nft_contract_addr: address,
    _delegation_registry_addr: address,
    _registry_addr: address,
):

    assert _vault_impl_addr != empty(address), "vault impl is the zero addr"
    assert _payment_token_addr != empty(address), "payment token is the zero addr"
    assert _nft_contract_addr != empty(address), "nft contract is the zero addr"
    assert _delegation_registry_addr != empty(address), "deleg registry is the zero addr"
    assert _registry_addr != empty(address), "registry is the zero addr"

    vault_impl_addr = _vault_impl_addr
    payment_token_addr = _payment_token_addr
    nft_contract_addr = _nft_contract_addr
    delegation_registry_addr = _delegation_registry_addr
    registry_addr = _registry_addr


@external
def create_vaults_and_deposit(token_ids: DynArray[uint256, 32], delegate: address):
    """
    create vault
    call vault deposit
    set vault ownership

    log VaultsCreated(msg.sender, nft_contract_addr, vault_logs, delegate)
    """


@external
def deposit(token_ids: DynArray[uint256, 32], delegate: address):
    """
    Q: should this be merged with create_vaults_and_deposit?
    call vault deposit
    set vault ownership

    log NftsDeposited(msg.sender, nft_contract_addr, vault_logs, delegate)
    """


@external
def withdraw(token_contexts: DynArray[uint256, 32]):
    """
    check if msg.sender is owner or has permission
    check if not withdrawal lock exists
    call vault withdraw
    remove vault ownership

    log NftsWithdrawn(msg.sender, nft_contract_addr, withdrawal_log)
    """


@external
def delegate_to_wallet(token_contexts: DynArray[uint256, 32], delegate: address):
    """
    check if msg.sender is owner or has permission
    check if no delegation lock exists
    call vault withdraw

    log DelegatedToWallet(msg.sender, delegate, nft_contract_addr, vaults)
    """


@external
def stake_deposit(token_id: uint256, amount: uint256):
    """
    check if msg.sender is owner or has permission
    call vault stake_deposit
    """

@external
def stake_withdraw(token_id: uint256, recepient: address, amount: uint256):
    """
    check if msg.sender is owner or has permission
    check if stacked_amount - locked_amount >= amount
    call vault stake_withdraw
    """

@external
def stake_claim(token_id: uint256, recepient: address):
    """
    check if msg.sender is owner or has permission
    check if not stake claims lock exists
    call vault stake_claim
    """

@external
def stake_compound(token_id: uint256):
    """
    check if msg.sender is owner
    check if pool limit is not exceeded
    call vault stake_claim and stake_deposit
    """

@view
@external
def is_vault_available(token_id: uint256) -> bool:
    return False


@view
@external
def tokenid_to_vault(token_id: uint256) -> address:
    return empty(address)


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

@view
@external
def get_registry() -> address:
    return registry_addr


## ERC721 Methods
