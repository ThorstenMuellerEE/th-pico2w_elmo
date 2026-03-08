"""
Boot diagnostics and initialization for Pico 2W
Runs first on startup before main.py
Provides early error detection and LED feedback
"""

import sys
import time
import machine
from machine import Pin

# ═══════════════════════════════════════════════════════════
# LED STATUS OUTPUT (for headless operation)
# ═══════════════════════════════════════════════════════════
try:
    status_led = Pin("LED")  # Built-in LED on Pico W
    status_led.init(Pin.OUT)  # Set as output
except Exception:
    status_led = None

def blink_led(count=1, duration=0.1):
    """Blink LED to indicate status during boot"""
    if status_led is None:
        return
    for _ in range(count):
        status_led.on()
        time.sleep(duration)
        status_led.off()
        time.sleep(duration)

print("\n" + "="*60)
print("BOOT: Pico W Prometheus Server Starting...")
print("="*60)

# ═══════════════════════════════════════════════════════════
# MEMORY CHECK
# ═══════════════════════════════════════════════════════════
import gc
gc.collect()
free_memory = gc.mem_free()
print(f"BOOT: Free memory: {free_memory} bytes")

if free_memory < 50000:
    print("BOOT: WARNING - Low memory (<50KB), some modules may fail")
    blink_led(2, 0.5)  # 2 long blinks = low memory warning

# ═══════════════════════════════════════════════════════════
# FILESYSTEM CHECK
# ═══════════════════════════════════════════════════════════
import os
print("BOOT: Checking filesystem...")
try:
    files = os.listdir('.')
    print(f"BOOT: Found {len(files)} files on device")
    
    # Verify critical files exist
    critical_files = ['main.py', 'config.py', 'secrets.py', 'logger.py']
    missing_files = [f for f in critical_files if f not in files]
    
    if missing_files:
        print(f"BOOT ERROR: Missing critical files: {missing_files}")
        blink_led(3, 1.0)  # 3 long blinks = missing files
        # Don't exit - let main.py handle recovery
    else:
        print("BOOT: All critical files present")
        blink_led(1, 0.1)  # 1 short blink = OK
        
except Exception as e:
    print(f"BOOT ERROR: Filesystem check failed: {e}")
    blink_led(4, 0.5)  # 4 blinks = filesystem error

# ═══════════════════════════════════════════════════════════
# SECRETS CHECK
# ═══════════════════════════════════════════════════════════
print("BOOT: Checking WiFi credentials...")
try:
    from secrets import wifi_secrets
    ssid = wifi_secrets.get('ssid', '')
    pw = wifi_secrets.get('pw', '')
    
    if not ssid or not pw:
        print("BOOT ERROR: WiFi credentials incomplete in secrets.py")
        blink_led(5, 0.5)  # 5 blinks = missing WiFi credentials
    else:
        print(f"BOOT: WiFi SSID configured: {ssid}")
        
except SyntaxError as e:
    print(f"BOOT ERROR: Syntax error in secrets.py: {e}")
    blink_led(6, 0.5)  # 6 blinks = syntax error
except ImportError as e:
    print(f"BOOT ERROR: Could not import secrets.py: {e}")
    blink_led(5, 0.5)

# ═══════════════════════════════════════════════════════════
# GPIO PIN CHECK
# ═══════════════════════════════════════════════════════════
print("BOOT: Checking GPIO pins...")
try:
    # Check DS18B20 pin (should be GPIO 22 based on main.py)
    ds_pin = Pin(22, Pin.IN)
    print("BOOT: DS18B20 GPIO 22 - OK")
    
    # Check if pull-up is needed
    pin_state = ds_pin.value()
    print(f"BOOT: DS18B20 pin state: {pin_state} (1=pulled high/OK, 0=pulled low)")
    
except Exception as e:
    print(f"BOOT ERROR: GPIO check failed: {e}")
    blink_led(2, 1.0)

# ═══════════════════════════════════════════════════════════
# CHECKSUM/VERSION CHECK
# ═══════════════════════════════════════════════════════════
print("BOOT: Checking version info...")
try:
    with open('version.txt', 'r') as f:
        version = f.read().strip()
        print(f"BOOT: Firmware version: {version}")
except Exception as e:
    print(f"BOOT: Warning - Could not read version.txt: {e}")

# ═══════════════════════════════════════════════════════════
# DONE - HAND OFF TO MAIN
# ═══════════════════════════════════════════════════════════
print("\nBOOT: Diagnostics complete - starting main application...")
print("="*60 + "\n")

# Signal boot complete with a pattern (3 blinks = ready)
blink_led(3, 0.2)

# Now main.py will run automatically
