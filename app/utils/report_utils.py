import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo


class InvalidReportError(ValueError):
    pass


REPORT_META_LABELS = {
    '报告编号': 'report_id',
    '生成时间': 'generated_at',
    'AI版本': 'ai_version',
    '数据截止日期': 'data_cutoff_date',
}


def _strip_json_fence(text):
    stripped = text.strip()
    if not stripped.startswith('```'):
        return stripped

    lines = stripped.splitlines()
    if lines and lines[0].strip().lower() in ('```', '```json'):
        lines = lines[1:]
    if lines and lines[-1].strip() == '```':
        lines = lines[:-1]
    return '\n'.join(lines).strip()


def _replace_placeholders(value, placeholders):
    if isinstance(value, dict):
        for key in value:
            value[key] = _replace_placeholders(value[key], placeholders)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            value[index] = _replace_placeholders(item, placeholders)
    elif isinstance(value, str):
        for placeholder, replacement in placeholders.items():
            value = value.replace(placeholder, replacement)
    return value


def _set_report_meta_fields(report_json, replacements):
    try:
        fields = report_json['basicInfo']['reportMeta']['fields']
    except (KeyError, TypeError) as exc:
        raise InvalidReportError('报告 JSON 缺少 basicInfo.reportMeta.fields') from exc

    if not isinstance(fields, list):
        raise InvalidReportError('报告 JSON 的 basicInfo.reportMeta.fields 必须是数组')

    replaced_labels = set()
    for field in fields:
        if not isinstance(field, dict):
            continue
        replacement_key = REPORT_META_LABELS.get(field.get('label'))
        if replacement_key:
            field['value'] = replacements[replacement_key]
            replaced_labels.add(field['label'])

    missing_labels = set(REPORT_META_LABELS) - replaced_labels
    if missing_labels:
        raise InvalidReportError(
            f'报告 JSON 缺少元数据字段: {", ".join(sorted(missing_labels))}'
        )


def _format_completed_at(completed_at):
    timezone = ZoneInfo('Asia/Shanghai')
    if isinstance(completed_at, (int, float)):
        completed = datetime.fromtimestamp(completed_at, tz=timezone)
    elif isinstance(completed_at, datetime):
        if completed_at.tzinfo is None:
            completed = completed_at.replace(tzinfo=timezone)
        else:
            completed = completed_at.astimezone(timezone)
    else:
        completed = datetime.now(timezone)
    return completed.isoformat(timespec='seconds')


def apply_report_metadata(result_data, record_id, ai_version, data_cutoff_date):
    """Replace server-owned metadata inside the final output_text JSON."""
    replacements = {
        'report_id': str(uuid.uuid5(
            uuid.NAMESPACE_URL,
            f'https://lexport.cn/compliance-reports/{record_id}',
        )),
        'generated_at': _format_completed_at(result_data.get('completed_at')),
        'ai_version': ai_version,
        'data_cutoff_date': data_cutoff_date,
    }
    placeholders = {
        '{{REPORT_ID}}': replacements['report_id'],
        '{{GENERATED_AT}}': replacements['generated_at'],
        '{{AI_VERSION}}': replacements['ai_version'],
        '{{DATA_CUTOFF_DATE}}': replacements['data_cutoff_date'],
    }

    for output_item in reversed(result_data.get('output', [])):
        if output_item.get('type') != 'message':
            continue
        for content in output_item.get('content', []):
            if content.get('type') != 'output_text' or not isinstance(content.get('text'), str):
                continue

            try:
                report_json = json.loads(_strip_json_fence(content['text']))
            except json.JSONDecodeError as exc:
                raise InvalidReportError('百炼 output_text 不是有效 JSON') from exc
            if not isinstance(report_json, dict):
                raise InvalidReportError('报告 JSON 根节点必须是对象')

            _replace_placeholders(report_json, placeholders)
            _set_report_meta_fields(report_json, replacements)

            content['text'] = json.dumps(report_json, ensure_ascii=False, indent=2)
            return result_data

    raise InvalidReportError('百炼响应中没有有效的 output_text JSON')
