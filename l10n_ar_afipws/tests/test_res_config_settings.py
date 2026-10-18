from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from . import common


@tagged('post_install', '-at_install')
class TestResConfigSettings(common.AfipwsCase):
    def test_settings_certificate_actions_and_notifications(self):
        certificate = self.certificate(state='confirmed', crt='mock')
        settings = self.env['res.config.settings'].create({'company_id': self.company.id,
                                                         'afip_ws_env_type': 'homologation'})
        self.assertEqual(settings.arca_certificate_id, certificate)
        settings.afip_ws_env_type = False
        settings._compute_arca_certificate()
        self.assertEqual(settings.arca_certificate_id, certificate)
        action = settings.action_arca_certificates()
        self.assertEqual(action['context']['default_type'], 'homologation')
        self.assertEqual(action['domain'], [('company_id', '=', self.company.id)])
        self.assertEqual(settings.action_arca_certificate_request()['target'], 'new')
        with patch.object(type(settings), 'execute'), \
                patch.object(type(self.company), 'get_connection', return_value=self.connection):
            result = settings.action_arca_connections()
            self.assertIn('autenticación correcta', result['params']['message'])
        with patch.object(type(settings), 'execute'), \
                patch.object(type(self.company), 'get_connection', side_effect=UserError('offline')):
            self.assertIn('offline', settings.action_arca_connections()['params']['message'])
