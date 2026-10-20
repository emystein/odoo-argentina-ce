##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import hashlib
import logging
import os
import sys
import time
import traceback

import dateutil.parser
import odoo.tools as tools
import pytz
from odoo import _, api, fields, models
from odoo.exceptions import UserError
import odoo.tools as tools

from ..exceptions import NotConfirmedCertificate
from ..tools.afip_connection_attempt import AfipConnectionAttempt
from ..tools.afip_environment import AfipEnvironment
from ..tools.key_and_certificate import KeyAndCertificate

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    alias_ids = fields.One2many(
        "afipws.certificate_alias",
        "company_id",
        "Aliases",
    )
    connection_ids = fields.One2many(
        "afipws.connection",
        "company_id",
        "Connections",
    )

    @api.model
    def get_environment(self):
        return AfipEnvironment.with_parameter_repository(self.parameter_repository())

    def get_key_and_certificate(self):
        self.ensure_one()
        certificate_repository = self.afip_certificate_repository()
        key_and_certificate = (
            certificate_repository.find_confirmed_by_company(self)
            .map(KeyAndCertificate.from_certificate)
            .default_with(lambda: KeyAndCertificate.from_configuration_for_company(self))
        )
        if key_and_certificate.are_empty():
            raise NotConfirmedCertificate.in_company(self)
        return key_and_certificate

    def get_connection(self, afip_ws):
        self.ensure_one()
        _logger.info("Getting connection for company %s and ws %s" % (self.name, afip_ws))
        now = fields.Datetime.now()
        environment = self.get_environment()
        connection = self.connection_ids.search(
            [
                ("type", "=", environment.type),
                ("generationtime", "<=", now),
                ("expirationtime", ">", now),
                ("afip_ws", "=", afip_ws),
                ("company_id", "=", self.id),
            ],
            limit=1,
        )
        if not connection:
            connection_attempt = AfipConnectionAttempt(self, afip_ws)
            connection = connection_attempt.connect()
        return connection

    @api.model
    def authenticate(
        self,
        service,
        key_and_certificate,
        force=False,
        cache="",
        wsdl="",
        proxy="",
    ):
        """
        Call AFIP Authentication webservice to get token & sign or error
        message
        """
        # import AFIP webservice authentication helper:
        from pyafipws.wsaa import WSAA

        # create AFIP webservice authentication helper instance:
        wsaa = WSAA()
        # raise python exceptions on any failure
        wsaa.LanzarExcepciones = True

        # five hours
        DEFAULT_TTL = 60 * 60 * 5

        # make md5 hash of the parameter for caching...
        fn = "%s.xml" % hashlib.md5(
            (service + key_and_certificate.cert + key_and_certificate.key).encode("utf-8")
        ).hexdigest()
        if not cache:
            cache = os.path.join(tools.config['data_dir'], 'pyafipws_cache')
            os.makedirs(cache, exist_ok=True)
        fn = os.path.join(cache, fn)

        try:
            # read the access ticket (if already authenticated)
            if not os.path.exists(fn) or os.path.getmtime(fn) + (DEFAULT_TTL) < time.time():
                # access ticket (TA) outdated, create new access request
                # ticket (TRA)
                tra = wsaa.CreateTRA(service=service, ttl=DEFAULT_TTL)
                # cryptographically sing the access ticket
                cms = wsaa.SignTRA(tra, key_and_certificate.cert, key_and_certificate.key)
                # connect to the webservice:
                wsaa.Conectar(cache, wsdl, proxy)
                # call the remote method
                ta = wsaa.LoginCMS(cms)
                if not ta:
                    raise RuntimeError()
                # write the access ticket for further consumption
                open(fn, "w").write(ta)
            else:
                # get the access ticket from the previously written file
                ta = open(fn).read()
            # analyze the access ticket xml and extract the relevant fields
            wsaa.AnalizarXml(xml=ta)
            token = wsaa.ObtenerTagXml("token")
            sign = wsaa.ObtenerTagXml("sign")
            expirationTime = wsaa.ObtenerTagXml("expirationTime")
            generationTime = wsaa.ObtenerTagXml("generationTime")
            uniqueId = wsaa.ObtenerTagXml("uniqueId")
        except Exception:
            token = sign = None
            if wsaa.Excepcion:
                # get the exception already parsed by the helper
                err_msg = wsaa.Excepcion
            else:
                # avoid encoding problem when reporting exceptions to the user:
                err_msg = traceback.format_exception_only(*sys.exc_info()[:2])[0]
            raise UserError(_("Could not connect. This is the what we received: %s") % (err_msg))
        return {
            "uniqueid": uniqueId,
            "generationtime": generationTime,
            "expirationtime": expirationTime,
            "token": token,
            "sign": sign,
        }

    def parameter_repository(self):
        return self.env["ir.config_parameter"]

    def afip_certificate_repository(self):
        return self.env["afipws.certificate"]

    def afip_connection_repository(self):
        return self.env["afipws.connection"]
