import logging

import odoo.tools as tools

_logger = logging.getLogger(__name__)

class AfipEnvironment:
    @staticmethod
    def with_parameter_repository(parameter_repository):
        """
        Function to define homologation/production environment
        First it search for a paramter "afip.ws.env.type" if exists and:
        * is production --> production
        * is homologation --> homologation
        Else
        Search for 'server_mode' parameter on conf file. If that parameter is:
        * 'test' or 'develop' -->  homologation
        * other or no parameter -->  production
        """
        parameter_env_type = parameter_repository.sudo().get_param("afip.ws.env.type")
        if parameter_env_type == "production":
            environment_type = "production"
        elif parameter_env_type == "homologation":
            environment_type = "homologation"
        else:
            server_mode = tools.config.get("server_mode")
            if not server_mode or server_mode == "production":
                environment_type = "production"
            else:
                environment_type = "homologation"
        _logger.info("Running arg electronic invoice on %s mode" % environment_type)
        return AfipEnvironment(environment_type)

    def __init__(self, type):
        self.type = type
