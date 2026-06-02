from __future__ import annotations

import enum
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from .schema import PlantSpecification


def to_plain_data(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return to_plain_data(value.model_dump(mode="json"))

    if isinstance(value, enum.Enum):
        return to_plain_data(value.value)

    if isinstance(value, Mapping):
        return {to_plain_data(key): to_plain_data(item) for key, item in value.items()}

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [to_plain_data(item) for item in value]

    return value


def spec_to_plain_dict(spec: PlantSpecification | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(spec, PlantSpecification):
        plain = to_plain_data(spec)
    elif isinstance(spec, Mapping):
        plain = to_plain_data(dict(spec))
    else:
        raise TypeError(f"spec must be PlantSpecification or mapping; got {type(spec).__name__}")

    if not isinstance(plain, dict):
        raise TypeError(f"serialized spec must be a dict; got {type(plain).__name__}")

    return plain


__all__ = ["spec_to_plain_dict", "to_plain_data"]
