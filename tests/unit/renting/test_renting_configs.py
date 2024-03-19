import boa
from eth_utils import decode_hex

from ...conftest_base import ZERO_ADDRESS, deploy_reverts, get_last_event

FOREVER = 2**256 - 1
PROTOCOL_FEE = 500


def test_deploy_validation(
    renting_contract_def,
    vault_contract,
    ape_contract,
    nft_contract,
    delegation_registry_warm_contract,
    protocol_wallet,
    renting721_contract,
):
    with deploy_reverts():
        renting_contract_def.deploy(
            vault_contract,
            ape_contract,
            nft_contract,
            delegation_registry_warm_contract,
            renting721_contract,
            ZERO_ADDRESS,
            0,
            0,
            ZERO_ADDRESS,
            protocol_wallet,
        )

    with deploy_reverts():
        renting_contract_def.deploy(
            vault_contract,
            ape_contract,
            nft_contract,
            delegation_registry_warm_contract,
            renting721_contract,
            ZERO_ADDRESS,
            0,
            0,
            protocol_wallet,
            ZERO_ADDRESS,
        )
    with deploy_reverts():
        renting_contract_def.deploy(
            vault_contract,
            ape_contract,
            nft_contract,
            delegation_registry_warm_contract,
            renting721_contract,
            ZERO_ADDRESS,
            10001,
            0,
            protocol_wallet,
            protocol_wallet,
        )

    with deploy_reverts():
        renting_contract_def.deploy(
            vault_contract,
            ape_contract,
            nft_contract,
            delegation_registry_warm_contract,
            renting721_contract,
            ZERO_ADDRESS,
            0,
            1,
            protocol_wallet,
            protocol_wallet,
        )

    with deploy_reverts():
        renting_contract_def.deploy(
            ZERO_ADDRESS,
            ZERO_ADDRESS,
            ZERO_ADDRESS,
            ZERO_ADDRESS,
            ZERO_ADDRESS,
            ZERO_ADDRESS,
            0,
            1,
            protocol_wallet,
            protocol_wallet,
        )


def test_initial_state(
    vault_contract,
    renting_contract,
    nft_contract,
    ape_contract,
    delegation_registry_warm_contract,
    protocol_wallet,
    owner,
    renting721_contract,
):
    assert renting_contract.vault_impl_addr() == vault_contract.address
    assert renting_contract.payment_token() == ape_contract.address
    assert renting_contract.nft_contract_addr() == nft_contract.address
    assert renting_contract.delegation_registry_addr() == delegation_registry_warm_contract.address
    assert renting_contract.renting_erc721() == renting721_contract.address
    assert renting_contract.staking_addr() == ZERO_ADDRESS
    assert renting_contract.protocol_admin() == owner
    assert renting_contract.protocol_wallet() == protocol_wallet
    assert renting_contract.max_protocol_fee() == PROTOCOL_FEE
    assert renting_contract.protocol_fee() == PROTOCOL_FEE
    assert not renting_contract.paused()


def test_renting_erc721_initialization(renting_erc721_contract_def, renting_contract_def):
    dummy = boa.env.generate_address("dummy")
    renting721 = renting_erc721_contract_def.deploy()
    renting = renting_contract_def.deploy(dummy, dummy, dummy, dummy, renting721, dummy, 0, 0, dummy, dummy)
    assert renting721.renting_addr() == renting.address
    assert renting.renting_erc721() == renting721.address


def test_supports_interface(renting_contract):
    assert renting_contract.supportsInterface(decode_hex("0x80ac58cd"))
    assert renting_contract.supportsInterface(decode_hex("0x01ffc9a7"))


def test_change_protocol_fee_reverts_if_wrong_caller(renting_contract, renter):
    with boa.reverts("not protocol admin"):
        renting_contract.set_protocol_fee(0, sender=renter)


def test_change_protocol_fee_reverts_if_higher_than_max(renting_contract, owner):
    with boa.reverts("protocol fee > max fee"):
        renting_contract.set_protocol_fee(PROTOCOL_FEE * 2, sender=owner)


def test_change_protocol_fee(renting_contract, protocol_wallet, owner):
    renting_contract.set_protocol_fee(0, sender=owner)
    event = get_last_event(renting_contract, "ProtocolFeeSet")

    assert renting_contract.protocol_fee() == 0

    assert event.old_fee == PROTOCOL_FEE
    assert event.new_fee == 0
    assert event.fee_wallet == protocol_wallet


def test_change_protocol_wallet_reverts_if_wrong_caller(renting_contract, renter):
    with boa.reverts("not protocol admin"):
        renting_contract.change_protocol_wallet(renter, sender=renter)


def test_change_protocol_wallet_reverts_if_zero_address(
    renting_contract,
    owner,
):
    with boa.reverts("wallet is the zero address"):
        renting_contract.change_protocol_wallet(ZERO_ADDRESS, sender=owner)


def test_change_protocol_wallet(renting_contract, protocol_wallet, owner, nft_owner):
    renting_contract.change_protocol_wallet(nft_owner, sender=owner)
    event = get_last_event(renting_contract, "ProtocolWalletChanged")

    assert renting_contract.protocol_wallet() == nft_owner

    assert event.old_wallet == protocol_wallet
    assert event.new_wallet == nft_owner


def test_set_staking_addr(renting_contract, owner):
    staking_addr = boa.env.generate_address("staking")

    renting_contract.set_staking_addr(staking_addr, sender=owner)
    event = get_last_event(renting_contract, "StakingAddressSet")
    assert event.new_value == staking_addr
    assert renting_contract.staking_addr() == staking_addr

    renting_contract.set_staking_addr(ZERO_ADDRESS, sender=owner)
    event = get_last_event(renting_contract, "StakingAddressSet")
    assert event.old_value == staking_addr
    assert event.new_value == ZERO_ADDRESS
    assert renting_contract.staking_addr() == ZERO_ADDRESS


def test_set_staking_addr_reverts_if_wrong_caller(renting_contract, renter):
    with boa.reverts("not protocol admin"):
        renting_contract.set_staking_addr(ZERO_ADDRESS, sender=renter)


def test_propose_admin_reverts_if_wrong_caller(renting_contract, renter):
    with boa.reverts("not the admin"):
        renting_contract.propose_admin(ZERO_ADDRESS, sender=renter)


def test_propose_admin_reverts_if_zero_address(renting_contract, owner):
    with boa.reverts("_address is the zero address"):
        renting_contract.propose_admin(ZERO_ADDRESS, sender=owner)


def test_propose_admin(renting_contract, owner, nft_owner):
    renting_contract.propose_admin(nft_owner, sender=owner)
    event = get_last_event(renting_contract, "AdminProposed")

    assert renting_contract.proposed_admin() == nft_owner

    assert event.admin == owner
    assert event.proposed_admin == nft_owner


def test_claim_ownership_reverts_if_wrong_caller(renting_contract, owner, nft_owner):
    renting_contract.propose_admin(nft_owner, sender=owner)

    with boa.reverts("not the proposed"):
        renting_contract.claim_ownership(sender=owner)


def test_claim_ownership(renting_contract, owner, nft_owner):
    renting_contract.propose_admin(nft_owner, sender=owner)

    renting_contract.claim_ownership(sender=nft_owner)
    event = get_last_event(renting_contract, "OwnershipTransferred")

    assert renting_contract.proposed_admin() == ZERO_ADDRESS
    assert renting_contract.protocol_admin() == nft_owner

    assert event.old_admin == owner
    assert event.new_admin == nft_owner


def test_set_paused(renting_contract, owner):
    renting_contract.set_paused(True, sender=owner)
    event = get_last_event(renting_contract, "PauseStateSet")
    assert event.new_value is True

    assert renting_contract.paused()

    renting_contract.set_paused(False, sender=owner)
    event = get_last_event(renting_contract, "PauseStateSet")
    assert event.old_value is True
    assert event.new_value is False

    assert not renting_contract.paused()
