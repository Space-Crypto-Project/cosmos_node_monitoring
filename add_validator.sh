#!/bin/bash

# This code is used to add a new validator to the prometheus configuration file (prometheus.yml)
# It's adapted for CometBFT, Node Exporter and Cosmos Validator Exporter.

# Node Exporter: https://github.com/prometheus/node_exporter
# Cosmos Validator Exporter: https://github.com/QuokkaStake/cosmos-validators-exporter

# Jobs:
# - node: Node Exporter
# - validator: Cosmos Validator Exporter
# - cosmos: CometBFT

# Usage: ./add_validator.sh <validator_ip> <prometheus_port> <node_instance_name>
# ./add_validator.sh 141.94.30.110 30061 Og_testnet

yq -i -y '.scrape_configs[] |= (.job_name as $name | .static_configs += (if $name == "prometheus" then [] elif $name == "node" then [{"targets": ["'"$1"':9100"], "labels": {"instance": "'"$3"'"}}] elif $name == "cosmos" then [{"targets": ["'"$1"':'"$2"'"], "labels": {"custom_instance": "'"$3"'"}}] else [] end))' ./prometheus/prometheus.yml

echo "Target $1:$2 added under 'cosmos' job."
echo "Target $1:9100 added under 'node' job."


existing_validator_target=$(yq -r '.scrape_configs[] | select(.job_name == "validator") | .static_configs[].targets[] | select(. == "'$1':9560")' ./prometheus/prometheus.yml)


if [ -z "$existing_validator_target" ]; then
  # Include the validator target if it does not exist

   yq -i -y '.scrape_configs[] |= (if .job_name == "validator" then .static_configs += [{"targets": ["'$1':9560"]}] else . end)' ./prometheus/prometheus.yml
   echo "Target $1:9560 added under 'validator' job."

else
  # Print a message if the target exists
  echo "Target $1:9560 already exists under 'validator' job. No changes made."
fi


#existing_node_target=$(yq -r '.scrape_configs[] | select(.job_name == "node") | .static_configs[].targets[] | select(. == "'$1':9100")' ./prometheus/prometheus.yml)

# Commented out the section that adds the 'node' target one time only
# if [ -z "$existing_node_target" ]; then
#   # Include the node target if it does not exist
#   yq -i '.scrape_configs[] |= (if .job_name == "node" then .static_configs += [{"targets": ["'$1':9100"], "labels": {"instance": "'$3'"}}] else . end)' ./prometheus/prometheus.yml
#   echo "Target $1:9100 added under 'node' job."
# else
#   # Print a message if the target exists
#   echo "Target $1:9100 already exists under 'node' job. No changes made."
# fi
