"""
Device Dashboard

Handles an overview of different configuration and status information.
"""

# Import the unified CSS from web_interface
try:
    from web_interface import UNIFIED_CSS, COMPLETE_NAVIGATION
except ImportError:
    # Fallback CSS if import fails
    UNIFIED_CSS = """
    body { font-family: Arial, sans-serif; background: #1a1a2e; color: #e0e0e0; margin: 0; padding: 20px; }
    .container { max-width: 800px; margin: 0 auto; background: rgba(255,255,255,0.05); border-radius: 10px; padding: 20px; }
    h1 { color: #00d4ff; text-align: center; }
    h2 { color: #ff6b6b; }
    table { width: 100%; border-collapse: collapse; margin: 20px 0; background: rgba(255,255,255,0.05); }
    th, td { padding: 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }
    th { background: #00d4ff; color: #1a1a2e; }
    .ok { color: #4CAF50; }
    .warn { color: #ff9800; }
    ul { list-style: none; padding: 0; }
    li { background: rgba(255,255,255,0.05); margin: 5px 0; padding: 10px; border-radius: 5px; }
    a { color: #00d4ff; text-decoration: none; }
    a:hover { color: #ff6b6b; }
    """
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

def dashboard_html(temperatures=None, wlan_obj=None, boot_ticks_val=None, ota_in_progress=False):
    print("Dashboard called.")
    
    # Handle None values
    if temperatures is None:
        temperatures = {}
    if wlan_obj is None:
        wifi = "DOWN"
        ip = "N/A"
    else:
        wifi = "OK" if wlan_obj.isconnected() else "DOWN"
        ip = wlan_obj.ifconfig()[0] if wlan_obj.isconnected() else "N/A"
    
    if boot_ticks_val is None:
        import time
        uptime = 0
    else:
        import time
        uptime = time.ticks_diff(time.ticks_ms(), boot_ticks_val) // 1000

    rows = ""
    for name, value in temperatures.items():
        rows += f"<tr><td>{name}</td><td>{value} °C</td></tr>"

    ota_status = "RUNNING" if ota_in_progress else "IDLE"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Pico W Dashboard</title>
<style>{UNIFIED_CSS}</style>
</head>
<body>
<div class="container">
<h1>🌡 Pico W Sensor Dashboard</h1>

<h2>System Status</h2>
<ul>
<li><strong>WiFi:</strong> <span class="ok">{wifi}</span></li>
<li><strong>IP Address:</strong> {ip}</li>
<li><strong>Uptime:</strong> {uptime}s</li>
<li><strong>OTA Status:</strong> {ota_status}</li>
</ul>

<h2>Temperature Sensors</h2>
<table>
<tr><th>Sensor</th><th>Temperature</th></tr>
{rows}
</table>

{COMPLETE_NAVIGATION}
</div>
</body>
</html>"""
