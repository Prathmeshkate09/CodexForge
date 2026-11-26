from __future__ import annotations

import base64
import fnmatch
import time
from typing import Any, cast

import httpx
import jwt

from app.core.config import Settings
from app.core.errors import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
)

REDACTED_PATTERNS: tuple[str, ...] = (
    ".env*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.cert",
    "id_rsa*",
    "id_ed25519*",
    "id_ecdsa*",
    "service-account*.json",
    "*credential*",
    "*secret*",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.pdf",
    "*.zip",
    "*.tar",
    "*.gz",
    "*.tgz",
    "*.7z",
    "*.exe",
    "*.dll",
    "*.so",
    "*.dylib",
    "*.bin",
    "*.wasm",
    "*.pyc",
    "*.pyo",
    "*.class",
    "*.jar",
    "*.sqlite",
    "*.db",
)

REDACTED_DIRECTORY_PARTS: tuple[str, ...] = (
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "dist",
    "build",
    "target",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
)


def is_path_redacted(path: str) -> bool:
    """Returns True if path contains sensitive secrets, binary files, or dependency cache."""
    normalized = path.replace("\\", "/").strip("/").lower()
    parts = normalized.split("/")

    for part in parts:
        if part in REDACTED_DIRECTORY_PARTS:
            return True

    filename = parts[-1]
    for pattern in REDACTED_PATTERNS:
        if fnmatch.fnmatch(filename, pattern):
            return True

    return False


class GitHubClient:
    """Read-only GitHub App client for repository evidence collection and commit pinning."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = http_client
        self._token_cache: dict[int, tuple[str, float]] = {}

    def _get_app_jwt(self) -> str:
        if self._settings.github_app_id is None:
            raise AuthorizationError("GitHub App ID is not configured.")
        private_key = self._settings.get_github_private_key_pem()
        if not private_key:
            raise AuthorizationError("GitHub App private key is not configured.")

        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + 600,
            "iss": str(self._settings.github_app_id),
        }
        return jwt.encode(payload, private_key, algorithm="RS256")

    async def get_installation_access_token(self, installation_id: int) -> str:
        now = time.time()
        cached = self._token_cache.get(installation_id)
        if cached is not None:
            token, expires_at = cached
            if expires_at - now > 120:
                return token

        app_jwt = self._get_app_jwt()
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"

        client = self._client or httpx.AsyncClient(timeout=15.0)
        try:
            resp = await client.post(url, headers=headers)
            if resp.status_code == 404:
                raise NotFoundError("GitHub App installation was not found or access was revoked.")
            if resp.status_code not in (200, 201):
                raise ServiceUnavailableError(
                    f"GitHub App token exchange failed with status {resp.status_code}."
                )
            data = resp.json()
            minted_token: str = data["token"]
            expires_at_epoch = now + 3500.0
            self._token_cache[installation_id] = (minted_token, expires_at_epoch)
            return minted_token
        finally:
            if self._client is None:
                await client.aclose()

    async def _authed_request(
        self,
        method: str,
        path: str,
        installation_id: int,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        token = await self.get_installation_access_token(installation_id)
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        url = f"https://api.github.com{path}"

        client = self._client or httpx.AsyncClient(timeout=20.0)
        try:
            resp = await client.request(method, url, headers=headers, params=params, json=json_body)
            return resp
        finally:
            if self._client is None:
                await client.aclose()

    async def get_default_branch_commit(
        self,
        installation_id: int,
        owner: str,
        repo: str,
    ) -> tuple[str, str]:
        """Returns (default_branch, commit_sha)."""
        resp = await self._authed_request("GET", f"/repos/{owner}/{repo}", installation_id)
        if resp.status_code == 404:
            raise NotFoundError(f"Repository {owner}/{repo} not found on GitHub.")
        if resp.status_code != 200:
            raise ServiceUnavailableError("Failed to fetch repository information from GitHub.")

        repo_data = resp.json()
        default_branch: str = repo_data.get("default_branch", "main")

        commit_resp = await self._authed_request(
            "GET", f"/repos/{owner}/{repo}/commits/{default_branch}", installation_id
        )
        if commit_resp.status_code != 200:
            raise ServiceUnavailableError(
                f"Failed to fetch HEAD commit for branch {default_branch}."
            )

        commit_data = commit_resp.json()
        commit_sha: str = commit_data["sha"]
        return default_branch, commit_sha

    async def get_repository_tree(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        commit_sha: str,
    ) -> list[dict[str, Any]]:
        """Returns safe, un-redacted repository tree entries."""
        resp = await self._authed_request(
            "GET",
            f"/repos/{owner}/{repo}/git/trees/{commit_sha}",
            installation_id,
            params={"recursive": "1"},
        )
        if resp.status_code != 200:
            raise ServiceUnavailableError("Failed to fetch repository git tree from GitHub.")

        tree = resp.json().get("tree", [])
        safe_tree: list[dict[str, Any]] = []
        for item in tree:
            item_path = item.get("path", "")
            if not is_path_redacted(item_path):
                safe_tree.append(item)
        return safe_tree

    async def get_file_content(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        path: str,
        commit_sha: str,
        max_lines: int = 400,
    ) -> str:
        """Fetches decoded, redacted, bounded file content."""
        if is_path_redacted(path):
            raise ConflictError(
                f"Access to file path '{path}' is blocked by security redaction policy."
            )

        resp = await self._authed_request(
            "GET",
            f"/repos/{owner}/{repo}/contents/{path}",
            installation_id,
            params={"ref": commit_sha},
        )
        if resp.status_code == 404:
            raise NotFoundError(f"File '{path}' not found at commit {commit_sha[:8]}.")
        if resp.status_code != 200:
            raise ServiceUnavailableError(f"Failed to fetch file content for '{path}'.")

        data = resp.json()
        encoding = data.get("encoding")
        content_raw = data.get("content", "")
        if encoding == "base64":
            try:
                decoded = base64.b64decode(content_raw).decode("utf-8", errors="replace")
            except Exception as exc:
                raise ConflictError("Unable to decode file content as UTF-8.") from exc
        else:
            decoded = content_raw

        lines = decoded.splitlines()
        if len(lines) > max_lines:
            truncated = "\n".join(lines[:max_lines])
            return f"{truncated}\n... [TRUNCATED at {max_lines} lines by CodexForge policy]"
        return decoded

    async def create_branch(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        branch_name: str,
        commit_sha: str,
    ) -> str:
        """Creates a git ref for a new branch pointing to commit_sha."""
        resp = await self._authed_request(
            "POST",
            f"/repos/{owner}/{repo}/git/refs",
            installation_id,
            json_body={"ref": f"refs/heads/{branch_name}", "sha": commit_sha},
        )
        if resp.status_code == 422:
            return branch_name
        if resp.status_code not in (200, 201):
            raise ServiceUnavailableError(f"Failed to create branch '{branch_name}' on GitHub.")
        return branch_name

    async def create_or_update_file(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        path: str,
        content: str,
        commit_message: str,
        branch: str,
    ) -> dict[str, Any]:
        """Creates or updates a single file in the branch."""
        existing_sha = None
        get_resp = await self._authed_request(
            "GET",
            f"/repos/{owner}/{repo}/contents/{path}",
            installation_id,
            params={"ref": branch},
        )
        if get_resp.status_code == 200:
            existing_sha = get_resp.json().get("sha")

        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        payload: dict[str, Any] = {
            "message": commit_message,
            "content": encoded,
            "branch": branch,
        }
        if existing_sha:
            payload["sha"] = existing_sha

        put_resp = await self._authed_request(
            "PUT",
            f"/repos/{owner}/{repo}/contents/{path}",
            installation_id,
            json_body=payload,
        )
        if put_resp.status_code not in (200, 201):
            raise ServiceUnavailableError(f"Failed to commit file '{path}' to branch '{branch}'.")
        return cast(dict[str, Any], put_resp.json())

    async def create_pull_request(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main",
        draft: bool = True,
    ) -> dict[str, Any]:
        """Creates a draft pull request via GitHub App permissions."""
        payload = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch,
            "draft": draft,
        }
        resp = await self._authed_request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            installation_id,
            json_body=payload,
        )
        if resp.status_code not in (200, 201):
            raise ServiceUnavailableError("Failed to create GitHub pull request.")
        data = resp.json()
        return {
            "number": data["number"],
            "url": data["html_url"],
            "branch_name": head_branch,
        }
