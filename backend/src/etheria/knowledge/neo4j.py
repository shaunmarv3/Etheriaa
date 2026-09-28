"""The Neo4j driver (spec 6.1). One async driver per process; it connects lazily."""

import neo4j
from neo4j import AsyncGraphDatabase

from etheria.core.settings import Settings


def create_driver(settings: Settings) -> neo4j.AsyncDriver:
    return AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
    )
