"""Shared helper — connect to the local Iceberg REST catalog backed by MinIO.

Both the learner code and the test rubric import `get_catalog()` from here.
Centralising the connection means a single endpoint configuration to keep in
sync between dev (the devcontainer) and CI (the GitHub Actions runner).

Endpoints are hardcoded on purpose: this stack is local-only, there are no
secrets to leak, and overriding them via env vars would be one more knob a
learner could turn the wrong way.
"""

from __future__ import annotations

from pyiceberg.catalog import load_catalog
from pyiceberg.catalog.rest import RestCatalog

CATALOG_NAME = "local"
NAMESPACE = "default"
TABLE_NAME = "orders_v1"
TABLE_IDENTIFIER = f"{NAMESPACE}.{TABLE_NAME}"

REST_URI = "http://localhost:8181"
S3_ENDPOINT = "http://localhost:9000"
S3_ACCESS_KEY = "admin"
S3_SECRET_KEY = "password"
WAREHOUSE = "s3://warehouse/"


def get_catalog() -> RestCatalog:
    """Return a PyIceberg `RestCatalog` configured against the local stack.

    PyIceberg's `load_catalog` builds the right subclass from the `type=` key
    in **properties. We use the REST catalog because that's what `tabulario/iceberg-rest`
    exposes.
    """
    return load_catalog(
        CATALOG_NAME,
        **{
            "type": "rest",
            "uri": REST_URI,
            "s3.endpoint": S3_ENDPOINT,
            "s3.access-key-id": S3_ACCESS_KEY,
            "s3.secret-access-key": S3_SECRET_KEY,
            "s3.path-style-access": "true",
            "warehouse": WAREHOUSE,
        },
    )


def ensure_namespace(catalog: RestCatalog) -> None:
    """Create the `default` namespace if it doesn't exist. Idempotent."""
    existing = {ns[0] if isinstance(ns, tuple) else ns for ns in catalog.list_namespaces()}
    if NAMESPACE not in existing:
        catalog.create_namespace(NAMESPACE)
