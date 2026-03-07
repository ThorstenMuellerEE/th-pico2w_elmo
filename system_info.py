import time
import gc

def get_system_info(wlan, boot_ticks):
    """Get system information for web interface."""
    print("get_system_info() called.")
    
    # WiFi information
    wifi_status = "Connected" if wlan.isconnected() else "Disconnected"
    wifi_class = "status-ok" if wlan.isconnected() else "status-error"
    ip_address = wlan.ifconfig()[0] if wlan.isconnected() else "N/A"

    # System uptime
    uptime_ms = time.ticks_diff(time.ticks_ms(), boot_ticks)
    print("uptime_ms:", uptime_ms)
    if uptime_ms < 0:
        uptime_ms = uptime_ms + (1 << 30)
    uptime_seconds = max(0, uptime_ms // 1000)
    uptime_hours = uptime_seconds // 3600
    uptime_minutes = (uptime_seconds % 3600) // 60
    uptime_days = uptime_hours // 24
    uptime_hours = uptime_hours % 24

    # Memory information
    gc.collect()
    free_memory = gc.mem_free()
    memory_mb = round(free_memory / 1024, 1)
    memory_class = "status-ok" if free_memory > 100000 else "status-warn" if free_memory > 50000 else "status-error"

    return {
        "wifi": (wifi_status, wifi_class, ip_address),
        "uptime": (uptime_hours, uptime_minutes),
        "uptime_detailed": (uptime_days, uptime_hours, uptime_minutes),
        "memory": memory_mb,
        "memory_detailed": (free_memory, memory_mb, memory_class),
    }
