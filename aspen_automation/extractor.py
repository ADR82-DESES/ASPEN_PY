import re
import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from .exceptions import ExtractionError
from .schema import PlantSpecification

logger = logging.getLogger("aspen_automation.extractor")

def _safe_node_value(aspen: Any, path: str) -> Optional[float]:
    try:
        node = aspen.Tree.FindNode(path)
        if node:
            val = node.Value
            if val is not None:
                return val
    except Exception:
        pass
    return None

def _get_element_names(aspen: Any, node_path: str) -> List[str]:
    names = []
    try:
        node = aspen.Tree.FindNode(node_path)
        if node:
            count = node.Elements.Count
            for i in range(1, count + 1):
                try:
                    element = node.Elements.Item(i)
                    if element and element.Name:
                        names.append(element.Name)
                except Exception:
                    pass
    except Exception:
        pass
    return names

def extract_stream_properties(aspen: Any, stream_names: List[str], component_ids: List[str]) -> pd.DataFrame:
    rows = []
    for name in stream_names:
        row = {"stream_name": name}
        row["temperature"] = _safe_node_value(aspen, rf"\Data\Streams\{name}\Output\TEMP_OUT\MIXED")
        row["pressure"] = _safe_node_value(aspen, rf"\Data\Streams\{name}\Output\PRES_OUT\MIXED")
        
        row["mass_flow"] = _safe_node_value(aspen, rf"\Data\Streams\{name}\Output\MASSFLMX\MIXED")
        
        row["mole_flow"] = _safe_node_value(aspen, rf"\Data\Streams\{name}\Output\MOLEFLMX\MIXED")
        
        for comp_id in component_ids:
            row[f"{comp_id}_mole_frac"] = _safe_node_value(aspen, rf"\Data\Streams\{name}\Output\MOLEFRAC\MIXED\{comp_id}")
            row[f"{comp_id}_mass_frac"] = _safe_node_value(aspen, rf"\Data\Streams\{name}\Output\MASSFRAC\MIXED\{comp_id}")
            
        rows.append(row)
    return pd.DataFrame(rows)

def extract_block_performance(aspen: Any, block_names: List[str]) -> pd.DataFrame:
    rows = []
    for name in block_names:
        row = {"block_name": name}
        row["block_type"] = _safe_node_value(aspen, rf"\Data\Blocks\{name}\Input\TYPE")
        
        duty = _safe_node_value(aspen, rf"\Data\Blocks\{name}\Output\QNET")
        if duty is None:
            duty = _safe_node_value(aspen, rf"\Data\Blocks\{name}\Output\DUTY")
        row["duty"] = duty
        
        row["conversion"] = _safe_node_value(aspen, rf"\Data\Blocks\{name}\Output\CONV")
        row["efficiency"] = _safe_node_value(aspen, rf"\Data\Blocks\{name}\Output\EFF")
        
        rows.append(row)
    return pd.DataFrame(rows)

def parse_purity_expression(expression: str) -> Tuple[str, str, str]:
    match = re.match(r"^(\S+)\s+(wt%|mol%|mass fraction|mole fraction)\s+in\s+(\S+)$", expression, re.IGNORECASE)
    if not match:
        raise ValueError(f"Invalid purity expression: '{expression}'")
    return match.group(1), match.group(2), match.group(3)

def evaluate_purity(aspen: Any, expression: str) -> Optional[float]:
    component, basis, stream = parse_purity_expression(expression)
    if basis.lower() in ("wt%", "mass fraction"):
        return _safe_node_value(aspen, rf"\Data\Streams\{stream}\Output\MASSFRAC\MIXED\{component}")
    else:
        return _safe_node_value(aspen, rf"\Data\Streams\{stream}\Output\MOLEFRAC\MIXED\{component}")

def calculate_material_balance(aspen: Any, spec: Union[PlantSpecification, Dict]) -> pd.DataFrame:
    if isinstance(spec, PlantSpecification):
        spec_dict = spec.model_dump()
    else:
        spec_dict = spec

    flowsheet = spec_dict.get("flowsheet", [])
    
    all_inputs = set()
    all_outputs = set()
    
    for entry in flowsheet:
        for inp in entry.get("inputs", []):
            all_inputs.add(inp)
        for out in entry.get("outputs", []):
            all_outputs.add(out)
            
    feed_streams = all_inputs - all_outputs
    product_streams = all_outputs - all_inputs

    components = spec_dict.get("components", [])
    rows = []
    
    for comp in components:
        comp_id = comp.get("id")
        
        total_in = 0.0
        for s in feed_streams:
            flow = _safe_node_value(aspen, rf"\Data\Streams\{s}\Output\MOLEFLMX\MIXED")
            frac = _safe_node_value(aspen, rf"\Data\Streams\{s}\Output\MOLEFRAC\MIXED\{comp_id}")
            if flow is not None and frac is not None:
                total_in += flow * frac
                
        total_out = 0.0
        for s in product_streams:
            flow = _safe_node_value(aspen, rf"\Data\Streams\{s}\Output\MOLEFLMX\MIXED")
            frac = _safe_node_value(aspen, rf"\Data\Streams\{s}\Output\MOLEFRAC\MIXED\{comp_id}")
            if flow is not None and frac is not None:
                total_out += flow * frac
                
        closure = 0.0
        if total_in > 0:
            closure = (total_out / total_in - 1) * 100
            
        rows.append({
            "component": comp_id,
            "input_kmol_hr": total_in,
            "output_kmol_hr": total_out,
            "closure_%": closure
        })
        
    return pd.DataFrame(rows)

def calculate_energy_balance(aspen: Any, spec: Union[PlantSpecification, Dict]) -> pd.DataFrame:
    if isinstance(spec, PlantSpecification):
        spec_dict = spec.model_dump()
    else:
        spec_dict = spec
        
    blocks = spec_dict.get("blocks", [])
    rows = []
    
    total_duty = 0.0
    for b in blocks:
        block_name = b.get("name")
        duty = _safe_node_value(aspen, rf"\Data\Blocks\{block_name}\Output\QNET")
        if duty is None:
            duty = _safe_node_value(aspen, rf"\Data\Blocks\{block_name}\Output\DUTY")
            
        rows.append({
            "block_name": block_name,
            "duty_kw": duty
        })
        
        if duty is not None:
            total_duty += duty
            
    rows.append({
        "block_name": "TOTAL",
        "duty_kw": total_duty
    })
    
    return pd.DataFrame(rows)

def extract_diagnostics(aspen: Any) -> Dict[str, Any]:
    per_error = _safe_node_value(aspen, r"\Data\Results Summary\Run-Status\Output\PER_ERROR")
    error_count = _safe_node_value(aspen, r"\Data\Results Summary\Run-Status\Output\NERROR")
    warning_count = _safe_node_value(aspen, r"\Data\Results Summary\Run-Status\Output\NWARN")
    
    convergence_status = "converged" if per_error == 0 else "failed"
    
    return {
        "per_error": per_error,
        "error_count": error_count,
        "warning_count": warning_count,
        "convergence_status": convergence_status
    }

def calculate_kpis(aspen: Any, spec: Union[PlantSpecification, Dict], streams_df: pd.DataFrame, blocks_df: pd.DataFrame) -> Dict[str, Any]:
    kpis = {
        "production_rate_tpd": None,
        "purity_fraction": None,
        "energy_consumption_mw": None,
        "yield_fraction": None,
        "convergence_status": None
    }
    
    if isinstance(spec, PlantSpecification):
        spec_dict = spec.model_dump()
    else:
        spec_dict = spec
        
    try:
        targets = spec_dict.get("targets", {})
        
        # production_rate_tpd
        prod_stream = targets.get("production_stream", "MEOH-PRO")
        if not streams_df.empty and "mass_flow" in streams_df.columns:
            stream_row = streams_df[streams_df["stream_name"] == prod_stream]
            if not stream_row.empty:
                mass_flow = stream_row.iloc[0]["mass_flow"]
                if mass_flow is not None and not pd.isna(mass_flow):
                    kpis["production_rate_tpd"] = mass_flow * 24 / 1000
                    
        # purity_fraction
        purity_dict = targets.get("purity", {})
        expression = purity_dict.get("expression", "CH3OH wt% in MEOH-PRO")
        kpis["purity_fraction"] = evaluate_purity(aspen, expression)
        
        # energy_consumption_mw
        if not blocks_df.empty and "duty_kw" in blocks_df.columns:
            filtered = blocks_df[blocks_df["block_name"] != "TOTAL"]
            duty_sum = filtered["duty_kw"].dropna().sum()
            kpis["energy_consumption_mw"] = duty_sum / 1000
            
        # yield_fraction
        # Moles of target component in product stream / moles of primary feed component in feed stream
        # derive stream names from spec targets or use defaults
        comp, basis, target_stream = parse_purity_expression(expression)
        
        # To get the feed component, we could look for a natural feed component, or use a default.
        # "moles of target component in product stream / moles of primary feed component in feed stream"
        yield_dict = targets.get("yield", {})
        # If no explicit yield target info given, make an assumption:
        feed_stream = "CO2-IN" # or maybe "SYNGAS"? What to use?
        feed_comp = "CO2"
        if "feed_stream" in yield_dict:
            feed_stream = yield_dict["feed_stream"]
        if "feed_component" in yield_dict:
            feed_comp = yield_dict["feed_component"]
            
        # Check if we can get mole flows
        if not streams_df.empty:
            target_row = streams_df[streams_df["stream_name"] == target_stream]
            feed_row = streams_df[streams_df["stream_name"] == feed_stream]
            
            if not target_row.empty and not feed_row.empty:
                t_flow = target_row.iloc[0]["mole_flow"]
                t_frac = target_row.iloc[0].get(f"{comp}_mole_frac")
                f_flow = feed_row.iloc[0]["mole_flow"]
                f_frac = feed_row.iloc[0].get(f"{feed_comp}_mole_frac")
                
                if pd.notna(t_flow) and pd.notna(t_frac) and pd.notna(f_flow) and pd.notna(f_frac) and f_flow * f_frac > 0:
                    kpis["yield_fraction"] = (t_flow * t_frac) / (f_flow * f_frac)
                    
        kpis["convergence_status"] = extract_diagnostics(aspen)["convergence_status"]
        
    except Exception as e:
        logger.warning(f"Error calculating KPIs: {e}")
        
    return kpis

def extract_results(aspen: Any, spec: Union[PlantSpecification, Dict]) -> Dict[str, Any]:
    try:
        if isinstance(spec, PlantSpecification):
            spec_dict = spec.model_dump()
        else:
            spec_dict = spec
            
        component_ids = [c.get("id") for c in spec_dict.get("components", []) if "id" in c]
        
        stream_names = _get_element_names(aspen, r"\Data\Streams")
        block_names = _get_element_names(aspen, r"\Data\Blocks")
        
        streams_df = extract_stream_properties(aspen, stream_names, component_ids)
        blocks_df = extract_block_performance(aspen, block_names)
        
        mat_bal = calculate_material_balance(aspen, spec_dict)
        nrg_bal = calculate_energy_balance(aspen, spec_dict)
        kpis = calculate_kpis(aspen, spec_dict, streams_df, blocks_df)
        diags = extract_diagnostics(aspen)
        
        metadata = {
            "extracted_at": datetime.datetime.now().isoformat(),
            "stream_count": len(stream_names),
            "block_count": len(block_names)
        }
        
        return {
            "streams": streams_df,
            "blocks": blocks_df,
            "material_balance": mat_bal,
            "energy_balance": nrg_bal,
            "kpis": kpis,
            "diagnostics": diags,
            "metadata": metadata
        }
    except Exception as e:
        raise ExtractionError(str(e))
