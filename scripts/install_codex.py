#!/usr/bin/env python3
"""Install or remove only manifest-owned Codex SEO files in one project."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import tempfile
import time
import tomllib
import uuid
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

BASE = Path('.codex/seo-codex')
MANIFEST = BASE / 'install-manifest.json'
CONFIG = Path('.codex/config.toml')
BEGIN = '# BEGIN seo-codex managed agents\n'
END = '# END seo-codex managed agents\n'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_path(root: Path, relative: str | Path) -> Path:
    value = PurePosixPath(relative.as_posix() if isinstance(relative, Path) else relative)
    if value.is_absolute() or '..' in value.parts or not value.parts or '\\' in str(value):
        raise ValueError(f'Unsafe relative path: {relative}')
    path = root.joinpath(*value.parts)
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise ValueError(f'Symlink is not allowed: {candidate}')
        if candidate == root:
            break
    return path


def absolute_directory(path: Path) -> Path:
    if not path.is_absolute():
        raise ValueError('Project, package and data directories must be absolute')
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise ValueError(f'Symlink is not allowed: {candidate}')
    path = path.resolve()
    if path == Path(path.anchor) or path == Path.home().resolve():
        raise ValueError('Use a dedicated project or data directory')
    return path


def atomic_write(path: Path, data: bytes, mode: int = 0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def installation_lock(project: Path):
    lock = safe_path(project, BASE / '.install.lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise ValueError(f'Installation lock exists: {lock}. Check the active installer before removing it.') from error
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(str(os.getpid()) + '\n')
        yield
    finally:
        lock.unlink()


def owned_path(project: Path, relative: str) -> Path:
    valid = (relative.startswith('.codex/seo-codex/package/')
             or re.match(r'^\.agents/skills/seo-codex(?:-[a-z0-9-]+)?/', relative)
             or re.fullmatch(r'\.codex/agents/seo-(?:codex|full)-[a-z0-9-]+\.toml', relative))
    if not valid:
        raise ValueError(f'Install manifest claims an invalid ownership path: {relative}')
    return safe_path(project, relative)


def previous_install(project: Path) -> dict | None:
    path = safe_path(project, MANIFEST)
    if not path.exists():
        return None
    manifest = json.loads(path.read_text())
    if manifest.get('schema_version') != 1 or manifest.get('name') != 'seo-codex':
        raise ValueError('Unsupported installation manifest')
    for entry in manifest['files']:
        owned_path(project, entry['path'])
    return manifest


def config_without_owned_block(current: str, previous: dict | None) -> str:
    block = previous.get('agent_block', '') if previous else ''
    if block:
        if current.count(block) != 1:
            raise ValueError('Managed agent registrations were edited or removed; preserve them or resolve the config conflict first')
        current = current.replace(block, '', 1)
    if BEGIN in current or END in current:
        raise ValueError('Unowned seo-codex managed block in project config')
    return current


def agent_block(files: dict[str, tuple[bytes, int, dict]], project: Path) -> str:
    blocks = []
    for relative, (data, _, _) in sorted(files.items()):
        if relative.startswith('.codex/agents/'):
            agent = tomllib.loads(data.decode())
            name = agent['name']
            if not re.fullmatch(r'seo-(?:full|codex)-[a-z0-9-]+', name):
                raise ValueError(f'Invalid agent name: {name}')
            blocks.append(f'[agents.{name}]\ndescription = {json.dumps(agent["description"])}\nconfig_file = {json.dumps(str(project / relative))}\n')
    return BEGIN + '\n'.join(blocks) + END


def substitute_paths(content: bytes, suffix: str, replacements: dict[str, str]) -> bytes:
    """Escape substitutions inside JSON/TOML strings while leaving prose readable."""
    if suffix not in {'.md', '.toml', '.json', '.txt'}:
        return content
    text = content.decode('utf-8')
    for token, value in replacements.items():
        if suffix in {'.toml', '.json'}:
            value = json.dumps(value, ensure_ascii=False)[1:-1]
        text = text.replace(token, value)
    return text.encode('utf-8')


def package_files(package: Path, project: Path, data_dir: Path) -> tuple[dict, dict]:
    manifest_path = safe_path(package, 'package-manifest.json')
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('schema_version') != 1 or manifest.get('name') != 'seo-codex':
        raise ValueError('Unsupported package manifest')
    installed_root = project / BASE / 'package'
    replacements = {'__CODEX_SEO_ROOT__': str(installed_root), '__CODEX_SEO_SKILLS_ROOT__': str(project / '.agents/skills'), '__CODEX_SEO_STATE_ROOT__': str(data_dir)}
    # Generated shell examples use double quotes; reject roots which would change
    # their meaning rather than silently producing executable shell fragments.
    if os.name != 'nt' and any(any(char in value for char in '\n\r"`$\\') for value in replacements.values()):
        raise ValueError('Installation paths cannot contain shell substitution or quoting characters')
    files = {}
    entries = list(manifest['files']) + [{'path': 'package-manifest.json', 'sha256': digest(manifest_path.read_bytes()), 'mode': 0o644}]
    seen = set()
    for entry in entries:
        relative = entry['path']
        if relative in seen:
            raise ValueError(f'Duplicate package path: {relative}')
        seen.add(relative)
        path = safe_path(package, relative)
        if not path.is_file():
            raise ValueError(f'Missing package file: {relative}')
        content = path.read_bytes()
        if digest(content) != entry['sha256']:
            raise ValueError(f'Package checksum mismatch: {relative}')
        resolved = content
        if relative != 'package-manifest.json':
            resolved = substitute_paths(content, path.suffix, replacements)
        mode = 0o755 if entry.get('mode') == 0o755 else 0o644
        files[(BASE / 'package' / relative).as_posix()] = (resolved, mode, entry)
        if relative.startswith('skills/'):
            destination = '.agents/' + relative
            owned_path(project, destination)
            files[destination] = (resolved, mode, entry)
        elif relative.startswith('agents/') and relative.endswith('.toml'):
            destination = '.codex/' + relative
            owned_path(project, destination)
            files[destination] = (resolved, mode, entry)
    return files, manifest


def apply_changes(project: Path, changes: dict[str, tuple[bytes, int] | None]) -> str:
    """Keep a durable pre-change backup and restore it if a write fails."""
    before = {}
    for relative in changes:
        path = safe_path(project, relative)
        if path.exists() and not path.is_file():
            raise ValueError(f'Expected a file: {path}')
        before[relative] = (path.read_bytes(), path.stat().st_mode & 0o777) if path.exists() else None
    backup_relative = BASE / 'backups' / f'{time.time_ns()}-{uuid.uuid4().hex[:8]}.json'
    backup = {'schema_version': 1, 'files': {name: {'data_base64': base64.b64encode(value[0]).decode(), 'mode': value[1]} if value else None for name, value in before.items()}}
    atomic_write(safe_path(project, backup_relative), (json.dumps(backup) + '\n').encode(), 0o600)
    completed = []
    try:
        for relative, value in changes.items():
            path = safe_path(project, relative)
            if value is None:
                if path.exists():
                    path.unlink()
            else:
                atomic_write(path, *value)
            completed.append(relative)
    except BaseException:
        for relative in reversed(completed):
            path = safe_path(project, relative)
            value = before[relative]
            if value is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, *value)
        raise
    return str(project / backup_relative)


def install(package: Path, project: Path, data_dir: Path | None = None) -> dict:
    package = absolute_directory(package)
    project = absolute_directory(project)
    data_dir = absolute_directory(data_dir or project / BASE / 'data')
    installed_root = project / BASE / 'package'
    if data_dir == installed_root or installed_root in data_dir.parents or data_dir in installed_root.parents:
        raise ValueError('Data directory must not overlap the installed package')
    if package == installed_root or package in installed_root.parents or installed_root in package.parents:
        raise ValueError('Package source and installation target must not overlap')
    files, package_manifest = package_files(package, project, data_dir)
    with installation_lock(project):
        previous = previous_install(project)
        old_entries = {entry['path']: entry for entry in previous['files']} if previous else {}
        conflicts = []
        for relative in set(files) | set(old_entries):
            path = owned_path(project, relative)
            if relative in old_entries:
                if not path.is_file() or digest(path.read_bytes()) != old_entries[relative]['sha256']:
                    conflicts.append(relative)
            elif path.exists():
                conflicts.append(relative)
        if conflicts:
            raise ValueError('Conflicting edits or unowned files: ' + ', '.join(sorted(conflicts)))
        config = safe_path(project, CONFIG)
        current = config.read_text() if config.exists() else ''
        remaining = config_without_owned_block(current, previous)
        block = agent_block(files, project)
        updated_config = remaining + ('\n' if remaining and not remaining.endswith('\n') else '') + block
        tomllib.loads(updated_config)  # catches duplicate registrations without rewriting other settings
        changes = {name: (value[0], value[1]) for name, value in files.items()}
        changes.update({name: None for name in old_entries.keys() - files.keys()})
        changes[CONFIG.as_posix()] = (updated_config.encode(), config.stat().st_mode & 0o777 if config.exists() else 0o600)
        manifest = {'schema_version': 1, 'name': 'seo-codex', 'source_ref': package_manifest.get('source_ref'), 'data_dir': str(data_dir), 'agent_block': block, 'files': [{'path': name, 'sha256': digest(value[0]), 'source': value[2].get('source'), 'package_path': value[2]['path'], 'package_sha256': value[2]['sha256']} for name, value in sorted(files.items())]}
        changes[MANIFEST.as_posix()] = ((json.dumps(manifest, indent=2) + '\n').encode(), 0o600)
        backup = apply_changes(project, changes)
    return {'status': 'installed', 'files': len(files), 'package_root': str(installed_root), 'data_dir': str(data_dir), 'backup': backup}


def uninstall(project: Path) -> dict:
    project = absolute_directory(project)
    with installation_lock(project):
        previous = previous_install(project)
        if previous is None:
            return {'status': 'not-installed', 'conflicts': []}
        changes = {}
        retained = []
        for entry in previous['files']:
            path = owned_path(project, entry['path'])
            if path.is_file() and digest(path.read_bytes()) == entry['sha256']:
                changes[entry['path']] = None
            elif path.exists():
                retained.append(entry)
        config = safe_path(project, CONFIG)
        config_conflict = False
        try:
            current = config.read_text() if config.exists() else ''
            remaining = config_without_owned_block(current, previous)
            tomllib.loads(remaining)
            changes[CONFIG.as_posix()] = (remaining.encode(), config.stat().st_mode & 0o777) if config.exists() else None
        except ValueError:
            config_conflict = True
        if retained or config_conflict:
            previous['files'] = retained
            if not config_conflict:
                previous['agent_block'] = ''
            changes[MANIFEST.as_posix()] = ((json.dumps(previous, indent=2) + '\n').encode(), 0o600)
        else:
            changes[MANIFEST.as_posix()] = None
        backup = apply_changes(project, changes)
    conflicts = [item['path'] for item in retained]
    if config_conflict:
        conflicts.append(CONFIG.as_posix())
    return {'status': 'conflicts-preserved' if conflicts else 'uninstalled', 'conflicts': conflicts, 'backup': backup, 'data_dir': previous['data_dir']}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    add = commands.add_parser('install')
    add.add_argument('--package', type=Path, required=True)
    add.add_argument('--project', type=Path, required=True)
    add.add_argument('--data-dir', type=Path)
    remove = commands.add_parser('uninstall')
    remove.add_argument('--project', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = install(args.package, args.project, args.data_dir) if args.command == 'install' else uninstall(args.project)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        parser.exit(2, f'{error}\n')
    print(json.dumps(result, indent=2))
    return 1 if result['status'] == 'conflicts-preserved' else 0


if __name__ == '__main__':
    raise SystemExit(main())
