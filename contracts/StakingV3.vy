# @version 0.3.10

# Interfaces

from vyper.interfaces import ERC20 as IERC20
from vyper.interfaces import ERC721 as IERC721


interface Renting:
    def consolidate_claims_and_approve(nft_owner: address, max_amount: uint256, token_contexts: DynArray[TokenContext, 32]) -> uint256: nonpayable
    def get_vaults(nft_owner: address, token_contexts: DynArray[TokenContext, 32]) -> DynArray[address, 32]: nonpayable


interface Vault:
    def initialise(staking_pool_id: uint256): nonpayable
    def deposit(token_id: uint256, nft_owner: address, delegate: address): nonpayable
    def withdraw(token_id: uint256, wallet: address): nonpayable
    def delegate_to_wallet(delegate: address, expiration: uint256): nonpayable
    def staking_deposit(sender: address, amount: uint256, token_id: uint256): nonpayable
    def staking_withdraw(wallet: address, amount: uint256, token_id: uint256): nonpayable
    def staking_claim(wallet: address, token_id: uint256): nonpayable
    def staking_compound(token_id: uint256): nonpayable

# Structs

struct Rental:
    id: bytes32 # keccak256 of the renter, token_id, start and expiration
    owner: address
    renter: address
    delegate: address
    token_id: uint256
    start: uint256
    min_expiration: uint256
    expiration: uint256
    amount: uint256
    protocol_fee: uint256

struct TokenContext:
    token_id: uint256
    nft_owner: address
    active_rental: Rental

# Events


struct StakingLog:
    token_id: uint256
    amount: uint256

event StakingDeposit:
    owner: address
    nft_contract: address
    staked_rewards: uint256
    tokens: DynArray[StakingLog, 32]

event StakingWithdraw:
    owner: address
    nft_contract: address
    recipient: address
    tokens: DynArray[StakingLog, 32]

event StakingClaim:
    owner: address
    nft_contract: address
    recipient: address
    tokens: DynArray[uint256, 32]

event StakingCompound:
    owner: address
    nft_contract: address
    tokens: DynArray[uint256, 32]


# Global Variables



renting: public(Renting)
payment_token: public(IERC20)
nft_contract_addr: public(address)

##### EXTERNAL METHODS - WRITE #####


@external
def __init__():
    pass


@external
def initialise(_payment_token: address, _nft_contract_addr: address):
    assert self.renting == empty(Renting), "already initialised"
    self.renting = Renting(msg.sender)
    self.payment_token = IERC20(_payment_token)
    self.nft_contract_addr = _nft_contract_addr




@external
def stake_deposit(
    staking_tokens: DynArray[TokenContext, 32],
    amounts: DynArray[uint256, 32],
    rental_tokens: DynArray[TokenContext, 32],
    stake_rewards: bool
):

    assert len(staking_tokens) == len(amounts), "length mismatch"
    staking_log: DynArray[StakingLog, 32] = empty(DynArray[StakingLog, 32])
    total_amount: uint256 = 0
    tokens_len: uint256 = len(staking_tokens)
    rewards_to_stake: uint256 = 0

    for amount in amounts:
        total_amount += amount

    if stake_rewards:
        rewards_to_stake = self.renting.consolidate_claims_and_approve(msg.sender, total_amount, rental_tokens)

    vaults: DynArray[address, 32] = self.renting.get_vaults(msg.sender, staking_tokens)

    assert self.payment_token.allowance(msg.sender, self) >= total_amount - rewards_to_stake, "insufficient allowance"

    rewards_remaining: uint256 = rewards_to_stake
    for i in range(len(staking_tokens), bound=32):
        if rewards_remaining == 0:
            assert self.payment_token.transferFrom(msg.sender, vaults[i], amounts[i]), "transferFrom failed"
        elif rewards_remaining >= amounts[i]:
            assert self.payment_token.transferFrom(self.renting.address, vaults[i], amounts[i]), "transferFrom failed"
            rewards_remaining -= amounts[i]
        else:
            assert self.payment_token.transferFrom(self.renting.address, vaults[i], rewards_remaining), "transferFrom failed"
            assert self.payment_token.transferFrom(msg.sender, vaults[i], amounts[i] - rewards_remaining), "transferFrom failed"
            rewards_remaining = 0

        Vault(vaults[i]).staking_deposit(msg.sender, amounts[i], staking_tokens[i].token_id)
        staking_log.append(StakingLog({
            token_id: staking_tokens[i].token_id,
            amount: amounts[i]
        }))

    log StakingDeposit(msg.sender, self.nft_contract_addr, rewards_to_stake, staking_log)


@external
def stake_withdraw(token_contexts: DynArray[TokenContext, 32], amounts: DynArray[uint256, 32], recipient: address):
    assert len(token_contexts) == len(amounts), "length mismatch"
    staking_log: DynArray[StakingLog, 32] = empty(DynArray[StakingLog, 32])

    vaults: DynArray[address, 32] = self.renting.get_vaults(msg.sender, token_contexts)

    for i in range(len(token_contexts), bound=32):
        Vault(vaults[i]).staking_withdraw(recipient, amounts[i], token_contexts[i].token_id)
        staking_log.append(StakingLog({
            token_id: token_contexts[i].token_id,
            amount: amounts[i]
        }))

    log StakingWithdraw(msg.sender, self.nft_contract_addr, recipient, staking_log)


@external
def stake_claim(token_contexts: DynArray[TokenContext, 32], recipient: address):
    tokens: DynArray[uint256, 32] = empty(DynArray[uint256, 32])

    vaults: DynArray[address, 32] = self.renting.get_vaults(msg.sender, token_contexts)

    for i in range(len(token_contexts), bound=32):
        Vault(vaults[i]).staking_claim(recipient, token_contexts[i].token_id)
        tokens.append(token_contexts[i].token_id)

    log StakingClaim(msg.sender, self.nft_contract_addr, recipient, tokens)

@external
def stake_compound(token_contexts: DynArray[TokenContext, 32]):

    tokens: DynArray[uint256, 32] = empty(DynArray[uint256, 32])

    vaults: DynArray[address, 32] = self.renting.get_vaults(msg.sender, token_contexts)

    for i in range(len(token_contexts), bound=32):
        Vault(vaults[i]).staking_compound(token_contexts[i].token_id)
        tokens.append(token_contexts[i].token_id)

    log StakingCompound(msg.sender, self.nft_contract_addr, tokens)
