from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


CSV_ARTIFACT_FILENAMES = {
    "streams": "streams.csv",
    "blocks": "blocks.csv",
    "material_balance": "material_balance.csv",
    "energy_balance": "energy_balance.csv",
}


def _artifact_roots(result: Any) -> list[Path]:
    roots: list[Path] = []

    report_dir = getattr(result, "report_dir", None)
    if report_dir:
        roots.append(Path(report_dir))

    layout = getattr(result, "layout", None)
    results_dir = getattr(layout, "results_dir", None) if layout is not None else None
    if results_dir:
        roots.append(Path(results_dir))

    unique_roots: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_roots.append(resolved)
    return unique_roots


def resolve_result_artifact_paths(result: Any) -> dict[str, Path]:
    artifact_paths: dict[str, Path] = {}

    for key, filename in CSV_ARTIFACT_FILENAMES.items():
        for root in _artifact_roots(result):
            candidate = root / filename
            if candidate.is_file():
                artifact_paths[key] = candidate
                break

    return artifact_paths


def load_result_artifact_tables(result: Any) -> tuple[dict[str, Path], dict[str, pd.DataFrame]]:
    artifact_paths = resolve_result_artifact_paths(result)
    tables: dict[str, pd.DataFrame] = {}

    for key, path in artifact_paths.items():
        try:
            tables[key] = pd.read_csv(path)
        except Exception:
            tables[key] = pd.DataFrame()

    return artifact_paths, tables


def _resolve_column(df: pd.DataFrame, *candidates: str) -> str | None:
    lookup = {str(column).strip().lower(): str(column) for column in df.columns}
    for candidate in candidates:
        column = lookup.get(candidate.strip().lower())
        if column is not None:
            return column
    return None


def _numeric_series(df: pd.DataFrame, *candidates: str) -> pd.Series:
    column = _resolve_column(df, *candidates)
    if column is None:
        return pd.Series(dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


def _format_number(value: float | int | None, *, decimals: int = 3) -> str:
    if value is None or pd.isna(value):
        return "n/a"

    numeric_value = float(value)
    if abs(numeric_value) >= 1000:
        return f"{numeric_value:,.1f}"
    if abs(numeric_value) >= 1:
        return f"{numeric_value:.{decimals}f}"
    return f"{numeric_value:.3g}"


def _summarize_streams(streams_df: pd.DataFrame) -> tuple[list[str], dict[str, Any]]:
    if streams_df.empty:
        return ["- `streams.csv`: no rows available."], {}

    lines = [f"- `streams.csv`: {len(streams_df)} stream row(s) loaded."]
    observations: dict[str, Any] = {}

    stream_name_col = _resolve_column(streams_df, "stream_name", "stream")
    mass_flow = _numeric_series(streams_df, "mass_flow")
    if stream_name_col is not None and not mass_flow.empty and mass_flow.notna().any():
        ranked = (
            streams_df.assign(_mass_flow=mass_flow)
            .dropna(subset=["_mass_flow"])
            .sort_values("_mass_flow", ascending=False)
            .head(3)
        )
        if not ranked.empty:
            top_streams = ", ".join(
                f"{row[stream_name_col]} ({_format_number(row['_mass_flow'])})"
                for _, row in ranked.iterrows()
            )
            lines.append(f"- Largest mass-flow streams: {top_streams}.")

    methanol_col = _resolve_column(streams_df, "CH3OH_mass_frac", "CH3OH_mole_frac", "MEOH_mass_frac", "MEOH_mole_frac")
    if stream_name_col is not None and methanol_col is not None:
        methanol_fraction = pd.to_numeric(streams_df[methanol_col], errors="coerce")
        if methanol_fraction.notna().any():
            best_index = methanol_fraction.fillna(-1.0).idxmax()
            best_fraction = methanol_fraction.loc[best_index]
            best_stream = streams_df.loc[best_index, stream_name_col]
            observations["methanol_signal"] = float(best_fraction)
            lines.append(
                f"- Strongest methanol-carrying stream: {best_stream} with `{methanol_col}`={_format_number(best_fraction, decimals=4)}."
            )

    return lines, observations


def _summarize_blocks(blocks_df: pd.DataFrame) -> tuple[list[str], dict[str, Any]]:
    if blocks_df.empty:
        return ["- `blocks.csv`: no rows available."], {}

    lines = [f"- `blocks.csv`: {len(blocks_df)} block row(s) loaded."]
    observations: dict[str, Any] = {}

    block_name_col = _resolve_column(blocks_df, "block_name", "block")
    duty_mw = _numeric_series(blocks_df, "duty_mw")
    if duty_mw.empty or not duty_mw.notna().any():
        duty_kw = _numeric_series(blocks_df, "duty_kw", "duty")
        if duty_kw.notna().any():
            duty_mw = duty_kw / 1000.0

    if block_name_col is not None and not duty_mw.empty and duty_mw.notna().any():
        ranked = (
            blocks_df.assign(_duty_mw=duty_mw, _abs_duty_mw=duty_mw.abs())
            .dropna(subset=["_duty_mw"])
            .sort_values("_abs_duty_mw", ascending=False)
            .head(3)
        )
        if not ranked.empty:
            top_duties = ", ".join(
                f"{row[block_name_col]} ({_format_number(row['_duty_mw'])} MW)"
                for _, row in ranked.iterrows()
            )
            lines.append(f"- Largest absolute block duties: {top_duties}.")

    work_kw = _numeric_series(blocks_df, "net_work_kw")
    if work_kw.notna().any():
        total_work_mw = float(work_kw.fillna(0.0).sum()) / 1000.0
        observations["net_work_mw"] = total_work_mw
        lines.append(f"- Net compressor/pump work from `blocks.csv`: {_format_number(total_work_mw)} MW.")

    return lines, observations


def _summarize_energy_balance(energy_balance_df: pd.DataFrame) -> tuple[list[str], dict[str, Any]]:
    if energy_balance_df.empty:
        return ["- `energy_balance.csv`: no rows available."], {}

    lines = [f"- `energy_balance.csv`: {len(energy_balance_df)} row(s) loaded."]
    observations: dict[str, Any] = {}

    category_col = _resolve_column(energy_balance_df, "category")
    value_mw = _numeric_series(energy_balance_df, "value_mw")
    if category_col is not None and value_mw.notna().any():
        values = {
            str(row[category_col]): float(value_mw.loc[index])
            for index, row in energy_balance_df.iterrows()
            if not pd.isna(value_mw.loc[index])
        }
        heat_input = values.get("Heat Input")
        heat_output = values.get("Heat Output")
        net_work = values.get("Net Work")
        observations.update(
            {
                "heat_input_mw": heat_input,
                "heat_output_mw": heat_output,
                "net_work_mw": net_work,
            }
        )
        lines.append(
            "- Energy summary: "
            f"heat input {_format_number(heat_input)} MW, "
            f"heat output {_format_number(heat_output)} MW, "
            f"net work {_format_number(net_work)} MW."
        )
        return lines, observations

    block_name_col = _resolve_column(energy_balance_df, "block_name", "block")
    duty_mw = _numeric_series(energy_balance_df, "duty_mw")
    if duty_mw.empty or not duty_mw.notna().any():
        duty_kw = _numeric_series(energy_balance_df, "duty_kw", "duty")
        if duty_kw.notna().any():
            duty_mw = duty_kw / 1000.0

    if block_name_col is None or duty_mw.empty or not duty_mw.notna().any():
        return lines, observations

    working_df = energy_balance_df.assign(_duty_mw=duty_mw).dropna(subset=["_duty_mw"])
    total_row = working_df[working_df[block_name_col].astype(str).str.upper() == "TOTAL"]
    detail_rows = working_df[working_df[block_name_col].astype(str).str.upper() != "TOTAL"]

    net_duty_mw = float(total_row["_duty_mw"].iloc[0]) if not total_row.empty else float(detail_rows["_duty_mw"].sum())
    heating_mw = float(detail_rows.loc[detail_rows["_duty_mw"] > 0, "_duty_mw"].sum())
    cooling_mw = float(detail_rows.loc[detail_rows["_duty_mw"] < 0, "_duty_mw"].sum())

    observations.update(
        {
            "net_duty_mw": net_duty_mw,
            "heating_mw": heating_mw,
            "cooling_mw": cooling_mw,
        }
    )
    lines.append(
        "- Energy summary: "
        f"net duty {_format_number(net_duty_mw)} MW, "
        f"heating {_format_number(heating_mw)} MW, "
        f"cooling {_format_number(cooling_mw)} MW."
    )
    return lines, observations


def _summarize_material_balance(material_balance_df: pd.DataFrame) -> tuple[list[str], dict[str, Any]]:
    if material_balance_df.empty:
        return ["- `material_balance.csv`: no rows available."], {}

    lines = [f"- `material_balance.csv`: {len(material_balance_df)} component row(s) loaded."]
    observations: dict[str, Any] = {}

    component_col = _resolve_column(material_balance_df, "component", "component_id")
    closure_pct = _numeric_series(material_balance_df, "closure_pct", "closure_%")
    if component_col is None or closure_pct.empty or not closure_pct.notna().any():
        return lines, observations

    ranked = (
        material_balance_df.assign(_closure_pct=closure_pct, _abs_closure_pct=closure_pct.abs())
        .dropna(subset=["_closure_pct"])
        .sort_values("_abs_closure_pct", ascending=False)
        .head(3)
    )
    if ranked.empty:
        return lines, observations

    worst_abs_closure_pct = float(ranked["_abs_closure_pct"].iloc[0])
    observations["worst_abs_closure_pct"] = worst_abs_closure_pct

    closure_summary = ", ".join(
        f"{row[component_col]} ({_format_number(row['_closure_pct'])}%)"
        for _, row in ranked.iterrows()
    )
    lines.append(f"- Largest feed/product closure gaps: {closure_summary}.")
    return lines, observations


def _diagnosis_lines(observations: dict[str, Any]) -> list[str]:
    focus_items: list[str] = []

    worst_abs_closure_pct = observations.get("worst_abs_closure_pct")
    if isinstance(worst_abs_closure_pct, (int, float)) and worst_abs_closure_pct > 5.0:
        focus_items.append("the feed/product cut is not materially closed")

    methanol_signal = observations.get("methanol_signal")
    if isinstance(methanol_signal, (int, float)) and methanol_signal < 0.5:
        focus_items.append("no methanol-rich stream stands out in `streams.csv`")

    net_duty_mw = observations.get("net_duty_mw")
    if isinstance(net_duty_mw, (int, float)) and abs(net_duty_mw) > 1000.0:
        focus_items.append("the net heat duty magnitude is extreme")

    if not focus_items:
        return ["- Diagnostic focus: review the dominant block duties and the identified product stream before trusting any KPI-level summary."]

    return ["- Diagnostic focus: " + "; ".join(focus_items) + "."]


def build_codex_results_markdown(
    process_name: str,
    artifact_paths: dict[str, Path],
    tables: dict[str, pd.DataFrame],
    *,
    acceptance: dict[str, Any] | None = None,
) -> str:
    lines = [
        f"### Codex Session Analysis: `{process_name}`",
        "",
        "Use the CSV artifacts below as the source of truth for interpretation:",
    ]

    for key in ["streams", "blocks", "material_balance", "energy_balance"]:
        filename = CSV_ARTIFACT_FILENAMES[key]
        path = artifact_paths.get(key)
        if path is None:
            lines.append(f"- `{filename}`: missing")
        else:
            lines.append(f"- `{filename}`: `{path}`")

    lines.append("")
    lines.append("CSV-based readout:")

    observations: dict[str, Any] = {}
    for helper, key in [
        (_summarize_streams, "streams"),
        (_summarize_blocks, "blocks"),
        (_summarize_material_balance, "material_balance"),
        (_summarize_energy_balance, "energy_balance"),
    ]:
        section_lines, section_observations = helper(tables.get(key, pd.DataFrame()))
        lines.extend(section_lines)
        observations.update(section_observations)

    if isinstance(acceptance, dict) and "passed" in acceptance:
        lines.append(f"- Acceptance status from `acceptance.json`: {acceptance.get('passed')}.")

    lines.extend(_diagnosis_lines(observations))
    return "\n".join(lines)


__all__ = [
    "CSV_ARTIFACT_FILENAMES",
    "build_codex_results_markdown",
    "load_result_artifact_tables",
    "resolve_result_artifact_paths",
]
