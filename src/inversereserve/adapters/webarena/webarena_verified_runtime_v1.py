"""Fresh, source-bound runtime support for WebArena-Verified transfer.

This module contains no task IDs, evaluator fields, target answers, or site
selectors used by the agent.  It provides four pieces of harness machinery:
immutable site specifications, loopback-only fresh containers, authenticated
BrowserGym setup, and credential-safe HAR sanitization.  Merely importing the
module starts no container and opens no URL.
"""

from __future__ import annotations

import json
import re
import socket
import subprocess
import time as time
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import urlopen

from inversereserve.adapters.webarena.network_evidence import SENSITIVE_HAR_HEADERS as SENSITIVE_HAR_HEADERS
from inversereserve.adapters.webarena.network_evidence import _filtered_headers as _filtered_headers
from inversereserve.adapters.webarena.network_evidence import (
    _redact_forbidden_values as _redact_forbidden_values,
)
from inversereserve.adapters.webarena.network_evidence import (
    sanitize_network_har_v1 as sanitize_network_har_v1,
)

CONTAINER_NAME = re.compile("[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
IMAGE_ID = re.compile("sha256:[0-9a-f]{64}")
DISTRIBUTION_DIGEST = re.compile("sha256:[0-9a-f]{64}")


@dataclass(frozen=True)
class SiteRuntimeSpecV1:
    site: str
    token: str
    internal_site_port: int
    public_path_prefix: str
    probe_path: str
    autologin_header: str | None
    form_login: bool = False
    shm_size_bytes: int = 64 * 1024 * 1024


SITE_RUNTIME_SPECS_V1 = {
    "reddit": SiteRuntimeSpecV1("reddit", "__REDDIT__", 80, "", "/login", "X-Postmill-Auto-Login"),
    "gitlab": SiteRuntimeSpecV1(
        "gitlab",
        "__GITLAB__",
        8023,
        "",
        "/users/sign_in",
        None,
        form_login=True,
        shm_size_bytes=2 * 1024 * 1024 * 1024,
    ),
    "shopping_admin": SiteRuntimeSpecV1(
        "shopping_admin", "__SHOPPING_ADMIN__", 80, "/admin", "/admin", "X-M2-Admin-Auto-Login"
    ),
    "shopping": SiteRuntimeSpecV1(
        "shopping", "__SHOPPING__", 80, "", "/customer/account/login", "X-M2-Customer-Auto-Login"
    ),
}
GITLAB_USERNAME_SELECTOR_V1 = '[data-testid="username-field"], #user_login, input[name="user[login]"]'
GITLAB_PASSWORD_SELECTOR_V1 = '[data-testid="password-field"], #user_password, input[name="user[password]"]'
GITLAB_SIGN_IN_SELECTOR_V1 = (
    '[data-testid="sign-in-button"], button[name="commit"], input[type="submit"][name="commit"]'
)


def click_no_wait(bid: str):
    """Click one public BrowserGym bid without awaiting navigation.

    Examples:
        click_no_wait('a51')
    """
    element = get_elem_by_bid(page, bid, demo_mode != "off")  # noqa: F821 - BrowserGym injected namespace; docs/FRAMEWORK_INJECTION.json
    element.click(timeout=3000, no_wait_after=True)


def run_command(
    arguments: list[str], *, timeout: float = 60.0, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, check=check, capture_output=True, text=True, timeout=timeout)


def site_spec_v1(site: str) -> SiteRuntimeSpecV1:
    try:
        return SITE_RUNTIME_SPECS_V1[str(site)]
    except KeyError as error:
        raise ValueError(f"unsupported WebArena-Verified site: {site}") from error


def site_origin_v1(site: str, host_port: int) -> str:
    site_spec_v1(site)
    if not 1024 <= int(host_port) <= 65535:
        raise ValueError("site host port must be unprivileged and valid")
    return f"http://127.0.0.1:{int(host_port)}"


def public_site_base_v1(site: str, host_port: int) -> str:
    spec = site_spec_v1(site)
    return site_origin_v1(site, host_port) + spec.public_path_prefix


def render_start_url_v1(template: str, *, site: str, host_port: int) -> str:
    spec = site_spec_v1(site)
    text = str(template)
    if text.count(spec.token) != 1:
        raise ValueError("start URL must contain the exact site token once")
    other_tokens = {row.token for name, row in SITE_RUNTIME_SPECS_V1.items() if name != site}
    if any((token in text for token in other_tokens)):
        raise ValueError("start URL contains a token from another site")
    rendered = text.replace(spec.token, public_site_base_v1(site, host_port))
    parsed = urlsplit(rendered)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port != int(host_port):
        raise ValueError("rendered start URL escaped the loopback site origin")
    return rendered


def validate_runtime_credentials_v1(
    site: str, *, autologin_value: str | None = None, username: str | None = None, password: str | None = None
) -> dict[str, str]:
    spec = site_spec_v1(site)
    if spec.form_login:
        if autologin_value is not None or not username or (not password):
            raise ValueError("GitLab requires harness-only username and password")
        return {"username": str(username), "password": str(password)}
    if username is not None or password is not None:
        raise ValueError("header-authenticated sites do not accept form credentials")
    if not autologin_value or ":" not in autologin_value:
        raise ValueError("site requires one harness-only autologin header value")
    left, right = autologin_value.split(":", 1)
    if not left or not right:
        raise ValueError("autologin header value is structurally incomplete")
    return {"autologin_value": str(autologin_value)}


def validate_image_record_v1(record: dict[str, Any]) -> None:
    if set(record) != {"loaded_image_tag", "loaded_image_id", "distribution_digest", "archive_sha256"}:
        raise ValueError("official image record shape changed")
    if not str(record["loaded_image_tag"]).strip():
        raise ValueError("loaded image tag is empty")
    if IMAGE_ID.fullmatch(str(record["loaded_image_id"])) is None:
        raise ValueError("loaded image ID is not immutable")
    if DISTRIBUTION_DIGEST.fullmatch(str(record["distribution_digest"])) is None:
        raise ValueError("distribution digest is not immutable")
    if re.fullmatch("[0-9a-f]{64}", str(record["archive_sha256"])) is None:
        raise ValueError("image archive hash is not immutable")


def container_run_arguments_v1(
    *, site: str, image_record: dict[str, Any], container_name: str, site_port: int, control_port: int
) -> list[str]:
    spec = site_spec_v1(site)
    validate_image_record_v1(image_record)
    if CONTAINER_NAME.fullmatch(str(container_name)) is None:
        raise ValueError("unsafe fresh-container name")
    if site_port == control_port:
        raise ValueError("site and control ports must differ")
    if spec.form_login and int(site_port) != spec.internal_site_port:
        raise ValueError(
            "GitLab requires the official 8023 host port because its entrypoint derives the internal nginx listener from the external URL"
        )
    origin = site_origin_v1(site, site_port)
    if not 1024 <= int(control_port) <= 65535:
        raise ValueError("control host port must be unprivileged and valid")
    arguments = [
        "docker",
        "run",
        "--pull=never",
        "-d",
        "--name",
        str(container_name),
        "-p",
        f"127.0.0.1:{int(site_port)}:{spec.internal_site_port}",
        "-p",
        f"127.0.0.1:{int(control_port)}:8877",
        "-e",
        f"WA_ENV_CTRL_EXTERNAL_SITE_URL={origin}",
    ]
    if spec.shm_size_bytes != 64 * 1024 * 1024:
        arguments.extend(("--shm-size", str(spec.shm_size_bytes)))
    arguments.append(str(image_record["loaded_image_tag"]))
    return arguments


def assert_port_available_v1(port: int) -> None:
    with socket.socket() as handle:
        handle.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        handle.bind(("127.0.0.1", int(port)))


def exact_container_names_v1(name: str) -> tuple[str, ...]:
    if CONTAINER_NAME.fullmatch(str(name)) is None:
        raise ValueError("unsafe container name")
    completed = run_command(
        ["docker", "ps", "-a", "--filter", f"name={name}", "--format", "{{.Names}}"], timeout=20
    )
    return tuple((row.strip() for row in completed.stdout.splitlines() if row.strip() == name))


def control_status_v1(control_port: int, *, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + float(timeout)
    last_error = "environment control did not respond"
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{int(control_port)}/status", timeout=5) as response:
                value = json.loads(response.read().decode("utf-8"))
            if value.get("success") is True:
                return value
            last_error = str(value)
        except Exception as error:
            last_error = f"{type(error).__name__}: {error}"
        time.sleep(1.0)
    raise TimeoutError(last_error)


def public_site_status_v1(site: str, host_port: int, *, timeout: float) -> int:
    """Wait until the public host mapping answers a generic non-task probe."""
    spec = site_spec_v1(site)
    deadline = time.monotonic() + float(timeout)
    last_error = "public site probe did not respond"
    url = site_origin_v1(site, host_port) + spec.probe_path
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=5) as response:
                status = int(response.status)
            if 200 <= status < 500:
                return status
            last_error = f"public site probe returned HTTP {status}"
        except HTTPError as error:
            if 200 <= int(error.code) < 500:
                return int(error.code)
            last_error = f"public site probe returned HTTP {error.code}"
        except Exception as error:
            last_error = f"{type(error).__name__}: {error}"
        time.sleep(1.0)
    raise TimeoutError(last_error)


class FreshWebArenaContainerV1(AbstractContextManager[dict[str, Any]]):
    """Start and remove one exact loopback-only official site container."""

    def __init__(
        self,
        *,
        site: str,
        image_record: dict[str, Any],
        container_name: str,
        site_port: int,
        control_port: int,
        startup_timeout: float,
    ) -> None:
        self.site = str(site)
        self.spec = site_spec_v1(site)
        validate_image_record_v1(image_record)
        self.image_record = dict(image_record)
        self.container_name = str(container_name)
        self.site_port = int(site_port)
        self.control_port = int(control_port)
        self.startup_timeout = float(startup_timeout)
        self.started = False
        self.record: dict[str, Any] = {}

    def _remove_started_container(self) -> None:
        if self.started:
            run_command(["docker", "rm", "-f", self.container_name], timeout=60, check=False)
            self.started = False

    def __enter__(self) -> dict[str, Any]:
        started_at = time.monotonic()
        if exact_container_names_v1(self.container_name):
            raise RuntimeError(f"fresh container already exists: {self.container_name}")
        assert_port_available_v1(self.site_port)
        assert_port_available_v1(self.control_port)
        inspected_image = json.loads(
            run_command(
                ["docker", "image", "inspect", self.image_record["loaded_image_tag"]], timeout=30
            ).stdout
        )
        if len(inspected_image) != 1 or inspected_image[0].get("Id") != self.image_record["loaded_image_id"]:
            raise RuntimeError("loaded official image identity changed")
        arguments = container_run_arguments_v1(
            site=self.site,
            image_record=self.image_record,
            container_name=self.container_name,
            site_port=self.site_port,
            control_port=self.control_port,
        )
        try:
            container_id = run_command(arguments, timeout=60).stdout.strip()
        except Exception:
            if exact_container_names_v1(self.container_name):
                self.started = True
                self._remove_started_container()
            raise
        self.started = True
        try:
            inspected = json.loads(run_command(["docker", "inspect", self.container_name], timeout=30).stdout)
            if len(inspected) != 1:
                raise RuntimeError("fresh container inspect was ambiguous")
            row = inspected[0]
            bindings = row["HostConfig"]["PortBindings"]
            expected_bindings = {
                f"{self.spec.internal_site_port}/tcp": [
                    {"HostIp": "127.0.0.1", "HostPort": str(self.site_port)}
                ],
                "8877/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(self.control_port)}],
            }
            if (
                row["Image"] != self.image_record["loaded_image_id"]
                or row["Mounts"] != []
                or row["HostConfig"]["Privileged"] is not False
                or (row["HostConfig"].get("DeviceRequests") not in (None, []))
                or (int(row["HostConfig"].get("ShmSize", 0)) != self.spec.shm_size_bytes)
                or (bindings != expected_bindings)
            ):
                raise RuntimeError("fresh container violated the frozen isolation policy")
            status = control_status_v1(self.control_port, timeout=self.startup_timeout)
            remaining_startup_seconds = max(1.0, self.startup_timeout - (time.monotonic() - started_at))
            public_probe_status = public_site_status_v1(
                self.site, self.site_port, timeout=remaining_startup_seconds
            )
            self.record = {
                "site": self.site,
                "container_id": container_id,
                "image_id": row["Image"],
                "distribution_digest": self.image_record["distribution_digest"],
                "mounts": row["Mounts"],
                "privileged": row["HostConfig"]["Privileged"],
                "gpu_device_requests": row["HostConfig"].get("DeviceRequests") or [],
                "shm_size_bytes": int(row["HostConfig"]["ShmSize"]),
                "port_bindings": bindings,
                "control_success": status.get("success") is True,
                "public_probe_status": public_probe_status,
                "control_services": status.get("details", {}).get("value", {}).get("services", {}),
                "site_origin": site_origin_v1(self.site, self.site_port),
                "public_site_base": public_site_base_v1(self.site, self.site_port),
            }
            return self.record
        except Exception:
            self._remove_started_container()
            raise

    def __exit__(self, *_args: Any) -> None:
        self._remove_started_container()


def make_webarena_environment_v1(
    *,
    site: str,
    start_url: str,
    goal: str,
    credentials: dict[str, str],
    har_path: Path,
    pre_observation_delay: float = 0.5,
    timeout_ms: int = 60000,
):
    """Create an open-ended BrowserGym environment with harness-only login."""
    spec = site_spec_v1(site)
    parsed = urlsplit(str(start_url))
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1":
        raise ValueError("WebArena start URL must use the loopback fresh container")
    if parsed.port is None:
        raise ValueError("WebArena start URL must expose an explicit host port")
    if spec.form_login:
        validated = validate_runtime_credentials_v1(
            site, username=credentials.get("username"), password=credentials.get("password")
        )
    else:
        validated = validate_runtime_credentials_v1(site, autologin_value=credentials.get("autologin_value"))
    from browsergym.core.action.highlevel import HighLevelActionSet
    from browsergym.core.env import BrowserEnv
    from browsergym.core.task import OpenEndedTask

    class ExactMutationTaskV1(OpenEndedTask):
        def __init__(self, seed: int, start_url: str, goal: str) -> None:
            super().__init__(seed=seed, start_url=start_url, goal=goal)
            self.viewport = {"width": 1280, "height": 720}
            self.slow_mo = 0
            self.timeout = int(timeout_ms)

        def setup(self, page):
            if spec.autologin_header is not None:
                page.context.set_extra_http_headers({spec.autologin_header: validated["autologin_value"]})
            elif spec.form_login:
                origin = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
                page.goto(f"{origin}/users/sign_in", timeout=self.timeout, wait_until="domcontentloaded")
                page.locator(GITLAB_USERNAME_SELECTOR_V1).first.fill(validated["username"])
                page.locator(GITLAB_PASSWORD_SELECTOR_V1).first.fill(validated["password"])
                page.locator(GITLAB_SIGN_IN_SELECTOR_V1).first.click()
                page.wait_for_url("**/", timeout=self.timeout)
            page.goto(self.start_url, timeout=self.timeout, wait_until="domcontentloaded")
            return (self.goal, {})

    action_set = HighLevelActionSet(
        subsets=["bid", "coord", "custom"],
        custom_actions=[click_no_wait],
        multiaction=False,
        strict=True,
        demo_mode="off",
        retry_with_force=False,
    )
    har_path = Path(har_path)
    har_path.parent.mkdir(parents=True, exist_ok=True)
    if har_path.exists():
        raise FileExistsError(f"network HAR already exists: {har_path}")
    return BrowserEnv(
        task_entrypoint=ExactMutationTaskV1,
        task_kwargs={"start_url": str(start_url), "goal": str(goal)},
        headless=True,
        action_mapping=action_set.to_python_code,
        pre_observation_delay=float(pre_observation_delay),
        pw_context_kwargs={
            "record_har_path": str(har_path),
            "record_har_content": "embed",
            "record_har_mode": "full",
        },
    )
