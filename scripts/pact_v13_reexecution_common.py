"""Fail-closed helpers for complete-stage PACT-v13 re-execution."""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pact_v13_full_reexecution_template as template_runner  # noqa: E402


MINIWOB_STAGES = ("c452", "repair", "final")
WEB_STAGES = ("webarena_development", "webarena_holdout")
ACTIVATION_KEYS = {
    "candidate",
    "created_utc",
    "git_head",
    "status",
    "stage",
    "correction_protocol",
    "template",
    "parent_result",
    "parent_protocol",
    "frozen_reexecution",
    "environment_resets",
    "partial_reexecution_allowed",
    "failed_scientific_gate_opens_descendants",
    "checks",
}


def _exact_reference(
    root: Path,
    reference: object,
    *,
    expected_relative: str,
    role: str,
) -> tuple[Path, dict[str, Any]]:
    if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
        raise ValueError(f"{role} reference changed")
    if reference.get("path") != expected_relative:
        raise ValueError(f"{role} path changed")
    path = template_runner._inside(root, expected_relative)
    if not path.is_file():
        raise FileNotFoundError(path)
    actual = template_runner.sha256(path)
    if actual != reference.get("sha256"):
        raise ValueError(f"{role} artifact changed: {actual}")
    return path, template_runner.load_json(path)


def verify_activation_protocol(
    path: Path,
    expected_sha256: str,
    *,
    stage_name: str,
    root: Path = ROOT,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Verify one create-once passing-parent v13 activation."""

    if stage_name not in template_runner.EXPECTED_STAGES:
        raise ValueError(f"unknown PACT-v13 re-execution stage: {stage_name}")
    stage = template_runner.EXPECTED_STAGES[stage_name]
    expected_path = template_runner._inside(root, stage["activation_protocol"])
    if path.resolve() != expected_path:
        raise ValueError("PACT-v13 activation path changed")
    actual = template_runner.sha256(path)
    if actual != expected_sha256:
        raise ValueError(f"PACT-v13 activation protocol changed: {actual}")
    activation = template_runner.load_json(path)
    if set(activation) != ACTIVATION_KEYS:
        raise ValueError("PACT-v13 activation schema changed")
    if not (
        activation.get("candidate") == "PACT-v13-full-reexecution-activation"
        and activation.get("status")
        == "sealed_after_passing_parent_before_first_v13_reset"
        and activation.get("stage") == stage_name
        and activation.get("frozen_reexecution") == stage
        and activation.get("environment_resets") == stage["episodes"]
        and activation.get("partial_reexecution_allowed") is False
        and activation.get("failed_scientific_gate_opens_descendants") is False
        and activation.get("checks")
        == {
            "passing_parent_is_exact": True,
            "parent_protocol_is_exact": True,
            "complete_population_is_required": True,
            "zero_reset_inheritance_is_forbidden": True,
        }
        and re.fullmatch(r"[0-9a-f]{40}", str(activation.get("git_head")))
        and re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z",
            str(activation.get("created_utc")),
        )
    ):
        raise ValueError("PACT-v13 activation semantics changed")

    correction_path, _correction = _exact_reference(
        root,
        activation["correction_protocol"],
        expected_relative=(
            "validation/pact_v13_complete_public_commit_protocol.json"
        ),
        role="PACT-v13 correction protocol",
    )
    template_runner.verify_correction_protocol(
        correction_path,
        str(activation["correction_protocol"]["sha256"]),
        root=root,
    )
    template_path, template = _exact_reference(
        root,
        activation["template"],
        expected_relative=(
            "validation/pact_v13_full_reexecution_template_protocol.json"
        ),
        role="PACT-v13 full-rerun template",
    )
    template_runner.verify_template(
        template_path,
        str(activation["template"]["sha256"]),
        root=root,
    )
    if template["stages"][stage_name] != stage:
        raise ValueError("PACT-v13 activation stage differs from its template")
    _parent_path, parent = _exact_reference(
        root,
        activation["parent_result"],
        expected_relative=stage["parent_result"],
        role="PACT-v13 re-execution parent result",
    )
    _protocol_path, parent_protocol = _exact_reference(
        root,
        activation["parent_protocol"],
        expected_relative=stage["parent_protocol"],
        role="PACT-v13 re-execution parent protocol",
    )
    if not (
        parent.get("passed") is True
        and parent.get("protocol") == stage["parent_protocol"]
        and parent.get("protocol_sha256")
        == activation["parent_protocol"]["sha256"]
    ):
        raise ValueError("PACT-v13 activation lost its exact passing parent")
    return activation, parent_protocol, actual


def mapped_miniwob_manifest(
    stage_name: str,
    parent_protocol: dict[str, Any],
) -> list[dict[str, Any]]:
    """Relabel the exact parent population without changing order or cells."""

    import c452_pact_v9_fresh_visible_development as c452
    from rcrps import matched_confirmation_v10 as matched_v10
    from rcrps import repair_holdout_v10 as repair_v10

    if stage_name == "c452":
        if c452.METHOD != "full_pact_v9":
            raise RuntimeError("C452 predecessor namespace was already modified")
        parent = c452.manifest(parent_protocol)
    elif stage_name == "repair":
        parent = repair_v10.episode_manifest(parent_protocol)
    elif stage_name == "final":
        parent = matched_v10.episode_manifest(parent_protocol)
    else:
        raise ValueError(f"stage is not a MiniWoB re-execution: {stage_name}")
    mapping = template_runner.EXPECTED_STAGES[stage_name]["method_mapping"]
    output = []
    for source in parent:
        row = copy.deepcopy(source)
        old_method = str(row["method"])
        if old_method not in mapping:
            raise ValueError(f"unregistered PACT-v13 method mapping: {old_method}")
        old_suffix = f"__{old_method}"
        if not str(row["episode_id"]).endswith(old_suffix):
            raise ValueError("parent episode identifier does not end in its method")
        new_method = str(mapping[old_method])
        row["method"] = new_method
        row["episode_id"] = f"{str(row['episode_id'])[:-len(old_suffix)]}__{new_method}"
        output.append(row)
    expected = int(template_runner.EXPECTED_STAGES[stage_name]["episodes"])
    if len(output) != expected or len({row["episode_id"] for row in output}) != expected:
        raise ValueError("PACT-v13 mapped manifest is incomplete or duplicated")
    return output


def normalize_rows_for_parent(
    rows: Iterable[dict[str, Any]],
    *,
    method_mapping: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Copy rows and undo only preregistered method-version labels."""

    reverse = {str(new): str(old) for old, new in method_mapping.items()}
    if len(reverse) != len(method_mapping):
        raise ValueError("PACT-v13 method mapping is not one-to-one")
    output = []
    for source in rows:
        row = copy.deepcopy(source)
        episode = row.get("episode")
        method_input = row.get("method_input")
        if not isinstance(episode, dict) or not isinstance(method_input, dict):
            raise ValueError("PACT-v13 row omits episode or method input")
        new_method = str(episode.get("method"))
        if new_method not in reverse:
            raise ValueError(f"unexpected PACT-v13 row method: {new_method}")
        if method_input.get("controller_arm") != new_method:
            raise ValueError("PACT-v13 controller arm differs from its manifest")
        suffix = f"__{new_method}"
        episode_id = str(episode.get("episode_id"))
        if not episode_id.endswith(suffix):
            raise ValueError("PACT-v13 episode identifier differs from its method")
        old_method = reverse[new_method]
        episode["method"] = old_method
        episode["episode_id"] = f"{episode_id[:-len(suffix)]}__{old_method}"
        method_input["controller_arm"] = old_method
        output.append(row)
    return output


def remap_exact_labels(value: Any, mapping: Mapping[str, str]) -> Any:
    """Recursively replace exact method labels and episode-ID suffixes."""

    def mapped_string(text: str) -> str:
        if text in mapping:
            return str(mapping[text])
        for old, new in mapping.items():
            suffix = f"__{old}"
            if text.endswith(suffix):
                return f"{text[:-len(suffix)]}__{new}"
        return text

    if isinstance(value, dict):
        output = {}
        for key, item in value.items():
            mapped_key = mapped_string(key) if isinstance(key, str) else key
            if mapped_key in output:
                raise ValueError("method-label remapping creates a dictionary collision")
            output[mapped_key] = remap_exact_labels(item, mapping)
        return output
    if isinstance(value, list):
        return [remap_exact_labels(item, mapping) for item in value]
    if isinstance(value, tuple):
        return tuple(remap_exact_labels(item, mapping) for item in value)
    if isinstance(value, str):
        return mapped_string(value)
    return value


def v13_population_audit(
    rows: Iterable[dict[str, Any]],
    manifest: Iterable[dict[str, Any]],
    *,
    method_mapping: Mapping[str, str],
) -> dict[str, Any]:
    """Audit exact labels, v12 no-effect checks, and v13 commit freshness."""

    rows = tuple(rows)
    manifest = tuple(manifest)
    expected = {row["episode_id"]: row for row in manifest}
    protected_methods = {
        str(method)
        for method in method_mapping.values()
        if not str(method).startswith("raw_open_loop_")
    }
    observed_ids = [str(row.get("episode", {}).get("episode_id")) for row in rows]
    exact_rows = bool(
        len(rows) == len(manifest)
        and len(expected) == len(manifest)
        and len(set(observed_ids)) == len(rows)
        and set(observed_ids) == set(expected)
        and all(
            row.get("episode")
            == expected.get(str(row.get("episode", {}).get("episode_id")))
            for row in rows
        )
    )
    protected = [
        row
        for row in rows
        if row.get("episode", {}).get("method") in protected_methods
    ]
    full_rows = [
        row
        for row in rows
        if str(row.get("episode", {}).get("method", "")).startswith(
            "full_pact_v13"
        )
    ]

    def event_counts(row: dict[str, Any]) -> tuple[int, int, int]:
        events = row.get("runtime_events", [])
        checks = sum(
            event.get("type") == "complete_public_observation_check_v12"
            for event in events
        )
        certificates = sum(
            event.get("type") == "complete_public_no_effect_certificate_v12"
            and event.get("passed") is True
            and event.get("inverse_skipped") is True
            for event in events
        )
        restoration_skips = sum(
            event.get("type") == "restoration"
            and event.get("inverse_skipped") is True
            and event.get("certificate_scope") == "complete_public_snapshot"
            for event in events
        )
        return checks, certificates, restoration_skips

    metric_rows = []
    for row in protected:
        metrics = row.get("metrics", {})
        event_checks, event_skips, restoration_skips = event_counts(row)
        metric_checks = metrics.get("complete_public_observation_checks_v12")
        metric_skips = metrics.get("complete_public_inverse_skips_v12")
        metric_rows.append(
            {
                "metric_checks": metric_checks,
                "metric_skips": metric_skips,
                "event_checks": event_checks,
                "event_skips": event_skips,
                "restoration_skips": restoration_skips,
                "exact": (
                    isinstance(metric_checks, int)
                    and metric_checks >= 0
                    and isinstance(metric_skips, int)
                    and metric_skips >= 0
                    and metric_checks == event_checks
                    and metric_skips == event_skips == restoration_skips
                    and metric_skips <= metric_checks
                ),
            }
        )
    accounting = bool(protected) and all(row["exact"] for row in metric_rows)

    commit_rows = []
    for row in full_rows:
        events = row.get("runtime_events", [])
        metrics = row.get("metrics", {})
        event_checks = sum(
            event.get("type") == "complete_public_commit_observation_check_v13"
            for event in events
        )
        event_passes = sum(
            event.get("type") == "complete_public_commit_observation_check_v13"
            and event.get("passed") is True
            for event in events
        )
        event_rejections = sum(
            event.get("type") == "complete_public_commit_observation_check_v13"
            and event.get("passed") is False
            for event in events
        )
        metric_checks = metrics.get("complete_public_commit_checks_v13")
        metric_passes = metrics.get("complete_public_commit_passes_v13")
        metric_rejections = metrics.get(
            "complete_public_commit_rejections_v13"
        )
        commit_rows.append(
            {
                "metric_checks": metric_checks,
                "metric_passes": metric_passes,
                "metric_rejections": metric_rejections,
                "exact": (
                    isinstance(metric_checks, int)
                    and metric_checks >= 0
                    and isinstance(metric_passes, int)
                    and metric_passes >= 0
                    and isinstance(metric_rejections, int)
                    and metric_rejections >= 0
                    and metric_checks == event_checks
                    and metric_passes == event_passes
                    and metric_rejections == event_rejections
                    and metric_checks == metric_passes + metric_rejections
                ),
            }
        )
    commit_accounting = bool(full_rows) and all(
        row["exact"] for row in commit_rows
    )
    commit_checks = (
        sum(int(row["metric_checks"]) for row in commit_rows)
        if commit_accounting
        else None
    )
    checks = {
        "exact_complete_v13_manifest": exact_rows,
        "controller_arm_matches_v13_manifest": all(
            row.get("method_input", {}).get("controller_arm")
            == row.get("episode", {}).get("method")
            for row in rows
        ),
        "all_runtime_protected_rows_report_complete_observation_guard": bool(
            protected
        )
        and all(
            isinstance(row["metric_checks"], int)
            and isinstance(row["metric_skips"], int)
            for row in metric_rows
        ),
        "complete_observation_metrics_match_runtime_events": accounting,
        "all_full_rows_report_complete_commit_freshness": bool(full_rows)
        and all(
            isinstance(row["metric_checks"], int)
            and isinstance(row["metric_passes"], int)
            and isinstance(row["metric_rejections"], int)
            for row in commit_rows
        ),
        "complete_commit_metrics_match_runtime_events": commit_accounting,
        "complete_commit_guard_is_exercised": (
            isinstance(commit_checks, int) and commit_checks > 0
        ),
    }
    return {
        "protected_rows": len(protected),
        "complete_public_observation_checks": (
            sum(int(row["metric_checks"]) for row in metric_rows)
            if accounting
            else None
        ),
        "complete_public_inverse_skips": (
            sum(int(row["metric_skips"]) for row in metric_rows)
            if accounting
            else None
        ),
        "complete_public_commit_checks": commit_checks,
        "complete_public_commit_passes": (
            sum(int(row["metric_passes"]) for row in commit_rows)
            if commit_accounting
            else None
        ),
        "complete_public_commit_rejections": (
            sum(int(row["metric_rejections"]) for row in commit_rows)
            if commit_accounting
            else None
        ),
        "checks": checks,
        "passed": all(checks.values()),
    }
