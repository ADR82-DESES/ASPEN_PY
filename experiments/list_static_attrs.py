"""
RESEARCH: Listing all Static Attributes
"""
import win32com.client as win32
import sys

log = open("all_static_attrs_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

try:
    aspen = win32.gencache.EnsureDispatch("Apwn.Document")
    log_print(f"Attributes of {aspen}:")
    attrs = sorted(dir(aspen))
    for a in attrs:
        log_print(f"  {a}")

except Exception as e:
    log_print(f"Error: {e}")

log.close()
