"""Exact episode-population checks; duplicate IDs and altered metadata fail closed."""

from __future__ import annotations

from typing import Any


def matches_registered_grid(rows: tuple[dict[str, Any], ...], manifest: list[dict[str, Any]]) -> bool:
    expected = {row["episode_id"]: row for row in manifest}
    observed_ids = [str(row.get("episode", {}).get("episode_id")) for row in rows]
    manifest_exact = (
        len(rows) == len(manifest)
        and len(set(observed_ids)) == len(rows)
        and (set(observed_ids) == set(expected))
        and all(
            (
                row.get("episode") == expected.get(str(row.get("episode", {}).get("episode_id")))
                for row in rows
            )
        )
    )
    return manifest_exact


def matches_claim_bound_grid(rows: tuple[dict[str, Any], ...], manifest: list[dict[str, Any]]) -> bool:
    expected = {row["episode_id"]: row for row in manifest}
    observed_ids = [str(row.get("episode", {}).get("episode_id")) for row in rows]
    manifest_exact = (
        len(rows) == len(manifest)
        and len(set(observed_ids)) == len(observed_ids)
        and (set(observed_ids) == set(expected))
        and all((row["episode"] == expected[row["episode"]["episode_id"]] for row in rows))
    )
    return manifest_exact


def matches_registered_grid_variant_3(
    rows: tuple[dict[str, Any], ...], manifest: list[dict[str, Any]]
) -> bool:
    expected = {row["episode_id"]: row for row in manifest}
    observed_ids = [str(row.get("episode", {}).get("episode_id")) for row in rows]
    manifest_exact = bool(
        len(rows) == len(manifest)
        and len(set(observed_ids)) == len(rows)
        and (set(observed_ids) == set(expected))
        and all(
            (
                row.get("episode") == expected.get(str(row.get("episode", {}).get("episode_id")))
                for row in rows
            )
        )
    )
    return manifest_exact
