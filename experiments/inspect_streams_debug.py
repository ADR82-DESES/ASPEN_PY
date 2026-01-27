
import win32com.client as win32
import os

filepath = os.path.abspath("automatedmixer.bkp")
print(f"Loading {filepath}")
aspen = win32.Dispatch("Apwn.Document")
aspen.InitFromArchive2(filepath)

print("Accessing streams...")
node = aspen.Tree.FindNode(r"\Data\Streams")
print(f"Count: {node.Elements.Count}")

for i in range(1, node.Elements.Count + 1):
    try:
        st = node.Elements.Item(i)
        print(f"Stream {i}: {st.Name}")
    except Exception as e:
        print(f"Stream {i} Error: {e}")

aspen.Quit()
