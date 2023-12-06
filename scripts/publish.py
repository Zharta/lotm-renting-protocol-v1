import hashlib
import json
import logging
import os
import warnings
from pathlib import Path

import boto3
import click

from ._helpers.deployment import DeploymentManager, Environment

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)
warnings.filterwarnings("ignore")


ENV = Environment[os.environ.get("ENV", "local")]
DYNAMODB = boto3.resource("dynamodb")
RENTING = DYNAMODB.Table(f"renting-configs-{ENV.name}")
ABI = DYNAMODB.Table(f"abis-{ENV.name}")
KEY_ATTRIBUTES = ["renting_key"]


def abi_key(abi: list) -> str:
    json_dump = json.dumps(abi, sort_keys=True)
    hash = hashlib.sha1(json_dump.encode("utf8"))
    return hash.hexdigest()


def get_abi_map(context, env: Environment) -> dict:
    config_file = f"{Path.cwd()}/configs/{env.name}/renting.json"
    with open(config_file, "r") as f:
        config = json.load(f)

    contracts = {f"{prefix}.{k}": v for prefix, contracts in config.items() for k, v in contracts.items()}
    for k, config in contracts.items():
        contract = context[k].contract
        config["abi"] = contract.contract_type.dict()["abi"]
        config["abi_key"] = abi_key(contract.contract_type.dict()["abi"])

    return contracts


def get_renting_configs(context, env: Environment) -> dict:
    config_file = f"{Path.cwd()}/configs/{env.name}/renting.json"
    with open(config_file, "r") as f:
        config = json.load(f)

    renting_configs = config["renting"]
    for k, config in renting_configs.items():
        contract = context[f"renting.{k}"].contract
        if "abi_key" not in config:
            config["abi_key"] = abi_key(contract.contract_type.dict()["abi"])

    return renting_configs


def update_renting_config(renting_key: str, renting: dict):
    indexed_attrs = list(enumerate(renting.items()))
    renting["renting_key"] = renting_key
    update_expr = ", ".join(f"{k}=:v{i}" for i, (k, v) in indexed_attrs if k not in KEY_ATTRIBUTES)
    values = {f":v{i}": v for i, (k, v) in indexed_attrs if k not in KEY_ATTRIBUTES}
    RENTING.update_item(
        Key={"renting_key": renting_key}, UpdateExpression=f"SET {update_expr}", ExpressionAttributeValues=values
    )


def update_abi(abi_key: str, abi: list[dict]):
    ABI.update_item(Key={"abi_key": abi_key}, UpdateExpression="SET abi=:v", ExpressionAttributeValues={":v": abi})


@click.command()
def cli():
    dm = DeploymentManager(ENV)

    print(f"Updating renting configs in {ENV.name}")

    abis = get_abi_map(dm.context, dm.env)
    for contract_key, config in abis.items():
        abi_key = config["abi_key"]
        print(f"adding abi {contract_key=} {abi_key=}")
        update_abi(abi_key, config["abi"])

    renting_configs = get_renting_configs(dm.context, dm.env)

    for k, v in renting_configs.items():
        properties_abis = {}
        for prop, prop_val in v.get("properties", {}).items():
            if prop_val in abis:
                properties_abis[prop] = abis[prop_val]["abi_key"]
        v["properties_abis"] = properties_abis

        abi_key = v["abi_key"]
        print(f"updating renting config {k} {abi_key=}")
        update_renting_config(k, v)

    print(f"Renting configs updated in {ENV.name}")
