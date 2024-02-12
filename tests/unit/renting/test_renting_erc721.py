from textwrap import dedent

import boa
from eth_utils import decode_hex

from ...conftest_base import (
    ZERO_ADDRESS,
    Rental,
    TokenContext,
    get_events,
    get_last_event,
)

FOREVER = 2**256 - 1
PROTOCOL_FEE = 500


def test_deposit_mints_token(renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract):
    token_id = 1

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)

    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)
    _, event = get_events(renting_contract, "Transfer")

    assert event.sender == ZERO_ADDRESS
    assert event.receiver == nft_owner
    assert event.tokenId == token_id

    assert nft_contract.ownerOf(token_id) == vault_addr
    assert renting_contract.ownerOf(token_id) == nft_owner
    assert renting_contract.balanceOf(nft_owner) == 1


def test_withdraw_burns_renting_token(renting_contract, nft_contract, nft_owner):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], nft_owner, sender=nft_owner)

    renting_contract.withdraw([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=nft_owner)
    event, _ = get_events(renting_contract, "Transfer")

    assert event.sender == nft_owner
    assert event.receiver == ZERO_ADDRESS
    assert event.tokenId == token_id

    assert renting_contract.balanceOf(nft_owner) == 0
    assert nft_contract.ownerOf(token_id) == nft_owner
    with boa.reverts():
        renting_contract.ownerOf(token_id)


def test_supports_interface(renting_contract):
    assert renting_contract.supportsInterface(decode_hex("0x80ac58cd"))
    assert renting_contract.supportsInterface(decode_hex("0x01ffc9a7"))


def test_balance_of(renting_contract, nft_contract, nft_owner, owner):
    nft_contract.mint(nft_owner, 2, sender=owner)
    assert renting_contract.balanceOf(nft_owner) == 0

    nft_contract.approve(renting_contract.tokenid_to_vault(1), 1, sender=nft_owner)
    nft_contract.approve(renting_contract.tokenid_to_vault(2), 2, sender=nft_owner)

    renting_contract.deposit([1], ZERO_ADDRESS, sender=nft_owner)
    assert renting_contract.balanceOf(nft_owner) == 1

    renting_contract.deposit([2], ZERO_ADDRESS, sender=nft_owner)
    assert renting_contract.balanceOf(nft_owner) == 2

    renting_contract.withdraw([TokenContext(1, nft_owner, Rental()).to_tuple()], sender=nft_owner)
    assert renting_contract.balanceOf(nft_owner) == 1

    renting_contract.withdraw([TokenContext(2, nft_owner, Rental()).to_tuple()], sender=nft_owner)
    assert renting_contract.balanceOf(nft_owner) == 0


def test_balance_of_reverts_if_invalid_owner(renting_contract):
    with boa.reverts():
        renting_contract.balanceOf(ZERO_ADDRESS)


def test_owner_of(renting_contract, nft_contract, nft_owner):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    assert renting_contract.ownerOf(token_id) == nft_owner


def test_owner_of_reverts_if_invalid_token_id(renting_contract):
    with boa.reverts():
        renting_contract.ownerOf(1)


def test_get_approved(renting_contract, nft_contract, nft_owner):
    token_id = 1
    approved = boa.env.generate_address("approved")

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    assert renting_contract.getApproved(token_id) == ZERO_ADDRESS
    renting_contract.approve(approved, token_id, sender=nft_owner)

    assert renting_contract.getApproved(token_id) == approved


def test_get_approved_reverts_if_invalid_token_id(renting_contract):
    with boa.reverts():
        renting_contract.getApproved(1)


def test_get_approved_for_all(renting_contract, nft_owner):
    operator = boa.env.generate_address("operator")

    assert not renting_contract.isApprovedForAll(nft_owner, operator)
    renting_contract.setApprovalForAll(operator, True, sender=nft_owner)

    assert renting_contract.isApprovedForAll(nft_owner, operator)


def test_approve(renting_contract, nft_contract, nft_owner):
    token_id = 1
    approved = boa.env.generate_address("approved")

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    assert renting_contract.getApproved(token_id) == ZERO_ADDRESS
    renting_contract.approve(approved, token_id, sender=nft_owner)

    assert renting_contract.getApproved(token_id) == approved


def test_approve_by_operator(renting_contract, nft_contract, nft_owner):
    token_id = 1
    operator = boa.env.generate_address("operator")
    approved = boa.env.generate_address("approved")

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    assert renting_contract.getApproved(token_id) == ZERO_ADDRESS
    renting_contract.setApprovalForAll(operator, True, sender=nft_owner)
    renting_contract.approve(approved, token_id, sender=operator)

    assert renting_contract.getApproved(token_id) == approved


def test_approve_logs_approval(renting_contract, nft_contract, nft_owner):
    token_id = 1
    approved = boa.env.generate_address("approved")

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    renting_contract.approve(approved, token_id, sender=nft_owner)
    event = get_last_event(renting_contract, "Approval")

    assert event.owner == nft_owner
    assert event.approved == approved
    assert event.tokenId == token_id


def test_approve_reverts_if_invalid_token_id(renting_contract, nft_owner):
    approved = boa.env.generate_address("approved")
    with boa.reverts():
        renting_contract.approve(approved, 1, sender=nft_owner)


def test_approve_reverts_if_approved_is_owner(renting_contract, nft_contract, nft_owner):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    with boa.reverts():
        renting_contract.approve(nft_owner, token_id, sender=nft_owner)


def test_approve_reverts_if_not_owner_or_operator(renting_contract, nft_owner):
    token_id = 1
    approved = boa.env.generate_address("approved")
    random_guy = boa.env.generate_address("random_guy")

    with boa.reverts():
        renting_contract.approve(approved, token_id, sender=random_guy)


def test_approve_for_all(renting_contract, nft_owner):
    operator = boa.env.generate_address("operator")

    assert not renting_contract.isApprovedForAll(nft_owner, operator)
    renting_contract.setApprovalForAll(operator, True, sender=nft_owner)

    assert renting_contract.isApprovedForAll(nft_owner, operator)
    renting_contract.setApprovalForAll(operator, False, sender=nft_owner)

    assert not renting_contract.isApprovedForAll(nft_owner, operator)


def test_approve_for_all_logs_approval(renting_contract, nft_owner):
    operator = boa.env.generate_address("operator")

    renting_contract.setApprovalForAll(operator, True, sender=nft_owner)
    event = get_last_event(renting_contract, "ApprovalForAll")

    assert event.owner == nft_owner
    assert event.operator == operator
    assert event.approved == True


def test_set_approval_for_all_reverts_if_operator_is_owner(renting_contract, nft_owner):
    with boa.reverts():
        renting_contract.setApprovalForAll(nft_owner, True, sender=nft_owner)


def test_transfer_from(renting_contract, nft_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    renting_contract.transferFrom(nft_owner, receiver, token_id, sender=nft_owner)

    assert renting_contract.ownerOf(token_id) == receiver
    assert renting_contract.balanceOf(nft_owner) == 0
    assert renting_contract.balanceOf(receiver) == 1


def test_transfer_from_by_operator(renting_contract, nft_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    operator = boa.env.generate_address("operator")

    renting_contract.setApprovalForAll(operator, True, sender=nft_owner)

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    renting_contract.transferFrom(nft_owner, receiver, token_id, sender=operator)

    assert renting_contract.ownerOf(token_id) == receiver
    assert renting_contract.balanceOf(nft_owner) == 0
    assert renting_contract.balanceOf(receiver) == 1


def test_transfer_from_by_approved(renting_contract, nft_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    approved = boa.env.generate_address("approved")

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    renting_contract.approve(approved, token_id, sender=nft_owner)
    renting_contract.transferFrom(nft_owner, receiver, token_id, sender=approved)

    assert renting_contract.ownerOf(token_id) == receiver
    assert renting_contract.balanceOf(nft_owner) == 0
    assert renting_contract.balanceOf(receiver) == 1


def test_transfer_from_logs_transfer(renting_contract, nft_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    renting_contract.transferFrom(nft_owner, receiver, token_id, sender=nft_owner)
    event = get_last_event(renting_contract, "Transfer")

    assert event.sender == nft_owner
    assert event.receiver == receiver
    assert event.tokenId == token_id


def test_transfer_from_clears_approvals(renting_contract, nft_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    approved = boa.env.generate_address("approved")

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    renting_contract.approve(approved, token_id, sender=nft_owner)
    renting_contract.transferFrom(nft_owner, receiver, token_id, sender=nft_owner)

    assert renting_contract.getApproved(token_id) == ZERO_ADDRESS


def test_transfer_from_reverts_if_invalid_token_id(renting_contract, nft_owner):
    receiver = boa.env.generate_address("receiver")
    with boa.reverts():
        renting_contract.transferFrom(nft_owner, receiver, 1, sender=nft_owner)


def test_transfer_from_reverts_if_sender_not_owner_or_approved(renting_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    with boa.reverts():
        renting_contract.transferFrom(nft_owner, receiver, token_id, sender=receiver)


def test_transfer_from_reverts_if_from_not_owner(renting_contract, nft_owner, nft_contract):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    not_owner = boa.env.generate_address("not_owner")

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    with boa.reverts():
        renting_contract.transferFrom(not_owner, receiver, token_id, sender=nft_owner)


def test_transfer_from_reverts_if_receiver_is_zero_address(renting_contract, nft_contract, nft_owner):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)
    with boa.reverts():
        renting_contract.transferFrom(nft_owner, ZERO_ADDRESS, token_id, sender=nft_owner)


def test_transfer_from_keeps_delegation(renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    delegate = boa.env.generate_address("delegate")

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], delegate, sender=nft_owner)

    renting_contract.transferFrom(nft_owner, receiver, token_id, sender=nft_owner)

    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate


def test_transfer_from_keeps_nft_owner(renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    delegate = boa.env.generate_address("delegate")

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    renting_contract.transferFrom(nft_owner, receiver, token_id, sender=nft_owner)

    assert renting_contract.ownerOf(token_id) == receiver
    assert nft_contract.ownerOf(token_id) == vault_addr

    renting_contract.delegate_to_wallet([TokenContext(token_id, nft_owner, Rental()).to_tuple()], delegate, sender=nft_owner)
    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate


def test_transfer_from_allows_withdraw(renting_contract, nft_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    renting_contract.transferFrom(nft_owner, receiver, token_id, sender=nft_owner)

    assert renting_contract.ownerOf(token_id) == receiver
    assert nft_contract.ownerOf(token_id) == vault_addr

    renting_contract.withdraw([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=receiver)
    assert nft_contract.ownerOf(token_id) == receiver


def test_safe_transfer_from_to_eoa(renting_contract, nft_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    data = b""

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    renting_contract.safeTransferFrom(nft_owner, receiver, token_id, data, sender=nft_owner)

    assert renting_contract.ownerOf(token_id) == receiver
    assert renting_contract.balanceOf(nft_owner) == 0
    assert renting_contract.balanceOf(receiver) == 1


def test_safe_transfer_from_to_contract(renting_contract, nft_contract, nft_owner):
    token_id = 1
    data = b""

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

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    renting_contract.safeTransferFrom(nft_owner, receiver.address, token_id, data, sender=nft_owner)

    assert renting_contract.ownerOf(token_id) == receiver.address
    assert renting_contract.balanceOf(nft_owner) == 0
    assert renting_contract.balanceOf(receiver.address) == 1


def test_safe_transfer_from_reverts_if_wrong_callback_response(renting_contract, nft_contract, nft_owner, empty_contract_def):
    token_id = 1
    data = b""

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    receiver = empty_contract_def.deploy()
    with boa.reverts():
        renting_contract.safeTransferFrom(nft_owner, receiver.address, token_id, data, sender=nft_owner)

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
        renting_contract.safeTransferFrom(nft_owner, receiver.address, token_id, data, sender=nft_owner)

    assert renting_contract.ownerOf(token_id) == nft_owner
    assert renting_contract.balanceOf(nft_owner) == 1
    assert renting_contract.balanceOf(receiver.address) == 0


def test_safe_transfer_from_send_data_to_callback(renting_contract, nft_contract, nft_owner):
    token_id = 1
    data = decode_hex("0x1234")

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

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    renting_contract.safeTransferFrom(nft_owner, receiver.address, token_id, data, sender=nft_owner)

    assert renting_contract.ownerOf(token_id) == receiver.address
    assert renting_contract.balanceOf(nft_owner) == 0
    assert renting_contract.balanceOf(receiver.address) == 1


def test_safe_transfer_from_by_operator(renting_contract, nft_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    operator = boa.env.generate_address("operator")
    data = b""

    renting_contract.setApprovalForAll(operator, True, sender=nft_owner)

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    renting_contract.safeTransferFrom(nft_owner, receiver, token_id, data, sender=operator)

    assert renting_contract.ownerOf(token_id) == receiver
    assert renting_contract.balanceOf(nft_owner) == 0
    assert renting_contract.balanceOf(receiver) == 1


def test_safe_transfer_from_by_approved(renting_contract, nft_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    approved = boa.env.generate_address("approved")
    data = b""

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    renting_contract.approve(approved, token_id, sender=nft_owner)
    renting_contract.safeTransferFrom(nft_owner, receiver, token_id, data, sender=approved)

    assert renting_contract.ownerOf(token_id) == receiver
    assert renting_contract.balanceOf(nft_owner) == 0
    assert renting_contract.balanceOf(receiver) == 1


def test_safe_transfer_from_logs_transfer(renting_contract, nft_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    data = b""

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    renting_contract.safeTransferFrom(nft_owner, receiver, token_id, data, sender=nft_owner)
    event = get_last_event(renting_contract, "Transfer")

    assert event.sender == nft_owner
    assert event.receiver == receiver
    assert event.tokenId == token_id


def test_safe_transfer_from_clears_approvals(renting_contract, nft_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    approved = boa.env.generate_address("approved")
    data = b""

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    renting_contract.approve(approved, token_id, sender=nft_owner)
    renting_contract.safeTransferFrom(nft_owner, receiver, token_id, data, sender=nft_owner)

    assert renting_contract.getApproved(token_id) == ZERO_ADDRESS


def test_safe_transfer_from_reverts_if_invalid_token_id(renting_contract, nft_owner):
    receiver = boa.env.generate_address("receiver")
    data = b""
    with boa.reverts():
        renting_contract.safeTransferFrom(nft_owner, receiver, 1, data, sender=nft_owner)


def test_safe_transfer_from_reverts_if_sender_not_owner_or_approved(renting_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    data = b""
    with boa.reverts():
        renting_contract.safeTransferFrom(nft_owner, receiver, token_id, data, sender=receiver)


def test_safe_transfer_from_reverts_if_from_not_owner(renting_contract, nft_owner, nft_contract):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    not_owner = boa.env.generate_address("not_owner")
    data = b""

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    with boa.reverts():
        renting_contract.safeTransferFrom(not_owner, receiver, token_id, data, sender=nft_owner)


def test_safe_transfer_from_reverts_if_receiver_is_zero_address(renting_contract, nft_contract, nft_owner):
    token_id = 1
    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)
    with boa.reverts():
        renting_contract.safeTransferFrom(nft_owner, ZERO_ADDRESS, token_id, b"", sender=nft_owner)


def test_safe_transfer_from_keeps_delegation(renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    delegate = boa.env.generate_address("delegate")
    data = b""

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], delegate, sender=nft_owner)

    renting_contract.safeTransferFrom(nft_owner, receiver, token_id, data, sender=nft_owner)

    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate


def test_safe_transfer_from_keeps_nft_owner(renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    delegate = boa.env.generate_address("delegate")
    data = b""

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    renting_contract.safeTransferFrom(nft_owner, receiver, token_id, data, sender=nft_owner)

    assert renting_contract.ownerOf(token_id) == receiver
    assert nft_contract.ownerOf(token_id) == vault_addr

    renting_contract.delegate_to_wallet([TokenContext(token_id, nft_owner, Rental()).to_tuple()], delegate, sender=nft_owner)
    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == delegate


def test_safe_transfer_from_allows_withdraw(renting_contract, nft_contract, nft_owner):
    token_id = 1
    receiver = boa.env.generate_address("receiver")
    data = b""

    vault_addr = renting_contract.tokenid_to_vault(token_id)
    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)

    renting_contract.safeTransferFrom(nft_owner, receiver, token_id, data, sender=nft_owner)

    assert renting_contract.ownerOf(token_id) == receiver
    assert nft_contract.ownerOf(token_id) == vault_addr

    renting_contract.withdraw([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=receiver)
    assert nft_contract.ownerOf(token_id) == receiver


def test_claim_token_ownership(renting_contract, nft_contract, nft_owner, delegation_registry_warm_contract):
    token_id = 1
    receiver = boa.env.generate_address("receiver")

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)
    renting_contract.safeTransferFrom(nft_owner, receiver, token_id, b"", sender=nft_owner)

    renting_contract.claim_token_ownership([TokenContext(token_id, nft_owner, Rental()).to_tuple()], sender=receiver)

    assert renting_contract.ownerOf(token_id) == receiver
    assert renting_contract.balanceOf(receiver) == 1

    renting_contract.delegate_to_wallet([TokenContext(token_id, receiver, Rental()).to_tuple()], receiver, sender=receiver)

    assert delegation_registry_warm_contract.getHotWallet(vault_addr) == receiver


def test_claim_token_ownership_reverts_if_invalid_context(renting_contract, nft_owner, nft_contract):
    token_id = 1
    receiver = boa.env.generate_address("receiver")

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)
    renting_contract.safeTransferFrom(nft_owner, receiver, token_id, b"", sender=nft_owner)

    with boa.reverts():
        renting_contract.claim_token_ownership([TokenContext(2, nft_owner, Rental()).to_tuple()], sender=receiver)


def test_claim_token_ownership_reverts_if_not_owner(renting_contract, nft_owner, nft_contract):
    token_id = 1
    receiver = boa.env.generate_address("receiver")

    vault_addr = renting_contract.tokenid_to_vault(token_id)

    nft_contract.approve(vault_addr, token_id, sender=nft_owner)
    renting_contract.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)
    renting_contract.safeTransferFrom(nft_owner, receiver, token_id, b"", sender=nft_owner)

    with boa.reverts():
        renting_contract.claim_token_ownership([TokenContext(1, nft_owner, Rental()).to_tuple()], sender=nft_owner)
