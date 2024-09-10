#!/bin/bash

read -p "Enter Chain Name, for example, cosmos: " CHAIN_NAME
read -p "Enter LCD endpoint to query data from: " LCD_ENDPOINT
read -p "Enter bond_denom value, for example, 'uatom' for Cosmos: " BOND_DENOM
read -p "Enter Ticker, for example, 'atom' for Cosmos: " DISPLAY_DENOM
read -p "Enter coingecko id, for example, 'cosmos' for Cosmos: " COINGECKO_ID
read -p "Enter bench wallet prefix value, for example, agoric for Agoric: " BENCH_PREFIX
read -p "Enter validator (valoper) address: " VALIDATOR_ADDR
read -p "Enter consensus (valcon) address: " CONSENSUS_ADDR
read -p "Enter the network precision or hit Enter for default precision [6]: " CHAIN_DECIMAL
CHAIN_DECIMAL=${CHAIN_DECIMAL:-6}

ExecStart="cosmos-validators-exporter --config $HOME/cosmos-validators-exporter/config.toml"

# Check if the $HOME/cosmos-validators-exporter directory exists
if [ ! -d "$HOME/cosmos-validators-exporter" ]; then
    echo -e "\e[1m\e[32m1. Installing cosmos-validators-exporter... \e[0m" && sleep 1

    # Install master branch
    git clone https://github.com/QuokkaStake/cosmos-validators-exporter
    cd cosmos-validators-exporter
    # This will produce a binary at ./cosmos-validators-exporter.
    make build
    # This will produce a binary at $GOPATH/bin/cosmos-validators-exporter.
    make install
    sudo useradd -rs /bin/false cosmos_exporter

    sudo cp ./cosmos-validators-exporter /usr/bin

    sudo tee /etc/systemd/system/cosmos-validators-exporter.service >/dev/null <<EOF
[Unit]
Description=Cosmos Validators Exporter
After=network-online.target

[Service]
User=$USER
TimeoutStartSec=0
CPUWeight=95
IOWeight=95
ExecStart=$ExecStart
Restart=always
RestartSec=2
LimitNOFILE=800000
KillSignal=SIGTERM

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable cosmos-validators-exporter
    sudo systemctl start cosmos-validators-exporter

    echo -e "\e[1m\e[32mcosmos-validators-exporter installed and started successfully. \e[0m"
else
    echo -e "\e[1m\e[33mcosmos-validators-exporter is already installed. \e[0m"
fi


# Check if the $HOME/cosmos-validators-exporter/config.toml file exists
if [ ! -f $HOME/cosmos-validators-exporter/config.toml ]; then
    echo -e "\e[1m\e[31mconfig.toml file does not exist, creation started.. \e[0m" && sleep 1
    touch $HOME/cosmos-validators-exporter/config.toml
    echo -e "\e[1m\e[32mconfig.toml file created successfully \e[0m" && sleep 1

    # Write the default configuration to the config.toml file
    CONFIG_CONTENT=$(cat <<EOF
# Global timeout for RPC queries, in seconds. Defaults to 5.
timeout = 10
# The address the exporter will listen on. Defaults to ":9560".
listen-address = ":9560"

# Logging config
[log]
# Log level. Change it to "debug" or even trace for more verbosity and debugging. Defaults to "info".
level = "debug"
# Whether all the logs should be written in JSON instead of a pretty-printed text. Useful if you have
# logging solutions, like Elastic stack. Defaults to false.
json = false

# List of queries to enable/disable.
# If the list is not provided, or the value for query is not specified,
# then this query will be enabled. Useful if some queries on some chains are broken or
# do not return any meaningful value (like signing info on e-Money) or are too heavy and
# the node can't handle such requests (like delegators count on Cosmos Hub).
[chains.queries]
# Query for delegators count. Isn't used on consumer chains.
delegations = true
# Query for unbonding delegations count. Isn't used on consumer chains.
unbonds = true
# Query for self-delegated amount. Isn't used on consumer chains.
self-delegation = true
# Query for all delegators count/ranking. Also used in total bonded tokens calculation and validator info.
validators = true
# Query for consumer chain's validators. Used in metric representing active validators count on chain.
consumer-validators = true
# Query for consumer chains list and info on provider. Only used on ICS provider chains.
consumer-info = true
# Query for validator unclaimed commission. Isn't used on consumer chains.
commission = true
# Query for validator unclaimed self-delegated rewards. Isn't used on consumer chains.
rewards = true
# Query for validator wallet balance
balance = true
# Query for validator's consumer assigned key. Only used for ICS.
# If disabled, then it'll be assumed that the validator is not using assigned keys.
assigned-key = true
# Query for validator signing info
signing-info = true
# Query for chain slashing params/missed blocks window
slashing-params = true
# Query for consumer's soft opt-out threshold. Is only used on consumer chains.
params = true
# Query for chain staking params/max validators count. Isn't used on consumer chains.
staking-params = true
# Query for node info (chain_id, app/cosmos-sdk/tendermint version, app name)
node-info = true
EOF
    )
    
    echo "$CONFIG_CONTENT" > $HOME/cosmos-validators-exporter/config.toml
    echo -e "\e[1m\e[32mDefault configuration written to config.toml \e[0m" && sleep 2
fi


echo '================================================='
echo -e "bond_denom: \e[1m\e[32m$BOND_DENOM\e[0m"
echo -e "bench_prefix: \e[1m\e[32m$BENCH_PREFIX\e[0m"
echo -e "LCD URL: \e[1m\e[32m$LCD_ENDPOINT\e[0m"
echo -e "Validator Address: \e[1m\e[32m$VALIDATOR_ADDR\e[0m"
echo -e "Consensus Address: \e[1m\e[32m$CONSENSUS_ADDR\e[0m"
echo -e "Chain Decimal: \e[1m\e[32m$CHAIN_DECIMAL\e[0m"

echo '================================================='
sleep 3

# Insert the chain configuration at the end of the config.toml file
CHAIN_CONTENT=$(cat <<EOF
[[chains]]
name = "$CHAIN_NAME"
lcd-endpoint = "$LCD_ENDPOINT"
base-denom = "$BOND_DENOM"
denoms = [
    { denom = "$BOND_DENOM", display-denom = "$DISPLAY_DENOM", coingecko-currency = "$COINGECKO_ID", denom-exponent = $CHAIN_DECIMAL, ignore = false }
]
bech-wallet-prefix = "$BENCH_PREFIX"
validators = [
    { address = "$VALIDATOR_ADDR", consensus-address = "$CONSENSUS_ADDR" }
]
is-provider = false
EOF
)

echo "$CHAIN_CONTENT" >> $HOME/cosmos-validators-exporter/config.toml
echo -e "\e[1m\e[32mChain configuration written to config.toml \e[0m" && sleep 1

echo -e "\e[1m\e[32mInstallation finished... \e[0m" && sleep 1
echo -e "\e[1m\e[32mPlease make sure port 9560 is open \e[0m" && sleep 1
