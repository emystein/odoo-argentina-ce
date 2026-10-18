"""Shared records and factories for AFIP WS model tests."""

from odoo.tests import TransactionCase


class AfipwsCase(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.env['ir.config_parameter'].sudo().set_param('afip.ws.env.type', 'homologation')
        self.connection = self.env['afipws.connection'].create({
            'company_id': self.company.id,
            'type': 'homologation',
            'afip_ws': 'ws_sr_padron_a5',
            'token': 'test-token',
            'sign': 'test-sign',
        })
        self.alias = self.env['afipws.certificate_alias'].create({
            'company_id': self.company.id,
            'country_id': self.env.ref('base.ar').id,
            'city': 'Buenos Aires',
            'company_cuit': '30712345678',
            'service_provider_cuit': '30787654321',
            'type': 'homologation',
            'key': 'fake-private-key',
        })

    def certificate(self, **values):
        return self.env['afipws.certificate'].create({'alias_id': self.alias.id, **values})

    def partner(self, **values):
        return self.env['res.partner'].create({
            'name': 'Original', 'country_id': self.env.ref('base.ar').id,
            'l10n_latam_identification_type_id': self.env.ref('l10n_ar.it_cuit').id,
            'vat': '30714295698', **values,
        })
