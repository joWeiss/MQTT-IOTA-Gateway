#!/usr/bin/env python
# coding: utf8
from hashing_passwords import make_hash

import os
from argparse import ArgumentParser
from json import loads
from logging import getLogger, INFO
from time import sleep
from typing import Dict, Tuple

from iota import Iota, Transaction, TryteString
from iota.filters import AddressNoChecksum
from pendulum import from_timestamp, now
from redis import StrictRedis

IOTA_NODE = os.environ.get("IOTA_NODE", "https://potato.iotasalad.org:14265")
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
VALUE_PER_TEN_SECONDS = os.environ.get("VALUE_PER_TEN_SECONDS", 1)
logger = getLogger()
logger.setLevel(INFO)


def extract_json(transaction) -> Dict:
    first_tryte_pair = (
        transaction.signature_message_fragment[0]
        + transaction.signature_message_fragment[1]
    )
    if first_tryte_pair != "OD":
        raise ValueError("No JSON found.")
    fragment = transaction.signature_message_fragment
    try:
        data = str(fragment.decode())
        extracted_json = loads(data)
    except ValueError as e:
        extracted_json = data if data else {}
    return extracted_json


def filter_transactions(iota, deposit_addr, allow_unconfirmed):
    transactions = iota.get_latest_inclusion(
        iota.find_transactions(addresses=[deposit_addr])["hashes"]
    )
    if allow_unconfirmed:
        return transactions["states"].keys()
    else:
        return filter(lambda t: transactions["states"][t], transactions["states"])


def parse_payload(payload) -> Tuple[str, str, str]:
    username = payload.get("username")
    topic = payload.get("topic")
    password = make_hash(f"{username}-{topic}")
    return username, topic, password


def check_for_payments(iota, t_hash, addr) -> Dict:
    payments = {}
    receiver_addr = AddressNoChecksum()._apply(TryteString(addr))
    t_bytes = bytes(t_hash)
    t_trytes = str(iota.get_trytes([t_bytes])["trytes"][0])
    transaction = Transaction.from_tryte_string(t_trytes)
    t_age = now() - from_timestamp(transaction.attachment_timestamp / 1000)
    if (
        transaction.address == receiver_addr
        and t_age.in_minutes() < 60
        and transaction.value >= VALUE_PER_TEN_SECONDS
    ):
        logger.warning(
            f"[{from_timestamp(transaction.timestamp)}] Payment of {transaction.value}i found on receiving address {addr[:8]}..."
        )
        try:
            data = extract_json(transaction)
            username, topic, password = parse_payload(data)
            payments["username"] = username
            payments["topic"] = topic
            payments["password"] = password
            payments["expires_after"] = 10 * (
                transaction.value // VALUE_PER_TEN_SECONDS
            )
            payments["t_hash"] = transaction.hash
            payments["t_value"] = transaction.value
        except Exception as e:
            logger.exception(e)
    return payments


def main(receiving_addr, allow_unconfirmed):
    iota = Iota(IOTA_NODE)
    redis = StrictRedis(REDIS_HOST)
    logger.warning("Successfully connected to remote IOTA node...")
    logger.warning(f"Receiving address: {receiving_addr}")
    while True:
        logger.warning("Searching for valid and unprocessed transactions...")
        payments = []
        for t in filter_transactions(iota, receiving_addr, allow_unconfirmed=allow_unconfirmed):
            skip = redis.get(t)
            if not skip:
                payments.append(check_for_payments(iota, t, receiving_addr))
        payments = list(filter(None, payments))
        if not (payments and all(payments)):
            logger.warning("No valid payments found.")
        else:
            for payment in payments:
                redis.set(
                    name=payment["username"],
                    value=payment["password"],
                    ex=payment["expires_after"],
                    nx=True,
                )
                # that's the only value that works right now...
                redis.set(
                    name=f"{payment['username']}-{payment['topic']}",
                    value=4,
                    ex=payment["expires_after"],
                    nx=True,
                )
                # mark transaction as processed, so that it is skipped the next round
                redis.set(name=payment["t_hash"], value=str(payment["t_hash"]))
        sleep(5)


if __name__ == "__main__":
    parser = ArgumentParser(description='Check for payments on address')
    parser.add_argument('address', metavar='address', type=str, help="The wallet address to check for valid payments.")
    parser.add_argument("--allow-unconfirmed", dest="allow", action='store_true')
    args = parser.parse_args()
    logger.debug(f"Allow unconfirmed: {args.allow}")
    main(receiving_addr=args.address, allow_unconfirmed=args.allow)
