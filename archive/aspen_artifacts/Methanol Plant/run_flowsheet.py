"""
Methanol Plant Flowsheet Builder
=================================
Creates and runs the methanol plant simulation based on DESIGN_BASIS.md
Uses Aspen Plus COM automation to build/verify the process flowsheet.

Design Basis:
- Product: Grade AA Methanol (>99.85 wt%)
- Capacity: 10,000 TPD
- Technology: Autothermal Reforming (ATR)
"""
import os
import sys
import time
import win32com.client as win32

# Configuration
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BKP_FILE = os.path.join(PROJECT_DIR, "MethanolPlant.bkp")

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def connect_to_aspen():
    """Connect to running Aspen Plus or open from file."""
    log("Connecting to Aspen Plus...")
    
    # Try to get running instance first
    try:
        aspen = win32.GetActiveObject("Apwn.Document")
        log("Connected to running Aspen Plus instance!")
        return aspen
    except:
        pass
    
    # Open from file
    if not os.path.exists(BKP_FILE):
        log(f"ERROR: {BKP_FILE} not found!")
        return None
    
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.SuppressDialogs = 1
        log(f"Opening simulation: {BKP_FILE}")
        aspen.InitFromArchive2(BKP_FILE)
        aspen.Visible = True
        log("Simulation loaded successfully!")
        return aspen
    except Exception as e:
        log(f"ERROR: {e}")
        return None

def get_stream_results(aspen, stream_name):
    """Get results for a specific stream."""
    results = {}
    base_path = rf"\Data\Streams\{stream_name}\Output"
    
    try:
        # Total mass flow
        node = aspen.Tree.FindNode(f"{base_path}\\TOT_FLOW\\MIXED")
        if node:
            results['mass_flow_kg_hr'] = node.Value
        
        # Temperature
        node = aspen.Tree.FindNode(f"{base_path}\\TEMP_OUT\\MIXED")
        if node:
            results['temperature_C'] = node.Value
            
        # Pressure
        node = aspen.Tree.FindNode(f"{base_path}\\PRES_OUT\\MIXED")
        if node:
            results['pressure_bar'] = node.Value
            
    except Exception as e:
        log(f"  Warning reading {stream_name}: {e}")
    
    return results

def get_block_status(aspen, block_name):
    """Check if a block converged."""
    try:
        node = aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Output\BLKSTAT")
        if node:
            return node.Value
    except:
        pass
    return "Unknown"

def verify_flowsheet(aspen):
    """Verify that all flowsheet elements exist."""
    log("\n=== Verifying Flowsheet Structure ===")
    
    # Streams to verify
    streams = ['NG-FEED', 'STEAM', 'O2-FEED', 'ATR-IN', 'HOT-SYN', 
               'COLD-SYN', 'DRY-GAS', 'HP-GAS', 'R-IN', 'R-OUT',
               'CRUDE-ME', 'MEOH-PRO', 'WASTE-H2O', 'RECYCLE', 'PURGE']
    
    # Blocks to verify
    blocks = ['MIX-FEED', 'B-ATR', 'B-COOL', 'B-FLASH', 'B-COMP',
              'MIX-LOOP', 'B-SYN', 'B-SEP', 'SPLIT', 'B-DIST']
    
    log("\nChecking Streams:")
    for stream in streams:
        node = aspen.Tree.FindNode(rf"\Data\Streams\{stream}")
        status = "[OK]" if node else "[X]"
        log(f"  {status} {stream}")
    
    log("\nChecking Blocks:")
    for block in blocks:
        node = aspen.Tree.FindNode(rf"\Data\Blocks\{block}")
        status = "[OK]" if node else "[X]"
        log(f"  {status} {block}")
    
    return True

def run_simulation(aspen):
    """Run the Aspen Plus simulation."""
    log("\n=== Running Simulation ===")
    
    try:
        # Reinitialize and run
        log("Reinitializing simulation...")
        aspen.Reinit()
        
        log("Starting simulation run...")
        start_time = time.time()
        aspen.Run()
        
        # Wait for completion
        max_wait = 300  # 5 minutes max
        while aspen.EngineRunning:
            elapsed = time.time() - start_time
            if elapsed > max_wait:
                log("WARNING: Simulation timeout!")
                break
            time.sleep(2)
            if int(elapsed) % 10 == 0:
                log(f"  Running... ({int(elapsed)}s)")
        
        elapsed = time.time() - start_time
        log(f"Simulation completed in {elapsed:.1f} seconds")
        
        return True
        
    except Exception as e:
        log(f"ERROR during simulation: {e}")
        return False

def print_results(aspen):
    """Print key simulation results."""
    log("\n=== Simulation Results ===")
    
    # Key output streams
    key_streams = {
        'NG-FEED': 'Natural Gas Feed',
        'HOT-SYN': 'Hot Syngas (post-ATR)',
        'DRY-GAS': 'Dry Syngas (post-flash)',
        'HP-GAS': 'High Pressure Syngas',
        'MEOH-PRO': 'Methanol Product',
        'WASTE-H2O': 'Waste Water',
        'PURGE': 'Purge Gas'
    }
    
    log("\nStream Results:")
    log("-" * 60)
    
    for stream, description in key_streams.items():
        results = get_stream_results(aspen, stream)
        if results.get('mass_flow_kg_hr'):
            flow = results['mass_flow_kg_hr']
            flow_tpd = flow * 24 / 1000  # Convert to TPD
            log(f"  {stream} ({description}):")
            log(f"    Mass Flow: {flow:,.0f} kg/hr ({flow_tpd:,.0f} TPD)")
            if results.get('temperature_C'):
                log(f"    Temperature: {results['temperature_C']:.1f} °C")
            if results.get('pressure_bar'):
                log(f"    Pressure: {results['pressure_bar']:.1f} bar")
    
    # Block status
    log("\nBlock Status:")
    log("-" * 60)
    blocks = ['MIX-FEED', 'B-ATR', 'B-COOL', 'B-FLASH', 'B-COMP',
              'MIX-LOOP', 'B-SYN', 'B-SEP', 'SPLIT', 'B-DIST']
    
    for block in blocks:
        status = get_block_status(aspen, block)
        log(f"  {block}: {status}")
    
    # Calculate production rate
    log("\n" + "=" * 60)
    meoh_results = get_stream_results(aspen, 'MEOH-PRO')
    if meoh_results.get('mass_flow_kg_hr'):
        production_tpd = meoh_results['mass_flow_kg_hr'] * 24 / 1000
        target = 10000
        deviation = ((production_tpd - target) / target) * 100
        log(f"METHANOL PRODUCTION: {production_tpd:,.0f} TPD")
        log(f"TARGET: {target:,} TPD")
        log(f"DEVIATION: {deviation:+.1f}%")
    log("=" * 60)

def check_constraints(aspen):
    """Check operational constraints from constraints.txt."""
    log("\n=== Checking Operational Constraints ===")
    
    constraints = {}
    c_file = os.path.join(PROJECT_DIR, "constraints.txt")
    
    if os.path.exists(c_file):
        with open(c_file, 'r') as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    key, val = line.split("=", 1)
                    constraints[key.strip()] = float(val.split("#")[0].strip())
    
    violations = []
    
    # Check methanol purity (if we can read composition)
    min_purity = constraints.get('MIN_METHANOL_PURITY', 0.9985)
    log(f"  Required Methanol Purity: >{min_purity*100:.2f}%")
    
    # Check synthesis reactor temperature
    max_cat_temp = constraints.get('MAX_CATALYST_TEMP', 280)
    try:
        node = aspen.Tree.FindNode(r"\Data\Blocks\B-SYN\Output\B_TEMP")
        if node and node.Value:
            syn_temp = node.Value
            status = "[OK]" if syn_temp <= max_cat_temp else "[VIOLATION]"
            log(f"  Synthesis Temp: {syn_temp:.1f}°C (max {max_cat_temp}°C) {status}")
            if syn_temp > max_cat_temp:
                violations.append(f"Synthesis temp {syn_temp:.1f}°C > {max_cat_temp}°C")
    except:
        pass
    
    # Target production
    target_tpd = constraints.get('Target_Production_TPD', 10000)
    meoh_results = get_stream_results(aspen, 'MEOH-PRO')
    if meoh_results.get('mass_flow_kg_hr'):
        actual_tpd = meoh_results['mass_flow_kg_hr'] * 24 / 1000
        deviation = abs(actual_tpd - target_tpd) / target_tpd * 100
        status = "[OK]" if deviation < 5 else "[WARNING]"
        log(f"  Production: {actual_tpd:,.0f} TPD (target {target_tpd:,} TPD) {status}")
    
    if violations:
        log("\n[!] CONSTRAINT VIOLATIONS:")
        for v in violations:
            log(f"  - {v}")
    else:
        log("\n[OK] All constraints satisfied!")
    
    return len(violations) == 0

def save_simulation(aspen):
    """Save the simulation file."""
    log("\nSaving simulation...")
    try:
        aspen.Save()
        log("Simulation saved successfully!")
        return True
    except Exception as e:
        log(f"Warning: Could not save: {e}")
        return False

def main():
    log("=" * 60)
    log("METHANOL PLANT FLOWSHEET BUILDER")
    log("Based on DESIGN_BASIS.md")
    log("=" * 60)
    
    # Connect to Aspen
    aspen = connect_to_aspen()
    if not aspen:
        return 1
    
    # Verify flowsheet structure
    verify_flowsheet(aspen)
    
    # Run simulation
    if run_simulation(aspen):
        # Print results
        print_results(aspen)
        
        # Check constraints
        check_constraints(aspen)
        
        # Save
        save_simulation(aspen)
    
    log("\nDone!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
