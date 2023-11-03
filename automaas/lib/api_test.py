from automaas.lib import maas_connector

if __name__ == "__main__":
    c = maas_connector.get_client(
        "http://10.10.20.2:5240/MAAS/",
        "8mAJYnH8aBfUaCD8FZ:AGQkxHchhKZdg82XNs:dtAu8ApBkRGTywQkvX8nmvPC5hYhP57P")
    b = c.maas.get_upstream_dns()
    maas_connector.set_dns(c, "8.8.8.8")