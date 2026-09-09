from __future__ import annotations

import inspect
import logging
from urllib.parse import urlparse

from services.agents_service.admin.agent_factory import create_agent
from services.agents_service.chat.service import AgentsService
from shared.config import get_settings
from shared.logging import get_logger, resolve_log_level

logger = get_logger(__name__)

DEFAULT_DEPLOYMENT_REQUIREMENTS = [
    "google-cloud-aiplatform[agent_engines,adk]==2.0.1",
    "requests==2.34.2",
    "python-dotenv==1.1.1",
]
DEFAULT_EXTRA_PACKAGES = ["services", "shared"]


def _required(value: str | None, name: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


def _validate_runtime_url(name: str, value: str) -> str:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1"}:
        raise ValueError(f"{name} must be reachable from Agent Runtime and cannot be localhost: {value}")
    return value


def _resource_name(agent_engine: object) -> str:
    for attr in ("resource_name", "name"):
        value = getattr(agent_engine, attr, None)
        if isinstance(value, str) and value:
            return value
    gca_resource = getattr(agent_engine, "gca_resource", None)
    if gca_resource is not None:
        value = getattr(gca_resource, "name", None)
        if isinstance(value, str) and value:
            return value
    raise RuntimeError("Deployment did not return a runtime resource name")


def _run_vertex_delete(resource_name: str) -> None:
    from vertexai import agent_engines as vertex_agent_engines

    if hasattr(vertex_agent_engines, "delete"):
        delete_fn = getattr(vertex_agent_engines, "delete")
        signature = inspect.signature(delete_fn)
        kwargs: dict[str, object] = {}
        if "force" in signature.parameters:
            kwargs["force"] = True
        if "resource_name" in signature.parameters:
            delete_fn(resource_name=resource_name, **kwargs)
            return
        if "name" in signature.parameters:
            delete_fn(name=resource_name, **kwargs)
            return
        delete_fn(resource_name, **kwargs)
        return

    engine = vertex_agent_engines.get(resource_name)
    if not hasattr(engine, "delete"):
        raise RuntimeError("Vertex Agent Engine SDK does not expose delete operation")
    delete_method = getattr(engine, "delete")
    method_signature = inspect.signature(delete_method)
    if "force" in method_signature.parameters:
        delete_method(force=True)
        return
    delete_method()


class AgentDeployer:
    def __init__(self) -> None:
        self._settings = get_settings()

    def deploy(self, agent_definition: dict) -> str:
        import vertexai
        from vertexai import agent_engines as vertex_agent_engines
        from vertexai import types
        from vertexai.agent_engines import AdkApp

        project_id = _required(self._settings.project_id, "PROJECT_ID")
        location = _required(self._settings.google_cloud_location, "GOOGLE_CLOUD_LOCATION")
        staging_bucket = _required(self._settings.agent_staging_bucket, "AGENT_STAGING_BUCKET")

        articles_service_url = _validate_runtime_url("ARTICLES_SERVICE_URL", self._settings.articles_service_url)
        users_service_url = _validate_runtime_url("USERS_SERVICE_URL", self._settings.users_service_url)
        identity_type = types.IdentityType(self._settings.agent_identity_type)
        service_account = (self._settings.agent_runtime_service_account or "").strip() or None

        if identity_type == types.IdentityType.AGENT_IDENTITY and service_account:
            raise ValueError("AGENT_IDENTITY cannot be used with AGENT_RUNTIME_SERVICE_ACCOUNT")
        if identity_type == types.IdentityType.SERVICE_ACCOUNT and not service_account:
            raise ValueError("SERVICE_ACCOUNT requires AGENT_RUNTIME_SERVICE_ACCOUNT")

        vertexai.init(project=project_id, location=location, staging_bucket=staging_bucket)
        app = AdkApp(agent=create_agent(agent_definition, AgentsService(bearer_token="")))
        log_level = _required(self._settings.log_level, "LOG_LEVEL")
        remote = vertex_agent_engines.create(
            agent_engine=app,
            requirements=DEFAULT_DEPLOYMENT_REQUIREMENTS,
            extra_packages=DEFAULT_EXTRA_PACKAGES,
            display_name=f"user-agent-{agent_definition['id']}",
            env_vars={
                "PROJECT_ID": project_id,
                "ARTICLES_SERVICE_URL": articles_service_url,
                "USERS_SERVICE_URL": users_service_url,
                "LOG_LEVEL": log_level,
            },
            service_account=service_account,
            identity_type=identity_type,
        )
        resource_name = _resource_name(remote)
        logger.info("Deployed agent_id=%s resource=%s", agent_definition["id"], resource_name)
        return resource_name

    def undeploy(self, resource_name: str) -> None:
        import vertexai

        if not resource_name.strip():
            return
        project_id = _required(self._settings.project_id, "PROJECT_ID")
        location = _required(self._settings.google_cloud_location, "GOOGLE_CLOUD_LOCATION")
        staging_bucket = _required(self._settings.agent_staging_bucket, "AGENT_STAGING_BUCKET")
        vertexai.init(project=project_id, location=location, staging_bucket=staging_bucket)
        _run_vertex_delete(resource_name)
        logger.info("Undeployed resource=%s", resource_name)
