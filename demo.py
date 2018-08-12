#!/usr/bin/env python
from hashing_passwords import make_hash

from json import loads
from pprint import pprint
from sys import exit
from time import sleep
from typing import Dict, Tuple

from iota import Iota, TryteString
from iota.filters import AddressNoChecksum
from pendulum import from_timestamp, now
from redis import StrictRedis


VALUE_PER_TEN_SECONDS = 1


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
                print(e)
        break
    return extracted_json


def filter_transactions(iota, deposit_addr):
    transactions = iota.get_latest_inclusion(
        iota.find_transactions(addresses=[deposit_addr])["hashes"]
    )
    return list(transactions["states"].keys())
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
        if t.address == trytes_addr and transaction_age.in_minutes() < 60 and t.value > 2 * VALUE_PER_TEN_SECONDS:
            print(
                f"[{from_timestamp(t.timestamp)}] Payment of {t.value}i found on receiving address {trytes_addr[:8]}..."
            )
            try:
                data = extract_json(iota.get_bundles(t.hash))
                username, topic, password = parse_payload(data)
                payments["username"] = username
                payments["topic"] = topic
                payments["password"] = password
                payments["expires_after"] = 10 * (t.value // VALUE_PER_TEN_SECONDS)
                payments[f"{username}-{topic}"] = {
                    "password": password,
                    "t_hash": t.hash,
                    "t_value": t.value,
                    "expires_after": 10 * (t.value // VALUE_PER_TEN_SECONDS),
                }
                pprint(payments)
            except Exception as e:
                print(e)
    return payments


def main():
    iota = Iota("https://potato.iotasalad.org:14265")
    receiving_addr = "MPUKMWNFTYFRLJDE9ZWJY9JPKVEIIKDOWANMJIHJJWPOINFRXKVLWOUHFCMCWLO9GAAWDRWGXMTKFCIZDDQTTHNERC"
    print("Successfully connected to remote IOTA node...")
    while True:
        print("Searching for valid transactions...")
        payments = []
        for t in filter_transactions(iota, receiving_addr):
            payments.append(check_for_payments(iota, t, receiving_addr))
        payments = list(filter(None, payments))
        pprint(payments)
        if not all(payments):
            print("No valid payments found.")
        else:
            redis = StrictRedis()
            for payment in payments:
                pprint(payment)
                redis.set(payment["username"], payment["password"], ex=payment["expires_after"], nx=True)
                # that's the only value that works right now...
                redis.set(f"{payment['username']}-{payment['topic']}", 4, ex=payment["expires_after"], nx=True)
        print("...")
        sleep(5)


if __name__ == "__main__":
    main()
