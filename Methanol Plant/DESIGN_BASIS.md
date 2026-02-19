# 🏭 Methanol Plant Design Basis (10,000 TPD)

## 1. Project Overview
- **Product**: Grade AA Methanol (>99.85 wt%)
- **Capacity**: 10,000 Metric Tonnes Per Day (TPD)
- **Location**: Industrial Zone (Default ISO conditions)
- **Feedstock**: Natural Gas (100% Methane basis for V1)

## 2. Process Technology: Autothermal Reforming (ATR)
Selected for single-train scalability.

### Block 1: Reforming
- **Feed**:
  - Natural Gas: 40°C, 30 bar
  - Steam: 250°C, 35 bar (S/C ratio ~ 0.6)
  - Oxygen: 99.5%, 150°C, 30 bar
- **Reactor (ATR)**:
  - Type: RGibbs (Equilibrium) or REquil
  - Temp: ~1000°C (Adiabatic)
  - Pressure: ~30 bar

### Block 2: Heat Recovery & Compression
- **Syngas Cooler**: Cool to 40°C
- **Flash**: Remove condensed water
- **Compressor**: Multi-stage to 80-100 bar

### Block 3: Synthesis Loop
- **Reactor**: RPlug or RStoic (Kinetic LHHW)
- **Technology**: Gas-cooled + Water-cooled reactors (Lurgi/Topsoe style)
- **Recycle**: High recycle ratio (3-5x) to maximize conversion

### Block 4: Purification
- **Topping Column**: Remove light ends (Ethers, dissolved gases)
- **Refining Column**: Remove Water/Ethanol
- **Target**: Water < 0.1 wt%

## 3. Automation Scope
- **Variable**: Feed Flowrate
- **Objective**: Maintain 10,000 TPD product while minimizing specific energy.
- **Constraints**:
  - Max Catalyst Temp: 280°C
  - Max Pressure Drop: 5 bar
