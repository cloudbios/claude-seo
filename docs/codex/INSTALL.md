# Install the complete Codex distribution

Build from the repository with Python 3.11–3.14. Use new absolute paths for the package output and a project where you want the skills available.

```bash
python3 scripts/build_codex_skills.py
python3 scripts/package_codex.py --output /absolute/path/seo-codex-package
python3 scripts/install_codex.py install \
  --package /absolute/path/seo-codex-package \
  --project /absolute/path/your-project
```

The installer places namespaced skills in `.agents/skills/seo-codex*`, native agent files in `.codex/agents/`, and the runtime in `.codex/seo-codex/package/`. It appends a marked agent registration block to the project's `.codex/config.toml`, preserving the existing text and settings. Existing files with conflicting ownership or modified installed content stop an upgrade before its file writes.

The default data directory is `.codex/seo-codex/data/` inside the target project. Pass `--data-dir /absolute/dedicated/path` to choose another directory. The installer resolves skill and agent resource paths to the chosen installation, including projects with spaces in their names. POSIX paths containing shell substitution or quoting characters are rejected. Windows paths are escaped when written into TOML and JSON.

Prepare and check the runtime explicitly after installation.

```bash
/absolute/path/your-project/.codex/seo-codex/package/scripts/codex-seo \
  --state-root /absolute/path/your-project/.codex/seo-codex/data setup
/absolute/path/your-project/.codex/seo-codex/package/scripts/codex-seo \
  --state-root /absolute/path/your-project/.codex/seo-codex/data doctor --json
```

On Windows, run the Python entrypoint directly from PowerShell. The `codex-seo` launcher requires Bash.

```powershell
python "C:\path\your-project\.codex\seo-codex\package\scripts\codex_runtime.py" --state-root "C:\path\your-project\.codex\seo-codex\data" setup
python "C:\path\your-project\.codex\seo-codex\package\scripts\codex_runtime.py" --state-root "C:\path\your-project\.codex\seo-codex\data" doctor --json
```

Use the same direct Python entrypoint for `run` commands in generated skill instructions on Windows.

`setup` downloads dependencies and may prepare the browser. Use `setup --skip-browser` when browser installation is outside your intended setup. The launcher discovers a supported Python interpreter or accepts an explicit executable through `CODEX_SEO_PYTHON`. Commands, package installation, provider authentication, write operations and paid APIs remain subject to the caller's authorization. Credentials belong in the dedicated data directory through the runtime's configuration flow.

Unlighthouse also requires Node.js. Its normal helper invocation uses only the
prepared npm cache. Authorize the pinned package download explicitly with
`run --allow-install unlighthouse_run.py <url>` when preparing that capability.
This option is separate from `--allow-write`, which gates external mutations.

Start a new Codex session in the target project and invoke `$seo-codex`. Project agent settings load when Codex trusts the project. Review that trust decision in Codex. Hooks have a separate trust boundary. The distribution includes the explicit schema validation helper, and the installer adds no hook registrations. Configure any desired lifecycle hooks only after reviewing their commands and trusting their current definitions. [OpenAI plugin documentation](https://developers.openai.com/plugins/build/plugins)

## Upgrade and uninstall

Build a new package directory and rerun the same installation command. Upgrade checks the recorded hashes of owned files and keeps durable pre-change backups under `.codex/seo-codex/backups/`. On a write failure, it restores files changed by that invocation. A leftover `.install.lock` after an interrupted process needs operator review before removal.

```bash
python3 /absolute/path/seo-codex-package/scripts/install_codex.py uninstall \
  --project /absolute/path/your-project
```

Uninstall removes unchanged manifest-owned files and the exact managed agent block. It retains modified files, unrelated skills/settings, runtime data and backup records, reporting any conflicts and returning a nonzero status. Review and resolve retained changes before retrying. Empty parent directories may remain.

`package-manifest.json` records source references, source hashes and distributed hashes. `install-manifest.json` records each owned target path, installed hash, source provenance and the exact agent block. The package includes the MIT license, upstream contributors and citations, and the original FLOW attribution and CC BY notices alongside adapted resources.

## Distribution and native-plugin loading

The generated package has a root `plugin.json` using the documented Agent Plugins 1.0.0 schema and a root `skills/` directory. It can be used as an input to a local plugin marketplace. Root repository skills are the upstream source set, so distribute the generated package directory. The project installer also makes native TOML agents available through explicit project registrations. Plugin discovery, project trust and native agent acceptance should be checked in the target Codex client before release. [OpenAI plugin packaging documentation](https://developers.openai.com/plugins/build/plugins)
