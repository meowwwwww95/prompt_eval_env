from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any


def normalize_dataset_choices(raw_choices: list[str]) -> list[str]:
    normalized = []
    for item in raw_choices:
        value = item.strip().lower()
        if value not in {'green', 'yellow', 'red', 'all'}:
            raise ValueError(f'不支持的数据集类型: {item}')
        normalized.append(value)

    if 'all' in normalized:
        return ['green', 'yellow', 'red']

    deduped = []
    for item in normalized:
        if item not in deduped:
            deduped.append(item)
    return deduped


def expected_judgment_from_label(label: str) -> str:
    return '是' if label == 'green' else '否'


def load_samples(dataset_root: Path, datasets: list[str], sample_size: int, seed: int) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    for dataset_name in datasets:
        dataset_dir = dataset_root / dataset_name
        if not dataset_dir.exists():
            raise FileNotFoundError(f'数据集目录不存在: {dataset_dir}')

        for file_path in sorted(dataset_dir.glob('*.json')):
            with file_path.open('r', encoding='utf-8') as file:
                row = json.load(file)

            row['dataset_name'] = dataset_name
            row['label'] = row.get('label', dataset_name)
            row['expected_judgment'] = expected_judgment_from_label(row['label'])
            row['sample_id'] = row.get('qId') or file_path.stem
            row['source_file'] = str(file_path)
            samples.append(row)

    if not samples:
        raise ValueError('未找到任何样本，请检查数据集路径和数据集选择')

    if sample_size and sample_size > 0 and sample_size < len(samples):
        rng = random.Random(seed)
        samples = rng.sample(samples, sample_size)

    samples.sort(key=lambda item: (item['dataset_name'], item['sample_id']))
    return samples
