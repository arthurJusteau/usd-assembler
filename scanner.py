"""
Asset scanning and project management
"""
import os
import json
from pathlib import Path

from usda_io import read_sublayer_paths

USD_EXTS = ('.usda', '.usdc')


# Per entity-type task lists used for assembly creation
ASSEMBLY_TASKS = {
    'asset':  ['Cfx', 'Fx', 'Layout', 'Lighting', 'Modeling', 'Shading'],
    'shot':   ['Animation', 'Cfx', 'CharFx', 'Fx', 'Layout', 'Lighting'],
    'previz': ['Animation', 'Layout', 'Lighting', 'Tracking'],
}

# Category prefix filters
CATEGORY_PREFIXES = {
    'character':   ('char',),
    'environment': ('env', 'subEnv'),
    'fx':          ('fx',),
    'props':       ('prp',),
}


def assembly_filename(entity_type, entity_name, assembly_name, task_cap):
    if entity_type == 'asset':
        return f"asset_{entity_name}_{assembly_name}{task_cap}.usda"
    return f"{entity_name}_{assembly_name}{task_cap}.usda"


class ProjectManager:
    @staticmethod
    def find_project_path():
        env = os.environ.get('PIPELINE_PROJECT_PATH')
        if env and Path(env).exists():
            return Path(env)
        return None


class AssetScanner:

    def __init__(self, project_path):
        self.project_path = Path(project_path)
        self.assets_path  = self.project_path / "assets"
        self.shots_path   = self.project_path / "shots"

    # ── Path helpers ──────────────────────────────────────────────────────────

    def _pub(self, entity_type, name):
        base = self.assets_path if entity_type == 'asset' else self.shots_path
        return base / name / "pub"

    def _assembly_base(self, entity_type, name):
        return self._pub(entity_type, name) / "assembly"

    # ── Entity lists ──────────────────────────────────────────────────────────

    def get_assets(self, category=None):
        if not self.assets_path.exists():
            return []
        assets = sorted(
            d.name for d in self.assets_path.iterdir()
            if d.is_dir() and not d.name.startswith('_')
        )
        if category and category in CATEGORY_PREFIXES:
            prefixes = CATEGORY_PREFIXES[category]
            assets = [a for a in assets if any(a.startswith(p) for p in prefixes)]
        return assets

    def get_sequences(self):
        """Return sorted unique sequence prefixes (e.g. sc010, sc020)."""
        if not self.shots_path.exists():
            return []
        seqs = set()
        for d in self.shots_path.iterdir():
            if d.is_dir() and d.name.startswith('sc') and not d.name.startswith('_'):
                idx = d.name.find('sh')
                seqs.add(d.name[:idx] if idx > 0 else d.name)
        return sorted(seqs)

    def get_shots(self, sequence=None):
        if not self.shots_path.exists():
            return []
        shots = sorted(
            d.name for d in self.shots_path.iterdir()
            if d.is_dir() and d.name.startswith('sc') and not d.name.startswith('_')
        )
        if sequence:
            shots = [s for s in shots if s.startswith(sequence)]
        return shots

    def get_previz(self):
        if not self.shots_path.exists():
            return []
        return sorted(
            d.name for d in self.shots_path.iterdir()
            if d.is_dir() and d.name.startswith('pvz') and not d.name.startswith('_')
        )

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def get_tasks(self, entity_type, name):
        """Return {task_name: has_usd} for the given entity."""
        pub = self._pub(entity_type, name)
        if not pub.exists():
            return {}
        if entity_type == 'previz':
            allowed = {'animation', 'layout', 'lighting', 'tracking'}
            dirs = [d for d in pub.iterdir() if d.is_dir() and d.name in allowed]
        else:
            excluded = {'assembly', 'client', 'online'}
            dirs = [d for d in pub.iterdir() if d.is_dir() and d.name not in excluded]
        return {d.name: self._has_usd_files(d) for d in dirs}

    # ── USD files ─────────────────────────────────────────────────────────────

    def get_usd_files(self, entity_type, name, task_name):
        """Return sorted list of file_info for latest USD per output."""
        task_path = self._pub(entity_type, name) / task_name
        if not task_path.exists():
            return []

        match = (lambda n, f: 'asset_' in f) if entity_type == 'asset' else (lambda n, f: n in f)
        results = []

        for output_dir in task_path.iterdir():
            if not output_dir.is_dir():
                continue
            fi = self._latest_usd(output_dir, name, match)
            if fi:
                results.append(fi)

        return sorted(results, key=lambda x: x['output_name'])

    def _latest_usd(self, output_dir, name, match_fn):
        # Fast path: latest folder
        latest = output_dir / "latest" / "usda"
        if latest.exists():
            for f in latest.iterdir():
                if f.suffix in USD_EXTS and match_fn(name, f.name):
                    return {'file': f, 'version': 'latest',
                            'output_name': output_dir.name,
                            'metadata': self._get_metadata(latest)}
        # Fallback: highest versioned folder
        best, best_v = None, -1
        for vdir in output_dir.iterdir():
            if not (vdir.is_dir() and vdir.name.startswith('v') and vdir.name[1:].isdigit()):
                continue
            v = int(vdir.name[1:])
            if v <= best_v:
                continue
            usda_dir = vdir / "usda"
            if not usda_dir.exists():
                continue
            for f in usda_dir.iterdir():
                if f.suffix in USD_EXTS and match_fn(name, f.name):
                    best = {'file': f, 'version': vdir.name,
                            'output_name': output_dir.name,
                            'metadata': self._get_metadata(usda_dir)}
                    best_v = v
                    break
        return best

    # ── Assemblies ────────────────────────────────────────────────────────────

    def get_available_assemblies(self, entity_type, name):
        base = self._assembly_base(entity_type, name)
        if not base.exists():
            return []
        # Sort tasks longest-first so "CharFx" is matched before "Fx"
        known = sorted(ASSEMBLY_TASKS[entity_type], key=len, reverse=True)
        assemblies = set()
        for folder in base.iterdir():
            if not folder.is_dir():
                continue
            fn = folder.name
            if fn.endswith("Assembly"):
                assemblies.add(fn[:-8])
            else:
                for task in known:
                    if fn.endswith(task) and fn != task:
                        prefix = fn[:-len(task)]
                        # Only valid if the prefix is non-empty and not itself a task name
                        if prefix and prefix not in known:
                            assemblies.add(prefix)
                            break
        return sorted(assemblies)

    def get_existing_assembly(self, entity_type, name, task_name, assembly_name):
        folder   = f"{assembly_name}{task_name.title()}"
        usda_dir = self._assembly_base(entity_type, name) / folder / "latest" / "usda"
        if not usda_dir.exists():
            return []
        fname = assembly_filename(entity_type, name, assembly_name, task_name.title())
        afile = usda_dir / fname
        if not afile.exists():
            return []
        try:
            paths = read_sublayer_paths(afile)
            return self._parse_sublayers(paths, entity_type, name, task_name)
        except Exception as e:
            print(f"Error reading {afile}: {e}")
            return []

    def get_all_existing_assemblies(self, entity_type, name):
        base = self._assembly_base(entity_type, name)
        if not base.exists():
            return []
        results = []
        for task_name in self.get_tasks(entity_type, name):
            task_cap = task_name.title()
            for d in base.iterdir():
                if not d.is_dir() or not d.name.endswith(task_cap):
                    continue
                assembly_name = d.name[:-len(task_cap)]
                files = self.get_existing_assembly(entity_type, name, task_name, assembly_name)
                for fi in files:
                    fi['assembly_name'] = assembly_name
                    fi['source_task']   = task_name
                results.extend(files)
        return results

    def check_assembly_folder(self, entity_type, name, task_name, assembly_name):
        folder = f"{assembly_name}{task_name.title()}"
        return (self._assembly_base(entity_type, name) / folder).exists()

    # ── Linked assets (shot.usda) ─────────────────────────────────────────────

    def get_linked_assets(self, entity_name, assembly_name='main'):
        """Read linked assets from [entity].usda (main) or [entity]_[assembly].usda."""
        if assembly_name == 'main':
            usda = self.shots_path / entity_name / f"{entity_name}.usda"
        else:
            usda = self.shots_path / entity_name / f"{entity_name}_{assembly_name}.usda"
        if not usda.exists():
            return []
        try:
            paths = read_sublayer_paths(usda)
            return self._parse_shot_usda(paths)
        except Exception as e:
            print(f"Error reading {usda.name}: {e}")
            return []

    # ── Internal parsers ──────────────────────────────────────────────────────

    def _parse_sublayers(self, sublayer_paths, entity_type, name, task_name):
        results = []
        for path in sublayer_paths:
            parts = path.split('/')
            try:
                idx = parts.index(task_name)
                output_name = parts[idx + 1]
            except (ValueError, IndexError):
                continue
            fi = self._reconstruct_file_info(entity_type, name, task_name, output_name)
            if fi:
                results.append(fi)
        return results

    def _reconstruct_file_info(self, entity_type, name, task_name, output_name):
        usda_dir = self._pub(entity_type, name) / task_name / output_name / "latest" / "usda"
        if not usda_dir.exists():
            return None
        files = [f for f in usda_dir.iterdir() if f.suffix in USD_EXTS]
        if not files:
            return None
        return {'file': files[0], 'version': 'latest',
                'output_name': output_name,
                'metadata': self._get_metadata(usda_dir)}

    def _parse_shot_usda(self, sublayer_paths):
        results = []
        for path in sublayer_paths:
            if path.startswith('./pub/assembly/') or '/assets/' not in path:
                continue
            parts = path.split('/')
            try:
                ai  = parts.index('assets')
                ali = parts.index('assembly')
                asset_name    = parts[ai + 1]
                assembly_name = parts[ali + 1].replace('Assembly', '')
            except (ValueError, IndexError):
                continue
            afile = (self.assets_path / asset_name / "pub" / "assembly" /
                     f"{assembly_name}Assembly" /
                     f"asset_{asset_name}_{assembly_name}Assembly.usda")
            if afile.exists():
                results.append({
                    'file': afile, 'version': 'Assembly',
                    'output_name': f"{asset_name}_{assembly_name}",
                    'metadata': {'user': 'asset', 'exportDate': '', 'groupName': asset_name},
                    'is_asset': True, 'asset_name': asset_name,
                    'assembly_name': assembly_name, 'published': True,
                })
        return results

    # ── Internals ─────────────────────────────────────────────────────────────

    def _has_usd_files(self, task_path):
        try:
            for output_dir in task_path.iterdir():
                if not output_dir.is_dir():
                    continue
                latest = output_dir / "latest" / "usda"
                if latest.exists() and any(f.suffix in USD_EXTS for f in latest.iterdir()):
                    return True
                for vdir in output_dir.iterdir():
                    if not (vdir.is_dir() and vdir.name.startswith('v')):
                        continue
                    usda = vdir / "usda"
                    if usda.exists() and any(f.suffix in USD_EXTS for f in usda.iterdir()):
                        return True
        except Exception:
            pass
        return False

    def _get_metadata(self, usda_dir):
        j = usda_dir / "versionInfo.json"
        if j.exists():
            try:
                return json.loads(j.read_text())
            except Exception:
                pass
        return {'user': 'unknown', 'exportDate': 'unknown', 'groupName': 'unknown'}