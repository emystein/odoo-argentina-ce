from unittest.mock import Mock, patch
import base64

from odoo.exceptions import UserError

from expression import Nothing, Option
from odoo.tests import tagged

from . import common
from ..models import afipws_certificate


@tagged('post_install', '-at_install')
class TestAfipwsCertificate(common.AfipwsCase):
    def test_find_confirmed_by_company_returns_option(self):
        repository = self.env['afipws.certificate']
        fallback = Mock(return_value=None)
        result = repository.find_confirmed_by_company(self.company)
        self.assertIsInstance(result, Option)
        self.assertEqual(result, Nothing)
        self.assertIsNone(result.default_with(fallback))
        fallback.assert_called_once_with()

        certificate = self.certificate(state='confirmed', crt='db-certificate')
        fallback.reset_mock()
        result = repository.find_confirmed_by_company(self.company)
        self.assertIsInstance(result, Option)
        self.assertEqual(result.default_with(fallback), certificate)
        fallback.assert_not_called()

    def test_certificate_request_download_and_draft_guard(self):
        certificate = self.env['afipws.certificate'].create({
            'alias_id': self.alias.id, 'csr': 'mock csr',
        })
        self.assertEqual(base64.b64decode(certificate.request_file), b'mock csr')
        self.assertEqual(certificate.request_filename, 'request.csr')
        with self.assertRaises(UserError):
            certificate.action_to_draft()
        self.alias.action_confirm()
        certificate.action_to_draft()
        self.assertEqual(certificate.state, 'draft')
        with self.assertRaises(UserError):
            certificate.action_confirm()

    def test_certificate_crypto_validation_and_states(self):
        certificate = self.certificate()
        self.assertFalse(certificate.request_file)
        certificate.crt = 'mock certificate'
        loaded = object()
        with patch.object(afipws_certificate.crypto, 'load_certificate', return_value=loaded):
            self.assertIs(certificate.get_certificate(), loaded)
            certificate.action_confirm()
        self.assertEqual(certificate.state, 'confirmed')
        certificate.action_cancel()
        self.assertEqual(certificate.state, 'cancel')
        for message in ['Expecting: CERTIFICATE', 'invalid ASN1']:
            with patch.object(afipws_certificate.crypto, 'load_certificate', side_effect=ValueError(message)), \
                    self.assertRaises(UserError):
                certificate.get_certificate()
        # A parser returning no certificate is rejected even with a nonempty PEM.
        with patch.object(type(certificate), 'get_certificate', return_value=None), self.assertRaises(UserError):
            certificate.verify_crt()
