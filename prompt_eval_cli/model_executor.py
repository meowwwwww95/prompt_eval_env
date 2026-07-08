from __future__ import annotations

import json
import time
from typing import Any

import requests

from config.skill_kb import SkillKB

from .adapters import ContextAdapter
from .adapters import OutputParserAdapter
from .context_builder import format_messages_for_export
from .models import PromptTemplate
from .models import RuntimeConfig


def extract_response_text(response_json: dict[str, Any]) -> str:
    choices = response_json.get('choices') or []
    if not choices:
        return ''

    message = choices[0].get('message') or {}
    content = message.get('content', '')
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'text':
                parts.append(item.get('text', ''))
        return '\n'.join(part for part in parts if part).strip()
    return str(content).strip()


def extract_usage(response_json: dict[str, Any]) -> tuple[int | None, int | None]:
    usage = response_json.get('usage') or {}
    input_tokens = usage.get('prompt_tokens')
    output_tokens = usage.get('completion_tokens')
    return input_tokens, output_tokens


def call_model(config: RuntimeConfig, messages: list[dict[str, str]]) -> tuple[dict[str, Any], str, int, int | None, int | None]:
    headers = {
        'Authorization': f'Bearer {config.api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': config.model,
        'messages': messages,
        'temperature': config.temperature,
    }

    started_at = time.perf_counter()
    response = requests.post(config.api_url, json=payload, headers=headers, timeout=config.timeout)
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    response.raise_for_status()
    response_json = response.json()
    content = extract_response_text(response_json)
    input_tokens, output_tokens = extract_usage(response_json)
    return response_json, content, latency_ms, input_tokens, output_tokens


def build_record(
    sample: dict[str, Any],
    template: PromptTemplate,
    messages: list[dict[str, str]],
    raw_output: str,
    parsed_judgment: str,
    parse_method: str,
    output_parser_adapter: OutputParserAdapter,
    latency_ms: int,
    input_tokens: int | None,
    output_tokens: int | None,
    error_message: str = '',
) -> dict[str, Any]:
    is_correct = parsed_judgment == sample['expected_judgment']
    if parsed_judgment == '未知':
        is_correct = False

    final_prompt = format_messages_for_export(messages)
    return {
        'run_id': '',
        'sample_id': sample['sample_id'],
        'dataset_name': sample['dataset_name'],
        'label': sample['label'],
        'ground_truth': sample['expected_judgment'],
        'expected_judgment': sample['expected_judgment'],
        'question': sample.get('question', ''),
        'history_question': sample.get('history_question', ''),
        'history_skill': sample.get('history_skill', ''),
        'prompt_name': template.name,
        'prompt_path': template.path,
        'final_prompt': final_prompt,
        'assembled_prompt': final_prompt,
        'request_messages_json': json.dumps(messages, ensure_ascii=False),
        'prediction': parsed_judgment,
        'parsed_judgment': parsed_judgment,
        'parse_method': parse_method,
        'parse_status': output_parser_adapter.parse_status(parsed_judgment, parse_method, error_message),
        'is_correct': is_correct,
        'status': 'failed' if error_message else 'success',
        'latency_ms': latency_ms,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'error_message': error_message,
        'raw_output': raw_output,
        'source_file': sample.get('source_file', ''),
    }


def evaluate_one(
    sample: dict[str, Any],
    template: PromptTemplate,
    config: RuntimeConfig,
    skill_kb: SkillKB,
    context_adapter: ContextAdapter,
    output_parser_adapter: OutputParserAdapter,
) -> dict[str, Any]:
    if config.request_delay > 0:
        time.sleep(config.request_delay)

    try:
        messages = context_adapter.render_messages(template, sample, skill_kb)
        _, content, latency_ms, input_tokens, output_tokens = call_model(config, messages)
        parsed_judgment, parse_method = output_parser_adapter.parse_judgment(content)
        return build_record(
            sample=sample,
            template=template,
            messages=messages,
            raw_output=content,
            parsed_judgment=parsed_judgment,
            parse_method=parse_method,
            output_parser_adapter=output_parser_adapter,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    except Exception as exc:  # noqa: BLE001
        return build_record(
            sample=sample,
            template=template,
            messages=messages if 'messages' in locals() else [],
            raw_output='',
            parsed_judgment='未知',
            parse_method='error',
            output_parser_adapter=output_parser_adapter,
            latency_ms=0,
            input_tokens=None,
            output_tokens=None,
            error_message=str(exc),
        )
