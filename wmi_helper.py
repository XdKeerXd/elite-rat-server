import os, sys, time, ctypes

while True:
    script = os.path.abspath(__file__)
    if not os.path.exists(script):
        time.sleep(60)
        continue
    os.system(f'start "" "{sys.executable}" "{script}"')
    time.sleep(300)
