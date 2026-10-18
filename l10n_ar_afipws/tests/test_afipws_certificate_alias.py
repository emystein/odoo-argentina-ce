from odoo.exceptions import ValidationError
from odoo.tests import tagged

from . import common


@tagged('post_install', '-at_install')
class TestAfipwsCertificateAlias(common.AfipwsCase):
    def test_alias_cuit_and_cancel_certificates(self):
        self.assertEqual(self.alias.cuit, self.alias.company_cuit)
        self.alias.service_type = 'outsourced'
        self.assertEqual(self.alias.cuit, self.alias.service_provider_cuit)
        certificate = self.env['afipws.certificate'].create({'alias_id': self.alias.id})
        self.alias.action_cancel()
        self.assertEqual(certificate.state, 'cancel')
        self.assertEqual(self.alias.state, 'cancel')

    def test_alias_name_limit(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.alias.common_name = 'x' * 51

    def test_alias_onchanges_key_and_request(self):
        empty = self.env['afipws.certificate_alias'].new({'company_id': False})
        empty.change_company_name()
        empty.change_company_id()
        self.alias.change_company_name()
        self.assertEqual(self.alias.common_name, ('AFIP WS homologation - ' + self.company.name)[:50])
        self.company.write({'country_id': self.env.ref('base.ar').id, 'city': 'Rosario'})
        self.alias.change_company_id()
        self.assertEqual(self.alias.city, 'Rosario')
        self.assertEqual(self.alias.country_id, self.company.country_id)
        self.alias.company_cuit = '30714295698'
        self.alias.key = False
        self.alias.action_confirm()
        self.assertIn('PRIVATE KEY', self.alias.key)
        for state in [False, self.env['res.country.state'].search([('country_id.code', '=', 'AR')], limit=1)]:
            self.alias.state_id = state
            action = self.alias.action_create_certificate_request()
            certificate = self.env['afipws.certificate'].browse(action['res_id'])
            self.assertIn('CERTIFICATE REQUEST', certificate.csr)
        self.alias.action_to_draft()
        self.assertEqual(self.alias.state, 'draft')
