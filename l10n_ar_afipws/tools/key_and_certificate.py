import logging

from .afip_configuration_parameters import AfipConfigurationParameters
from .files import read_file

_logger = logging.getLogger(__name__)

class KeyAndCertificate():
    @staticmethod
    def empty():
        return KeyAndCertificate(None, None)

    @staticmethod
    def from_certificate(certificate):
        credentials = certificate.key_and_certificate()
        _logger.info("Using DB certificates")
        return credentials

    @staticmethod
    def from_configuration(environment):
        credentials = KeyAndCertificate.from_environment_configuration(environment)
        _logger.info("Using odoo conf certificates")
        return credentials

    @staticmethod
    def from_environment_configuration(environment):
        parameters = AfipConfigurationParameters.for_environment(environment)
        pkey_path = parameters.file_path_for_file_type("pkey")
        cert_path = parameters.file_path_for_file_type("cert")
        return KeyAndCertificate.from_paths(pkey_path, cert_path)

    @staticmethod
    def from_paths(pkey_path, cert_path):
        pkey = read_file(pkey_path)
        cert = read_file(cert_path)
        return KeyAndCertificate(pkey, cert)

    def __init__(self, key, cert):
        self.key = key
        self.cert = cert

    def are_empty(self):
        return not self.key or not self.cert

    def as_tuple(self):
        return (self.key, self.cert)

