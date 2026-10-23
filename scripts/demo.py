"""Run a safe, self-contained DevMeter demonstration."""

import asyncio
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command
from dev_meter.app import create_app
from dev_meter.core.config import Settings
from dev_meter.services.auth import password_hasher


def main() -> None:
    """Run the complete demo against a disposable SQLite database."""
    with TemporaryDirectory(prefix="dev-meter-demo-") as directory:
        database_path = Path(directory) / "demo.db"
        database_url = f"sqlite:///{database_path}"
        settings = Settings(
            database_url=database_url,
            environment="testing",
            admin_username="demo-admin",
            admin_password_hash=password_hasher.hash("demo-password"),
            jwt_secret="demo-jwt-secret-that-is-long-enough",
        )

        previous_database_url = os.environ.get("DEVMETER_DATABASE_URL")
        os.environ["DEVMETER_DATABASE_URL"] = database_url
        try:
            command.upgrade(Config("alembic.ini"), "head")
        finally:
            if previous_database_url is None:
                os.environ.pop("DEVMETER_DATABASE_URL", None)
            else:
                os.environ["DEVMETER_DATABASE_URL"] = previous_database_url

        with TestClient(create_app(settings)) as client:
            login = client.post(
                "/v1/auth/login",
                json={"username": "demo-admin", "password": "demo-password"},
            )
            management_headers = {
                "Authorization": f"Bearer {login.json()['access_token']}"
            }
            original_http_client = client.app.state.http_client

            def mock_upstream(request: httpx.Request) -> httpx.Response:
                return httpx.Response(
                    200,
                    json={"demo": True, "received": json.loads(request.read())},
                )

            demo_http_client = httpx.AsyncClient(
                transport=httpx.MockTransport(mock_upstream)
            )
            client.app.state.http_client = demo_http_client
            try:
                service = client.post(
                    "/v1/services",
                    headers=management_headers,
                    json={
                        "name": "Local demo service",
                        "upstream_base_url": "https://demo.invalid",
                    },
                ).json()
                key = client.post(
                    f"/v1/services/{service['id']}/keys",
                    headers=management_headers,
                    json={"name": "Demo key"},
                ).json()
                gateway_response = client.post(
                    f"/v1/gateway/{service['id']}",
                    headers={"Authorization": f"Bearer {key['secret']}"},
                    json={"message": "hello"},
                )
                summary = client.get(
                    f"/v1/services/{service['id']}/usage/summary",
                    headers=management_headers,
                )
                daily = client.get(
                    f"/v1/services/{service['id']}/usage/daily",
                    headers=management_headers,
                )
            finally:
                client.app.state.http_client = original_http_client
                asyncio.run(demo_http_client.aclose())

            print(f"Service: {service['id']}")
            print(f"Created key prefix: {key['key_prefix']}")
            print(f"Gateway response: {gateway_response.json()}")
            print(f"Usage summary: {summary.json()}")
            print(f"Daily usage: {daily.json()}")


if __name__ == "__main__":
    main()
