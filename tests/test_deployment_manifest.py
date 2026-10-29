"""The real serverless runtime must install the same graph tested in CI."""
from importlib.metadata import version
from pathlib import Path
import re
import tomllib


def test_vercel_manifest_contains_entire_pinned_lock_graph_and_actual_httpx():
    root = Path(__file__).resolve().parents[1]
    manifest = tomllib.loads((root / 'pyproject.toml').read_text())
    locked = set(re.findall(r'^([a-zA-Z0-9_.-]+==[^\s\\]+)',
                           (root / 'requirements.lock').read_text(), re.M))
    assert len(locked) >= 30
    assert set(manifest['project']['dependencies']) == locked
    assert 'httpx==' + version('httpx') in locked
    assert manifest['tool']['uv']['package'] is False
