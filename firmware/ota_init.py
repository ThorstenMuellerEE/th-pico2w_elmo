ota_requested = False
ota_in_progress = False
ota_updater = None

def init_ota():
    global ota_updater
    try:
        from ota_updater import GitHubOTAUpdater
        ota_updater = GitHubOTAUpdater()
        log_info("OTA initialized", "OTA")
    except Exception as e:
        log_error(f"OTA init failed: {e}", "OTA")