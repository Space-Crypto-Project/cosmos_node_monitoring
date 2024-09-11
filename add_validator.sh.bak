#!/bin/bash

# This code is used to add a new validator to the prometheus configuration file (prometheus.yml)
# It's adapted for CometBFT, Node Exporter and Cosmos Exporter.

# Cosmos Exporter: https://github.com/solarlabsteam/cosmos-exporter
# Node Exporter: https://github.com/prometheus/node_exporter

# Jobs:
# - node: Node Exporter
# - cosmos: CometBFT
# - validator: Cosmos Exporter
# - validators: Cosmos Exporter
# - wallet: Cosmos Exporter


# Usage: ./add_validator.sh <validator_ip> <prometheus_port> <validator_address> <wallet_address> <node_instance_name>

yq -i -y '.scrape_configs[] |= (.job_name as $name | .static_configs += if $name == "prometheus" then [] else ([{targets:["'$1'" + (if $name == "node" then ":9100" elif $name == "cosmos" then ":'$2'" else ":9300" end)], labels:(if $name == "validator" then {address: "'$3'"} elif $name == "wallet" then {address: "'$4'"} elif $name == "node" then {instance: "'$5'"} elif $name == "cosmos" then {custom_instance: "'$5'"} else {} end)}]) end)' ./prometheus/prometheus.yml