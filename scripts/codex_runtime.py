#!/usr/bin/env python3
"""Full prepared Codex runtime. Uses only stdlib until managed dispatch.

The explicit state root owns config/, cache/, runtime/. No legacy state or
ambient Python, proxy, cloud SDK or package-manager settings are inherited.
Only the provider environment keys listed in PROVIDER_ENV are opt-in inputs.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent


def _sibling(name):
    spec = importlib.util.spec_from_file_location('_codex_' + name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


legacy = _sibling('runtime')
paths_module = _sibling('state_paths')
CORE_SCRIPTS = legacy.ALLOWED_CORE_SCRIPTS | legacy.CODEX_ALLOWED_SCRIPTS | {"codex_full_audit.py"}
EXTENSIONS = {'banana': frozenset({'generate.py', 'edit.py', 'batch.py', 'cost_tracker.py', 'presets.py', 'setup_mcp.py', 'validate_setup.py'})}
# Per-script inputs, intentionally excluding credential paths/ADC, HOME, PATH,
# PYTHON*, HTTP(S)_PROXY, PIP_*, and all legacy host configuration.
GOOGLE_ENV = ('GOOGLE_API_KEY', 'GA4_PROPERTY_ID', 'GSC_PROPERTY')
BACKLINK_ENV = ('MOZ_API_KEY', 'BING_WEBMASTER_API_KEY', 'KEYWORDSEVERYWHERE_API_KEY')
MATOMO_ENV = ('MATOMO_URL', 'MATOMO_API_TOKEN', 'MATOMO_TOKEN', 'MATOMO_SITE_ID', 'MATOMO_IDSITE')
PROVIDER_ENV = {name: GOOGLE_ENV for name in ('google_auth.py', 'ga4_report.py', 'gsc_query.py', 'gsc_inspect.py', 'indexing_notify.py', 'pagespeed_check.py', 'crux_history.py', 'google_report.py', 'keyword_planner.py', 'nlp_analyze.py', 'youtube_search.py')}
PROVIDER_ENV.update({name: BACKLINK_ENV for name in ('backlinks_auth.py', 'moz_api.py', 'bing_webmaster.py', 'keywordseverywhere_api.py', 'domain_history.py', 'commoncrawl_graph.py')})
PROVIDER_ENV.update({name: MATOMO_ENV for name in ('matomo_auth.py', 'matomo_report.py')})
PROVIDER_ENV.update({name: ('DATAFORSEO_USERNAME', 'DATAFORSEO_PASSWORD') for name in ('dataforseo_costs.py', 'dataforseo_merchant.py')})
PROVIDER_ENV['indexnow_submit.py'] = ('INDEXNOW_KEY', 'INDEXNOW_KEY_LOCATION')
SCHEMA = 1


def executable_path():
    """Find platform-installed tools without inheriting the caller's PATH."""
    directories = os.defpath.split(os.pathsep)
    if sys.platform == 'darwin':
        directories.extend(['/opt/homebrew/bin', '/usr/local/bin'])
    elif sys.platform == 'win32':
        directories.append(str(Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'nodejs'))
    else:
        directories.append('/usr/local/bin')
    return os.pathsep.join(dict.fromkeys(directories))


def environment(paths, script=None, extension=None, allow_write=False, allow_install=False):
    env = legacy._codex_env(paths)
    env['PATH'] = executable_path()
    env['PLAYWRIGHT_BROWSERS_PATH'] = str(paths['runtime'] / 'ms-playwright')
    env['PIP_CONFIG_FILE'] = os.devnull
    env['PIP_CACHE_DIR'] = str(paths['cache'] / 'pip')
    env['NETRC'] = os.devnull
    env['MPLCONFIGDIR'] = str(paths['cache'] / 'matplotlib')
    env['XDG_CONFIG_HOME'] = str(paths['config'])
    env['XDG_CACHE_HOME'] = str(paths['cache'])
    env['NPM_CONFIG_CACHE'] = str(paths['cache'] / 'npm')
    env['NPM_CONFIG_USERCONFIG'] = os.devnull
    env['NPM_CONFIG_GLOBALCONFIG'] = os.devnull
    keys = PROVIDER_ENV.get(script, ()) if script else ()
    if extension == 'banana':
        keys = ('GOOGLE_AI_API_KEY', 'GOOGLE_API_KEY', 'NANOBANANA_MODEL')
    env.update({key: os.environ[key] for key in keys if key in os.environ})
    if allow_write:
        env['CODEX_SEO_ALLOW_WRITE'] = '1'
    if allow_install:
        env['CODEX_SEO_ALLOW_INSTALL'] = '1'
    return env


def resolve_script(name, extension=None):
    if not legacy.SCRIPT_NAME_RE.fullmatch(name):
        raise ValueError('Use a bundled script basename')
    if extension is None:
        if name not in CORE_SCRIPTS:
            raise ValueError('Script is not in the audited Codex allowlist')
        directory = ROOT / 'scripts'
    else:
        if name not in EXTENSIONS.get(extension, ()):
            raise ValueError('Extension script is not in the audited Codex allowlist')
        directory = ROOT / 'extensions' / extension / 'scripts'
    target = directory / name
    for part in (target, *target.parents):
        if part == ROOT.parent:
            break
        if part.is_symlink():
            raise ValueError('Bundled scripts must not contain symlinks')
    if not target.is_file() or target.resolve().parent != directory.resolve():
        raise ValueError('Bundled script is missing or outside the prepared source')
    return target


def requires_write(name, args, extension=None):
    """Conservative capability gate; help and explicit inspections are safe."""
    if args in (['--help'], ['-h']):
        return False
    if extension == 'banana':
        if name in ('generate.py', 'edit.py'):
            return True
        if name == 'setup_mcp.py':
            return '--check' not in args
        if name == 'presets.py':
            return not args or args[0] not in ('list', 'show')
        if name == 'cost_tracker.py':
            return bool(args and args[0] in ('log', 'budget', 'reset'))
    if name == 'indexing_notify.py':
        return not any(arg.startswith('--status=') and bool(arg.split('=', 1)[1]) or (arg == '--status' and i + 1 < len(args) and bool(args[i + 1]) and not args[i + 1].startswith('-')) for i, arg in enumerate(args))
    if name == 'indexnow_submit.py':
        return True
    if name in ('content_humanize.py', 'agentic_fix.py'):
        return True
    if name == 'iptc_ai_label.py':
        return bool(args and args[0] == 'inject')
    if name == 'dataforseo_costs.py':
        return bool(args and (args[0] in ('log', 'reset') or (args[0] == 'config' and len(args) > 1)))
    if name == 'sync_flow.py':
        return '--dry-run' not in args
    if name == 'google_auth.py':
        return any(arg.startswith('--') and any(flag.startswith(arg.split('=')[0]) for flag in ('--auth', '--exchange')) for arg in args)
    if name in ('backlinks_auth.py', 'matomo_auth.py'):
        return any(arg.startswith(('--set', '--save', '--remove')) for arg in args)
    return False


def status(paths):
    data = paths['runtime']
    expected = legacy._expected(ROOT)
    expected['codex_runtime_schema'] = SCHEMA
    state = legacy._load_state(data)
    python = legacy._venv_python(data / '.venv')
    reasons = []
    if not legacy._python_supported():
        reasons.append('Python 3.11 through 3.14 is required')
    if not python.is_file():
        reasons.append('Managed environment is missing; run setup')
    for key in ('runtime_schema', 'requirements_sha256', 'python', 'codex_runtime_schema'):
        if state.get(key) != expected[key]:
            reasons.append(f'{key} differs; run setup')
    for path in (data / '.venv', data / 'runtime-state.json', data / 'ms-playwright'):
        if path.is_symlink():
            raise ValueError('Managed runtime paths must not be symlinks')
    browser_dir = data / 'ms-playwright'
    browsers = browser_dir.is_dir() and any(p.name.startswith(('chromium-', 'chromium_headless_shell-')) for p in browser_dir.iterdir())
    return dict(ready=not reasons, reasons=reasons, python_path=python, expected=expected,
                browser_ready=bool(state.get('browser_ready')) and browsers)


def doctor(paths, args):
    current = status(paths)
    public = {k: current[k] for k in ('ready', 'reasons', 'browser_ready')}
    public.update(host='codex', mode='full', credentials='not inspected',
                  python_version=f'{sys.version_info.major}.{sys.version_info.minor}',
                  core_scripts=len(CORE_SCRIPTS), extensions=sorted(EXTENSIONS),
                  state_policy='explicit-root-no-legacy-fallback')
    if args.json:
        print(json.dumps(public, indent=2, sort_keys=True))
    else:
        print('Codex full runtime: ' + ('ready' if current['ready'] else 'setup required'))
        for reason in current['reasons']:
            print('Reason: ' + reason)
    return 0 if current['ready'] else 3


def setup(paths, args):
    if not legacy._python_supported():
        raise ValueError('Codex requires Python 3.11 through 3.14')
    data = paths['runtime']
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    final = data / '.venv'
    backup = data / '.venv.previous'
    staged = data / f'.venv.next-{os.getpid()}'
    temporary = data / '.runtime-state.next'
    env = environment(paths)
    previous_moved = swapped = committed = False
    with legacy.SetupLock(data / '.setup.lock'):
        for path in (final, backup, staged, temporary, data / 'runtime-state.json', data / 'ms-playwright'):
            if path.is_symlink():
                raise ValueError('Managed runtime paths must not be symlinks')
        prior = legacy._load_state(data)
        if final.exists() and prior.get('codex_runtime_schema') != SCHEMA:
            raise ValueError('Refusing to replace an unmanaged environment; choose an empty state root')
        if staged.exists() or backup.exists() or temporary.exists():
            raise ValueError('Incomplete setup artifacts exist; inspect runtime state before retrying')
        try:
            print('Creating isolated Codex SEO environment...', flush=True)
            legacy._run_checked([sys.executable, '-I', '-B', '-m', 'venv', '--without-pip', str(staged)], env=env, stage='virtual environment creation')
            python = legacy._venv_python(staged)
            legacy._run_checked([str(python), '-I', '-B', '-m', 'ensurepip', '--upgrade', '--default-pip'], env=env, stage='pip bootstrap')
            legacy._run_checked([str(python), '-I', '-B', '-m', 'pip', 'install', '--disable-pip-version-check', '-r', str(ROOT / 'requirements.txt')], env=env, stage='dependency installation')
            browser_ready = False
            if not args.skip_browser:
                try:
                    legacy._run_checked([str(python), '-I', '-B', '-m', 'playwright', 'install', 'chromium'], env=env, stage='Chromium installation')
                    browser_ready = True
                except RuntimeError:
                    print('Chromium installation failed; core setup will remain usable', file=sys.stderr)
            legacy._run_checked([str(python), '-I', '-B', '-c', 'import bs4, lxml, lxml_html_clean, playwright, requests, trafilatura, google.auth'], env=env, stage='runtime import validation')
            if final.exists():
                final.replace(backup)
                previous_moved = True
            staged.replace(final)
            swapped = True
            manifest = status(paths)['expected']
            manifest['browser_ready'] = browser_ready
            temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
            temporary.replace(legacy._state_path(data))
            committed = True
            if backup.exists():
                shutil.rmtree(backup)
        except BaseException:
            if staged.exists():
                shutil.rmtree(staged)
            temporary.unlink(missing_ok=True)
            if not committed:
                if swapped:
                    shutil.rmtree(final)
                if previous_moved:
                    backup.replace(final)
            raise
    print('Codex SEO runtime is ready.')
    return 0 if args.skip_browser or browser_ready else 10


def _redacted_output(text, env, paths):
    values = []
    for key, value in env.items():
        if any(word in key for word in ('KEY', 'TOKEN', 'PASSWORD', 'SECRET', 'USERNAME')):
            values.append(value)
    # Read only explicit state, never home credentials. Provider errors sometimes
    # echo key material without a label, so also mask known secret JSON fields.
    def collect(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str) and any(word in key.lower() for word in ('key', 'token', 'password', 'secret', 'username', 'authorization')):
                    values.append(value)
                elif isinstance(value, (dict, list)):
                    collect(value)
        elif isinstance(obj, list):
            for item in obj:
                collect(item)
    for file in paths['config'].rglob('*.json'):
        if any(p.is_symlink() for p in (file, *file.parents)) or file.stat().st_size > 1024 * 1024:
            continue
        try:
            collect(json.loads(file.read_text(encoding='utf-8')))
        except (OSError, ValueError):
            pass
    for value in sorted(set(values), key=len, reverse=True):
        if value:
            text = text.replace(value, '<redacted>')
    return legacy._redact(text)


def run(paths, args):
    script = resolve_script(args.script, args.extension)
    if requires_write(args.script, args.script_args, args.extension) and not args.allow_write:
        raise ValueError('This operation requires run --allow-write before the script name')
    current = status(paths)
    if not current['ready']:
        print('Codex runtime needs setup; run setup with the same --state-root', file=sys.stderr)
        return 3
    env = environment(paths, args.script, args.extension, args.allow_write, getattr(args, 'allow_install', False))
    # -I drops the script directory. Add only audited bundled import directories;
    # never the working directory or caller-controlled PYTHONPATH.
    bootstrap = "import runpy,sys;sys.path[:0]=sys.argv[1:3];p=sys.argv[3];sys.argv=sys.argv[3:];runpy.run_path(p,run_name='__main__')"
    result = subprocess.run([str(current['python_path']), '-I', '-B', '-c', bootstrap,
                             str(script.parent), str(ROOT / 'scripts'), str(script), *args.script_args],
                            env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    sys.stdout.write(_redacted_output(result.stdout, env, paths))
    sys.stderr.write(_redacted_output(result.stderr, env, paths))
    return legacy._propagate_result(result)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-root', required=True, help='Absolute dedicated Codex state root')
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('doctor')
    check.add_argument('--json', action='store_true')
    install = sub.add_parser('setup')
    install.add_argument('--skip-browser', action='store_true')
    dispatch = sub.add_parser('run')
    dispatch.add_argument('--extension', choices=sorted(EXTENSIONS))
    dispatch.add_argument('--allow-write', action='store_true')
    dispatch.add_argument('--allow-install', action='store_true', help='Allow dependency downloads for this invocation')
    dispatch.add_argument('script')
    dispatch.add_argument('script_args', nargs=argparse.REMAINDER)
    return parser


def main(argv=None):
    legacy._configure_utf8()
    args = build_parser().parse_args(argv)
    paths = None
    try:
        paths = paths_module.resolve_codex_paths(args.state_root, ROOT)
        return {'doctor': doctor, 'setup': setup, 'run': run}[args.command](paths, args)
    except ValueError as exc:
        print('Codex runtime: ' + legacy._redact(str(exc)), file=sys.stderr)
        return 2
    except (OSError, RuntimeError) as exc:
        # Do not echo dependency/provider exception bodies, credential paths or
        # user-supplied secret arguments into diagnostics.
        if args.command == 'setup' and paths is not None:
            print('Codex setup: ' + _redacted_output(str(exc), {}, paths), file=sys.stderr)
        else:
            print('Codex runtime could not complete the command. Check explicit state paths, Python 3.11–3.14, setup readiness, bundled script names, and run --allow-write for mutations.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
