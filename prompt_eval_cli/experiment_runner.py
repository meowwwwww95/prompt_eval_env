from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from datetime import datetime
from pathlib import Path

from config.skill_kb import init_kb

from .catalog import load_prompt_templates
from .dataset_loader import load_samples
from .dataset_loader import normalize_dataset_choices
from .model_executor import evaluate_one
from .models import ExperimentMeta
from .models import PromptTemplate
from .models import RuntimeConfig
from .reporting import build_comparison_rows
from .reporting import build_summary_rows
from .reporting import write_csv
from .reporting import write_json
from .reporting import write_jsonl


def build_experiment_meta(
    run_id: str,
    run_dir: Path,
    config: RuntimeConfig,
    total_samples: int,
    total_requests: int,
    templates: list[PromptTemplate],
    status: str,
    created_at: str,
) -> ExperimentMeta:
    return ExperimentMeta(
        run_id=run_id,
        path=str(run_dir),
        status=status,
        created_at=created_at,
        total_samples=total_samples,
        total_requests=total_requests,
        prompt_names=[template.name for template in templates],
        datasets=list(config.datasets),
    )


def summarize_experiment_status(records: list[dict[str, object]]) -> str:
    if not records:
        return 'failed'
    success_total = sum(record['status'] == 'success' for record in records)
    if success_total == len(records):
        return 'success'
    if success_total == 0:
        return 'failed'
    return 'partial_success'


def run_experiment(config: RuntimeConfig) -> int:
    dataset_root = config.dataset_root_path()
    output_root = config.output_root_path()
    datasets = normalize_dataset_choices(config.datasets)
    templates = load_prompt_templates(config.prompt_files)
    samples = load_samples(dataset_root, datasets, config.sample_size, config.seed)
    skill_kb = init_kb()

    run_id = datetime.now().strftime('run_%Y%m%d_%H%M%S')
    created_at = datetime.now().isoformat(timespec='seconds')
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    total_tasks = len(samples) * len(templates)
    experiment_meta = build_experiment_meta(run_id, run_dir, config, len(samples), total_tasks, templates, 'running', created_at)
    write_json(run_dir / 'experiment.json', experiment_meta.to_dict())

    run_config = config.to_dict()
    run_config.update(
        {
            'run_id': run_id,
            'started_at': created_at,
            'datasets': datasets,
            'prompt_files': [template.path for template in templates],
            'total_samples': len(samples),
            'total_requests': total_tasks,
        }
    )
    write_json(run_dir / 'run_config.json', run_config)

    records: list[dict[str, object]] = []
    completed = 0

    print(f'[run] 输出目录: {run_dir}')
    print(f'[run] 样本数: {len(samples)} | prompt 版本数: {len(templates)} | 总请求数: {total_tasks}')

    try:
        with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
            futures = [
                executor.submit(evaluate_one, sample, template, config, skill_kb)
                for sample in samples
                for template in templates
            ]
            for future in as_completed(futures):
                completed += 1
                record = future.result()
                record['run_id'] = run_id
                records.append(record)
                if completed == total_tasks or completed % 10 == 0:
                    print(f'[progress] {completed}/{total_tasks}')
    except KeyboardInterrupt:
        experiment_meta.status = 'stopped'
        experiment_meta.completed_at = datetime.now().isoformat(timespec='seconds')
        experiment_meta.error_message = '用户手动终止'
        write_json(run_dir / 'experiment.json', experiment_meta.to_dict())
        raise
    except Exception as exc:
        experiment_meta.status = 'failed'
        experiment_meta.completed_at = datetime.now().isoformat(timespec='seconds')
        experiment_meta.error_message = str(exc)
        write_json(run_dir / 'experiment.json', experiment_meta.to_dict())
        raise

    typed_records = list(records)
    typed_records.sort(key=lambda item: (item['dataset_name'], item['sample_id'], item['prompt_name']))
    prompt_names = [template.name for template in templates]
    summary_rows = build_summary_rows(typed_records)
    comparison_rows = build_comparison_rows(typed_records, prompt_names)

    write_jsonl(run_dir / 'records.jsonl', typed_records)
    write_csv(run_dir / 'records.csv', typed_records)
    write_csv(run_dir / 'summary.csv', summary_rows)
    write_json(run_dir / 'summary.json', summary_rows)
    write_csv(run_dir / 'comparison.csv', comparison_rows)
    write_json(run_dir / 'comparison.json', comparison_rows)

    experiment_meta.status = summarize_experiment_status(typed_records)
    experiment_meta.completed_at = datetime.now().isoformat(timespec='seconds')
    write_json(run_dir / 'experiment.json', experiment_meta.to_dict())

    print('[done] 已生成:')
    print(f"  - {run_dir / 'experiment.json'}")
    print(f"  - {run_dir / 'summary.csv'}")
    print(f"  - {run_dir / 'summary.json'}")
    print(f"  - {run_dir / 'records.csv'}")
    print(f"  - {run_dir / 'records.jsonl'}")
    print(f"  - {run_dir / 'comparison.csv'}")
    print(f"  - {run_dir / 'comparison.json'}")

    overall_rows = [row for row in summary_rows if row['dataset_name'] == 'overall']
    for row in overall_rows:
        print(
            f"[summary] {row['prompt_name']}: accuracy={row['accuracy']}% "
            f"parse_rate={row['parse_rate']}% valid_accuracy={row['valid_accuracy']}%"
        )

    return 0
