"""
Minimal Web Interface for Pico W Prometheus DHT22 Sensor
Ultra-lightweight implementation to maximize memory for OTA updates.
"""

import time
import gc
from logger import log_info, log_warn, log_error, log_debug, get_logger
from device_config import (
    load_device_config,
    save_device_config,
    validate_config_input,
    get_config_for_metrics,
)
from config import SENSOR_CONFIG_DHT22, SENSOR_CONFIG_DS18B20, WIFI_CONFIG, SERVER_CONFIG, METRICS_ENDPOINT

print("web_interface.py started")

# Unified CSS theme for all web pages
UNIFIED_CSS = """
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    color: #e0e0e0;
    margin: 0;
    padding: 20px;
    min-height: 100vh;
}
.container {
    max-width: 800px;
    margin: 0 auto;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 10px;
    padding: 20px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}
h1 {
    color: #00d4ff;
    text-align: center;
    margin-bottom: 30px;
    font-size: 2.2em;
    text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
    border-bottom: 2px solid #00d4ff;
    padding-bottom: 10px;
}
h2 {
    color: #ff6b6b;
    margin-top: 30px;
    margin-bottom: 15px;
    font-size: 1.4em;
    border-left: 4px solid #ff6b6b;
    padding-left: 15px;
}
p {
    line-height: 1.6;
    margin: 10px 0;
}
.status-info {
    background: rgba(0, 212, 255, 0.1);
    border: 1px solid #00d4ff;
    border-radius: 5px;
    padding: 15px;
    margin: 15px 0;
}
.nav-links {
    text-align: center;
    margin: 20px 0;
    padding: 15px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 5px;
}
.nav-links a {
    color: #00d4ff;
    text-decoration: none;
    margin: 0 15px;
    font-weight: bold;
    transition: all 0.3s ease;
}
.nav-links a:hover {
    color: #ff6b6b;
    text-decoration: underline;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 5px;
    overflow: hidden;
}
th, td {
    padding: 12px;
    text-align: left;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
th {
    background: #00d4ff;
    color: #1a1a2e;
    font-weight: bold;
}
tr:hover {
    background: rgba(255, 255, 255, 0.05);
}
.ok { color: #4CAF50; font-weight: bold; }
.warn { color: #ff9800; font-weight: bold; }
.error { color: #f44336; font-weight: bold; }
input[type="text"], input[type="number"], select {
    background: #2a2a4e;
    color: #e0e0e0;
    border: 1px solid #00d4ff;
    padding: 8px 12px;
    border-radius: 4px;
    width: 100%;
    max-width: 300px;
    font-size: 14px;
}
input[type="text"]:focus, input[type="number"]:focus, select:focus {
    outline: none;
    border-color: #ff6b6b;
    box-shadow: 0 0 5px rgba(255, 107, 107, 0.5);
}
input[type="checkbox"] {
    margin-right: 8px;
    accent-color: #00d4ff;
}
input[type="submit"] {
    background: linear-gradient(45deg, #00d4ff, #0099cc);
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 5px;
    cursor: pointer;
    font-weight: bold;
    font-size: 16px;
    transition: all 0.3s ease;
    margin-top: 10px;
}
input[type="submit"]:hover {
    background: linear-gradient(45deg, #ff6b6b, #cc5555);
    transform: translateY(-2px);
    box-shadow: 0 4px 15px rgba(255, 107, 107, 0.3);
}
ul {
    list-style: none;
    padding: 0;
}
li {
    background: rgba(255, 255, 255, 0.05);
    margin: 5px 0;
    padding: 10px 15px;
    border-radius: 5px;
    border-left: 4px solid #00d4ff;
}
a {
    color: #00d4ff;
    text-decoration: none;
    transition: color 0.3s ease;
}
a:hover {
    color: #ff6b6b;
    text-decoration: underline;
}
"""

# Complete navigation menu for all pages
COMPLETE_NAVIGATION = """
<div class="nav-links">
<strong>Navigation:</strong><br>
<a href="/">Dashboard</a> |
<a href="/dashboard">Sensor View</a> |
<a href="/health">Health Check</a> |
<a href="/config">Configuration</a> |
<a href="/logs">System Logs</a> |
<a href="/metrics">Metrics</a> |
<a href="/update">OTA Update</a> |
<a href="/reboot">Reboot Device</a>
</div>
"""



def unquote_plus(string):
    """MicroPython-compatible URL decoding function."""
    # Replace + with spaces
    string = string.replace('+', ' ')

    # Basic URL decoding for common characters
    replacements = {
        '%20': ' ', '%21': '!', '%22': '"', '%23': '#', '%24': '$', '%25': '%',
        '%26': '&', '%27': "'", '%28': '(', '%29': ')', '%2A': '*', '%2B': '+',
        '%2C': ',', '%2D': '-', '%2E': '.', '%2F': '/', '%3A': ':', '%3B': ';',
        '%3C': '<', '%3D': '=', '%3E': '>', '%3F': '?', '%40': '@', '%5B': '[',
        '%5C': '\\', '%5D': ']', '%5E': '^', '%5F': '_', '%60': '`', '%7B': '{',
        '%7C': '|', '%7D': '}', '%7E': '~'
    }

    for encoded, decoded in replacements.items():
        string = string.replace(encoded, decoded)

    return string

def handle_start_page(system_info):
    """Handle start page with minimal plain text dashboard."""
    print("web_interface::handle_start_page called")
    try:
        wifi_status, wifi_class, ip_address = system_info["wifi"]
        uptime_hours, uptime_minutes = system_info["uptime"]
        memory_mb = system_info["memory"]
        #version = ota_updater.get_current_version() if ota_updater else "unknown"

        # Ultra-minimal HTML
        html = f"""<!DOCTYPE html><html><head><title>Pico 2W Sensor</title>
<style>{UNIFIED_CSS}</style></head><body>
<div class="container">
<h1>Pico 2W Sensor Dashboard</h1>
<div class="status-info">
<p><strong>Network:</strong> {wifi_status} | <strong>IP:</strong> {ip_address}</p>
<p><strong>Uptime:</strong> {uptime_hours:02d}:{uptime_minutes:02d} | <strong>Memory:</strong> {memory_mb}KB</p>
</div>
{COMPLETE_NAVIGATION}
</div></body></html>"""

        return f"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n{html}"
    except Exception as e:
        log_error(f"Root page error: {e}", "HTTP")
        return f"HTTP/1.0 500 Internal Server Error\r\nContent-Type: text/plain\r\n\r\nError: {e}"
    
def handle_root_page(system_info):
    """Handle start page with minimal plain text dashboard."""
    print("web_interfac::handle_start_page called")
    try:
        wifi_status, wifi_class, ip_address = system_info["wifi"]
        uptime_hours, uptime_minutes = system_info["uptime"]
        memory_mb = system_info["memory"]
        #version = ota_updater.get_current_version() if ota_updater else "unknown"

        # Ultra-minimal HTML
        html = f"""<!DOCTYPE html><html><head><title>Pico 2W Sensor</title>
<style>{UNIFIED_CSS}</style></head><body>
<div class="container">
<h1>Pico 2W Sensor Dashboard</h1>
<div class="status-info">
<p><strong>Network:</strong> {wifi_status} | <strong>IP:</strong> {ip_address}</p>
<p><strong>Uptime:</strong> {uptime_hours:02d}:{uptime_minutes:02d} | <strong>Memory:</strong> {memory_mb}KB</p>
</div>
{COMPLETE_NAVIGATION}
</div></body></html>"""

        return f"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n{html}"
    except Exception as e:
        log_error(f"Root page error: {e}", "HTTP")
        return f"HTTP/1.0 500 Internal Server Error\r\nContent-Type: text/plain\r\n\r\nError: {e}"   

def handle_favicon_html():
    """Handle favicon."""
    print("web_interface::handle_favicon_html start")
    
    try:
        # Ultra-minimal HTML
        html = f"""<!DOCTYPE html><html><head><title>Favicon</title>
<style>{UNIFIED_CSS}</style></head><body>
<div class="container">
<h1>Favicon</h1>
<p>Favicon loaded successfully</p>
{COMPLETE_NAVIGATION}
</div></body></html>"""
    
        return f"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n{html}"
    except Exception as e:
        log_error(f"Root page error: {e}", "HTTP")
        return f"HTTP/1.0 500 Internal Server Error\r\nContent-Type: text/plain\r\n\r\nError: {e}"


#def handle_health_check(sensor_data, system_info, ota_updater, wlan, ssid, request_str=""):
def handle_health_check(system_info, request_str=""):
    """Handle health check with minimal HTML and clickable links."""
    try:
        #temp, hum = sensor_data
        #temp = sensor_data
        hum = 2
        wifi_status, _, ip_address = system_info["wifi"]
        uptime_days, uptime_hours, uptime_minutes = system_info["uptime_detailed"]
        free_memory, memory_mb, _ = system_info["memory_detailed"]

        print("system_info for health: ", wifi_status, ip_address, uptime_days, uptime_hours, uptime_minutes, free_memory, memory_mb)

        #version = ota_updater.get_current_version() if ota_updater else "unknown"
        config = get_config_for_metrics()
        location, device_name = config["location"], config["device"]

        # Minimal HTML health report with clickable links
        health_html = f"""<!DOCTYPE html><html><head><title>Health Check</title>
<style>{UNIFIED_CSS}</style></head><body>
<div class="container">
<h1>PICO W HEALTH CHECK</h1>

<h2>Device Information</h2>
<div class="status-info">
<p><strong>Device:</strong> {device_name}<br>
<strong>Location:</strong> {location}</p>
</div>

<h2>Sensor Status</h2>
<div class="status-info">
<p><strong>Humidity:</strong> {hum if hum is not None else "ERROR"}%</p>
</div>

<h2>Network Status</h2>
<div class="status-info">
<p><strong>Network:</strong> {wifi_status}<br>
<strong>IP Address:</strong> {ip_address}</p>
</div>

<h2>System Resources</h2>
<div class="status-info">
<p><strong>Uptime:</strong> {uptime_days}d {uptime_hours:02d}:{uptime_minutes:02d}<br>
<strong>Free Memory:</strong> {free_memory:,} bytes ({memory_mb}KB)</p>
</div>

{COMPLETE_NAVIGATION}
</div></body></html>"""

        return f"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n{health_html}"
    except Exception as e:
        log_error(f"Health check failed: {e}", "SYSTEM")
        return f"HTTP/1.0 500 Internal Server Error\r\nContent-Type: text/html\r\n\r\n<h1>Health Check Failed</h1><p>Error: {e}</p><p><a href='/'>Return home</a></p>"



#def handle_health_check(sensor_data, system_info, ota_updater, wlan, ssid, request_str=""):
#     """Handle health check with minimal HTML and clickable links."""
#     try:
#         #temp, hum = sensor_data
#         #temp = sensor_data
#         hum = 2
#         wifi_status, _, ip_address = system_info["wifi"]
#         uptime_days, uptime_hours, uptime_minutes = system_info["uptime_detailed"]
#         free_memory, memory_mb, _ = system_info["memory_detailed"]

#         #version = ota_updater.get_current_version() if ota_updater else "unknown"
#         config = get_config_for_metrics()
#         location, device_name = config["location"], config["device"]

#         # Minimal HTML health report with clickable links
#         health_html = f"""<!DOCTYPE html><html><head><title>Health Check</title></head><body>
# <h1>PICO W HEALTH CHECK</h1>

# <h2>Device Information</h2>
# <p><strong>Device:</strong> {device_name}<br>
# <strong>Location:</strong> {location}<br>
# <strong>Version:</strong> {version}</p>

# <h2>Sensor Status</h2>
# <p><strong>Status:</strong> {"OK" if temp is not None else "FAIL"}<br>
# <strong>Temperature:</strong> {temp if temp is not None else "ERROR"}C<br>
# <strong>Humidity:</strong> {hum if hum is not None else "ERROR"}%<br>
# <strong>Sensor Pin DHT22:</strong> GPIO {SENSOR_CONFIG_DHT22['pin']}<br>
# <strong>Sensor Pin DS18B20:</strong> GPIO {SENSOR_CONFIG_DS18B20['pin']}</p>

# <h2>Network Status</h2>
# <p><strong>Network:</strong> {wifi_status}<br>
# <strong>IP Address:</strong> {ip_address}<br>
# <strong>SSID:</strong> {ssid if wlan.isconnected() else "Not connected"}</p>

# <h2>System Resources</h2>
# <p><strong>Uptime:</strong> {uptime_days}d {uptime_hours:02d}:{uptime_minutes:02d}<br>
# <strong>Free Memory:</strong> {free_memory:,} bytes ({memory_mb}KB)<br>
# <strong>OTA Status:</strong> {"Enabled" if ota_updater else "Disabled"}</p>

# <h2>Links</h2>
# <p><a href="/">Dashboard</a> | <a href="/config">Config</a> | <a href="/logs">Logs</a> | <a href="/update">Update</a> | <a href="/metrics">Metrics</a> | <a href="/reboot">Reboot</a></p>
# </body></html>"""

#         return f"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n{health_html}"
#     except Exception as e:
#         log_error(f"Health check failed: {e}", "SYSTEM")
#         return f"HTTP/1.0 500 Internal Server Error\r\nContent-Type: text/html\r\n\r\n<h1>Health Check Failed</h1><p>Error: {e}</p><p><a href='/'>Return home</a></p>"




def handle_config_page():
    """Handle configuration page with minimal HTML form."""
    try:
        config = load_device_config()
        device_config = config.get("device", {})
        ota_config = config.get("ota", {})

        location = device_config.get("location", "default-location")
        device_name = device_config.get("name", "default-device")
        description = device_config.get("description", "")

        ota_enabled = ota_config.get("enabled", True)
        auto_update = ota_config.get("auto_update", True)
        update_interval = ota_config.get("update_interval", 1.0)
        github_repo = ota_config.get("github_repo", {})
        repo_owner = github_repo.get("owner", "TerrifiedBug")
        repo_name = github_repo.get("name", "pico-w-prometheus-dht22")
        branch = github_repo.get("branch", "main")

        # Minimal HTML form
        html = f"""<!DOCTYPE html><html><head><title>Device Config</title>
<style>{UNIFIED_CSS}</style></head><body>
<div class="container">
<h1>Device Configuration</h1>

{COMPLETE_NAVIGATION}

<h2>Current Settings</h2>
<div class="status-info">
<p><strong>Device:</strong> {device_name} | <strong>Location:</strong> {location}</p>
<p><strong>OTA:</strong> {"Enabled" if ota_enabled else "Disabled"} | <strong>Auto:</strong> {"Yes" if auto_update else "No"}</p>
<p><strong>Repo:</strong> {repo_owner}/{repo_name} ({branch})</p>
</div>

<h2>Update Configuration</h2>
<form method="POST">
<p><strong>Location:</strong><br><input type="text" name="location" value="{location}" size="20"></p>
<p><strong>Device Name:</strong><br><input type="text" name="device" value="{device_name}" size="20"></p>
<p><strong>Description:</strong><br><input type="text" name="description" value="{description}" size="30"></p>
<p><input type="checkbox" name="ota_enabled" {"checked" if ota_enabled else ""}> <strong>Enable OTA Updates</strong></p>
<p><input type="checkbox" name="auto_update" {"checked" if auto_update else ""}> <strong>Auto Updates</strong></p>
<p><strong>Update Interval (hours):</strong><br><input type="number" name="update_interval" value="{update_interval}" min="0.5" max="168" step="0.5" size="5"></p>
<p><strong>Repo Owner:</strong><br><input type="text" name="repo_owner" value="{repo_owner}" size="15"></p>
<p><strong>Repo Name:</strong><br><input type="text" name="repo_name" value="{repo_name}" size="25"></p>
<p><strong>Branch:</strong><br><select name="branch">
<option value="main" {"selected" if branch == "main" else ""}>main</option>
<option value="dev" {"selected" if branch == "dev" else ""}>dev</option>
</select></p>
<p><input type="submit" value="Save Configuration"></p>
</form>
</div></body></html>"""

        return f"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n{html}"
    except Exception as e:
        log_error(f"Config page error: {e}", "HTTP")
        return f"HTTP/1.0 500 Internal Server Error\r\nContent-Type: text/plain\r\n\r\nConfig error: {e}"


def handle_logs_page(request):
    """Handle logs page with plain text output."""
    try:
        request_str = request.decode('utf-8')
        query_params = {}

        if '?' in request_str:
            query_string = request_str.split('?')[1].split(' ')[0]
            for param in query_string.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    query_params[key] = value

        level_filter = query_params.get('level', 'ALL')
        category_filter = query_params.get('category', 'ALL')
        action = query_params.get('action', '')

        if action == 'clear':
            logger = get_logger()
            logger.clear_logs()
            log_info("Logs cleared via web interface", "SYSTEM")
            return "HTTP/1.0 302 Found\r\nLocation: /logs\r\n\r\n"

        logger = get_logger()
        stats = logger.get_statistics()
        logs = logger.get_logs(level_filter, category_filter, last_n=50)

        log_lines = []
        for log in logs:
            timestamp_str = f"+{log['t']}s"
            line = f"[{timestamp_str:>6}] {log['l']:5} {log['c']:7}: {log['m']}"
            log_lines.append(line)

        logs_text = "\n".join(log_lines) if log_lines else "No logs found."

        response_text = f"""System Logs
===========

Stats: {stats['total_entries']} entries | {stats['memory_usage_kb']}KB | Errors: {stats['logs_by_level']['ERROR']}

Filter: level={level_filter} category={category_filter}
Links: /logs?level=ERROR /logs?level=OTA /logs?action=clear

{logs_text}

Showing last 50 entries. Logs cleared on restart.
"""

        return f"HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\n\r\n{response_text}"
    except Exception as e:
        log_error(f"Logs page error: {e}", "HTTP")
        return f"HTTP/1.0 500 Internal Server Error\r\nContent-Type: text/plain\r\n\r\nLogs error: {e}"


def parse_form_data(request):
    """Parse form data from HTTP POST request."""
    MAX_KEY_LEN = 32
    MAX_VALUE_LEN = 256  # Increased from 128 to 256 to handle longer repo names
    try:
        request_str = request.decode("utf-8")
        body_start = request_str.find("\r\n\r\n")
        if body_start == -1:
            return {}
        form_body = request_str[body_start + 4 :]
        if not form_body:
            return {}

        form_data = {}
        pairs = form_body.split("&")

        for pair in pairs:
            if "=" in pair:
                key, value = pair.split("=", 1)
                key_decoded = unquote_plus(key)[:MAX_KEY_LEN]
                value_decoded = unquote_plus(value)[:MAX_VALUE_LEN]

                form_data[key_decoded] = value_decoded
        return form_data
    except Exception as e:
        log_error(f"Error parsing form data: {e}", "HTTP")
        return {}


def handle_config_update(request, ota_updater=None):
    """Handle configuration update from POST request."""
    try:
        form_data = parse_form_data(request)
        log_info(f"Config update: {list(form_data.keys())}", "CONFIG")

        config = validate_config_input(form_data)

        if save_device_config(config):
            log_info(f"Config updated: {config['device']['location']}/{config['device']['name']}", "CONFIG")

            # Reload OTA config if OTA updater exists and config contains OTA changes
            if ota_updater and "ota" in config:
                try:
                    if ota_updater.reload_config():
                        log_info("OTA configuration reloaded successfully", "CONFIG")
                    else:
                        log_warn("OTA configuration reload failed", "CONFIG")
                except Exception as e:
                    log_error(f"Error reloading OTA config: {e}", "CONFIG")

            return "HTTP/1.0 302 Found\r\nLocation: /config\r\n\r\n"
        else:
            log_error("Failed to save configuration", "CONFIG")
            return "HTTP/1.0 500 Internal Server Error\r\nContent-Type: text/plain\r\n\r\nFailed to save config"
    except Exception as e:
        log_error(f"Config update failed: {e}", "CONFIG")
        return f"HTTP/1.0 400 Bad Request\r\nContent-Type: text/plain\r\n\r\nConfig update failed: {e}"


def handle_update_page(ota_updater=None):
    """Display OTA update page with current status and update button."""
    try:
        # Get current OTA status
        ota_status = ota_updater.get_update_status() if ota_updater else {}
        current_version = ota_status.get("current_version", "unknown")
        ota_enabled = ota_status.get("ota_enabled", False)
        auto_check = ota_status.get("auto_check", False)
        repo = ota_status.get("repo", "unknown")
        branch = ota_status.get("branch", "unknown")

        html_content = f"""
        <div class="container">
            <h1>OTA Update Center</h1>
            
            <div class="status-info">
                <h2>Current Status</h2>
                <p><strong>Current Version:</strong> {current_version}</p>
                <p><strong>Repository:</strong> {repo}</p>
                <p><strong>Branch:</strong> {branch}</p>
                <p><strong>OTA Enabled:</strong> {"Yes" if ota_enabled else "No"}</p>
                <p><strong>Auto-Update:</strong> {"Yes" if auto_check else "No"}</p>
            </div>

            <h2>Update Options</h2>
            <form method="POST" action="/update">
                <button type="submit" style="
                    background-color: #00d4ff;
                    color: #1a1a2e;
                    padding: 10px 20px;
                    font-size: 1rem;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    font-weight: bold;
                    transition: all 0.3s ease;
                ">
                    Check for Updates
                </button>
            </form>

            <div class="status-info" style="margin-top: 20px;">
                <h2>Update Log</h2>
                <p>The update process will:</p>
                <ul>
                    <li>Check GitHub for new releases</li>
                    <li>Download firmware files</li>
                    <li>Create backup of current files</li>
                    <li>Apply the update</li>
                    <li>Restart the device</li>
                </ul>
            </div>

            {get_nav_links()}
        </div>
        """

        response = f"HTTP/1.0 200 OK\r\nContent-Type: text/html\r\n\r\n" + \
                   f"<!DOCTYPE html><html><head><meta charset=\"UTF-8\"><title>OTA Update</title>" + \
                   f"<style>{UNIFIED_CSS}</style></head><body>" + \
                   html_content + \
                   "</body></html>"
        
        return response.encode() if isinstance(response, str) else response
    except Exception as e:
        log_error(f"Update page rendering failed: {e}", "UPDATE")
        return f"HTTP/1.0 500 Internal Server Error\r\nContent-Type: text/plain\r\n\r\nUpdate page error: {e}"


def get_nav_links():
    """Return navigation links for all pages."""
    return """
    <div class="nav-links">
        <a href="/">Dashboard</a> |
        <a href="/config">Config</a> |
        <a href="/logs">Logs</a> |
        <a href="/update">Update</a> |
        <a href="/metrics">Metrics</a>
    </div>
    """
