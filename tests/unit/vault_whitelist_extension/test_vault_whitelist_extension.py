import boa
import pytest

from ...conftest_base import ZERO_ADDRESS, TokenContext, deploy_minimal_proxy, deploy_runtime, get_last_event


def word(address: str) -> bytes:
    return bytes.fromhex(address[2:].rjust(64, "0"))


@pytest.fixture(scope="module")
def vault_impl(vault_contract_def, ape_contract, nft_contract, delegation_registry_warm_contract):
    return vault_contract_def.deploy(ape_contract, nft_contract, delegation_registry_warm_contract)


@pytest.fixture(scope="module")
def deploy_renting(
    renting_contract_def,
    renting_erc721_contract_def,
    vault_impl,
    ape_contract,
    delegation_registry_warm_contract,
    protocol_wallet,
    owner,
):
    def _deploy(collection: str):
        return renting_contract_def.deploy(
            vault_impl,
            ape_contract,
            collection,
            delegation_registry_warm_contract,
            renting_erc721_contract_def.deploy("", "", "", ""),
            ZERO_ADDRESS,
            0,
            0,
            protocol_wallet,
            owner,
        )

    return _deploy


@pytest.fixture(scope="module")
def renting(deploy_renting, nft_contract):
    return deploy_renting(nft_contract.address)


@pytest.fixture(scope="module")
def extension_def():
    return boa.load_partial("contracts/VaultWhitelistExtension.vy")


@pytest.fixture(scope="module")
def extension(extension_def, renting):
    return extension_def.deploy([renting.address])


@pytest.fixture(autouse=True)
def isolation():
    with boa.env.anchor():
        yield


@pytest.fixture
def deposit(nft_contract, owner, nft_owner):
    def _deposit(renting, token_id: int) -> str:
        vault = renting.tokenid_to_vault(token_id)
        nft_contract.mint(nft_owner, token_id, sender=owner)
        nft_contract.approve(vault, token_id, sender=nft_owner)
        renting.deposit([token_id], ZERO_ADDRESS, sender=nft_owner)
        return vault

    return _deposit


def test_markets(extension, renting, nft_contract):
    assert extension.markets(0) == (nft_contract.address, renting.address)


def test_deploy_without_markets(extension_def):
    with boa.reverts("no markets"):
        extension_def.deploy([])


def test_deploy_with_non_contract_renting(extension_def, renting):
    with boa.reverts("renting not a contract"):
        extension_def.deploy([renting.address, boa.env.generate_address()])


def test_deploy_with_non_renting_contract(extension_def, empty_contract_def):
    with boa.reverts():
        extension_def.deploy([empty_contract_def.deploy().address])


def test_register_vaults_unknown_renting(extension, deploy_renting, nft_contract):
    with boa.reverts("unknown renting"):
        extension.register_vaults(deploy_renting(nft_contract.address).address, [1])


def test_register_vaults_before_deployment(extension, renting, deposit):
    extension.register_vaults(renting.address, [1, 2])
    event = get_last_event(extension, "VaultRegistered")

    vault = deposit(renting, 2)
    assert extension.vaults(vault) == (1, 2)
    assert (event.vault, event.renting, event.token_id) == (vault, renting.address, 2)
    assert extension.vaults(renting.tokenid_to_vault(1)) == (1, 1)


def test_register_vaults_again(extension, renting):
    extension.register_vaults(renting.address, [1])
    extension.register_vaults(renting.address, [1, 1])
    assert extension.vaults(renting.tokenid_to_vault(1)) == (1, 1)


def test_vault_whitelisted_while_owning_its_token(extension, renting, nft_contract, nft_owner, deposit):
    vault = renting.tokenid_to_vault(1)
    extension.register_vaults(renting.address, [1])
    assert not extension.isWhitelisted(nft_contract.address, vault)

    deposit(renting, 1)
    assert extension.isWhitelisted(nft_contract.address, vault)

    renting.withdraw([TokenContext(1, nft_owner).to_tuple()], sender=nft_owner)
    assert nft_contract.ownerOf(1) == nft_owner
    assert not extension.isWhitelisted(nft_contract.address, vault)


def test_vault_owning_other_token(extension, renting, nft_contract, owner):
    vault = renting.tokenid_to_vault(1)
    extension.register_vaults(renting.address, [1])
    nft_contract.mint(vault, 2, sender=owner)
    assert not extension.isWhitelisted(nft_contract.address, vault)


def test_vault_owning_same_token_id_of_other_collection(extension_def, renting, deploy_renting):
    # the other collection also has a market, so only the collection check prevents the vault from being whitelisted
    other_collection = boa.load("contracts/auxiliary/ERC721.vy")
    extension = extension_def.deploy([renting.address, deploy_renting(other_collection.address).address])
    vault = renting.tokenid_to_vault(1)
    extension.register_vaults(renting.address, [1])
    other_collection.mint(vault, 1, sender=boa.env.eoa)

    assert other_collection.ownerOf(1) == vault
    assert not extension.isWhitelisted(other_collection.address, vault)


def test_unregistered_vault(extension, renting, nft_contract, deposit):
    vault = deposit(renting, 1)
    assert not extension.isWhitelisted(nft_contract.address, vault)


def test_vault_of_other_collection(extension, renting, nft_contract, deposit, empty_contract_def):
    vault = deposit(renting, 1)
    extension.register_vaults(renting.address, [1])
    assert extension.isWhitelisted(nft_contract.address, vault)
    for collection in [empty_contract_def.deploy().address, ZERO_ADDRESS, renting.address]:
        assert not extension.isWhitelisted(collection, vault)


def test_vault_lookalike(extension, renting, nft_contract, owner, vault_impl, vault_contract_def):
    # same code as a vault, initialised by the renting contract and owning a token, but not deployed by the renting contract
    lookalike = vault_contract_def.at(deploy_minimal_proxy(vault_impl.address, boa.env.generate_address()))
    lookalike.initialise(sender=renting.address)
    nft_contract.mint(lookalike.address, 1, sender=owner)
    extension.register_vaults(renting.address, [1])

    assert lookalike.caller() == renting.address
    assert extension.vaults(lookalike.address) == (0, 0)
    assert not extension.isWhitelisted(nft_contract.address, lookalike.address)


def test_non_vault_accounts(extension, renting, nft_contract, vault_impl):
    for account in [ZERO_ADDRESS, boa.env.generate_address(), renting.address, vault_impl.address, nft_contract.address]:
        assert not extension.isWhitelisted(nft_contract.address, account)


def test_markets_sharing_collection(extension_def, deploy_renting, nft_contract, nft_owner, deposit):
    renting_a, renting_b = deploy_renting(nft_contract.address), deploy_renting(nft_contract.address)
    extension = extension_def.deploy([renting_a.address, renting_b.address])
    vault_a, vault_b = renting_a.tokenid_to_vault(1), deposit(renting_b, 1)
    extension.register_vaults(renting_b.address, [1])

    assert extension.vaults(vault_a) == (0, 0)
    assert extension.vaults(vault_b) == (2, 1)
    assert extension.isWhitelisted(nft_contract.address, vault_b)

    renting_b.withdraw([TokenContext(1, nft_owner).to_tuple()], sender=nft_owner)
    nft_contract.approve(vault_a, 1, sender=nft_owner)
    renting_a.deposit([1], ZERO_ADDRESS, sender=nft_owner)
    extension.register_vaults(renting_a.address, [1])

    assert extension.vaults(vault_a) == (1, 1)
    assert extension.isWhitelisted(nft_contract.address, vault_a)
    assert not extension.isWhitelisted(nft_contract.address, vault_b)


# `ownerOf` failure modes, using collections whose `ownerOf` returns or reverts with the words in storage slots 0 and 1

LOAD_WORDS = "600054600052" + "600154602052"  # mstore(0, sload(0)), mstore(32, sload(1))


@pytest.mark.parametrize(
    ("name", "runtime", "dirty", "expected"),
    [
        ("returns the vault", LOAD_WORDS + "60206000f3", False, True),
        ("returns the vault plus a word", LOAD_WORDS + "60406000f3", False, False),
        ("returns 20 bytes", LOAD_WORDS + "60146000f3", False, False),
        ("returns the vault with dirty upper bits", LOAD_WORDS + "60206000f3", True, False),
        ("reverts with the vault", LOAD_WORDS + "60206000fd", False, False),
        ("reverts", "60006000fd", False, False),
        ("invalid opcode", "fe", False, False),
        ("returns nothing", "00", False, False),
        ("burns all gas", "5b600056", False, False),
    ],
)
def test_owner_of_call(extension_def, deploy_renting, name, runtime, dirty, expected):
    collection = deploy_runtime(bytes.fromhex(runtime))
    renting = deploy_renting(collection)
    extension = extension_def.deploy([renting.address])
    vault = renting.tokenid_to_vault(1)
    extension.register_vaults(renting.address, [1])
    vault_word = int.from_bytes(word(vault))
    boa.env.set_storage(collection, 0, vault_word | (0xFF << 248 if dirty else 0))
    boa.env.set_storage(collection, 1, vault_word)

    assert extension.isWhitelisted(collection, vault) == expected, name
    assert extension._computation.get_gas_used() < extension.OWNER_OF_GAS() + 20_000
