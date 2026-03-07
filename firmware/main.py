"""
Async Prometheus Temperature Server
Raspberry Pi Zero 2 W – MicroPython + uasyncio
DS18B20 + internal temperature
"""

# BOOT PROTECTION: Try to import all modules with fallback to recovery mode
try:
    import uasyncio as asyncio # pyright: ignore[reportMissingImports]
    import network # pyright: ignore[reportMissingImports]
    import rp2 # pyright: ignore[reportMissingImports]
    import socket
    import time
    import gc
    #import dht

    from array import array
    
    from machine import Pin # pyright: ignore[reportMissingImports]
    from secrets import wifi_secrets
    import onewire # pyright: ignore[reportMissingImports]
    import ds18x20 # pyright: ignore[reportMissingImports]

    from logger import log_info, log_warn, log_error, log_debug

    from device_config import get_config_for_metrics
    from config import (
        METRIC_NAMES,
        METRICS_ENDPOINT,
        SENSOR_CONFIG_DS18B20,
        SERVER_CONFIG,
        PROM_LABEL_CONFIG,
        WIFI_CONFIG,
    )

    from internal_temp import (
        read_internal_temperature,
        celsius_to_fahrenheit,
    )

    from dashboard import dashboard_html
    
    from system_info import get_system_info

    # Import OTA updater
    from ota_updater import GitHubOTAUpdater

    # Import web interface functions
    from web_interface import (
        handle_start_page,
        handle_favicon_html,
        handle_root_page,
        handle_health_check,
        handle_config_page,
        handle_config_update,
        handle_logs_page,
        handle_update_page,
    )
    
    print("BOOT: All modules loaded successfully")
    RECOVERY_MODE = False

except ImportError as e:
    print(f"BOOT FAILURE: Module import failed: {e}")
    print("ACTIVATING RECOVERY MODE...")
    RECOVERY_MODE = True

    # Execute recovery mode
    exec(open('recovery.py').read())
    # Recovery mode runs its own server loop, so we exit here
    exit()

except Exception as e:
    print(f"BOOT FAILURE: Unexpected error: {e}")
    print("ACTIVATING RECOVERY MODE...")
    RECOVERY_MODE = True

    # Execute recovery mode
    exec(open('recovery.py').read())
    # Recovery mode runs its own server loop, so we exit here
    exit()


# Record boot time using ticks for accurate uptime calculation
boot_ticks = time.ticks_ms()


# ───────────────────────── WIFI ─────────────────────────
rp2.country(WIFI_CONFIG["country_code"])
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

async def wifi_connect():
    log_info("Connecting to WiFi...", "NETWORK")
    wlan.connect(wifi_secrets["ssid"], wifi_secrets["pw"])

    for _ in range(20):
        if wlan.status() == 3:
            log_info(f"WiFi connected: {wlan.ifconfig()[0]}", "NETWORK")
            return
        await asyncio.sleep(1)

    raise RuntimeError("WiFi connection failed")

# ───────────────────────── DS18B20 ─────────────────────────
DS_PIN = Pin(4)
ds = ds18x20.DS18X20(onewire.OneWire(DS_PIN))
DS_ROMS = ds.scan()

DS_LABELS = {
    b'\x28\x40\x43\xef\x80\x10\x00\x76': "air",
    b'\x28\x40\x6c\xa6\xc8\x0f\x00\x75': "lamp",
    b'\x28\x40\x74\x00\x7b\x00\x00\x66': "water",
}

log_info(f"Found {len(DS_ROMS)} DS18B20 sensors", "SENSOR")

# ───────────────────────── OTA UPDATER ─────────────────────────
ota_updater = None
try:
    ota_updater = GitHubOTAUpdater()
    log_info("OTA updater initialized", "OTA")
except Exception as e:
    log_warn(f"Failed to initialize OTA updater: {e}", "OTA")
    ota_updater = None

# ───────────────────────── SHARED STATE ─────────────────────────
temperatures = {}
boot_ticks = time.ticks_ms()
ota_requested = False  # Flag to trigger OTA update
ota_check_result = None  # Store check result: {'has_update': bool, 'latest_version': str, 'current_version': str}
ota_in_progress = False  # Flag to prevent concurrent OTA operations

# ───────────────────────── SENSOR TASK ─────────────────────────
async def sensor_task():
    global temperatures

    while True:
        try:
            ds.convert_temp()
            await asyncio.sleep_ms(750)

            temps = {}
            for rom in DS_ROMS:
                temp = ds.read_temp(rom)
                if temp is None:
                    continue
                label = DS_LABELS.get(rom, "unknown")
                temps[label] = round(temp, 2)

            temps["internal"] = round(read_internal_temperature(), 2)
            temperatures = temps

        except Exception as e:
            log_error(f"Sensor error: {e}", "SENSOR")

        await asyncio.sleep(5)

# ───────────────────────── OTA TASK ─────────────────────────
async def ota_task():
    global ota_requested, ota_in_progress
    
    print("OTA: Task started and monitoring...")

    while True:
        try:
            # Debug: Show current state periodically
            if ota_requested or ota_in_progress:
                print(f"OTA: Task state - requested={ota_requested}, in_progress={ota_in_progress}")
            
            if ota_requested and not ota_in_progress:
                ota_in_progress = True
                ota_requested = False
                print(f"OTA: Task activated - beginning update process")

                try:
                    if not ota_updater:
                        print("OTA: ERROR - OTA updater not available")
                        log_error("OTA updater not available", "OTA")
                        ota_in_progress = False
                        await asyncio.sleep(1)
                        continue

                    print("OTA: Starting update process...")
                    log_info("OTA update started", "OTA")
                    gc.collect()

                    print("OTA: Checking for updates on GitHub...")
                    has_update, new_version, release_data = ota_updater.check_for_updates()

                    if not has_update:
                        print("OTA: No update available")
                        log_info("No OTA update available", "OTA")
                        ota_in_progress = False
                        continue

                    print(f"OTA: Update found! Downloading version {new_version}...")
                    log_info(f"Downloading version {new_version}", "OTA")
                    success = ota_updater.download_update(new_version, None)
                    if not success:
                        print("OTA: Download failed!")
                        raise RuntimeError("Download failed")

                    print("OTA: Download successful, applying update...")
                    gc.collect()

                    print(f"OTA: Applying version {new_version}...")
                    log_info("Applying update", "OTA")
                    success = ota_updater.apply_update(new_version)
                    if not success:
                        print("OTA: Apply failed!")
                        raise RuntimeError("Apply failed")

                    print("OTA: Update successful! Rebooting in 2 seconds...")
                    log_info("OTA successful, rebooting in 2s", "OTA")
                    await asyncio.sleep(2)

                    import machine
                    machine.reset()

                except Exception as e:
                    print(f"OTA: ERROR - {e}")
                    log_error(f"OTA failed: {e}", "OTA")
                    ota_in_progress = False
                    gc.collect()
        except Exception as e:
            print(f"OTA: Task error - {e}")
            log_error(f"OTA task error: {e}", "OTA")
            await asyncio.sleep(5)

        await asyncio.sleep(1)

# ───────────────────────── METRICS ─────────────────────────
def format_metrics():
    config = get_config_for_metrics()
    labels = f'{{location="{PROM_LABEL_CONFIG["location"]}",device="{PROM_LABEL_CONFIG["device"]}"}}'

    metrics = []

    for name, value in temperatures.items():
        metric = f"pico_temperature_{name}"
        metrics.extend([
            f"# HELP {metric} Temperature in Celsius",
            f"# TYPE {metric} gauge",
            f"{metric}{labels} {value}",
        ])

    uptime = time.ticks_diff(time.ticks_ms(), boot_ticks) // 1000
    metrics.extend([
        "# HELP pico_uptime_seconds Device uptime",
        "# TYPE pico_uptime_seconds counter",
        f"pico_uptime_seconds{labels} {uptime}",
    ])

    return "\n".join(metrics) + "\n"

# ───────────────────────── HTTP SERVER ─────────────────────────
async def handle_client(reader, writer):
    global ota_requested, ota_check_result, ota_in_progress
    print("handle_client called.")
    #print("reader: ", reader)
    #print("writer: ", writer)

#     try:
#         # Parse request
#         #request_str = request.decode('utf-8')
#         request_str = reader.decode('utf-8')
#         lines = request_str.split('\r\n')
#         if not lines:
#             cl.send("HTTP/1.0 400 Bad Request\r\n\r\n")
#             return
# 
#         # Extract method and path
#         request_line = lines[0]
#         parts = request_line.split(' ')
#         if len(parts) < 2:
#             cl.send("HTTP/1.0 400 Bad Request\r\n\r\n")
#             return
# 
#         method = parts[0]
#         path = parts[1]
    try:
        request = await reader.readline()
        print("called request:", request)
        if not request:
            await writer.aclose()
            return

        method = request.decode().split(" ")[0].split("?")[0]
        print("called method:", method)
        path = request.decode().split(" ")[1].split("?")[0]
        print("called path:", path)
        
        # Read headers and capture Content-Length for POST requests
        headers = {}
        while True:
            header_line = await reader.readline()
            if header_line == b"\r\n":
                break
            header_str = header_line.decode().strip()
            if ':' in header_str:
                key, value = header_str.split(':', 1)
                headers[key.strip().lower()] = value.strip()
        
        # Read body for POST requests
        request_body = b""
        if method == "POST":
            content_length = int(headers.get('content-length', 0))
            if content_length > 0:
                request_body = await reader.readexactly(content_length)
               
        if method == "GET" and path == "/":
            system_info = get_system_info(wlan, boot_ticks)
            print("system_info:", system_info)
            response = handle_start_page(system_info)
            #writer.write(b"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n")
            writer.write(response.encode())

        elif method == "GET" and path == "/root":
            # Root endpoint - dashboard interface
            #sensor_data = read_dht22()
            # TODO disabled for the moment
            #sensor_data = read_ds18b20()
            system_info = get_system_info(wlan, boot_ticks)
            #response = handle_root_page(sensor_data, system_info, ota_updater)
            response = handle_root_page(system_info)
            writer.write(response.encode())

        elif path == "/dashboard":
            html = dashboard_html(temperatures, wlan, boot_ticks, ota_in_progress)
            writer.write(b"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n")
            writer.write(html.encode())
            
        elif path == "/favicon.ico":
            html = handle_favicon_html()
            writer.write(b"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n")
            writer.write(html.encode())
            
        elif path == METRICS_ENDPOINT:
            response = format_metrics()
            writer.write(b"HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\n\r\n")
            writer.write(response.encode())
            
        elif method == "GET" and path == "/health":
            # Health check endpoint
            #sensor_data = read_dht22()
            #sensor_data = read_ds18b20()
            print("GET /health called")
            system_info = get_system_info(wlan, boot_ticks)
            print("system_info for health:", system_info)
            # TODO: extend health check later with ota_updater and wlan
            #response = handle_health_check(sensor_data, system_info, ota_updater, wlan, ssid, request_str)
            response = handle_health_check(system_info)
            writer.write(response)

        elif method == "GET" and path == "/config":
            # Configuration page
            response = handle_config_page()
            writer.write(response)

        elif method == "POST" and path == "/config_update":
            # Configuration update
            print(f"CONFIG: Received POST request with body size: {len(request_body)} bytes")
            # TODO: enable ota_updater later
            #response = handle_config_update(request_body, ota_updater)
            response = handle_config_update(request_body)
            writer.write(response)

        elif method == "GET" and path == "/logs":
            # Logs page endpoint
            response = handle_logs_page(request)
            writer.write(response)

        elif method == "GET" and path == "/update":
            # OTA update page endpoint
            response = handle_update_page(ota_updater, ota_check_result)
            writer.write(response)
        
        elif method == "POST" and path == "/update":
            # OTA check and update endpoint
            if ota_updater:
                # Check for updates
                if not ota_in_progress:
                    print("OTA: User requested update check...")
                    has_update, latest_version, release_data = ota_updater.check_for_updates()
                    ota_check_result = {
                        'has_update': has_update,
                        'latest_version': latest_version,
                        'current_version': ota_updater.get_current_version()
                    }
                    print(f"OTA: Check complete - has_update={has_update}, latest={latest_version}")
                    log_info(f"Update check: has_update={has_update}, latest={latest_version}", "OTA")
                response = b"HTTP/1.0 302 Found\r\nLocation: /update\r\n\r\n"
            else:
                response = b"HTTP/1.0 500 Internal Server Error\r\nContent-Type: text/plain\r\n\r\nOTA updater not initialized"
            writer.write(response)
        
        elif method == "POST" and path == "/update_perform":
            # Perform actual update if available
            if ota_updater and ota_check_result and ota_check_result.get('has_update') and not ota_in_progress:
                ota_requested = True
                print(f"OTA: User confirmed update to {ota_check_result.get('latest_version')} - starting download...")
                print(f"OTA: Set ota_requested={ota_requested}, ota_in_progress={ota_in_progress}")
                log_info("OTA update triggered by user", "OTA")
                response = b"HTTP/1.0 302 Found\r\nLocation: /update\r\n\r\n"
            else:
                print("OTA: Update request rejected - no update available or update in progress")
                print(f"OTA: Conditions - updater={ota_updater}, check_result={ota_check_result}, has_update={ota_check_result.get('has_update') if ota_check_result else 'N/A'}, in_progress={ota_in_progress}")
                response = b"HTTP/1.0 400 Bad Request\r\nContent-Type: text/plain\r\n\r\nNo update available or update in progress"
            writer.write(response)
                
        else:
            writer.write(b"HTTP/1.0 404 Not Found\r\n\r\n")

        await writer.drain()
        
    
    except Exception as e:
        log_error(f"HTTP error: {e}", "HTTP")
    finally:
        await writer.aclose()

async def http_server():
    server = await asyncio.start_server(
        handle_client,
        "0.0.0.0",
        SERVER_CONFIG["port"]
    )
     
    log_info(f"HTTP server running on port {SERVER_CONFIG['port']}", "SYSTEM")
    await server.wait_closed()

# ───────────────────────── MAIN ─────────────────────────
async def main():
    gc.collect()
    await wifi_connect()

#    init_ota()

    asyncio.create_task(sensor_task())
    asyncio.create_task(ota_task())
    await http_server()



# ───────────────────────── START ─────────────────────────
try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()
