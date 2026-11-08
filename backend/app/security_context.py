from contextvars import ContextVar

# Context propagates into FastAPI's worker threads. Never use a process-global actor.
request_principal = ContextVar('request_principal',default=None)
request_database = ContextVar('request_database', default=None)
