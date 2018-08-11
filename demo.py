#!/usr/bin/env python
from hashing_passwords import make_hash

from json import loads
from pprint import pprint
from sys import exit
from typing import Dict

from iota import Iota, TryteString
from iota.filters import AddressNoChecksum
from pendulum import from_timestamp, now
from redis import StrictRedis


VALUE_PER_TEN_SECONDS = 1


def extract_json(transaction) -> Dict:
    print("Extracting payload...")
    extracted_json = {}
    first_tryte_pair = (
        transaction.signature_message_fragment[0]
        + transaction.signature_message_fragment[1]
    )
    if first_tryte_pair != "OD":
        raise ValueError("No JSON found.")
    fragment = transaction.signature_message_fragment
    try:
        extracted_json = loads(fragment.decode())
    except ValueError as e:
        pass
    return extracted_json


def filter_transactions(iota, deposit_addr):
    transactions = iota.get_latest_inclusion(
        iota.find_transactions(addresses=[deposit_addr])["hashes"]
    )
    return filter(lambda t: transactions["states"][t], transactions["states"])


def parse_payload(payload):
    username = payload.get("username")
    topic = payload.get("topic")
    password = make_hash(f"{username}-{topic}")
    return username, topic, password


def check_payments(iota, transactions, addr):
    payments = {}
    bundles = iota.get_bundles(transactions)
    for t in bundles["bundles"][0]:
        trytes_addr = AddressNoChecksum()._apply(TryteString(addr))
        transaction_age = now() - from_timestamp(t.timestamp)
        if t.address == trytes_addr and transaction_age.in_minutes() < 5 and t.value > VALUE_PER_TEN_SECONDS:
            print(
                f"[{from_timestamp(t.timestamp)}] Payment of {t.value}i found on receiving address {trytes_addr[:8]}..."
            )
            data = extract_json(t)
            username, topic, password = parse_payload(data)
            payments[f"{username}-{topic}"] = {
                "password": password,
                "t_hash": t.hash,
                "t_value": t.value,
                "expires_in": t.value // VALUE_PER_TEN_SECONDS,
            }
    if not payments:
        print("No valid payments found.")
        exit(1)
    return payments


def main():
    iota = Iota("https://potato.iotasalad.org:14265")
    receiving_addr = "MPUKMWNFTYFRLJDE9ZWJY9JPKVEIIKDOWANMJIHJJWPOINFRXKVLWOUHFCMCWLO9GAAWDRWGXMTKFCIZDDQTTHNERC"
    print("Successfully connected to remote IOTA node...")
    print("Searching for valid transactions...")
    payments = []
    for t in filter_transactions(iota, receiving_addr):
        payments.append(check_payments(iota, t, receiving_addr))
    pprint(payments)


if __name__ == "__main__":
    main()
