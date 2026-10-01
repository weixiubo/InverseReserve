from __future__ import annotations

import inspect
import json
from urllib.error import HTTPError
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import rcrps.webarena_verified_runtime_v1 as runtime  # noqa: E402
from rcrps.webarena_verified_runtime_v1 import (  # noqa: E402
    FreshWebArenaContainerV1,
    SITE_RUNTIME_SPECS_V1,
    container_run_arguments_v1,
    public_site_base_v1,
    public_site_status_v1,
    render_start_url_v1,
    sanitize_network_har_v1,
    site_origin_v1,
    site_spec_v1,
    validate_image_record_v1,
    validate_runtime_credentials_v1,
)


def image_record() -> dict[str, str]:
    return {
        "loaded_image_tag": "official:aaai27-pinned",
        "loaded_image_id": "sha256:" + "1" * 64,
        "distribution_digest": "sha256:" + "2" * 64,
        "archive_sha256": "3" * 64,
    }


def test_custom_click_action_has_browsergym_parseable_documentation_shape() -> None:
    documentation = inspect.getdoc(runtime.click_no_wait)
    assert documentation is not None
    assert "\n\nExamples:\n    click_no_wait('a51')" in documentation


def test_gitlab_login_selectors_cover_current_and_legacy_official_dom() -> None:
    assert '[data-testid="username-field"]' in runtime.GITLAB_USERNAME_SELECTOR_V1
    assert "#user_login" in runtime.GITLAB_USERNAME_SELECTOR_V1
    assert "#user_password" in runtime.GITLAB_PASSWORD_SELECTOR_V1
    assert 'button[name="commit"]' in runtime.GITLAB_SIGN_IN_SELECTOR_V1


def test_environment_navigation_waits_for_dom_not_background_network_idle() -> None:
    source = inspect.getsource(runtime.make_webarena_environment_v1)
    assert source.count('wait_until="domcontentloaded"') == 2
    assert 'wait_until="networkidle"' not in source


def test_public_site_probe_waits_for_host_mapping_and_accepts_auth_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def eventually_ready(url, *, timeout):
        calls.append((url, timeout))
        if len(calls) == 1:
            raise ConnectionRefusedError("host mapping not ready")
        return Response()

    monkeypatch.setattr(runtime, "urlopen", eventually_ready)
    monkeypatch.setattr(runtime.time, "sleep", lambda _seconds: None)
    assert public_site_status_v1("shopping_admin", 24780, timeout=10) == 200
    assert calls[0][0] == "http://127.0.0.1:24780/admin"

    error = HTTPError(calls[0][0], 403, "auth required", {}, None)
    monkeypatch.setattr(runtime, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(error))
    assert public_site_status_v1("shopping_admin", 24780, timeout=10) == 403


def test_four_site_runtime_specs_and_public_bases_are_exact() -> None:
    assert set(SITE_RUNTIME_SPECS_V1) == {
        "reddit",
        "gitlab",
        "shopping_admin",
        "shopping",
    }
    assert site_origin_v1("reddit", 20999) == "http://127.0.0.1:20999"
    assert public_site_base_v1("shopping_admin", 22780) == (
        "http://127.0.0.1:22780/admin"
    )
    assert site_spec_v1("gitlab").internal_site_port == 8023
    assert site_spec_v1("gitlab").form_login is True
    with pytest.raises(ValueError, match="unsupported"):
        site_spec_v1("wikipedia")


@pytest.mark.parametrize(
    ("site", "template", "port", "expected"),
    [
        ("reddit", "__REDDIT__", 20999, "http://127.0.0.1:20999"),
        (
            "gitlab",
            "__GITLAB__/profile",
            22023,
            "http://127.0.0.1:22023/profile",
        ),
        (
            "shopping_admin",
            "__SHOPPING_ADMIN__",
            22780,
            "http://127.0.0.1:22780/admin",
        ),
        (
            "shopping",
            "__SHOPPING__/sales/order/history/",
            22770,
            "http://127.0.0.1:22770/sales/order/history/",
        ),
    ],
)
def test_start_url_rendering_is_loopback_and_site_exact(
    site: str, template: str, port: int, expected: str
) -> None:
    assert render_start_url_v1(template, site=site, host_port=port) == expected


def test_start_url_rejects_missing_duplicate_or_cross_site_tokens() -> None:
    with pytest.raises(ValueError, match="exact site token once"):
        render_start_url_v1("https://example.test", site="reddit", host_port=20999)
    with pytest.raises(ValueError, match="exact site token once"):
        render_start_url_v1(
            "__REDDIT__/__REDDIT__", site="reddit", host_port=20999
        )
    with pytest.raises(ValueError, match="another site"):
        render_start_url_v1(
            "__REDDIT__/__GITLAB__", site="reddit", host_port=20999
        )


def test_harness_credentials_are_site_typed_and_never_defaulted() -> None:
    assert validate_runtime_credentials_v1(
        "reddit", autologin_value="user:secret"
    ) == {"autologin_value": "user:secret"}
    assert validate_runtime_credentials_v1(
        "gitlab", username="user", password="secret"
    ) == {"username": "user", "password": "secret"}
    with pytest.raises(ValueError):
        validate_runtime_credentials_v1("reddit", username="user", password="secret")
    with pytest.raises(ValueError):
        validate_runtime_credentials_v1("gitlab", autologin_value="user:secret")
    with pytest.raises(ValueError):
        validate_runtime_credentials_v1("shopping", autologin_value="")


def test_container_arguments_pin_image_and_isolate_ports_without_mount_or_gpu() -> None:
    record = image_record()
    validate_image_record_v1(record)
    arguments = container_run_arguments_v1(
        site="shopping_admin",
        image_record=record,
        container_name="rps-wa-dev-488",
        site_port=22780,
        control_port=22781,
    )
    assert arguments[:4] == ["docker", "run", "--pull=never", "-d"]
    assert "127.0.0.1:22780:80" in arguments
    assert "127.0.0.1:22781:8877" in arguments
    assert "WA_ENV_CTRL_EXTERNAL_SITE_URL=http://127.0.0.1:22780" in arguments
    assert arguments[-1] == record["loaded_image_tag"]
    assert "--privileged" not in arguments
    assert "--gpus" not in arguments
    assert "-v" not in arguments

    gitlab = container_run_arguments_v1(
        site="gitlab",
        image_record=record,
        container_name="rps-wa-dev-449",
        site_port=8023,
        control_port=22024,
    )
    assert "127.0.0.1:8023:8023" in gitlab
    assert "WA_ENV_CTRL_EXTERNAL_SITE_URL=http://127.0.0.1:8023" in gitlab
    assert gitlab[gitlab.index("--shm-size") + 1] == str(2 * 1024**3)
    with pytest.raises(ValueError, match="official 8023 host port"):
        container_run_arguments_v1(
            site="gitlab",
            image_record=record,
            container_name="rps-wa-wrong-gitlab-port",
            site_port=22023,
            control_port=22024,
        )


def test_image_record_and_container_name_fail_closed() -> None:
    weakened = image_record()
    weakened["loaded_image_id"] = "latest"
    with pytest.raises(ValueError, match="immutable"):
        validate_image_record_v1(weakened)
    with pytest.raises(ValueError, match="unsafe"):
        container_run_arguments_v1(
            site="reddit",
            image_record=image_record(),
            container_name="bad name; rm",
            site_port=20999,
            control_port=20998,
        )


def test_fresh_container_teardown_removes_only_the_exact_started_name(
    monkeypatch,
) -> None:
    calls = []

    def fake_run(arguments, **kwargs):
        calls.append((arguments, kwargs))
        return None

    monkeypatch.setattr(runtime, "run_command", fake_run)
    container = FreshWebArenaContainerV1(
        site="reddit",
        image_record=image_record(),
        container_name="rps-wa-dev-399",
        site_port=20999,
        control_port=20998,
        startup_timeout=90,
    )
    container.started = True
    container.__exit__()
    assert calls == [
        (
            ["docker", "rm", "-f", "rps-wa-dev-399"],
            {"timeout": 60, "check": False},
        )
    ]
    assert container.started is False


def test_har_sanitization_removes_auth_and_preserves_task_payload(
    tmp_path: Path,
) -> None:
    credential = "user:secret"
    password = "secret"
    target = "This is the exact task value"
    path = tmp_path / "network.har"
    path.write_text(
        json.dumps(
            {
                "log": {
                    "version": "1.2",
                    "entries": [
                        {
                            "request": {
                                "url": "http://127.0.0.1/login",
                                "headers": [
                                    {
                                        "name": "X-Postmill-Auto-Login",
                                        "value": credential,
                                    },
                                    {"name": "Content-Type", "value": "text/plain"},
                                ],
                                "cookies": [{"name": "session", "value": "abc"}],
                                "postData": {
                                    "mimeType": "application/x-www-form-urlencoded",
                                    "text": f"password={password}",
                                },
                            },
                            "response": {
                                "headers": [
                                    {"name": "Set-Cookie", "value": "session=abc"}
                                ],
                                "cookies": [{"name": "session", "value": "abc"}],
                                "content": {"text": f"logged in with {credential}"},
                            },
                        },
                        {
                            "request": {
                                "url": "http://127.0.0.1/save",
                                "headers": [
                                    {"name": "Content-Type", "value": "text/plain"}
                                ],
                                "cookies": [],
                                "postData": {"text": target},
                            },
                            "response": {"headers": [], "cookies": []},
                        },
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    audit = sanitize_network_har_v1(
        path,
        forbidden_values=(credential, password),
    )
    serialized = path.read_text(encoding="utf-8")
    result = json.loads(serialized)
    assert credential not in serialized
    assert password not in serialized
    assert target in serialized
    assert audit == {
        "entries": 2,
        "removed_sensitive_headers": 2,
        "removed_cookie_records": 2,
        "redacted_credential_strings": 2,
        "credential_material_remaining": False,
        "noncredential_post_data_preserved": True,
    }
    assert result["log"]["entries"][0]["request"]["headers"] == [
        {"name": "Content-Type", "value": "text/plain"}
    ]
