import odoo.tools as tools

class AfipConfigurationParameters():
    @staticmethod
    def for_environment(environment_type):
        return AfipConfigurationParameters(environment_type)

    def __init__(self, environment_type):
        self.environment_type = environment_type
        self.env = "prod" if self.environment_type == "production" else "homo"

    def file_path_for_file_type(self, file_type):
        return tools.config.get("afip_" + self.env + "_" + file_type + "_file")
