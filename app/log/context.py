import structlog


def set_thread_context(thread_id: str):
    structlog.contextvars.bind_contextvars(thread_id=thread_id)


def clear_thread_context():
    structlog.contextvars.clear_contextvars()
