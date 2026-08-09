##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import base64

from odoo import api, fields, models


class L10nArAfipwsUploadCertificate(models.TransientModel):
    _name = "afipws.upload_certificate.wizard"
    _description = "afipws.upload_certificate.wizard"

    @api.model
    def _default_certificate(self):
        if self._context.get('active_model') == 'afipws.certificate':
            return self.env['afipws.certificate'].browse(
                self._context.get('active_id'))
        return False

    @api.model
    def _default_alias(self):
        if self._context.get('active_model') == 'afipws.certificate_alias':
            return self.env['afipws.certificate_alias'].browse(
                self._context.get('active_id'))
        return False

    certificate_id = fields.Many2one(
        "afipws.certificate",
        required=True,
        readonly=True,
        default=_default_certificate,
        ondelete="cascade",
    )
    alias_id = fields.Many2one(
        'afipws.certificate_alias',
        readonly=True,
        default=_default_alias,
        ondelete='cascade',
    )
    certificate_file = fields.Binary("Upload Certificate", required=True)
    certificate_key_file = fields.Binary(
        'Upload Private Key',
        help='Optional. Provide the private key (.key) matching this '
        'certificate when the key pair was generated outside of Odoo.'
    )

    def action_confirm(self):
        self.ensure_one()
        alias = self.alias_id or self.certificate_id.alias_id
        if self.certificate_key_file:
            alias.write(
                {'key': base64.decodebytes(self.certificate_key_file)})
        certificate = self.certificate_id
        if not certificate:
            if not alias.key:
                raise UserError(_(
                    'The alias has no private key. Please upload the '
                    'private key (.key) file corresponding to this '
                    'certificate.'))
            certificate = self.env['afipws.certificate'].create({
                'alias_id': alias.id,
                'crt': base64.decodebytes(self.certificate_file),
            })
        else:
            certificate.write(
                {'crt': base64.decodebytes(self.certificate_file)})
        certificate.action_confirm()
        return True
