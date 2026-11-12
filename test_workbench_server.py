"""Exercise the local HTTP boundary without binding sockets or starting threads."""

from io import BytesIO
import json
from types import SimpleNamespace

import pytest

from workbench_server import (
    DEFAULT_ORIGINS, MAX_REQUEST_BYTES, WorkbenchHandler, _origin,
)


class MemorySocket:
    def __init__(self, request):
        self.input = BytesIO(request)
        self.output = bytearray()
        self.timeout = None

    def makefile(self, mode, *args):
        assert mode == 'rb'
        return self.input

    def settimeout(self, value):
        self.timeout = value

    def sendall(self, data):
        self.output.extend(data)


class QuietHandler(WorkbenchHandler):
    def log_message(self, *args):
        pass


def headers(body=b''):
    return [
        ('Host', '127.0.0.1:8765'),
        ('Origin', 'http://localhost:5174'),
        ('Content-Type', 'application/json'),
        ('Content-Length', str(len(body))),
    ]


def exchange(method, path, payload=None, *, body=None, request_headers=None):
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8') if body is None else body
    supplied_headers = headers(body) if request_headers is None else request_headers
    head = f'{method} {path} HTTP/1.1\r\n' + ''.join(
        f'{key}: {value}\r\n' for key, value in supplied_headers
    ) + '\r\n'
    connection = MemorySocket(head.encode('latin-1') + body)
    server = SimpleNamespace(
        server_address=('127.0.0.1', 8765), allowed_origins=frozenset(DEFAULT_ORIGINS),
    )
    QuietHandler(connection, ('127.0.0.1', 12345), server)
    response_headers, response_body = bytes(connection.output).split(b'\r\n\r\n', 1)
    lines = response_headers.decode('latin-1').split('\r\n')
    status = int(lines[0].split(' ')[1])
    actual_headers = dict(line.split(': ', 1) for line in lines[1:])
    assert actual_headers['Content-Type'] == 'application/json; charset=utf-8'
    assert actual_headers['Content-Length'] == str(len(response_body))
    assert actual_headers['Cache-Control'] == 'no-store'
    assert actual_headers['X-Content-Type-Options'] == 'nosniff'
    assert actual_headers['Connection'] == 'close'
    assert not any(key.lower().startswith('access-control-') for key in actual_headers)
    assert connection.timeout == 10
    return status, json.loads(response_body)


def test_http_start_continue_and_validate_preserve_a_replayable_record():
    status, value = exchange('POST', '/api/workbench/start', {
        'dictionary': {'name': 'Small reader example', 'entries': [['answer', '5+6']]},
        'demand': 'answer', 'context': 'A supplied response remains unchecked.',
    })
    assert status == 200
    record = value['record']
    assert record['question']['demand'] == 'answer'
    status, value = exchange('POST', '/api/workbench/command', {
        'record': record,
        'command': {'operation': 'recall', 'frame_id': 'F', 'position': 0, 'entry_index': 0},
    })
    assert status == 200
    recalled = value['record']
    assert recalled['snapshots'][-1]['prediction_set']['result'] == '5+6'
    status, value = exchange('POST', '/api/workbench/command', {
        'record': recalled,
        'command': {'operation': 'reduce', 'frame_id': 'F', 'response': '12'},
    })
    assert status == 200
    continued = value['record']
    assert continued['record_id'] == record['record_id']
    assert continued['snapshots'][:-1] == recalled['snapshots']
    claims = continued['snapshots'][-1]['prediction_set']['predictions']
    assert claims[-1]['evidence']['stimulus'] == '5+6'
    assert claims[-1]['evidence']['response'] == '12'
    assert claims[-1]['verification'] == 'unchecked'
    status, value = exchange('POST', '/api/workbench/validate', {'record': continued})
    assert status == 200
    assert value['record'] == continued


def test_health_supports_local_cli_requests_without_an_origin():
    status, value = exchange('GET', '/api/workbench/health', request_headers=[('Host', 'localhost:8765')])
    assert status == 200
    assert value['protocol_version'] == 1
    assert value['producer']['name'] == 'VDfirst'


@pytest.mark.parametrize('bad_headers', [
    [], [('Host', 'untrusted.example:8765')], [('Host', '127.0.0.1:8766')],
    [('Host', '127.0.0.1')], [('Host', '127.0.0.1:8765'), ('Host', 'localhost:8765')],
    [('Host', 'localhost:8765'), ('Origin', 'https://untrusted.example')],
    [('Host', 'localhost:8765'), ('Origin', 'null')],
    [('Host', 'localhost:8765'), ('Origin', 'http://localhost:9999')],
    [('Host', 'localhost:8765'), ('Origin', 'http://localhost:5174'), ('Origin', 'http://localhost:5174')],
])
def test_unexpected_host_and_origin_are_rejected_before_reading_a_body(bad_headers):
    status, value = exchange('POST', '/api/workbench/start', body=b'', request_headers=bad_headers)
    assert status == 403
    assert 'error' in value


@pytest.mark.parametrize('content_type', [None, 'text/plain', 'application/x-www-form-urlencoded'])
def test_simple_cross_origin_content_types_cannot_enter_the_json_api(content_type):
    supplied = [('Host', 'localhost:8765'), ('Content-Length', '0')]
    if content_type is not None:
        supplied.append(('Content-Type', content_type))
    status, value = exchange('POST', '/api/workbench/start', body=b'', request_headers=supplied)
    assert status == 415
    assert 'application/json' in value['error']


@pytest.mark.parametrize('length_headers', [
    [], [('Content-Length', '-1')], [('Content-Length', '1.0')],
    [('Content-Length', '\xb2')], [('Content-Length', '0'), ('Content-Length', '0')],
    [('Content-Length', '0'), ('Transfer-Encoding', 'chunked')],
])
def test_ambiguous_or_invalid_request_lengths_are_rejected(length_headers):
    supplied = [('Host', 'localhost:8765'), ('Content-Type', 'application/json'), *length_headers]
    status, value = exchange('POST', '/api/workbench/start', body=b'', request_headers=supplied)
    assert status == 400
    assert 'Content-Length' in value['error']


@pytest.mark.parametrize('length', [str(MAX_REQUEST_BYTES + 1), '9' * 5000])
def test_request_size_is_rejected_before_reading_or_converting_unbounded_lengths(length):
    supplied = [('Host', 'localhost:8765'), ('Content-Type', 'application/json'), ('Content-Length', length)]
    status, value = exchange('POST', '/api/workbench/start', body=b'', request_headers=supplied)
    assert status == 413
    assert 'size limit' in value['error']


@pytest.mark.parametrize('body', [
    b'{"record":{},"record":{}}', b'{"record":{"same":1,"same":2}}',
    b'{"record":NaN}', b'{"record":Infinity}', b'[]', b'null', b'{', b'\xff',
])
def test_duplicate_keys_nonfinite_values_and_malformed_json_are_rejected(body):
    status, value = exchange('POST', '/api/workbench/validate', body=body)
    assert status == 400
    assert 'error' in value


def test_incomplete_body_is_reported_as_a_json_error():
    supplied = [('Host', 'localhost:8765'), ('Content-Type', 'application/json'), ('Content-Length', '100')]
    status, value = exchange('POST', '/api/workbench/validate', body=b'{}', request_headers=supplied)
    assert status == 400
    assert value['error'] == 'incomplete request body'


@pytest.mark.parametrize('method,path,expected', [
    ('GET', '/secrets', 404), ('POST', '/api/workbench/unknown', 404),
    ('OPTIONS', '/api/workbench/start', 405),
])
def test_the_bridge_serves_only_its_explicit_api_routes(method, path, expected):
    status, value = exchange(method, path)
    assert status == expected
    assert 'error' in value


@pytest.mark.parametrize('origin', [
    'https://localhost:5174', 'http://untrusted.example:5174', 'null',
    'http://localhost:5174/', 'http://user@localhost:5174', 'http://localhost',
])
def test_extra_allowed_origins_must_be_explicit_local_http_origins(origin):
    with pytest.raises(ValueError):
        _origin(origin)
