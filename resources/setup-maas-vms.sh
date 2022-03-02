#!/bin/bash

# login into maas
maas  login automaas http://10.10.10.2:5240/MAAS/ Fa7X5ejRtzACur6PBh:YRxB9JRvf79S5xu7QY:jFbSUUwcvZRCDS8ATS832pJfPGNZfy9a
# get the list of new machines
maas automaas machines read | jq -r '(["HOSTNAME","SYSID","POWER","STATUS",
"OWNER", "TAGS", "POOL", "VLAN","FABRIC","SUBNET"] | (., map(length*"-"))),
(.[] | [.hostname, .system_id, .power_state, .status_name, .owner // "-", 
.tag_names[0] // "-", .pool.name,
.boot_interface.vlan.name, .boot_interface.vlan.fabric,
.boot_interface.links[0].subnet.name]) | @tsv' | column -t
# commission all new machines
# wait the machines to be in ready state
# configure the interfaces of each machine
maas $PROFILE interfaces read sttr3b | jq ".[] | \
    {id:.id, name:.name, mac:.mac_address, vid:.vlan.vid, fabric:.vlan.fabric}" --compact-output


client = maas.client.connect("http://10.10.10.2:5240/MAAS/", apikey="Fa7X5ejRtzACur6PBh:YRxB9JRvf79S5xu7QY:jFbSUUwcvZRCDS8ATS832pJfPGNZfy9a")


#maas setup from scratch
sudo snap install maas
sudo maas init region+rack --database-uri maas-test-db:///
api_key=$(sudo maas apikey --username admin)
# sudo maas login default http://10.212.123.163:5240/MAAS ${api_key}
sudo maas-cli login -p default --apikey ${api_key} http://10.212.123.163:5240/MAAS
