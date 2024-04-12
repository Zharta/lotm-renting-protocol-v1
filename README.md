# LOTM Renting Protocol by Zharta

## Introduction

This protocol is targeted at [LOTM](https://lotm.otherside.xyz/) from Yuga Labs. The protocol serves as a trustless way for LOTM players to rent game assets from users.

There are two major domains in the protocol:
* the vaults
* the renting logic


## Overview

| **Version** | **Language** | **Reference implementation**                       |
| ---         | ---          | ---                                                |
| V1          | Vyper 0.3.9  | https://github.com/Zharta/lotm-renting-protocol-v1 |
| V2          | Vyper 0.3.9  | https://github.com/Zharta/lotm-renting-protocol-v1 |
| V3          | Vyper 0.3.10  | https://github.com/Zharta/lotm-renting-protocol-v1 |

There are two major domains in the protocol:
* the vaults
* the renting logic

The renting of an NFT in the context of this protocol means that:
1. an asset owner deposits the NFT in a vault, setting the terms of the rental: price and minimum/maximum rental duration
2. a user (renter) selects the NFT put for rental and starts the rental by paying for the rental upfront
3. the vault where the NFT asset is escrowed delegates it to a renter's specified wallet for a specific duration
4. once the duration of the rental is reached, the rental finishes

In addition, the vaults can be represented as NFTs which can be exchanged between users, either directly or through a marketplace. This also means the vaults can be used by other NFT-FI protocols as collateral.


## General considerations

The current status of the protocol follows certain assumptions.

The assumptions are the following:
1. delegation is supported using [warm.xyz](https://warm.xyz)
2. the current version of [warm.xyz](https://warm.xyz) if the same as the last verified version seen [here](https://etherscan.io/address/0xad0b7f45750f2211b55a1218f907e67dfac841fa#code)
3. because [warm.xyz](https://warm.xyz) does not support NFT-level delegation and only supports wallet-level delegation, the protocol needs to create one vault per NFT
4. since the protocol is running using [$APE](https://etherscan.io/address/0x4d224452801ACEd8B2F0aebE155379bb5D594381) as the payment token, the protocol also supports the use of [APE Staking](https://apestake.io/) by users


## Security
Below are the smart contract audits performed for the protocol so far:

| **Auditor** 	| **Version** 	| **Status** 	| **PDF** 	                                            |
|:-----------:	|:----------:	|:----------:	|---------	                                            |
| Hacken      	| V1    	    | Done    	    | [Audit_Hacken.pdf](audits/Audit_Hacken.pdf)  	        |
| Hacken      	| V2    	    | Done    	    | [Audit_Hacken_v2.pdf](audits/Audit_Hacken_v2.pdf)  	|
| Hacken      	| V3    	    | Pending    	|   	|


## Architecture

As previously stated, there are two domains of the protocol:
* the vaults implemented in [`VaultV3.vy`](https://github.com/Zharta/lotm-renting-protocol-v1/blob/main/contracts/VaultV3.vy)
* the renting logic implemented in [`RentingV3.vy`](https://github.com/Zharta/lotm-renting-protocol-v1/blob/main/contracts/RentingV3.vy)
* the ERC721 interface of the vaults is implemented in [`RentingERC721V3.vy`](https://github.com/Zharta/lotm-renting-protocol-v1/blob/main/contracts/RentingERC721V3.vy)

Users and other protocols should always interact with the [`RentingV3.vy`](https://github.com/Zharta/lotm-renting-protocol-v1/blob/main/contracts/RentingV3.vy) contract. The `RentingV3.vy` contract is the entry point of the protocol and it is responsible for:
* NFT owners depositing NFTs in the protocol, which means the protocol creates a vault for each NFT
* renters starting rentals
* renters extending rentals
* renters closing rentals before the due date
* NFT owners claiming rental fees
* NFT owners withdrawing NFTs from the protocol
* NFT owners can stake their APE tokens in the official APE Staking protocol to earn rewards
* NFT owners can exchange and trade their vaults

### Vaults and NFT deposits

Each NFT put for rental needs to be in its own vault (see the 3rd point in [General considerations](#general-considerations)). This means that when an NFT owner wants to deposit an NFT in the protocol, the NFT owner may need to create the vault prior to depositing the NFT. If the vault for that specific NFT has already been created before, it can be reused.

**NFT owners do not need to create the vaults themselves, the protocol will create the vaults when needed.**

The protocol creates the vaults using minimal proxies and the `CREATE2` opcode. This means that when a vault for a specific NFT needs to be created, the protocol is able to compute the destination address of the vault before creating it and the user may approve the NFT to be transferred. Therefore, creating the vault and depositing the NFT can be done atomically.

### Listing conditions

The listing conditions are signed by the NFT owner and stored offchain. The listing conditions are composed by the price per hour and the minimum and maximum rental duration. Whenever there is a protocol interaction that requires them, Zharta's infrastructure signs the owner-signed listing conditions:
* `RentingV3.start_rentals`
* `RentingV3.close_rentals`
* `RentingV3.extend_rentals`
* `RentingV3.withdraw`
* `RentingV3.claim`

In order to help owners secure their assets, there is an addition method `RentingV3.revoke_listing` that allows the owner to set a timestamp after which listings set before it are no longer valid.

### Rentals

Whenever a rental starts, the renter pays the full amount of the rental upfront. This amount is locked in the `RentingV3.vy` contract until the end of the rental. Once the rental finishes, the rental amount is released to the NFT owner for claiming. Since the protocol is using [warm.xyz](https://warm.xyz) which supports setting a specific timestamp for the end of the delegation, the protocol computes the amount of fees that are claimable taking this into consideration. Unclaimed fees are only set explicitly for certain actions:
1. `RentingV3.claim`: the NFT owner claims unclaimed fees
2. `RentingV3.withdraw`: the NFT owner withdraws the NFT from the vault, along with any unclaimed fees
3. `RentingV3.start_rentals`: a renter starts the rental and the previous rental fees, if not claimed, are set explicitly as unclaimed
4. `RentingV3.close_rentals`: a renter may finish a rental before its due date and pays only for the time used, and unclaimed fees are explicitly set
5. `RentingV3.extend_rentals`: a renter may extend an ongoing rental and has to pay the rental fees for the extension upfront, and unclaimed fees are explicitly set

### Roles

The protocol does supports an **admin role** with the following purposes:
* enabling/disabling the protocol fee and its
* setting the protocol wallet that receives the protocol fee
* validating the signature passed in the `RentingV3.start_rentals` method

The roles are the following:
* `Renting.vy`:
    * `admin`: the protocol admin with permissions limited to set the value of protocol fees (up to a fixed limit) and the protocol wallet that receives those fees. The `admin` value can be changed via the `propose_admin` and `claim_ownership` functions.
    * `owner`: the owner of the NFT that is escrowed in vault, which means that only this address can perform certain actions against the vault
    * `vault owner`: the owner of the NFT that represents the vault itself. When a vault changes ownernship, the new vault owner can claim ownership of the NFT escrowed in the vault, thus changing the value of `owner`.

### Delegation

The protocol uses [warm.xyz](https://warm.xyz) to perform wallet level delegation of the vaults. At any moment, at most one delegation can be active, meaning that setting a new hot wallet cancels any ongoing delegation. The usage of delegation happens as following:
* Renter:
    * `RentingV3.start_rentals`: when initiating a rental, the renter specifies a `delegate` which will be used as the vault hot wallet for the specified rental duration.
    * `RentingV3.close_rentals`: if the renter cancels the rental, the delegation is also removed.
    * `RentingV3.extend_rentals`: if the renter extends the rental, the delegation is also extended.
    * `RentingV3.renter_delegate_to_wallet`: at any time that a renter has an ongoing rental is not ongoing, the renter can specify a different wallet for the delegation.
* NFT Owner:
    * `RentingV3.deposit`: as part of this operation, an optional `delegate` can be set. If not empty, it is set as the vault hot wallet without expiration period.
    * `RentingV3.delegate_to_wallet`: at any time that a rental is not ongoing, the vault owner can use this function to set a new delegate as the vault hot wallet without expiration period.


### Protocol fees

The protocol supports the definition of a fee to be applied over the rental's amount. It works as following:

* The `RentingV3.vy` contract stores the `protocol_fee` and `protocol_wallet` values, which are used as parameters when a new rental is created (`RentingV3.start_rental`).
* For each rental, the `protocol_fee` and `protocol_wallet` initially defined are not changed, meaning the conditions defined during rental creation are valid for the full life of the rental.
* The `admin` role can change both the `protocol_fee` and `protocol_wallet`, which become valid for every new rental thereafter.
* At deployment time, a `max_protocol_fee` is set, which limits the max possible `protocol_fee` value that the `admin` can set. This value can't be changed.
* Protocol fees follow a simliar process to rental rewards, meaning that they can be acumulated and transfered on specific actions: `RentingV3.withdraw`, `RentingV3.claim`, `RentingV3.close_rental`, and `RentingV3.extend_rental`.
* In case of early rental cancelation (`RentingV3.close_rental`) the fees are applied over the pro-rata rental amount, similary to the rewards.


## Development

### Implementation

#### Renting contract (`RentingV3.vy`)

The renting contract is the single user-facing contract for each Renting Market. This contract holds payment tokens and manages the creation of vaults (as minimal proxies to the vault implementation). It manages the state of rentals and delegates some calls to the vaults, with the exception of the admin functions.

##### State variables

| **Variable**             | **Type**                    | **Mutable** | **Desciption**                                                                                                                                                |
| ---                      | ---                         | :-:         | ---                                                                                                                                                           |
| vault_impl_addr          | `address`                   | No          | address of the Vault implementation contract for the renting market                                                                                           |
| payment_token_addr       | `address`                   | No          | address of the payment token (ERC20) contract for the renting market                                                                                          |
| nft_contract_addr        | `address`                   | No          | address of the NFT (ERC721) contract for the renting market                                                                                                   |
| delegation_registry_addr | `address`                   | No          | address of the delegation (warm.xyz) contract                                                                                                                 |
| staking_addr             | `address`                   | No          | address of the APE Staking (apestake.io) contract                                                                                                             |
| renting_erc721           | `address`                   | No          | address of the ERC721 interface of the vault contract                                                                                                         |
| max_protocol_fee         | `uint256`                   | No          | maximum value for the admin configurable `protocol_fee` parameter                                                                                             |
| staking_pool_id          | `address`                   | No          | integer specifying the APE Staking (apestake.io) pool to be used for the renting market                                                                       |
| protocol_wallet          | `address`                   | Yes         | wallet address to receive the protocol fees                                                                                                                   |
| protocol_fee             | `uint256`                   | Yes         | fraction of the rentals' values (in bps) to be paid as fee                                                                                                    |
| protocol_admin           | `address`                   | Yes         | wallet address of the protocol admin                                                                                                                          |
| proposed_admin           | `address`                   | Yes         | wallet to be proposed as admin by using the `propose_admin` function, it becomes the `protocol_admin` after the wallet claims it by calling `claim_ownership` |
| rental_states            | `HashMap[uint256, bytes32]` | Yes         | map of rental states: stores the hash of a Rental structure for a given token ID (NFT)                                                                        |
| listing_revocations      | `HashMap[uint256, uint256]` | Yes         | map of listing revocations: for each token ID, stores the timestamp before which past listings become invalidated                                             |
| unclaimed_rewards        | `uint256`                   | Yes         | keeps the amount of the owner's unclaimed rewards, which result from rentals expiration and must be accounted for later claim                                 |
| protocol_fees_amount     | `uint256`                   | Yes         | keeps the amount of unclaimed protocol fees, which result from rentals expiration and must be accounted for later claim by the protocol admin                 |

##### Externalized State

The information regarding listings and rentals was externalized in order to reduce the gas costs while using the protocol. That requires the state to be passed as an argument to each function and validated by matching it's hash against the one stored in the contract. Conversly, changes to the state are hashed and stored, and the resulting state variables returned to the caller (the Renting contract), to either be published as events or returned directly to the user. The structures that hold the state are the `Listing` and the `Rentals`, although not every member is part of the state if is not required to keep the integrity of the contract.

| **Struct** | **Variable**    | **Type**                        | **Part of State** | **Desciption**                                                                                                               |
| ---        | ---             | ---                             | :-:               | ---                                                                                                                          |
| Rental     | id              | `bytes32`                       | Yes               | id of a rental, calculated as the keccak256 of the renter, token_id, start and expiration; empty if there's no active rental |
|            | owner           | `address`                       | Yes               | wallet address owner of the deposited NFT                                                                                    |
|            | renter          | `address`                       | Yes               | wallet address renting the NFT                                                                                               |
|            | delegate        | `address`                       | No                | used as hot wallet during the rental period                                                                                  |
|            | token_id        | `uint256`                       | Yes               | id of the deposited token                                                                                                    |
|            | start           | `uint256`                       | Yes               | timestamp marking the start of the rental period                                                                             |
|            | min_expiration  | `uint256`                       | Yes               | timestamp marking the minimal period charged in case of rental cancelation by the renter                                     |
|            | expiration      | `uint256`                       | Yes               | timestamp marking the end of the rental period                                                                               |
|            | amount          | `uint256`                       | Yes               | amount (of the payment token) to be paid by the renter for the rental                                                        |
|            | protocol_fee    | `uint256`                       | Yes               | fee in bps to be charged for the rental                                                                                      |
|            | protocol_wallet | `address`                       | Yes               | wallet to receive the protocol fee                                                                                           |
|            |                 |                                 |                   |                                                                                                                              |
| Listing    | token_id        | `uint256`                       | Yes               | id of the deposited token                                                                                                    |
|            | price           | `uint256`                       | Yes               | price per hour, 0 means not listed                                                                                           |
|            | min_duration    | `uint256`                       | Yes               | min duration in hours                                                                                                        |
|            | max_duration    | `uint256`                       | Yes               | max duration in hours, 0 means unlimited                                                                                     |
|            | timestamp       | `uint256`                       | Yes               | timestamp when the listing was submitted offchain                                                                            |
|            |                 |                                 |                   |                                                                                                                              |
| Signature  | v, r, s         | `uint256`, `uint256`, `uint256` | Yes               | parameters of the owner's signature of a listing                                                                             |

##### Relevant external functions

| **Function**              | **Roles Allowed**    | **Modifier** | **Description**                                                                                                                 |
| ---                       | :-:                  | ---          | ---                                                                                                                             |
| delegate_to_wallet        | Owner                | Nonpayable   | delegates call to each token's vault to perform a delegation to a given hot wallet                                              |
| renter_delegate_to_wallet | Owner                | Nonpayable   | delegates call to each token's vault to perform a delegation to a given hot wallet when an NFT is rented                        |
| deposit                   | Any (becomes Owner)  | Nonpayable   | creates and initializes vaults for given tokens and delegates for each vault the deposit of the token and creation of a listing |
| mint                      | Owner                | Nonpayable   | mints an NFT representation of the vault that can be transacted and/or used as collateral                                       |
| revoke_listing            | Owner                | Nonpayable   | sets a timestamp before which past listings become invalidated                                                                  |
| start_rentals             | Any (becomes Renter) | Nonpayable   | starts rentals for the specific duration and delegates call to each token's vault to delegate themselves to the renter          |
| close_rentals             | Renter               | Nonpayable   | cancels the rentals and delegates call to each token's vault to cancel the delegation                                           |
| extend_rentals            | Renter               | Nonpayable   | extends the rentals and delegates call to each token's vault to extend the delegation                                           |
| withdraw                  | Owner                | Nonpayable   | after delegating calls to each token's vault to withdraw the NFTs and mark the vaults as inactive, claims pending rewards       |
| stake_deposit             | Owner                | Nonpayable   | transfers APE to the vaults and delegates call to each token's vault to stake in the corresponding APE staking pool             |
| stake_withdraw            | Owner                | Nonpayable   | delegates call to each token's vault to claim pending staking rewards and to unstake and send APE to the owner's wallet         |
| stake_claim               | Owner                | Nonpayable   | delegates call to each token's vault to claim pending staking rewards to the owner's wallet                                     |
| stake_compound            | Owner                | Nonpayable   | delegates call to each token's vault to claim pending staking rewards and stake them in the same staking pool                   |
| claim                     | Owner                | Nonpayable   | claims all unclaimed owner rewards                                                                                              |
| claim_token_ownership     | Owner                | Nonpayable   | changes the owner of the vault to the owner of the vault's NFT representation (useful when the vault is traded)                 |
| claim_fees                | Admin                | Nonpayable   | claims all unclaimed protocol fees                                                                                              |
| set_protocol_fee          | Admin                | Nonpayable   | sets the protocol fee (in bps) to be charged for each rental                                                                    |
| change_protocol_wallet    | Admin                | Nonpayable   | changes the wallet address to reveive the protocol fees                                                                         |
| set_paused                | Admin                | Nonpayable   | pauses and unpaused the protocol                                                                                                |
| propose_admin             | Admin                | Nonpayable   | sets the `proposed_admin` variable, which can then claim ownership                                                              |
| claim_ownership           | *proposed owner*     | Nonpayable   | claims ownership of the contract, setting the `protocol_admin` variable                                                         |
| is_vault_available        | Any                  | View         | checks if the vault for a given token already exists and if is not active                                                       |
| tokenid_to_vault          | Any                  | View         | returns the address of an existing or yet to be created vault, allowing asset approvals for deposits or creation of rentals     |

#### Vault implementation contract (`VaultV3.vy`)

The Vault is the implementation contract for each vault, which is deployed as a minimal proxy (ERC1167) by the `RentingV3.vy` and accepts only calls from it. This contract holds the NFTs and does not store state. The contract also sets the delegation to hot wallets, as well as calling the APE staking contract.

##### State variables

| **Variable**             | **Type**  | **Mutable** | **Desciption**                                                                                                                                   |
| ---                      | ---       | :-:         | ---                                                                                                                                              |
| caller                   | `address` | Yes         | address of the Renting contract who deployed and manages the vault                                                                               |
| payment_token_addr       | `address` | No          | address of the payment token (ERC20) contract for the renting market                                                                             |
| nft_contract_addr        | `address` | No          | address of the NFT (ERC721) contract for the renting market                                                                                      |
| delegation_registry_addr | `address` | No          | address of the delegation (warm.xyz) contract                                                                                                    |
| staking_addr             | `address` | No          | address of the APE staking (apestake.io) contract                                                                                                |
| staking_pool_id          | `address` | Yes         | integer specifying the APE Staking (apestake.io) pool to be used for the renting market                                                          |

##### Relevant external functions

| **Function**       | **Roles Allowed** | **Modifier** | **Description**                                                                                                                            |
| ---                | :-:               | ---          | ---                                                                                                                                        |
| initialise         | --                | Nonpayable   | called by Renting to set up the initial vault state                                                                                        |
| deposit            | Any               | Nonpayable   | transfers the token from the user to the vault, optionaly creates a listing and sets up a delegation to a given wallet                     |
| withdraw           | Any               | Nonpayable   | transfers the token back to the owner together with any pending rewards, transfers any pending protocolo fees and uninitializes the vault  |
| delegate_to_wallet | Any               | Nonpayable   | creates a delegation for a given wallet if no rental is active                                                                             |
| is_initialised     | Any               | Nonpayable   | return wether the vault is currently initialized                                                                                           |
| stake_deposit      | Any               | Nonpayable   | stakes the APE and the NFT in the corresponding APE staking pool                                                                           |
| stake_withdraw     | Any               | Nonpayable   | claims pending staking rewards and to unstake and send APE to the owner's wallet                                                           |
| stake_claim        | Any               | Nonpayable   | claims pending staking rewards to the owner's wallet                                                                                       |
| stake_compound     | Any               | Nonpayable   | claims pending staking rewards and stake them in the same staking pool                                                                     |

### Testing

There are three types of tests implemented, running on py-evm using titanoboa:
1. Unit tests focus on individual functions for each contract, mocking external dependencies (ERC20, ERC721, and warm.xyz HotWallet)
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
