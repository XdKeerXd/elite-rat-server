
import os
import time
from datetime import datetime
import ctypes
while True:
    if not os.path.exists("c:\Users\Keer\Desktop\Spy\client.py"):
        time.sleep(60)
        continue
    os.system(f'start "" "c:\Users\Keer\Desktop\Spy\client.py"')
    time.sleep(300)
