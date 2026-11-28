import json
import io
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from scripts import hw


def component(reference, **changes):
    value = {
        "reference": reference,
        "value": "10k",
        "footprint": "Library:R_0603",
        "mpn": "RC0603",
        "manufacturer": "Yageo",
        "datasheet": "https://example.test/rc0603.pdf",
        "dnp": False,
        "in_bom": True,
    }
    value.update(changes)
    return value


def pin(reference, number, name=""):
    return {
        "component": reference,
        "pin_number": str(number),
        "pin_name": name,
        "pin_type": "passive",
    }


def net(name, *pins, no_connect=False):
    return {
        "name": name,
        "pins": list(pins),
        "point_count": len(pins),
        "no_connect": no_connect,
        "labels": [],
    }


def finding(finding_id="finding:a", **changes):
    value = {
        "finding_id": finding_id,
        "detector": "connectivity",
        "rule_id": "NT-001",
        "severity": "warning",
        "confidence": "deterministic",
        "evidence_source": "topology",
        "summary": "single pin net",
        "recommendation": "connect it",
        "components": ["R1"],
        "nets": ["SIG"],
        "pins": [{"component": "R1", "pin_number": "1"}],
    }
    value.update(changes)
    return value


def analysis(*, components=None, nets=None, bom=None, findings=None):
    return {
        "analyzer_type": "schematic",
        "schema_version": "1.4.0",
        "components": components or [component("R1"), component("R2")],
        "nets": nets
        or {
            "SIG": net("SIG", pin("R1", 1, "A"), pin("R2", 1, "A")),
            "GND": net("GND", pin("R1", 2, "B"), pin("R2", 2, "B")),
        },
        "bom": bom
        or [
            {
                "value": "10k",
                "footprint": "Library:R_0603",
                "mpn": "RC0603",
                "manufacturer": "Yageo",
                "datasheet": "https://example.test/rc0603.pdf",
                "description": "resistor",
                "references": ["R1", "R2"],
                "quantity": 2,
                "dnp": False,
                "type": "passive",
            }
        ],
        "findings": findings or [finding()],
        "no_connects": [{"x": 1.0, "y": 2.0}],
    }


def current_result(raw=None):
    raw = raw or analysis()
    state = hw.canonicalize_analysis(raw)
    return {
        "analysis": raw,
        "state": state,
        "delta": hw.semantic_diff(state, state),
        "footprint_changes": {"added": [], "modified": [], "deleted": []},
        "parse_ok": True,
    }


def write_ready_session(directory, session, sources, footprints=None):
    state = hw.canonicalize_analysis(analysis())
    hw.write_json(
        directory / "session.json",
        {"schema_version": hw.SESSION_SCHEMA, "session": session, "status": "ready"},
    )
    hw.write_json(
        directory / "baseline.json",
        {
            "schema_version": hw.SESSION_SCHEMA,
            "session": session,
            "sources": sources,
            "footprints": footprints or {"files": {}, "aggregate": "baseline"},
            "analysis_fingerprint": {"digest": "baseline"},
        },
    )
    hw.write_json(directory / "baseline-state.json", state)


class CanonicalStateTests(unittest.TestCase):
    def test_serialization_and_reordering_have_no_semantic_delta(self):
        first = analysis()
        reordered = analysis(
            components=list(reversed(first["components"])),
            nets={"GND": first["nets"]["GND"], "SIG": first["nets"]["SIG"]},
            bom=[{**first["bom"][0], "references": ["R2", "R1"]}],
            findings=list(reversed(first["findings"])),
        )
        reordered["nets"]["SIG"]["pins"].reverse()

        delta = hw.semantic_diff(
            hw.canonicalize_analysis(first), hw.canonicalize_analysis(reordered)
        )

        self.assertTrue(hw.delta_is_empty(delta), delta)

    def test_power_symbols_are_excluded_and_component_bom_state_is_explicit(self):
        raw = analysis(
            components=[
                component("#PWR01", value="GND", in_bom=False),
                component("R1", dnp=True),
                component("TP1", in_bom=False),
            ],
            nets={"GND": net("GND", pin("#PWR01", 1), pin("R1", 2))},
        )

        state = hw.canonicalize_analysis(raw)

        self.assertNotIn("#PWR01", state["components"])
        self.assertEqual("dnp", state["components"]["R1"]["bom_state"])
        self.assertEqual("excluded", state["components"]["TP1"]["bom_state"])
        self.assertEqual(["R1"], [member[0] for member in state["nets"][0]["members"]])

    def test_added_component_is_compact_and_does_not_add_pin_reassignments(self):
        before = hw.canonicalize_analysis(analysis())
        after_raw = analysis()
        after_raw["components"].append(component("C1", value="100n"))
        after_raw["nets"]["SIG"]["pins"].append(pin("C1", 1))
        after = hw.canonicalize_analysis(after_raw)

        delta = hw.semantic_diff(before, after)

        self.assertEqual(["C1"], delta["components"]["added"])
        self.assertEqual([], delta["pin_net_changes"])

    def test_component_metadata_change_reports_exact_fields(self):
        before = hw.canonicalize_analysis(analysis())
        raw = analysis()
        raw["components"][0]["mpn"] = "NEW-MPN"
        raw["components"][0]["dnp"] = True
        after = hw.canonicalize_analysis(raw)

        changed = hw.semantic_diff(before, after)["components"]["changed"]

        self.assertEqual("R1", changed[0]["reference"])
        self.assertEqual(
            {"bom_state": ["included", "dnp"], "dnp": [False, True], "mpn": ["RC0603", "NEW-MPN"]},
            changed[0]["fields"],
        )

    def test_pin_reassignment_reports_one_exact_pin_move(self):
        before = hw.canonicalize_analysis(analysis())
        raw = analysis()
        moved = raw["nets"]["SIG"]["pins"].pop(0)
        raw["nets"]["GND"]["pins"].append(moved)
        after = hw.canonicalize_analysis(raw)

        changes = hw.semantic_diff(before, after)["pin_net_changes"]

        self.assertEqual(
            [{"member": ["R1", "1", "A"], "from": "SIG", "to": "GND"}], changes
        )

    def test_named_net_pin_attach_and_detach_are_reported(self):
        before_raw = analysis(
            components=[component("R1"), component("R2"), component("R3")]
        )
        after_raw = analysis(
            components=[component("R1"), component("R2"), component("R3")]
        )
        after_raw["nets"]["SIG"]["pins"] = [
            pin("R1", 1, "A"),
            pin("R3", 1, "IN"),
        ]

        changes = hw.semantic_diff(
            hw.canonicalize_analysis(before_raw), hw.canonicalize_analysis(after_raw)
        )["pin_net_changes"]

        self.assertEqual(
            [
                {"member": ["R2", "1", "A"], "from": "SIG", "to": None},
                {"member": ["R3", "1", "IN"], "from": None, "to": "SIG"},
            ],
            changes,
        )

    def test_pin_name_change_uses_reference_and_number_identity(self):
        before_raw = analysis()
        after_raw = analysis()
        after_raw["nets"]["SIG"]["pins"][0]["pin_name"] = "RENAMED_A"

        changes = hw.semantic_diff(
            hw.canonicalize_analysis(before_raw), hw.canonicalize_analysis(after_raw)
        )["pin_net_changes"]

        self.assertEqual(
            [
                {
                    "member": ["R1", "1", "RENAMED_A"],
                    "from": "SIG",
                    "to": "SIG",
                    "pin_name": {"from": "A", "to": "RENAMED_A"},
                }
            ],
            changes,
        )

    def test_pure_net_rename_does_not_explode_into_pin_moves(self):
        before = hw.canonicalize_analysis(analysis())
        raw = analysis()
        raw["nets"]["RENAMED"] = raw["nets"].pop("SIG")
        raw["nets"]["RENAMED"]["name"] = "RENAMED"
        after = hw.canonicalize_analysis(raw)

        delta = hw.semantic_diff(before, after)

        self.assertEqual([{"from": "SIG", "to": "RENAMED"}], delta["net_renames"])
        self.assertEqual([], delta["pin_net_changes"])

    def test_unnamed_net_identity_uses_membership_not_analyzer_counter(self):
        before_raw = analysis(nets={"__unnamed_4": net("__unnamed_4", pin("R1", 1), pin("R2", 1))})
        after_raw = analysis(nets={"__unnamed_99": net("__unnamed_99", pin("R2", 1), pin("R1", 1))})

        before = hw.canonicalize_analysis(before_raw)
        after = hw.canonicalize_analysis(after_raw)

        self.assertEqual("", before["nets"][0]["name"])
        self.assertNotIn("__unnamed", json.dumps(before))
        self.assertTrue(hw.delta_is_empty(hw.semantic_diff(before, after)))

    def test_no_connect_delta_comes_from_net_members_not_coordinates(self):
        before_raw = analysis(
            nets={"NC": net("NC", pin("R1", 1, "A"), no_connect=True)}
        )
        after_raw = analysis(
            nets={"NC": net("NC", pin("R2", 1, "A"), no_connect=True)}
        )
        before_raw["no_connects"] = [{"x": 1, "y": 1}]
        after_raw["no_connects"] = [{"x": 999, "y": 999}]

        delta = hw.semantic_diff(
            hw.canonicalize_analysis(before_raw), hw.canonicalize_analysis(after_raw)
        )["no_connects"]

        self.assertEqual([["R2", "1", "A"]], delta["added"])
        self.assertEqual([["R1", "1", "A"]], delta["removed"])

    def test_bom_reference_change_is_canonicalized_as_group_change(self):
        before = hw.canonicalize_analysis(analysis())
        raw = analysis()
        raw["bom"][0]["references"] = ["R1"]
        raw["bom"][0]["quantity"] = 1
        after = hw.canonicalize_analysis(raw)

        changes = hw.semantic_diff(before, after)["bom_groups"]

        self.assertEqual([], changes["added"])
        self.assertEqual([], changes["removed"])
        self.assertEqual(["R1", "R2"], changes["changed"][0]["before"]["references"])
        self.assertEqual(["R1"], changes["changed"][0]["after"]["references"])

    def test_findings_can_be_added_removed_and_changed(self):
        before = hw.canonicalize_analysis(
            analysis(findings=[finding("a"), finding("b"), finding("c")])
        )
        after = hw.canonicalize_analysis(
            analysis(
                findings=[
                    finding("b", severity="error", summary="now broken"),
                    finding("c"),
                    finding("d"),
                ]
            )
        )

        changes = hw.semantic_diff(before, after)["findings"]

        self.assertEqual(["d"], [item["identity"] for item in changes["added"]])
        self.assertEqual(["a"], [item["identity"] for item in changes["removed"]])
        self.assertEqual(["b"], [item["identity"] for item in changes["changed"]])


class FootprintTests(unittest.TestCase):
    def test_added_modified_and_deleted_footprints_are_discovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Path(tmp)
            (library / "same.kicad_mod").write_text("same")
            (library / "modified.kicad_mod").write_text("after")
            (library / "added.kicad_mod").write_text("added")
            baseline = {
                "same.kicad_mod": hw.sha256_bytes(b"same"),
                "modified.kicad_mod": hw.sha256_bytes(b"before"),
                "deleted.kicad_mod": hw.sha256_bytes(b"deleted"),
            }

            current = hw.hash_footprints(library)
            changes = hw.diff_footprints(baseline, current["files"])

        self.assertEqual(["added.kicad_mod"], changes["added"])
        self.assertEqual(["modified.kicad_mod"], changes["modified"])
        self.assertEqual(["deleted.kicad_mod"], changes["deleted"])
        self.assertEqual(64, len(current["aggregate"]))


class SessionTests(unittest.TestCase):
    def test_session_validation_rejects_traversal_before_path_resolution(self):
        for value in (".", "..", "../victim", "/tmp/victim", "bad session", ""):
            with self.subTest(value=value):
                with self.assertRaises(hw.ConfigError):
                    hw.validate_session(value)

    def test_sessions_resolve_to_isolated_sibling_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = hw.session_path(root, "agent.one")
            second = hw.session_path(root, "agent-two")

        self.assertEqual(root / "agent.one", first)
        self.assertEqual(root / "agent-two", second)
        self.assertNotEqual(first, second)

    def test_atomic_session_creation_reports_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "already-there"
            existing.mkdir()

            with self.assertRaises(hw.ConfigError) as caught:
                hw.create_session_directory(existing, "already-there")

        self.assertIn("run clean already-there", str(caught.exception))


class ToolingTests(unittest.TestCase):
    def test_analyzer_run_preserves_schema_probe_and_analysis_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skill"
            script = root / "scripts" / "analyze_schematic.py"
            script.parent.mkdir(parents=True)
            script.write_text(
                "#!/usr/bin/env python3\n"
                "import json, pathlib, sys\n"
                "if '--schema' in sys.argv:\n"
                "    print(json.dumps({'properties': {'schema_version': {'const': '1.4.7'}}}))\n"
                "else:\n"
                "    output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
                "    output.write_text(json.dumps({'schema_version': '1.4.7', "
                "'components': [], 'nets': {}, 'bom': [], 'findings': []}))\n"
                "    (output.parent / 'capability_mode.json').write_text('{}')\n"
            )
            output = Path(tmp) / "analysis.json"
            diagnostics = {"commands": []}
            old = os.environ.get("KICAD_HAPPY_DIR")
            os.environ["KICAD_HAPPY_DIR"] = str(root)
            try:
                result = hw._run_analyzer(output, diagnostics)
            finally:
                if old is None:
                    os.environ.pop("KICAD_HAPPY_DIR", None)
                else:
                    os.environ["KICAD_HAPPY_DIR"] = old

        self.assertIsNotNone(result)
        self.assertEqual(2, len(diagnostics["commands"]))
        self.assertEqual("--schema", diagnostics["commands"][0]["args"][-1])
        self.assertIn("--output", diagnostics["commands"][1]["args"])
        analysis_command = diagnostics["commands"][1]
        self.assertEqual(
            [str(output.parent / "capability_mode.json")],
            analysis_command["observed_optional_outputs"],
        )
        self.assertEqual(
            [str(output), str(output.parent / "capability_mode.json")],
            analysis_command["expected_outputs"],
        )
        self.assertEqual(
            sorted([str(output), str(output.parent / "capability_mode.json")]),
            analysis_command["new_outputs"],
        )
        self.assertEqual([], analysis_command["unexpected_outputs"])

    def test_analyzer_without_capability_sidecar_still_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skill"
            script = root / "scripts" / "analyze_schematic.py"
            script.parent.mkdir(parents=True)
            script.write_text(
                "#!/usr/bin/env python3\n"
                "import json, pathlib, sys\n"
                "if '--schema' in sys.argv:\n"
                "    print(json.dumps({'properties': {'schema_version': {'const': '1.4.0'}}}))\n"
                "else:\n"
                "    output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
                "    output.write_text(json.dumps({'schema_version': '1.4.0', "
                "'components': [], 'nets': {}, 'bom': [], 'findings': []}))\n"
            )
            diagnostics = {"commands": []}
            old = os.environ.get("KICAD_HAPPY_DIR")
            os.environ["KICAD_HAPPY_DIR"] = str(root)
            try:
                result = hw._run_analyzer(Path(tmp) / "analysis.json", diagnostics)
            finally:
                if old is None:
                    os.environ.pop("KICAD_HAPPY_DIR", None)
                else:
                    os.environ["KICAD_HAPPY_DIR"] = old

        self.assertIsNotNone(result)
        self.assertEqual([], diagnostics["commands"][1]["observed_optional_outputs"])
        self.assertEqual([], diagnostics["commands"][1]["unexpected_outputs"])

    def test_analyzer_unexpected_new_file_is_recorded_and_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skill"
            script = root / "scripts" / "analyze_schematic.py"
            script.parent.mkdir(parents=True)
            script.write_text(
                "#!/usr/bin/env python3\n"
                "import json, pathlib, sys\n"
                "if '--schema' in sys.argv:\n"
                "    print(json.dumps({'properties': {'schema_version': {'const': '1.4.0'}}}))\n"
                "else:\n"
                "    output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
                "    output.write_text(json.dumps({'schema_version': '1.4.0', "
                "'components': [], 'nets': {}, 'bom': [], 'findings': []}))\n"
                "    (output.parent / 'surprise.tmp').write_text('unexpected')\n"
                "    (output.parent / 'surprise-dir').mkdir()\n"
            )
            output = Path(tmp) / "analysis.json"
            diagnostics = {"commands": []}
            old = os.environ.get("KICAD_HAPPY_DIR")
            os.environ["KICAD_HAPPY_DIR"] = str(root)
            try:
                result = hw._run_analyzer(output, diagnostics)
            finally:
                if old is None:
                    os.environ.pop("KICAD_HAPPY_DIR", None)
                else:
                    os.environ["KICAD_HAPPY_DIR"] = old

        self.assertIsNone(result)
        self.assertEqual(
            sorted(
                [
                    str(output.parent / "surprise-dir"),
                    str(output.parent / "surprise.tmp"),
                ]
            ),
            diagnostics["commands"][1]["unexpected_outputs"],
        )

    def test_malformed_analysis_collections_raise_config_error(self):
        valid = analysis()
        malformed = [
            {**valid, "components": {}},
            {**valid, "components": [None]},
            {**valid, "bom": {}},
            {**valid, "bom": [None]},
            {**valid, "findings": {}},
            {**valid, "findings": [None]},
            {**valid, "nets": []},
            {**valid, "nets": {"SIG": []}},
            {**valid, "nets": {"SIG": {"pins": {}}}},
            {**valid, "nets": {"SIG": {"pins": [None]}}},
        ]

        for index, data in enumerate(malformed):
            with self.subTest(index=index):
                with self.assertRaises(hw.ConfigError):
                    hw.validate_analysis(data, Path("malformed.json"))

    def test_malformed_nested_collections_report_exact_field_path(self):
        cases = []

        data = analysis()
        data["bom"][0]["references"] = 1
        cases.append(("bom[0].references", data))

        data = analysis()
        data["bom"][0]["references"] = [1]
        cases.append(("bom[0].references[0]", data))

        for field in ("components", "nets", "pins"):
            data = analysis()
            data["findings"][0][field] = 1
            cases.append((f"findings[0].{field}", data))

            data = analysis()
            data["findings"][0][field] = [1]
            cases.append((f"findings[0].{field}[0]", data))

        data = analysis()
        data["nets"]["SIG"]["pins"] = [1]
        cases.append(("nets['SIG'].pins[0]", data))

        for path, malformed in cases:
            with self.subTest(path=path):
                with self.assertRaises(hw.ConfigError) as caught:
                    hw.validate_analysis(malformed, Path("malformed.json"))
                self.assertIn(path, str(caught.exception))

    def test_incompatible_schema_probe_diagnostic_survives_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "skill"
            script = root / "scripts" / "analyze_schematic.py"
            script.parent.mkdir(parents=True)
            script.write_text(
                "#!/usr/bin/env python3\n"
                "import json\n"
                "print(json.dumps({'properties': {'schema_version': {'const': '1.3.0'}}}))\n"
            )
            diagnostics = {"commands": []}
            old = os.environ.get("KICAD_HAPPY_DIR")
            os.environ["KICAD_HAPPY_DIR"] = str(root)
            try:
                result = hw._run_analyzer(Path(tmp) / "analysis.json", diagnostics)
            finally:
                if old is None:
                    os.environ.pop("KICAD_HAPPY_DIR", None)
                else:
                    os.environ["KICAD_HAPPY_DIR"] = old

        self.assertIsNone(result)
        self.assertEqual(1, len(diagnostics["commands"]))
        self.assertEqual("--schema", diagnostics["commands"][0]["args"][-1])
        self.assertIn("v2.2.0", diagnostics["analyzer_error"])

    def test_missing_analyzer_has_exact_pinned_recovery_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(hw.ConfigError) as caught:
                hw.probe_analyzer(Path(tmp))

        message = str(caught.exception)
        self.assertIn("--ref v2.2.0", message)
        self.assertIn("--repo aklofas/kicad-happy", message)
        self.assertIn("--path skills/kicad", message)
        self.assertIn("install-skill-from-github.py", message)
        self.assertIn("move or remove", message.lower())

    def test_incompatible_analyzer_schema_has_pinned_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "scripts" / "analyze_schematic.py"
            script.parent.mkdir()
            script.write_text(
                "#!/usr/bin/env python3\n"
                "import json\n"
                "print(json.dumps({'properties': {'schema_version': {'const': '1.3.9'}}}))\n"
            )
            script.chmod(script.stat().st_mode | stat.S_IXUSR)

            with self.assertRaises(hw.ConfigError) as caught:
                hw.probe_analyzer(root)

        self.assertIn("schema 1.4", str(caught.exception))
        self.assertIn("v2.2.0", str(caught.exception))

    def test_process_abort_and_missing_outputs_remain_in_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "never-created.txt"
            result = hw.run_command(
                ["python3", "-c", "import os, signal; os.kill(os.getpid(), signal.SIGTERM)"],
                expected_outputs=[missing],
            )

        self.assertEqual(-15, result["returncode"])
        self.assertEqual("SIGTERM", result["signal"])
        self.assertIn(str(missing), result["missing_outputs"])
        self.assertIn("stdout", result)
        self.assertIn("stderr", result)

    def test_success_without_expected_output_is_still_diagnostic_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.txt"
            result = hw.run_command(
                ["python3", "-c", "print('ran but wrote nothing')"],
                expected_outputs=[missing],
            )

        self.assertEqual(0, result["returncode"])
        self.assertEqual([str(missing)], result["missing_outputs"])
        self.assertIn("ran but wrote nothing", result["stdout"])

    def test_unexpected_output_is_a_tooling_failure(self):
        result = {
            "returncode": 0,
            "missing_outputs": [],
            "unexpected_outputs": ["surprise.txt"],
        }

        self.assertTrue(hw._command_tooling_failure(result))


class VerifyLogicTests(unittest.TestCase):
    def test_pcb_drift_is_design_regression(self):
        self.assertEqual(0, hw.pcb_drift_exit("abc", "abc"))
        self.assertEqual(1, hw.pcb_drift_exit("abc", "def"))

    def test_new_deterministic_error_blocks_but_baseline_and_warnings_do_not(self):
        before = hw.canonicalize_analysis(
            analysis(findings=[finding("baseline", severity="error")])
        )
        after = hw.canonicalize_analysis(
            analysis(
                findings=[
                    finding("baseline", severity="error"),
                    finding("warning", severity="warning"),
                    finding("heuristic", severity="error", confidence="heuristic"),
                    finding("blocking", severity="error", confidence="deterministic"),
                ]
            )
        )
        delta = hw.semantic_diff(before, after)

        self.assertEqual(["blocking"], hw.new_blocking_finding_ids(delta))

    def test_finding_transition_to_deterministic_error_blocks(self):
        before = hw.canonicalize_analysis(
            analysis(
                findings=[
                    finding("warning", severity="warning", confidence="deterministic"),
                    finding("heuristic", severity="error", confidence="heuristic"),
                ]
            )
        )
        after = hw.canonicalize_analysis(
            analysis(
                findings=[
                    finding("warning", severity="error", confidence="deterministic"),
                    finding("heuristic", severity="error", confidence="deterministic"),
                ]
            )
        )

        delta = hw.semantic_diff(before, after)

        self.assertEqual(
            ["heuristic", "warning"], hw.new_blocking_finding_ids(delta)
        )


class FastSessionWorkflowTests(unittest.TestCase):
    def test_inspect_component_net_pin_and_changes_have_stable_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_root = Path(tmp) / "cache"
            session = "inspect"
            directory = cache_root / session
            directory.mkdir(parents=True)
            write_ready_session(directory, session, hw._source_hashes())
            current = current_result()
            output = io.StringIO()
            with patch.object(hw, "CACHE_ROOT", cache_root), patch.object(
                hw, "_compute_current", return_value=current
            ) as compute, redirect_stdout(output):
                self.assertEqual(
                    0,
                    hw.command_inspect(
                        session, "component", ["R1"], json_output=True, force=True
                    ),
                )
            payload = json.loads(output.getvalue())

        self.assertEqual("component", payload["target"])
        self.assertEqual("R1", payload["component"]["reference"])
        self.assertEqual(
            {"GND", "SIG"}, {item["net"] for item in payload["component"]["pins"]}
        )
        self.assertIn("properties", payload["component"])
        self.assertIn("findings", payload)
        self.assertIn("changes", payload)
        self.assertTrue(compute.call_args.kwargs["force"])

        net_payload = hw._net_inspection(current, "SIG", session)
        pin_payload = hw._pin_inspection(current, "R1", "1", session)
        changes_payload = hw._changes_inspection(current, session)
        self.assertEqual(["R1", "R2"], [item["reference"] for item in net_payload["components"]])
        self.assertEqual("SIG", pin_payload["pin"]["net"])
        self.assertEqual(current["delta"], changes_payload["changes"])

    def test_inspect_missing_identifiers_are_actionable(self):
        current = current_result()
        for callback, text in (
            (lambda: hw._component_inspection(current, "R99", "inspect"), "component not found: R99"),
            (lambda: hw._net_inspection(current, "MISSING", "inspect"), "net not found: MISSING"),
            (lambda: hw._pin_inspection(current, "R1", "99", "inspect"), "pin not found: R1.99"),
        ):
            with self.subTest(text=text), self.assertRaises(hw.ConfigError) as caught:
                callback()
            self.assertEqual(text, str(caught.exception))

    def test_valid_analysis_cache_reuses_and_force_or_corruption_refreshes(self):
        raw = analysis()
        calls = []

        def fake_analyzer(output, diagnostics):
            calls.append(output)
            hw.write_json(output, raw)
            return raw

        fingerprint = {"digest": "fingerprint", "inputs": {"schematic": "one"}}
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            hw, "_run_analyzer", side_effect=fake_analyzer
        ):
            directory = Path(tmp) / "session"
            first, first_reused = hw._cached_analysis(directory, fingerprint, {"commands": []}, force=False)
            second, second_reused = hw._cached_analysis(directory, fingerprint, {"commands": []}, force=False)
            hw.write_json(directory / "analysis-cache" / "fingerprint" / "complete.json", {"bad": True})
            third, third_reused = hw._cached_analysis(directory, fingerprint, {"commands": []}, force=False)
            fourth, fourth_reused = hw._cached_analysis(directory, fingerprint, {"commands": []}, force=True)

        self.assertEqual(raw, first)
        self.assertEqual(raw, second)
        self.assertEqual(raw, third)
        self.assertEqual(raw, fourth)
        self.assertFalse(first_reused)
        self.assertTrue(second_reused)
        self.assertFalse(third_reused)
        self.assertFalse(fourth_reused)
        self.assertEqual(3, len(calls))

    def test_changed_footprint_parser_has_separate_validated_cache(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            library = root / "Library.pretty"
            library.mkdir()
            (library / "changed.kicad_mod").write_text("(footprint changed)")
            cli = root / "kicad-cli"
            cli.write_text("#!/bin/sh\n")
            cli.chmod(cli.stat().st_mode | stat.S_IXUSR)
            footprints = hw.hash_footprints(library)
            changes = {"added": ["changed.kicad_mod"], "modified": [], "deleted": []}

            def fake_command(args, *, cwd=None, expected_outputs=()):
                calls.append(list(args))
                for output in expected_outputs:
                    Path(output).parent.mkdir(parents=True, exist_ok=True)
                    Path(output).write_text("(footprint parsed)")
                return {
                    "returncode": 0,
                    "missing_outputs": [],
                    "unexpected_outputs": [],
                    "stdout": "",
                    "stderr": "",
                }

            with patch.object(hw, "FOOTPRINT_LIBRARY", library), patch.object(
                hw, "kicad_cli_path", return_value=cli
            ), patch.object(hw, "run_command", side_effect=fake_command):
                directory = root / "session"
                first = hw._cached_changed_footprints(
                    directory, footprints, changes, {"commands": []}, force=False
                )
                second = hw._cached_changed_footprints(
                    directory, footprints, changes, {"commands": []}, force=False
                )
                forced = hw._cached_changed_footprints(
                    directory, footprints, changes, {"commands": []}, force=True
                )

        self.assertEqual((True, False), first)
        self.assertEqual((True, True), second)
        self.assertEqual((True, False), forced)
        self.assertEqual(2, len(calls))

    def test_session_lock_rejects_overlapping_operations(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "session"
            directory.mkdir()
            with hw.session_operation_lock(directory, "session"):
                with self.assertRaises(hw.ConfigError) as caught:
                    with hw.session_operation_lock(directory, "session"):
                        pass

        self.assertIn("session is busy", str(caught.exception))

    def test_quick_stops_for_pcb_drift_before_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            schematic = root / "board.kicad_sch"
            pcb = root / "board.kicad_pcb"
            project = root / "board.kicad_pro"
            library = root / "Library.pretty"
            cache_root = root / "cache"
            for path in (schematic, pcb, project):
                path.write_text(path.name)
            library.mkdir()
            sources = {
                "schematic": hw.sha256_file(schematic),
                "pcb": hw.sha256_file(pcb),
                "project": hw.sha256_file(project),
            }
            session = "pcb-drift"
            directory = cache_root / session
            directory.mkdir(parents=True)
            write_ready_session(directory, session, sources)
            pcb.write_text("changed pcb")
            with patch.object(hw, "SCHEMATIC", schematic), patch.object(
                hw, "PCB", pcb
            ), patch.object(hw, "PROJECT", project), patch.object(
                hw, "FOOTPRINT_LIBRARY", library
            ), patch.object(hw, "CACHE_ROOT", cache_root), patch.object(
                hw, "_compute_current", side_effect=AssertionError("analysis started")
            ):
                with redirect_stderr(io.StringIO()):
                    self.assertEqual(1, hw.command_quick(session))

    def test_old_session_metadata_has_clean_and_preflight_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "old"
            directory.mkdir()
            with self.assertRaises(hw.ConfigError) as caught:
                hw._load_baseline(directory, "old")

        self.assertIn("clean old", str(caught.exception))
        self.assertIn("preflight old", str(caught.exception))

    def test_corrupt_session_metadata_has_clean_and_preflight_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "broken"
            directory.mkdir()
            (directory / "session.json").write_text("{")
            with self.assertRaises(hw.ConfigError) as caught:
                hw._load_baseline(directory, "broken")

        self.assertIn("metadata is corrupt", str(caught.exception))
        self.assertIn("clean broken", str(caught.exception))
        self.assertIn("preflight broken", str(caught.exception))

    def test_analyzer_and_cli_discovery_orders_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shared = root / "shared"
            codex = root / "codex"
            claude = root / "claude"
            codex_script = codex / "skills" / "kicad" / "scripts" / "analyze_schematic.py"
            claude_script = claude / "skills" / "kicad" / "scripts" / "analyze_schematic.py"
            codex_script.parent.mkdir(parents=True)
            claude_script.parent.mkdir(parents=True)
            codex_script.write_text("# analyzer")
            claude_script.write_text("# analyzer")
            environment = {
                "AGENTS_HOME": str(shared),
                "CODEX_HOME": str(codex),
                "CLAUDE_CONFIG_DIR": str(claude),
                "KICAD_HAPPY_DIR": "",
            }
            with patch.dict(os.environ, environment, clear=False):
                self.assertEqual(codex / "skills" / "kicad", hw.resolve_analyzer_root())
                codex_script.unlink()
                self.assertEqual(claude / "skills" / "kicad", hw.resolve_analyzer_root())
            cli = root / "kicad-cli"
            cli.write_text("#!/bin/sh\n")
            cli.chmod(cli.stat().st_mode | stat.S_IXUSR)
            with patch.dict(os.environ, {"KICAD_CLI": ""}, clear=False), patch(
                "scripts.hw.shutil.which", return_value=str(cli)
            ):
                self.assertEqual(cli, hw.kicad_cli_path())
            with patch.dict(os.environ, {"KICAD_CLI": str(root / "missing")}, clear=False):
                with self.assertRaises(hw.ConfigError) as caught:
                    hw.kicad_cli_path()

        self.assertIn("KICAD_CLI is invalid", str(caught.exception))


class DeltaOutputTests(unittest.TestCase):
    def test_compact_output_names_each_actual_change(self):
        delta = {
            "components": {
                "added": ["C1"],
                "removed": ["R9"],
                "changed": [{"reference": "R1", "fields": {"value": ["1k", "2k"]}}],
            },
            "nets": {"added": [], "removed": []},
            "net_renames": [],
            "pin_net_changes": [],
            "no_connects": {
                "added": [["R2", "1", "A"]],
                "removed": [["R3", "2", "B"]],
            },
            "bom_groups": {
                "added": [{"references": ["C1"], "value": "100n", "footprint": "C_0603"}],
                "removed": [{"references": ["R9"], "value": "10k", "footprint": "R_0603"}],
                "changed": [{"identity": "group-r1", "before": {}, "after": {}}],
            },
            "findings": {
                "added": [{"identity": "finding-add"}],
                "removed": [{"identity": "finding-remove"}],
                "changed": [{"identity": "finding-change"}],
            },
        }
        footprints = {
            "added": ["new.kicad_mod"],
            "modified": ["changed.kicad_mod"],
            "deleted": ["old.kicad_mod"],
        }

        output = io.StringIO()
        with redirect_stdout(output):
            hw._print_delta(delta, footprints)
        text = output.getvalue()

        for expected in (
            "components added: C1",
            "components removed: R9",
            "components changed: R1",
            "no-connect added: R2.1.A",
            "no-connect removed: R3.2.B",
            "bom added: C1",
            "bom removed: R9",
            "bom changed: group-r1",
            "findings added: finding-add",
            "findings removed: finding-remove",
            "findings changed: finding-change",
            "footprints added: new.kicad_mod",
            "footprints modified: changed.kicad_mod",
            "footprints deleted: old.kicad_mod",
        ):
            self.assertIn(expected, text)


class LiveReceiverRailTopologyTests(unittest.TestCase):
    def test_live_analyzer_preserves_receiver_rail_membership(self):
        try:
            analyzer = hw.probe_analyzer(hw.resolve_analyzer_root())["script"]
        except hw.ConfigError as exc:
            self.skipTest(f"KiCad analyzer unavailable: {exc}")
        schematic = hw.SCHEMATIC
        if not schematic.is_file():
            self.skipTest(f"schematic unavailable: {schematic}")

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "analysis.json"
            completed = subprocess.run(
                ["python3", str(analyzer), str(schematic), "--output", str(output), "--compact"],
                cwd=hw.REPO_ROOT,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0 or not output.is_file():
                self.fail(
                    f"live analyzer failed ({completed.returncode}): "
                    f"{completed.stdout}\n{completed.stderr}"
                )
            state = hw.canonicalize_analysis(json.loads(output.read_text()))

        for reference in ("Q3", "R11", "R6", "C3", "U2"):
            self.assertIn(reference, state["components"])
        named_nets = {item["name"] for item in state["nets"]}
        self.assertTrue({"ir_en", "ir_vdd", "+3.3V", "GND"}.issubset(named_nets))
        named_members = {
            item["name"]: {member[0] for member in item["members"]}
            for item in state["nets"]
        }
        self.assertTrue({"Q3", "R11", "U1"}.issubset(named_members["ir_en"]))
        self.assertTrue({"Q3", "R6"}.issubset(named_members["ir_vdd"]))
        unnamed_member_refs = [
            {member[0] for member in item["members"]}
            for item in state["nets"]
            if item["name"] == ""
        ]
        self.assertTrue(
            any({"R6", "C3", "U2"}.issubset(refs) for refs in unnamed_member_refs),
            unnamed_member_refs,
        )


if __name__ == "__main__":
    unittest.main()
