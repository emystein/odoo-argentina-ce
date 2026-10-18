from types import SimpleNamespace
from unittest.mock import Mock, patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from . import common


@tagged('post_install', '-at_install')
class TestResPartner(common.AfipwsCase):
    def census(self, **values):
        return SimpleNamespace(**dict(dict(imp_iva='AC', denominacion='EMPRESA TEST', direccion='CALLE 123',
                                          localidad='Rosario', cod_postal='2000', impuestos=[],
                                          monotributo='N', provincia=''), **values))

    def test_parse_mock_padron(self):
        census = SimpleNamespace(
            imp_iva='S', denominacion='Empresa de prueba', direccion='Calle 123',
            localidad='Rosario', cod_postal='2000', impuestos=[10], monotributo='N', provincia='',
        )
        vals = self.env['res.partner'].parce_census_vals(census)
        self.assertEqual(vals['name'], census.denominacion)
        self.assertEqual(vals['imp_iva_padron'], 'AC')
        self.assertEqual(vals['imp_ganancias_padron'], 'AC')
        self.assertEqual(vals['l10n_ar_afip_responsibility_type_id'], self.env.ref('l10n_ar.res_IVARI').id)
        census.imp_iva = 'N'
        census.monotributo = 'S'
        census.impuestos = []
        vals = self.env['res.partner'].parce_census_vals(census)
        self.assertEqual(vals['imp_ganancias_padron'], 'NC')
        self.assertEqual(vals['l10n_ar_afip_responsibility_type_id'], self.env.ref('l10n_ar.res_RM').id)

    def test_padron_tax_and_province_mapping(self):
        partner = self.env['res.partner']
        for values, tax in [({'imp_iva': 'EX', 'impuestos': [12]}, 'EX'),
                            ({'imp_iva': 'NI'}, None),
                            ({'imp_iva': 'NI', 'monotributo': 'N'}, None)]:
            result = partner.parce_census_vals(self.census(**values))
            self.assertEqual(result.get('imp_ganancias_padron'), tax)
        for province, city in [('Santa Fe', 'Rosario'), ('Capital Federal', ''), ('Inexistente', 'Ciudad')]:
            result = partner.parce_census_vals(self.census(provincia=province, localidad=city))
            if province == 'Inexistente':
                self.assertNotIn('state_id', result)
            else:
                self.assertTrue(result['state_id'])

    def test_padron_lookup_fallback_and_failures(self):
        partner = self.partner()
        ws = Mock(**vars(self.census()))
        with patch.object(type(partner), 'ensure_vat', return_value='30714295698'), \
                patch.object(type(self.company), 'get_connection', return_value=self.connection), \
                patch.object(type(self.connection), 'connect', return_value=ws), \
                patch.object(type(self.company), 'get_key_and_certificate', return_value=('key', 'crt')):
            self.assertEqual(partner.get_data_from_padron_afip()['name'], 'EMPRESA TEST')
            ws.Consultar.assert_called_once_with('30714295698')
            ws.Consultar.side_effect = RuntimeError('service error')
            with self.assertRaisesRegex(UserError, 'service error'):
                partner.get_data_from_padron_afip()
            ws.Consultar.side_effect = None
            for name in [False, ', ']:
                ws.denominacion = name
                with self.assertRaisesRegex(UserError, 'no devolvió nombre'):
                    partner.get_data_from_padron_afip()
            ws.denominacion = 'Fallback'
            with patch.object(type(self.company), 'get_key_and_certificate', side_effect=UserError('missing')):
                with self.assertRaisesRegex(UserError, 'Not confirmed certificate'):
                    partner.get_data_from_padron_afip()
                self.certificate(state='confirmed', crt='mock')
                self.assertEqual(partner.get_data_from_padron_afip()['name'], 'Fallback')

    def test_credit_invoice_threshold(self):
        partner = self.partner()
        ws = Mock(Resultado='S')
        ws.ConsultarMontoObligadoRecepcion.return_value = '1000.50'
        with patch.object(type(self.company), 'get_connection', return_value=self.connection), \
                patch.object(type(self.connection), 'connect', return_value=ws):
            partner.l10n_ar_afipws_fe_min_ammount()
            self.assertTrue(partner.mipyme_required)
            self.assertEqual(partner.mipyme_from_amount, 1000.5)
            ws.Resultado = 'N'
            partner.l10n_ar_afipws_fe_min_ammount()
            self.assertFalse(partner.mipyme_required)
            partner.vat = False
            ws.ConsultarMontoObligadoRecepcion.reset_mock()
            partner.l10n_ar_afipws_fe_min_ammount()
            ws.ConsultarMontoObligadoRecepcion.assert_not_called()
