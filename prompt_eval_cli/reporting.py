from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def build_summary_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[(record['prompt_name'], record['dataset_name'])].append(record)
        grouped[(record['prompt_name'], 'overall')].append(record)

    rows = []
    for (prompt_name, dataset_name), items in sorted(grouped.items()):
        total = len(items)
        parsed_total = sum(item['prediction'] != '未知' for item in items)
        correct_total = sum(bool(item['is_correct']) for item in items)
        unknown_total = total - parsed_total
        rows.append(
            {
                'prompt_name': prompt_name,
                'dataset_name': dataset_name,
                'total': total,
                'parsed_total': parsed_total,
                'unknown_total': unknown_total,
                'correct_total': correct_total,
                'error_total': sum(bool(item['error_message']) for item in items),
                'accuracy': round((correct_total / total) * 100, 2) if total else 0.0,
                'parse_rate': round((parsed_total / total) * 100, 2) if total else 0.0,
                'valid_accuracy': round((correct_total / parsed_total) * 100, 2) if parsed_total else 0.0,
                'pred_yes': sum(item['prediction'] == '是' for item in items),
                'pred_no': sum(item['prediction'] == '否' for item in items),
                'expected_yes': sum(item['ground_truth'] == '是' for item in items),
                'expected_no': sum(item['ground_truth'] == '否' for item in items),
            }
        )
    return rows


def classify_pair_case(left_correct: bool, right_correct: bool) -> str:
    if left_correct and right_correct:
        return 'both_correct'
    if (not left_correct) and (not right_correct):
        return 'both_wrong'
    if (not left_correct) and right_correct:
        return 'improved'
    return 'regressed'


def build_comparison_rows(records: list[dict[str, Any]], prompt_names: list[str]) -> list[dict[str, Any]]:
    by_sample: dict[str, dict[str, Any]] = {}
    for record in records:
        sample_id = record['sample_id']
        row = by_sample.setdefault(
            sample_id,
            {
                'sample_id': sample_id,
                'dataset_name': record['dataset_name'],
                'label': record['label'],
                'ground_truth': record['ground_truth'],
                'question': record['question'],
                'history_question': record['history_question'],
                'history_skill': record['history_skill'],
            },
        )
        prefix = record['prompt_name']
        row[f'{prefix}_prediction'] = record['prediction']
        row[f'{prefix}_correct'] = record['is_correct']
        row[f'{prefix}_latency_ms'] = record['latency_ms']
        row[f'{prefix}_error'] = record['error_message']
        row[f'{prefix}_raw_output'] = record['raw_output']

    comparison_rows = []
    for row in by_sample.values():
        predictions = [row.get(f'{prompt_name}_prediction', '') for prompt_name in prompt_names]
        row['prediction_set'] = ' | '.join(value for value in sorted(set(predictions)) if value)
        row['has_disagreement'] = len({value for value in predictions if value}) > 1
        if len(prompt_names) == 2:
            left_prompt, right_prompt = prompt_names
            left_correct = bool(row.get(f'{left_prompt}_correct'))
            right_correct = bool(row.get(f'{right_prompt}_correct'))
            row['baseline_prompt'] = left_prompt
            row['target_prompt'] = right_prompt
            row['pair_case_type'] = classify_pair_case(left_correct, right_correct)
        comparison_rows.append(row)

    comparison_rows.sort(key=lambda item: (item['dataset_name'], item['sample_id']))
    return comparison_rows


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open('w', encoding='utf-8') as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + '\n')


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text('', encoding='utf-8')
        return

    fieldnames = list(rows[0].keys())
    with path.open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
