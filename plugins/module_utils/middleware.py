# This module is a thin layer between individual modules and the
# TrueNAS middleware. It talks to middlewared natively through the
# TrueNAS client library (see client.py).

# XXX - 'exceptions.py' has exceptions to use when thing fail. Use
# that instead of generic Exceptions.


class MiddleWare:
    def __init__(self):
        """Initialize the MiddleWare client.

        This method is deprecated.
        """

        self.client = MiddleWare._pick_method()

    @classmethod
    def _pick_method(cls):
        """Return the class used to interact with middlewared."""

        # Imported lazily because the TrueNAS client library only
        # exists on the TrueNAS host, not on the Ansible controller.
        from ..module_utils.client import MiddlewareClient

        return MiddlewareClient

    def call(self, func, *args, **kwargs):
        return self.client.call(func, *args, **kwargs)

    def job(self, func, *args, **kwargs):
        return self.client.job(func, *args, **kwargs)

    @classmethod
    def client(cls):
        """Return a client for interfacing with middlewared."""
        client_class = MiddleWare._pick_method()

        return client_class()
