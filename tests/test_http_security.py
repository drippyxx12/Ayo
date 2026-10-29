from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from ayo.http_security import BodyLimitMiddleware


def test_request_size_guard_handles_declared_and_streamed_oversize_before_endpoint():
    app = FastAPI()
    app.add_middleware(BodyLimitMiddleware, max_bytes=32)
    reached = []

    @app.post('/')
    async def echo(request: Request):
        reached.append(True)
        return {'size': len(await request.body())}

    with TestClient(app) as client:
        assert client.post('/', content=b'x' * 33).status_code == 413
        assert client.post('/', content=iter([b'x' * 20, b'y' * 20])).status_code == 413
        assert not reached
        response = client.post('/', content=b'exact bytes')
        assert response.status_code == 200 and response.json()['size'] == 11


def test_malformed_body_length_is_rejected():
    app = FastAPI()
    app.add_middleware(BodyLimitMiddleware)
    with TestClient(app) as client:
        assert client.post('/', content=b'a', headers={'Content-Length': '-1'}).status_code == 400
