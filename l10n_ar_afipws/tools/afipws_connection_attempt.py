import dateutil.parser
import logging
import pytz

_logger = logging.getLogger(__name__)

class AfipWsConnectionAttempt:
    def __init__(self, afip_ws):
        self.afip_ws = afip_ws

    def connect(self, company):
        company.ensure_one()
        environment = company.get_environment()
        _logger.info(
            "Creating connection for company %s, environment type %s and ws "
            "%s" % (company.name, environment.type, self.afip_ws)
        )
        login_url = company.afip_connection_repository().get_afip_login_url(environment.type)
        key_and_certificate = company.get_key_and_certificate()
        authentication_result = company.authenticate(self.afip_ws, key_and_certificate, wsdl=login_url)
        self.update_authentication_result(company, environment, authentication_result)
        _logger.info("Successful Connection to AFIP.")
        return company.connection_ids.create(authentication_result)

    def update_authentication_result(self, company, environment, authentication_result):
        authentication_result.update(
            {
                "company_id": company.id,
                "afip_ws": self.afip_ws,
                "type": environment.type,
            }
        )
        authentication_result["generationtime"] = (
            dateutil.parser.parse(authentication_result["generationtime"]).astimezone(pytz.utc).replace(tzinfo=None)
        )
        authentication_result["expirationtime"] = (
            dateutil.parser.parse(authentication_result["expirationtime"]).astimezone(pytz.utc).replace(tzinfo=None)
        )
