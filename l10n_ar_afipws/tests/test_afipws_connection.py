from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from odoo.exceptions import RedirectWarning, UserError
from odoo.tests import tagged

from . import common
from ..models import afipws_connection, res_company


@tagged('post_install', '-at_install')
class TestAfipwsConnection(common.AfipwsCase):
    def test_connect_passes_credentials_to_mock_service(self):
        ws = Mock()
        with TemporaryDirectory() as directory, \
                patch.object(type(self.connection), '_get_ws', return_value=ws), \
                patch.object(type(self.company.partner_id), 'ensure_vat', return_value='30712345678'), \
                patch.object(afipws_connection.tools, 'config', {'data_dir': directory}):
            self.assertIs(self.connection.connect(), ws)
            ws.Conectar.assert_called_once_with(
                directory + '/pyafipws_cache', self.connection.afip_ws_url, '')
        self.assertFalse(ws.HOMO)
        self.assertEqual(ws.Cuit, '30712345678')
        self.assertEqual(ws.Token, 'test-token')
        self.assertEqual(ws.Sign, 'test-sign')
        self.assertEqual(ws.Errores, [])

    def test_connection_error_is_user_error(self):
        ws = Mock()
        ws.Conectar.side_effect = RuntimeError('offline')
        with TemporaryDirectory() as directory, \
                patch.object(type(self.connection), '_get_ws', return_value=ws), \
                patch.object(afipws_connection.tools, 'config', {'data_dir': directory}), \
                self.assertRaisesRegex(UserError, 'offline'):
            self.connection.connect()

    def test_service_mismatch(self):
        self.connection.check_afip_ws('ws_sr_padron_a5')
        with self.assertRaises(UserError):
            self.connection.check_afip_ws('wsfecred')

    def test_service_urls_and_factories(self):
        model = self.env['afipws.connection']
        for environment in ['production', 'homologation']:
            for service, suffix in [('ws_sr_padron_a4', 'personaServiceA4?wsdl'),
                                    ('ws_sr_padron_a5', 'personaServiceA5?wsdl'),
                                    ('wsfecred', 'FECredService?wsdl')]:
                with self.subTest(environment=environment, service=service):
                    connection = model.new({'type': environment, 'afip_ws': service})
                    self.assertTrue(connection.afip_ws_url.endswith(suffix))
                    self.assertIn('LoginCms', connection.afip_login_url)
        self.assertFalse(model.get_afip_ws_url('unknown', 'production'))
        with self.assertRaises(UserError):
            model.new({'type': 'homologation', 'afip_ws': 'ws_sr_padron_a10'})._compute_afip_urls()
        empty = model.new({'type': 'homologation'})
        empty.afip_ws = False
        empty._compute_afip_urls()
        self.assertFalse(empty.afip_ws_url)
        a4, a5, credit = Mock(), Mock(), Mock()
        with patch.dict('sys.modules', {
            'pyafipws.ws_sr_padron': SimpleNamespace(WSSrPadronA4=a4, WSSrPadronA5=a5),
            'pyafipws.wsfecred': SimpleNamespace(WSFECred=credit),
        }):
            for service, factory in [('ws_sr_padron_a4', a4), ('ws_sr_padron_a5', a5), ('wsfecred', credit)]:
                self.assertIs(model._get_ws(service), factory.return_value)
            self.assertFalse(model._get_ws('unknown'))

    def test_connection_unimplemented_and_redirect(self):
        connection = self.env['afipws.connection'].new({'type': 'homologation', 'afip_ws': 'wsfecred'})
        with patch.object(type(connection), '_get_ws', return_value=False), self.assertRaises(UserError):
            connection.connect()
        for message in ['ExpatError', 'mismatched tag', 'Conexión reinicializada por la máquina remota',
                        "module 'httplib2' has no attribute 'SSLHandshakeError'"]:
            ws = Mock()
            ws.Conectar.side_effect = RuntimeError(message)
            with self.subTest(message=message), TemporaryDirectory() as directory, \
                    patch.object(type(connection), '_get_ws', return_value=ws), \
                    patch.object(res_company.tools, 'config', {'data_dir': directory}), \
                    self.assertRaises(RedirectWarning):
                connection.connect()
