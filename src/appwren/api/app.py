"""The application factory."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from appwren import PRODUCT_NAME, __version__, jobs
from appwren.access.middleware import install_access
from appwren.access.policy import authorize
from appwren.api.problems import install_problem_handlers
from appwren.api.routers import (
    assessment,
    assistant,
    branding,
    catalog,
    connectors,
    decisions,
    insight,
    integration,
    inventory,
    keeping,
    landscape,
    operations,
    people,
    planning,
    program,
    reporting,
    session,
    sso,
    system,
)
from appwren.api.routers.branding import install_branding
from appwren.api.security import install_security_headers
from appwren.api.static import install_static
from appwren.config import ENV_CONFIG, Config, load_config
from appwren.db.engine import Database
from appwren.home import DataHome

ROUTERS = (
    system, session, sso, people, branding, inventory, assessment, decisions, reporting,
    landscape, operations, keeping, program, connectors, catalog, planning, insight,
    integration, assistant,
)  # fmt: skip


def create_app(config: Config) -> FastAPI:
    from appwren.program import branding as brand_rules

    brand_rules.pin(config.branding)  # the configuration file's part of the branding
    from appwren import connectors

    connectors.reserve(
        config.sso.client_secret_env, config.mail.password_env, config.assistant.key_env
    )
    home = DataHome(config.data.home)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        home.require()
        app.state.db = Database(config.database_url)
        # The scheduler runs beside the server for as long as it is up.
        stop_jobs = jobs.start_worker(app.state.db, config) if config.server.scheduler else None
        try:
            yield
        finally:
            if stop_jobs is not None:
                stop_jobs.set()
            app.state.db.dispose()

    app = FastAPI(
        title=PRODUCT_NAME,
        version=__version__,
        summary="An open system of record for application portfolio management.",
        lifespan=lifespan,
        docs_url=None,  # the bundled documentation pages load third-party scripts
        redoc_url=None,
        openapi_url="/api/openapi.json",
        dependencies=[Depends(authorize)],  # every API route is checked against the policy table
    )
    app.state.config = config
    app.state.home = home

    install_access(app)  # runs inside the header middleware, so refusals carry the headers
    install_security_headers(app)
    install_problem_handlers(app)
    for module in ROUTERS:
        app.include_router(module.router)
    install_branding(app)
    install_static(app)  # last: its catch-all would shadow anything registered after it
    return app


def create_app_from_env() -> FastAPI:
    """The factory uvicorn's workers call. ``appwren serve`` names the configuration."""
    return create_app(load_config(os.environ.get(ENV_CONFIG)))
