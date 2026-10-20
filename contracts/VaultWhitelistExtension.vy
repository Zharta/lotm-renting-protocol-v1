# @version 0.4.1

"""
@title Zharta Vault Whitelist Extension
@author [Zharta](https://zharta.io/)
@notice Whitelist extension for the LimitBreak Creator Token Transfer Validator that allows Zharta renting vaults to return the NFTs they hold, for collections whose transfers are gated by a whitelist ruleset. It only enables withdrawals: a vault is whitelisted only while it owns its token, so deposits into vaults remain blocked.
@dev Implements `IWhitelistExtension.isWhitelisted(collection, account)`, which the validator queries for accounts not whitelisted by address or codehash. Vaults are minimal proxies (EIP-1167) deployed by the renting contract with CREATE2, using the token id as salt, so a vault address can only hold a vault deployed by the renting contract. As the validator doesn't provide the token id, vaults must be registered beforehand: anyone can register the vaults of a renting contract for a set of token ids, as their addresses are provided by the renting contract (`tokenid_to_vault`). The code and storage of an account are not used to identify vaults, as other contracts can replicate both.
A registered vault is whitelisted only while it owns its token, which holds during a withdrawal (the validator runs before the transfer) but not during a deposit. The whitelisting applies to the account, for any transfer validated meanwhile, but the renting protocol can only make a vault transfer its own token.
The validator calls extensions without try/catch for every collection sharing the list, so `isWhitelisted` must never revert. Markets are immutable and the contract has no owner.
"""


# Interfaces

interface IRenting:
    def nft_contract_addr() -> address: view
    def tokenid_to_vault(token_id: uint256) -> address: view


# Structs

struct Market:
    collection: address
    renting: address

struct Vault:
    market_id: uint256 # market index + 1, 0 if not registered
    token_id: uint256


# Events

event VaultRegistered:
    vault: indexed(address)
    renting: indexed(address)
    token_id: uint256


# Global Variables

MAX_MARKETS: constant(uint256) = 16
MAX_TOKENS: constant(uint256) = 128
OWNER_OF_GAS: public(constant(uint256)) = 100000

markets: public(immutable(DynArray[Market, MAX_MARKETS]))
vaults: public(HashMap[address, Vault])


##### EXTERNAL METHODS - WRITE #####

@deploy
def __init__(_rentings: DynArray[address, MAX_MARKETS]):

    """
    @dev Sets up the markets, reading the NFT collection of each renting contract.
    @param _rentings The renting contracts (V2 or V3) of the markets.
    """

    assert len(_rentings) > 0, "no markets"

    new_markets: DynArray[Market, MAX_MARKETS] = []
    for renting: address in _rentings:
        assert renting.is_contract, "renting not a contract"
        new_markets.append(Market({collection: staticcall IRenting(renting).nft_contract_addr(), renting: renting}))

    markets = new_markets


@external
def register_vaults(renting: address, token_ids: DynArray[uint256, MAX_TOKENS]):

    """
    @notice Register the vaults of a renting contract for the given token ids, whether they are already deployed or not.
    @dev Permissionless, as the vault addresses are provided by the renting contract. Registering a vault again has no effect.
    @param renting The address of the renting contract of the market.
    @param token_ids The ids of the tokens whose vaults are registered.
    """

    market_id: uint256 = self._market_id(renting)
    assert market_id != 0, "unknown renting"

    for token_id: uint256 in token_ids:
        vault: address = staticcall IRenting(renting).tokenid_to_vault(token_id)
        self.vaults[vault] = Vault({market_id: market_id, token_id: token_id})
        log VaultRegistered(vault, renting, token_id)


##### EXTERNAL METHODS - VIEW #####

@view
@external
def isWhitelisted(collection: address, account: address) -> bool:

    """
    @notice Check if an account is a registered Zharta vault for the given collection, currently owning its token.
    @dev Called by the validator. Never reverts.
    @param collection The address of the collection whose transfer is being validated.
    @param account The address being checked by the validator.
    @return True if the account is a registered vault of a market for the collection and owns its token, False otherwise.
    """

    market_id: uint256 = self.vaults[account].market_id
    if market_id == 0:
        return False
    if markets[market_id - 1].collection != collection:
        return False
    return self._owner_of(collection, self.vaults[account].token_id) == convert(account, bytes32)


##### INTERNAL METHODS #####

@view
@internal
def _market_id(renting: address) -> uint256:
    for i: uint256 in range(MAX_MARKETS):
        if i >= len(markets):
            break
        if markets[i].renting == renting:
            return i + 1
    return 0


@view
@internal
def _owner_of(collection: address, token_id: uint256) -> bytes32:
    # returns the raw `ownerOf` word, or empty if the call fails or doesn't return exactly one word
    success: bool = False
    response: Bytes[64] = b""
    success, response = raw_call(
        collection,
        abi_encode(token_id, method_id=method_id("ownerOf(uint256)")),
        max_outsize=64,
        gas=OWNER_OF_GAS,
        is_static_call=True,
        revert_on_failure=False,
    )
    if not success or len(response) != 32:
        return empty(bytes32)
    return extract32(response, 0)
