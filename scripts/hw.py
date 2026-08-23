#!/usr/bin/env python3
"""Fast, session-scoped schematic and custom-footprint validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal as signal_module
import subprocess
import sys
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMATIC = REPO_ROOT / "c6remote-kicad" / "c6remote.kicad_sch"
PCB = REPO_ROOT / "c6remote-kicad" / "c6remote.kicad_pcb"
FOOTPRINT_LIBRARY = REPO_ROOT / "kicad lib" / "Library.pretty"
CACHE_ROOT = REPO_ROOT / ".cache" / "hw"
DEFAULT_KICAD_CLI = Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
REQUIRED_SCHEMA = (1, 4)
SESSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
RECOVERY_COMMAND = (
    'python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer/scripts/'
    'install-skill-from-github.py" --repo aklofas/kicad-happy --ref v2.2.0 '
    "--path skills/kicad"
)

COMPONENT_FIELDS = (
    "value",
    "footprint",
    "mpn",
    "manufacturer",
    "datasheet",
    "dnp",
    "bom_state",
)
BOM_FIELDS = (
    "value",
    "footprint",
    "mpn",
    "manufacturer",
    "datasheet",
    "description",
    "digikey",
    "mouser",
    "adafruit",
    "lcsc",
    "dnp",
    "type",
)
FINDING_FIELDS = (
    "detector",
    "rule_id",
    "severity",
    "confidence",
    "evidence_source",
    "summary",
    "recommendation",
    "description",
    "category",
    "components",
    "nets",
    "pins",
    "report_context",
    "extra",
)


class ConfigError(RuntimeError):
    """Tooling or configuration prevents a trustworthy result."""

    def __init__(self, message: str, *, diagnostic: dict[str, Any] | None = None):
        super().__init__(message)
        self.diagnostic = diagnostic


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read valid JSON from {path}: {exc}") from exc


def validate_session(session: str) -> str:
    if session in {".", ".."} or not SESSION_PATTERN.fullmatch(session or ""):
        raise ConfigError(
            "invalid session: use 1 to 64 letters, digits, dots, underscores, or hyphens; "
            "first character must be alphanumeric"
        )
    return session


def session_path(cache_root: Path, session: str) -> Path:
    return Path(cache_root) / validate_session(session)


def create_session_directory(directory: Path, session: str) -> None:
    try:
        directory.mkdir(parents=True)
    except FileExistsError as exc:
        raise ConfigError(
            f"session already exists: {directory}; run clean {session} before reuse"
        ) from exc


def resolve_analyzer_root() -> Path:
    override = os.environ.get("KICAD_HAPPY_DIR")
    if override:
        return Path(override).expanduser()
    codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    return codex_home / "skills" / "kicad"


def kicad_cli_path() -> Path:
    return Path(os.environ.get("KICAD_CLI", str(DEFAULT_KICAD_CLI))).expanduser()


def recovery_message(reason: str) -> str:
    return (
        f"{reason}. Move or remove the existing KiCad skill destination before reinstalling, "
        f"then run:\n{RECOVERY_COMMAND}"
    )


def run_command(
    args: Iterable[os.PathLike[str] | str],
    *,
    cwd: Path | None = None,
    expected_outputs: Iterable[Path] = (),
) -> dict[str, Any]:
    command = [str(arg) for arg in args]
    expected = [str(Path(path)) for path in expected_outputs]
    result: dict[str, Any] = {
        "args": command,
        "cwd": str(cwd) if cwd else None,
        "returncode": None,
        "signal": None,
        "stdout": "",
        "stderr": "",
        "expected_outputs": expected,
        "missing_outputs": [],
        "unexpected_outputs": [],
    }
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        result["returncode"] = completed.returncode
        result["stdout"] = completed.stdout
        result["stderr"] = completed.stderr
        if completed.returncode < 0:
            try:
                result["signal"] = signal_module.Signals(-completed.returncode).name
            except ValueError:
                result["signal"] = str(-completed.returncode)
    except OSError as exc:
        result["exception"] = f"{type(exc).__name__}: {exc}"
        result["stderr"] = str(exc)
    result["missing_outputs"] = [path for path in expected if not Path(path).exists()]
    return result


def _schema_version(schema: dict[str, Any]) -> str | None:
    direct = schema.get("schema_version")
    if isinstance(direct, str):
        return direct
    field = schema.get("properties", {}).get("schema_version", {})
    if isinstance(field, dict):
        if isinstance(field.get("const"), str):
            return field["const"]
        enum = field.get("enum")
        if isinstance(enum, list) and enum and isinstance(enum[0], str):
            return enum[0]
    return None


def _version_tuple(value: str | None) -> tuple[int, int, int] | None:
    if not value:
        return None
    match = re.fullmatch(r"(\d+)\.(\d+)(?:\.(\d+))?(?:[-+].*)?", value)
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())  # type: ignore[return-value]


def probe_analyzer(root: Path) -> dict[str, Any]:
    script = Path(root) / "scripts" / "analyze_schematic.py"
    if not script.is_file():
        raise ConfigError(recovery_message(f"KiCad analyzer missing at {script}"))
    command = run_command([sys.executable, script, "--schema"])
    if command["returncode"] != 0:
        detail = command["stderr"].strip() or command["stdout"].strip() or "schema probe failed"
        raise ConfigError(
            recovery_message(f"KiCad analyzer schema probe failed: {detail}"),
            diagnostic=command,
        )
    try:
        schema = json.loads(command["stdout"])
    except json.JSONDecodeError as exc:
        raise ConfigError(
            recovery_message(f"KiCad analyzer returned invalid schema JSON: {exc}"),
            diagnostic=command,
        ) from exc
    version = _schema_version(schema)
    parsed = _version_tuple(version)
    if parsed is None or parsed[:2] != REQUIRED_SCHEMA:
        raise ConfigError(
            recovery_message(
                f"KiCad analyzer schema {version or 'unknown'} is incompatible; schema 1.4.x required"
            ),
            diagnostic=command,
        )
    return {
        "root": Path(root),
        "script": script,
        "schema_version": version,
        "package_version": "unknown",
        "probe": command,
    }


def validate_analysis(data: Any, source: Path) -> dict[str, Any]:
    def shape_error(path: str, expected: str) -> ConfigError:
        return ConfigError(f"analyzer output {source} field {path} must be {expected}")

    if not isinstance(data, dict):
        raise ConfigError(f"analyzer output {source} is not a JSON object")
    version = data.get("schema_version")
    parsed = _version_tuple(version if isinstance(version, str) else None)
    if parsed is None or parsed[:2] != REQUIRED_SCHEMA:
        raise ConfigError(
            recovery_message(
                f"analyzer output {source} has schema {version or 'unknown'}; schema 1.4.x required"
            )
        )
    for field in ("components", "bom", "findings"):
        value = data.get(field)
        if not isinstance(value, list):
            raise shape_error(field, "a list")
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                raise shape_error(f"{field}[{index}]", "an object")
    nets = data.get("nets")
    if not isinstance(nets, dict):
        raise shape_error("nets", "an object")
    for name, net_value in nets.items():
        net_path = f"nets[{name!r}]"
        if not isinstance(net_value, dict):
            raise shape_error(net_path, "an object")
        pins = net_value.get("pins")
        if not isinstance(pins, list):
            raise shape_error(f"{net_path}.pins", "a list")
        for index, item in enumerate(pins):
            if not isinstance(item, dict):
                raise shape_error(f"{net_path}.pins[{index}]", "an object")

    for index, bom_item in enumerate(data["bom"]):
        references = bom_item.get("references")
        if references is None:
            continue
        path = f"bom[{index}].references"
        if not isinstance(references, list):
            raise shape_error(path, "a list")
        for reference_index, reference in enumerate(references):
            if not isinstance(reference, str):
                raise shape_error(f"{path}[{reference_index}]", "a string")

    for index, finding_item in enumerate(data["findings"]):
        finding_path = f"findings[{index}]"
        for field in ("components", "nets", "pins"):
            value = finding_item.get(field)
            if value is None:
                continue
            path = f"{finding_path}.{field}"
            if not isinstance(value, list):
                raise shape_error(path, "a list")
            allowed_types = (str, dict) if field == "pins" else (str,)
            expected = "a string or object" if field == "pins" else "a string"
            for item_index, item in enumerate(value):
                if not isinstance(item, allowed_types):
                    raise shape_error(f"{path}[{item_index}]", expected)
    return data


def validate_analysis_file(path: Path) -> dict[str, Any]:
    return validate_analysis(read_json(path), path)


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _member(value: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _text(value.get("component")),
        _text(value.get("pin_number")),
        _text(value.get("pin_name")),
    )


def _is_unnamed(name: str) -> bool:
    return not name or name.startswith("__unnamed_")


def _finding_identity(finding: dict[str, Any]) -> str:
    for field in ("finding_id", "detection_id"):
        if finding.get(field):
            return _text(finding[field])
    locator = {
        "detector": finding.get("detector"),
        "rule_id": finding.get("rule_id"),
        "components": sorted(_text(item) for item in (finding.get("components") or [])),
        "nets": sorted(_text(item) for item in (finding.get("nets") or [])),
        "pins": sorted(canonical_json(item) for item in (finding.get("pins") or [])),
    }
    if not locator["components"] and not locator["nets"] and not locator["pins"]:
        locator["summary"] = finding.get("summary")
    return "derived:" + sha256_bytes(canonical_json(locator).encode())[:20]


def canonicalize_analysis(data: dict[str, Any]) -> dict[str, Any]:
    components: dict[str, dict[str, Any]] = {}
    for raw in data.get("components", []):
        reference = _text(raw.get("reference"))
        if not reference or reference.startswith("#"):
            continue
        dnp = bool(raw.get("dnp", False))
        included = raw.get("in_bom", raw.get("exclude_from_bom") is not True)
        if not included:
            bom_state = "excluded"
        elif dnp:
            bom_state = "dnp"
        else:
            bom_state = "included"
        components[reference] = {
            "value": _text(raw.get("value")),
            "footprint": _text(raw.get("footprint")),
            "mpn": _text(raw.get("mpn") or raw.get("MPN")),
            "manufacturer": _text(raw.get("manufacturer") or raw.get("Manufacturer")),
            "datasheet": _text(raw.get("datasheet") or raw.get("Datasheet")),
            "dnp": dnp,
            "bom_state": bom_state,
        }
    components = {key: components[key] for key in sorted(components)}

    nets: list[dict[str, Any]] = []
    no_connects: set[tuple[str, str, str]] = set()
    for key, raw in data.get("nets", {}).items():
        raw_name = _text(raw.get("name", key))
        members = sorted(
            {
                _member(item)
                for item in raw.get("pins", [])
                if _text(item.get("component"))
                and not _text(item.get("component")).startswith("#")
            }
        )
        name = "" if _is_unnamed(raw_name) else raw_name
        if name:
            identity = "named:" + name
        else:
            identity = "members:" + sha256_bytes(canonical_json(members).encode())[:20]
        record = {
            "identity": identity,
            "name": name,
            "members": [list(item) for item in members],
        }
        nets.append(record)
        if raw.get("no_connect"):
            no_connects.update(members)
    nets.sort(key=lambda item: (item["name"], item["identity"], item["members"]))

    bom_groups: dict[str, dict[str, Any]] = {}
    for raw in data.get("bom", []):
        references = sorted(
            _text(ref)
            for ref in (raw.get("references") or ([raw.get("reference")] if raw.get("reference") else []))
            if _text(ref) and not _text(ref).startswith("#")
        )
        metadata = {field: raw.get(field) for field in BOM_FIELDS}
        metadata = {
            field: bool(value) if field == "dnp" else _text(value)
            for field, value in metadata.items()
        }
        group_key = canonical_json([metadata["value"], metadata["footprint"]])
        record = {**metadata, "references": references, "quantity": len(references)}
        if group_key in bom_groups:
            group_key += ":" + sha256_bytes(canonical_json(metadata).encode())[:12]
        bom_groups[group_key] = record
    bom_groups = {key: bom_groups[key] for key in sorted(bom_groups)}

    findings: dict[str, dict[str, Any]] = {}
    for raw in data.get("findings", []):
        identity = _finding_identity(raw)
        record: dict[str, Any] = {}
        for field in FINDING_FIELDS:
            value = raw.get(field)
            if field in {"components", "nets"}:
                value = sorted(_text(item) for item in (value or []))
            elif field == "pins":
                value = sorted((value or []), key=canonical_json)
            record[field] = value
        findings[identity] = record
    findings = {key: findings[key] for key in sorted(findings)}

    return {
        "schema_version": "1.0",
        "components": components,
        "nets": nets,
        "no_connects": [list(item) for item in sorted(no_connects)],
        "bom_groups": bom_groups,
        "findings": findings,
    }


def _changed_fields(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[Any]]:
    return {
        key: [before.get(key), after.get(key)]
        for key in sorted(set(before) | set(after))
        if before.get(key) != after.get(key)
    }


def _net_label(net: dict[str, Any]) -> str:
    return net["name"] or net["identity"]


def semantic_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_components = before["components"]
    after_components = after["components"]
    component_added = sorted(set(after_components) - set(before_components))
    component_removed = sorted(set(before_components) - set(after_components))
    component_changed = [
        {
            "reference": reference,
            "fields": _changed_fields(before_components[reference], after_components[reference]),
        }
        for reference in sorted(set(before_components) & set(after_components))
        if before_components[reference] != after_components[reference]
    ]

    before_nets = {item["identity"]: item for item in before["nets"]}
    after_nets = {item["identity"]: item for item in after["nets"]}
    before_by_members = {canonical_json(item["members"]): item for item in before["nets"]}
    after_by_members = {canonical_json(item["members"]): item for item in after["nets"]}
    net_renames: list[dict[str, str]] = []
    renamed_before: set[str] = set()
    renamed_after: set[str] = set()
    rename_translation: dict[str, str] = {}
    for members in sorted(set(before_by_members) & set(after_by_members)):
        old = before_by_members[members]
        new = after_by_members[members]
        if old["name"] and new["name"] and old["name"] != new["name"]:
            net_renames.append({"from": old["name"], "to": new["name"]})
            renamed_before.add(old["identity"])
            renamed_after.add(new["identity"])
            rename_translation[old["name"]] = new["name"]

    before_pin_map: dict[tuple[str, str], dict[str, str]] = {}
    after_pin_map: dict[tuple[str, str], dict[str, str]] = {}
    for item in before["nets"]:
        for member in item["members"]:
            before_pin_map[(member[0], member[1])] = {
                "pin_name": member[2],
                "net": _net_label(item),
            }
    for item in after["nets"]:
        for member in item["members"]:
            after_pin_map[(member[0], member[1])] = {
                "pin_name": member[2],
                "net": _net_label(item),
            }
    pin_changes: list[dict[str, Any]] = []
    for pin_identity in sorted(set(before_pin_map) | set(after_pin_map)):
        if pin_identity[0] in component_added or pin_identity[0] in component_removed:
            continue
        old = before_pin_map.get(pin_identity)
        new = after_pin_map.get(pin_identity)
        old_label = old["net"] if old else None
        new_label = new["net"] if new else None
        old_name = old["pin_name"] if old else ""
        new_name = new["pin_name"] if new else ""
        same_net = rename_translation.get(old_label, old_label) == new_label
        same_name = old_name == new_name
        if same_net and same_name:
            continue
        change: dict[str, Any] = {
            "member": [pin_identity[0], pin_identity[1], new_name or old_name],
            "from": old_label,
            "to": new_label,
        }
        if old is not None and new is not None and not same_name:
            change["pin_name"] = {"from": old_name, "to": new_name}
        pin_changes.append(change)

    before_bom = before["bom_groups"]
    after_bom = after["bom_groups"]
    bom_changed = [
        {"identity": identity, "before": before_bom[identity], "after": after_bom[identity]}
        for identity in sorted(set(before_bom) & set(after_bom))
        if before_bom[identity] != after_bom[identity]
    ]

    before_findings = before["findings"]
    after_findings = after["findings"]
    finding_added = [
        {"identity": identity, **after_findings[identity]}
        for identity in sorted(set(after_findings) - set(before_findings))
    ]
    finding_removed = [
        {"identity": identity, **before_findings[identity]}
        for identity in sorted(set(before_findings) - set(after_findings))
    ]
    finding_changed = [
        {
            "identity": identity,
            "before": before_findings[identity],
            "after": after_findings[identity],
            "fields": _changed_fields(before_findings[identity], after_findings[identity]),
        }
        for identity in sorted(set(before_findings) & set(after_findings))
        if before_findings[identity] != after_findings[identity]
    ]

    return {
        "components": {
            "added": component_added,
            "removed": component_removed,
            "changed": component_changed,
        },
        "nets": {
            "added": [
                _net_label(after_nets[key])
                for key in sorted(set(after_nets) - set(before_nets) - renamed_after)
            ],
            "removed": [
                _net_label(before_nets[key])
                for key in sorted(set(before_nets) - set(after_nets) - renamed_before)
            ],
        },
        "net_renames": net_renames,
        "pin_net_changes": pin_changes,
        "no_connects": {
            "added": sorted([item for item in after["no_connects"] if item not in before["no_connects"]]),
            "removed": sorted([item for item in before["no_connects"] if item not in after["no_connects"]]),
        },
        "bom_groups": {
            "added": [after_bom[key] for key in sorted(set(after_bom) - set(before_bom))],
            "removed": [before_bom[key] for key in sorted(set(before_bom) - set(after_bom))],
            "changed": bom_changed,
        },
        "findings": {
            "added": finding_added,
            "removed": finding_removed,
            "changed": finding_changed,
        },
    }


def delta_is_empty(delta: Any) -> bool:
    if isinstance(delta, dict):
        return all(delta_is_empty(value) for value in delta.values())
    if isinstance(delta, list):
        return len(delta) == 0
    return not bool(delta)


def new_blocking_finding_ids(delta: dict[str, Any]) -> list[str]:
    added = [
        item["identity"]
        for item in delta["findings"]["added"]
        if item.get("severity") == "error" and item.get("confidence") == "deterministic"
    ]
    changed = [
        item["identity"]
        for item in delta["findings"]["changed"]
        if item["after"].get("severity") == "error"
        and item["after"].get("confidence") == "deterministic"
        and not (
            item["before"].get("severity") == "error"
            and item["before"].get("confidence") == "deterministic"
        )
    ]
    return sorted(added + changed)


def hash_footprints(library: Path) -> dict[str, Any]:
    if not library.is_dir():
        raise ConfigError(f"custom footprint library missing: {library}")
    files = {
        path.relative_to(library).as_posix(): sha256_file(path)
        for path in sorted(library.rglob("*.kicad_mod"))
    }
    aggregate_source = "".join(f"{name}\0{files[name]}\n" for name in sorted(files))
    return {"files": files, "aggregate": sha256_bytes(aggregate_source.encode())}


def diff_footprints(before: dict[str, str], after: dict[str, str]) -> dict[str, list[str]]:
    return {
        "added": sorted(set(after) - set(before)),
        "modified": sorted(name for name in set(before) & set(after) if before[name] != after[name]),
        "deleted": sorted(set(before) - set(after)),
    }


def pcb_drift_exit(baseline_hash: str, current_hash: str) -> int:
    return 0 if baseline_hash == current_hash else 1


def _command_tooling_failure(result: dict[str, Any]) -> bool:
    code = result.get("returncode")
    return (
        code is None
        or code < 0
        or bool(result.get("missing_outputs"))
        or bool(result.get("unexpected_outputs"))
    )


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def _require_repo_inputs() -> None:
    missing = [str(path) for path in (SCHEMATIC, PCB, FOOTPRINT_LIBRARY) if not path.exists()]
    if missing:
        raise ConfigError("missing repository input(s): " + ", ".join(missing))


def _source_hashes() -> dict[str, str]:
    return {
        "schematic": sha256_file(SCHEMATIC),
        "pcb": sha256_file(PCB),
    }


def _run_analyzer(output: Path, diagnostics: dict[str, Any]) -> dict[str, Any] | None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    before_outputs = {str(path) for path in output.parent.rglob("*")}
    capability_sidecar = output.parent / "capability_mode.json"
    try:
        analyzer = probe_analyzer(resolve_analyzer_root())
    except ConfigError as exc:
        if exc.diagnostic is not None:
            diagnostics["commands"].append(exc.diagnostic)
        diagnostics["analyzer_error"] = str(exc)
        return None
    diagnostics["commands"].append(analyzer["probe"])
    result = run_command(
        [sys.executable, analyzer["script"], SCHEMATIC, "--output", output, "--compact"],
        cwd=REPO_ROOT,
        expected_outputs=[output],
    )
    after_outputs = {str(path) for path in output.parent.rglob("*")}
    new_outputs = sorted(after_outputs - before_outputs)
    known_outputs = {str(output), str(capability_sidecar)}
    result["optional_outputs"] = [str(capability_sidecar)]
    result["observed_optional_outputs"] = (
        [str(capability_sidecar)] if capability_sidecar.is_file() else []
    )
    result["expected_outputs"].extend(result["observed_optional_outputs"])
    result["new_outputs"] = new_outputs
    result["unexpected_outputs"] = [
        path for path in new_outputs if path not in known_outputs
    ]
    diagnostics["commands"].append(result)
    if result["returncode"] != 0 or _command_tooling_failure(result):
        return None
    try:
        return validate_analysis_file(output)
    except ConfigError as exc:
        diagnostics["analyzer_error"] = str(exc)
        return None


def _parse_changed_footprints(
    directory: Path,
    changes: dict[str, list[str]],
    diagnostics: dict[str, Any],
) -> bool:
    to_parse = changes["added"] + changes["modified"]
    if not to_parse:
        return True
    source = directory / "changed.pretty"
    parsed = directory / "changed-parsed.pretty"
    _reset_dir(source)
    if parsed.exists():
        shutil.rmtree(parsed)
    for name in to_parse:
        source_path = FOOTPRINT_LIBRARY / name
        target_path = source / name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
    expected = [parsed / name for name in to_parse]
    result = run_command(
        [kicad_cli_path(), "fp", "upgrade", source, "-o", parsed, "--force"],
        cwd=REPO_ROOT,
        expected_outputs=expected,
    )
    diagnostics["commands"].append(result)
    return result["returncode"] == 0 and not result["missing_outputs"]


def _load_baseline(directory: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    baseline_path = directory / "baseline.json"
    state_path = directory / "baseline-state.json"
    if not baseline_path.is_file() or not state_path.is_file():
        raise ConfigError(f"session is incomplete; run clean then preflight again: {directory.name}")
    baseline = read_json(baseline_path)
    state = read_json(state_path)
    return baseline, state


def _compute_current(directory: Path, diagnostics: dict[str, Any]) -> dict[str, Any] | None:
    try:
        baseline, baseline_state = _load_baseline(directory)
    except ConfigError as exc:
        diagnostics["error"] = str(exc)
        return None
    current_analysis_path = directory / "current-analysis.json"
    analysis_data = _run_analyzer(current_analysis_path, diagnostics)
    footprints = hash_footprints(FOOTPRINT_LIBRARY)
    footprint_changes = diff_footprints(baseline["footprints"]["files"], footprints["files"])
    diagnostics["footprint_changes"] = footprint_changes
    parse_ok = _parse_changed_footprints(directory, footprint_changes, diagnostics)
    if analysis_data is None:
        return None
    state = canonicalize_analysis(analysis_data)
    delta = semantic_diff(baseline_state, state)
    write_json(directory / "current-state.json", state)
    write_json(directory / "delta.json", delta)
    return {
        "baseline": baseline,
        "baseline_state": baseline_state,
        "analysis": analysis_data,
        "state": state,
        "delta": delta,
        "footprints": footprints,
        "footprint_changes": footprint_changes,
        "parse_ok": parse_ok,
    }


def _delta_counts(delta: dict[str, Any]) -> dict[str, int]:
    return {
        "components_added": len(delta["components"]["added"]),
        "components_removed": len(delta["components"]["removed"]),
        "components_changed": len(delta["components"]["changed"]),
        "net_renames": len(delta["net_renames"]),
        "pin_net_changes": len(delta["pin_net_changes"]),
        "no_connect_changes": len(delta["no_connects"]["added"])
        + len(delta["no_connects"]["removed"]),
        "bom_group_changes": len(delta["bom_groups"]["added"])
        + len(delta["bom_groups"]["removed"])
        + len(delta["bom_groups"]["changed"]),
        "findings_added": len(delta["findings"]["added"]),
        "findings_removed": len(delta["findings"]["removed"]),
        "findings_changed": len(delta["findings"]["changed"]),
    }


def _print_delta(delta: dict[str, Any], footprint_changes: dict[str, list[str]]) -> None:
    def show(label: str, values: list[str]) -> None:
        if values:
            print(f"{label}: {', '.join(values)}")

    def member_text(member: list[str]) -> str:
        return ".".join(part for part in member if part)

    def bom_text(group: dict[str, Any]) -> str:
        references = group.get("references") or []
        if references:
            return ",".join(references)
        return f"{group.get('value', '')}@{group.get('footprint', '')}"

    counts = _delta_counts(delta)
    print("semantic delta: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    show("components added", delta["components"]["added"])
    show("components removed", delta["components"]["removed"])
    show(
        "components changed",
        [item["reference"] for item in delta["components"]["changed"]],
    )
    show(
        "no-connect added",
        [member_text(item) for item in delta["no_connects"]["added"]],
    )
    show(
        "no-connect removed",
        [member_text(item) for item in delta["no_connects"]["removed"]],
    )
    show("bom added", [bom_text(item) for item in delta["bom_groups"]["added"]])
    show("bom removed", [bom_text(item) for item in delta["bom_groups"]["removed"]])
    show(
        "bom changed",
        [item["identity"] for item in delta["bom_groups"]["changed"]],
    )
    for category in ("added", "removed", "changed"):
        show(
            f"findings {category}",
            [item["identity"] for item in delta["findings"][category]],
        )
    show("footprints added", footprint_changes["added"])
    show("footprints modified", footprint_changes["modified"])
    show("footprints deleted", footprint_changes["deleted"])
    for rename in delta["net_renames"]:
        print(f"net rename: {rename['from']} -> {rename['to']}")
    for change in delta["pin_net_changes"]:
        print(f"pin move: {'.'.join(change['member'][:2])} {change['from']} -> {change['to']}")


def command_doctor() -> int:
    problems: list[str] = []
    print(f"repo: {REPO_ROOT}")
    for label, path in (
        ("schematic", SCHEMATIC),
        ("pcb", PCB),
        ("footprint library", FOOTPRINT_LIBRARY),
    ):
        exists = path.exists()
        print(f"{label}: {'ok' if exists else 'missing'} ({path})")
        if not exists:
            problems.append(f"{label} missing")
    cli = kicad_cli_path()
    cli_ok = cli.is_file() and os.access(cli, os.X_OK)
    print(f"kicad-cli: {'ok' if cli_ok else 'missing or not executable'} ({cli})")
    if not cli_ok:
        problems.append("kicad-cli unavailable")
    try:
        analyzer = probe_analyzer(resolve_analyzer_root())
        print(f"kicad-happy package: {analyzer['package_version']}")
        print(f"analyzer schema: {analyzer['schema_version']} (compatible)")
        print(f"analyzer: {analyzer['script']}")
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        problems.append("analyzer unavailable or incompatible")
    if problems:
        print("doctor: tooling/config failure: " + ", ".join(problems), file=sys.stderr)
        return 2
    print("doctor: pass")
    return 0


def command_preflight(session: str) -> int:
    _require_repo_inputs()
    directory = session_path(CACHE_ROOT, session)
    create_session_directory(directory, session)
    diagnostics: dict[str, Any] = {"session": session, "commands": [], "status": "running"}
    report = directory / "preflight-erc.rpt"
    erc = run_command(
        [kicad_cli_path(), "sch", "erc", SCHEMATIC, "-o", report, "--exit-code-violations"],
        cwd=REPO_ROOT,
        expected_outputs=[report],
    )
    diagnostics["commands"].append(erc)
    if _command_tooling_failure(erc):
        diagnostics["status"] = "tooling_failure"
        write_json(directory / "preflight.json", diagnostics)
        return 2
    if erc["returncode"] != 0:
        diagnostics["status"] = "erc_regression"
        write_json(directory / "preflight.json", diagnostics)
        return 1
    source_hashes = _source_hashes()
    footprints = hash_footprints(FOOTPRINT_LIBRARY)
    analysis_path = directory / "baseline-analysis.json"
    analysis_data = _run_analyzer(analysis_path, diagnostics)
    if analysis_data is None:
        diagnostics["status"] = "tooling_failure"
        write_json(directory / "preflight.json", diagnostics)
        return 2
    state = canonicalize_analysis(analysis_data)
    baseline = {
        "schema_version": "1.0",
        "session": session,
        "sources": source_hashes,
        "footprints": footprints,
        "analyzer_schema": analysis_data["schema_version"],
    }
    write_json(directory / "baseline-state.json", state)
    write_json(directory / "baseline.json", baseline)
    diagnostics["status"] = "pass"
    diagnostics["sources"] = source_hashes
    diagnostics["footprints"] = footprints
    write_json(directory / "preflight.json", diagnostics)
    print(f"preflight pass: session={session} cache={directory}")
    return 0


def command_quick(session: str) -> int:
    _require_repo_inputs()
    directory = session_path(CACHE_ROOT, session)
    if not directory.is_dir():
        raise ConfigError(f"session does not exist: {directory}; run preflight {session}")
    diagnostics: dict[str, Any] = {"session": session, "commands": [], "status": "running"}
    try:
        current = _compute_current(directory, diagnostics)
    except ConfigError as exc:
        diagnostics["error"] = str(exc)
        current = None
    if current is None or not current["parse_ok"]:
        diagnostics["status"] = "tooling_failure"
        write_json(directory / "quick.json", diagnostics)
        return 2
    delta = current["delta"]
    blockers = new_blocking_finding_ids(delta)
    diagnostics["status"] = "design_regression" if blockers else "pass"
    diagnostics["blocking_findings"] = blockers
    diagnostics["counts"] = _delta_counts(delta)
    write_json(directory / "quick.json", diagnostics)
    _print_delta(delta, current["footprint_changes"])
    if blockers:
        print("blocking new deterministic errors: " + ", ".join(blockers), file=sys.stderr)
        return 1
    return 0


def _record_unexpected_files(result: dict[str, Any], directory: Path, expected: list[Path]) -> None:
    if not directory.is_dir():
        return
    expected_set = {str(path) for path in expected}
    result["unexpected_outputs"] = [
        str(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file() and str(path) not in expected_set
    ]


def command_verify(session: str) -> int:
    _require_repo_inputs()
    directory = session_path(CACHE_ROOT, session)
    if not directory.is_dir():
        raise ConfigError(f"session does not exist: {directory}; run preflight {session}")
    verification: dict[str, Any] = {
        "session": session,
        "commands": [],
        "checks": {},
        "status": "running",
    }
    tooling_failure = False
    design_regression = False
    try:
        current = _compute_current(directory, verification)
    except ConfigError as exc:
        verification["error"] = str(exc)
        current = None
    if current is None or not current["parse_ok"]:
        tooling_failure = True

    report = directory / "verify-erc.rpt"
    if report.exists():
        report.unlink()
    erc = run_command(
        [kicad_cli_path(), "sch", "erc", SCHEMATIC, "-o", report, "--exit-code-violations"],
        cwd=REPO_ROOT,
        expected_outputs=[report],
    )
    verification["commands"].append(erc)
    if _command_tooling_failure(erc):
        tooling_failure = True
    elif erc["returncode"] != 0:
        design_regression = True
    verification["checks"]["erc"] = {
        "passed": erc["returncode"] == 0 and not erc["missing_outputs"],
        "report": str(report),
    }

    netlist = directory / "c6remote.net"
    if netlist.exists():
        netlist.unlink()
    netlist_result = run_command(
        [kicad_cli_path(), "sch", "export", "netlist", SCHEMATIC, "-o", netlist],
        cwd=REPO_ROOT,
        expected_outputs=[netlist],
    )
    verification["commands"].append(netlist_result)
    if netlist_result["returncode"] != 0 or netlist_result["missing_outputs"]:
        tooling_failure = True

    bom = directory / "c6remote-bom.csv"
    if bom.exists():
        bom.unlink()
    bom_result = run_command(
        [
            kicad_cli_path(),
            "sch",
            "export",
            "bom",
            SCHEMATIC,
            "-o",
            bom,
            "--fields",
            "Reference,QUANTITY,Value,Footprint,Datasheet,Description,Manufacturer,MPN,Digikey,Mouser,Adafruit,LCSC",
            "--labels",
            "Reference,Qty,Value,Footprint,Datasheet,Description,Manufacturer,MPN,Digikey,Mouser,Adafruit,LCSC",
            "--group-by",
            "Value,Footprint",
            "--ref-delimiter",
            ", ",
            "--ref-range-delimiter",
            "",
        ],
        cwd=REPO_ROOT,
        expected_outputs=[bom],
    )
    verification["commands"].append(bom_result)
    if bom_result["returncode"] != 0 or bom_result["missing_outputs"]:
        tooling_failure = True

    parsed_library = directory / "Library-parsed.pretty"
    if parsed_library.exists():
        shutil.rmtree(parsed_library)
    expected_footprints = [
        parsed_library / path.relative_to(FOOTPRINT_LIBRARY)
        for path in sorted(FOOTPRINT_LIBRARY.rglob("*.kicad_mod"))
    ]
    fp_result = run_command(
        [kicad_cli_path(), "fp", "upgrade", FOOTPRINT_LIBRARY, "-o", parsed_library, "--force"],
        cwd=REPO_ROOT,
        expected_outputs=expected_footprints,
    )
    _record_unexpected_files(fp_result, parsed_library, expected_footprints)
    verification["commands"].append(fp_result)
    if fp_result["returncode"] != 0 or _command_tooling_failure(fp_result):
        tooling_failure = True

    svg_directory = directory / "footprint-svg"
    _reset_dir(svg_directory)
    footprint_changes = (
        current["footprint_changes"]
        if current is not None
        else {"added": [], "modified": [], "deleted": []}
    )
    for name in footprint_changes["added"] + footprint_changes["modified"]:
        footprint_name = Path(name).stem
        expected_svg = svg_directory / f"{footprint_name}.svg"
        svg_result = run_command(
            [
                kicad_cli_path(),
                "fp",
                "export",
                "svg",
                FOOTPRINT_LIBRARY,
                "-o",
                svg_directory,
                "--footprint",
                footprint_name,
                "--layers",
                "F.Cu,F.Paste,F.SilkS,F.Fab",
                "--black-and-white",
            ],
            cwd=REPO_ROOT,
            expected_outputs=[expected_svg],
        )
        verification["commands"].append(svg_result)
        if svg_result["returncode"] != 0 or svg_result["missing_outputs"]:
            tooling_failure = True

    diff_check = run_command(["git", "diff", "--check"], cwd=REPO_ROOT)
    verification["commands"].append(diff_check)
    if diff_check["returncode"] is None or diff_check["returncode"] < 0:
        tooling_failure = True
    elif diff_check["returncode"] != 0:
        design_regression = True

    try:
        baseline, _ = _load_baseline(directory)
        current_pcb_hash = sha256_file(PCB)
        pcb_drift = pcb_drift_exit(baseline["sources"]["pcb"], current_pcb_hash)
        verification["checks"]["pcb_hash"] = {
            "baseline": baseline["sources"]["pcb"],
            "current": current_pcb_hash,
            "passed": pcb_drift == 0,
        }
        design_regression = design_regression or pcb_drift == 1
    except (ConfigError, KeyError, OSError) as exc:
        verification["checks"]["pcb_hash"] = {"passed": False, "error": str(exc)}
        tooling_failure = True

    blockers: list[str] = []
    if current is not None:
        blockers = new_blocking_finding_ids(current["delta"])
        design_regression = design_regression or bool(blockers)
        verification["checks"]["semantic_delta"] = {
            "counts": _delta_counts(current["delta"]),
            "blocking_findings": blockers,
            "footprint_changes": footprint_changes,
        }

    exit_code = 2 if tooling_failure else 1 if design_regression else 0
    verification["status"] = {0: "pass", 1: "design_regression", 2: "tooling_failure"}[exit_code]
    verification["exit_code"] = exit_code
    write_json(directory / "verification.json", verification)
    if current is not None:
        _print_delta(current["delta"], footprint_changes)
    print(f"verify: {verification['status']}")
    return exit_code


def command_clean(session: str) -> int:
    directory = session_path(CACHE_ROOT, session)
    if not directory.exists():
        print(f"clean: session absent: {session}")
        return 0
    if not directory.is_dir():
        raise ConfigError(f"session target is not a directory: {directory}")
    shutil.rmtree(directory)
    print(f"clean: removed {directory}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("doctor", help="check KiCad and analyzer dependencies")
    for name, help_text in (
        ("preflight", "create a session baseline after native ERC"),
        ("quick", "run fast semantic and changed-footprint checks"),
        ("verify", "run full session verification"),
        ("clean", "remove one validated session cache"),
    ):
        command = subcommands.add_parser(name, help=help_text)
        command.add_argument("session")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "doctor":
            return command_doctor()
        if args.command == "preflight":
            return command_preflight(args.session)
        if args.command == "quick":
            return command_quick(args.session)
        if args.command == "verify":
            return command_verify(args.session)
        if args.command == "clean":
            return command_clean(args.session)
    except ConfigError as exc:
        print(f"tooling/config error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
