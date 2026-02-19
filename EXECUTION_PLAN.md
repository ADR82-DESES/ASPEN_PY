# 🏗️ Execution Plan: Folder Refactor & Methanol Plant Design

## 1. 📂 Folder Reorganization
We will clean up the root directory by moving the completed Water Mixer project files.

### Destination: `Water mixture/`
**Files to move:**
- `AutomatedMixer.*` (All Aspen simulation files: .bkp, .apw, .appdf, .def, .his)
- `main.py` (Automation script)
- `results.csv` & `streams.csv` (Output data)
- `QUICK_START.md`, `README.md`, `status_summary.md` (Documentation)
- `docs/`, `logs/`, `legacy/`, `experiments/`, `tests/`, `temp/` (Project folders)
- `Water mixer/` (Merge existing content)

**Action:**
- Create `Water mixture` folder.
- Move identified files and folders into it.
- Consolidate `Water mixer` content if any.

---

## 2. 🏭 Methanol Plant Structure (10,000 TPD)
We will initialize the structure for a new **World-Scale Methanol Plant**.

### Design Basis
- **Product**: Grade AA Methanol
- **Capacity**: 10,000 Tonnes Per Day (TPD) (~3.3 Million Tonnes/Year)
- **Feedstock**: Natural Gas (Methane)
- **Technology Choice**: **Autothermal Reforming (ATR)**
  - *Reasoning*: For capacities >5,000 TPD, standard Steam Methane Reforming (SMR) becomes capital inefficient (requires multiple trains). ATR allows for single-train mega-plants.

### Process Flow Diagram (PFD) Concept
1.  **Pre-Treatment**: Natural Gas Desulfurization (ZnO beds).
2.  **Reforming (ATR)**: 
    - Inputs: Natural Gas + Oxygen + Steam.
    - Reaction: Partial oxidation + Reforming.
    - Goal: Syngas ratio (H2 - CO2) / (CO + CO2) ~ 2.05.
3.  **Heat Recovery**: Generate high-pressure steam from hot syngas.
4.  **Compression**: Syngas compressor (Methanol runs at 50-100 bar).
5.  **Synthesis**: Isothermal or Adiabatic reactors in a loop.
    - CO + 2H2 <-> CH3OH
6.  **Purification**: 2-3 Column Distillation (Remove light ends + water).

### New Directory: `Methanol Plant/`
**Files to create:**
1.  **`DESIGN_BASIS.md`**: Detailed process specs and stream definitions.
2.  **`automation_setup.py`**: Python script to initialize the new Aspen simulation.
3.  **`constraints.txt`**: List of hard constraints (Max T, Max P, Emission limits).

---

## 3. 🚀 Next Steps (after approval)
1. Execute the file moves.
2. Generate the `Methanol Plant` files.
3. Instruct Python to spin up the new Aspen Interface for the Methanol project.
