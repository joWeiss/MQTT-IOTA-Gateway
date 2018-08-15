#!/bin/sh

REDIS=redis

redis-cli -h $REDIS SET admin 'PBKDF2$sha256$901$NWq3cjVMjsrHT+VX$bwGz77L8DoHNAu4rUrAZRYFMGimifkLQ'
redis-cli -h $REDIS GET admin
