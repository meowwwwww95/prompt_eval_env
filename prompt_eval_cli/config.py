from __future__ import annotations

import os
import re
from argparse import Namespace
from pathlib import Path
from typing import Any

import yaml

from .models import RuntimeConfig


CONFIG_FILE_PATH = Path('config') / 'prompt_eval.yaml'
ENV_VAR_RE = re.compile(r'\$\{([A-Za-z_]\w*)\}')


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def expand_env_placeholders(value: Any) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            return os.getenv(match.group(1), '')

        return ENV_VAR_RE.sub(replace, value)

    if isinstance(value, list):
        return [expand_env_placeholders(item) for item in value]

    if isinstance(value, dict):
        return {key: expand_env_placeholders(item) for key, item in value.items()}

    return value


def load_yaml_config(config_path: Path = CONFIG_FILE_PATH) -> dict[str, Any]:
    if not config_path.exists():
        return {}

    with config_path.open('r', encoding='utf-8') as file:
        payload = yaml.safe_load(file) or {}

    if not isinstance(payload, dict):
        raise ValueError(f'配置文件格式错误，根节点必须是对象: {config_path}')

    return expand_env_placeholders(payload)


def _resolve_value(args: Namespace, arg_name: str, yaml_config: dict[str, Any], config_key: str) -> Any:
    cli_value = getattr(args, arg_name, None)
    if cli_value is not None:
        return cli_value
    return yaml_config.get(config_key)


def build_runtime_config(args: Namespace, yaml_config: dict[str, Any]) -> RuntimeConfig:
    config = RuntimeConfig(
        prompt_files=list(_resolve_value(args, 'prompts', yaml_config, 'prompt_files') or []),
        datasets=list(_resolve_value(args, 'dataset', yaml_config, 'datasets') or []),
        dataset_root=str(_resolve_value(args, 'dataset_root', yaml_config, 'dataset_root') or ''),
        output_root=str(_resolve_value(args, 'output_root', yaml_config, 'output_root') or ''),
        sample_size=int(_resolve_value(args, 'sample_size', yaml_config, 'sample_size') or 0),
        seed=int(_resolve_value(args, 'seed', yaml_config, 'seed') or 0),
        max_workers=int(_resolve_value(args, 'max_workers', yaml_config, 'max_workers') or 0),
        timeout=int(_resolve_value(args, 'timeout', yaml_config, 'timeout') or 0),
        temperature=float(_resolve_value(args, 'temperature', yaml_config, 'temperature') or 0),
        request_delay=float(_resolve_value(args, 'request_delay', yaml_config, 'request_delay') or 0),
        api_url=str(_resolve_value(args, 'api_url', yaml_config, 'api_url') or ''),
        api_key=str(_resolve_value(args, 'api_key', yaml_config, 'api_key') or ''),
        model=str(_resolve_value(args, 'model', yaml_config, 'model') or ''),
        dataset_adapter=str(_resolve_value(args, 'dataset_adapter', yaml_config, 'dataset_adapter') or 'default'),
        context_adapter=str(_resolve_value(args, 'context_adapter', yaml_config, 'context_adapter') or 'default'),
        output_parser=str(_resolve_value(args, 'output_parser', yaml_config, 'output_parser') or 'default'),
    )
    validate_runtime_config(config)
    return config


def validate_runtime_config(config: RuntimeConfig) -> None:
    missing_fields = []
    if not config.prompt_files:
        missing_fields.append('prompt_files / --prompt')
    if not config.datasets:
        missing_fields.append('datasets / --dataset')
    if not config.dataset_root:
        missing_fields.append('dataset_root / --dataset-root')
    if not config.output_root:
        missing_fields.append('output_root / --output-root')
    if not config.api_url:
        missing_fields.append('api_url / --api-url')
    if not config.api_key:
        missing_fields.append('api_key / --api-key')
    if not config.model:
        missing_fields.append('model / --model')

    if missing_fields:
        missing_text = '\n'.join(f'- {item}' for item in missing_fields)
        raise ValueError(f'缺少运行配置:\n{missing_text}')

    if config.max_workers < 1:
        raise ValueError('--max-workers 必须大于等于 1')
    if config.sample_size < 0:
        raise ValueError('--sample-size 不能小于 0')
    if config.timeout <= 0:
        raise ValueError('--timeout 必须大于 0')


def resolve_dataset_root(explicit_value: str | None, yaml_config: dict[str, Any]) -> Path:
    return Path(explicit_value or yaml_config.get('dataset_root') or 'dataset')


def resolve_output_root(explicit_value: str | None, yaml_config: dict[str, Any]) -> Path:
    return Path(explicit_value or yaml_config.get('output_root') or 'outputs')


def resolve_prompt_dir(explicit_value: str | None, yaml_config: dict[str, Any]) -> Path:
    if explicit_value:
        return Path(explicit_value)

    prompt_files = yaml_config.get('prompt_files') or []
    if prompt_files:
        return Path(prompt_files[0]).parent
    return Path('prompts')
