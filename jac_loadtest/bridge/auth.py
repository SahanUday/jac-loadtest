"""jac-scale auth: per-VU JWT login and header injection.

AuthProvider loads credentials from a CSV file or shared username/password,
authenticates each VU independently against /user/login, and returns the
Bearer token for injection into subsequent requests.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    from jac_loadtest.config import LoadTestConfig


class AuthenticationError(Exception):
    """Raised when login fails; carries a human-readable message for the user."""


@dataclass
class Credential:
    username: str
    password: str


class AuthProvider:
    def __init__(
        self,
        credentials: list[Credential],
        login_path: str = "/user/login",
    ) -> None:
        self._credentials = credentials
        self._login_path = login_path

    @classmethod
    def from_config(cls, config: LoadTestConfig) -> AuthProvider | None:
        """Return an AuthProvider if credentials are configured, else None."""
        if config.credentials_file:
            creds = _load_csv(config.credentials_file)
        elif config.username and config.password:
            creds = [Credential(config.username, config.password)]
        else:
            return None
        return cls(creds, config.login_path)

    def get_credential(self, vu_id: int) -> Credential:
        """Wrap-around assignment: VU i gets row i % len(credentials)."""
        return self._credentials[vu_id % len(self._credentials)]

    async def authenticate(
        self,
        vu_id: int,
        session: aiohttp.ClientSession,
        base_url: str,
    ) -> str:
        """POST /user/login for VU vu_id and return the JWT token string.

        identity.type is inferred: values containing '@' use 'email', else 'username'.
        Raises AuthenticationError on 4xx/5xx so callers get a clear message.
        """
        cred = self.get_credential(vu_id)
        identity_type = "email" if "@" in cred.username else "username"
        payload = {
            "identity": {"type": identity_type, "value": cred.username},
            "credential": {"type": "password", "password": cred.password},
        }
        url = base_url.rstrip("/") + self._login_path
        try:
            async with session.post(url, json=payload) as resp:
                if resp.status == 401:
                    raise AuthenticationError(
                        f"Login failed for VU {vu_id} ({identity_type}={cred.username!r}): "
                        f"401 Unauthorized — check credentials."
                    )
                if not resp.ok:
                    raise AuthenticationError(
                        f"Login failed for VU {vu_id} ({identity_type}={cred.username!r}): "
                        f"server returned {resp.status}."
                    )
                body = await resp.json()
        except aiohttp.ClientConnectorError as exc:
            raise AuthenticationError(
                f"Cannot reach login endpoint {url!r}: {exc}"
            ) from exc
        try:
            return body["data"]["token"]
        except (KeyError, TypeError) as exc:
            raise AuthenticationError(
                f"Unexpected login response shape from {url!r}: {body!r}"
            ) from exc


def _load_csv(path: str) -> list[Credential]:
    """Read credentials.csv and return a list of Credential objects.

    Skips a header row if the first column value is 'username' (case-insensitive).
    Raises ValueError if the file is empty or has no valid rows.
    """
    credentials: list[Credential] = []
    with open(path, newline="") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if len(row) < 2:
                continue
            username, password = row[0].strip(), row[1].strip()
            if i == 0 and username.lower() == "username":
                continue
            credentials.append(Credential(username=username, password=password))
    if not credentials:
        raise ValueError(f"No credentials found in {path!r}")
    return credentials
