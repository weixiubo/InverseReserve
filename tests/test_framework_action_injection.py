"""The custom BrowserGym action executes only inside its injected namespace."""

import inspect
from types import SimpleNamespace

import pytest

from inversereserve.adapters.webarena.webarena_verified_runtime_v1 import click_no_wait


@pytest.mark.parametrize("mode", ["off", "default", "highlight"])
def test_click_no_wait_uses_framework_page_and_explicit_no_wait(mode):
    page = object()
    lookups = []
    clicks = []

    def lookup(observed_page, bid, demo):
        lookups.append((observed_page, bid, demo))
        return SimpleNamespace(click=lambda **kwargs: clicks.append(kwargs))

    namespace = {"get_elem_by_bid": lookup, "page": page, "demo_mode": mode}
    exec(compile(inspect.getsource(click_no_wait), "browsergym-action", "exec"), namespace)
    namespace["click_no_wait"]("public-target")
    assert lookups == [(page, "public-target", mode != "off")]
    assert clicks == [{"timeout": 3000, "no_wait_after": True}]
