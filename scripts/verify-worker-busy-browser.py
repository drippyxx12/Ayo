"""Offline browser protocol regression:202 waits without repeated commands."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    counts = {'intake_get': 0, 'worker_post': 0, 'status_get': 0}
    revision = 'a' * 64

    class Fixture(BaseHTTPRequestHandler):
        def send(self, status, body, content_type='application/json'):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == '/':
                counts['intake_get'] += 1
                self.send(200, '<!doctype html><title>Offline busy-command fixture</title>'
                    '<main data-research-watch="/fixture-status" data-research-revision="' + revision + '">'
                    '<form data-research-dispatch method="post" action="/fixture-worker">'
                    '<input name="csrf" value="offline-only-form-fixture"><button type="submit">Run fixture</button>'
                    '<p data-worker-dispatch-status></p></form><p data-research-poll-status></p></main>'
                    '<script src="/workspace.js" defer></script>', 'text/html; charset=utf-8')
            elif self.path == '/workspace.js':
                self.send(200, (ROOT / 'static/workspace.js').read_bytes(), 'text/javascript')
            elif self.path == '/fixture-status':
                counts['status_get'] += 1
                self.send(200, json.dumps({'revision': revision, 'terminal': False}))
            else:
                self.send(404, '{}')

        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length', 0)))
            counts['worker_post'] += 1
            self.send(202, '{"processed":false}')

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = 'http://127.0.0.1:' + str(server.server_address[1])
    errors = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
            context = browser.new_context()
            context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(origin + '/') else route.abort())
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            with page.expect_response(lambda response: response.url == origin + '/fixture-status', timeout=10000):
                page.goto(origin)
            assert counts == {'intake_get': 1, 'worker_post': 1, 'status_get': 1}, counts
            assert 'did not start another attempt' in page.locator('[data-worker-dispatch-status]').inner_text()
            assert not errors
            context.close()
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    receipt = {'date': datetime.now(timezone.utc).isoformat(), 'mode': 'offline_browser_busy_response_protocol',
        'response_status': 202, 'counts': counts, 'no_automatic_repost': True,
        'real_source_model_calls': 0, 'page_errors': errors, 'server_stopped': not thread.is_alive()}
    (ROOT / 'docs/evidence/worker-busy-browser.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
