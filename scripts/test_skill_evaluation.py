"""Behavior checks for metadata inventory and preparation-only grading."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from skill_evaluation import InventoryNormalizer, OutcomeValidator


class InventoryTests(unittest.TestCase):
    def test_exposed_tools_are_not_reported_as_exercised(self):
        payload = {'total': 1, 'sections': [{'name': 'file', 'tools': [
            {'name': 'read_file', 'description': 'Read a file.'}]}]}
        rows = InventoryNormalizer.tools(payload)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name'], 'read_file')
        self.assertEqual(rows[0]['evidence'], 'live_owner_exposure')
        self.assertFalse(rows[0]['operation_verified'])

    def test_declared_total_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            InventoryNormalizer.tools({'total': 2, 'sections': []})

    def test_duplicate_tool_names_are_rejected(self):
        payload = {'total': 2, 'sections': [{'name': 'file', 'tools': [
            {'name': 'read_file'}, {'name': 'read_file'}]}]}
        with self.assertRaises(ValueError):
            InventoryNormalizer.tools(payload)

    def test_same_plugin_name_with_different_roles_is_preserved(self):
        rows = InventoryNormalizer.plugins([
            {'name': 'provider', 'source': 'bundled', 'status': 'enabled', 'description': 'Images.'},
            {'name': 'provider', 'source': 'bundled', 'status': 'enabled', 'description': 'Video.'},
        ])
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]['inventory_id'], rows[1]['inventory_id'])
        self.assertTrue(all(row['readiness'] == 'unverified' for row in rows))

    def test_duplicate_plugin_identity_is_not_silently_dropped(self):
        entry = {'name': 'provider', 'source': 'bundled', 'status': 'enabled', 'description': 'Images.'}
        with self.assertRaises(ValueError):
            InventoryNormalizer.plugins([entry, entry])

    def test_session_identity_comes_from_owner_rows(self):
        rows = [{'session_id': 'stored', 'running': False}, {'session_id': 'live', 'running': True}]
        self.assertEqual(InventoryNormalizer.session_id(rows), 'live')
        with self.assertRaises(ValueError):
            InventoryNormalizer.session_id(rows, 'agent:main:local:dm:live')

    def test_ambiguous_running_sessions_need_explicit_selection(self):
        rows = [{'session_id': 'one', 'running': True}, {'session_id': 'two', 'running': True}]
        with self.assertRaises(ValueError):
            InventoryNormalizer.session_id(rows)
        self.assertEqual(InventoryNormalizer.session_id(rows, 'two'), 'two')


class OutcomeTests(unittest.TestCase):
    def test_key_order_and_whitespace_do_not_change_correctness(self):
        verdict = OutcomeValidator.check('{ "exit_code": 3, "ok": false }', {'ok': False, 'exit_code': 3})
        self.assertTrue(verdict['semantic_pass'])
        self.assertTrue(verdict['format_pass'])

    def test_false_is_not_integer_zero(self):
        verdict = OutcomeValidator.check('{"ok": 0}', {'ok': False})
        self.assertFalse(verdict['semantic_pass'])

    def test_wrong_value_and_extra_fields_are_rejected(self):
        for text in ('{"exit_code": 0}', '{"exit_code": 3, "repaired": true}'):
            with self.subTest(text=text):
                self.assertFalse(OutcomeValidator.check(text, {'exit_code': 3})['semantic_pass'])

    def test_code_fence_is_semantic_success_but_format_failure(self):
        verdict = OutcomeValidator.check('```json\n{"ok": false}\n```', {'ok': False})
        self.assertTrue(verdict['semantic_pass'])
        self.assertFalse(verdict['format_pass'])

    def test_missing_and_malformed_json_fail(self):
        for text in ('', 'success', '{"ok":', 'The answer is {"ok": false}'):
            with self.subTest(text=text):
                self.assertFalse(OutcomeValidator.check(text, {'ok': False})['semantic_pass'])

    def test_multiple_objects_do_not_hide_a_wrong_answer(self):
        verdict = OutcomeValidator.check('{"ok": true}\n{"ok": false}', {'ok': False})
        self.assertFalse(verdict['semantic_pass'])

    def test_duplicate_keys_do_not_hide_a_wrong_answer(self):
        verdict = OutcomeValidator.check('{"ok": true, "ok": false}', {'ok': False})
        self.assertFalse(verdict['semantic_pass'])

    def test_cli_has_no_inference_command(self):
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('skill_evaluation.py')), 'run'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn('invalid choice', result.stderr)


class PreparationTests(unittest.TestCase):
    def test_baseline_preparation_needs_no_machine_specific_skills(self):
        from prepare_skill_trials import FixturePreparation
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            root = Path(directory)
            inventory = root / 'inventory.json'
            inventory.write_text(json.dumps({'profile_home': str(root / 'profile'), 'skills': []}))
            preparation = FixturePreparation(root / 'upstream', root / 'worker.py', inventory,
                                             root / 'workspace', root / 'output')
            self.assertEqual(preparation.freeze_skills(), [])

    def test_dangling_workspace_link_cannot_create_another_target(self):
        from prepare_skill_trials import FixturePreparation
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            root = Path(directory)
            inventory = root / 'inventory.json'
            inventory.write_text(json.dumps({'profile_home': str(root / 'profile')}))
            (root / 'workspace').symlink_to(root / 'unexpected')
            preparation = FixturePreparation(root / 'upstream', root / 'worker.py', inventory,
                                             root / 'workspace', root / 'output')
            try:
                preparation.prepare()
            except OSError:
                pass
            self.assertFalse((root / 'unexpected').exists())

    def test_existing_output_is_never_overwritten(self):
        from prepare_skill_trials import FixturePreparation
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            with self.assertRaises(FileExistsError):
                FixturePreparation.require_new(Path(directory))

    def test_symlink_fixture_is_rejected(self):
        from prepare_skill_trials import FixturePreparation
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            root = Path(directory)
            workspace = root / 'workspace'
            workspace.mkdir()
            (root / 'outside.txt').write_text('synthetic')
            (workspace / 'link').symlink_to(root / 'outside.txt')
            with self.assertRaises(ValueError):
                FixturePreparation.file_manifest(workspace)

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'FIFO fixtures require a POSIX host')
    def test_fifo_metadata_is_collected_without_reading_it(self):
        from prepare_skill_trials import FixturePreparation
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            root = Path(directory)
            os.mkfifo(root / 'stream')
            self.assertEqual(FixturePreparation.file_manifest(root)['stream']['kind'], 'fifo')

    def test_changed_fixture_is_detected(self):
        from prepare_skill_trials import FixturePreparation
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            root = Path(directory)
            (root / 'input.txt').write_text('original')
            before = FixturePreparation.file_manifest(root)
            (root / 'input.txt').write_text('changed')
            with self.assertRaises(ValueError):
                FixturePreparation.verify_files(root, before)


if __name__ == '__main__':
    unittest.main()
