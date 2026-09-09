#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import vertexai
from vertexai import types
from vertexai import agent_engines as vertex_agent_engines
from vertexai.agent_engines import AdkApp

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.agents_service.admin.default_agents import build_articles_agent, build_users_agent
from services.agents_service.chat.service import AgentsService
from shared.config import get_settings

DEFAULT_REQUIREMENTS = [
    "google-cloud-aiplatform[agent_engines,adk]==2.0.1",
    "requests==2.34.2",
    "python-dotenv==1.1.1",
]


def _required(name: str, cli_value: str | None, settings) -> str:
    value = (cli_value or "").strip()
    if not value:
        value = str(getattr(settings, name.lower(), "") or "").strip()
    if not value:
        raise ValueError(f"Missing required value for {name}")
    return value


def _ensure_local_packaging_deps() -> None:
    try:
        import cloudpickle  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Missing local dependency 'cloudpickle'. Install deployment extras with "
            "'pip install -r requirements.txt' (or 'pip install \"google-cloud-aiplatform[agent_engines]\"')."
        ) from exc


def _validate_runtime_url(name: str, value: str) -> str:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1"}:
        raise ValueError(
            f"{name} cannot use localhost for deployed agents: {value}. "
            "Use your deployed service URL."
        )
    return value


def _deploy_one(
    *,
    app: AdkApp,
    display_name: str,
    env_vars: dict[str, str],
    requirements: list[str],
    extra_packages: list[str],
    identity_type: types.IdentityType,
    service_account: str | None,
) -> object:
    if identity_type == types.IdentityType.AGENT_IDENTITY and service_account:
        raise ValueError(
            "AGENT_IDENTITY cannot be combined with --service-account. "
            "Unset AGENT_RUNTIME_SERVICE_ACCOUNT/--service-account, or set --identity-type SERVICE_ACCOUNT."
        )

    if identity_type == types.IdentityType.SERVICE_ACCOUNT and not service_account:
        raise ValueError(
            "SERVICE_ACCOUNT identity requires --service-account (or AGENT_RUNTIME_SERVICE_ACCOUNT)."
        )

    return vertex_agent_engines.create(
        agent_engine=app,
        requirements=requirements,
        extra_packages=extra_packages,
        display_name=display_name,
        env_vars=env_vars,
        service_account=service_account,
        identity_type=identity_type,
    )


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
    return "<unknown-resource-name>"


def main() -> None:
    settings = get_settings()

    parser = argparse.ArgumentParser(
        description="Deploy articles and users agents to Vertex Agent Engine.",
    )
    parser.add_argument("--project-id", default=settings.project_id)
    parser.add_argument("--location", default=settings.google_cloud_location)
    parser.add_argument("--staging-bucket", default=settings.agent_staging_bucket)
    parser.add_argument(
        "--identity-type",
        choices=["AGENT_IDENTITY", "SERVICE_ACCOUNT"],
        default=settings.agent_identity_type,
        help="Runtime identity mode for Agent Engine.",
    )
    parser.add_argument(
        "--service-account",
        default=settings.agent_runtime_service_account,
        help="Required only when --identity-type SERVICE_ACCOUNT.",
    )
    parser.add_argument(
        "--articles-display-name",
        default="my-articles-agent-runtime",
    )
    parser.add_argument(
        "--users-display-name",
        default="my-users-agent-runtime",
    )
    parser.add_argument(
        "--articles-service-url",
        default=settings.articles_service_url,
        help="Articles service base URL reachable from Agent Runtime.",
    )
    parser.add_argument(
        "--users-service-url",
        default=settings.users_service_url,
        help="Users service base URL reachable from Agent Runtime.",
    )
    args = parser.parse_args()

    project_id = _required("PROJECT_ID", args.project_id, settings)
    location = _required("GOOGLE_CLOUD_LOCATION", args.location, settings)
    staging_bucket = _required("AGENT_STAGING_BUCKET", args.staging_bucket, settings)
    articles_service_url = _required("ARTICLES_SERVICE_URL", args.articles_service_url, settings)
    users_service_url = _required("USERS_SERVICE_URL", args.users_service_url, settings)
    articles_service_url = _validate_runtime_url("ARTICLES_SERVICE_URL", articles_service_url)
    users_service_url = _validate_runtime_url("USERS_SERVICE_URL", users_service_url)
    identity_type = types.IdentityType(args.identity_type)

    _ensure_local_packaging_deps()
    os.chdir(BACKEND_DIR)
    vertexai.init(project=project_id, location=location, staging_bucket=staging_bucket)

    # Agent definitions require an AgentsService instance, but deployment does not use bearer auth.
    service = AgentsService(bearer_token="")
    articles_app = AdkApp(agent=build_articles_agent(service))
    users_app = AdkApp(agent=build_users_agent(service))

    env_vars = {
        "PROJECT_ID": project_id,
        "ARTICLES_SERVICE_URL": articles_service_url,
        "USERS_SERVICE_URL": users_service_url,
    }
    extra_packages = ["services", "shared"]

    articles_remote = _deploy_one(
        app=articles_app,
        display_name=args.articles_display_name,
        env_vars=env_vars,
        requirements=DEFAULT_REQUIREMENTS,
        extra_packages=extra_packages,
        identity_type=identity_type,
        service_account=args.service_account,
    )
    users_remote = _deploy_one(
        app=users_app,
        display_name=args.users_display_name,
        env_vars=env_vars,
        requirements=DEFAULT_REQUIREMENTS,
        extra_packages=extra_packages,
        identity_type=identity_type,
        service_account=args.service_account,
    )

    print("Agents deployed successfully:")
    print(f"- articles_agent: {_resource_name(articles_remote)}")
    print(f"- users_expert_agent: {_resource_name(users_remote)}")


if __name__ == "__main__":
    main()
