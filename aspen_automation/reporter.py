import datetime
import json
import os
from typing import Any, Dict

import pandas as pd
from .schema import PlantSpecification


def _create_run_dir(output_dir: str) -> str:
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = os.path.join(output_dir, f"run_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def _write_csv_reports(results: Dict[str, Any], run_dir: str) -> None:
    for key in ["streams", "blocks", "material_balance", "energy_balance"]:
        df = results.get(key)
        if isinstance(df, pd.DataFrame) and not df.empty:
            df.to_csv(os.path.join(run_dir, f"{key}.csv"), index=False)


def _write_json_reports(results: Dict[str, Any], run_dir: str) -> None:
    kpis_path = os.path.join(run_dir, "kpis.json")
    diagnostics_path = os.path.join(run_dir, "diagnostics.json")

    with open(kpis_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(results.get("kpis", {}), indent=2, default=str))

    with open(diagnostics_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(results.get("diagnostics", {}), indent=2, default=str))


def _extract_spec_metadata(spec: Any) -> Dict[str, Any]:
    if isinstance(spec, dict):
        metadata = spec.get("metadata", {})
        return metadata if isinstance(metadata, dict) else {}

    if isinstance(spec, PlantSpecification):
        metadata = spec.model_dump().get("metadata", {})
        return metadata if isinstance(metadata, dict) else {}

    return {}


def _write_html_summary(results: Dict[str, Any], spec: Any, run_dir: str) -> None:
    metadata = _extract_spec_metadata(spec)
    title = metadata.get("title", "Aspen Run Summary")

    kpis = results.get("kpis", {}) or {}
    status = kpis.get("convergence_status", "unknown")
    status_color = "#27ae60" if status == "converged" else "#e74c3c"

    streams_df = results.get("streams")
    if isinstance(streams_df, pd.DataFrame) and not streams_df.empty:
        streams_table = streams_df.head(10).to_html(index=False, border=0)
    else:
        streams_table = "<p>No stream data available.</p>"

    blocks_df = results.get("blocks")
    if isinstance(blocks_df, pd.DataFrame) and not blocks_df.empty:
        blocks_table = blocks_df.head(10).to_html(index=False, border=0)
    else:
        blocks_table = "<p>No block data available.</p>"

    kpi_rows = "".join(
        f"<tr><td>{name}</td><td>{value}</td></tr>"
        for name, value in kpis.items()
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #2c3e50; }}
    h1, h2 {{ margin-bottom: 8px; }}
    .status {{ font-weight: 700; color: {status_color}; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 16px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background: #f5f7fa; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <p>Convergence Status: <span class="status">{status}</span></p>

  <h2>KPIs</h2>
  <table>
    <thead><tr><th>KPI</th><th>Value</th></tr></thead>
    <tbody>{kpi_rows}</tbody>
  </table>

  <h2>Top 10 Streams</h2>
  {streams_table}

  <h2>Top 10 Blocks</h2>
  {blocks_table}
</body>
</html>
"""

    with open(os.path.join(run_dir, "run_summary.html"), "w", encoding="utf-8") as f:
        f.write(html)


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "No data available."

    columns = list(df.columns)
    header = "| " + " | ".join(str(col) for col in columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    rows = []
    for _, row in df.iterrows():
        rows.append("| " + " | ".join(str(row[col]) for col in columns) + " |")
    return "\n".join([header, separator] + rows)


def _write_markdown_summary(results: Dict[str, Any], spec: Any, run_dir: str) -> None:
    metadata = _extract_spec_metadata(spec)
    title = metadata.get("title", "Aspen Run Summary")
    kpis = results.get("kpis", {}) or {}

    lines = [f"# {title}", ""]

    lines.append("## KPIs")
    lines.append("| KPI | Value |")
    lines.append("| --- | --- |")
    for name, value in kpis.items():
        lines.append(f"| {name} | {value} |")
    lines.append("")

    lines.append("## Streams (Top 10)")
    streams_df = results.get("streams")
    if isinstance(streams_df, pd.DataFrame) and not streams_df.empty:
        lines.append(_df_to_markdown_table(streams_df.head(10)))
    else:
        lines.append("No stream data available.")
    lines.append("")

    lines.append("## Blocks (Top 10)")
    blocks_df = results.get("blocks")
    if isinstance(blocks_df, pd.DataFrame) and not blocks_df.empty:
        lines.append(_df_to_markdown_table(blocks_df.head(10)))
    else:
        lines.append("No block data available.")
    lines.append("")

    with open(os.path.join(run_dir, "run_summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _print_console_summary(results: Dict[str, Any], run_dir: str) -> None:
    kpis = results.get("kpis", {}) or {}
    status = kpis.get("convergence_status", "unknown")

    print("=" * 80)
    print(f"Convergence status: {status}")
    print("KPI values:")
    for name, value in kpis.items():
        print(f"- {name}: {value}")
    print("Generated files:")
    for filename in sorted(os.listdir(run_dir)):
        print(f"- {filename}")


def generate_reports(results: Dict[str, Any], spec: Any, output_dir: str = "results/", format: str = "html") -> str:
    run_dir = _create_run_dir(output_dir)
    _write_csv_reports(results, run_dir)
    _write_json_reports(results, run_dir)

    if format == "html":
        _write_html_summary(results, spec, run_dir)
    else:
        _write_markdown_summary(results, spec, run_dir)

    _print_console_summary(results, run_dir)
    return run_dir
