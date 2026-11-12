"""Loopback-only, stateless HTTP adapter for the VDfirst workbench.

Run alongside VD-website's Vite server. It serves no files, persists no
sessions, and never executes code supplied in requests.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import BoundedSemaphore
from urllib.parse import urlsplit

from workbench import (
    MAX_RECORD_BYTES, RecordError, apply_command, producer,
    start_record, validate_record,
)

DEFAULT_ORIGINS = tuple(f'http://{host}:{port}' for host in ('127.0.0.1', 'localhost')
                        for port in (5173, 5174))
MAX_REQUEST_BYTES = MAX_RECORD_BYTES + 65536


def _origin(value):
    parsed = urlsplit(value)
    try:
        valid = (parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost')
                 and parsed.port is not None and not parsed.username and not parsed.password
                 and not parsed.path and not parsed.query and not parsed.fragment)
    except ValueError:
        valid = False
    if not valid:
        raise ValueError('allowed origins must be explicit http://localhost:PORT or http://127.0.0.1:PORT')
    return value


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RecordError('duplicate JSON object keys are not allowed')
        result[key] = value
    return result


class WorkbenchServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 8

    def __init__(self, port=8765, allowed_origins=DEFAULT_ORIGINS):
        self.allowed_origins = frozenset(_origin(value) for value in allowed_origins)
        self._workers = BoundedSemaphore(8)
        super().__init__(('127.0.0.1', port), WorkbenchHandler)

    def process_request(self, request, client_address):
        if not self._workers.acquire(blocking=False):
            data = b'{"error":"local workbench is busy; try again"}'
            try:
                request.settimeout(1)
                request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nContent-Type: application/json\r\n'
                                + f'Content-Length: {len(data)}\r\nConnection: close\r\n\r\n'.encode('ascii') + data)
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._workers.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._workers.release()


class WorkbenchHandler(BaseHTTPRequestHandler):
    server_version = 'VDfirstWorkbench/1'

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def _reply(self, code, value):
        data = json.dumps(value, ensure_ascii=False, allow_nan=False,
                          separators=(',', ':')).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        self.wfile.write(data)

    def _allowed(self):
        port = self.server.server_address[1]
        hosts = self.headers.get_all('Host', [])
        if len(hosts) != 1 or hosts[0].lower() not in {f'127.0.0.1:{port}', f'localhost:{port}'}:
            self._reply(403, {'error': 'unexpected local Host header'})
            return False
        origins = self.headers.get_all('Origin', [])
        if len(origins) > 1 or (origins and origins[0] not in self.server.allowed_origins):
            self._reply(403, {'error': 'origin is not an allowed local workbench'})
            return False
        return True

    def do_GET(self):
        if not self._allowed():
            return
        if self.path != '/api/workbench/health':
            return self._reply(404, {'error': 'unknown workbench route'})
        self._reply(200, {'protocol_version': 1, 'producer': producer()})

    def do_OPTIONS(self):
        if self._allowed():
            self._reply(405, {'error': 'use the website development proxy for local requests'})

    def do_POST(self):
        if not self._allowed():
            return
        if self.path not in {'/api/workbench/start', '/api/workbench/command', '/api/workbench/validate'}:
            return self._reply(404, {'error': 'unknown workbench route'})
        if self.headers.get_content_type() != 'application/json':
            return self._reply(415, {'error': 'request Content-Type must be application/json'})
        lengths = self.headers.get_all('Content-Length', [])
        if (self.headers.get('Transfer-Encoding') or len(lengths) != 1
                or not lengths[0].isascii() or not lengths[0].isdigit()):
            return self._reply(400, {'error': 'one valid Content-Length is required'})
        if len(lengths[0]) > 10:
            return self._reply(413, {'error': 'request exceeds the workbench size limit'})
        length = int(lengths[0])
        if length > MAX_REQUEST_BYTES:
            return self._reply(413, {'error': 'request exceeds the workbench size limit'})
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise RecordError('incomplete request body')
            value = json.loads(raw.decode('utf-8'), object_pairs_hook=_object,
                               parse_constant=lambda _: (_ for _ in ()).throw(RecordError('non-finite JSON values are not allowed')))
            if type(value) is not dict:
                raise RecordError('request body must be an object')
            if self.path.endswith('/start'):
                if not {'dictionary', 'demand'} <= value.keys() or set(value) - {'dictionary', 'demand', 'context'}:
                    raise RecordError('start requires dictionary, demand and optional context')
                record = start_record(value['dictionary'], value['demand'], value.get('context', ''))
            elif self.path.endswith('/command'):
                if set(value) != {'record', 'command'}:
                    raise RecordError('command requires record and command')
                record = apply_command(value['record'], value['command'])
            else:
                if set(value) != {'record'}:
                    raise RecordError('validate requires a record')
                record = validate_record(value['record'])
            self._reply(200, {'record': record})
        except (RecordError, ValueError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
            self._reply(400, {'error': str(exc)[:500]})
        except TimeoutError:
            self._reply(408, {'error': 'request body timed out'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--allow-origin', action='append', default=[])
    args = parser.parse_args()
    try:
        server = WorkbenchServer(args.port, (*DEFAULT_ORIGINS, *args.allow_origin))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(f'VDfirst workbench ready at http://127.0.0.1:{server.server_address[1]}', flush=True)
    print('Start VD-website with pnpm dev; responses remain interpreter supplied.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
