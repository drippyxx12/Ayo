"""Bound request bodies before multipart/form parsing or webhook processing."""
import asyncio
from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    def __init__(self, app, max_bytes=262144, timeout=15):
        self.app, self.max_bytes, self.timeout = app, max_bytes, timeout

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('method') not in {'POST', 'PUT', 'PATCH'}:
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        try:
            length = int(headers.get(b'content-length', b'0'))
            if length < 0:
                raise ValueError()
        except ValueError:
            return await JSONResponse({'detail': 'Invalid request size.'}, status_code=400)(scope, receive, send)
        if length > self.max_bytes:
            return await JSONResponse({'detail': 'Request body exceeds the size limit.'}, status_code=413)(scope, receive, send)
        chunks, size = [], 0
        deadline = asyncio.get_running_loop().time() + self.timeout
        try:
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError()
                message = await asyncio.wait_for(receive(), remaining)
                if message['type'] == 'http.disconnect':
                    return
                chunk = message.get('body', b'')
                size += len(chunk)
                if size > self.max_bytes:
                    return await JSONResponse({'detail': 'Request body exceeds the size limit.'}, status_code=413)(scope, receive, send)
                chunks.append(chunk)
                if not message.get('more_body', False):
                    break
        except TimeoutError:
            return await JSONResponse({'detail': 'Request body timed out.'}, status_code=408)(scope, receive, send)
        body = b''.join(chunks)
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {'type': 'http.request', 'body': body, 'more_body': False}
            return await receive()

        return await self.app(scope, replay, send)
