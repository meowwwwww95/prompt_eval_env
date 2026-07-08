from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .models import DatasetInfo
from .models import ExperimentMeta
from .models import PromptTemplate


DEFAULT_USER_TEMPLATE = """任务：判断“当前问句”是否可以复用“历史技能”。

判断原则：
1. 如果当前问句和历史问句属于同一任务，只是股票名称、数值、措辞变化，输出“是”。
2. 如果当前问句的目标、分析维度、任务类型发生变化，输出“否”。

当前问句：{question}
历史问句：{history_question}
历史技能：{history_skill}

请严格按以下格式输出：
结论：是/否
理由：不超过50字
"""
SECTION_MARKER_RE = re.compile(r'^===\s*(SYSTEM|USER)\s*===\s*$', re.IGNORECASE | re.MULTILINE)
PLACEHOLDER_RE = re.compile(r'\{\{\s*([A-Za-z_]\w*)\s*\}\}|\{\s*([A-Za-z_]\w*)\s*\}')


def parse_prompt_sections(text: str) -> tuple[str, str]:
    matches = list(SECTION_MARKER_RE.finditer(text))
    if not matches:
        return '', text.strip()

    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        name = match.group(1).upper()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[name] = text[start:end].strip()

    system_text = sections.get('SYSTEM', '')
    user_text = sections.get('USER', '') or DEFAULT_USER_TEMPLATE
    return system_text, user_text


def extract_template_variables(text: str) -> list[str]:
    found = []
    for match in PLACEHOLDER_RE.finditer(text):
        key = match.group(1) or match.group(2)
        if key and key not in found:
            found.append(key)
    return found


def load_prompt_templates(prompt_paths: list[str]) -> list[PromptTemplate]:
    templates: list[PromptTemplate] = []
    seen_names: set[str] = set()

    for raw_path in prompt_paths:
        path = Path(raw_path)
        if not path.exists():
            raise FileNotFoundError(f'prompt 文件不存在: {path}')

        system_text, user_text = parse_prompt_sections(path.read_text(encoding='utf-8'))
        prompt_name = path.stem
        if prompt_name in seen_names:
            raise ValueError(f'prompt 名称重复，请使用不同文件名: {prompt_name}')
        seen_names.add(prompt_name)
        templates.append(
            PromptTemplate(
                name=prompt_name,
                path=str(path),
                system=system_text,
                user=user_text,
            )
        )

    return templates


def list_prompt_infos(prompt_dir: Path) -> list[dict[str, Any]]:
    if not prompt_dir.exists():
        raise FileNotFoundError(f'prompt 目录不存在: {prompt_dir}')

    rows = []
    for path in sorted(item for item in prompt_dir.iterdir() if item.is_file()):
        text = path.read_text(encoding='utf-8')
        system_text, user_text = parse_prompt_sections(text)
        variables = extract_template_variables(text)
        rows.append(
            {
                'name': path.stem,
                'path': str(path),
                'has_system_section': bool(system_text),
                'has_user_section': '===USER===' in text.upper(),
                'variable_count': len(variables),
                'variables': variables,
                'line_count': len(text.splitlines()),
                'char_count': len(text),
                'user_preview': user_text.splitlines()[0] if user_text else '',
            }
        )
    return rows


def list_dataset_infos(dataset_root: Path) -> list[DatasetInfo]:
    if not dataset_root.exists():
        raise FileNotFoundError(f'数据集目录不存在: {dataset_root}')

    items: list[DatasetInfo] = []
    for path in sorted(item for item in dataset_root.iterdir() if item.is_dir()):
        sample_count = sum(1 for file_path in path.glob('*.json'))
        items.append(DatasetInfo(name=path.name, path=str(path), sample_count=sample_count))
    return items


def read_dataset_index(dataset_root: Path) -> dict[str, Any]:
    index_path = dataset_root / 'index.json'
    if not index_path.exists():
        return {}
    return json.loads(index_path.read_text(encoding='utf-8'))


def list_experiments(output_root: Path) -> list[ExperimentMeta]:
    if not output_root.exists():
        return []

    items: list[ExperimentMeta] = []
    run_dirs = sorted(
        (item for item in output_root.iterdir() if item.is_dir()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for run_dir in run_dirs:
        experiment_path = run_dir / 'experiment.json'
        if experiment_path.exists():
            payload = json.loads(experiment_path.read_text(encoding='utf-8'))
            items.append(
                ExperimentMeta(
                    run_id=payload.get('run_id', run_dir.name),
                    path=str(run_dir),
                    status=payload.get('status', 'unknown'),
                    created_at=payload.get('created_at', ''),
                    completed_at=payload.get('completed_at', ''),
                    total_samples=int(payload.get('total_samples', 0) or 0),
                    total_requests=int(payload.get('total_requests', 0) or 0),
                    prompt_names=list(payload.get('prompt_names') or []),
                    datasets=list(payload.get('datasets') or []),
                    error_message=payload.get('error_message', ''),
                )
            )
            continue

        config_path = run_dir / 'run_config.json'
        if not config_path.exists():
            continue
        payload = json.loads(config_path.read_text(encoding='utf-8'))
        items.append(
            ExperimentMeta(
                run_id=payload.get('run_id', run_dir.name),
                path=str(run_dir),
                status='success' if (run_dir / 'summary.json').exists() else 'unknown',
                created_at=payload.get('started_at', ''),
                completed_at=payload.get('completed_at', ''),
                total_samples=int(payload.get('total_samples', 0) or 0),
                total_requests=int(payload.get('total_requests', 0) or 0),
                prompt_names=[Path(item).stem for item in payload.get('prompt_files', [])],
                datasets=list(payload.get('datasets') or []),
            )
        )
    return items
