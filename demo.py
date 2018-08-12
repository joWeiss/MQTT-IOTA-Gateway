#!/usr/bin/env python
from hashing_passwords import make_hash

from json import loads
from logging import getLogger
from time import sleep
from typing import Dict, Tuple

from iota import Iota, TryteString
from iota.filters import AddressNoChecksum
from pendulum import from_timestamp, now
from redis import StrictRedis


VALUE_PER_TEN_SECONDS = 1
logger = getLogger()


def extract_json(bundle) -> Dict:
    extracted_json = {}
    first_transaction = bundle["bundles"][0][0]
    first_tryte_pair = (
        first_transaction.signature_message_fragment[0]
        + first_transaction.signature_message_fragment[1]
    )
    if first_tryte_pair != "OD":
        raise ValueError("No JSON found.")
    for b in bundle["bundles"]:
        for transaction in b:
            fragment = transaction.signature_message_fragment
            try:
                extracted_json.update(loads(fragment.decode()))
                break
            except ValueError as e:
                logger.exception(e)
        break
    return extracted_json


def filter_transactions(iota, deposit_addr):
    transactions = iota.get_latest_inclusion(
        iota.find_transactions(addresses=[deposit_addr])["hashes"]
    )
    return transactions["states"].keys()
    # pprint(transactions)
    # return filter(lambda t: transactions["states"][t], transactions["states"])


def parse_payload(payload) -> Tuple[str, str, str]:
    username = payload.get("username")
    topic = payload.get("topic")
    password = make_hash(f"{username}-{topic}")
    return username, topic, password


def check_for_payments(iota, transactions, addr) -> Dict:
    payments = {}
    bundles = iota.get_bundles(transactions)
    for t in bundles["bundles"][0]:
        trytes_addr = AddressNoChecksum()._apply(TryteString(addr))
        transaction_age = now() - from_timestamp(t.timestamp)
        if (
            t.address == trytes_addr
            and transaction_age.in_minutes() < 60
            and t.value >= VALUE_PER_TEN_SECONDS
        ):
            logger.info(
                f"[{from_timestamp(t.timestamp)}] Payment of {t.value}i found on receiving address {trytes_addr[:8]}..."
            )
            try:
                data = extract_json(iota.get_bundles(t.hash))
                username, topic, password = parse_payload(data)
                payments["username"] = username
                payments["topic"] = topic
                payments["password"] = password
                payments["expires_after"] = 10 * (t.value // VALUE_PER_TEN_SECONDS)
                payments["t_hash"] = t.hash
                payments["t_value"] = t.value
            except Exception as e:
                logger.exception(e)
    return payments


def main():
    iota = Iota("https://potato.iotasalad.org:14265")
    receiving_addr = "MPUKMWNFTYFRLJDE9ZWJY9JPKVEIIKDOWANMJIHJJWPOINFRXKVLWOUHFCMCWLO9GAAWDRWGXMTKFCIZDDQTTHNERC"
    logger.info("Successfully connected to remote IOTA node...")
    while True:
        logger.info("Searching for valid transactions...")
        payments = []
        for t in filter_transactions(iota, receiving_addr):
            payments.append(check_for_payments(iota, t, receiving_addr))
        payments = list(filter(None, payments))
        if not all(payments):
            logger.info("No valid payments found.")
        else:
            redis = StrictRedis()
            for payment in payments:
                if not redis.get(payment["t_hash"]):
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
                    redis.set(name=payment["t_hash"], value=1)
                else:
                    continue
        sleep(5)


if __name__ == "__main__":
    main()
