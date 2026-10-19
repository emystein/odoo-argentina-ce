from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
import os

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from . import common
from ..models import res_company
from ..tools.afip_environment import AfipEnvironment


@tagged('post_install', '-at_install')
class TestResCompany(common.AfipwsCase):
    def test_environment_parameter(self):
        self.assertEqual(self.company.get_environment().type, 'homologation')
        self.env['ir.config_parameter'].sudo().set_param('afip.ws.env.type', 'production')
        self.assertEqual(self.company.get_environment().type, 'production')

    def test_reuse_valid_connection_and_replace_expired(self):
        now = fields.Datetime.now()
        self.connection.write({
            'generationtime': now - timedelta(hours=1),
            'expirationtime': now + timedelta(hours=1),
        })
        with patch.object(type(self.company), '_create_connection') as create:
            self.assertEqual(self.company.get_connection('ws_sr_padron_a5'), self.connection)
            create.assert_not_called()
            self.connection.expirationtime = now - timedelta(seconds=1)
            create.return_value = self.connection
            self.assertEqual(self.company.get_connection('ws_sr_padron_a5'), self.connection)
            create.assert_called_once_with('ws_sr_padron_a5', self.company.get_environment())

    def test_create_connection_normalizes_authentication_dates(self):
        auth = {
            'uniqueid': '123', 'token': 'token', 'sign': 'sign',
            'generationtime': '2026-01-01T09:00:00-03:00',
            'expirationtime': '2026-01-01T14:00:00-03:00',
        }
        with patch.object(type(self.company), 'get_key_and_certificate',
                          return_value=('-----BEGIN PRIVATE KEY-----\nfake', 'fake-cert')), \
                patch.object(type(self.company), 'authenticate', return_value=auth) as authenticate:
            connection = self.company._create_connection('ws_sr_padron_a5', self.company.get_environment())
        self.assertEqual(connection.generationtime, fields.Datetime.to_datetime('2026-01-01 12:00:00'))
        self.assertEqual(connection.expirationtime, fields.Datetime.to_datetime('2026-01-01 17:00:00'))
        self.assertEqual(authenticate.call_args.args[2], '-----BEGIN RSA PRIVATE KEY-----\nfake')

    def test_authenticate_and_reuse_cached_ticket(self):
        wsaa = Mock(Excepcion='')
        wsaa.LoginCMS.return_value = '<ticket>mock</ticket>'
        tags = {'token': 'token', 'sign': 'sign', 'uniqueId': '42',
                'generationTime': '2026-01-01T12:00:00Z', 'expirationTime': '2026-01-01T17:00:00Z'}
        wsaa.ObtenerTagXml.side_effect = tags.__getitem__
        with TemporaryDirectory() as directory, patch.dict('sys.modules', {'pyafipws.wsaa': SimpleNamespace(WSAA=Mock(return_value=wsaa))}):
            first = self.company.authenticate('ws_sr_padron_a5', 'cert', 'key', cache=directory)
            second = self.company.authenticate('ws_sr_padron_a5', 'cert', 'key', cache=directory)
        self.assertEqual(first, second)
        self.assertEqual(first['token'], 'token')
        self.assertEqual(first['uniqueid'], '42')
        wsaa.LoginCMS.assert_called_once()
        wsaa.SignTRA.assert_called_once_with(wsaa.CreateTRA.return_value, 'cert', 'key')
        self.assertEqual(wsaa.AnalizarXml.call_count, 2)

    def test_authentication_failure(self):
        wsaa = Mock(Excepcion='AFIP mock failure')
        wsaa.LoginCMS.return_value = ''
        with TemporaryDirectory() as directory, patch.dict('sys.modules', {'pyafipws.wsaa': SimpleNamespace(WSAA=Mock(return_value=wsaa))}), \
                self.assertRaisesRegex(UserError, 'AFIP mock failure'):
            self.company.authenticate('ws_sr_padron_a5', 'cert', 'key', cache=directory)

    def test_certificate_selection_and_duplicate_rejection(self):
        certificate = self.env['afipws.certificate'].create({
            'alias_id': self.alias.id, 'crt': 'fake-cert', 'state': 'confirmed',
        })
        self.assertEqual(self.company.get_key_and_certificate(self.company.get_environment()),
                         ('fake-private-key', 'fake-cert'))
        certificate.copy({'state': 'confirmed'})
        with self.assertRaises(UserError):
            self.company.get_key_and_certificate(self.company.get_environment())

    def test_environment_config_fallback(self):
        self.env['ir.config_parameter'].set_param('afip.ws.env.type', 'invalid')
        for mode, expected in [(None, 'production'), ('production', 'production'), ('develop', 'homologation')]:
            with self.subTest(mode=mode), patch.object(res_company.tools, 'config', {'server_mode': mode}):
                self.assertEqual(self.company.get_environment().type, expected)

    def test_certificate_files_and_failures(self):
        for environment_type, prefix in [('production', 'afip_prod'), ('homologation', 'afip_homo')]:
            environment = AfipEnvironment(environment_type)
            with self.subTest(environment=environment), TemporaryDirectory() as directory:
                key, cert = Path(directory) / 'key', Path(directory) / 'cert'
                config = {prefix + '_pkey_file': str(key), prefix + '_cert_file': str(cert)}
                with patch.object(res_company.tools, 'config', config):
                    with self.assertRaisesRegex(UserError, 'Not confirmed certificate'):
                        self.company.get_key_and_certificate(environment)
                    key.write_text('private key')
                    cert.write_text('certificate')
                    self.assertEqual(self.company.get_key_and_certificate(environment), ('private key', 'certificate'))
                    real_open = open
                    for unreadable_path in (key, cert):
                        def open_file(path, *args, **kwargs):
                            if Path(path) == unreadable_path:
                                raise PermissionError('denied')
                            return real_open(path, *args, **kwargs)

                        with self.subTest(unreadable_path=unreadable_path), \
                                patch('builtins.open', side_effect=open_file), \
                                self.assertRaisesRegex(UserError, 'Could not read %s file' % unreadable_path):
                            self.company.get_key_and_certificate(environment)
        with patch.object(res_company.tools, 'config', {}), self.assertRaises(UserError):
            self.company.get_key_and_certificate(self.company.get_environment())

    def test_create_connection_with_rsa_key(self):
        auth = dict(uniqueid='1', token='t', sign='s', generationtime='2026-01-01T12:00:00Z',
                    expirationtime='2026-01-01T17:00:00Z')
        with patch.object(type(self.company), 'get_key_and_certificate', return_value=('RSA key', 'crt')), \
                patch.object(type(self.company), 'authenticate', return_value=auth) as authenticate:
            connection = self.company._create_connection('wsfecred', self.company.get_environment())
        self.assertEqual(authenticate.call_args.args[2], 'RSA key')
        self.assertEqual(connection.type, self.company.get_environment().type)

    def test_authentication_default_cache_expiration_and_unparsed_error(self):
        wsaa = Mock(Excepcion='')
        wsaa.LoginCMS.return_value = '<ticket/>'
        wsaa.ObtenerTagXml.return_value = 'mock'
        with TemporaryDirectory() as directory, \
                patch.dict('sys.modules', {'pyafipws.wsaa': SimpleNamespace(WSAA=Mock(return_value=wsaa))}), \
                patch.object(res_company.tools, 'config', {'data_dir': directory}):
            self.assertEqual(self.company.authenticate('service', 'crt', 'key')['token'], 'mock')
            ticket = next((Path(directory) / 'pyafipws_cache').glob('*.xml'))
            os.utime(ticket, (0, 0))
            self.company.authenticate('service', 'crt', 'key')
            self.assertEqual(wsaa.LoginCMS.call_count, 2)
            wsaa.AnalizarXml.side_effect = ValueError('invalid ticket')
            with self.assertRaisesRegex(UserError, 'invalid ticket'):
                self.company.authenticate('service', 'crt', 'key')
