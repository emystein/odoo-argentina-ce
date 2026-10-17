##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    afip_ws_env_type = fields.Selection(
        [("homologation", "Homologación"), ("production", "Producción")],
        string="Entorno de ARCA",
        config_parameter="afip.ws.env.type",
    )

    arca_certificate_id = fields.Many2one(
        "afipws.certificate", string="Certificado",
        compute="_compute_arca_certificate",
        help="Certificado confirmado utilizado por la empresa en el entorno seleccionado.",
    )

    @api.depends("company_id", "afip_ws_env_type")
    def _compute_arca_certificate(self):
        for settings in self:
            settings.arca_certificate_id = self.env["afipws.certificate"].search([
                ("alias_id.company_id", "=", settings.company_id.id),
                ("alias_id.type", "=", settings.afip_ws_env_type or settings.company_id._get_environment_type()),
                ("state", "=", "confirmed"),
            ], limit=1)

    def action_arca_certificates(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "l10n_ar_afipws.act_afipws_certificate_alias")
        action.update({
            "domain": [("company_id", "=", self.company_id.id)],
            "context": {
                "default_company_id": self.company_id.id,
                "default_type": self.afip_ws_env_type or self.company_id._get_environment_type(),
            },
        })
        return action

    def action_arca_connections(self):
        self.ensure_one()
        self.execute()
        services = dict(self.env["afipws.connection"]._fields["afip_ws"]._description_selection(self.env))
        results = []
        for service in ("wsfe", "ws_sr_padron_a5"):
            if service not in services:
                continue
            try:
                with self.env.cr.savepoint():
                    connection = self.company_id.get_connection(service)
                    results.append(_("%s: autenticación correcta (vence %s)") % (
                        service, connection.expirationtime))
            except Exception as error:
                results.append("%s: %s" % (service, error))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Conexiones AFIP/ARCA"),
                "message": "\n".join(results),
                "type": "info",
                "sticky": True,
            },
        }

    def action_arca_certificate_request(self):
        action = self.action_arca_certificates()
        action.update({"view_mode": "form", "views": [(False, "form")], "target": "new"})
        return action
