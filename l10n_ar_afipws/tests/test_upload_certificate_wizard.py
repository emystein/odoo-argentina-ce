from unittest.mock import patch
import base64

from odoo.exceptions import UserError
from odoo.tests import tagged

from . import common


@tagged('post_install', '-at_install')
class TestUploadCertificateWizard(common.AfipwsCase):
    def test_upload_defaults_and_validation(self):
        model = self.env['afipws.upload_certificate.wizard']
        certificate = self.certificate()
        self.assertFalse(model._default_alias())
        self.assertFalse(model._default_certificate())
        self.assertEqual(model.with_context(active_model='afipws.certificate', active_id=certificate.id)
                         ._default_certificate(), certificate)
        self.assertEqual(model.with_context(active_model='afipws.certificate_alias', active_id=self.alias.id)
                         ._default_alias(), self.alias)
        wizard = model.create({'certificate_file': base64.b64encode(b'mock crt')})
        with self.assertRaisesRegex(UserError, 'alias'):
            wizard.action_confirm()
        wizard.alias_id = self.alias
        self.alias.key = False
        with self.assertRaisesRegex(UserError, 'no private key'):
            wizard.action_confirm()
        wizard.certificate_id = certificate
        with self.assertRaisesRegex(UserError, 'clave privada'):
            wizard.action_confirm()
        wizard.certificate_key_file = base64.b64encode(b'mock key')
        with patch.object(type(certificate), 'verify_crt', return_value=True):
            wizard.action_confirm()
            self.assertEqual(certificate.state, 'confirmed')
            self.assertEqual(self.alias.key, 'mock key')
            wizard.certificate_id = False
            wizard.certificate_key_file = False
            wizard.action_confirm()
        self.assertEqual(len(self.alias.certificate_ids), 2)
