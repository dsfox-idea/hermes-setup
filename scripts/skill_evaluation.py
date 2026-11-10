"""Metadata inventory and outcome checks; deliberately no model execution API."""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
import logging
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone


class InventoryNormalizer:
    @staticmethod
    def tools(payload):
        rows = []
        for section in payload['sections']:
            for tool in section['tools']:
                rows.append({'inventory_id': 'tool:' + tool['name'], 'name': tool['name'],
                             'group': section['name'], 'description': tool.get('description', ''),
                             'evidence': 'live_owner_exposure', 'operation_verified': False})
        names = [row['name'] for row in rows]
        if len(rows) != payload['total'] or len(set(names)) != len(names):
            raise ValueError('Tool count or identity mismatch')
        return sorted(rows, key=lambda row: (row['group'], row['name']))

    @staticmethod
    def plugins(payload):
        rows = []
        identities = set()
        for item in payload:
            projected = {key: item.get(key) for key in ('name', 'source', 'version', 'status', 'description')}
            identity = hashlib.sha256(json.dumps(projected, sort_keys=True).encode()).hexdigest()
            if identity in identities:
                raise ValueError('Ambiguous duplicate plugin identity')
            identities.add(identity)
            rows.append({'inventory_id': 'plugin:' + identity[:20], **projected, 'readiness': 'unverified'})
        return rows

    @staticmethod
    def session_id(rows, requested=None):
        if requested is not None:
            matches = [row for row in rows if row.get('session_id') == requested]
        else:
            matches = [row for row in rows if row.get('running')]
        if len(matches) != 1 or not matches[0].get('session_id'):
            raise ValueError('Select an exact session_id from owner metadata; selection is ambiguous or absent')
        return matches[0]['session_id']


class OutcomeValidator:
    @staticmethod
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result

    @staticmethod
    def check(response, expected):
        text = response.strip()
        format_pass = True
        fenced = re.fullmatch(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()
            format_pass = False
        try:
            actual = json.loads(text, object_pairs_hook=OutcomeValidator.unique_object)
        except (ValueError, TypeError):
            return {'semantic_pass': False, 'format_pass': False, 'reason': 'invalid_json'}
        canonical = lambda value: json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)
        try:
            matched = canonical(actual) == canonical(expected)
        except ValueError:
            matched = False
        return {'semantic_pass': matched, 'format_pass': format_pass, 'reason': 'matched' if matched else 'different_value_or_type'}


class LocalArtifacts:
    @staticmethod
    def load_module(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ValueError('Cannot load the inspected source module')
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def write_json(path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + '\n')

    @staticmethod
    def bootstrap(arguments):
        command = json.loads(subprocess.check_output(['hermes', '--print-runtime-command'], text=True, timeout=15))
        prefix, separator, _ = command[-1].rpartition('runpy.run_module(')
        if not separator:
            raise RuntimeError('Inspect the changed native launcher before proceeding')
        command[-1] = prefix + 'sys.dont_write_bytecode=True; sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name="__main__")'
        return subprocess.run([*command, str(Path(__file__).resolve()), *arguments], timeout=55).returncode


class CapabilityInventory:
    def __init__(self, project, session_id=None):
        self.project = project.resolve()
        self.requested_session = session_id
        self.errors = []

    async def live_tools(self):
        from hermes_constants import get_hermes_home
        from hermes_cli.gateway_client import connect_gateway
        from hermes_cli.gateway_runtime import discover_gateway_endpoint
        discovery = discover_gateway_endpoint(get_hermes_home())
        if discovery.endpoint is None:
            raise RuntimeError('No existing gateway; inventory must not start one')
        async with connect_gateway(endpoint=discovery.endpoint) as client:
            sessions = await client.rpc('session.list', limit=100, _timeout=15)
            session_id = InventoryNormalizer.session_id(sessions['sessions'], self.requested_session)
            tools = await client.rpc('tools.show', session_id=session_id, _timeout=15)
            toolsets = await client.rpc('tools.list', session_id=session_id, _timeout=15)
        return {'scope': 'live_owner_listing_for_selected_session',
                'session_id_sha256': hashlib.sha256(session_id.encode()).hexdigest(),
                'tools': InventoryNormalizer.tools(tools), 'toolsets': toolsets['toolsets']}

    def collect(self):
        from hermes_constants import get_hermes_home
        home = get_hermes_home()
        report = {'format': 1, 'recorded_at': datetime.now(timezone.utc).isoformat(),
                  'profile_home': str(home), 'project': str(self.project),
                  'quality_measured': False, 'evaluation_model_requests': 0,
                  'hosted_connectors': {'status': 'not_collected_by_local_helper', 'count': None},
                  'errors': self.errors}
        try:
            report['live'] = asyncio.run(self.live_tools())
        except Exception as error:
            self.errors.append({'section': 'live_tools', 'error_type': type(error).__name__})
            report['live'] = {'scope': 'unavailable', 'tools': [], 'toolsets': []}
        plugins = subprocess.run(['hermes', 'plugins', 'list', '--json'], capture_output=True, text=True, timeout=25, check=True)
        report['plugins'] = InventoryNormalizer.plugins(json.loads(plugins.stdout))
        support_path = Path(__file__).with_name('capability_inventory_support.py')
        support = LocalArtifacts.load_module('skill_evaluation_support', support_path)
        boundary = support.OfflineBoundary()
        sys.addaudithook(boundary.check)
        from tools.skills_tool import _skill_catalog, skills_list
        from hermes_cli.config_effective import load_user_config_effective
        from tools.mcp_tool_common import mcp_server_enabled
        from tools.mcp_tool_schema import sanitize_mcp_name_component
        from agent.runtime_cwd import set_session_cwd, reset_session_cwd
        token = set_session_cwd(str(self.project))
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                config = load_user_config_effective(fail_closed=True)
                report['configuration'] = support.NativeFacts.public_config(config, sanitize_mcp_name_component, mcp_server_enabled)
                report['curator'] = support.NativeFacts.curator()
                catalog = _skill_catalog(skip_disabled=True, include_hidden=True)
                active_paths = {str(row['path']) for row in _skill_catalog()}
                listed = json.loads(skills_list())
                if not listed.get('success') or listed['count'] != len(listed['skills']):
                    raise ValueError('Native skill listing is incomplete')
                report['skills'] = []
                local_names = set()
                for entry in catalog:
                    path = Path(entry['path'])
                    local_names.update(name for name in (entry['name'], entry.get('load_name')) if name)
                    report['skills'].append({
                        'inventory_id': 'skill:' + hashlib.sha256(str(path).encode()).hexdigest()[:20],
                        'name': entry['name'], 'load_name': entry.get('load_name'),
                        'description': entry.get('description', ''), 'category': entry.get('category'),
                        'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'registration': entry['status'], 'enabled': str(path) in active_paths,
                        'quality': 'unmeasured', 'readiness': 'not_probed'})
                report['additional_registered_skills'] = [row for row in listed['skills'] if row['name'] not in local_names]
                report['native_skill_listing_count'] = listed['count']
                from hermes_cli.plugins import discover_plugins, get_plugin_manager
                discover_plugins()
                manager = get_plugin_manager()
                servers = dict(config.get('mcp_servers') or {})
                owners: dict[str, str | None] = {name: None for name in servers}
                try:
                    portable = manager.get_portable_mcp_servers()
                    plugin_owners = manager.get_portable_mcp_server_plugins()
                    for name, entry in portable.items():
                        if name not in servers:
                            servers[name] = entry
                            owners[name] = plugin_owners.get(name)
                except Exception as error:
                    self.errors.append({'section': 'plugin_mcp', 'error_type': type(error).__name__})
                report['mcp_servers'] = [{'name': name, 'enabled': mcp_server_enabled(entry),
                                          'owner_plugin': owners[name], 'connection_verified': False}
                                         for name, entry in sorted(servers.items())]
                from tools.tool_search import bridge_tool_schemas
                report['supplemental_tools'] = [
                    {'name': item['function']['name'], 'group': 'tool_dispatch_bridge',
                     'description': item['function']['description'], 'evidence': 'native_schema_factory',
                     'operation_verified': False}
                    for item in bridge_tool_schemas(0)]
                provider = (config.get('memory') or {}).get('provider', 'builtin')
                report['memory_provider'] = provider
                if provider == 'honcho':
                    schema_path = home / 'plugins/honcho/tool_schemas.py'
                    schemas = LocalArtifacts.load_module('skill_evaluation_memory_schemas', schema_path)
                    report['supplemental_tools'].extend(
                        {'name': item['name'], 'group': 'honcho_memory', 'description': item['description'],
                         'evidence': 'active_provider_schema_source', 'operation_verified': False}
                        for item in schemas.ALL_TOOL_SCHEMAS)
                    report['memory_schema_sha256'] = hashlib.sha256(schema_path.read_bytes()).hexdigest()
                elif provider != 'builtin':
                    self.errors.append({'section': 'memory_tool_schemas', 'error_type': 'UnsupportedProvider'})
        finally:
            reset_session_cwd(token)
        report['blocked_network_attempts'] = boundary.blocked_connections
        report['status'] = 'partial' if self.errors else 'local_inventory_collected_hosted_connectors_unknown'
        report['counts'] = {'skills_on_disk': len(report['skills']),
                            'additional_registered_skills': len(report['additional_registered_skills']),
                            'live_listed_tools': len(report['live']['tools']),
                            'supplemental_tool_schemas': len(report['supplemental_tools']),
                            'unique_named_tools_across_sources': len({row['name'] for row in report['live']['tools'] + report['supplemental_tools']}),
                            'toolsets': len(report['live']['toolsets']),
                            'plugin_declarations': len(report['plugins']),
                            'mcp_server_declarations': len(report['mcp_servers']),
                            'hosted_connectors': None}
        return report


class InventoryReport:
    @staticmethod
    def write_csv(path, report):
        columns = ('layer', 'name', 'group', 'description', 'state', 'evidence')
        with path.open('x', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for row in report['skills']:
                writer.writerow({'layer': 'skill', 'name': row['name'], 'group': row['category'],
                                 'description': row['description'], 'state': 'enabled' if row['enabled'] else 'disabled_or_hidden',
                                 'evidence': 'native_catalog; quality_unmeasured'})
            for row in report['additional_registered_skills']:
                writer.writerow({'layer': 'registered_skill', 'name': row['name'], 'group': row.get('category'),
                                 'description': row.get('description'), 'state': 'listed', 'evidence': 'native_skills_list'})
            for row in report['live']['tools']:
                writer.writerow({'layer': 'tool', 'name': row['name'], 'group': row['group'],
                                 'description': row['description'], 'state': 'listed_by_live_owner', 'evidence': row['evidence']})
            for row in report['supplemental_tools']:
                writer.writerow({'layer': 'adapter_tool', 'name': row['name'], 'group': row['group'],
                                 'description': row['description'], 'state': 'declared_not_probed', 'evidence': row['evidence']})
            for row in report['plugins']:
                writer.writerow({'layer': 'plugin', 'name': row['name'], 'group': row['source'],
                                 'description': row['description'], 'state': row['status'], 'evidence': 'plugin_declaration; readiness_unverified'})
            for row in report['mcp_servers']:
                writer.writerow({'layer': 'mcp', 'name': row['name'], 'group': row['owner_plugin'],
                                 'state': 'enabled' if row['enabled'] else 'disabled', 'evidence': 'configuration; connection_unverified'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    inventory = commands.add_parser('inventory')
    inventory.add_argument('--project', type=Path, required=True)
    inventory.add_argument('--session-id')
    inventory.add_argument('--output', type=Path, required=True)
    validate = commands.add_parser('check-answer')
    validate.add_argument('--answer', type=Path, required=True)
    validate.add_argument('--expected', type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == 'check-answer':
        verdict = OutcomeValidator.check(arguments.answer.read_text(), json.loads(arguments.expected.read_text()))
        print(json.dumps(verdict))
        return 0 if verdict['semantic_pass'] and verdict['format_pass'] else 1
    if importlib.util.find_spec('hermes_constants') is None:
        return LocalArtifacts.bootstrap(sys.argv[1:])
    logging.disable(logging.CRITICAL)
    report = CapabilityInventory(arguments.project, arguments.session_id).collect()
    LocalArtifacts.write_json(arguments.output, report)
    InventoryReport.write_csv(arguments.output.with_suffix('.csv'), report)
    print(json.dumps({'status': report['status'], 'counts': report['counts'], 'errors': report['errors'],
                      'output': str(arguments.output), 'evaluation_model_requests': 0}))
    return 0 if not report['errors'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
