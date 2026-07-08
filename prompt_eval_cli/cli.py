from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .catalog import list_dataset_infos
from .catalog import list_experiments
from .catalog import list_prompt_infos
from .catalog import read_dataset_index
from .config import CONFIG_FILE_PATH
from .config import build_runtime_config
from .config import load_env_file
from .config import load_yaml_config
from .config import resolve_dataset_root
from .config import resolve_output_root
from .config import resolve_prompt_dir
from .experiment_runner import run_experiment

CASE_TYPES = {'all', 'both_correct', 'both_wrong', 'improved', 'regressed'}
INTERACTIVE_MENU_OPTIONS = {
    '1': '查看数据集',
    '2': '查看 Prompt 列表',
    '3': '运行实验',
    '4': '查看实验列表',
    '5': '查看单个实验详情',
    '6': '比较同一实验中的两个 Prompt',
    '0': '退出',
}


class ReturnToMenu(Exception):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='提示词对比评估命令行工具')
    parser.add_argument('--interactive', action='store_true', help='启动交互式菜单')
    subparsers = parser.add_subparsers(dest='command')

    run_parser = subparsers.add_parser('run', help='批量运行多个 prompt 版本并导出结果')
    run_parser.add_argument('--prompt', dest='prompts', nargs='+', help='一个或多个 prompt 文件路径')
    run_parser.add_argument('--dataset', nargs='+', help='要跑的数据集，可选: green yellow red all')
    run_parser.add_argument('--dataset-root', help='数据集根目录')
    run_parser.add_argument('--sample-size', type=int, help='抽样数量，0 表示全量')
    run_parser.add_argument('--seed', type=int, help='抽样随机种子')
    run_parser.add_argument('--max-workers', type=int, help='并发请求数')
    run_parser.add_argument('--timeout', type=int, help='单次请求超时秒数')
    run_parser.add_argument('--temperature', type=float, help='模型温度')
    run_parser.add_argument('--api-url', help='接口地址')
    run_parser.add_argument('--api-key', help='接口密钥')
    run_parser.add_argument('--model', help='模型名称')
    run_parser.add_argument('--output-root', help='输出目录根路径')
    run_parser.add_argument('--request-delay', type=float, help='每次请求前的延迟秒数，用于限流')

    datasets_parser = subparsers.add_parser('datasets', help='查看本地数据集信息')
    datasets_subparsers = datasets_parser.add_subparsers(dest='datasets_command', required=True)
    datasets_list_parser = datasets_subparsers.add_parser('list', help='列出可用数据集')
    datasets_list_parser.add_argument('--dataset-root', help='数据集根目录')
    datasets_list_parser.add_argument('--json', action='store_true', help='以 JSON 输出')

    prompts_parser = subparsers.add_parser('prompts', help='查看本地 prompt 信息')
    prompts_subparsers = prompts_parser.add_subparsers(dest='prompts_command', required=True)
    prompts_list_parser = prompts_subparsers.add_parser('list', help='列出 prompt 模板')
    prompts_list_parser.add_argument('--prompt-dir', help='prompt 目录')
    prompts_list_parser.add_argument('--json', action='store_true', help='以 JSON 输出')

    experiments_parser = subparsers.add_parser('experiments', help='查看本地实验结果')
    experiments_subparsers = experiments_parser.add_subparsers(dest='experiments_command', required=True)
    experiments_list_parser = experiments_subparsers.add_parser('list', help='列出本地实验')
    experiments_list_parser.add_argument('--output-root', help='实验输出目录')
    experiments_list_parser.add_argument('--json', action='store_true', help='以 JSON 输出')

    experiments_show_parser = experiments_subparsers.add_parser('show', help='查看单个实验详情')
    experiments_show_parser.add_argument('run_id', help='实验 ID，例如 run_20260707_120000')
    experiments_show_parser.add_argument('--output-root', help='实验输出目录')
    experiments_show_parser.add_argument('--json', action='store_true', help='以 JSON 输出')

    experiments_compare_parser = experiments_subparsers.add_parser('compare', help='查看同一实验内两个 prompt 的差异 case')
    experiments_compare_parser.add_argument('run_id', help='实验 ID，例如 run_20260707_120000')
    experiments_compare_parser.add_argument('--baseline', required=True, help='基线 prompt 名称')
    experiments_compare_parser.add_argument('--target', required=True, help='目标 prompt 名称')
    experiments_compare_parser.add_argument(
        '--case-type',
        default='all',
        choices=sorted(CASE_TYPES),
        help='筛选 case 类型，默认 all',
    )
    experiments_compare_parser.add_argument('--dataset', nargs='+', help='按数据集筛选，例如 green yellow')
    experiments_compare_parser.add_argument('--limit', type=int, default=20, help='最多显示多少条 case，默认 20')
    experiments_compare_parser.add_argument('--output-root', help='实验输出目录')
    experiments_compare_parser.add_argument('--json', action='store_true', help='以 JSON 输出')

    return parser.parse_args()


def print_rows_as_table(rows: list[dict[str, Any]], columns: list[str]) -> None:
    if not rows:
        print('[]')
        return

    widths = {column: len(column) for column in columns}
    for row in rows:
        for column in columns:
            widths[column] = max(widths[column], len(str(row.get(column, ''))))

    header = ' | '.join(column.ljust(widths[column]) for column in columns)
    divider = '-+-'.join('-' * widths[column] for column in columns)
    print(header)
    print(divider)
    for row in rows:
        print(' | '.join(str(row.get(column, '')).ljust(widths[column]) for column in columns))


def handle_run(args: argparse.Namespace, yaml_config: dict[str, Any]) -> int:
    config = build_runtime_config(args, yaml_config)
    return run_experiment(config)


def handle_datasets_list(args: argparse.Namespace, yaml_config: dict[str, Any]) -> int:
    dataset_root = resolve_dataset_root(args.dataset_root, yaml_config)
    dataset_infos = [item.to_dict() for item in list_dataset_infos(dataset_root)]
    index_payload = read_dataset_index(dataset_root)

    if args.json:
        print(json.dumps({'dataset_root': str(dataset_root), 'datasets': dataset_infos, 'index': index_payload}, ensure_ascii=False, indent=2))
        return 0

    print(f'[datasets] root={dataset_root}')
    if index_payload:
        print(f"[datasets] labeled_total={index_payload.get('labeled_total', 0)} total_rows={index_payload.get('total_rows', 0)}")
    print_rows_as_table(dataset_infos, ['name', 'sample_count', 'path'])
    return 0


def handle_prompts_list(args: argparse.Namespace, yaml_config: dict[str, Any]) -> int:
    prompt_dir = resolve_prompt_dir(args.prompt_dir, yaml_config)
    rows = list_prompt_infos(prompt_dir)

    if args.json:
        print(json.dumps({'prompt_dir': str(prompt_dir), 'prompts': rows}, ensure_ascii=False, indent=2))
        return 0

    print(f'[prompts] dir={prompt_dir}')
    display_rows = []
    for row in rows:
        display_rows.append(
            {
                'name': row['name'],
                'variable_count': row['variable_count'],
                'line_count': row['line_count'],
                'path': row['path'],
            }
        )
    print_rows_as_table(display_rows, ['name', 'variable_count', 'line_count', 'path'])
    return 0


def handle_experiments_list(args: argparse.Namespace, yaml_config: dict[str, Any]) -> int:
    output_root = resolve_output_root(args.output_root, yaml_config)
    rows = [item.to_dict() for item in list_experiments(output_root)]

    if args.json:
        print(json.dumps({'output_root': str(output_root), 'experiments': rows}, ensure_ascii=False, indent=2))
        return 0

    print(f'[experiments] root={output_root}')
    print_rows_as_table(rows, ['run_id', 'status', 'created_at', 'completed_at', 'total_samples', 'total_requests'])
    return 0


def handle_experiments_show(args: argparse.Namespace, yaml_config: dict[str, Any]) -> int:
    output_root = resolve_output_root(args.output_root, yaml_config)
    run_dir = output_root / args.run_id
    if not run_dir.exists():
        raise FileNotFoundError(f'实验目录不存在: {run_dir}')

    experiment_payload = {}
    experiment_path = run_dir / 'experiment.json'
    if experiment_path.exists():
        experiment_payload = json.loads(experiment_path.read_text(encoding='utf-8'))

    run_config = {}
    run_config_path = run_dir / 'run_config.json'
    if run_config_path.exists():
        run_config = json.loads(run_config_path.read_text(encoding='utf-8'))

    summary_rows = []
    summary_path = run_dir / 'summary.json'
    if summary_path.exists():
        summary_rows = json.loads(summary_path.read_text(encoding='utf-8'))

    comparison_path = run_dir / 'comparison.json'
    payload = {
        'experiment': experiment_payload,
        'run_config': run_config,
        'summary': summary_rows,
        'files': {
            'records_jsonl': str(run_dir / 'records.jsonl'),
            'records_csv': str(run_dir / 'records.csv'),
            'summary_json': str(summary_path),
            'summary_csv': str(run_dir / 'summary.csv'),
            'comparison_json': str(comparison_path),
            'comparison_csv': str(run_dir / 'comparison.csv'),
        },
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(json.dumps(payload['experiment'], ensure_ascii=False, indent=2))
    if summary_rows:
        print('[summary]')
        print_rows_as_table(summary_rows, ['prompt_name', 'dataset_name', 'accuracy', 'parse_rate', 'valid_accuracy', 'correct_total', 'error_total'])
    return 0


def get_prompt_prediction(row: dict[str, Any], prompt_name: str) -> Any:
    for key in [f'{prompt_name}_prediction', f'{prompt_name}_parsed']:
        if key in row:
            return row.get(key)
    return None


def get_prompt_correct(row: dict[str, Any], prompt_name: str) -> Any:
    key = f'{prompt_name}_correct'
    if key in row:
        return row.get(key)
    return None


def classify_case_type(baseline_correct: bool, target_correct: bool) -> str:
    if baseline_correct and target_correct:
        return 'both_correct'
    if (not baseline_correct) and (not target_correct):
        return 'both_wrong'
    if (not baseline_correct) and target_correct:
        return 'improved'
    return 'regressed'


def build_compare_case(row: dict[str, Any], baseline: str, target: str) -> dict[str, Any]:
    baseline_prediction = get_prompt_prediction(row, baseline)
    target_prediction = get_prompt_prediction(row, target)
    baseline_correct = get_prompt_correct(row, baseline)
    target_correct = get_prompt_correct(row, target)

    if baseline_prediction is None:
        raise ValueError(f'实验结果中找不到 baseline prompt 字段: {baseline}')
    if target_prediction is None:
        raise ValueError(f'实验结果中找不到 target prompt 字段: {target}')
    if baseline_correct is None:
        raise ValueError(f'实验结果中找不到 baseline 正确性字段: {baseline}')
    if target_correct is None:
        raise ValueError(f'实验结果中找不到 target 正确性字段: {target}')

    case_type = classify_case_type(bool(baseline_correct), bool(target_correct))
    return {
        'sample_id': row.get('sample_id', ''),
        'dataset_name': row.get('dataset_name', ''),
        'ground_truth': row.get('ground_truth', row.get('expected_judgment', '')),
        'case_type': case_type,
        'baseline_prompt': baseline,
        'target_prompt': target,
        'baseline_prediction': baseline_prediction,
        'target_prediction': target_prediction,
        'baseline_correct': bool(baseline_correct),
        'target_correct': bool(target_correct),
        'history_question': row.get('history_question', ''),
        'history_skill': row.get('history_skill', ''),
        'question': row.get('question', ''),
    }


def handle_experiments_compare(args: argparse.Namespace, yaml_config: dict[str, Any]) -> int:
    output_root = resolve_output_root(args.output_root, yaml_config)
    run_dir = output_root / args.run_id
    if not run_dir.exists():
        raise FileNotFoundError(f'实验目录不存在: {run_dir}')

    comparison_path = run_dir / 'comparison.json'
    if not comparison_path.exists():
        raise FileNotFoundError(f'实验对比结果不存在: {comparison_path}')

    comparison_rows = json.loads(comparison_path.read_text(encoding='utf-8'))
    if not isinstance(comparison_rows, list):
        raise ValueError(f'对比结果格式错误: {comparison_path}')

    dataset_filter = None
    if args.dataset:
        dataset_filter = {item.strip().lower() for item in args.dataset}

    all_cases = []
    for row in comparison_rows:
        case_row = build_compare_case(row, args.baseline, args.target)
        dataset_name = str(case_row['dataset_name']).lower()
        if dataset_filter and dataset_name not in dataset_filter:
            continue
        all_cases.append(case_row)

    counts = {case_type: 0 for case_type in sorted(CASE_TYPES - {'all'})}
    for case_row in all_cases:
        counts[case_row['case_type']] += 1

    filtered_cases = all_cases
    if args.case_type != 'all':
        filtered_cases = [case_row for case_row in all_cases if case_row['case_type'] == args.case_type]

    limited_cases = filtered_cases[: max(args.limit, 0)]
    payload = {
        'run_id': args.run_id,
        'baseline': args.baseline,
        'target': args.target,
        'dataset_filter': sorted(dataset_filter) if dataset_filter else [],
        'case_type': args.case_type,
        'total_cases': len(all_cases),
        'matched_cases': len(filtered_cases),
        'counts': counts,
        'cases': limited_cases,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(
        f"[compare] run={args.run_id} baseline={args.baseline} "
        f"target={args.target} dataset={','.join(sorted(dataset_filter)) if dataset_filter else 'all'}"
    )
    print(
        f"[compare] total={len(all_cases)} matched={len(filtered_cases)} "
        f"both_correct={counts['both_correct']} both_wrong={counts['both_wrong']} "
        f"improved={counts['improved']} regressed={counts['regressed']}"
    )
    print_rows_as_table(
        limited_cases,
        [
            'sample_id',
            'dataset_name',
            'case_type',
            'ground_truth',
            'baseline_prediction',
            'target_prediction',
            'baseline_correct',
            'target_correct',
            'question',
        ],
    )
    return 0


def clear_screen() -> None:
    os.system('cls' if os.name == 'nt' else 'clear')


def print_task_header(title: str) -> None:
    clear_screen()
    print(f'=== {title} ===')
    print('[提示] 输入 /back 可随时返回主菜单。')
    print()


def wait_for_menu_return() -> None:
    input('\n按回车返回主菜单...')


def prompt_text(message: str, default: str | None = None, allow_back: bool = False) -> str:
    suffix = f' [{default}]' if default not in (None, '') else ''
    value = input(f'{message}{suffix}: ').strip()
    if allow_back and value.lower() in {'/back', '/menu', ':q'}:
        raise ReturnToMenu()
    if not value and default is not None:
        return default
    return value


def prompt_optional_int(message: str, default: int | None = None) -> int | None:
    while True:
        raw = prompt_text(message, '' if default is None else str(default), allow_back=True)
        if raw == '':
            return None
        try:
            return int(raw)
        except ValueError:
            print('请输入整数，或直接回车使用默认值。')


def prompt_optional_float(message: str, default: float | None = None) -> float | None:
    while True:
        raw = prompt_text(message, '' if default is None else str(default), allow_back=True)
        if raw == '':
            return None
        try:
            return float(raw)
        except ValueError:
            print('请输入数字，或直接回车使用默认值。')


def parse_multi_values(raw: str) -> list[str]:
    return [item for item in raw.replace(',', ' ').split() if item]


def print_interactive_menu() -> None:
    print('\n=== Prompt Eval CLI ===')
    for key, label in INTERACTIVE_MENU_OPTIONS.items():
        print(f'{key}. {label}')


def select_run_id(output_root: Path) -> str:
    experiments = list_experiments(output_root)
    if not experiments:
        raise ValueError(f'当前没有实验记录: {output_root}')

    rows = []
    for index, item in enumerate(experiments, start=1):
        rows.append(
            {
                'index': index,
                'run_id': item.run_id,
                'status': item.status,
                'created_at': item.created_at,
            }
        )
    print_rows_as_table(rows, ['index', 'run_id', 'status', 'created_at'])

    while True:
        raw = prompt_text('请输入实验编号或 run_id', allow_back=True)
        if raw.isdigit():
            index = int(raw)
            if 1 <= index <= len(experiments):
                return experiments[index - 1].run_id
        matched = [item.run_id for item in experiments if item.run_id == raw]
        if matched:
            return matched[0]
        print('输入无效，请重新输入。')


def load_run_prompt_names(output_root: Path, run_id: str) -> list[str]:
    run_dir = output_root / run_id
    experiment_path = run_dir / 'experiment.json'
    if experiment_path.exists():
        payload = json.loads(experiment_path.read_text(encoding='utf-8'))
        prompt_names = list(payload.get('prompt_names') or [])
        if prompt_names:
            return prompt_names

    run_config_path = run_dir / 'run_config.json'
    if run_config_path.exists():
        payload = json.loads(run_config_path.read_text(encoding='utf-8'))
        return [Path(item).stem for item in payload.get('prompt_files', [])]

    return []


def select_prompt_name(prompt_names: list[str], message: str, excluded: set[str] | None = None) -> str:
    excluded = excluded or set()
    available_names = [name for name in prompt_names if name not in excluded]
    if not available_names:
        raise ValueError('没有可选的 Prompt。')

    rows = [{'index': index, 'prompt_name': name} for index, name in enumerate(available_names, start=1)]
    print_rows_as_table(rows, ['index', 'prompt_name'])

    while True:
        raw = prompt_text(message, allow_back=True)
        if raw.isdigit():
            index = int(raw)
            if 1 <= index <= len(available_names):
                return available_names[index - 1]
        if raw in available_names:
            return raw
        print('输入无效，请重新输入。')


def interactive_datasets_list(yaml_config: dict[str, Any]) -> int:
    print_task_header('查看数据集')
    args = argparse.Namespace(dataset_root=None, json=False)
    return handle_datasets_list(args, yaml_config)


def interactive_prompts_list(yaml_config: dict[str, Any]) -> int:
    print_task_header('查看 Prompt 列表')
    args = argparse.Namespace(prompt_dir=None, json=False)
    return handle_prompts_list(args, yaml_config)


def interactive_run(yaml_config: dict[str, Any]) -> int:
    print_task_header('运行实验')
    print('[run] 直接回车表示使用 YAML 默认值。')
    print(f"[run] 当前默认 prompts: {', '.join(yaml_config.get('prompt_files') or []) or '(未配置)'}")
    print(f"[run] 当前默认 datasets: {', '.join(yaml_config.get('datasets') or []) or '(未配置)'}")

    prompts_raw = prompt_text('输入 prompt 文件路径，多个用空格或逗号分隔', '', allow_back=True)
    datasets_raw = prompt_text('输入数据集，多个用空格或逗号分隔', '', allow_back=True)
    sample_size = prompt_optional_int('抽样数量 sample_size', yaml_config.get('sample_size'))
    seed = prompt_optional_int('随机种子 seed', yaml_config.get('seed'))
    max_workers = prompt_optional_int('并发数 max_workers', yaml_config.get('max_workers'))
    timeout = prompt_optional_int('超时秒数 timeout', yaml_config.get('timeout'))
    temperature = prompt_optional_float('温度 temperature', yaml_config.get('temperature'))
    request_delay = prompt_optional_float('请求间隔 request_delay', yaml_config.get('request_delay'))

    args = argparse.Namespace(
        prompts=parse_multi_values(prompts_raw) if prompts_raw else None,
        dataset=parse_multi_values(datasets_raw) if datasets_raw else None,
        dataset_root=None,
        sample_size=sample_size,
        seed=seed,
        max_workers=max_workers,
        timeout=timeout,
        temperature=temperature,
        api_url=None,
        api_key=None,
        model=None,
        output_root=None,
        request_delay=request_delay,
    )
    return handle_run(args, yaml_config)


def interactive_experiments_list(yaml_config: dict[str, Any]) -> int:
    print_task_header('查看实验列表')
    args = argparse.Namespace(output_root=None, json=False)
    return handle_experiments_list(args, yaml_config)


def interactive_experiments_show(yaml_config: dict[str, Any]) -> int:
    print_task_header('查看单个实验详情')
    output_root = resolve_output_root(None, yaml_config)
    run_id = select_run_id(output_root)
    args = argparse.Namespace(run_id=run_id, output_root=None, json=False)
    return handle_experiments_show(args, yaml_config)


def interactive_experiments_compare(yaml_config: dict[str, Any]) -> int:
    print_task_header('比较同一实验中的两个 Prompt')
    output_root = resolve_output_root(None, yaml_config)
    run_id = select_run_id(output_root)
    prompt_names = load_run_prompt_names(output_root, run_id)
    if len(prompt_names) < 2:
        raise ValueError(f'该实验少于 2 个 Prompt，无法比较: {run_id}')

    print('\n[compare] 请选择基线 Prompt')
    baseline = select_prompt_name(prompt_names, '输入基线 Prompt 编号或名称')
    print('\n[compare] 请选择目标 Prompt')
    target = select_prompt_name(prompt_names, '输入目标 Prompt 编号或名称', excluded={baseline})
    case_type = prompt_text('输入 case 类型 all/both_correct/both_wrong/improved/regressed', 'all', allow_back=True)
    while case_type not in CASE_TYPES:
        print('case 类型无效，请重新输入。')
        case_type = prompt_text('输入 case 类型 all/both_correct/both_wrong/improved/regressed', 'all', allow_back=True)
    dataset_raw = prompt_text('输入数据集筛选，多个用空格或逗号分隔，直接回车表示全部', '', allow_back=True)
    limit = prompt_optional_int('显示条数 limit', 20)

    args = argparse.Namespace(
        run_id=run_id,
        baseline=baseline,
        target=target,
        case_type=case_type,
        dataset=parse_multi_values(dataset_raw) if dataset_raw else None,
        limit=20 if limit is None else limit,
        output_root=None,
        json=False,
    )
    return handle_experiments_compare(args, yaml_config)


def run_interactive_menu(yaml_config: dict[str, Any]) -> int:
    handlers = {
        '1': interactive_datasets_list,
        '2': interactive_prompts_list,
        '3': interactive_run,
        '4': interactive_experiments_list,
        '5': interactive_experiments_show,
        '6': interactive_experiments_compare,
    }

    while True:
        clear_screen()
        print_interactive_menu()
        try:
            choice = prompt_text('请输入编号', '0')
        except (EOFError, KeyboardInterrupt):
            print('\n已退出。')
            return 0

        if choice == '0':
            print('已退出。')
            return 0
        handler = handlers.get(choice)
        if handler is None:
            print('无效编号，请重新输入。')
            continue

        try:
            handler(yaml_config)
            wait_for_menu_return()
        except ReturnToMenu:
            print('\n已返回主菜单。')
        except KeyboardInterrupt:
            print('\n操作已取消。')
        except EOFError:
            print('\n输入已结束，返回主菜单。')
        except Exception as exc:  # noqa: BLE001
            print(f'[error] {exc}')


def main() -> int:
    load_env_file(Path('.env'))
    yaml_config = load_yaml_config(CONFIG_FILE_PATH)
    args = parse_args()

    if args.interactive or args.command is None:
        return run_interactive_menu(yaml_config)

    if args.command == 'run':
        return handle_run(args, yaml_config)
    if args.command == 'datasets' and args.datasets_command == 'list':
        return handle_datasets_list(args, yaml_config)
    if args.command == 'prompts' and args.prompts_command == 'list':
        return handle_prompts_list(args, yaml_config)
    if args.command == 'experiments' and args.experiments_command == 'list':
        return handle_experiments_list(args, yaml_config)
    if args.command == 'experiments' and args.experiments_command == 'show':
        return handle_experiments_show(args, yaml_config)
    if args.command == 'experiments' and args.experiments_command == 'compare':
        return handle_experiments_compare(args, yaml_config)
    raise ValueError(f'不支持的命令: {args.command}')


if __name__ == '__main__':
    sys.exit(main())
