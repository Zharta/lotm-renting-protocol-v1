from textwrap import dedent

import boa
import pytest
from eth_utils import decode_hex

from ...conftest_base import (
    ZERO_ADDRESS,
    Listing,
    Rental,
    RentalLog,
    TokenAndWallet,
    TokenContext,
    TokenContextAndListing,
    compute_state_hash,
    get_last_event,
    sign_listing,
)

FOREVER = 2**256 - 1
PROTOCOL_FEE = 500


@pytest.fixture(scope="module")
def vault_contract(vault_contract_def, ape_contract, nft_contract, delegation_registry_warm_contract):
    return vault_contract_def.deploy(ape_contract, nft_contract, delegation_registry_warm_contract)


@pytest.fixture(scope="module")
def renting721_contract(renting_erc721_contract_def):
    return renting_erc721_contract_def.deploy()


@pytest.fixture(scope="module")
def renting_contract(
    renting_contract_def,
    vault_contract,
    ape_contract,
    nft_contract,
    delegation_registry_warm_contract,
    protocol_wallet,
    owner,
    renting721_contract,
):
    return renting_contract_def.deploy(
        vault_contract,
        ape_contract,
        nft_contract,
        delegation_registry_warm_contract,
        renting721_contract,
        ZERO_ADDRESS,
        PROTOCOL_FEE,
        PROTOCOL_FEE,
        protocol_wallet,
        owner,
    )


@pytest.fixture(autouse=True)
def mint(nft_owner, owner, renter, nft_contract, ape_contract):
    with boa.env.anchor():
        nft_contract.mint(nft_owner, 1, sender=owner)
        ape_contract.mint(renter, int(1000 * 1e18), sender=owner)
        yield


def test_initial_state(renting721_contract, renting_contract, vault_contract, nft_contract, ape_contract, nft_owner):
    assert renting721_contract.renting_addr() == renting_contract.address
    # assert renting721_contract.name() == ""
    # assert renting721_contract.symbol() == ""
    assert renting721_contract.tokenURI(0) == ""


def test_initialise(renting_erc721_contract_def):
    renting = boa.env.generate_address("renting")
    renting721 = renting_erc721_contract_def.deploy()
    renting721.initialise(sender=renting)
    assert renting721.renting_addr() == renting


def test_initialise_reverts_if_initialised(renting721_contract, renting_contract):
    with boa.reverts("already initialised"):
        renting721_contract.initialise(sender=renting_contract.address)


def test_balance_of(renting721_contract, renting_contract, nft_owner, owner):
    assert renting721_contract.balanceOf(nft_owner) == 0

    renting721_contract.mint([TokenAndWallet(1, nft_owner)], sender=renting_contract.address)
    assert renting721_contract.balanceOf(nft_owner) == 1

    renting721_contract.mint([TokenAndWallet(2, nft_owner)], sender=renting_contract.address)
    assert renting721_contract.balanceOf(nft_owner) == 2

    renting721_contract.burn([TokenAndWallet(1, nft_owner)], sender=renting_contract.address)
    assert renting721_contract.balanceOf(nft_owner) == 1

    renting721_contract.burn([TokenAndWallet(2, nft_owner)], sender=renting_contract.address)
    assert renting721_contract.balanceOf(nft_owner) == 0


def test_balance_of_reverts_if_invalid_owner(renting721_contract):
    with boa.reverts():
        renting721_contract.balanceOf(ZERO_ADDRESS)


def test_owner_of(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)
    assert renting721_contract.ownerOf(token_id) == nft_owner


def test_owner_of_reverts_if_invalid_token_id(renting721_contract):
    with boa.reverts():
        renting721_contract.ownerOf(1)


def test_get_approved(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    approved = boa.env.generate_address("approved")

    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    assert renting721_contract.getApproved(token_id) == ZERO_ADDRESS
    renting721_contract.approve(approved, token_id, sender=nft_owner)

    assert renting721_contract.getApproved(token_id) == approved


def test_get_approved_reverts_if_invalid_token_id(renting721_contract):
    with boa.reverts():
        renting721_contract.getApproved(1)


def test_get_approved_for_all(renting721_contract, nft_owner):
    operator = boa.env.generate_address("operator")

    assert not renting721_contract.isApprovedForAll(nft_owner, operator)
    renting721_contract.setApprovalForAll(operator, True, sender=nft_owner)

    assert renting721_contract.isApprovedForAll(nft_owner, operator)


def test_approve(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    approved = boa.env.generate_address("approved")
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    assert renting721_contract.getApproved(token_id) == ZERO_ADDRESS
    renting721_contract.approve(approved, token_id, sender=nft_owner)

    assert renting721_contract.getApproved(token_id) == approved


def test_approve_by_operator(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    operator = boa.env.generate_address("operator")
    approved = boa.env.generate_address("approved")

    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    assert renting721_contract.getApproved(token_id) == ZERO_ADDRESS
    renting721_contract.setApprovalForAll(operator, True, sender=nft_owner)
    renting721_contract.approve(approved, token_id, sender=operator)

    assert renting721_contract.getApproved(token_id) == approved


def test_approve_logs_approval(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    approved = boa.env.generate_address("approved")

    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    renting721_contract.approve(approved, token_id, sender=nft_owner)
    event = get_last_event(renting721_contract, "Approval")

    assert event.owner == nft_owner
    assert event.approved == approved
    assert event.tokenId == token_id


def test_approve_reverts_if_invalid_token_id(renting721_contract, nft_owner):
    approved = boa.env.generate_address("approved")
    with boa.reverts():
        renting721_contract.approve(approved, 1, sender=nft_owner)


def test_approve_reverts_if_approved_is_owner(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    with boa.reverts():
        renting721_contract.approve(nft_owner, token_id, sender=nft_owner)


def test_approve_reverts_if_not_owner_or_operator(renting721_contract, nft_owner):
    token_id = 1
    approved = boa.env.generate_address("approved")
    random_guy = boa.env.generate_address("random_guy")

    with boa.reverts():
        renting721_contract.approve(approved, token_id, sender=random_guy)


def test_approve_for_all(renting721_contract, nft_owner):
    operator = boa.env.generate_address("operator")

    assert not renting721_contract.isApprovedForAll(nft_owner, operator)
    renting721_contract.setApprovalForAll(operator, True, sender=nft_owner)

    assert renting721_contract.isApprovedForAll(nft_owner, operator)
    renting721_contract.setApprovalForAll(operator, False, sender=nft_owner)

    assert not renting721_contract.isApprovedForAll(nft_owner, operator)


def test_approve_for_all_logs_approval(renting721_contract, nft_owner):
    operator = boa.env.generate_address("operator")

    renting721_contract.setApprovalForAll(operator, True, sender=nft_owner)
    event = get_last_event(renting721_contract, "ApprovalForAll")

    assert event.owner == nft_owner
    assert event.operator == operator
    assert event.approved == True


def test_set_approval_for_all_reverts_if_operator_is_owner(renting721_contract, nft_owner):
    with boa.reverts():
        renting721_contract.setApprovalForAll(nft_owner, True, sender=nft_owner)


def test_transfer_from(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    renting721_contract.transferFrom(nft_owner, receiver, token_id, sender=nft_owner)

    assert renting721_contract.ownerOf(token_id) == receiver
    assert renting721_contract.balanceOf(nft_owner) == 0
    assert renting721_contract.balanceOf(receiver) == 1


def test_transfer_from_by_operator(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    operator = boa.env.generate_address("operator")

    renting721_contract.setApprovalForAll(operator, True, sender=nft_owner)
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    renting721_contract.transferFrom(nft_owner, receiver, token_id, sender=operator)

    assert renting721_contract.ownerOf(token_id) == receiver
    assert renting721_contract.balanceOf(nft_owner) == 0
    assert renting721_contract.balanceOf(receiver) == 1


def test_transfer_from_by_approved(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    approved = boa.env.generate_address("approved")
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    renting721_contract.approve(approved, token_id, sender=nft_owner)
    renting721_contract.transferFrom(nft_owner, receiver, token_id, sender=approved)

    assert renting721_contract.ownerOf(token_id) == receiver
    assert renting721_contract.balanceOf(nft_owner) == 0
    assert renting721_contract.balanceOf(receiver) == 1


def test_transfer_from_logs_transfer(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    renting721_contract.transferFrom(nft_owner, receiver, token_id, sender=nft_owner)
    event = get_last_event(renting721_contract, "Transfer")

    assert event.sender == nft_owner
    assert event.receiver == receiver
    assert event.tokenId == token_id


def test_transfer_from_clears_approvals(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    approved = boa.env.generate_address("approved")
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    renting721_contract.approve(approved, token_id, sender=nft_owner)
    renting721_contract.transferFrom(nft_owner, receiver, token_id, sender=nft_owner)

    assert renting721_contract.getApproved(token_id) == ZERO_ADDRESS


def test_transfer_from_reverts_if_invalid_token_id(renting721_contract, nft_owner):
    receiver = boa.env.generate_address("receiver")
    with boa.reverts():
        renting721_contract.transferFrom(nft_owner, receiver, 1, sender=nft_owner)


def test_transfer_from_reverts_if_sender_not_owner_or_approved(renting721_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    with boa.reverts():
        renting721_contract.transferFrom(nft_owner, receiver, token_id, sender=receiver)


def test_transfer_from_reverts_if_from_not_owner(renting721_contract, nft_owner, renting_contract):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    not_owner = boa.env.generate_address("not_owner")
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    with boa.reverts():
        renting721_contract.transferFrom(not_owner, receiver, token_id, sender=nft_owner)


def test_transfer_from_reverts_if_receiver_is_zero_address(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)
    with boa.reverts():
        renting721_contract.transferFrom(nft_owner, ZERO_ADDRESS, token_id, sender=nft_owner)


def test_transfer_from_keeps_delegation(
    renting721_contract, renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract
):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    delegate = boa.env.generate_address("delegate")

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], delegate, sender=nft_owner)
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    renting721_contract.transferFrom(nft_owner, receiver, token_id, sender=nft_owner)

    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate


def test_transfer_from_keeps_nft_owner(
    renting721_contract, renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract
):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    delegate = boa.env.generate_address("delegate")

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    renting721_contract.transferFrom(nft_owner, receiver, token_id, sender=nft_owner)

    assert renting721_contract.ownerOf(token_id) == receiver
    assert nft_contract.ownerOf(token_id) == vault_addr

    renting_contract.delegate_to_wallet([TokenContext(token_id, nft_owner, Rental()).to_tuple()], delegate, sender=nft_owner)
    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate


def test_transfer_from_allows_withdraw(renting721_contract, renting_contract, nft_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    renting721_contract.transferFrom(nft_owner, receiver, token_id, sender=nft_owner)

    assert renting721_contract.ownerOf(token_id) == receiver
    assert nft_contract.ownerOf(token_id) == vault_addr

    renting_contract.withdraw([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=receiver)
    assert renting721_contract.ownerOf(token_id) == receiver


def test_safe_transfer_from_to_eoa(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    data = b""
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    renting721_contract.safeTransferFrom(nft_owner, receiver, token_id, data, sender=nft_owner)

    assert renting721_contract.ownerOf(token_id) == receiver
    assert renting721_contract.balanceOf(nft_owner) == 0
    assert renting721_contract.balanceOf(receiver) == 1


def test_safe_transfer_from_to_contract(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    data = b""
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    receiver = boa.loads(
        dedent(
            """
        @view
        @external
        def onERC721Received(_operator: address, _from: address, _tokenId: uint256, _data: Bytes[1024]) -> bytes4:
            return method_id("onERC721Received(address,address,uint256,bytes)", output_type=bytes4)
        """
        )
    )

    renting721_contract.safeTransferFrom(nft_owner, receiver.address, token_id, data, sender=nft_owner)

    assert renting721_contract.ownerOf(token_id) == receiver.address
    assert renting721_contract.balanceOf(nft_owner) == 0
    assert renting721_contract.balanceOf(receiver.address) == 1


def test_safe_transfer_from_reverts_if_wrong_callback_response(
    renting721_contract, renting_contract, nft_owner, empty_contract_def
):
    token_id = 1
    data = b""
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    receiver = empty_contract_def.deploy()
    with boa.reverts():
        renting721_contract.safeTransferFrom(nft_owner, receiver.address, token_id, data, sender=nft_owner)

    receiver = boa.loads(
        dedent(
            """
        @view
        @external
        def onERC721Received(_operator: address, _from: address, _tokenId: uint256, _data: Bytes[1024]) -> bytes4:
            return 0x00000000
        """
        )
    )

    with boa.reverts():
        renting721_contract.safeTransferFrom(nft_owner, receiver.address, token_id, data, sender=nft_owner)

    assert renting721_contract.ownerOf(token_id) == nft_owner
    assert renting721_contract.balanceOf(nft_owner) == 1
    assert renting721_contract.balanceOf(receiver.address) == 0


def test_safe_transfer_from_send_data_to_callback(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    data = decode_hex("0x1234")
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    receiver = boa.loads(
        dedent(
            """
        @view
        @external
        def onERC721Received(_operator: address, _from: address, _tokenId: uint256, _data: Bytes[1024]) -> bytes4:
            assert len(_data) == 2
            assert convert(slice(_data, 0, 2), bytes2) == 0x1234
            return method_id("onERC721Received(address,address,uint256,bytes)", output_type=bytes4)
        """
        )
    )

    renting721_contract.safeTransferFrom(nft_owner, receiver.address, token_id, data, sender=nft_owner)

    assert renting721_contract.ownerOf(token_id) == receiver.address
    assert renting721_contract.balanceOf(nft_owner) == 0
    assert renting721_contract.balanceOf(receiver.address) == 1


def test_safe_transfer_from_by_operator(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    operator = boa.env.generate_address("operator")
    data = b""

    renting721_contract.setApprovalForAll(operator, True, sender=nft_owner)

    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    renting721_contract.safeTransferFrom(nft_owner, receiver, token_id, data, sender=operator)

    assert renting721_contract.ownerOf(token_id) == receiver
    assert renting721_contract.balanceOf(nft_owner) == 0
    assert renting721_contract.balanceOf(receiver) == 1


def test_safe_transfer_from_by_approved(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    approved = boa.env.generate_address("approved")
    data = b""

    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    renting721_contract.approve(approved, token_id, sender=nft_owner)
    renting721_contract.safeTransferFrom(nft_owner, receiver, token_id, data, sender=approved)

    assert renting721_contract.ownerOf(token_id) == receiver
    assert renting721_contract.balanceOf(nft_owner) == 0
    assert renting721_contract.balanceOf(receiver) == 1


def test_safe_transfer_from_logs_transfer(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    data = b""

    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    renting721_contract.safeTransferFrom(nft_owner, receiver, token_id, data, sender=nft_owner)
    event = get_last_event(renting721_contract, "Transfer")

    assert event.sender == nft_owner
    assert event.receiver == receiver
    assert event.tokenId == token_id


def test_safe_transfer_from_clears_approvals(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    approved = boa.env.generate_address("approved")
    data = b""

    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    renting721_contract.approve(approved, token_id, sender=nft_owner)
    renting721_contract.safeTransferFrom(nft_owner, receiver, token_id, data, sender=nft_owner)

    assert renting721_contract.getApproved(token_id) == ZERO_ADDRESS


def test_safe_transfer_from_reverts_if_invalid_token_id(renting721_contract, nft_owner):
    receiver = boa.env.generate_address("receiver")
    data = b""
    with boa.reverts():
        renting721_contract.safeTransferFrom(nft_owner, receiver, 1, data, sender=nft_owner)


def test_safe_transfer_from_reverts_if_sender_not_owner_or_approved(renting721_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    data = b""
    with boa.reverts():
        renting721_contract.safeTransferFrom(nft_owner, receiver, token_id, data, sender=receiver)


def test_safe_transfer_from_reverts_if_from_not_owner(renting721_contract, nft_owner, renting_contract):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    not_owner = boa.env.generate_address("not_owner")
    data = b""

    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    with boa.reverts():
        renting721_contract.safeTransferFrom(not_owner, receiver, token_id, data, sender=nft_owner)


def test_safe_transfer_from_reverts_if_receiver_is_zero_address(renting721_contract, renting_contract, nft_owner):
    token_id = 1
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)
    with boa.reverts():
        renting721_contract.safeTransferFrom(nft_owner, ZERO_ADDRESS, token_id, b"", sender=nft_owner)


def test_safe_transfer_from_keeps_delegation(
    renting721_contract, renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract
):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    delegate = boa.env.generate_address("delegate")
    data = b""

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], delegate, sender=nft_owner)
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    renting721_contract.safeTransferFrom(nft_owner, receiver, token_id, data, sender=nft_owner)

    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate


def test_safe_transfer_from_keeps_nft_owner(
    renting721_contract, renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract
):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    delegate = boa.env.generate_address("delegate")
    data = b""

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    renting721_contract.safeTransferFrom(nft_owner, receiver, token_id, data, sender=nft_owner)

    assert renting721_contract.ownerOf(token_id) == receiver
    assert nft_contract.ownerOf(token_id) == vault_addr

    renting_contract.delegate_to_wallet([TokenContext(token_id, nft_owner, Rental()).to_tuple()], delegate, sender=nft_owner)
    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate


def test_safe_transfer_from_allows_withdraw(renting721_contract, renting_contract, nft_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    data = b""

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)

    renting721_contract.safeTransferFrom(nft_owner, receiver, token_id, data, sender=nft_owner)

    assert renting721_contract.ownerOf(token_id) == receiver
    assert nft_contract.ownerOf(token_id) == vault_addr

    renting_contract.withdraw([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=receiver)
    assert renting721_contract.ownerOf(token_id) == receiver


def test_claim_token_ownership(
    renting721_contract, renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract
):
    token_id = 1
    receiver = boa.env.generate_address("receiver")

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)
    renting721_contract.safeTransferFrom(nft_owner, receiver, token_id, b"", sender=nft_owner)

    renting_contract.claim_token_ownership([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=receiver)

    assert renting721_contract.ownerOf(token_id) == receiver
    assert renting721_contract.balanceOf(receiver) == 1

    renting_contract.delegate_to_wallet([TokenContext(token_id, receiver, Rental()).to_tuple()], receiver, sender=receiver)

    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == receiver


def test_claim_token_ownership_logs_token_ownership_changed(renting721_contract, renting_contract, nft_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)
    renting721_contract.safeTransferFrom(nft_owner, receiver, token_id, b"", sender=nft_owner)

    renting_contract.claim_token_ownership([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=receiver)
    event = get_last_event(renting_contract, "TokenOwnershipChanged")

    assert event.new_owner == receiver
    assert event.nft_contract == nft_contract.address
    assert len(event.tokens) == 1
    assert event.tokens[0] == token_id


def test_claim_token_ownership_reverts_if_invalid_context(renting721_contract, nft_contract, nft_owner, renting_contract):
    token_id = 1
    receiver = boa.env.generate_address("receiver")

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)
    renting721_contract.safeTransferFrom(nft_owner, receiver, token_id, b"", sender=nft_owner)

    with boa.reverts("invalid context"):
        renting_contract.claim_token_ownership([TokenContext(2, nft_owner, Rental()).to_tuple()], sender=receiver)


def test_claim_token_ownership_reverts_if_not_owner(renting721_contract, nft_contract, nft_owner, renting_contract):
    token_id = 1
    receiver = boa.env.generate_address("receiver")

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)
    renting721_contract.mint([TokenAndWallet(token_id, nft_owner)], sender=renting_contract.address)
    renting721_contract.safeTransferFrom(nft_owner, receiver, token_id, b"", sender=nft_owner)

    with boa.reverts("not owner"):
        renting_contract.claim_token_ownership([TokenContext(1, nft_owner, Rental()).to_tuple()], sender=nft_owner)


def test_claim_token_ownership_keeps_active_rental(
    renting721_contract,
    renting_contract,
    ape_contract,
    nft_contract,
    nft_owner,
    nft_owner_key,
    owner,
    owner_key,
    renter,
    delegation_registry_warm_contract,
):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    delegate = boa.env.generate_address("delegate")
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    price = int(1e18)
    duration = 10
    rental_amount = price * duration
    start_time = boa.eval("block.timestamp")

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], delegate, sender=nft_owner)

    listing = Listing(token_id, price, 0, 0, start_time)
    signed_listing = sign_listing(listing, nft_owner_key, owner_key, start_time, renting_contract.address)
    token_context = TokenContext(token_id, nft_owner, Rental())

    ape_contract.approve(renting_contract, rental_amount, sender=renter)

    renting_contract.start_rentals(
        [TokenContextAndListing(token_context, signed_listing).to_tuple()],
        duration,
        delegate,
        start_time,
        sender=renter,
    )
    rental_started_event = get_last_event(renting_contract, "RentalStarted")
    rental = RentalLog(*rental_started_event.rentals[0]).to_rental(renter=renter, delegate=delegate)
    token_context = TokenContext(token_id, nft_owner, rental)

    renting_contract.mint([token_context.to_tuple()], sender=nft_owner)
    renting721_contract.safeTransferFrom(nft_owner, receiver, token_id, sender=nft_owner)

    renting_contract.claim_token_ownership([token_context.to_tuple()], sender=receiver)

    assert renting_contract.rental_states(token_id) == compute_state_hash(token_id, receiver, rental)
    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate
