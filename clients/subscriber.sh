#!/usr/bin/env bash
set -e

BROKER_HOST=mosquitto
BROKER_PORT=1883

SUBSCRIBER_USERNAME=jonas
SUBSCRIPTION=mytopic
SUBSCRIBER_PASSWORD="${SUBSCRIBER_USERNAME}"-"${SUBSCRIPTION}"

while true ; do
    mosquitto_sub -h "${BROKER_HOST}" -p "${BROKER_PORT}" -u "${SUBSCRIBER_USERNAME}" \
    -P "${SUBSCRIBER_PASSWORD}" -t "${SUBSCRIPTION}"
    sleep 1
done