"""Falhas esperadas da integração, sem detalhes sensíveis do provedor."""


class AIConfigurationError(Exception):
    pass


class AIProviderError(Exception):
    pass


class AITimeoutError(Exception):
    pass
