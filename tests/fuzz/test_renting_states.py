import random

import boa
import hypothesis.strategies as st
from hypothesis import Phase, assume, settings
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

from ..conftest_base import (
    ZERO_ADDRESS,
    ZERO_BYTES32,
    Listing,
    Rental,
    RentalLog,
    RewardLog,
    TokenContext,
    compute_state_hash,
    get_last_event,
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
        self.active_rental = {}
        self.listing = {}
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

    @rule(
        token=tokens_in_vaults,
        new_price=st.integers(min_value=1, max_value=10**6),
        min_duration=st.integers(min_value=0, max_value=50),
        max_duration=st.integers(min_value=50, max_value=100),
    )
    def change_listings_prices(self, token, new_price, min_duration, max_duration):
        owner = self.owner_of[token]
        token_context = TokenContext(token, self.active_rental[token], self.listing[token])
        self.renting.set_listings(
            [token_context.to_tuple()], new_price, min_duration, max_duration, ZERO_ADDRESS, sender=owner
        )
        self.listing[token] = Listing(token, new_price, min_duration, max_duration)

    @rule(token=tokens_in_vaults)
    def cancel_listings(self, token):
        owner = self.owner_of[token]
        token_context = TokenContext(token, self.active_rental[token], self.listing[token])
        self.renting.cancel_listings([token_context.to_tuple()], ZERO_ADDRESS, sender=owner)
        self.listing[token] = Listing(token_id=token)

    @rule(
        target=tokens_in_vaults,
        token=consumes(tokens_not_in_vaults),
        price=st.integers(min_value=1, max_value=10**6),
        min_duration=st.integers(min_value=0, max_value=50),
        max_duration=st.integers(min_value=50, max_value=100),
    )
    def deposit(self, token, price, min_duration, max_duration):
        now = boa.eval("block.timestamp")
        owner = self.owner_of[token]

        assume(token not in self.active_rental or self.active_rental[token].expiration < now)

        vault = self.renting.tokenid_to_vault(token)
        self.nft.approve(vault, token, sender=owner)
        if token in self.vaults:
            self.renting.deposit([token], price, min_duration, max_duration, ZERO_ADDRESS, sender=owner)
        else:
            self.renting.create_vaults_and_deposit([token], price, min_duration, max_duration, ZERO_ADDRESS, sender=owner)

        self.vaults[token] = self.vault.at(vault)
        self.listing[token] = Listing(token, price, min_duration, max_duration)
        self.active_rental[token] = Rental()

        return token

    @rule(target=tokens_not_in_vaults, token=consumes(tokens_in_vaults))
    def withdraw(self, token):
        now = boa.eval("block.timestamp")
        owner = self.owner_of[token]

        assume(token not in self.active_rental or self.active_rental[token].expiration < now)

        claimable_rewards = self.vaults[token].claimable_rewards(self.active_rental[token].to_tuple())

        assert claimable_rewards <= self.ape.balanceOf(self.vaults[token])

        token_context = TokenContext(token, self.active_rental[token], self.listing[token])

        self.claimed[owner] += claimable_rewards
        self.renting.withdraw([token_context.to_tuple()], sender=owner)

        del self.listing[token]
        if token in self.active_rental:
            del self.active_rental[token]

        return token

    @rule(target=tokens_in_rental, token=consumes(tokens_in_vaults), renter=st.sampled_from(renters))
    def start_rental_from_tokens_in_vaults(self, token, renter):
        owner = self.owner_of[token]

        listing = self.listing[token]
        min_duration = listing.min_duration
        max_duration = listing.max_duration
        hours = random.randint(min_duration, max_duration) if max_duration else random.randint(min_duration, 100)

        assume(self.listing[token].price > 0)

        self.ape.approve(self.vaults[token], max(0, self.listing[token].price * hours), sender=renter)
        token_context = TokenContext(token, self.active_rental[token], self.listing[token])
        self.renting.start_rentals([token_context.to_tuple()], hours, renter, sender=renter)

        event = get_last_event(self.renting, "RentalStarted")
        rental = RentalLog(*event.rentals[0]).to_rental(renter)

        self.active_rental[token] = rental
        self.paid[renter] += rental.amount
        self.rewards[owner] += rental.amount

        return token

    @rule(token=tokens_in_rental, renter=st.sampled_from(renters))
    def start_rental_from_tokens_in_rental(self, token, renter):
        now = boa.eval("block.timestamp")
        owner = self.owner_of[token]

        listing = self.listing[token]
        min_duration = listing.min_duration
        max_duration = listing.max_duration
        hours = random.randint(min_duration, max_duration) if max_duration else random.randint(min_duration, 100)

        assume(self.listing[token].price > 0)
        assume(self.active_rental[token].expiration < now)

        self.ape.approve(self.vaults[token], max(0, self.listing[token].price * hours), sender=renter)
        token_context = TokenContext(token, self.active_rental[token], self.listing[token])
        self.renting.start_rentals([token_context.to_tuple()], hours, renter, sender=renter)

        event = get_last_event(self.renting, "RentalStarted")
        rental = RentalLog(*event.rentals[0]).to_rental(renter)

        self.active_rental[token] = rental
        self.paid[renter] += rental.amount
        self.rewards[owner] += rental.amount

    @rule(target=tokens_in_vaults, token=consumes(tokens_in_rental))
    def close_rental(self, token):
        now = boa.eval("block.timestamp")
        rental = self.active_rental[token]

        assume(rental.expiration > now)

        rental_duration = max(now, rental.min_expiration) - rental.start
        rental_amount = rental_duration * rental.amount // (rental.expiration - rental.start)
        amount_to_return = rental.amount - rental_amount

        balance_before = self.ape.balanceOf(rental.renter)
        token_context = TokenContext(token, self.active_rental[token], self.listing[token])
        self.renting.close_rentals([token_context.to_tuple()], sender=rental.renter)
        balance_after = self.ape.balanceOf(rental.renter)

        event = get_last_event(self.renting, "RentalClosed")
        closed_rental = RentalLog(*event.rentals[0]).to_rental(rental.renter)

        assert balance_after - balance_before == amount_to_return
        assert closed_rental.amount == rental_amount

        self.active_rental[token] = Rental()
        self.paid[rental.renter] -= amount_to_return
        self.rewards[rental.owner] -= amount_to_return

        return token

    @rule(token=tokens_in_vaults)
    def claim_from_tokens_in_vaults(self, token):
        owner = self.owner_of[token]
        claimable_rewards = self.vaults[token].claimable_rewards(self.active_rental[token].to_tuple())
        if claimable_rewards > 0:
            token_context = TokenContext(token, self.active_rental[token], self.listing[token])
            self.renting.claim([token_context.to_tuple()], sender=owner)

            event = get_last_event(self.renting, "RewardsClaimed")
            event_reward = RewardLog(*event.rewards[0])
            assert event_reward.amount == claimable_rewards

            self.claimed[owner] += claimable_rewards
            self.active_rental[token].amount = event_reward.active_rental_amount

            claimable_rewards_after = self.vaults[token].claimable_rewards(self.active_rental[token].to_tuple())
            assert claimable_rewards_after == 0

    @rule(token=tokens_in_rental)
    def claim_from_tokens_in_rentals(self, token):
        owner = self.owner_of[token]
        claimable_rewards = self.vaults[token].claimable_rewards(self.active_rental[token].to_tuple())
        if claimable_rewards > 0:
            token_context = TokenContext(token, self.active_rental[token], self.listing[token])
            self.renting.claim([token_context.to_tuple()], sender=owner)

            event = get_last_event(self.renting, "RewardsClaimed")
            event_reward = RewardLog(*event.rewards[0])
            assert event_reward.amount == claimable_rewards

            self.claimed[owner] += claimable_rewards
            self.active_rental[token].amount = event_reward.active_rental_amount

            claimable_rewards_after = self.vaults[token].claimable_rewards(self.active_rental[token].to_tuple())
            assert claimable_rewards_after == 0

    @invariant()
    def avoid_simultaneous_actions(self):
        boa.env.time_travel(seconds=1)

    @invariant()
    def check_vaults(self):
        for token, vault in self.vaults.items():
            if token in self.listing:
                assert not self.renting.is_vault_available(token)
                assert self.renting.tokenid_to_vault(token) == vault.address
                assert self.renting.active_vaults(token) == vault.address
                assert vault.state() == compute_state_hash(self.active_rental[token], self.listing[token])
                assert self.nft.ownerOf(token) == vault.address
            else:
                assert self.renting.is_vault_available(token)
                assert self.renting.active_vaults(token) == ZERO_ADDRESS
                assert self.nft.ownerOf(token) == self.owner_of[token]
                assert vault.state() == ZERO_BYTES32

    @invariant()
    def check_ape_balance(self):
        for renter, amount in self.paid.items():
            assert self.ape.balanceOf(renter) == INITIAL_BALANCE - amount
        for owner, amount in self.claimed.items():
            assert self.ape.balanceOf(owner) == amount

    @invariant()
    def check_rewards(self):
        for owner, rewards in self.rewards.items():
            owner_vaults = [(t, self.vaults[t]) for t in self.tokens_of[owner] if t in self.vaults]
            pending_claiming = sum(
                self.active_rental.get(token_id, Rental()).amount + v.unclaimed_rewards() for token_id, v in owner_vaults
            )
            assert rewards == self.claimed[owner] + pending_claiming

    @invariant()
    def check_delegation(self):
        now = boa.eval("block.timestamp")
        for token, rental in self.active_rental.items():
            if rental.expiration >= now:
                assert self.warm.getHotWallet(self.vaults[token]) == rental.renter
            else:
                assert self.warm.getHotWallet(self.vaults[token]) == ZERO_ADDRESS

    def teardown(self):
        pass


def test_renting_states(renting_contract, ape_contract, nft_contract, delegation_registry_warm_contract, vault_contract_def):
    StateMachine.renting = renting_contract
    StateMachine.ape = ape_contract
    StateMachine.nft = nft_contract
    StateMachine.warm = delegation_registry_warm_contract
    StateMachine.vault = vault_contract_def

    StateMachine.TestCase.settings = settings(
        phases=tuple(Phase)[: Phase.shrink],
        deadline=300 * 1000,
    )
    run_state_machine_as_test(StateMachine)
