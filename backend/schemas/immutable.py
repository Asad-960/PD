"""Immutable mappings with ordinary JSON/Pydantic serialization boundaries."""
import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any
from pydantic import BaseModel


class ImmutableMap(Mapping):
    __slots__ = ("_data",)

    def __init__(self, values):
        object.__setattr__(self, "_data", MappingProxyType(dict(values)))

    def __setattr__(self, name, value):
        raise TypeError("Immutable mappings cannot be changed")

    def __delattr__(self, name):
        raise TypeError("Immutable mappings cannot be changed")

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __deepcopy__(self, memo):
        return self


def freeze(value: Any, depth=0):
    if depth > 32:
        raise ValueError("Metadata nesting exceeds 32 levels")
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("JSON mapping keys must be strings")
        return ImmutableMap({key: freeze(item, depth + 1) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item, depth + 1) for item in value)
    if isinstance(value, BaseModel) and value.model_config.get("frozen"):
        return value
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ValueError("Metadata must contain finite JSON values")


def thaw(value: Any):
    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [thaw(item) for item in value]
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def freeze_json(value, max_nodes=1024, max_string_length=4096):
    """Metadata cannot smuggle Python models into a JSON field."""
    nodes = 0
    def reject_models(item, depth=0):
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes:
            raise ValueError(f"Metadata exceeds {max_nodes} values")
        if depth > 32 or isinstance(item, BaseModel):
            raise ValueError("Metadata requires bounded JSON values")
        if isinstance(item, str) and len(item) > max_string_length:
            raise ValueError(f"Metadata strings exceed {max_string_length} characters")
        if isinstance(item, Mapping):
            for key, child in item.items():
                if not isinstance(key, str) or len(key) > 4096:
                    raise ValueError("Metadata requires bounded string keys")
                reject_models(child, depth + 1)
        elif isinstance(item, (tuple, list)):
            for child in item:
                reject_models(child, depth + 1)
    reject_models(value)
    return freeze(value)
