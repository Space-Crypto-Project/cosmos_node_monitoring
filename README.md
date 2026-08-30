# Instructions on how to set up monitoring stack for your cosmos validator

## Prerequisites

### Install exporters on validator node
First of all you will have to install exporters on validator node. For that you can use one-liner below
```
wget -O install_exporters.sh https://github.com/Space-Crypto-Project/cosmos_node_monitoring/master/install_exporters.sh && chmod +x install_exporters.sh && ./install_exporters.sh
```

| KEY |VALUE |
|---------------|-------------|
| **bond_denom** | Denominated token name, for example, `uatom` for Cosmos Hub. You can find it in genesis file |
| **bench_prefix** | Prefix for chain addresses, for example, `atom` for Cosmos Hub. You can find it in public addresses like this **agoric**_valoper1zyyz4m9ytdf60fn9yaafx7uy7h463n7alv2ete_ |
| **rpc_port** | Your validator `rpc` port that is defined in `config.toml` file. Default value for aura is `26657` |
| **grpc_port** | Your validator `grpc` port that is defined in `app.toml` file. Default value for aura is `9090` |
| **Chain Precision** | Network precision. Default value is `6` |

make sure prometheus is enabled in validator `config.toml` file:
```
sed -i -e "s/prometheus = false/prometheus = true/" $HOME/.gaiad/config/config.toml
```

make sure following ports are open:
- `9100` ([node-exporter](https://github.com/prometheus/node_exporter))
- `9300` ([cosmos-exporter](https://github.com/solarlabsteam/cosmos-exporter))
- `26660` (validator prometheus)

### Install validator exporter on validator node
Additionally, you can install [cosmos validator exporter](https://github.com/QuokkaStake/cosmos-validators-exporter). 
We recommend using this exporter if you run multiple validators on the same server.

For that you can use one-liner below
```
wget -O install_validator_exporter.sh https://raw.githubusercontent.com/Space-Crypto-Project/cosmos_node_monitoring/master/install_cosmos_validator_exporter.sh && chmod +x install_validator_exporter.sh && ./install_validator_exporter.sh
```

| KEY |VALUE |
|---------------|-------------|
| **Chain Name** | Blockchain Name, for example, `cosmos` for Cosmos |
| **LCD Endpoint** | Use local or third party endpoint, for example: `http://localhost/26657`
| **bond_denom** | Denominated token name, for example, `uatom` for Cosmos Hub or `ibc/xxxxx` for IBC denoms. You can find it in genesis file |
| **Ticker** | Token ticker, for example, `atom` for Cosmos Hub. |
| **coingecko id** | Coingecko ID, specify it if you want to also get the wallet balance example: `cosmos` |
| **bench_prefix** | Prefix for chain addresses, for example, `agoric` for Agoric. You can find it in public addresses like this **agoric**_valoper1zyyz4m9ytdf60fn9yaafx7uy7h463n7alv2ete_ |
| **validator address** | Valoper Address |
| **consensus address** | Valcon / Consensus Address, specify it if you want to get signing-infos metrics |
| **Chain Precision** | Network precision. Default value is `6` |

make sure prometheus is enabled in validator `config.toml` file:
```
sed -i -e "s/prometheus = false/prometheus = true/" $HOME/.gaiad/config/config.toml
```

make sure following ports are open:
- `9560` ([cosmos-validators-exporter](https://github.com/QuokkaStake/cosmos-validators-exporter))
- `26660` (validator prometheus)

## Deployment
Monitoring stack needs to be deployed on seperate machine to be able to notify in case if validator goes down! 
To run monitoring stack you dont need beastly server with multiple cores. It will be more than enough to run it on smallest available vps

### System requirements
Ubuntu 20.04 / 1 VCPU / 2 GB RAM / 20 GB SSD

### Install monitoring stack
To install monitirng stack you can use one-liner below
```
wget -O install_monitoring.sh https://github.com/Cosmos-TechHub/cosmos_node_monitoring/master/install_monitoring.sh && chmod +x install_monitoring.sh && ./install_monitoring.sh
```

### Copy _.env.example_ into _.env_
```
cp $HOME/cosmos_node_monitoring/config/.env.example $HOME/cosmos_node_monitoring/config/.env
```

### Update values in _.env_ file
```
vim $HOME/cosmos_node_monitoring/config/.env
```

| KEY | VALUE |
|---------------|-------------|
| TELEGRAM_ADMIN | Your user id you can get from [@userinfobot](https://t.me/userinfobot). The bot will only reply to messages sent from the user. All other messages are dropped and logged on the bot's console |
| TELEGRAM_TOKEN | Your telegram bot access token you can get from [@botfather](https://telegram.me/botfather). To generate new token just follow a few simple steps described [here](https://core.telegram.org/bots#6-botfather) |

### Notification policies

Telegram and e-mail have independent alert lists and delivery cadences. Run `bash run_monitoring.sh` after changing `config/.env`; it renders and restarts Alertmanager. The settings below use Alertmanager duration syntax (`0s`, `5m`, `1h`, `24h`). Alert lists are comma-separated names from [`prometheus/alerts/alert.rules`](prometheus/alerts/alert.rules); the launcher rejects unknown names before changing the active runtime configuration.

Telegram keeps the historical defaults: every active alert, immediate delivery, five-minute grouping, hourly reminders, and a resolved message. Change only the values you need:

| KEY | Default | VALUE |
|---------------|-------------|-------------|
| TELEGRAM_ALERTS | `all` | `all` for every active alert, or selected names such as `InstanceDown,IsJailed` |
| TELEGRAM_GROUP_WAIT | `0s` | Wait before the first notification for a group |
| TELEGRAM_GROUP_INTERVAL | `5m` | Minimum delay for new alerts added to an existing group |
| TELEGRAM_REPEAT_INTERVAL | `1h` | Reminder cadence while an incident remains active |

### Optional SMTP e-mail notifications

To enable SMTP e-mail, set the following local values in `config/.env` and change `EMAIL_NOTIFICATIONS_ENABLED` to `true`:

| KEY | VALUE |
|---------------|-------------|
| EMAIL_SMTP_HOST | SMTP relay hostname, for example `smtp.example.invalid` |
| EMAIL_SMTP_PORT | SMTP relay port, such as `587` |
| EMAIL_SMTP_FROM | Sender address, such as `alerts@example.invalid` |
| EMAIL_SMTP_TO | Recipient list; separate multiple recipients with commas, for example `primary@example.invalid,backup@example.invalid` |
| EMAIL_SMTP_USERNAME / EMAIL_SMTP_PASSWORD | Optional SMTP authentication pair; set both or neither |
| EMAIL_SMTP_REQUIRE_TLS | `true` by default; set `false` only if the local SMTP relay explicitly requires it |

E-mail defaults to immediate firing and resolution messages only for `InstanceDown`, `IsJailed`, and `ValidatorIsJailed`; repeated alerts are limited to once every 24 hours. Its policy does not affect Telegram:

| KEY | Default | VALUE |
|---------------|-------------|-------------|
| EMAIL_ALERTS | `InstanceDown,IsJailed,ValidatorIsJailed` | Selected active alert names; use `all` to receive every active alert by e-mail |
| EMAIL_GROUP_WAIT | `0s` | Wait before the first e-mail for a group |
| EMAIL_GROUP_INTERVAL | `5m` | Minimum delay for new alerts added to an existing e-mail group |
| EMAIL_REPEAT_INTERVAL | `24h` | Reminder cadence while an e-mail incident remains active |

Matching e-mail alerts still go to Telegram. The launcher reads a deliberately limited `KEY=VALUE` format: quote values containing spaces, and do not use shell interpolation such as `${VARIABLE}` or `$(command)`.

### Add validator into _prometheus_ configuration file

If you installed [cosmos-exporter](https://github.com/solarlabsteam/cosmos-exporter), use the following command with specified `VALIDATOR_IP`, `PROMETHEUS_PORT`, `VALOPER_ADDRESS`, `WALLET_ADDRESS` and `PROJECT_NAME`
```
$ cd cosmos_node_monitoring
$ ./add_validator_cexp.sh VALIDATOR_IP PROMETHEUS_PORT VALOPER_ADDRESS WALLET_ADDRESS PROJECT_NAME
```

> example: ```./add_validator_cexp.sh 1.2.3.4 26660 cosmosvaloper1s9rtstp8amx9vgsekhf3rk4rdr7qvg8dlxuy8v cosmos1s9rtstp8amx9vgsekhf3rk4rdr7qvg8d6jg3tl cosmos```


If you installed [cosmos-validators-exporter](https://github.com/QuokkaStake/cosmos-validators-exporter), use the following command with specified `VALIDATOR_IP`, `PROMETHEUS_PORT`, and `PROJECT_NAME`
```
$ cd cosmos_node_monitoring
$ ../add_validator.sh VALIDATOR_IP PROMETHEUS_PORT PROJECT_NAME
```

> example: ```../add_validator.sh 1.2.3.4 26660 kopi_testnet```

To add more validators just run commands above with validator values

### Run monitoring stack

Render the local Alertmanager configuration and deploy the monitoring stack:
```
cd $HOME/cosmos_node_monitoring && bash run_monitoring.sh
```

The launcher requires Docker Compose v2 because authenticated SMTP uses a Compose secret. It passes `config/.env` directly to Compose; do not export its values into your shell profile. It restricts that directory to the local owner, renders non-secret SMTP settings there, injects the SMTP password as an Alertmanager-only Compose secret, and restarts Alertmanager so changed SMTP settings take effect.

ports used:
- `8080` (alertmanager-bot)
- `9090` (prometheus)
- `9093` (alertmanager)
- `9999` (grafana)

## Configuration

### Configure Grafana
1. Open Grafana in your web browser. It should be available on port `9999`

![image](https://user-images.githubusercontent.com/50621007/160622455-09af4fbf-2efb-4afb-a8f8-57a2b247f705.png)

2. Login using defaults `admin/admin` and change password

3. Import custom dashboard

3.1. Press "+" icon on the left panel and then choose **"Import"**

![image](https://user-images.githubusercontent.com/50621007/160622732-aa9fe887-823c-4586-9fad-4c2c7fdf5011.png)

3.2. Input grafana.com dashboard id `15991` and press **"Load"**

![image](https://user-images.githubusercontent.com/50621007/160625753-b9f11287-a3ba-4529-96f9-7c9113c6df3a.png)

3.3. Select Prometheus data source and press **"Import"**

![image](https://user-images.githubusercontent.com/50621007/160623287-0340acf8-2d30-47e7-8a3a-56295bea8a15.png)

4. Change your chain explorer url

4.1. Edit **"Top validators missing blocks panel"**

![image](https://user-images.githubusercontent.com/50621007/160623476-50d8bf62-03cd-4de6-92de-53bc2df830cc.png)

4.2. Go to **"Overrides"** and edit **"Data links"**

![image](https://user-images.githubusercontent.com/50621007/160623555-ae7e9d54-9a0b-4ec9-9b1d-278fafe06682.png)

4.3 Change url to your chain data explorer and hit **"Save"**

![image](https://user-images.githubusercontent.com/50621007/160623647-1f23a1dc-35b0-494f-8ba4-fb4d90f1b0c5.png)

4.4. Hit **"Save"** button on the left top corner to save changes to dashboard

5. Congratulations you have successfully configured Cosmos Validator Dashboard


### Configrure Telegram alerting
1. Open conversation with your Telegram bot you created with [@botfather](https://telegram.me/botfather) and type `/start` to activate bot

![image](https://user-images.githubusercontent.com/50621007/160623782-e18a42c4-659d-477b-9189-43d9027d518c.png)

2. Now you are all set! If you want see other commands type `/help`

> If you want learn more about `alermanager-bot` please visit [their github repo](https://github.com/metalmatze/alertmanager-bot/)

## Testing

### Test alerts
1. Use a disposable validator or test environment. Do not stop a production exporter to trigger an alert.
2. Start the stack with `bash run_monitoring.sh`, then inspect the Alertmanager logs with `docker compose logs alertmanager`.
3. For SMTP, use a disposable SMTP endpoint or leave `EMAIL_NOTIFICATIONS_ENABLED=false`; never test with a production recipient until the configuration is verified.
4. Confirm that the test alert reaches Telegram and, when selected and enabled, the configured e-mail recipients. Resolved alerts are sent to both selected channels.

## Dashboard contents
Grafana dashboard is devided into 4 sections:
- **Validator health** - main stats for validator health. connected peers and missed blocks

![image](https://user-images.githubusercontent.com/50621007/160629676-bc3c4f0f-66df-4a5f-9844-dca308072e7a.png)

- **Chain health** - summary of chain health stats and list of top validators missing blocks

![image](https://user-images.githubusercontent.com/50621007/160629937-52253f35-8782-4dd2-80cc-ad31d0231a84.png)

- **Validator stats** - information about validator such as rank, bounded tokens, comission, delegations and rewards

![image](https://user-images.githubusercontent.com/50621007/160630119-0abad099-b138-4f61-9e73-49506c2295ff.png)

- **Hardware health** - system hardware metrics. cpu, ram, network usage

![image](https://user-images.githubusercontent.com/50621007/160630213-5e92b3ce-92c9-4f48-8856-383ca884b621.png)

## Cleanup all container data
```
cd $HOME/cosmos_node_monitoring
docker-compose down
docker volume prune -f
```

## Reference list
Resources I used in this project:
- Grafana Validator stats [Cosmos Validator by freak12techno](https://grafana.com/grafana/dashboards/14914)
- Grafana Hardware health [AgoricTools by Chainode](https://github.com/Chainode/AgoricTools)
- Stack of monitoring tools, docker configuration [node_tooling by Xiphiar](https://github.com/Xiphiar/node_tooling/)
- Alertmanager telegram bot [alertmanager-bot by metalmatze](https://github.com/metalmatze/alertmanager-bot)
