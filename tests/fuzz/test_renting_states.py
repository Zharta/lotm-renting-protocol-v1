import boa

from ..conftest_base import Rental, Listing, ZERO_ADDRESS

import hypothesis.strategies as st
from hypothesis import Verbosity, Phase, settings, assume
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    consumes,
    initialize,
    invariant,
    multiple,
    rule,
    run_state_machine_as_test,
)

INITIAL_BALANCE = int(1e21)


class StateMachine(RuleBasedStateMachine):
    renting = None
    ape = None
    nft = None
    warm = None
    vault = None

    owners = [boa.env.generate_address() for _ in range(3)]
    renters = [boa.env.generate_address() for _ in range(3)]
    tokens = Bundle("tokens")
    tokens_not_in_vaults = Bundle("tokens_not_in_vaults")
    tokens_in_vaults = Bundle("tokens_in_vaults")
    tokens_in_rental = Bundle("tokens_in_rental")

    @initialize()
    def setup(self):
        self.rentals = {}
        self.listing_price = {}
        self.rewards = {owner: 0 for owner in self.owners}
        self.paid = {renter: 0 for renter in self.renters}
        self.claimed = {owner: 0 for owner in self.owners}
        self.vaults = dict()  # token: address

        for renter in self.renters:
            self.ape.mint(renter, INITIAL_BALANCE, sender=self.ape.minter())

    @initialize(targets=[tokens, tokens_not_in_vaults])
    def setup_tokens(self):
        token_count = 100
        owners_count = len(self.owners)

        tokens = list(range(token_count))
        self.owner_of = {t: self.owners[t % owners_count] for t in tokens}
        self.tokens_of = {self.owners[i]: list(range(i, token_count, owners_count)) for i in range(owners_count)}

        for token in tokens:
            self.nft.mint(self.owner_of[token], token, sender=self.nft.minter())

        return multiple(*tokens)

    @rule(hours=st.integers(min_value=1, max_value=24))
    def time_passing(self, hours):
        boa.env.time_travel(seconds=hours * 3600)

    @rule(token=tokens_not_in_vaults, new_owner=st.sampled_from(owners))
    def token_transfer(self, token, new_owner):
        owner = self.owner_of[token]
        assume(new_owner != owner)
        self.nft.transferFrom(owner, new_owner, token, sender=owner)
        self.owner_of[token] = new_owner
        self.tokens_of[owner].remove(token)
        self.tokens_of[new_owner].append(token)

    @rule(token=tokens_in_vaults, new_price=st.integers(min_value=0, max_value=10**6))
    def change_listing_price(self, token, new_price):
        owner = self.owner_of[token]
        self.renting.set_listing_price(token, new_price, sender=owner)
        self.listing_price[token] = new_price

    @rule(token=tokens_in_vaults)
    def cancel_listing(self, token):
        owner = self.owner_of[token]
        self.renting.cancel_listing(token, sender=owner)
        self.listing_price[token] = 0

    # FAQ:
    # fees
    # delegaion to owner?
    # max rental period?

    @rule(target=tokens_in_vaults, token=consumes(tokens_not_in_vaults), price=st.integers(min_value=0, max_value=10**6))
    def deposit(self, token, price):
        now = boa.eval("block.timestamp")
        owner = self.owner_of[token]

        assume(token not in self.rentals or self.rentals[token].expiration < now)

        vault = self.renting.tokenid_to_vault(token)
        self.nft.approve(vault, token, sender=owner)
        if token in self.vaults:
            self.renting.deposit(token, price, sender=owner)
        else:
            self.renting.create_vault_and_deposit(token, price, sender=owner)

        self.vaults[token] = self.vault.at(vault)
        self.listing_price[token] = price
        if token in self.rentals:
            del self.rentals[token]

        return token

    @rule(target=tokens_not_in_vaults, token=consumes(tokens_in_vaults))
    def withdraw(self, token):
        now = boa.eval("block.timestamp")
        owner = self.owner_of[token]

        assume(token not in self.rentals or self.rentals[token].expiration < now)

        claimable_rewards = self.vaults[token].claimable_rewards()
        assert claimable_rewards <= self.ape.balanceOf(self.vaults[token])

        self.claimed[owner] += claimable_rewards
        self.renting.withdraw(token, sender=owner)

        del self.listing_price[token]
        if token in self.rentals:
            del self.rentals[token]

        return token

    @rule(
        target=tokens_in_rental,
        token=consumes(tokens_in_vaults),
        renter=st.sampled_from(renters),
        hours=st.integers(min_value=0, max_value=100),
    )
    def start_rental_from_tokens_in_vaults(self, token, renter, hours):
        now = boa.eval("block.timestamp")
        owner = self.owner_of[token]
        expiration = now + hours * 3600

        assume(self.listing_price[token] > 0)
        # assume(token not in self.rentals or self.rentals[token].expiration < now)

        self.ape.approve(self.vaults[token], max(0, self.listing_price[token] * hours), sender=renter)
        self.renting.start_rental(token, expiration, sender=renter)

        rental = Rental(*self.vaults[token].active_rental())
        self.rentals[token] = rental
        self.paid[renter] += rental.amount
        self.rewards[owner] += rental.amount

        return token

    @rule(
        token=tokens_in_rental,
        renter=st.sampled_from(renters),
        hours=st.integers(min_value=0, max_value=100),
    )
    def start_rental_from_tokens_in_rental(self, token, renter, hours):
        now = boa.eval("block.timestamp")
        owner = self.owner_of[token]
        expiration = now + hours * 3600

        assume(self.listing_price[token] > 0)
        assume(self.rentals[token].expiration < now)

        self.ape.approve(self.vaults[token], max(0, self.listing_price[token] * hours), sender=renter)
        self.renting.start_rental(token, expiration, sender=renter)

        rental = Rental(*self.vaults[token].active_rental())
        self.rentals[token] = rental
        self.paid[renter] += rental.amount
        self.rewards[owner] += rental.amount

    @rule(target=tokens_in_vaults, token=consumes(tokens_in_rental))
    def close_rental(self, token):
        now = boa.eval("block.timestamp")
        rental = self.rentals[token]

        assume(rental.expiration >= now)
        rental_amount = (now - rental.start) * rental.amount // (rental.expiration - rental.start)
        amount_to_return = rental.amount - rental_amount

        balance_before = self.ape.balanceOf(rental.renter)
        self.renting.close_rental(token, sender=rental.renter)
        balance_after = self.ape.balanceOf(rental.renter)

        new_rental = Rental(*self.vaults[token].active_rental())

        assert balance_after - balance_before == amount_to_return
        assert new_rental.amount == 0

        del self.rentals[token]
        self.paid[rental.renter] -= amount_to_return
        self.rewards[rental.owner] -= amount_to_return

        return token

    @rule(token=tokens_in_vaults)
    def claim_from_tokens_in_vaults(self, token):
        owner = self.owner_of[token]
        claimable_rewards = self.vaults[token].claimable_rewards()
        if claimable_rewards > 0:
            self.renting.claim(token, sender=owner)
            self.claimed[owner] += claimable_rewards

    @rule(token=tokens_in_rental)
    def claim_from_tokens_in_rentals(self, token):
        owner = self.owner_of[token]
        claimable_rewards = self.vaults[token].claimable_rewards()
        if claimable_rewards > 0:
            self.renting.claim(token, sender=owner)
            self.claimed[owner] += claimable_rewards

    @invariant()
    def avoid_simultaneous_actions(self):
        boa.env.time_travel(seconds=1)

    @invariant()
    def check_vaults(self):
        for token, vault in self.vaults.items():
            if token in self.listing_price:
                assert not self.renting.is_vault_available(token)
                assert self.renting.tokenid_to_vault(token) == vault.address
                assert self.renting.active_vaults(token) == vault.address
                listing = Listing(*vault.listing())
                assert listing.token_id == token
                assert listing.price == self.listing_price[token]
                assert self.nft.ownerOf(token) == vault.address
            else:
                assert self.renting.is_vault_available(token)
                assert self.renting.active_vaults(token) == ZERO_ADDRESS
                assert self.nft.ownerOf(token) == self.owner_of[token]

    @invariant()
    def check_ape_balance(self):
        for renter, amount in self.paid.items():
            assert self.ape.balanceOf(renter) == INITIAL_BALANCE - amount
        for owner, amount in self.claimed.items():
            assert self.ape.balanceOf(owner) == amount

    @invariant()
    def check_rewards(self):
        for owner, rewards in self.rewards.items():
            owner_vaults = [self.vaults[t] for t in self.tokens_of[owner] if t in self.vaults]
            pending_claiming = sum(Rental(*v.active_rental()).amount + v.unclaimed_rewards() for v in owner_vaults)
            assert rewards == self.claimed[owner] + pending_claiming

    @invariant()
    def check_delegation(self):
        now = boa.eval("block.timestamp")
        for token, rental in self.rentals.items():
            if rental.expiration >= now:
                assert self.warm.getHotWallet(self.vaults[token]) == rental.renter
            else:
                assert self.warm.getHotWallet(self.vaults[token]) == ZERO_ADDRESS

    def teardown(self):
        pass


def test_renting_states(renting_contract, ape_contract, nft_contract, delegation_registry_mock, vault_contract_def):
    StateMachine.renting = renting_contract
    StateMachine.ape = ape_contract
    StateMachine.nft = nft_contract
    StateMachine.warm = delegation_registry_mock
    StateMachine.vault = vault_contract_def

    StateMachine.TestCase.settings = settings(
        # max_examples=1000,
        # stateful_step_count=10,
        # verbosity=Verbosity.verbose,
        phases=tuple(Phase)[:Phase.shrink],
        deadline=10 * 1000,
    )
    run_state_machine_as_test(StateMachine)
