# 🧪 Methanol Plant Simulation Files

This directory contains the necessary files to generate the Methanol Plant simulation in Aspen Plus.

## Files

- **`DESIGN_BASIS.md`**: The process design specification.
- **`MethanolPlant.inp`**: The Aspen Plus Input File. This is the **master definition** of the simulation logic, streams, and blocks.
- **`constraints.txt`**: Operational limits for the automation script.
- **`automation_setup.py`**: Python script to connect to the simulation once open.

## 🚀 How to Create the Simulation

Since Aspen Plus files (`.bkp`) are binary, we use the Input file (`.inp`) to generate the initial simulation.

1.  **Open Aspen Plus**.
2.  Go to **File > Import**.
3.  Select **Aspen Plus Input Files (*.inp)** from the file type dropdown.
4.  Navigate to this folder and select `MethanolPlant.inp`.
5.  Aspen Plus will process the file and generate the flowsheet automatically.
6.  **Save the file** as `MethanolPlant.bkp` in this same directory.

## 🤖 Running the Automation

Once `MethanolPlant.bkp` exists:
1.  Ensure Aspen Plus is open with the file.
2.  Run the python setup script:
    ```bash
    python automation_setup.py
    ```
3.  The script will verify the connection and read the constraints.
