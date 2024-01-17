# @version 0.3.9

# Interfaces


# Structs

struct DelegateLock:
    locker: address
    expiration: uint256

struct StakeLock:
    locker: address
    amount: uint256
    expiration: uint256

struct StakeRewardLock:
    locker: address
    expiration: uint256

# Events

event AccessChanged:
    owner: address
    contract: address
    operations: uint256


event LockStatusChanged:
    lock: String[30]
    locked: bool
    locker: address
    expiration: uint256
    value: uint256

# Global Variables

PERMISSION_DELEGATE: constant(uint256) = shift(1, 0)
PERMISSION_STAKE_DEPOSIT: constant(uint256) = shift(1, 1)
PERMISSION_STAKE_WITHDRAW: constant(uint256) = shift(1, 2)
PERMISSION_STAKE_CLAIM: constant(uint256) = shift(1, 3)

PERMISSION_LOCK_DELEGATE: constant(uint256) = shift(1, 4)
PERMISSION_LOCK_WITHDRAWAL: constant(uint256) = shift(1, 5)
PERMISSION_LOCK_STAKE: constant(uint256) = shift(1, 6)
PERMISSION_LOCK_STAKING_REWARDS: constant(uint256) = shift(1, 7)



permissions: public(HashMap[address, HashMap[address, uint256]]) # owner -> contract -> bitmask

withdrawal_locks: public(HashMap[uint256, address]) # token_id -> locker address
delegation_locks: public(HashMap[uint256, DelegateLock]) # token_id -> lock
staking_locks: public(HashMap[uint256, StakeLock]) # token_id -> lock
staking_rewards_locks: public(HashMap[uint256, StakeRewardLock]) # token_id -> lock


# todo: set permissions per vault manager


##### EXTERNAL METHODS - WRITE #####

@external
def __init__():
    pass


@external
def set_permissions(_contract: address, _permissions_mask: uint256):
    """
    check msg.sender == owner
    set permission mask
    """

    log AccessChanged(msg.sender, _contract, _permissions_mask)

@external
def has_permission(_contract: address, _vault_owner: address, _permission: uint256) -> bool:
    return self.permissions[_vault_owner][_contract] & _permission != 0


@external
def set_withdrawal_lock(_token_id: uint256):
    """
    check msg.sender has PERMISSION_LOCK_WITHDRAWAL
    check not current lock exists
    set lock
    """

    log LockStatusChanged("WITHDRAWAL", True, msg.sender, 0, 0)


@external
def unset_withdrawal_lock(_token_id: uint256):
    """
    check for current lock with locker == msg.sender
    remove lock
    """

    log LockStatusChanged("WITHDRAWAL", False, msg.sender, 0, 0)


@external
def set_delegate_lock(_token_id: uint256, _expiration: uint256):
    """
    check msg.sender has PERMISSION_LOCK_DELEGATE
    check not current lock exists
    set lock
    """
    log LockStatusChanged("DELEGATE", True, msg.sender, _expiration, 0)

@external
def unset_delegate_lock(_token_id: uint256):
    """
    check for current lock with locker == msg.sender
    remove lock
    """
    log LockStatusChanged("DELEGATE", False, msg.sender, 0, 0)


@external
def set_staking_lock(_token_id: uint256, _expiration: uint256, amount: uint256):
    """
    check msg.sender has PERMISSION_LOCK_STAKE
    check not current lock exists
    set lock
    """
    log LockStatusChanged("STAKE", True, msg.sender, _expiration, amount)

@external
def unset_staking_lock(_token_id: uint256):
    """
    check for current lock with locker == msg.sender
    remove lock
    """
    log LockStatusChanged("STAKE", False, msg.sender, 0, 0)

@external
def set_staking_rewards_lock(_token_id: uint256, _expiration: uint256):
    """
    check msg.sender has PERMISSION_LOCK_STAKING_REWARDS
    check not current lock exists
    set lock
    """
    log LockStatusChanged("STAKING_REWARDS", True, msg.sender, _expiration, 0)

@external
def unset_staking_rewards_lock(_token_id: uint256):
    """
    check for current lock with locker == msg.sender
    remove lock
    """
    log LockStatusChanged("STAKING_REWARDS", False, msg.sender, 0, 0)
