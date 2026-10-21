
import subprocess, time
p = subprocess.Popen([r"C:\tmp\hotkey\dist\PetalMenu.exe"],
                     creationflags=0x00000008,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("launched pid", p.pid)
