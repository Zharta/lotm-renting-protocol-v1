# @version 0.4.0

"""
@title Zharta RentingERC721 Contract
@author [Zharta](https://zharta.io/)
@notice This contract wraps renting vaults with deposited NFTs, exposing them as ERC721 tokens.
@dev This contract is a ERC721 implementation representing the NFTs deposited in the renting vaults. Tokens are minted and burned by the renting contract, and can be transferred by the owner or approved operators. The contract can be used with any ERC721 compatible wallet or marketplace.
Tokens are minted when the underlying NFTs are deposited in the renting vaults, and burned when the NFTs are withdrawn. The contract is initialised with the renting contract address, and only the renting contract can mint and burn tokens.
The ownership can be transferred while rentals are ongoing, althought ownership change does not automatically changes the permissions to manage rentals (set listings, claim rewards). Renting permissions can be claimed the owner by calling the `claim_token_ownership` in the `RentingV3.vy` contract.
"""

# Interfaces


interface ERC721Receiver:
    def onERC721Received(_operator: address, _from: address, _tokenId: uint256, _data: Bytes[1024]) -> bytes4: view

# Structs

struct TokenAndWallet:
    token_id: uint256
    wallet: address

# Events


event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    tokenId: indexed(uint256)

event Approval:
    owner: indexed(address)
    approved: indexed(address)
    tokenId: indexed(uint256)

event ApprovalForAll:
    owner: indexed(address)
    operator: indexed(address)
    approved: bool

# Global Variables
SUPPORTED_INTERFACES: constant(bytes4[3]) = [0x01ffc9a7, 0x80ac58cd, 0x5b5e139f] # ERC165, ERC721, ERC721Metadata

name: public(immutable(String[30]))
symbol: public(immutable(String[20]))

base_url: immutable(String[60])

contractURI: public(immutable(String[60]))

id_to_owner: HashMap[uint256, address]
id_to_approvals: HashMap[uint256, address]
owner_to_operators: HashMap[address, HashMap[address, bool]]
owner_to_nft_count: HashMap[address, uint256]

renting_addr: public(address)

##### EXTERNAL METHODS - WRITE #####


@deploy
def __init__(_name: String[30], _symbol: String[20], _base_url: String[60], _contract_uri: String[60]):

    """
    @notice Initialises the contract with the renting contract address.
    @param _name Name of the collection.
    @param _symbol Symbol of the collection.
    @param _base_url Base URL for the token URIs.
    @param _contract_uri URI for the contract metadata.
    """

    name = _name
    symbol = _symbol
    base_url = _base_url
    contractURI = _contract_uri


@external
def initialise():

    """
    @notice Initialises the contract with the renting contract address.
    @dev This method can only be called once, and sets the renting contract address.
    """

    assert self.renting_addr == empty(address), "already initialised"
    self.renting_addr = msg.sender


@external
def mint(tokens: DynArray[TokenAndWallet, 32]):

    """
    @notice Mints tokens for the given NFTs.
    @dev This method can only be called by the renting contract, and mints tokens wrapping the given NFTs to the given wallets.
    @param tokens Array of TokenAndWallet structs, containing the token id and the wallet address.
    """

    assert msg.sender == self.renting_addr, "not renting contract"

    for token: TokenAndWallet in tokens:
        assert self.id_to_owner[token.token_id] == empty(address), "token already minted"
        self._mint_token_to(token.wallet, token.token_id)
        log Transfer(empty(address), token.wallet, token.token_id)


@external
def burn(tokens: DynArray[TokenAndWallet, 32]):

    """
    @notice Burns tokens for the given NFTs.
    @dev This method can only be called by the renting contract, and burns tokens wrapping the given NFTs from the given wallets.
    @param tokens Array of TokenAndWallet structs, containing the token id and the wallet address.
    """

    assert msg.sender == self.renting_addr, "not renting contract"

    for token: TokenAndWallet in tokens:
        if self.id_to_owner[token.token_id] == token.wallet:
            self._burn_token_from(token.wallet, token.token_id)


@view
@external
def balanceOf(_owner: address) -> uint256:

    """
    @notice Returns the number of NFTs owned by the given address.
    @dev This method returns the number of NFTs owned by the given address.
    @param _owner Address for which to query the balance.
    @return uint256 Number of NFTs owned by the given address.
    """

    assert _owner != empty(address)
    return self.owner_to_nft_count[_owner]


@view
@external
def ownerOf(_tokenId: uint256) -> address:

    """
    @notice Returns the owner of the given NFT.
    @dev This method returns the owner of the given NFT. Reverts if the NFT does not exist.
    @param _tokenId ID of the NFT to query the owner of.
    @return address Address of the owner of the NFT.
    """

    owner: address = self.id_to_owner[_tokenId]
    assert owner != empty(address)
    return owner


@view
@external
def owner_of(_tokenId: uint256) -> address:

    """
    @notice Returns the owner of the given NFT.
    @dev This method returns the owner of the given NFT. Contrary to the ERC721 equivalent, does not revert if the NFT does not exist.
    @param _tokenId ID of the NFT to query the owner of.
    @return address Address of the owner of the NFT.
    """

    return self.id_to_owner[_tokenId]


@view
@external
def getApproved(_tokenId: uint256) -> address:

    """
    @notice Returns the approved address for the given NFT.
    @dev This method returns the approved address for the given NFT, if any. Reverts if the NFT does not exist.
    @param _tokenId ID of the NFT to query the approval of.
    @return address Address of the approved address for the NFT.
    """

    assert self.id_to_owner[_tokenId] != empty(address)
    return self.id_to_approvals[_tokenId]


@view
@external
def isApprovedForAll(_owner: address, _operator: address) -> bool:

    """
    @notice Returns if the given operator is approved to manage all NFTs of the given owner.
    @dev This method returns if the given operator is approved to manage all NFTs of the given owner.
    @param _owner Address of the owner to query for.
    @param _operator Address of the operator to query for.
    @return bool True if the operator is approved to manage all NFTs of the given owner, false otherwise.
    """

    return self.owner_to_operators[_owner][_operator]


@external
def transferFrom(_from: address, _to: address, _tokenId: uint256):

    """
    @notice Transfers the ownership of the given NFT to the given address.
    @dev This method transfers the ownership of the given NFT to the given address. Reverts if the sender is not the owner, the NFT does not exist, or the sender is not approved to transfer the NFT.
    @param _from Address of the current owner of the NFT.
    @param _to Address of the new owner of the NFT.
    @param _tokenId ID of the NFT to transfer.
    """

    self._transfer_from(_from, _to, _tokenId, msg.sender)


@external
def safeTransferFrom(_from: address, _to: address, _tokenId: uint256, _data: Bytes[1024]=b""):

    """
    @notice Safely transfers the ownership of the given NFT to the given address.
    @dev This method safely transfers the ownership of the given NFT to the given address. Reverts if the sender is not the owner, the NFT does not exist, or the sender is not approved to transfer the NFT. If the receiver is a contract, it must implement the ERC721Receiver interface.
    @param _from Address of the current owner of the NFT.
    @param _to Address of the new owner of the NFT.
    @param _tokenId ID of the NFT to transfer.
    @param _data Additional data with no specified format, sent in call to `_to`.
    """

    self._transfer_from(_from, _to, _tokenId, msg.sender)
    if _to.is_contract:
        returnValue: bytes4 = staticcall ERC721Receiver(_to).onERC721Received(msg.sender, _from, _tokenId, _data)
        assert returnValue == convert(method_id("onERC721Received(address,address,uint256,bytes)", output_type=Bytes[4]), bytes4)


@external
def approve(_approved: address, _tokenId: uint256):

    """
    @notice Approves the given address to manage the given NFT.
    @dev This method approves the given address to manage the given NFT. Reverts if the sender is not the owner of the NFT.
    @param _approved Address to approve for the given NFT.
    @param _tokenId ID of the NFT to approve.
    """

    owner: address = self.id_to_owner[_tokenId]
    assert owner != empty(address)
    assert _approved != owner
    assert (self.id_to_owner[_tokenId] == msg.sender or self.owner_to_operators[owner][msg.sender])
    self.id_to_approvals[_tokenId] = _approved
    log Approval(owner, _approved, _tokenId)


@external
def setApprovalForAll(_operator: address, _approved: bool):

    """
    @notice Approves or revokes the given operator to manage all NFTs of the sender.
    @dev This method approves or revokes the given operator to manage all NFTs of the sender.
    @param _operator Address to approve or revoke for all NFTs of the sender.
    @param _approved True to approve, false to revoke.
    """

    assert _operator != msg.sender
    self.owner_to_operators[msg.sender][_operator] = _approved
    log ApprovalForAll(msg.sender, _operator, _approved)


@view
@external
def tokenURI(tokenId: uint256) -> String[138]:

    """
    @notice Returns the URI for the given token.
    @dev This method returns the URI for the given token. Reverts if the token does not exist.
    @param tokenId ID of the token to query the URI of.
    @return String[] URI for the given token.
    """

    return concat(base_url, uint2str(tokenId))


@pure
@external
def supportsInterface(interface_id: bytes4) -> bool:
    """
    @notice Check if the contract supports the given interface, as defined in ERC-165
    @dev Checks if the contract supports the given interface and returns true if it does.
    @param interface_id The interface id.
    @return True if the contract supports the given interface.
    """
    return interface_id in SUPPORTED_INTERFACES


@view
@internal
def _is_approved_or_owner(_spender: address, _token_id: uint256) -> bool:
    owner: address = self.id_to_owner[_token_id]
    return _spender == owner or _spender == self.id_to_approvals[_token_id] or self.owner_to_operators[owner][_spender]


@internal
def _mint_token_to(_to: address, _token_id: uint256):
    self._add_token_to(_to, _token_id)


@internal
def _burn_token_from(_owner: address, _token_id: uint256):
    self._remove_token_from(_owner, _token_id)
    log Transfer(_owner, empty(address), _token_id)


@internal
def _add_token_to(_to: address, _token_id: uint256):
    self.id_to_owner[_token_id] = _to
    self.owner_to_nft_count[_to] += 1


@internal
def _remove_token_from(_from: address, _token_id: uint256):
    self.id_to_owner[_token_id] = empty(address)
    self.owner_to_nft_count[_from] -= 1
    self._clear_approval(_from, _token_id)


@internal
def _clear_approval(_owner: address, _token_id: uint256):
    if self.id_to_approvals[_token_id] != empty(address):
        self.id_to_approvals[_token_id] = empty(address)


@internal
def _transfer_from(_from: address, _to: address, _token_id: uint256, _sender: address):
    assert self.id_to_owner[_token_id] == _from, "not owner"
    assert self._is_approved_or_owner(_sender, _token_id), "not approved or owner"
    assert _to != empty(address)
    self._clear_approval(_from, _token_id)
    self.id_to_owner[_token_id] = _to
    self.owner_to_nft_count[_from] -= 1
    self.owner_to_nft_count[_to] += 1
    log Transfer(_from, _to, _token_id)
