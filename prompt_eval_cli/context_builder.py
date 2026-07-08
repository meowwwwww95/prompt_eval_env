from __future__ import annotations

import re
from typing import Any

from config.skill_kb import SkillKB

from .catalog import PLACEHOLDER_RE
from .models import PromptTemplate


def lookup_skill_details(skill_kb: SkillKB, history_skill: str) -> list[dict[str, str]]:
    if not history_skill:
        return []

    details = skill_kb.find_details(history_skill)
    if details:
        return details
    return [{'name': history_skill, 'description': ''}]


def build_skill_specification(details: list[dict[str, str]]) -> str:
    if not details:
        return ''

    lines = []
    for detail in details:
        lines.append(f"技能名称：{detail['name']}")
        lines.append(f"技能描述：{detail.get('description', '')}")
    return '\n'.join(lines)


def build_template_context(sample: dict[str, Any], skill_kb: SkillKB) -> dict[str, str]:
    history_skill = sample.get('history_skill', '')
    skill_details = lookup_skill_details(skill_kb, history_skill)
    skill_descriptions = [detail.get('description', '') for detail in skill_details if detail.get('description')]

    context = {key: '' if value is None else str(value) for key, value in sample.items()}
    context.update(
        {
            'lastQuery': sample.get('history_question', ''),
            'thisQuery': sample.get('question', ''),
            'lastSkill': history_skill,
            'lastSkillDescription': '\n'.join(skill_descriptions),
            'lastSkillSpecification': build_skill_specification(skill_details),
        }
    )
    return context


def find_missing_variables(text: str, context: dict[str, str]) -> list[str]:
    missing = []
    for match in PLACEHOLDER_RE.finditer(text):
        key = match.group(1) or match.group(2) or ''
        if key and key not in context and key not in missing:
            missing.append(key)
    return missing


def render_template_text(text: str, context: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1) or match.group(2) or ''
        return context.get(key, '')

    return PLACEHOLDER_RE.sub(replace, text).strip()


def render_messages(template: PromptTemplate, sample: dict[str, Any], skill_kb: SkillKB) -> list[dict[str, str]]:
    context = build_template_context(sample, skill_kb)
    missing_vars = find_missing_variables(template.system, context) + find_missing_variables(template.user, context)
    if missing_vars:
        unique_vars = []
        for item in missing_vars:
            if item not in unique_vars:
                unique_vars.append(item)
        raise ValueError(f'模板变量缺失: {", ".join(unique_vars)}')

    system_text = render_template_text(template.system, context)
    user_text = render_template_text(template.user, context)

    messages = []
    if system_text:
        messages.append({'role': 'system', 'content': system_text})
    messages.append({'role': 'user', 'content': user_text})
    return messages


def format_messages_for_export(messages: list[dict[str, str]]) -> str:
    sections = []
    for message in messages:
        role = (message.get('role') or '').upper()
        content = message.get('content', '')
        sections.append(f'=== {role} ===\n{content}')
    return '\n\n'.join(sections)
