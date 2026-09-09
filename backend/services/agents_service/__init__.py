# Keep compatibility with ADK loader that expects `root_agent`.
try:
    from .admin.default_agents import root_agent
except ModuleNotFoundError:  # pragma: no cover - allows non-ADK contexts to import service package
    root_agent = None

__all__ = ["root_agent"]