import libvirt
from maas.client import connect

client = maas.client.connect(
    "http://10.230.62.108:5240/MAAS/",
    apikey="Fa7X5ejRtzACur6PBh:YRxB9JRvf79S5xu7QY:jFbSUUwcvZRCDS8ATS832pJfPGNZfy9a",
    insecure=True)

def rename_maas_domains():
