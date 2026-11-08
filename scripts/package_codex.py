#!/usr/bin/env python3
"""Build a self-contained Codex distribution without touching host installations."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESOURCE_SUFFIXES = {'.py', '.js', '.md', '.json', '.toml', '.txt', '.csv', '.yaml', '.yml', '.lock', '.html'}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def regular_files(root: Path):
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'Symlinks cannot be packaged: {path}')
        if path.is_file() and not any(part.startswith('.') or part == '__pycache__' for part in path.relative_to(root).parts):
            if path.suffix in RESOURCE_SUFFIXES or path.name in {'LICENSE', 'NOTICE'}:
                yield path


def build(output: Path, source_ref: str | None = None, source: Path = ROOT) -> dict:
    if not output.is_absolute():
        raise ValueError('--output must be an absolute new directory')
    if output.exists() or output.is_symlink():
        raise ValueError('--output must not already exist')
    for ancestor in output.parents:
        if ancestor.is_symlink():
            raise ValueError('Output ancestors must not be symlinks')
    full = source / 'adapters/codex/full'
    upstream = json.loads((full / 'source-manifest.json').read_text(encoding="utf-8"))
    origins = {item['destination']: item for item in upstream['files']}
    tracked_result = subprocess.run(['git', '-C', str(source), 'ls-files', '-z'], capture_output=True, check=True)
    tracked = set(tracked_result.stdout.decode().split('\0'))
    planned: dict[str, tuple[Path, dict]] = {}

    def add(path: Path, destination: str, origin: dict | None = None):
        if not path.is_relative_to(source):
            raise ValueError(f'Source file escapes repository: {path}')
        for candidate in (path, *path.parents):
            if candidate.is_symlink():
                raise ValueError(f'Symlink source is not allowed: {candidate}')
            if candidate == source:
                break
        if not path.is_file():
            raise ValueError(f'Expected regular source file: {path}')
        planned[destination] = (path, origin or {})

    for directory, destination in [('skills', 'source-skills'), ('schema', 'schema'), ('data', 'data'), ('extensions', 'extensions')]:
        for path in regular_files(source / directory):
            if path.relative_to(source).as_posix() in tracked:
                add(path, f'{destination}/{path.relative_to(source / directory).as_posix()}')
    for relative, origin in origins.items():
        path = full / relative
        if any(part.startswith('.') or part in {'__pycache__', 'node_modules', 'venv'} for part in Path(relative).parts):
            raise ValueError(f'Private or generated state in package manifest: {relative}')
        if origin.get('source') and origin['source'] not in tracked:
            raise ValueError(f'Generated resource has an untracked source: {origin["source"]}')
        if Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError(f'Unsafe generated path: {relative}')
        if digest(path.read_bytes()) != origin['sha256']:
            raise ValueError(f'Generated file changed; rebuild the Codex skills: {relative}')
        if origin.get('source') and origin.get('source_sha256'):
            original = source / origin['source']
            if digest(original.read_bytes()) != origin['source_sha256']:
                raise ValueError(f'Generated source changed; rebuild the Codex skills: {origin["source"]}')
        add(path, relative, origin)
    add(full / 'source-manifest.json', 'source-manifest.json')
    for path in sorted((source / 'scripts').glob('*.py')):
        if path.relative_to(source).as_posix() in tracked:
            add(path, f'scripts/{path.name}')
    for name in ['scripts/codex-seo', 'hooks/validate-schema.py', 'requirements.txt', 'pyproject.toml', 'LICENSE', 'CONTRIBUTORS.md', 'CITATION.cff', 'plugin.json', 'docs/codex/INSTALL.md', 'docs/codex/FULL-PORT.md']:
        add(source / name, name)
    if source_ref is None:
        result = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=False)
        source_ref = result.stdout.strip() if result.returncode == 0 else 'unknown'
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.seo-codex-package-', dir=output.parent))
    manifest = {'schema_version': 1, 'name': 'seo-codex', 'source_ref': source_ref, 'files': []}
    try:
        for destination, (path, origin) in sorted(planned.items()):
            data = path.read_bytes()
            target = temporary / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o755 if destination == 'scripts/codex-seo' else 0o644)
            manifest['files'].append({'path': destination, 'source': origin.get('source', path.relative_to(source).as_posix()), 'source_sha256': origin.get('source_sha256', origin.get('sha256', digest(data))), 'sha256': digest(data), 'transformed': origin.get('source_sha256', digest(data)) != digest(data), 'mode': target.stat().st_mode & 0o777})
        (temporary / 'package-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding="utf-8")
        os.rename(temporary, output)
    except BaseException:
        shutil.rmtree(temporary)
        raise
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-ref')
    args = parser.parse_args()
    try:
        manifest = build(args.output, args.source_ref)
    except (ValueError, OSError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        parser.exit(2, f'{error}\n')
    print(json.dumps({'output': str(args.output), 'files': len(manifest['files']), 'source_ref': manifest['source_ref']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
