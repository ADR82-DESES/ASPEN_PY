from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
import enum

class UnitSystem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pressure: str = Field(..., description="Pressure units (e.g., bar, psi, atm, kPa, MPa)")
    temperature: str = Field(..., description="Temperature units (e.g., C, F, K, R)")
    flow: str = Field(..., description="Flow units (e.g., kg/hr, kmol/hr, lb/hr, lbmol/hr)")

class Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    description: Optional[str] = None
    units: UnitSystem

class Component(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    formula: Optional[str] = None

class Properties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: str
    databanks: Optional[List[str]] = None

class FlowsheetConnection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    block: str
    inputs: List[str]
    outputs: List[str]

class Stream(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    temperature: float
    pressure: float
    mass_flow: Optional[float] = None
    mole_flow: Optional[float] = None
    composition: Dict[str, float]

    @model_validator(mode='after')
    def check_flow_provided(self) -> 'Stream':
        if self.mass_flow is None and self.mole_flow is None:
            raise ValueError("Either mass_flow or mole_flow must be provided for stream")
        return self

    @field_validator('composition')
    @classmethod
    def validate_composition_sum(cls, v: Dict[str, float]) -> Dict[str, float]:
        total = sum(v.values())
        if not (0.999 <= total <= 1.001):
            raise ValueError(f"Composition sum is {total}, expected 1.0 (±0.001)")
        return v

class Block(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: str
    parameters: Optional[Dict[str, Union[float, str]]] = None
    reactions: Optional[str] = None
    split_fractions: Optional[List["SplitFraction"]] = None
    sep_fractions: Optional[List["SepFraction"]] = None

class ChemistryStoichiometry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    component: str
    coefficient: float

class Reaction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    stoichiometry: List[ChemistryStoichiometry]

class Chemistry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    reactions: List[Reaction]

class ReactionSet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    block_type: str
    reaction_ids: List[int]

class SplitFraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stream: str
    fraction: float

class SepFraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stream: str
    substream: str = "MIXED"
    component: str
    fraction: float

class PurityTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expression: str
    min_value: float

class Targets(BaseModel):
    model_config = ConfigDict(extra="forbid")
    production_rate_tpd: float
    tolerance: float = 0.01
    purity: Optional[PurityTarget] = None

class FlowsheetingOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mass_balance: bool = Field(default=True, description="Enable mass balance calculation")
    energy_balance: bool = Field(default=True, description="Enable energy balance calculation")


class PlantSpecification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metadata: Metadata
    components: List[Component]
    properties: Properties

    flowsheeting_options: Optional[FlowsheetingOptions] = None
    flowsheet: List[FlowsheetConnection]
    streams: List[Stream]
    blocks: List[Block]
    chemistry: Optional[List[Chemistry]] = None
    reaction_sets: Optional[List[ReactionSet]] = None
    targets: Optional[Targets] = None

Block.model_rebuild()
PlantSpecification.model_rebuild()
