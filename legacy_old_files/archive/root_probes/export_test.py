import win32com.client as win32
import os

print("Starting Aspen...")
aspen = win32.Dispatch('Apwn.Document')
aspen.InitFromArchive2(r"C:\Program Files\AspenTech\Aspen Plus V14.0\GUI\Xeq\Blank.apt")
aspen.SuppressDialogs = 1

print("Adding stream...")
aspen.Tree.Elements("Data").Elements("Streams").Elements.Add("S1")
s1 = aspen.Tree.FindNode(r"\Data\Streams\S1")
s1.FindNode(r"Input\TEMP\MIXED").Value = 25
s1.FindNode(r"Input\PRES\MIXED").Value = 1
s1.FindNode(r"Input\TOTFLOW\MIXED").Value = 100

print("Adding components...")
comps = aspen.Tree.Elements("Data").Elements("Components").Elements("Specifications").Elements("Input").Elements("COMP-ID")
comps.Elements.Add("WATER")
comps.Elements("WATER").Value = "H2O"

print("Adding fractions...")
s1.FindNode(r"Input\FLOW\MIXED\WATER").Value = 1

print("Exporting...")
import_path = os.path.abspath("test_export.inp")
# Using Export method: 2 is typically the format for INP
try:
    aspen.Export(2, import_path)
    print("Exported to", import_path)
except Exception as e:
    print("Export failed:", e)

aspen.Quit()
