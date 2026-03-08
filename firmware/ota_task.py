from logger import log_info, log_warn, log_error, log_debug
from ota_updater import download_update, check_for_updates, apply_update
import asyncio
import gc  


async def ota_task():
    global ota_requested, ota_in_progress

    while True:
        if ota_requested and not ota_in_progress:
            ota_in_progress = True
            ota_requested = False

            try:
                log_info("OTA update started", "OTA")

                gc.collect()
                has_update, new_version, err = ota_updater.check_for_updates()

                if not has_update:
                    log_info("No OTA update available", "OTA")
                    ota_in_progress = False
                    continue

                log_info(f"Downloading version {new_version}", "OTA")
                success = ota_updater.download_update(new_version, None)
                if not success:
                    raise RuntimeError("Download failed")

                gc.collect()

                log_info("Applying update", "OTA")
                success = ota_updater.apply_update(new_version)
                if not success:
                    raise RuntimeError("Apply failed")

                log_info("OTA successful, rebooting in 2s", "OTA")
                
                # Create reboot marker before reset
                try:
                    with open("ota_reboot_marker.txt", "w") as f:
                        import time
                        f.write(str(time.time()))
                    log_info("OTA reboot marker created", "OTA")
                except Exception as e:
                    log_warn(f"Could not create reboot marker: {e}", "OTA")
                
                await asyncio.sleep(2)
                
                gc.collect()
                await asyncio.sleep(0.5)  # Small delay to ensure filesystem operations complete
                
                import machine
                machine.reset()

            except Exception as e:
                log_error(f"OTA failed: {e}", "OTA")
                ota_in_progress = False
                gc.collect()

        await asyncio.sleep(1)

