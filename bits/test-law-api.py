#!/usr/bin/env python3
"""Run live law API smoke tests with login, journaling, and cleanup.

The script only creates uniquely named ``API冒烟测试`` records. Every created
law ID is persisted before the next step and deleted in ``finally``. If cleanup
cannot finish, rerun with ``--cleanup-only``. Credentials are loaded from .env,
but are never written to the recovery state file.
"""

import argparse
import getpass
import json
import os
import signal
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_FILE = REPO_ROOT / 'uploads' / 'tmp' / 'law-api-smoke-state.json'
TEST_TEXT = 'LexPort law API smoke-test document. Safe to delete.\n'


class SmokeFailure(RuntimeError):
    pass


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ApiClient:
    def __init__(self, base_url, timeout):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.opener = build_opener(NoRedirectHandler())

    def request(self, method, path, *, token=None, json_body=None,
                form=None, file_path=None):
        headers = {'Accept': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        body = None
        if form is not None or file_path is not None:
            body, content_type = _encode_multipart(form or {}, file_path)
            headers['Content-Type'] = content_type
        elif json_body is not None:
            body = json.dumps(json_body, ensure_ascii=False).encode('utf-8')
            headers['Content-Type'] = 'application/json'

        request = Request(
            f'{self.base_url}{path}', data=body, headers=headers, method=method,
        )
        try:
            response = self.opener.open(request, timeout=self.timeout)
            return response.status, dict(response.headers), response.read()
        except HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()
        except URLError as exc:
            raise SmokeFailure(f'无法连接 API：{exc.reason}') from exc

    def json(self, method, path, *, expected, token=None, json_body=None,
             form=None, file_path=None):
        status, headers, raw = self.request(
            method, path, token=token, json_body=json_body,
            form=form, file_path=file_path,
        )
        try:
            payload = json.loads(raw.decode('utf-8')) if raw else None
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SmokeFailure(
                f'{method} {path} 返回 {status}，但响应不是合法 JSON'
            ) from exc

        statuses = {expected} if isinstance(expected, int) else set(expected)
        if status not in statuses:
            detail = json.dumps(payload, ensure_ascii=False) if payload else raw[:300]
            raise SmokeFailure(
                f'{method} {path} 预期 {sorted(statuses)}，实际 {status}: {detail}'
            )
        if payload is not None and status < 400 and not payload.get('success'):
            raise SmokeFailure(f'{method} {path} 返回 success=false: {payload}')
        return payload, headers


def _encode_multipart(form, file_path):
    boundary = f'----LexPortSmoke{uuid.uuid4().hex}'
    chunks = []
    for key, value in form.items():
        if value is None:
            continue
        chunks.extend([
            f'--{boundary}\r\n'.encode(),
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(),
            str(value).encode('utf-8'),
            b'\r\n',
        ])
    if file_path is not None:
        path = Path(file_path)
        chunks.extend([
            f'--{boundary}\r\n'.encode(),
            (
                f'Content-Disposition: form-data; name="file"; '
                f'filename="{path.name}"\r\n'
            ).encode(),
            b'Content-Type: text/plain; charset=utf-8\r\n\r\n',
            path.read_bytes(),
            b'\r\n',
        ])
    chunks.append(f'--{boundary}--\r\n'.encode())
    return b''.join(chunks), f'multipart/form-data; boundary={boundary}'


def _step(message):
    print(f'  ✓ {message}')


def _require(condition, message):
    if not condition:
        raise SmokeFailure(message)


def _login(client, login_id, password, expected_role):
    payload, _ = client.json(
        'POST', '/api/auth/login', expected=200,
        json_body={'login_id': login_id, 'password': password},
    )
    data = payload['data']
    role = data['user']['role']
    _require(role == expected_role, f'账号 {login_id} 的角色是 {role}，预期 {expected_role}')
    return data['access_token']


def _password(env_name, label):
    value = os.environ.get(env_name, '')
    if value:
        return value
    if not sys.stdin.isatty():
        raise SmokeFailure(f'请通过 {env_name} 配置{label}密码')
    return getpass.getpass(f'{label}密码（输入不会显示）: ')


def _load_state(path):
    try:
        with path.open('r', encoding='utf-8') as file:
            state = json.load(file)
    except FileNotFoundError as exc:
        raise SmokeFailure(f'恢复状态文件不存在：{path}') from exc
    if not isinstance(state.get('law_ids'), list):
        raise SmokeFailure(f'恢复状态文件格式错误：{path}')
    return state


def _save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    with temporary.open('w', encoding='utf-8') as file:
        json.dump(state, file, ensure_ascii=False, indent=2)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, path)


def _track(path, state, law_id):
    state['law_ids'].append(int(law_id))
    _save_state(path, state)


def _forget(path, state, law_id):
    state['law_ids'] = [item for item in state['law_ids'] if item != int(law_id)]
    _save_state(path, state)


def _cleanup(client, token, state_path, state):
    failures = []
    law_ids = set(state['law_ids'])
    try:
        query = urlencode({
            'keyword': state['run_id'],
            'page': 1,
            'per_page': 100,
        })
        payload, _ = client.json(
            'GET', f'/api/admin/laws?{query}', expected=200, token=token,
        )
        for item in payload['data']['items']:
            if (state['run_id'] in (item.get('title_cn') or '')
                    and (item.get('title_cn') or '').startswith('API冒烟测试-')):
                law_ids.add(int(item['id']))
    except Exception as exc:
        failures.append(('discovery', str(exc)))
        print(f'  ✗ 无法反查本次测试记录: {exc}', file=sys.stderr)

    for law_id in reversed(sorted(law_ids)):
        try:
            payload, _ = client.json(
                'DELETE', f'/api/admin/laws/{law_id}',
                expected=(200, 404), token=token,
            )
            if (payload and payload.get('success') is False
                    and payload.get('error', {}).get('code') != 'NOT_FOUND'):
                raise SmokeFailure(str(payload))
            _forget(state_path, state, law_id)
            print(f'  ✓ 已清理测试法规 {law_id}')
        except Exception as exc:
            failures.append((law_id, str(exc)))
            print(f'  ✗ 无法清理测试法规 {law_id}: {exc}', file=sys.stderr)

    if not state['law_ids'] and not failures:
        try:
            state_path.unlink()
        except FileNotFoundError:
            pass
    return failures


def _item(payload):
    try:
        return payload['data']['item']
    except (KeyError, TypeError) as exc:
        raise SmokeFailure(f'法规响应结构不符合预期：{payload}') from exc


def _run(client, admin_token, editor_token, args, state_path, state):
    suffix = state['run_id']
    admin_title = f'API冒烟测试-管理员-{suffix}'
    renamed_title = f'{admin_title}-已更新'

    with tempfile.TemporaryDirectory(prefix='lexport-law-api-') as temp_dir:
        first_file = Path(temp_dir) / 'smoke-first.txt'
        second_file = Path(temp_dir) / 'smoke-second.txt'
        first_file.write_text(TEST_TEXT, encoding='utf-8')
        second_file.write_text(TEST_TEXT + 'Replacement version.\n', encoding='utf-8')

        print('\n管理员与公开 API：')
        payload, _ = client.json(
            'POST', '/api/admin/laws', expected=201, token=admin_token,
            form={
                'title_cn': admin_title,
                'title_en': f'API Smoke Admin {suffix}',
                'law_number': f'SMOKE-{suffix}',
                'country_id': args.country_id,
                'scene_id': args.scene_id,
                'summary': '自动化 API 冒烟测试；脚本结束后删除。',
            },
            file_path=first_file,
        )
        law = _item(payload)
        admin_id = law['id']
        _track(state_path, state, admin_id)
        _require(law['status'] == 'published' and law['has_file'], '管理员新增结果不正确')
        _step(f'管理员新增带 TXT 文件法规 {admin_id}')

        query = urlencode({'keyword': admin_title, 'page': 1, 'per_page': 10})
        payload, _ = client.json(
            'GET', f'/api/admin/laws?{query}', expected=200, token=admin_token,
        )
        _require(admin_id in {row['id'] for row in payload['data']['items']}, '列表未返回测试法规')
        _step('管理员列表与关键字过滤')

        payload, _ = client.json(
            'GET', f'/api/admin/laws/{admin_id}', expected=200, token=admin_token,
        )
        _require(_item(payload)['id'] == admin_id, '管理员详情 ID 不一致')
        _step('管理员详情')

        payload, _ = client.json('GET', f'/api/laws/{admin_id}', expected=200)
        _require(
            payload['data']['id'] == admin_id and payload['data']['has_file'],
            '公开详情结果不正确',
        )
        _step('公开详情')

        status, headers, _ = client.request('GET', f'/api/laws/{admin_id}/download')
        _require(status == 302 and bool(headers.get('Location')), '下载未返回 OSS 302 签名地址')
        _step('公开下载签名跳转')

        payload, _ = client.json(
            'PUT', f'/api/admin/laws/{admin_id}', expected=200, token=admin_token,
            form={'title_cn': renamed_title, 'summary': '管理员已更新并替换文件。'},
            file_path=second_file,
        )
        law = _item(payload)
        _require(law['title_cn'] == renamed_title and law['has_file'], '管理员修改结果不正确')
        _step('管理员重命名并替换 OSS 文件')

        if editor_token:
            payload, _ = client.json(
                'PUT', f'/api/admin/laws/{admin_id}', expected=200, token=editor_token,
                form={'summary': '编辑提交、随后由管理员丢弃的测试草稿。'},
                file_path=first_file,
            )
            _require(_item(payload)['review_status'] == 'pending', 'editor 修改未进入待审')
            _step('Editor 修改 published 法规进入待审')

            payload, _ = client.json(
                'DELETE', f'/api/admin/laws/{admin_id}/draft',
                expected=200, token=admin_token,
            )
            _require(not _item(payload)['has_draft'], '丢弃后仍存在 LawDraft')
            _step('管理员丢弃 editor 草稿并恢复主版本')

        payload, _ = client.json(
            'POST', f'/api/admin/laws/{admin_id}/suspend',
            expected=200, token=admin_token,
        )
        law = _item(payload)
        _require(law['status'] == 'draft' and law['has_pending_file'], '挂起结果不正确')
        _step('挂起 published 法规')

        payload, _ = client.json(
            'POST', f'/api/admin/laws/{admin_id}/approve',
            expected=200, token=admin_token,
        )
        law = _item(payload)
        _require(law['status'] == 'published' and law['has_file'], '重新审核结果不正确')
        _step('重新审核并发布挂起法规')

        client.json(
            'DELETE', f'/api/admin/laws/{admin_id}', expected=200, token=admin_token,
        )
        _forget(state_path, state, admin_id)
        client.json('GET', f'/api/laws/{admin_id}', expected=404)
        _step('删除 published 法规并确认公开 API 返回 404')

        if editor_token:
            print('\nEditor 新增与审核 API：')
            payload, _ = client.json(
                'POST', '/api/admin/laws', expected=201, token=editor_token,
                form={
                    'title_cn': f'API冒烟测试-编辑-{suffix}',
                    'title_en': f'API Smoke Editor {suffix}',
                    'country_id': args.country_id,
                    'scene_id': args.scene_id,
                    'summary': 'Editor 新增测试；审核后删除。',
                },
                file_path=first_file,
            )
            law = _item(payload)
            editor_id = law['id']
            _track(state_path, state, editor_id)
            _require(law['status'] == 'draft' and law['has_pending_file'], 'editor 新增未进入 draft')
            _step(f'Editor 新增待审法规 {editor_id}')

            payload, _ = client.json(
                'POST', f'/api/admin/laws/{editor_id}/approve',
                expected=200, token=admin_token,
            )
            _require(_item(payload)['status'] == 'published', 'Editor 新增审核后未发布')
            _step('管理员审核 Editor 新增法规')

            client.json(
                'DELETE', f'/api/admin/laws/{editor_id}', expected=200, token=admin_token,
            )
            _forget(state_path, state, editor_id)
            _step('删除 Editor 测试法规')


def _args():
    parser = argparse.ArgumentParser(description='法律 API 现场冒烟测试与自动恢复')
    parser.add_argument(
        '--base-url',
        default=os.environ.get('LAW_API_TEST_BASE_URL', 'http://127.0.0.1:6768'),
    )
    parser.add_argument('--admin-login', default=os.environ.get('LAW_API_TEST_ADMIN_LOGIN'))
    parser.add_argument('--editor-login', default=os.environ.get('LAW_API_TEST_EDITOR_LOGIN'))
    parser.add_argument('--country-id', default=os.environ.get('LAW_API_TEST_COUNTRY_ID', 'ZA'))
    parser.add_argument('--scene-id', default=os.environ.get('LAW_API_TEST_SCENE_ID', 'customs'))
    parser.add_argument('--timeout', type=float, default=30.0)
    parser.add_argument('--state-file', type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument('--cleanup-only', action='store_true')
    return parser.parse_args()


def main():
    load_dotenv(REPO_ROOT / '.env')
    args = _args()
    state_path = args.state_file.expanduser().resolve()

    if not args.admin_login:
        if not sys.stdin.isatty():
            raise SmokeFailure('请配置 LAW_API_TEST_ADMIN_LOGIN')
        args.admin_login = input('Admin 登录名: ').strip()
    admin_password = _password('LAW_API_TEST_ADMIN_PASSWORD', 'Admin')

    client = ApiClient(args.base_url, args.timeout)
    print(f'连接：{args.base_url}')
    admin_token = _login(client, args.admin_login, admin_password, 'admin')
    _step(f'Admin 登录成功：{args.admin_login}')

    if args.cleanup_only:
        state = _load_state(state_path)
        _require(
            state.get('base_url') == args.base_url.rstrip('/'),
            f'状态文件属于 {state.get("base_url")}，当前是 {args.base_url.rstrip("/")}',
        )
        failures = _cleanup(client, admin_token, state_path, state)
        if failures:
            raise SmokeFailure(f'仍有 {len(failures)} 条测试法规未清理；状态文件已保留')
        print('\n✅ 现场恢复完成。')
        return 0

    if state_path.exists():
        raise SmokeFailure(
            f'发现上次运行的恢复状态：{state_path}\n'
            '请先执行 python bits/test-law-api.py --cleanup-only'
        )

    editor_token = None
    if args.editor_login:
        editor_token = _login(
            client, args.editor_login,
            _password('LAW_API_TEST_EDITOR_PASSWORD', 'Editor'), 'editor',
        )
        _step(f'Editor 登录成功：{args.editor_login}')
    else:
        print('  ! 未配置 LAW_API_TEST_EDITOR_LOGIN，跳过 Editor 专属流程')

    state = {
        'version': 1,
        'run_id': uuid.uuid4().hex[:10],
        'base_url': args.base_url.rstrip('/'),
        'created_at': datetime.now(timezone.utc).isoformat(),
        'law_ids': [],
    }
    _save_state(state_path, state)
    print(f'恢复状态：{state_path}')

    test_error = None
    cleanup_failures = []
    try:
        _run(client, admin_token, editor_token, args, state_path, state)
    except BaseException as exc:
        test_error = exc
    finally:
        print('\n现场恢复：')
        cleanup_failures = _cleanup(client, admin_token, state_path, state)

    if cleanup_failures:
        print(f'恢复状态文件保留在：{state_path}', file=sys.stderr)
        raise SmokeFailure(
            f'有 {len(cleanup_failures)} 条测试法规未清理；修复后运行 --cleanup-only'
        )
    if test_error:
        raise test_error

    print('\n✅ 法律 API 冒烟测试全部通过，现场已恢复。')
    return 0


def _interrupt(_signum, _frame):
    raise KeyboardInterrupt('收到终止信号')


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, _interrupt)
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('\n❌ 测试被中断；已尝试恢复现场。', file=sys.stderr)
        raise SystemExit(130)
    except SmokeFailure as exc:
        print(f'\n❌ {exc}', file=sys.stderr)
        raise SystemExit(1)
