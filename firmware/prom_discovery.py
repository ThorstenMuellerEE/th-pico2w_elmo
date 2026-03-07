from config import SERVER_CONFIG, PROM_LABEL_CONFIG

def discovery_json():
    config = get_config_for_metrics()
    ip = wlan.ifconfig()[0]
    port = SERVER_CONFIG["port"]

    return """[
  {
    "targets": ["%s:%d"],
    "labels": {
      "job": "pico",
      "device": "%s",
      "location": "%s"
    }
  }
]""" % (
        ip,
        port,
        PROM_LABEL_CONFIG["device"],
        PROM_LABEL_CONFIG["location"],
    )
