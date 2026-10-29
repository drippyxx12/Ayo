#!/usr/bin/env python3
"""Build a restricted, secret-free Vercel preview bundle; never deploy it."""
import argparse
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SCREENS = ('home', 'report', 'dashboard', 'leads', 'settings', 'security')
FONTS = (
    'syne-variable.ttf', 'dm-sans-variable.ttf', 'dm-mono-regular.ttf',
    'OFL-Syne.txt', 'OFL-DM-Sans.txt', 'OFL-DM-Mono.txt', 'README.md',
)
ENTRYPOINT = '''"""Restricted preview entrypoint. Never enable merchant storage/provider routes here."""
import os
from cryptography.fernet import Fernet
os.environ["AYO_PREVIEW_MODE"] = "1"
os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["AYO_PROVIDER_SPEND_AUTHORIZED"] = "0"
os.environ["AYO_MAIL_SEND_AUTHORIZED"] = "0"
os.environ["TOKEN_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
if os.getenv("VERCEL_URL"):
    os.environ["APP_ORIGIN"] = "https://" + os.environ["VERCEL_URL"]
from ayo.app import app
'''
VERCEL = {
    '$schema': 'https://openapi.vercel.sh/vercel.json',
    'framework': 'fastapi',
    'functions': {'app.py': {
        'maxDuration': 15, 'includeFiles': '{ayo/**,templates/**,static/**}',
    }},
    'headers': [{'source': '/(.*)', 'headers': [{
        'key': 'X-Robots-Tag', 'value': 'noindex, nofollow, noarchive',
    }]}],
}


def build(evidence: Path, output: Path, screenshot_prefix: str = 'gemini') -> None:
    """Copy only explicit runtime files and labeled offline screenshot evidence."""
    evidence = evidence.resolve(strict=True)
    if screenshot_prefix not in {'gemini', 'platform'}:
        raise ValueError('Select an existing labeled Gemini or original platform evidence set.')
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('Output must be an explicitly new directory; refusing to overwrite.')
    if not evidence.is_dir():
        raise ValueError('Evidence must be a directory of labeled offline test screenshots.')
    files = {}
    for folder, suffix in [('ayo', '*.py'), ('templates', '*.html')]:
        for source in (ROOT / folder).rglob(suffix):
            if '__pycache__' not in source.parts:
                files[source.relative_to(ROOT)] = source
    files[Path('static/ayo.css')] = ROOT / 'static/ayo.css'
    files[Path('static/experience.css')] = ROOT / 'static/experience.css'
    files[Path('static/workspace.js')] = ROOT / 'static/workspace.js'
    for name in FONTS:
        files[Path('static/fonts') / name] = ROOT / 'static/fonts' / name
    files[Path('static/tour.html')] = ROOT / 'preview/tour.html'
    files[Path('static/tour-assets/tour.css')] = ROOT / 'preview/tour.css'
    for screen in SCREENS:
        for width, variant in [(390, 'mobile'), (1440, 'desktop')]:
            files[Path(f'static/tour-assets/{screen}-{variant}.png')] = (
                evidence / f'{screenshot_prefix}-{screen}-{width}.png'
            )
    files[Path('requirements.txt')] = ROOT / 'requirements.lock'
    for source in files.values():
        if source.is_symlink() or not source.is_file():
            raise ValueError(f'Missing or symlinked whitelisted source: {source}')
    lock = (ROOT / 'requirements.lock').read_text()
    if any(line.lstrip().startswith(('-r ', '--requirement ', '-e '))
           for line in lock.splitlines()):
        raise ValueError('Lock must contain flattened pinned requirements, not includes.')
    os.umask(0o077)
    output.mkdir(parents=True, exist_ok=False)
    for relative, source in files.items():
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    base = output / 'templates/base.html'
    original = 'Development preview · Business intake only.'
    replacement = ('Development preview · <a href="/static/tour.html">'
                   'View the implemented screens ↗</a> · Business intake only.')
    content = base.read_text()
    if content.count(original) != 1:
        raise ValueError('Preview banner changed; review the source before rebuilding.')
    base.write_text(content.replace(original, replacement))
    (output / 'app.py').write_text(ENTRYPOINT)
    (output / '.python-version').write_text('3.12\n')
    (output / 'vercel.json').write_text(json.dumps(VERCEL, indent=2) + '\n')
    print(f'Built restricted preview in {output}; no deployment performed.')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir', type=Path, required=True,
                        help='Existing labeled offline workflow screenshots, never merchant captures.')
    parser.add_argument('--output', type=Path, required=True,
                        help='New output directory; existing directories are never overwritten.')
    parser.add_argument('--screenshot-prefix', choices=('gemini', 'platform'), default='gemini',
                        help='Labeled evidence set; Gemini is the current report implementation.')
    args = parser.parse_args()
    try:
        build(args.evidence_dir, args.output, args.screenshot_prefix)
    except (OSError, ValueError) as error:
        parser.exit(2, f'Preview build refused: {error}\n')


if __name__ == '__main__':
    main()
