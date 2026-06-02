"""
RESEARCH: Testing Stream Creation
Testing if Elements.Add works for Streams
"""
import win32com.client as win32
import time

log = open("stream_test_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS STREAM TEST")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    aspen.Visible = True

    # Try creating a stream
    log_print("\nTesting Elements.Add('S1', 'MATERIAL')...")
    try:
        streams = aspen.Tree.FindNode(r"\Data\Streams")
        s1 = streams.Elements.Add("S1", "MATERIAL")
        log_print("  [SUCCESS] Stream S1 created!")
    except Exception as e:
        log_print(f"  [FAIL] {e}")

    # Try creating a Heat stream
    log_print("\nTesting Elements.Add('Q1', 'HEAT')...")
    try:
        s2 = streams.Elements.Add("Q1", "HEAT")
        log_print("  [SUCCESS] Stream Q1 created!")
    except Exception as e:
        log_print(f"  [FAIL] {e}")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
