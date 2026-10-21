"""Falhas esperadas, sem corpos de resposta ou credenciais do provedor."""


class CatalogConfigurationError(Exception):
    pass


class CatalogProviderError(Exception):
    pass


class CatalogTimeoutError(Exception):
    pass


class CatalogFilterError(Exception):
    """Filtro sem correspondência exata e única; nunca removê-lo silenciosamente."""

    def __init__(self, field: str):
        self.field = field
        super().__init__("Filtro não reconhecido pelo catálogo.")


class CatalogRateLimitError(Exception):
    def __init__(self, retry_after: int = 1):
        self.retry_after = retry_after
        super().__init__("Limite de consultas ao catálogo excedido.")
