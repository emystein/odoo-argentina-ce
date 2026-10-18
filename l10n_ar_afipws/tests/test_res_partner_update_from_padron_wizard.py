from types import SimpleNamespace
from unittest.mock import Mock, patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from . import common
from ..wizard.res_partner_update_from_padron_wizard import ResPartnerUpdateFromPadronWizard


@tagged('post_install', '-at_install')
class TestResPartnerUpdateFromPadronWizard(common.AfipwsCase):
    def wizard(self, **values):
        return self.env['res.partner.update.from.padron.wizard'].create({
            'partner_ids': [(5, 0, 0)], **values,
        })

    def test_padron_wizard_defaults(self):
        model = self.env['res.partner.update.from.padron.wizard']
        partner = self.partner()
        invalid = self.partner(vat=False)
        for parameter, expected in [('False', False), ('0', False), ('True', True)]:
            self.env['ir.config_parameter'].set_param('use_title_case_on_padron_afip', parameter)
            self.assertEqual(model._get_default_title_case(), expected)
        model.get_partners()
        with self.assertRaises(UserError):
            model.with_context(active_model='res.partner', active_ids=[invalid.id]).default_get(['state'])
        defaults = model.with_context(active_model='res.partner', active_ids=[partner.id]).default_get(['state'])
        self.assertEqual(defaults['partner_id'], partner.id)
        self.assertEqual(defaults['state'], 'selection')
        other = self.partner(name='Other')
        defaults = model.with_context(active_model='res.partner', active_ids=[partner.id, other.id]).default_get(['state'])
        self.assertEqual(defaults['state'], 'option')

    def test_padron_wizard_selection_and_automatic_updates(self):
        partner = self.partner()
        other = self.partner(name='Other')
        wizard = self.wizard(partner_ids=[(6, 0, [partner.id, other.id])])
        with patch.object(type(partner), 'get_data_from_padron_afip', return_value={
            'name': 'NUEVO NOMBRE', 'street': '', 'city': 'ROSARIO',
            'l10n_ar_afip_responsibility_type_id': self.env.ref('l10n_ar.res_IVARI').id,
        }):
            self.assertEqual(wizard.start_process_cb()['res_id'], wizard.id)
            self.assertEqual(wizard.state, 'selection')
            self.assertTrue(wizard.field_ids)
            wizard.update_selection()
            self.assertEqual(partner.name, 'Nuevo Nombre')
            self.assertEqual(wizard.partner_id, other)
            wizard.automatic_process_cb()
            self.assertEqual(other.city, 'Rosario')
            self.assertEqual(wizard.state, 'finished')
            wizard.partner_ids = False
            wizard.next_cb()
            self.assertEqual(wizard.state, 'finished')
        empty = self.wizard()
        empty.change_partner()
        empty.next_cb()
        self.assertEqual(empty.update_selection()['res_id'], empty.id)
        self.assertEqual(empty.state, 'finished')

    def test_padron_wizard_unchanged_and_no_title_case(self):
        partner = self.partner()
        wizard = self.wizard(partner_id=partner.id, title_case=False)
        with patch.object(type(partner), 'get_data_from_padron_afip', return_value={'name': partner.name}):
            wizard.change_partner()
            self.assertFalse(wizard.field_ids)
        with patch.object(type(partner), 'get_data_from_padron_afip', return_value={'name': 'UPPERCASE'}):
            wizard.change_partner()
            wizard._update()
            self.assertEqual(partner.name, 'UPPERCASE')

    def test_padron_wizard_extension_relational_fields(self):
        # Extensions can provide these many2many fields. Exercise their command
        # conversion without installing an unrelated extension in this suite.
        partner = Mock()
        partner.__getitem__ = Mock(return_value=SimpleNamespace(ids=[1]))
        partner.get_data_from_padron_afip.return_value = {'impuestos_padron': [2]}
        wizard = SimpleNamespace(ensure_one=Mock(), field_ids=Mock(), partner_id=partner,
                                 field_to_update_ids=Mock(), title_case=False, id=1)
        wizard.field_to_update_ids.mapped.return_value = ['impuestos_padron']
        ResPartnerUpdateFromPadronWizard.change_partner(wizard)
        self.assertEqual(wizard.field_ids[0][2]['new_value'], [2])
        wizard.field_ids = [SimpleNamespace(field='impuestos_padron', new_value='[2]')]
        ResPartnerUpdateFromPadronWizard._update(wizard)
        partner.write.assert_called_once_with({'impuestos_padron': [(6, False, [2])]})
