"""A restricted preview must ship the shared assets its real templates use."""
import importlib.util
import os
from pathlib import Path


def test_bundle_includes_icons_motion_and_script_without_private_files(tmp_path):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('build_preview', root / 'scripts/build-preview.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    evidence = tmp_path / 'explicit-fixture-screens'
    evidence.mkdir()
    for screen in module.SCREENS:
        for width in (390, 1440):
            (evidence / f'gemini-{screen}-{width}.png').write_bytes(b'Offline screenshot path fixture; not display evidence')
    output = tmp_path / 'restricted-bundle'
    previous = os.umask(0o077)
    try:
        module.build(evidence, output)
    finally:
        os.umask(previous)
    for path in ('static/ayo.css', 'static/experience.css', 'static/workspace.js', 'templates/_icons.html'):
        assert (output / path).read_bytes() == (root / path).read_bytes()
    assert not list(output.rglob('.env*')) and not list(output.rglob('*.db'))
    entry = (output / 'app.py').read_text()
    assert '"AYO_PREVIEW_MODE"] = "1"' in entry
    assert 'sqlite:///:memory:' in entry
