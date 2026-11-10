"""Privacy and offline boundaries of portable inventory support."""
import unittest

from capability_inventory_support import NativeFacts, OfflineBoundary


class InventorySupportTests(unittest.TestCase):
    def test_configuration_keeps_metadata_without_commands_or_credentials(self):
        config = {'mcp_servers': {'sample': {'command': 'private-command', 'env': {'KEY': 'private-value'}}},
                  'plugins': {'enabled': ['example']}, 'curator': {'enabled': True},
                  'hooks': {'pre_tool_call': [{'command': 'private-hook'}]}}
        result = NativeFacts.public_config(config, lambda name: name, lambda entry: True)
        self.assertEqual(result['mcp'], [{'name': 'sample', 'prefix': 'mcp__sample__', 'enabled': True}])
        self.assertNotIn('private-', str(result))

    def test_invalid_scalar_does_not_pass_as_public_metadata(self):
        with self.assertRaises(ValueError):
            NativeFacts.public_config({'curator': {'enabled': 'private-value'}}, str, bool)

    def test_offline_boundary_blocks_connection_and_name_resolution(self):
        for event in ('socket.connect', 'socket.getaddrinfo', 'socket.sendto'):
            with self.subTest(event=event):
                boundary = OfflineBoundary()
                with self.assertRaises(PermissionError):
                    boundary.check(event, ())
                self.assertEqual(boundary.blocked_connections, 1)


if __name__ == '__main__':
    unittest.main()
