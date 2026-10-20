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
        """
        Funcion que busca para el environment definido,
        una clave y un certificado en los siguientes lugares y segun estas
        prioridades:
        * en el conf del server de odoo
        * en registros de esta misma clase
        """
        self.ensure_one()
        environment = self.get_environment()
        key_and_certificate = KeyAndCertificate.empty()
        certificate_repository = self.afip_certificate_repository()
        certificate = certificate_repository.find_confirmed_by_company(self)
        if certificate:
            key_and_certificate = certificate.key_and_certificate()
            _logger.info("Using DB certificates")
        # not certificate on bd, we search on odoo conf file
        else:
            key_and_certificate = KeyAndCertificate.from_environment_configuration(environment)
            _logger.info("Using odoo conf certificates")
        if key_and_certificate.is_empty():
            msg = _("Not confirmed certificate for %s on company %s") % (environment.type, self.name)
            raise UserError(msg)
        return key_and_certificate.as_tuple()

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
            connection = self._create_connection(afip_ws)
        return connection

    def _create_connection(self, afip_ws):
        """
        This function should be called from get_connection. Not to be used
        directyl
        TODO ver si podemos usar metodos de pyafipws para esto
        """
        self.ensure_one()
        environment = self.get_environment()
        _logger.info(
            "Creating connection for company %s, environment type %s and ws "
            "%s" % (self.name, environment.type, afip_ws)
        )
        login_url = self.env["afipws.connection"].get_afip_login_url(environment.type)
        pkey, cert = self.get_key_and_certificate()
        # because pyafipws wsaa loos for "BEGIN RSA PRIVATE KEY" we change key
        if pkey.startswith("-----BEGIN PRIVATE KEY-----"):
            pkey = pkey.replace(" PRIVATE KEY", " RSA PRIVATE KEY")
        auth_data = self.authenticate(afip_ws, cert, pkey, wsdl=login_url)
        auth_data.update(
            {
                "company_id": self.id,
                "afip_ws": afip_ws,
                "type": environment.type,
            }
        )

        auth_data["generationtime"] = (
            dateutil.parser.parse(auth_data["generationtime"]).astimezone(pytz.utc).replace(tzinfo=None)
        )
        auth_data["expirationtime"] = (
            dateutil.parser.parse(auth_data["expirationtime"]).astimezone(pytz.utc).replace(tzinfo=None)
        )

        _logger.info("Successful Connection to AFIP.")
        return self.connection_ids.create(auth_data)

    @api.model
    def authenticate(
        self,
        service,
        certificate,
        private_key,
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
        fn = "%s.xml" % hashlib.md5((service + certificate + private_key).encode("utf-8")).hexdigest()
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
                cms = wsaa.SignTRA(tra, certificate, private_key)
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

