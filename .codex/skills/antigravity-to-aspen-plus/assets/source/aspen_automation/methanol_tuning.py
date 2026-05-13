from __future__ import annotations

import copy
import datetime as _dt
import json
import math
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

import pandas as pd

from .parser import load_spec
from .process_library import ProcessRunResult, run_process_batch_first
from .process_spec_coherence import dump_process_spec_yaml


DEFAULT_PRE_EXPONENTIAL_MULTIPLIERS = (10.0, 30.0, 100.0, 300.0, 1000.0)
DEFAULT_RPLUG_LENGTHS = (12.0, 16.0, 24.0)
DEFAULT_RPLUG_DIAMETERS = (4.0, 6.0)
DEFAULT_PURGE_FRACTIONS = (0.02, 0.05, 0.08, 0.10, 0.15, 0.20)
DEFAULT_ATR_FACTORS = (
    (1.00, 1.00),
    (1.10, 0.95),
    (1.20, 0.90),
    (1.30, 0.85),
    (1.40, 0.80),
)
EXTENDED_ATR_FACTOR = (1.50, 0.75)
DEFAULT_MIN_R_OUT_CH3OH_MOLE_FRAC = 0.01
DEFAULT_MIN_PRODUCT_CH3OH_TPD = 500.0


@dataclass(frozen=True)
class MethanolTuningSettings:
    case_id: str
    stage: str
    pre_exponential_multiplier: float = 1.0
    length: float | None = None
    diameter: float | None = None
    purge_fraction: float | None = None
    steam_factor: float = 1.0
    oxygen_factor: float = 1.0
    parent_case_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "stage": self.stage,
            "pre_exponential_multiplier": self.pre_exponential_multiplier,
            "length": self.length,
            "diameter": self.diameter,
            "purge_fraction": self.purge_fraction,
            "recycle_fraction": None if self.purge_fraction is None else 1.0 - self.purge_fraction,
            "steam_factor": self.steam_factor,
            "oxygen_factor": self.oxygen_factor,
            "parent_case_id": self.parent_case_id,
        }


@dataclass
class MethanolTuningCaseResult:
    settings: MethanolTuningSettings
    process_dir: Path
    spec_path: Path
    result: ProcessRunResult | None
    metrics: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    @property
    def stop_rule_met(self) -> bool:
        return bool(self.metrics.get("stop_rule_met"))

    @property
    def succeeded(self) -> bool:
        return bool(self.metrics.get("succeeded"))

    def to_summary_row(self) -> dict[str, Any]:
        row = self.settings.to_dict()
        row.update(
            {
                "process_dir": str(self.process_dir),
                "spec_path": str(self.spec_path),
                "run_dir": self.metrics.get("run_dir"),
                "status": self.metrics.get("status", "not_run"),
                "succeeded": self.succeeded,
                "clean_history": self.metrics.get("clean_history"),
                "results_readable": self.metrics.get("results_readable"),
                "stop_rule_met": self.stop_rule_met,
                "r_out_ch3oh_mole_frac": self.metrics.get("r_out_ch3oh_mole_frac"),
                "product_ch3oh_tpd": self.metrics.get("product_ch3oh_tpd"),
                "product_total_tpd": self.metrics.get("product_total_tpd"),
                "purity_fraction": self.metrics.get("purity_fraction"),
                "rin_stoichiometric_number": self.metrics.get("rin_stoichiometric_number"),
                "rin_ch4_mole_frac": self.metrics.get("rin_ch4_mole_frac"),
                "rin_co2_mole_frac": self.metrics.get("rin_co2_mole_frac"),
                "purge_ch3oh_tpd": self.metrics.get("purge_ch3oh_tpd"),
                "purge_methanol_loss_fraction": self.metrics.get("purge_methanol_loss_fraction"),
                "recycle_ch4_co2_mole_frac": self.metrics.get("recycle_ch4_co2_mole_frac"),
                "recycle_not_ch4_co2_dominated": self.metrics.get("recycle_not_ch4_co2_dominated"),
                "score": self.metrics.get("score"),
                "error": self.error or self.metrics.get("error"),
            }
        )
        return row


@dataclass
class MethanolTuningCampaignResult:
    campaign_dir: Path
    summary_csv_path: Path
    summary_json_path: Path
    best_process_path: Path | None
    promoted: bool
    promoted_spec_path: Path | None
    backup_spec_path: Path | None
    best_case: MethanolTuningCaseResult | None
    cases: list[MethanolTuningCaseResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_dir": str(self.campaign_dir),
            "summary_csv_path": str(self.summary_csv_path),
            "summary_json_path": str(self.summary_json_path),
            "best_process_path": str(self.best_process_path) if self.best_process_path else None,
            "promoted": self.promoted,
            "promoted_spec_path": str(self.promoted_spec_path) if self.promoted_spec_path else None,
            "backup_spec_path": str(self.backup_spec_path) if self.backup_spec_path else None,
            "best_case": self.best_case.to_summary_row() if self.best_case else None,
            "case_count": len(self.cases),
            "stop_rule_met": bool(self.best_case and self.best_case.stop_rule_met),
        }


def build_methanol_tuning_variant_spec(
    base_spec: dict[str, Any],
    settings: MethanolTuningSettings,
) -> dict[str, Any]:
    variant = copy.deepcopy(base_spec)
    _scale_kinetic_pre_exponentials(variant, settings.pre_exponential_multiplier)
    if settings.length is not None or settings.diameter is not None:
        _set_b_syn_geometry(variant, length=settings.length, diameter=settings.diameter)
    if settings.purge_fraction is not None:
        _set_purge_fraction(variant, settings.purge_fraction)
    _scale_external_feed(variant, stream_name="STEAM", factor=settings.steam_factor)
    _scale_external_feed(variant, stream_name="O2-FEED", factor=settings.oxygen_factor)
    _annotate_variant(variant, settings)
    return variant


def score_methanol_tuning_metrics(
    metrics: dict[str, Any],
    *,
    min_r_out_ch3oh_mole_frac: float = DEFAULT_MIN_R_OUT_CH3OH_MOLE_FRAC,
    min_product_ch3oh_tpd: float = DEFAULT_MIN_PRODUCT_CH3OH_TPD,
) -> tuple[float, ...]:
    succeeded = 1.0 if metrics.get("succeeded") else 0.0
    stop_rule = 1.0 if metrics.get("stop_rule_met") else 0.0
    product = _finite_float(metrics.get("product_ch3oh_tpd"), default=-1.0)
    r_out = _finite_float(metrics.get("r_out_ch3oh_mole_frac"), default=-1.0)
    sn = _finite_float(metrics.get("rin_stoichiometric_number"), default=0.0)
    purge_loss = _finite_float(metrics.get("purge_methanol_loss_fraction"), default=1.0)
    purity = _finite_float(metrics.get("purity_fraction"), default=0.0)

    near_product_target = min(product / min_product_ch3oh_tpd, 1.0) if min_product_ch3oh_tpd > 0 else 0.0
    near_rout_target = min(r_out / min_r_out_ch3oh_mole_frac, 1.0) if min_r_out_ch3oh_mole_frac > 0 else 0.0
    return (
        succeeded,
        stop_rule,
        product,
        near_product_target,
        r_out,
        near_rout_target,
        -abs(sn - 2.0),
        -purge_loss,
        purity,
    )


def run_methanol_tuning_campaign(
    process_dir: str | Path,
    runs_root: str | Path,
    *,
    campaign_root: str | Path | None = None,
    visible: bool = False,
    timeout_seconds: int = 1800,
    batch_timeout_seconds: int = 1800,
    report_format: str = "html",
    engine_path: str | None = None,
    max_cases: int = 40,
    promote: bool = True,
    min_r_out_ch3oh_mole_frac: float = DEFAULT_MIN_R_OUT_CH3OH_MOLE_FRAC,
    min_product_ch3oh_tpd: float = DEFAULT_MIN_PRODUCT_CH3OH_TPD,
    runner: Callable[..., ProcessRunResult] = run_process_batch_first,
) -> MethanolTuningCampaignResult:
    process_path = Path(process_dir).expanduser().resolve()
    canonical_spec_path = process_path / "process.yaml"
    if not canonical_spec_path.is_file():
        raise FileNotFoundError(f"Canonical process spec not found: {canonical_spec_path}")

    root = Path(campaign_root).expanduser().resolve() if campaign_root else _default_campaign_root(runs_root)
    variants_root = root / "variants"
    live_runs_root = root / "live_runs"
    root.mkdir(parents=True, exist_ok=True)
    variants_root.mkdir(parents=True, exist_ok=True)
    live_runs_root.mkdir(parents=True, exist_ok=True)

    base_spec = load_spec(str(canonical_spec_path))
    cases: list[MethanolTuningCaseResult] = []

    def run_case(settings: MethanolTuningSettings, source_spec: dict[str, Any]) -> MethanolTuningCaseResult:
        if len(cases) >= max_cases:
            raise RuntimeError(f"Methanol tuning case budget exhausted at {max_cases} cases.")
        variant_spec = build_methanol_tuning_variant_spec(source_spec, settings)
        variant_process_dir = variants_root / settings.case_id
        spec_path = _write_variant_process_dir(process_path, variant_process_dir, variant_spec, settings)
        try:
            result = runner(
                variant_process_dir,
                live_runs_root,
                visible=visible,
                enforce_acceptance_targets=False,
                timeout_seconds=timeout_seconds,
                batch_timeout_seconds=batch_timeout_seconds,
                report_format=report_format,
                engine_path=engine_path,
            )
            metrics = collect_methanol_tuning_metrics(
                result,
                min_r_out_ch3oh_mole_frac=min_r_out_ch3oh_mole_frac,
                min_product_ch3oh_tpd=min_product_ch3oh_tpd,
            )
            metrics["score"] = score_methanol_tuning_metrics(
                metrics,
                min_r_out_ch3oh_mole_frac=min_r_out_ch3oh_mole_frac,
                min_product_ch3oh_tpd=min_product_ch3oh_tpd,
            )
            _write_live_aspen_summary(result, metrics)
            case = MethanolTuningCaseResult(settings, variant_process_dir, spec_path, result, metrics)
        except Exception as exc:
            metrics = {
                "status": "exception",
                "succeeded": False,
                "stop_rule_met": False,
                "error": str(exc),
                "score": score_methanol_tuning_metrics({"succeeded": False, "stop_rule_met": False}),
            }
            case = MethanolTuningCaseResult(settings, variant_process_dir, spec_path, None, metrics, error=str(exc))
        cases.append(case)
        _write_campaign_outputs(root, cases, best_case=_best_case(cases), promoted=False)
        return case

    stage1_cases = []
    for multiplier in DEFAULT_PRE_EXPONENTIAL_MULTIPLIERS:
        if len(cases) >= max_cases:
            break
        stage1_cases.append(
            run_case(
                MethanolTuningSettings(
                    case_id=f"s1_pre_x{_format_case_number(multiplier)}",
                    stage="stage1_pre_exponential_sweep",
                    pre_exponential_multiplier=multiplier,
                ),
                base_spec,
            )
        )

    best_stage1 = _best_case(stage1_cases)
    if best_stage1 is not None and not any(case.stop_rule_met for case in stage1_cases):
        best_stage1_spec = load_spec(str(best_stage1.spec_path))
        for length in DEFAULT_RPLUG_LENGTHS:
            for diameter in DEFAULT_RPLUG_DIAMETERS:
                if len(cases) >= max_cases:
                    break
                stage1_cases.append(
                    run_case(
                        MethanolTuningSettings(
                            case_id=(
                                f"s1_vol_L{_format_case_number(length)}_D{_format_case_number(diameter)}"
                            ),
                            stage="stage1_reactor_volume_sweep",
                            pre_exponential_multiplier=1.0,
                            length=length,
                            diameter=diameter,
                            parent_case_id=best_stage1.settings.case_id,
                        ),
                        best_stage1_spec,
                    )
                )
            if len(cases) >= max_cases:
                break

    best_stage1 = _best_case(stage1_cases) or _best_case(cases)
    if best_stage1 is not None:
        stage2_cases = []
        best_stage1_spec = load_spec(str(best_stage1.spec_path))
        baseline_product = _finite_float(best_stage1.metrics.get("product_ch3oh_tpd"), default=0.0)
        for purge_fraction in DEFAULT_PURGE_FRACTIONS:
            if len(cases) >= max_cases:
                break
            case = run_case(
                MethanolTuningSettings(
                    case_id=f"s2_purge_{_format_case_number(purge_fraction)}",
                    stage="stage2_purge_sweep",
                    purge_fraction=purge_fraction,
                    parent_case_id=best_stage1.settings.case_id,
                ),
                best_stage1_spec,
            )
            if _stage2_case_is_eligible(case, baseline_product):
                stage2_cases.append(case)
        best_stage2 = _best_case(stage2_cases) or best_stage1
    else:
        best_stage2 = None

    if best_stage2 is not None:
        stage3_cases = []
        best_stage2_spec = load_spec(str(best_stage2.spec_path))
        for steam_factor, oxygen_factor in DEFAULT_ATR_FACTORS:
            if len(cases) >= max_cases:
                break
            stage3_cases.append(
                run_case(
                    MethanolTuningSettings(
                        case_id=(
                            f"s3_atr_S{_format_case_number(steam_factor)}"
                            f"_O{_format_case_number(oxygen_factor)}"
                        ),
                        stage="stage3_atr_feed_sweep",
                        steam_factor=steam_factor,
                        oxygen_factor=oxygen_factor,
                        parent_case_id=best_stage2.settings.case_id,
                    ),
                    best_stage2_spec,
                )
            )
        best_stage3 = _best_case(stage3_cases) or best_stage2
        if (
            best_stage3 is not None
            and _finite_float(best_stage3.metrics.get("rin_stoichiometric_number"), default=0.0) < 1.8
            and len(cases) < max_cases
        ):
            steam_factor, oxygen_factor = EXTENDED_ATR_FACTOR
            stage3_cases.append(
                run_case(
                    MethanolTuningSettings(
                        case_id=(
                            f"s3_atr_S{_format_case_number(steam_factor)}"
                            f"_O{_format_case_number(oxygen_factor)}"
                        ),
                        stage="stage3_atr_feed_sweep_extended",
                        steam_factor=steam_factor,
                        oxygen_factor=oxygen_factor,
                        parent_case_id=best_stage2.settings.case_id,
                    ),
                    best_stage2_spec,
                )
            )
    best = _best_case(cases)

    best_process_path: Path | None = None
    promoted_spec_path: Path | None = None
    backup_spec_path: Path | None = None
    promoted = False
    if best is not None:
        best_process_path = root / "best_process.yaml"
        shutil.copy2(best.spec_path, best_process_path)
        if promote and best.stop_rule_met:
            backup_spec_path = process_path / f"process.bak_tuning_{_timestamp()}.yaml"
            shutil.copy2(canonical_spec_path, backup_spec_path)
            shutil.copy2(best_process_path, canonical_spec_path)
            promoted = True
            promoted_spec_path = canonical_spec_path

    summary_csv, summary_json = _write_campaign_outputs(
        root,
        cases,
        best_case=best,
        promoted=promoted,
        best_process_path=best_process_path,
        promoted_spec_path=promoted_spec_path,
        backup_spec_path=backup_spec_path,
    )
    return MethanolTuningCampaignResult(
        campaign_dir=root,
        summary_csv_path=summary_csv,
        summary_json_path=summary_json,
        best_process_path=best_process_path,
        promoted=promoted,
        promoted_spec_path=promoted_spec_path,
        backup_spec_path=backup_spec_path,
        best_case=best,
        cases=cases,
    )


def collect_methanol_tuning_metrics(
    result: ProcessRunResult,
    *,
    min_r_out_ch3oh_mole_frac: float = DEFAULT_MIN_R_OUT_CH3OH_MOLE_FRAC,
    min_product_ch3oh_tpd: float = DEFAULT_MIN_PRODUCT_CH3OH_TPD,
) -> dict[str, Any]:
    layout = result.layout
    results_dir = layout.results_dir if layout is not None else None
    kpis = _read_json(results_dir / "kpis.json") if results_dir is not None else {}
    build = _read_json(results_dir / "build_diagnostics.json") if results_dir is not None else {}
    simulation = _read_json(results_dir / "simulation_diagnostics.json") if results_dir is not None else {}
    streams = _read_streams(results_dir / "streams.csv") if results_dir is not None else pd.DataFrame()
    synthesis = kpis.get("synthesis_loop", {}) if isinstance(kpis, dict) else {}
    history = build.get("history_diagnostics", {}) if isinstance(build, dict) else {}

    r_out_ch3oh = _stream_value(streams, "R-OUT", "CH3OH_mole_frac")
    if r_out_ch3oh is None:
        r_out_ch3oh = synthesis.get("outlet_ch3oh_mole_frac") if isinstance(synthesis, dict) else None

    product_ch3oh_tpd = kpis.get("product_component_tpd", kpis.get("methanol_tpd")) if isinstance(kpis, dict) else None
    product_total_tpd = kpis.get("product_total_tpd", kpis.get("production_rate_tpd")) if isinstance(kpis, dict) else None
    purge_ch3oh_tpd = _component_tpd(streams, "PURGE", "CH3OH")
    product_stream = kpis.get("product_stream", "MEOH-PRO") if isinstance(kpis, dict) else "MEOH-PRO"
    product_from_stream_tpd = _component_tpd(streams, str(product_stream), "CH3OH")
    if product_ch3oh_tpd is None and product_from_stream_tpd is not None:
        product_ch3oh_tpd = product_from_stream_tpd

    denom = _finite_float(purge_ch3oh_tpd, default=0.0) + _finite_float(product_ch3oh_tpd, default=0.0)
    purge_loss_fraction = None if denom <= 0 else _finite_float(purge_ch3oh_tpd, default=0.0) / denom
    recycle_ch4_co2 = _combined_mole_fraction(streams, "RECYCLE", ("CH4", "CO2"))
    recycle_not_dominated = None if recycle_ch4_co2 is None else recycle_ch4_co2 < 0.5
    clean_history = (
        history.get("status") == "converged"
        and not history.get("input_translation_failed", False)
        and not history.get("terminal_errors")
        and not history.get("severe_errors")
    )
    results_readable = simulation.get("results_status") == "readable"
    succeeded = bool(result.succeeded and clean_history and results_readable)
    product_value = _finite_float(product_ch3oh_tpd, default=0.0)
    r_out_value = _finite_float(r_out_ch3oh, default=0.0)
    stop_rule_met = succeeded and product_value >= min_product_ch3oh_tpd and r_out_value >= min_r_out_ch3oh_mole_frac

    metrics: dict[str, Any] = {
        "status": result.status,
        "error": result.error,
        "succeeded": succeeded,
        "clean_history": clean_history,
        "results_readable": results_readable,
        "stop_rule_met": stop_rule_met,
        "run_dir": str(layout.run_dir) if layout is not None else None,
        "results_dir": str(results_dir) if results_dir is not None else None,
        "report_dir": str(result.report_dir) if result.report_dir else None,
        "r_out_ch3oh_mole_frac": r_out_ch3oh,
        "product_ch3oh_tpd": product_ch3oh_tpd,
        "product_total_tpd": product_total_tpd,
        "purity_fraction": kpis.get("purity_fraction") if isinstance(kpis, dict) else None,
        "rin_stoichiometric_number": synthesis.get("inlet_stoichiometric_number") if isinstance(synthesis, dict) else None,
        "rin_ch4_mole_frac": synthesis.get("inlet_ch4_mole_frac") if isinstance(synthesis, dict) else None,
        "rin_co2_mole_frac": synthesis.get("inlet_co2_mole_frac") if isinstance(synthesis, dict) else None,
        "purge_ch3oh_tpd": purge_ch3oh_tpd,
        "purge_methanol_loss_fraction": purge_loss_fraction,
        "recycle_ch4_co2_mole_frac": recycle_ch4_co2,
        "recycle_not_ch4_co2_dominated": recycle_not_dominated,
        "history_status": history.get("status"),
        "simulation_status": simulation.get("status"),
        "simulation_results_status": simulation.get("results_status"),
    }
    return metrics


def _scale_kinetic_pre_exponentials(spec: dict[str, Any], multiplier: float) -> None:
    for chemistry in spec.get("chemistry") or []:
        for reaction in chemistry.get("reactions") or []:
            parameters = reaction.get("parameters") or {}
            if str(parameters.get("reaction_type", "")).upper() != "KINETIC":
                continue
            value = parameters.get("pre_exponential_factor")
            if value is not None:
                parameters["pre_exponential_factor"] = float(value) * float(multiplier)


def _set_b_syn_geometry(spec: dict[str, Any], *, length: float | None, diameter: float | None) -> None:
    block = _find_block(spec, "B-SYN")
    parameters = block.setdefault("parameters", {})
    if length is not None:
        parameters["LENGTH"] = float(length)
    if diameter is not None:
        parameters["DIAM"] = float(diameter)


def _set_purge_fraction(spec: dict[str, Any], purge_fraction: float) -> None:
    if not 0.0 < purge_fraction < 1.0:
        raise ValueError("purge_fraction must be between 0 and 1")
    split = _find_block(spec, "SPLIT")
    fractions = split.get("split_fractions") or []
    if not fractions:
        raise ValueError("SPLIT block must define split_fractions")
    for item in fractions:
        stream = str(item.get("stream", "")).upper()
        if stream == "PURGE":
            item["fraction"] = float(purge_fraction)
        elif stream == "RECYCLE":
            item["fraction"] = float(1.0 - purge_fraction)


def _scale_external_feed(spec: dict[str, Any], *, stream_name: str, factor: float) -> None:
    if factor == 1.0:
        return
    stream = _find_stream(spec, stream_name)
    mass_flow = stream.get("mass_flow")
    if mass_flow is None:
        raise ValueError(f"Stream {stream_name!r} does not define mass_flow")
    stream["mass_flow"] = float(mass_flow) * float(factor)


def _annotate_variant(spec: dict[str, Any], settings: MethanolTuningSettings) -> None:
    models = spec.get("kinetic_models")
    if isinstance(models, list) and models:
        model = models[0]
        if isinstance(model, dict):
            model["campaign_note"] = (
                "Methanol tuning campaign scales POWERLAW pre-exponential factors and RPLUG "
                "LENGTH/DIAM only; CAT-WT remains documented but inactive because INP generation "
                "does not emit it for RPLUG in this workflow."
            )


def _find_block(spec: dict[str, Any], name: str) -> dict[str, Any]:
    for block in spec.get("blocks") or []:
        if str(block.get("name", "")).upper() == name.upper():
            return block
    raise ValueError(f"Block not found: {name}")


def _find_stream(spec: dict[str, Any], name: str) -> dict[str, Any]:
    for stream in spec.get("streams") or []:
        if str(stream.get("name", "")).upper() == name.upper():
            return stream
    raise ValueError(f"Stream not found: {name}")


def _write_variant_process_dir(
    source_process_dir: Path,
    variant_process_dir: Path,
    spec: dict[str, Any],
    settings: MethanolTuningSettings,
) -> Path:
    variant_process_dir.mkdir(parents=True, exist_ok=True)
    assets_src = source_process_dir / "assets"
    assets_dst = variant_process_dir / "assets"
    if assets_src.is_dir() and not assets_dst.exists():
        shutil.copytree(assets_src, assets_dst)
    spec_path = variant_process_dir / "process.yaml"
    spec_path.write_text(dump_process_spec_yaml(spec), encoding="utf-8")
    (variant_process_dir / "tuning_case.json").write_text(
        json.dumps(settings.to_dict(), indent=2, default=str),
        encoding="utf-8",
    )
    return spec_path


def _write_campaign_outputs(
    campaign_dir: Path,
    cases: Iterable[MethanolTuningCaseResult],
    *,
    best_case: MethanolTuningCaseResult | None,
    promoted: bool,
    best_process_path: Path | None = None,
    promoted_spec_path: Path | None = None,
    backup_spec_path: Path | None = None,
) -> tuple[Path, Path]:
    rows = [case.to_summary_row() for case in cases]
    summary_csv_path = campaign_dir / "tuning_campaign_summary.csv"
    summary_json_path = campaign_dir / "tuning_campaign_summary.json"
    pd.DataFrame(rows).to_csv(summary_csv_path, index=False)
    payload = {
        "campaign_dir": str(campaign_dir),
        "case_count": len(rows),
        "promoted": promoted,
        "best_process_path": str(best_process_path) if best_process_path else None,
        "promoted_spec_path": str(promoted_spec_path) if promoted_spec_path else None,
        "backup_spec_path": str(backup_spec_path) if backup_spec_path else None,
        "best_case": best_case.to_summary_row() if best_case else None,
        "cases": rows,
    }
    summary_json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return summary_csv_path, summary_json_path


def _write_live_aspen_summary(result: ProcessRunResult, metrics: dict[str, Any]) -> None:
    if result.layout is None:
        return
    run_dir = result.layout.run_dir
    results_dir = result.layout.results_dir
    summary = {
        "status": result.status,
        "succeeded": result.succeeded,
        "error": result.error,
        "run_dir": str(run_dir),
        "generated_inp_path": str(result.layout.generated_inp_path),
        "output_bkp_path": str(run_dir / f"{result.process_name}_output.bkp"),
        "context_probe_path": str(results_dir / "context_probe.json"),
        "build_diagnostics_path": str(results_dir / "build_diagnostics.json"),
        "simulation_diagnostics_path": str(results_dir / "simulation_diagnostics.json"),
        "acceptance_path": str(results_dir / "acceptance.json"),
        "kpis_path": str(results_dir / "kpis.json"),
        "streams_path": str(results_dir / "streams.csv"),
        "blocks_path": str(results_dir / "blocks.csv"),
        "report_dir": str(result.report_dir) if result.report_dir else None,
        "tuning_metrics": metrics,
    }
    (run_dir / "live_aspen_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")


def _best_case(cases: Iterable[MethanolTuningCaseResult]) -> MethanolTuningCaseResult | None:
    eligible = list(cases)
    if not eligible:
        return None
    return max(eligible, key=lambda case: tuple(case.metrics.get("score") or score_methanol_tuning_metrics(case.metrics)))


def _stage2_case_is_eligible(case: MethanolTuningCaseResult, baseline_product_tpd: float) -> bool:
    if not case.succeeded:
        return False
    if case.metrics.get("recycle_not_ch4_co2_dominated") is False:
        return False
    product = _finite_float(case.metrics.get("product_ch3oh_tpd"), default=-1.0)
    return product >= baseline_product_tpd


def _default_campaign_root(runs_root: str | Path) -> Path:
    return Path(runs_root).expanduser().resolve() / "methanol_tuning_campaigns" / f"campaign_{_timestamp()}"


def _timestamp() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _format_case_number(value: float) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return str(int(numeric))
    return str(numeric).replace(".", "p").replace("-", "m")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _read_streams(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _stream_value(streams: pd.DataFrame, stream_name: str, column: str) -> float | None:
    if streams.empty or "stream_name" not in streams.columns or column not in streams.columns:
        return None
    row = streams.loc[streams["stream_name"].astype(str).str.upper() == stream_name.upper()]
    if row.empty:
        return None
    value = pd.to_numeric(row.iloc[0][column], errors="coerce")
    if pd.isna(value):
        return None
    return float(value)


def _component_tpd(streams: pd.DataFrame, stream_name: str, component: str) -> float | None:
    mass_flow = _stream_value(streams, stream_name, "mass_flow")
    mass_frac = _stream_value(streams, stream_name, f"{component}_mass_frac")
    if mass_flow is None or mass_frac is None:
        return None
    return mass_flow * mass_frac * 24.0 / 1000.0


def _combined_mole_fraction(streams: pd.DataFrame, stream_name: str, components: tuple[str, ...]) -> float | None:
    values = [_stream_value(streams, stream_name, f"{component}_mole_frac") for component in components]
    if any(value is None for value in values):
        return None
    return sum(float(value) for value in values if value is not None)


def _finite_float(value: Any, *, default: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(numeric):
        return default
    return numeric


__all__ = [
    "DEFAULT_ATR_FACTORS",
    "DEFAULT_MIN_PRODUCT_CH3OH_TPD",
    "DEFAULT_MIN_R_OUT_CH3OH_MOLE_FRAC",
    "DEFAULT_PRE_EXPONENTIAL_MULTIPLIERS",
    "DEFAULT_PURGE_FRACTIONS",
    "DEFAULT_RPLUG_DIAMETERS",
    "DEFAULT_RPLUG_LENGTHS",
    "MethanolTuningCampaignResult",
    "MethanolTuningCaseResult",
    "MethanolTuningSettings",
    "build_methanol_tuning_variant_spec",
    "collect_methanol_tuning_metrics",
    "run_methanol_tuning_campaign",
    "score_methanol_tuning_metrics",
]
