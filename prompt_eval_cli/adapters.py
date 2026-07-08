from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Callable
from typing import TypeVar

from config.skill_kb import SkillKB

from .context_builder import render_messages as default_render_messages
from .dataset_loader import load_samples as default_load_samples
from .dataset_loader import normalize_dataset_choices as default_normalize_dataset_choices
from .models import PromptTemplate
from .output_parser import parse_judgment as default_parse_judgment
from .output_parser import parse_status_from_result as default_parse_status_from_result

DatasetNormalizeFunc = Callable[[list[str]], list[str]]
DatasetLoadFunc = Callable[[Path, list[str], int, int], list[dict[str, Any]]]
ContextRenderFunc = Callable[[PromptTemplate, dict[str, Any], SkillKB], list[dict[str, str]]]
OutputParseFunc = Callable[[str], tuple[str, str]]
ParseStatusFunc = Callable[[str, str, str], str]
AdapterT = TypeVar('AdapterT')


@dataclass(frozen=True, slots=True)
class DatasetAdapter:
    name: str
    normalize_dataset_choices: DatasetNormalizeFunc
    load_samples: DatasetLoadFunc


@dataclass(frozen=True, slots=True)
class ContextAdapter:
    name: str
    render_messages: ContextRenderFunc


@dataclass(frozen=True, slots=True)
class OutputParserAdapter:
    name: str
    parse_judgment: OutputParseFunc
    parse_status: ParseStatusFunc


DATASET_ADAPTERS: dict[str, DatasetAdapter] = {
    'default': DatasetAdapter(
        name='default',
        normalize_dataset_choices=default_normalize_dataset_choices,
        load_samples=default_load_samples,
    )
}
CONTEXT_ADAPTERS: dict[str, ContextAdapter] = {
    'default': ContextAdapter(name='default', render_messages=default_render_messages)
}
OUTPUT_PARSER_ADAPTERS: dict[str, OutputParserAdapter] = {
    'default': OutputParserAdapter(
        name='default',
        parse_judgment=default_parse_judgment,
        parse_status=default_parse_status_from_result,
    )
}


def register_dataset_adapter(adapter: DatasetAdapter) -> None:
    DATASET_ADAPTERS[adapter.name] = adapter


def register_context_adapter(adapter: ContextAdapter) -> None:
    CONTEXT_ADAPTERS[adapter.name] = adapter


def register_output_parser_adapter(adapter: OutputParserAdapter) -> None:
    OUTPUT_PARSER_ADAPTERS[adapter.name] = adapter


def _resolve_adapter_name(name: str | None) -> str:
    return (name or 'default').strip() or 'default'


def _get_adapter(registry: dict[str, AdapterT], name: str | None, field_name: str) -> AdapterT:
    resolved_name = _resolve_adapter_name(name)
    adapter = registry.get(resolved_name)
    if adapter is None:
        available_names = ', '.join(sorted(registry))
        raise ValueError(f'未知的 {field_name}: {resolved_name}，可选值: {available_names}')
    return adapter


def get_dataset_adapter(name: str | None) -> DatasetAdapter:
    return _get_adapter(DATASET_ADAPTERS, name, 'dataset_adapter')


def get_context_adapter(name: str | None) -> ContextAdapter:
    return _get_adapter(CONTEXT_ADAPTERS, name, 'context_adapter')


def get_output_parser_adapter(name: str | None) -> OutputParserAdapter:
    return _get_adapter(OUTPUT_PARSER_ADAPTERS, name, 'output_parser')
