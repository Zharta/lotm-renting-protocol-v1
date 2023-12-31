# LOTM Renting Protocol by Zharta

## Introduction

This protocol is targeted at [LOTM](https://lotm.otherside.xyz/) from Yuga Labs. The protocol serves as a trustless way for LOTM players to rent game assets from users.

There are two major domains in the protocol:
* the vaults
* the renting logic

The Renting a game asset in the context of this protocol means that a user deposits the asset in a vault and the


## Overview

| **Version** | **Language** | **Reference implementation**                       |
| ---         | ---          | ---                                                |
| V1          | Vyper 0.3.9  | https://github.com/Zharta/lotm-renting-protocol-v1 |

There are two major domains in the protocol:
* the vaults
* the renting logic

The renting of an NFT in the context of this protocol means that:
1. an asset owner deposits the NFT in a vault, setting the terms of the rental: price and minimum/maximum rental duration
2. a user (renter) selects the NFT put for rental and starts the rental by paying for the rental upfront
3. the vault where the NFT asset is escrowed delegates it to a renter's specified wallet for a specific duration
4. once the duration of the rental is reached, the rental finishes

## General considerations

The current status of the protocol follows certain assumptions.

The assumptions are the following:
1. delegation is supported using [warm.xyz](https://warm.xyz)
2. the current version of [warm.xyz](https://warm.xyz) if the same as the last verified version seen [here](https://etherscan.io/address/0xad0b7f45750f2211b55a1218f907e67dfac841fa#code)
3. because [warm.xyz](https://warm.xyz) does not support NFT-level delegation and only supports wallet-level delegation, one vault per NFT needs to be created


## Security
Below are the smart contract audits performed for the protocol so far:

| **Auditor** 	| **Version** 	| **Status** 	| **PDF** 	                            |
|:-----------:	|:----------:	|:----------:	|---------	                            |
| Hacken      	| V1    	    | Done    	    | [PDF](audits/Audit_Hacken.pdf)  	    |
| Hacken      	| V1.5    	    | Done    	    | [PDF](audits/Audit_Hacken_v15.pdf)  	|

## Architecture

As previously stated, there are two domains of the protocol:
* the vaults implemented in [`Vault.vy`](https://github.com/Zharta/lotm-renting-protocol-v1/blob/main/contracts/Vault.vy)
* the renting logic implemented in [`Renting.vy`](https://github.com/Zharta/lotm-renting-protocol-v1/blob/main/contracts/Renting.vy)

Users and other protocols should always interact with the [`Renting.vy`](https://github.com/Zharta/lotm-renting-protocol-v1/blob/main/contracts/Renting.vy) contract. The `Renting.vy` contract is the entry point of the protocol and it is responsible for:
* NFT owners depositing NFTs in the protocol, which means a vault is created for each NFT
* NFT owners defining the terms of the rentals: price and minimum/maximum rental duration
* renters starting rentals
* renters closing rentals before the due date
* NFT owners claiming unclaimed fees
* NFT owners withdrawing NFTs from the protocol

### Vaults and NFT deposits

Each NFT put for rental needs to be in its own vault (see the 3rd point in [General considerations](#general-considerations)). This means that when an NFT owner wants to deposit an NFT in the protocol, the NFT owner may need to create the vault prior to depositing the NFT. If the vault for that specific NFT has already been created before, it can be reused.

**NFT owners do not need to create the vaults themselves, the protocol will create the vaults when needed.**

The protocol creates the vaults using minimal proxies and the `CREATE2` opcode. This means that when a vault for a specific NFT needs to be created, the protocol is able to compute the destination address of the vault before creating it and the user may approve the NFT to be transferred. Therefore, creating the vault and depositing the NFT can be done atomically.

### Rentals

Whenever a rental starts, the renter pays the full amount of the rental upfront. This amount is locked in the NFT vault until the end of the rental. Once the rental finishes, the rental amount is released to the NFT owner for claiming. Since the protocol is using [warm.xyz](https://warm.xyz) which supports setting a specific timestamp for the end of the delegation, the protocol computes the amount of fees that are claimable taking this into consideration. Unclaimed fees are only set explicitly for certain actions:
1. `claim`: the NFT owner claims unclaimed fees
2. `withdraw`: the NFT owner withdraws the NFT from the vault, along with any unclaimed fees
3. `start_rental`: a renter starts the rental and the previous rental fees, if not claimed, are set explicitly as unclaimed
4. `close_rental`: a renter may finish a rental before its due date and pays only for the time used, and unclaimed fees are explicitly set

### Roles

The protocol does supports an admin role, with exclusive purpose of setting the protocol fees parameter. The only roles are the following:
* `Renting.vy`:
    * `admin`: the protocol admin with permissions limited to set the value of protocol fees (up to a fixed limit) and the protocol wallet that receives those fees. The `admin` value can be changed via the `propose_admin` and `claim_ownership` functions.
* `Vault.vy`:
    * `owner`: the owner of the NFT that is escrowed in vault, which means that only this address can perform certain actions against the vault, but those action still need to be performed through the `Renting.vy` contract

### Delegation

The protocol uses [warm.xyz](https://warm.xyz) to perform wallet level delegation of the vaults. At any moment, at most one delegation is active, meaning that setting a new hot wallet cancels any ongoing delegation. The usage of delegation happens as following:
* Renter:
    * `start_rentals`: when initiating a rental, the renter specifies a `delegate` which will be used as the vault hot wallet for the specified rental duration.
    * `close_rentals`: if the renter cancels the rental, the delegation is also removed.
* NFT Owner:
    * `deposit`, `set_listings`, `cancel_listings`: as part of these operations, an optional `delegate` can be set. If not empty, it is set as the vault hot wallet without expiration period.
    * `delegate_to_wallet`: at any time that a rental is not ongoing, the vault owner can use this function to set a new delegate as the vault hot wallet without expiration period.


### Protocol fees

The protocol supports the definition of a fee to be applied over the rental's amount. It works as following:

* The `Renting.vy` contract stores the `protocol_fee` and `protocol_wallet` values, which are used as parameters when a new rental is created (`Vault.start_rental`).
* For each rental, the `protocol_fee` and `protocol_wallet` initially defined are not changed, meaning the conditions defined during rental creation are valid for the full life of the rental.
* The `admin` role can change both the `protocol_fee` and `protocol_wallet`, which become valid for every new rental thereafter.
* At deployment time a `max_protocol_fee` is set, which limits the max possible `protocol_fee` value that the `admin` can set. This value can't be changed.
* Protocol fees follow a simliar process to rental rewards, meaning that they can be acumulated and transfered on specific actions: `withdraw`, `claim` and `close_rental`
* In case of early rental cancelation (`close_rental`) the fees are applied over the pro-rata rental amount, similary to the rewards.


## Development

### Implementation

#### Renting contract (`Renting.vy`)

The renting contract is the single user-facing contract for each Renting Market. This contract does not hold any assets, it manages the creation of vaults (as minimal proxies to the vault implementation) and delegates the calls to the vaults, with the exception of the admin functions.

##### State variables

| **Variable**             | **Type**                    | **Mutable** | **Desciption**                                                                                                                                                |
| ---                      | ---                         | :-:         | ---                                                                                                                                                           |
| vault_impl_addr          | `address`                   | No          | address of the Vault implementation contract for the renting market                                                                                           |
| payment_token_addr       | `address`                   | No          | address of the payment token (ERC20) contract for the renting market                                                                                          |
| nft_contract_addr        | `address`                   | No          | address of the NFT (ERC721) contract for the renting market                                                                                                   |
| delegation_registry_addr | `address`                   | No          | address of the delegation (warm.xyz) contract                                                                                                                 |
| max_protocol_fee         | `uint256`                   | No          | maximum value for the admin configurable `protocol_fee` parameter                                                                                             |
| protocol_wallet          | `address`                   | Yes         | wallet address to receive the protocol fees                                                                                                                   |
| protocol_fee             | `uint256`                   | Yes         | fraction of the rentals' values (in bps) to be paid as fee                                                                                                    |
| protocol_admin           | `address`                   | Yes         | wallet address of the protocol admin                                                                                                                          |
| proposed_admin           | `address`                   | Yes         | wallet to be proposed as admin by using the `propose_admin` function, it becomes the `protocol_admin` after the wallet claims it by calling `claim_ownership` |
| active_vaults            | `HashMap[uint256, address]` | Yes         | map of active vaults: a vault becomes active upon a deposit and is deactivated after a withdraw                                                               |


##### Relevant external functions


| **Function**              | **Roles Allowed**    | **Modifier** | **Description**                                                                                                                 |
| ---                       | :-:                  | ---          | ---                                                                                                                             |
| create_vaults_and_deposit | Any (becomes Owner)  | Nonpayable   | creates and initializes vaults for given tokens and delegates for each vault the deposit of the token and creation of a listing |
| deposit                   | Owner                | Nonpayable   | initializes exisintg vaults for given tokens and delegates for each vault the deposit of the token  and creation of a listing   |
| set_listings              | Owner                | Nonpayable   | delegates call to each token's vault to change the listing conditions                                                           |
| cancel_listings           | Owner                | Nonpayable   | delegates call to each token's vault to cancel the listing (listing price = 0)                                                  |
| start_rentals             | Any (becomes Renter) | Nonpayable   | delegates call to each token's vault to start a rental for the specified duration                                               |
| close_rentals             | Renter               | Nonpayable   | delegates call to each token's vault to perform an early cancelation of the active rental                                       |
| claim                     | Owner                | Nonpayable   | delegates call to each token's vault to claim all unclaimed owner rewards                                                       |
| withdraw                  | Owner                | Nonpayable   | after delegating calls to each token's vault to withdraw it and claim pending rewards, marks the vault as inactive              |
| delegate_to_wallet        | Owner                | Nonpayable   | delegates call to each token's vault to perform a delegation to a given hot wallet                                              |
| set_protocol_fee          | Admin                | Nonpayable   | sets the protocol fee (in bps) to be charged for each rental                                                                    |
| change_protocol_wallet    | Admin                | Nonpayable   | changes the wallet address to reveive the protcol fees                                                                          |
| propose_admin             | Admin                | Nonpayable   | sets the `proposed_admin` variable, which can then claim ownership                                                              |
| claim_ownership           | *proposed owner*     | Nonpayable   | claims ownership of the contract, setting the `protocol_admin` variable                                                         |
| is_vault_available        | Any                  | View         | checks if the vault for a given token already exists and if is not active                                                       |
| tokenid_to_vault          | Any                  | View         | returns the address of an existing or yet to be created vault, allowing asset approvals for deposits or creation of rentals     |


#### Vault implementation contract (`Vault.vy`)

The Vault is the implementation contract for each vault, which is deployed as a minimal proxy (ERC1167) by `Renting.vy` and accepts only calls from it. This contract holds the assets (NFT, payment tokens) for each token, holds the listing and rental states, performs rewards and fee payments and sets the delegation to hot wallets.

##### State variables

| **Variable**             | **Type**  | **Mutable** | **Desciption**                                                                                                                                   |
| ---                      | ---       | :-:         | ---                                                                                                                                              |
| payment_token_addr       | `address` | No          | address of the payment token (ERC20) contract for the renting market                                                                             |
| nft_contract_addr        | `address` | No          | address of the NFT (ERC721) contract for the renting market                                                                                      |
| delegation_registry_addr | `address` | No          | address of the delegation (warm.xyz) contract                                                                                                    |
| owner                    | `address` | Yes         | wallet address of the owner of the deposited token                                                                                               |
| caller                   | `address` | Yes         | address of the Renting contract who deployed and manages the vault                                                                               |
| state                    | `bytes32` | Yes         | hash of the current vault state, which is externalized to reduce the gas costs associated with storage; empty means the vault is not initialized |
| unclaimed_rewards        | `uint256` | Yes         | keeps the amount of the owner's unclaimed rewards, which result from rentals expiration and must be accounted for later claim                    |
| unclaimed_protocol_fee   | `uint256` | Yes         | keeps the amount of unclaimed protocol fees, which result from rentals expiration and must be accounted for later payment                        |


##### Externalized State

The information regarding listings and rentals was externalized in order to reduce the gas costs while using the protocol. That requires the state to be passed as an argument to each function and validated by matching it's hash against the one stored in the contract. Conversly, changes to the state are hashed and stored, and the resulting state variables returned to the caller (the Renting contract), to either be published as events or returned directly to the user. The structures that hold the state are the `Listing` and the `Rentals`, although not every member is part of the state if is not required to keep the integrity of the contract.

| **Struct** | **Variable**    | **Type**  | **Part of State** | **Desciption**                                                                                                               |
| ---        | ---             | ---       | :-:               | ---                                                                                                                          |
| Rental     | id              | `bytes32` | Yes               | id of a rental, calculated as the keccak256 of the renter, token_id, start and expiration; empty if there's no active rental |
|            | owner           | `address` | Yes               | wallet address owner of the deposited NFT                                                                                    |
|            | renter          | `address` | Yes               | wallet address renting the NFT                                                                                               |
|            | delegate        | `address` | No                | used as hot wallet during the rental period                                                                                  |
|            | token_id        | `uint256` | Yes               | id of the deposited token                                                                                                    |
|            | start           | `uint256` | Yes               | timestamp marking the start of the rental period                                                                             |
|            | min_expiration  | `uint256` | Yes               | timestamp marking the minimal period charged in case of rental cancelation by the renter                                     |
|            | expiration      | `uint256` | Yes               | timestamp marking the end of the rental period                                                                               |
|            | amount          | `uint256` | Yes               | amount (of the payment token) to be paid by the renter for the rental                                                        |
|            | protocol_fee    | `uint256` | Yes               | fee in bps to be charged for the rental                                                                                      |
|            | protocol_wallet | `address` | Yes               | wallet to receive the protocol fee                                                                                           |
|            |                 |           |                   |                                                                                                                              |
| Listing    | token_id        | `uint256` | Yes               | id of the deposited token                                                                                                    |
|            | price           | `uint256` | Yes               | price per hour, 0 means not listed                                                                                           |
|            | min_duration    | `uint256` | Yes               | min duration in hours                                                                                                        |
|            | max_duration    | `uint256` | Yes               | max duration in hours, 0 means unlimited                                                                                     |

##### Relevant external functions


| **Function**       | **Roles Allowed** | **Modifier** | **Description**                                                                                                                                                                                                                                                 |
| ---                | :-:               | ---          | ---                                                                                                                                                                                                                                                             |
| initialise         | --                | Nonpayable   | called by Renting to set up the initial vault state                                                                                                                                                                                                             |
| deposit            | Any               | Nonpayable   | transfers the token from the user to the vault, optionaly creates a listing and sets up a delegation to a given wallet                                                                                                                                          |
| set_listing        | Any               | Nonpayable   | changes the listing conditions and optionaly sets up a delegation to a given wallet                                                                                                                                                                             |
| start_rental       | Any               | Nonpayable   | creates a rental for a given renter and expiration, transfers the calculated rental amount from the renter to the vault and and creates the delegation to the given wallet                                                                                      |
| close_rental       | Any               | Nonpayable   | cancels the delegation, calculates the pro-rata rental amount and protocol fees, accounts for the revised amount as unclaimed rewards and transfers the excess amount to the renter; also transfers the rental fees and any pending fees to the protocol wallet |
| claim              | Any               | Nonpayable   | transfers any unclaimed rewards to the owner and any pending protocol fees to the protocol wallet                                                                                                                                                               |
| withdraw           | Any               | Nonpayable   | transfers the token back to the owner together with any pending rewards, transfers any pending protocolo fees and uninitializes the vault                                                                                                                       |
| delegate_to_wallet | Any               | Nonpayable   | creates a delegation for a given wallet if no rental is active                                                                                                                                                                                                  |
| claimable_rewards  | Any               | Nonpayable   | calculates the amount of rewards claimable by the owner; it does not validate the input state as it is a convenience and has no side effects                                                                                                                    |
| is_initialised     | Any               | Nonpayable   | return wether the vault is currently initialized                                                                                                                                                                                                                |

### Testing

There are three types of tests implemented, running on py-evm using titanoboa:
1. Unit tests focus on individual functions for each contract, mocking external dependencies (ERC20, ERC721 and warm.xyz HotWallet)
2. Integration tests run on a forked chain, testing the integration between the contracts in the protocol and real implementations of the external dependencies
3. Fuzz tests implement stateful testing, validating that invariants are kept over multiple interactions with the protocol

Additionaly, under `contracts/auxiliary` there are mock implementations of external dependencies **which are NOT part of the protocol** and are only used to support deployments in private and test networks:
```
contracts/
└── auxiliary
    ├── ERC20.vy
    ├── ERC721.vy
    └── HotWalletMock.vy
```
The `ERC20.vy` and `ERC721.vy` contracts are used to deploy mock ERC20 and ERC721 tokens, respectively. The `HotWalletMock.vy` contract is used to deploy a mock implementation of the [warm.xyz](https://warm.xyz) delegation contract.

### Run the project

Run the following command to set everything up:
```
make install-dev
```

To run the tests:
* unit tests
```
make unit-tests
```
* integration tests
```
make integration-tests
```
* fuzz tests
```
make fuzz-tests
```
* gas profiling
```
make gas
```

### Deployment

For each environment a makefile rule is available to deploy the contracts, eg for DEV:
```
make deploy-dev
```

Because the protocol dependends on external contracts that may not be available in all environments, mocks are also deployed to replace them if needed.


| **Stage** | **Network**     | **Payment Contract**                                 | **NFT Contract**                                                                                        | **Delegation Contract**                                              |
| ---       | ---             | ---                                                  | ---                                                                                                     | ---                                                                  |
| DEV       | Private network | Mock (`ERC20.vy`)                                    | Mock (`ERC721.vy`)                                                                                      | Mock (`HotWalletMock.vy`)                                            |
| INT       | Sepolia         | Mock (`ERC20.vy`)                                    | Mock (`ERC721.vy`)                                                                                      | warm.xyz HotWalletProxy `0x050e78c41339DDCa7e5a25c554c6f2C3dbB95dC4` |
| PROD      | Mainnet         | ApeCoin `0x4d224452801ACEd8B2F0aebE155379bb5D594381` | Koda `0xE012Baf811CF9c05c408e879C399960D1f305903` and Mara `0x3Bdca51226202Fc2a64211Aa35A8d95D61C6ca99` | warm.xyz HotWalletProxy `0xC3AA9bc72Bd623168860a1e5c6a4530d3D80456c` |

Additionaly, for each Renting Market in each environment (eg Koda Renting Market in PROD), the following contracts are deployed:

| **Contract** | **Deployment parameters**            | **Description**                                                      |
| ---          | ---                                  | ---                                                                  |
| `Renting.vy` | `_vault_impl_addr: address`          | address of the Vault implementation contract for the renting market  |
|              | `_payment_token_addr: address`       | address of the payment token (ERC20) contract for the renting market |
|              | `_nft_contract_addr: address`        | address of the NFT (ERC721) contract for the renting market          |
|              | `_delegation_registry_addr: address` | address of the delegation (warm.xyz) contract                        |
|              | `_max_protocol_fee: uint256`         | maximum value for the admin configurable `protocol_fee` parameter    |
|              | `_protocol_fee: uint256`             | fraction of the rentals' values (in bps) to be paid as fee           |
|              | `_protocol_wallet: address`          | wallet address to receive the protocol fees                          |
|              | `_protocol_admin: address`           | wallet address of the protocol admin                                 |
|              |                                      |                                                                      |
| `Vault.vy`   | `_payment_token_addr: address`       | address of the payment token (ERC20) contract for the renting market |
|              | `_nft_contract_addr: address`        | address of the NFT (ERC721) contract for the renting market          |
|              | `_delegation_registry_addr: address` | address of the delegation (warm.xyz) contract                        |
