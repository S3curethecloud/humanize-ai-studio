class RewriteProviderError(RuntimeError):
    """Base error raised by rewrite providers."""


class RewriteProviderConfigurationError(RewriteProviderError):
    """Raised when provider configuration is incomplete or invalid."""


class RewriteProviderTransportError(RewriteProviderError):
    """Raised when the provider cannot be reached."""


class RewriteProviderResponseError(RewriteProviderError):
    """Raised when a provider returns an invalid or unsuccessful response."""
