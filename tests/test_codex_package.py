"""Focused ownership and rollback checks for the complete Codex installer."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('install_codex', ROOT / 'scripts/install_codex.py')
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)
PACKAGE_SPEC = importlib.util.spec_from_file_location('package_codex', ROOT / 'scripts/package_codex.py')
packager = importlib.util.module_from_spec(PACKAGE_SPEC)
PACKAGE_SPEC.loader.exec_module(packager)


def package_at(path: Path, text: str = 'version one') -> Path:
    files = {
        'skills/seo-codex/SKILL.md': f'---\nname: seo-codex\ndescription: Test\n---\n{text}\n__CODEX_SEO_ROOT__ __CODEX_SEO_STATE_ROOT__ __CODEX_SEO_SKILLS_ROOT__\n',
        'agents/seo-full-test.toml': 'name = "seo-full-test"\ndescription = "Test"\ndeveloper_instructions = "Read __CODEX_SEO_SKILLS_ROOT__/seo-codex/SKILL.md"\n',
        'scripts/codex-seo': '#!/bin/sh\nexit 0\n',
        'LICENSE': 'MIT attribution',
    }
    manifest = {'name': 'seo-codex', 'schema_version': 1, 'source_ref': 'test', 'files': []}
    for name, value in files.items():
        destination = path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        content = value.encode()
        destination.write_bytes(content)
        manifest['files'].append({'path': name, 'sha256': hashlib.sha256(content).hexdigest(), 'source': name, 'mode': 0o755 if name.endswith('codex-seo') else 0o644})
    (path / 'package-manifest.json').write_text(json.dumps(manifest))
    return path


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='codex install ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.package = package_at(self.root / 'package')
        self.project = self.root / 'project'
        self.project.mkdir()
        (self.project / '.codex').mkdir()
        self.original = 'model = "test-model"\n\n[agents.unrelated]\nconfig_file = "custom.toml"\n'
        (self.project / '.codex/config.toml').write_text(self.original)

    def test_install_upgrade_uninstall_preserves_unrelated(self):
        installer.install(self.package, self.project)
        skill = self.project / '.agents/skills/seo-codex/SKILL.md'
        self.assertNotIn('__CODEX_', skill.read_text())
        self.assertIn(str(self.project / '.codex/seo-codex/package'), skill.read_text())
        config = self.project / '.codex/config.toml'
        self.assertTrue(config.read_text().startswith(self.original))
        package_at(self.package, 'version two')
        installer.install(self.package, self.project)
        self.assertIn('version two', skill.read_text())
        config.write_text(config.read_text() + '\n[profiles.custom]\nmodel = "another"\n')
        (self.project / '.codex/seo-codex/data').mkdir()
        (self.project / '.codex/seo-codex/data/user.txt').write_text('keep')
        result = installer.uninstall(self.project)
        self.assertEqual(result['status'], 'uninstalled')
        self.assertFalse(skill.exists())
        self.assertIn('[profiles.custom]', config.read_text())
        self.assertIn('[agents.unrelated]', config.read_text())
        self.assertTrue((self.project / '.codex/seo-codex/data/user.txt').exists())
        self.assertTrue(list((self.project / '.codex/seo-codex/backups').glob('*.json')))

    def test_edits_refuse_upgrade_and_survive_uninstall(self):
        installer.install(self.package, self.project)
        skill = self.project / '.agents/skills/seo-codex/SKILL.md'
        skill.write_text('user modification')
        with self.assertRaisesRegex(ValueError, 'Conflicting edits'):
            installer.install(self.package, self.project)
        result = installer.uninstall(self.project)
        self.assertEqual(result['status'], 'conflicts-preserved')
        self.assertEqual(skill.read_text(), 'user modification')
        self.assertIn('.agents/skills/seo-codex/SKILL.md', result['conflicts'])

    def test_tampered_package_is_rejected_before_install(self):
        (self.package / 'LICENSE').write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            installer.install(self.package, self.project)
        self.assertFalse((self.project / '.agents').exists())

    def test_unowned_namespace_file_is_never_replaced(self):
        skill = self.project / '.agents/skills/seo-codex/SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('existing user skill')
        with self.assertRaisesRegex(ValueError, 'unowned files'):
            installer.install(self.package, self.project)
        self.assertEqual(skill.read_text(), 'existing user skill')

    def test_invalid_manifest_and_symlinks_are_rejected(self):
        manifest = json.loads((self.package / 'package-manifest.json').read_text())
        manifest['files'][0]['path'] = '../outside'
        (self.package / 'package-manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'Unsafe relative path'):
            installer.install(self.package, self.project)
        other = self.root / 'other'
        other.mkdir()
        try:
            (self.project / '.agents').symlink_to(other, target_is_directory=True)
        except OSError:
            if os.name == 'nt':
                self.skipTest('Windows symlink creation requires an enabled privilege')
            raise
        package_at(self.package)
        with self.assertRaisesRegex(ValueError, 'Symlink'):
            installer.install(self.package, self.project)

    def test_windows_paths_are_escaped_in_structured_resources(self):
        windows_path = r'C:\Users\User Name\project\.codex\seo-codex\package'
        replacements = {'__CODEX_SEO_ROOT__': windows_path}
        toml = installer.substitute_paths(b'path = "__CODEX_SEO_ROOT__"', '.toml', replacements)
        self.assertEqual(tomllib.loads(toml.decode())['path'], windows_path)
        json_text = installer.substitute_paths(b'{"path": "__CODEX_SEO_ROOT__"}', '.json', replacements)
        self.assertEqual(json.loads(json_text)['path'], windows_path)
        markdown = installer.substitute_paths(b'Root __CODEX_SEO_ROOT__', '.md', replacements)
        self.assertEqual(markdown.decode(), 'Root ' + windows_path)

    def test_changed_config_blocks_upgrade_and_is_preserved(self):
        installer.install(self.package, self.project)
        config = self.project / '.codex/config.toml'
        changed = config.read_text().replace('description = "Test"', 'description = "My edits"')
        config.write_text(changed)
        with self.assertRaisesRegex(ValueError, 'registrations were edited'):
            installer.install(self.package, self.project)
        result = installer.uninstall(self.project)
        self.assertIn('.codex/config.toml', result['conflicts'])
        self.assertEqual(config.read_text(), changed)

    def test_upgrade_removes_retired_owned_files_only(self):
        installer.install(self.package, self.project)
        keep = self.project / '.agents/skills/seo-codex/user-notes.md'
        keep.write_text('keep user notes')
        manifest_path = self.package / 'package-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['files'] = [entry for entry in manifest['files'] if entry['path'] != 'LICENSE']
        manifest_path.write_text(json.dumps(manifest))
        installer.install(self.package, self.project)
        self.assertFalse((self.project / '.codex/seo-codex/package/LICENSE').exists())
        self.assertEqual(keep.read_text(), 'keep user notes')

    def test_failure_rolls_back_changed_files(self):
        target = self.project / 'one.txt'
        target.write_text('original')
        real = installer.atomic_write

        def failing(path, data, mode=0o644):
            if path.name == 'two.txt':
                raise OSError('simulated failure')
            real(path, data, mode)

        with patch.object(installer, 'atomic_write', side_effect=failing):
            with self.assertRaisesRegex(OSError, 'simulated failure'):
                installer.apply_changes(self.project, {'one.txt': (b'changed', 0o644), 'two.txt': (b'new', 0o644)})
        self.assertEqual(target.read_text(), 'original')
        self.assertFalse((self.project / 'two.txt').exists())


class PackageTests(unittest.TestCase):
    def test_source_inventory_hashes_and_private_file_exclusion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / 'source'
            source.mkdir()
            names = ['scripts/codex-seo', 'scripts/tool.py', 'hooks/validate-schema.py',
                     'requirements.txt', 'pyproject.toml', 'LICENSE', 'CONTRIBUTORS.md',
                     'CITATION.cff', 'plugin.json', 'docs/codex/INSTALL.md', 'docs/codex/FULL-PORT.md',
                     'skills/seo-flow/references/notice.md', 'schema/templates.json',
                     'data/google-updates.json', 'extensions/banana/scripts/test.py']
            for name in names:
                file = source / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text('fixture ' + name)
            subprocess.run(['git', 'init', '-q', str(source)], check=True)
            subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
            (source / 'skills/private-credentials.json').write_text('secret excluded')
            (source / 'extensions/banana/.env').write_text('secret excluded')
            full = source / 'adapters/codex/full'
            skill = full / 'skills/seo-codex/SKILL.md'
            skill.parent.mkdir(parents=True)
            skill.write_text('native skill')
            (full / 'unlisted-secret.json').write_text('secret excluded')
            upstream = {'files': [{'destination': 'skills/seo-codex/SKILL.md',
                                   'sha256': packager.digest(skill.read_bytes())}]}
            (full / 'source-manifest.json').write_text(json.dumps(upstream))
            output = root / 'output'
            manifest = packager.build(output, 'fixture-ref', source)
            actual = {entry['path'] for entry in manifest['files']}
            self.assertIn('source-skills/seo-flow/references/notice.md', actual)
            self.assertIn('extensions/banana/scripts/test.py', actual)
            self.assertIn('skills/seo-codex/SKILL.md', actual)
            self.assertFalse(any('secret' in name or '.env' in name for name in actual))
            self.assertEqual(manifest['source_ref'], 'fixture-ref')
            for entry in manifest['files']:
                self.assertEqual(packager.digest((output / entry['path']).read_bytes()), entry['sha256'])
            with self.assertRaisesRegex(ValueError, 'already exist'):
                packager.build(output, 'fixture-ref', source)
            skill.write_text('tampered generated skill')
            with self.assertRaisesRegex(ValueError, 'Generated file changed'):
                packager.build(root / 'another-output', 'fixture-ref', source)


if __name__ == '__main__':
    unittest.main()
