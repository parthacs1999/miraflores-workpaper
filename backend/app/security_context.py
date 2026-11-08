from contextvars import ContextVar

# Context propagates into FastAPI's worker threads. Never use a process-global actor.
request_principal = ContextVar('request_principal',default=None)
request_database = ContextVar('request_database', default=None)

# Optional request-scoped path for disposable public sandboxes. Never set in secure profiles.
request_database_path = ContextVar('request_database_path', default=None)
