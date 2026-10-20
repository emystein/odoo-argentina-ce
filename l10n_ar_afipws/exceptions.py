from odoo import _
from odoo.exceptions import UserError


class NotConfirmedCertificate(UserError):
    @staticmethod
    def in_company(company):
        return NotConfirmedCertificate(company)

    def __init__(self, company):
        environment = company.get_environment()
        super().__init__(
            _("Not confirmed certificate for %s on company %s") % (environment.type, company.name)
        )
