# @version 0.3.10

from vyper.interfaces import ERC20 as IERC20
from vyper.interfaces import ERC721 as IERC721

struct SingleNft:
    tokenId: uint32
    amount: uint224

event Deposit:
    user: address
    amount: uint256
    recipient: address

event DepositNft:
    user: address
    poolId: uint256
    amount: uint256
    tokenId: uint256

event Withdraw:
    user: address
    amount: uint256
    recipient: address

event WithdrawNft:
    user: address
    poolId: uint256
    amount: uint256
    recipient: address
    tokenId: uint256

event ClaimRewards:
    user: address
    amount: uint256
    recipient: address

event ClaimRewardsNft:
    user: address
    poolId: uint256
    amount: uint256
    tokenId: uint256

MIN_DEPOSIT: constant(uint256) = 10**18
BAYC_POOL: constant(uint256) = 1
MAYC_POOL: constant(uint256) = 2

ape_coin: public(immutable(IERC20))
bayc: public(immutable(IERC721))
mayc: public(immutable(IERC721))

staked_ape: public(HashMap[address, uint256])
staked_nfts: public(HashMap[uint256, HashMap[uint256, uint256]])

@external
def __init__(_ape_coin: address, _bayc: address, _mayc: address):
    ape_coin = IERC20(_ape_coin)
    bayc = IERC721(_bayc)
    mayc = IERC721(_mayc)

@external
def depositApeCoin(amount: uint256, recipient: address):
    assert amount >= MIN_DEPOSIT, "min deposit 1 ape"
    self.staked_ape[msg.sender] += amount
    ape_coin.transferFrom(msg.sender, self, amount)
    log Deposit(msg.sender, amount, recipient)

@external
def depositBAYC(nfts: DynArray[SingleNft,1]):
    assert len(nfts) == 1, "only 1 nft"
    amount: uint256 = convert(nfts[0].amount, uint256)
    token_id: uint256 = convert(nfts[0].tokenId, uint256)

    assert amount >= MIN_DEPOSIT, "min deposit 1 ape"
    assert bayc.ownerOf(token_id) == msg.sender, "not owner"
    self.staked_nfts[BAYC_POOL][token_id] += amount
    ape_coin.transferFrom(msg.sender, self, amount)
    log DepositNft(msg.sender, BAYC_POOL, amount, token_id)

@external
def depositMAYC(nfts: DynArray[SingleNft,1]):
    assert len(nfts) == 1, "only 1 nft"
    amount: uint256 = convert(nfts[0].amount, uint256)
    token_id: uint256 = convert(nfts[0].tokenId, uint256)

    assert amount >= MIN_DEPOSIT, "min deposit 1 ape"
    assert mayc.ownerOf(token_id) == msg.sender, "not owner"
    self.staked_nfts[MAYC_POOL][token_id] += amount
    ape_coin.transferFrom(msg.sender, self, amount)
    log DepositNft(msg.sender, MAYC_POOL, amount, token_id)

@external
def withdrawApeCoin(amount: uint256, recipient: address):
    assert self.staked_ape[msg.sender] >= amount, "not enough staked"
    self.staked_ape[msg.sender] -= amount
    ape_coin.transfer(recipient, amount)
    log Withdraw(msg.sender, amount, recipient)

@external
def withdrawBAYC(nfts: DynArray[SingleNft,1], recipient: address):
    amount: uint256 = convert(nfts[0].amount, uint256)
    token_id: uint256 = convert(nfts[0].tokenId, uint256)
    assert self.staked_nfts[BAYC_POOL][token_id] >= amount, "not enough staked"
    self.staked_nfts[BAYC_POOL][token_id] -= amount
    ape_coin.transfer(recipient, amount)
    log WithdrawNft(msg.sender, BAYC_POOL, amount, recipient, token_id)

@external
def withdrawMAYC(nfts: DynArray[SingleNft,1], recipient: address):
    amount: uint256 = convert(nfts[0].amount, uint256)
    token_id: uint256 = convert(nfts[0].tokenId, uint256)
    assert self.staked_nfts[MAYC_POOL][token_id] >= amount, "not enough staked"
    self.staked_nfts[MAYC_POOL][token_id] -= amount
    ape_coin.transfer(recipient, amount)
    log WithdrawNft(msg.sender, MAYC_POOL, amount, recipient, token_id)

@external
def claimApeCoin(recipient: address):
    assert self.staked_ape[msg.sender] > 0, "nothing to claim"
    amount: uint256 = self.staked_ape[msg.sender] / 100
    ape_coin.transfer(recipient, amount)
    log ClaimRewards(msg.sender, amount, recipient)

@external
def claimBAYC(nfts: DynArray[uint256,1], recipient: address):
    assert self.staked_nfts[BAYC_POOL][nfts[0]] > 0, "nothing to claim"
    assert bayc.ownerOf(nfts[0]) == msg.sender, "not owner"

    amount: uint256 = self.staked_nfts[BAYC_POOL][nfts[0]] / 100
    ape_coin.transfer(recipient, amount)
    log ClaimRewardsNft(msg.sender, BAYC_POOL, amount, nfts[0])

@external
def claimMAYC(nfts: DynArray[uint256,1], recipient: address):
    assert self.staked_nfts[MAYC_POOL][nfts[0]] > 0, "nothing to claim"
    assert mayc.ownerOf(nfts[0]) == msg.sender, "not owner"

    amount: uint256 = self.staked_nfts[MAYC_POOL][nfts[0]] / 100
    ape_coin.transfer(recipient, amount)
    log ClaimRewardsNft(msg.sender, MAYC_POOL, amount, nfts[0])
