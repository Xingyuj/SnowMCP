import ssl

import truststore


def system_ssl_context() -> ssl.SSLContext:
    """Use the OS trust store, including enterprise-managed root certificates."""
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
