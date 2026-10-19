import odoo.tools as tools

class AfipConfigurationParameters():
    @staticmethod
    def for_environment(environment):
        return AfipConfigurationParameters(environment)

    def __init__(self, environment):
        # self.environment_type = environment.type
        self.env = "prod" if environment.type == "production" else "homo"

    def file_path_for_file_type(self, file_type):
        return tools.config.get("afip_" + self.env + "_" + file_type + "_file")
