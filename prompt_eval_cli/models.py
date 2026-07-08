from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class PromptTemplate:
    name: str
    path: str
    system: str
    user: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DatasetInfo:
    name: str
    path: str
    sample_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ExperimentMeta:
    run_id: str
    path: str
    status: str
    created_at: str
    completed_at: str = ''
    total_samples: int = 0
    total_requests: int = 0
    prompt_names: list[str] | None = None
    datasets: list[str] | None = None
    error_message: str = ''

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['prompt_names'] = self.prompt_names or []
        payload['datasets'] = self.datasets or []
        return payload


@dataclass(slots=True)
class RuntimeConfig:
    prompt_files: list[str]
    datasets: list[str]
    dataset_root: str
    output_root: str
    sample_size: int
    seed: int
    max_workers: int
    timeout: int
    temperature: float
    request_delay: float
    api_url: str
    api_key: str
    model: str

    def output_root_path(self) -> Path:
        return Path(self.output_root)

    def dataset_root_path(self) -> Path:
        return Path(self.dataset_root)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
