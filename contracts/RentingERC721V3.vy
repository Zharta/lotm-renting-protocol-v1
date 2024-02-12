# @version 0.3.10

# Interfaces

from vyper.interfaces import ERC20 as IERC20
from vyper.interfaces import ERC721 as IERC721


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


SUPPORTED_INTERFACES: constant(bytes4[2]) = [0x01ffc9a7, 0x80ac58cd] # ERC165, ERC721

# TODO: should we add name, symbol and tokenURI? can be useful if we want to create a proper NFT
name: constant(String[10]) = ""
symbol: constant(String[4]) = ""

id_to_owner: HashMap[uint256, address]
id_to_approvals: HashMap[uint256, address]
owner_to_operators: HashMap[address, HashMap[address, bool]]
owner_to_nft_count: HashMap[address, uint256]

renting_addr: public(address)

##### EXTERNAL METHODS - WRITE #####


@external
def __init__():
    pass


@external
def initialise():
    assert self.renting_addr == empty(address), "already initialised"
    self.renting_addr = msg.sender


@external
def mint(tokens: DynArray[TokenAndWallet, 32]):
    assert msg.sender == self.renting_addr, "not renting contract"

    for token in tokens:
        assert self.id_to_owner[token.token_id] == empty(address), "token already minted"
        # TODO check if deposited
        self._mint_token_to(token.wallet, token.token_id)
        log Transfer(empty(address), token.wallet, token.token_id)


@external
def burn(tokens: DynArray[TokenAndWallet, 32]):
    assert msg.sender == self.renting_addr, "not renting contract"

    for token in tokens:
        token_owner: address = self.id_to_owner[token.token_id]
        assert token_owner != empty(address), "invalid token"
        if token_owner == token.wallet:
            self._burn_token_from(token.wallet, token.token_id)
            log Transfer(token.wallet, empty(address), token.token_id)


@pure
@external
def supportsInterface(interface_id: bytes4) -> bool:
    return interface_id in SUPPORTED_INTERFACES

@view
@external
def balanceOf(_owner: address) -> uint256:
    assert _owner != empty(address)
    return self.owner_to_nft_count[_owner]


@view
@external
def ownerOf(_tokenId: uint256) -> address:
    owner: address = self.id_to_owner[_tokenId]
    assert owner != empty(address)
    return owner


@view
@external
def getApproved(_tokenId: uint256) -> address:
    assert self.id_to_owner[_tokenId] != empty(address)
    return self.id_to_approvals[_tokenId]


@view
@external
def isApprovedForAll(_owner: address, _operator: address) -> bool:
    return self.owner_to_operators[_owner][_operator]


@external
def transferFrom(_from: address, _to: address, _tokenId: uint256):
    self._transfer_from(_from, _to, _tokenId, msg.sender)


@external
def safeTransferFrom(_from: address, _to: address, _tokenId: uint256, _data: Bytes[1024]=b""):
    self._transfer_from(_from, _to, _tokenId, msg.sender)
    if _to.is_contract:
        returnValue: bytes4 = ERC721Receiver(_to).onERC721Received(msg.sender, _from, _tokenId, _data)
        assert returnValue == convert(method_id("onERC721Received(address,address,uint256,bytes)", output_type=Bytes[4]), bytes4)


@external
def approve(_approved: address, _tokenId: uint256):
    owner: address = self.id_to_owner[_tokenId]
    assert owner != empty(address)
    assert _approved != owner
    assert (self.id_to_owner[_tokenId] == msg.sender or self.owner_to_operators[owner][msg.sender])
    self.id_to_approvals[_tokenId] = _approved
    log Approval(owner, _approved, _tokenId)


@external
def setApprovalForAll(_operator: address, _approved: bool):
    assert _operator != msg.sender
    self.owner_to_operators[msg.sender][_operator] = _approved
    log ApprovalForAll(msg.sender, _operator, _approved)


@view
@external
def tokenURI(tokenId: uint256) -> String[132]:
    return ""


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
