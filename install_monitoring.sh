#!/bin/bash
echo "=================================================="
echo -e "\033[0;35m"

echo "  _____                                _______        _     _    _       _     ";
echo " / ____|                              |__   __|      | |   | |  | |     | |    ";
echo "| |     ___  ___ _ __ ___   ___  ___     | | ___  ___| |__ | |__| |_   _| |__  ";
echo "| |    / _ \/ __| |_ \ _ \ / _ \/ __|    | |/ _ \/ __| |_ \|  __  | | | | |_ \ ";
echo "| |___| (_) \__ \ | | | | | (_) \__ \    | |  __/ (__| | | | |  | | |_| | |_) |";
echo " \_____\___/|___/_| |_| |_|\___/|___/    |_|\___|\___|_| |_|_|  |_|\____|____/ ";

echo -e "\e[0m"
echo "=================================================="

sleep 2

echo -e "\e[1m\e[32m1. Updating dependencies... \e[0m" && sleep 1
sudo apt-get update

echo "=================================================="

echo -e "\e[1m\e[32m2. Installing required dependencies... \e[0m" && sleep 1
sudo apt install jq -y
sudo apt install python3-pip -y
sudo pip install yq

echo "=================================================="

echo -e "\e[1m\e[32m3. Checking if Docker is installed... \e[0m" && sleep 1

if ! command -v docker &> /dev/null
then
    echo -e "\e[1m\e[32m3.1 Installing Docker... \e[0m" && sleep 1
    sudo apt-get install ca-certificates curl gnupg lsb-release wget -y
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    sudo chmod a+r /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install docker-ce docker-ce-cli containerd.io -y
fi

echo "=================================================="

echo -e "\e[1m\e[32m4. Checking if Docker Compose is installed ... \e[0m" && sleep 1

docker-compose version
if [ $? -ne 0 ]
then
    echo -e "\e[1m\e[32m4.1 Installing Docker Compose... \e[0m" && sleep 1
	docker_compose_version=$(wget -qO- https://api.github.com/repos/docker/compose/releases/latest | jq -r ".tag_name")
	sudo wget -O /usr/bin/docker-compose "https://github.com/docker/compose/releases/download/${docker_compose_version}/docker-compose-`uname -s`-`uname -m`"
	sudo chmod +x /usr/bin/docker-compose
fi

echo "=================================================="

echo -e "\e[1m\e[32m5. Downloading Node Monitoring config files ... \e[0m" && sleep 1
cd $HOME
rm -rf cosmos_node_monitoring
git clone https://github.com/Cosmos-TechHub/cosmos_node_monitoring.git

chmod +x $HOME/cosmos_node_monitoring/add_validator.sh
