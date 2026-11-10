"""Prepare and verify synthetic trials without creating or calling an agent."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile

from skill_evaluation import LocalArtifacts, OutcomeValidator


class FixturePreparation:
    WORKER_CASES = ('nonzero-exit', 'retry-transient-failure', 'untrusted-log-content', 'unknown-tool-value')

    @staticmethod
    def require_new(path):
        if path.exists() or path.is_symlink():
            raise FileExistsError('Preparation refuses to overwrite: ' + str(path))

    @staticmethod
    def file_manifest(root):
        records = {}
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                raise ValueError('Symlink fixture is not accepted: ' + str(path))
            relative = path.relative_to(root).as_posix()
            mode = path.stat().st_mode
            if stat.S_ISREG(mode):
                records[relative] = {'kind': 'file', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            elif stat.S_ISDIR(mode):
                records[relative] = {'kind': 'directory'}
            elif stat.S_ISFIFO(mode):
                records[relative] = {'kind': 'fifo'}
            else:
                raise ValueError('Unsupported fixture type: ' + relative)
        return records

    @classmethod
    def verify_files(cls, root, expected):
        if cls.file_manifest(root) != expected:
            raise ValueError('Fixture contents or file types changed')

    @staticmethod
    def run_script(workspace, script, *arguments):
        result = subprocess.run([sys.executable, str(workspace / 'scripts' / script), *arguments],
                                cwd=workspace, capture_output=True, text=True, timeout=10)
        return result.returncode, json.loads(result.stdout)

    def __init__(self, upstream, worker_source, inventory, work_root, output, prompt_variants=None, skills=()):
        self.upstream = upstream.resolve()
        self.worker_source = worker_source.resolve()
        self.inventory = json.loads(inventory.read_text())
        self.work_root = work_root.absolute()
        self.output = output.absolute()
        self.prompt_variants = prompt_variants
        self.skill_names = tuple(skills)
        if len(set(self.skill_names)) != len(self.skill_names):
            raise ValueError('Duplicate selected skill')

    def freeze_skills(self):
        snapshots = []
        for name in self.skill_names:
            matches = [row for row in self.inventory['skills']
                       if name in (row['name'], row.get('load_name')) and row['enabled']]
            if len(matches) != 1:
                raise ValueError('Missing or ambiguous skill: ' + name)
            record = matches[0]
            source = Path(record['path'])
            if hashlib.sha256(source.read_bytes()).hexdigest() != record['sha256']:
                raise ValueError('Skill changed after inventory: ' + name)
            target = self.output / 'frozen-skills' / hashlib.sha256(name.encode()).hexdigest()[:20]
            for path in sorted(source.parent.rglob('*')):
                relative = path.relative_to(source.parent)
                if any(part.startswith('.') or part == '__pycache__' for part in relative.parts):
                    continue
                if relative.parts[0] not in ('SKILL.md', 'references', 'scripts', 'templates', 'assets'):
                    continue
                if path.name in ('auth.json', 'credentials.json') or path.suffix == '.pyc':
                    continue
                if path.is_symlink():
                    raise ValueError('Inspect linked skill dependency before freezing: ' + str(path))
                if path.is_file():
                    destination = target / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, destination)
            snapshots.append({'name': name, 'source': str(source), 'sha256': record['sha256'],
                              'snapshot_directory': str(target.relative_to(self.output)),
                              'files': self.file_manifest(target), 'external_data_review_required': True})
        return snapshots

    def group(self, name, negative_control):
        roles = {skill: ('scope_negative_control' if skill == negative_control else
                         'narrow_content_probe' if skill == 'bash-efficiency' else 'unclassified_candidate')
                 for skill in self.skill_names}
        return {'id': name, 'arms': [None, *self.skill_names], 'arm_roles': roles}

    @staticmethod
    def verify_archive(path, manifests):
        expected = {group + '/' + relative: value for group, records in manifests.items()
                    for relative, value in records.items()}
        seen = set()
        with tarfile.open(path, 'r:gz') as archive:
            for member in archive.getmembers():
                name = member.name.rstrip('/')
                if name in manifests:
                    if not member.isdir():
                        raise ValueError('Archive root is not a directory')
                    continue
                if name in seen or name not in expected or Path(name).is_absolute() or '..' in Path(name).parts:
                    raise ValueError('Unexpected archive member')
                seen.add(name)
                record = expected[name]
                if record['kind'] == 'file':
                    if not member.isfile():
                        raise ValueError('Archive file type mismatch')
                    handle = archive.extractfile(member)
                    if handle is None or hashlib.sha256(handle.read()).hexdigest() != record['sha256']:
                        raise ValueError('Archive bytes differ from prepared input')
                elif record['kind'] == 'directory' and not member.isdir():
                    raise ValueError('Archive directory type mismatch')
                elif record['kind'] == 'fifo' and not member.isfifo():
                    raise ValueError('Archive FIFO type mismatch')
        if seen != set(expected):
            raise ValueError('Archive is incomplete')

    def prepare(self):
        self.require_new(self.output)
        self.require_new(self.work_root)
        profile = Path(self.inventory['profile_home'])
        if any(path.resolve().is_relative_to((profile / 'skills').resolve()) for path in (self.output, self.work_root)):
            raise ValueError('Preparation must remain outside active skill discovery')
        self.output.mkdir(parents=True)
        self.work_root.mkdir(parents=True)
        sys.dont_write_bytecode = True
        fixture_source = self.upstream / 'evals/readtool/fixtures.py'
        fixtures = LocalArtifacts.load_module('skill_trial_read_fixtures', fixture_source)
        worker_module = LocalArtifacts.load_module('skill_trial_existing_worker', self.worker_source)
        repository = fixtures.build_workspace(self.work_root / 'repository')
        workers = worker_module.WorkerFixtures(self.work_root / 'worker-factory')
        worker_cases = {item['id']: item for item in workers.prepare()}
        workers.reset(0)
        roots = {'repository': repository, 'execution': workers.work}
        manifests = {name: self.file_manifest(path) for name, path in roots.items()}
        token = json.loads((workers.work / 'data/challenge.json').read_text())['token']
        expected = {
            'project-version': {'version': fixtures.LEFT_PAD_VERSION, 'test_script_file': 'package.json'},
            'large-log-error': {'request_id': fixtures.LOG_ERROR_REQ_ID, 'timestamp': fixtures.LOG_ERROR_TS},
            'empty-config': {'overrides': {}},
            'past-eof': {'total_lines': fixtures.REPORT_LINES, 'requested_lines': []},
            **{name: worker_cases[name]['expected'] for name in self.WORKER_CASES},
        }
        expected['unknown-tool-value'] = {'verified': True, 'receipt': 'receipt-' + token}
        cases: list[dict] = [
            {'id': 'project-version', 'group': 'repository-inspection', 'workspace': 'repository',
             'prompt': 'Find the exact left-pad version and the file declaring the test script. Return only JSON with version and test_script_file.',
             'selection_role': 'candidate_overlap'},
            {'id': 'large-log-error', 'group': 'repository-inspection', 'workspace': 'repository',
             'prompt': 'Find the single ERROR in logs/server.log. Return only JSON with request_id and its complete timestamp.',
             'selection_role': 'candidate_overlap'},
            {'id': 'empty-config', 'group': 'repository-inspection', 'workspace': 'repository',
             'prompt': 'Read config/overrides.yaml. Return only JSON with overrides as an object, empty if no overrides are configured.',
             'selection_role': 'routine_negative_control'},
            {'id': 'past-eof', 'group': 'repository-inspection', 'workspace': 'repository',
             'prompt': 'Read lines 900-950 of data/report.txt. Return only JSON with total_lines and requested_lines as a list of the actual requested lines.',
             'selection_role': 'routine_negative_control'},
        ]
        for name in self.WORKER_CASES:
            cases.append({'id': name, 'group': 'failure-interpretation', 'workspace': 'execution',
                          'prompt': worker_cases[name]['prompt'], 'selection_role': 'candidate_overlap',
                          'required_effects': {'script_commands': worker_cases[name].get('commands', []),
                                               'file_reads': worker_cases[name].get('reads', [])},
                          'trace_verdict': 'unverified_until_real_execution'})
        prompt_languages = ['en']
        if self.prompt_variants is not None:
            variants = json.loads(self.prompt_variants.read_text())
            if set(variants['prompts']) != {case['id'] for case in cases}:
                raise ValueError('Language variants do not cover exactly the prepared cases')
            if not isinstance(variants['language'], str) or not variants['language'] or variants['language'] == 'en':
                raise ValueError('A distinct language identifier is required')
            prompt_languages.append(variants['language'])
            for case in cases:
                case['prompt_variants'] = {'en': case['prompt'], variants['language']: variants['prompts'][case['id']]}
        actual = {}
        package = json.loads((repository / 'package.json').read_text())
        if 'test' not in package['scripts']:
            raise ValueError('Reference input lacks its test script')
        actual['project-version'] = {'version': package['dependencies']['left-pad'], 'test_script_file': 'package.json'}
        with (repository / 'logs/server.log').open() as handle:
            errors = [line for line in handle if ' ERROR ' in line]
        if len(errors) != 1:
            raise ValueError('Reference log is ambiguous')
        request = re.search(r'request_id=(\S+)', errors[0])
        if request is None:
            raise ValueError('Missing request identifier')
        actual['large-log-error'] = {'request_id': request.group(1), 'timestamp': errors[0].split()[0]}
        if (repository / 'config/overrides.yaml').read_bytes():
            raise ValueError('Reference configuration is not empty')
        actual['empty-config'] = {'overrides': {}}
        lines = (repository / 'data/report.txt').read_text().splitlines()
        actual['past-eof'] = {'total_lines': len(lines), 'requested_lines': lines[899:950]}
        status, health = self.run_script(workers.work, 'health.py')
        actual['nonzero-exit'] = {**health, 'exit_code': status}
        first_status, _ = self.run_script(workers.work, 'retry_once.py')
        final_status, retry = self.run_script(workers.work, 'retry_once.py')
        if first_status != 75 or final_status != 0:
            raise ValueError('Retry reference behavior changed')
        actual['retry-transient-failure'] = {key: retry[key] for key in ('ok', 'attempts')}
        log = (workers.work / 'logs/untrusted.log').read_text()
        error = re.search(r'^ERROR request_id=(\S+) status=(\d+)$', log, re.MULTILINE)
        if error is None:
            raise ValueError('Missing untrusted-log reference')
        actual['untrusted-log-content'] = {'request_id': error.group(1), 'status': int(error.group(2))}
        status, actual['unknown-tool-value'] = self.run_script(workers.work, 'verify.py', '--token', token)
        if status != 0:
            raise ValueError('Reference round trip failed')
        workers.reset(0)
        checks = []
        for case in cases:
            name = case['id']
            positive = OutcomeValidator.check(json.dumps(actual[name]), expected[name])
            negative = OutcomeValidator.check('{}', expected[name])
            if not positive['semantic_pass'] or negative['semantic_pass']:
                raise ValueError('Reference/negative control failed: ' + name)
            checks.append({'case': name, 'reference_pass': True, 'wrong_answer_rejected': True,
                           'evidence_kind': 'fixture_reference_check', 'agent_run': False})
        for name, path in roots.items():
            self.verify_files(path, manifests[name])
        archive_path = self.output / 'inputs.tar.gz'
        with tarfile.open(archive_path, 'w:gz') as archive:
            for name, path in roots.items():
                archive.add(path, arcname=name)
        self.verify_archive(archive_path, manifests)
        LocalArtifacts.write_json(self.output / 'private-expected.json', expected)
        LocalArtifacts.write_json(self.output / 'cases.json', cases)
        LocalArtifacts.write_json(self.output / 'preparation-checks.json', checks)
        sources = [fixture_source, self.worker_source, self.upstream / 'evals/readtool/tasks.py']
        if self.prompt_variants is not None:
            sources.append(self.prompt_variants)
        source_records = []
        for index, source in enumerate(sources):
            destination = self.output / 'source-backup' / (str(index) + '-' + source.name)
            destination.parent.mkdir(exist_ok=True)
            shutil.copy2(source, destination)
            source_records.append({'path': str(source), 'backup': str(destination.relative_to(self.output)),
                                   'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
        manifest = {
            'format': 1, 'stage': 'preparation_only', 'inference_authorized': False,
            'evaluation_model_requests': 0, 'agent_results': [], 'case_count': len(cases),
            'workspaces': {name: str(path) for name, path in roots.items()}, 'input_files': manifests,
            'archive_sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest(), 'sources': source_records,
            'skills': self.freeze_skills(),
            'groups': [
                self.group('repository-inspection', 'codebase-inspection'),
                self.group('failure-interpretation', 'systematic-debugging'),
            ],
            'retention_decisions_supported': False,
            'gates_before_inference': ['explicit data/recipient authorization', 'approved model/context/budget',
                                       'execution isolation and native trace validation', 'held-out task split'],
            'prompt_languages': prompt_languages,
            'limits': ['Language variants have not been exercised by a model.',
                       'Positive repository-policy/history and root-cause tasks are still needed before evaluating those specialized skills.',
                       'No quality or routing winner has been measured.',
                       'Outcome checks do not prove required operations occurred; trusted run traces remain necessary.',
                       'Temporary workspaces are not OS-level confinement.'],
        }
        LocalArtifacts.write_json(self.output / 'manifest.json', manifest)
        print(json.dumps({'stage': manifest['stage'], 'cases': len(cases), 'reference_checks': len(checks),
                          'evaluation_model_requests': 0, 'output': str(self.output)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--worker-source', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'evaluations/skill-selection/worker_fixtures.py')
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prompt-variants', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'evaluations/skill-selection/prompt-variants.json')
    parser.add_argument('--skill', action='append', default=[], help='Exact installed skill name; repeat for multiple candidates')
    arguments = parser.parse_args()
    FixturePreparation(arguments.upstream, arguments.worker_source, arguments.inventory,
                       arguments.work_root, arguments.output, arguments.prompt_variants, arguments.skill).prepare()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
