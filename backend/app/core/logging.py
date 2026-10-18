"""Evita que mensagens brutas do SDK exponham conteúdo do provedor nos logs."""

import logging


class AgentLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = "Evento do Agents SDK; detalhes omitidos por privacidade."
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


def configure_agent_logging() -> None:
    logger = logging.getLogger("openai.agents")
    if not any(isinstance(item, AgentLogFilter) for item in logger.filters):
        logger.addFilter(AgentLogFilter())
