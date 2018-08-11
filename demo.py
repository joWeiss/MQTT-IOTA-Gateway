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


def extract_json(transaction) -> Dict:
    print("Extracting payload...")
    extracted_json = {}
    # first_tryte_pair = (
        # transaction.signature_message_fragment[0]
        # + transaction.signature_message_fragment[1]
    # )
    # if first_tryte_pair != "OD":
        # raise ValueError("No JSON found.")
    fragment = transaction.signature_message_fragment
    print(fragment)
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
        if t.address == trytes_addr and t.value > VALUE_PER_TEN_SECONDS:
            print(
                f"[{from_timestamp(t.timestamp)}] Payment of {t.value}i found on receiving address {trytes_addr[:8]}..."
            )
            try:
                data = extract_json(t)
                username, topic, password = parse_payload(data)
                payments["username"] = username
                payments["topic"] = topic
                payments["password"] = password
                payments["expires_in"] = t.value // VALUE_PER_TEN_SECONDS
                payments[f"{username}-{topic}"] = {
                    "password": password,
                    "t_hash": t.hash,
                    "t_value": t.value,
                    "expires_in": t.value // VALUE_PER_TEN_SECONDS,
                }
            except Exception as e:
                pass
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
        if not all(payments):
            print("No valid payments found.")
        else:
            pprint(payments)
            redis = StrictRedis()
            for payment in payments:
                pprint(payment)
                redis.set(payment["username"], payment["password"], ex=payment["expires_in"], nx=True)
                # that's the only value that works right now...
                redis.set(f"{payment['username']}-{payment['topic']}", 4, ex=payment["expires_in"], nx=True)
        print("...")
        sleep(5)


if __name__ == "__main__":
    main()
