import os

from odoo.exceptions import UserError

def read_file(path):
    if path:
        try:
            if os.path.isfile(path):
                with open(path) as file:
                    return file.read()
        except Exception as error:
            raise UserError("Could not read %s file" % path) from error
    return False
