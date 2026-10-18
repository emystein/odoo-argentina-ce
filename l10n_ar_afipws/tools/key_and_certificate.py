class KeyAndCertificate():
    @staticmethod
    def empty():
        return KeyAndCertificate(None, None)

    def __init__(self, key, cert):
        self.key = key
        self.cert = cert

    def is_empty(self):
        return not self.key or not self.cert

    def as_tuple(self):
        return (self.key, self.cert)
