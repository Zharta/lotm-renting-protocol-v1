import boa
import pytest

from ...conftest_base import ZERO_ADDRESS, deploy_reverts, get_last_event

FOREVER = 2**256 - 1
PROTOCOL_FEE = 500


@pytest.fixture(scope="module")
def vault_contract(vault_contract_def, ape_contract, nft_contract, delegation_registry_warm_contract):
    return vault_contract_def.deploy(ape_contract, nft_contract, delegation_registry_warm_contract, ZERO_ADDRESS)


@pytest.fixture(scope="module")
def renting_contract(
    renting_contract_def, vault_contract, ape_contract, nft_contract, delegation_registry_warm_contract, protocol_wallet, owner
):
    return renting_contract_def.deploy(
        vault_contract,
        ape_contract,
        nft_contract,
        delegation_registry_warm_contract,
        ZERO_ADDRESS,
        0,
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


def test_deploy_validation(
    renting_contract_def, vault_contract, ape_contract, nft_contract, delegation_registry_warm_contract, protocol_wallet
):
    with deploy_reverts():
        renting_contract_def.deploy(
            vault_contract,
            ape_contract,
            nft_contract,
            delegation_registry_warm_contract,
            ZERO_ADDRESS,
            0,
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
            ZERO_ADDRESS,
            0,
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
            ZERO_ADDRESS,
            0,
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
            ZERO_ADDRESS,
            0,
            0,
            1,
            protocol_wallet,
            protocol_wallet,
        )

    with deploy_reverts():
        renting_contract_def.deploy(
            ZERO_ADDRESS, ZERO_ADDRESS, ZERO_ADDRESS, ZERO_ADDRESS, ZERO_ADDRESS, 0, 0, 1, protocol_wallet, protocol_wallet
        )


def test_initial_state(
    vault_contract, renting_contract, nft_contract, ape_contract, delegation_registry_warm_contract, protocol_wallet, owner
):
    assert renting_contract.vault_impl_addr() == vault_contract.address
    assert renting_contract.payment_token() == ape_contract.address
    assert renting_contract.nft_contract_addr() == nft_contract.address
    assert renting_contract.delegation_registry_addr() == delegation_registry_warm_contract.address
    assert renting_contract.staking_addr() == ZERO_ADDRESS
    assert renting_contract.protocol_admin() == owner
    assert renting_contract.protocol_wallet() == protocol_wallet
    assert renting_contract.max_protocol_fee() == PROTOCOL_FEE
    assert renting_contract.protocol_fee() == PROTOCOL_FEE


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
