class PrivateKeyCertificatePair():
    @staticmethod
    def empty():
        return PrivateKeyCertificatePair(None, None)

    def __init__(self, pkey, cert):
        self.pkey = pkey
        self.cert = cert

    def is_empty(self):
        return not self.pkey or not self.cert

    def as_tuple(self):
        return (self.pkey, self.cert)
