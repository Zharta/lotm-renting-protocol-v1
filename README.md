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
3. the vault where the NFTasset is escrowed delegates it to the renter's wallet for a specific duration
4. once the duration of the rental is reached, the rental finishes

## General considerations

The current status of the protocol follows certain assumptions that must be validated as more information about LOTM is released.

The assumptions are the following:
1. delegation is supported using [warm.xyz](https://warm.xyz)
2. the current version of [warm.xyz](https://warm.xyz) if the same as the last verified version seen [here](https://etherscan.io/address/0xad0b7f45750f2211b55a1218f907e67dfac841fa#code)
3. because [warm.xyz](https://warm.xyz) does not support NFT-level delegation and only supports wallet-level delegation, one vault per NFT needs to be created


## Security
Below are the smart contract audits performed for the protocol so far:

| **Auditor** 	| **Status** 	| **PDF** 	|
|:-----------:	|:----------:	|---------	|
| Hacken      	| Ongoing    	| _TBA_   	|

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
2. `withdraw`: the NFT owner withdraws the NFT from the vault, together it any unclaimed fees
3. `start_rental`: a renter starts the rental and the previous rental fees, if not claimed, are set explicitly as unclaimed
4. `close_rental`: a renter may finish a rental before its due date and pays only for the time used, and unclaimed fees are explicitly set

### Roles

The protocol does not support any admin role. The only roles are the following:
* `Vault.vy`:
    * `owner`: the owner of the NFT that is escrowed in vault, which means that only this address can perform certain actions against the vault, but those action still need to be performed through the `Renting.vy` contract


## Development

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
make install-dev install
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
