#!/usr/bin/env bash

read -p "Enter bond_denom value, for example, ubld for Agoric: " BOND_DENOM
read -p "Enter bench_prefix value, for example, agoric for Agoric: " BENCH_PREFIX
read -p "Enter rpc_port value or hit Enter for default port [26657]: " RPC_PORT
RPC_PORT=${RPC_PORT:-26657}
read -p "Enter grpc_port value or hit Enter for default port [9090]: " GRPC_PORT
GRPC_PORT=${GRPC_PORT:-9090}
#read -p "Enter chain decimal value or hit Enter for default decimal [1000000]: " CHAIN_DECIMAL
#CHAIN_DECIMAL=${CHAIN_DECIMAL:-1000000}
read -p "Enter the network precision or hit Enter for default precision [6]: " CHAIN_DECIMAL
CHAIN_DECIMAL=${CHAIN_DECIMAL:-6}
read -p "Enter account prefix or hit Enter to use the default prefix [$BENCH_PREFIX]: " ACCOUNT_PREFIX
ACCOUNT_PREFIX=${ACCOUNT_PREFIX:-$BENCH_PREFIX}
read -p "Enter account pubkey prefix or hit Enter to use the default prefix [$BENCH_PREFIX]: " ACCOUNT_P_PREFIX
ACCOUNT_P_PREFIX=${ACCOUNT_P_PREFIX:-$BENCH_PREFIX}
read -p "Enter validator prefix or hit Enter to use the default prefix [$BENCH_PREFIX]: " VAL_PREFIX
VAL_PREFIX=${VAL_PREFIX:-$BENCH_PREFIX}
read -p "Enter validator pubkey prefix or hit Enter to use the default prefix [$BENCH_PREFIX]: " VAL_P_PREFIX
VAL_P_PREFIX=${VAL_P_PREFIX:-$BENCH_PREFIX}
read -p "Enter tendermint concensus prefix or hit Enter to use the default prefix [$BENCH_PREFIX]: " CONS_PREFIX
CONS_PREFIX=${CONS_PREFIX:-$BENCH_PREFIX}
read -p "Enter tendermint concensus pubkey prefix or hit Enter to use the default prefix [$BENCH_PREFIX]: " CONS_P_PREFIX
CONS_P_PREFIX=${CONS_P_PREFIX:-$BENCH_PREFIX}

#ExecStart="cosmos-exporter --denom ${BOND_DENOM} --denom-coefficient ${CHAIN_DECIMAL} --bech-prefix ${BENCH_PREFIX} --tendermint-rpc http://localhost:${RPC_PORT} --node localhost:${GRPC_PORT}"
ExecStart="cosmos-exporter --denom ${BOND_DENOM} --denom-exponent ${CHAIN_DECIMAL} --bech-prefix ${BENCH_PREFIX} --tendermint-rpc http://localhost:${RPC_PORT} --node localhost:${GRPC_PORT}"


if [ "$ACCOUNT_PREFIX" != "$BENCH_PREFIX" ]; then
    ExecStart="$ExecStart --bech-account-prefix $ACCOUNT_PREFIX"
fi

if [ "$ACCOUNT_P_PREFIX" != "$BENCH_PREFIX" ]; then
    ExecStart="$ExecStart --bech-account-pubkey-prefix $ACCOUNT_P_PREFIX"
fi

if [ "$VAL_PREFIX" != "$BENCH_PREFIX" ]; then
    ExecStart="$ExecStart --bech-validator-prefix $VAL_PREFIX"
fi

if [ "$VAL_P_PREFIX" != "$BENCH_PREFIX" ]; then
    ExecStart="$ExecStart --bech-validator-pubkey-prefix $VAL_P_PREFIX"
fi

if [ "$CONS_PREFIX" != "$BENCH_PREFIX" ]; then
    ExecStart="$ExecStart --bech-consensus-node-prefix $CONS_PREFIX"
fi

if [ "$CONS_P_PREFIX" != "$BENCH_PREFIX" ]; then
    ExecStart="$ExecStart --bech-consensus-node-pubkey-prefix $CONS_P_PREFIX"
fi

echo '================================================='
echo -e "bond_denom: \e[1m\e[32m$BOND_DENOM\e[0m"
echo -e "bench_prefix: \e[1m\e[32m$BENCH_PREFIX\e[0m"
echo -e "rpc_port: \e[1m\e[32m$RPC_PORT\e[0m"
echo -e "grpc_port: \e[1m\e[32m$GRPC_PORT\e[0m"
echo '================================================='
sleep 3

echo -e "\e[1m\e[32m1. Installing cosmos-exporter... \e[0m" && sleep 1

# install cosmos-exporter last release (depreciated)
# wget https://github.com/solarlabsteam/cosmos-exporter/releases/download/v0.3.0/cosmos-exporter_0.3.0_Linux_x86_64.tar.gz
# tar xvfz cosmos-exporter*
#sudo cp ./cosmos-exporter /usr/bin
#rm cosmos-exporter* -rf

# install cosmos-exporter master branch (compatible with ethermint)
git clone https://github.com/solarlabsteam/cosmos-exporter.git
cd cosmos-exporter
go build -o cosmos-exporter
sudo cp cosmos-exporter /usr/bin
cd
rm -rf cosmos-exporter

sudo useradd -rs /bin/false cosmos_exporter

sudo tee /etc/systemd/system/${BENCH_PREFIX}-cosmos-exporter.service >/dev/null <<EOF
[Unit]
Description=Cosmos Exporter
After=network-online.target

[Service]
User=cosmos_exporter
Group=cosmos_exporter
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

echo -e "\e[1m\e[32m2. Installing node-exporter... \e[0m" && sleep 1
# install node-exporter
wget https://github.com/prometheus/node_exporter/releases/download/v1.3.1/node_exporter-1.3.1.linux-amd64.tar.gz
tar xvfz node_exporter-*.*-amd64.tar.gz
sudo mv node_exporter-*.*-amd64/node_exporter /usr/local/bin/
rm node_exporter-* -rf

sudo useradd -rs /bin/false node_exporter

sudo tee <<EOF >/dev/null /etc/systemd/system/node_exporter.service
[Unit]
Description=Node Exporter
After=network.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable cosmos-exporter
sudo systemctl start cosmos-exporter
sudo systemctl enable node_exporter
sudo systemctl start node_exporter

echo -e "\e[1m\e[32mInstallation finished... \e[0m" && sleep 1
echo -e "\e[1m\e[32mPlease make sure ports 9100 and 9300 are open \e[0m" && sleep 1
