#!/usr/bin/env bash
set -e

BROKER_HOST=mosquitto
BROKER_PORT=1883

SUPERUSER=admin
SUPERUSER_PASSWORD=mysupersecretpassword
# This password is stored in redis exactly as the following PBKDF2 hash:
# PBKDF2$sha256$901$NWq3cjVMjsrHT+VX$bwGz77L8DoHNAu4rUrAZRYFMGimifkLQ

PUBLISHING_TOPIC=mytopic

while true ; do
    mosquitto_pub -h "${BROKER_HOST}" -p "${BROKER_PORT}" -t "${PUBLISHING_TOPIC}" -m "$(date)" \
    -u "${SUPERUSER}" -P "${SUPERUSER_PASSWORD}"
    sleep 1
done