#!/usr/bin/env python3
"""Mirror-accuracy and gate tests for the dependency-declaration v1 contract.

The native strict decoder (FloeAgent/Sources/FloeSkills/SkillDependency.swift)
is the authority; scripts/dependency_declaration.py must accept exactly what it
accepts and reject what it rejects. These tests pin that parity with a
positive/negative corpus per grammar, the structural decoder rules, the package
cross-validation, and the two producer gates (strict decode + minimumAppVersion
raise). The real frozen runtime descriptor bytes are reused as read-only data
for the runtimeComponent cross-validation positive; nothing is executed.
"""
import json
import pathlib
import shutil
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE / "scripts"))
import dependency_declaration as dd  # noqa: E402
import hubcore  # noqa: E402
import runtime_dependency  # noqa: E402

REAL_DESCRIPTOR = (HERE / "sources" / "impeccable" / "references"
                   / "engine-dependency.json").read_bytes()


def req(kind, **kwargs):
    base = {"kind": kind, "purpose": "Exact pin for the worked example.",
            "required": True}
    base.update(kwargs)
    return base


def envelope(requirements, profile_id="linux-guest", arch=None):
    return {
        "schemaVersion": 1,
        "profiles": [{
            "id": profile_id,
            "target": {"os": "linux",
                       "architectures": ["any"] if arch is None else arch},
            "requirements": requirements,
        }],
    }


def pip_req(name="pypdf", version="5.4.0", lockfile=None):
    kwargs = {"name": name, "version": version}
    if lockfile is not None:
        kwargs["lockfile"] = lockfile
    return req("pip", **kwargs)


class PatternParityTests(unittest.TestCase):
    """Character-level parity with the native ASCII pattern sets."""

    def test_pip_name(self):
        for ok in ("pypdf", "1abc", "a" * 128, "matplotlib", "charset-normalizer"):
            self.assertTrue(dd.is_valid_pip_name(ok), ok)
        for bad in ("-a", "a b", "a[b]", "", "a" * 129, "é"):
            self.assertFalse(dd.is_valid_pip_name(bad), bad)

    def test_pip_version(self):
        for ok in ("5.4.0", "1.0rc1", "1!2.0", "2.0+local", "1.2.*", "0.0.0"):
            self.assertTrue(dd.is_valid_pip_version(ok), ok)
        for bad in ("", "a b", "1.0|2", "1.0 " * 30):
            self.assertFalse(dd.is_valid_pip_version(bad), bad)
        self.assertFalse(dd.is_valid_pip_version("1" + "2" * 128))

    def test_apt_name(self):
        for ok in ("python3-scipy", "fonts-noto-cjk", "a" * 128):
            self.assertTrue(dd.is_valid_apt_name(ok), ok)
        for bad in ("Python", "a b", "-a", "A"):
            self.assertFalse(dd.is_valid_apt_name(bad), bad)

    def test_apt_version(self):
        for ok in ("1.15.3-1", "1:20240730+repack1-1", "25.03.0-5+deb13u4",
                   "3.10.1+dfsg1-4", "2.15.0-2.3", "a" * 128):
            self.assertTrue(dd.is_valid_apt_version(ok), ok)
        for bad in ("1:", ":", "-1", "1:é", ""):
            self.assertFalse(dd.is_valid_apt_version(bad), bad)
        self.assertFalse(dd.is_valid_apt_version("1:" + "2" * 129))

    def test_npm_name(self):
        for ok in ("typescript", "@scope/validator", "@s/v", "a" * 128):
            self.assertTrue(dd.is_valid_npm_name(ok), ok)
        for bad in ("@scope/", "@Scope/x", "a b", "A/B", "@"):
            self.assertFalse(dd.is_valid_npm_name(bad), bad)

    def test_npm_version(self):
        for ok in ("5.9.3", "1.2.0", "1.0.0-alpha.1", "1.02.3"):
            self.assertTrue(dd.is_valid_npm_version(ok), ok)
        for bad in ("1.2", "1.2.3.4", "1.2.3+build", "1.0.0-", "1.0.0-a b",
                    "", "1.2.x"):
            self.assertFalse(dd.is_valid_npm_version(bad), bad)
        self.assertFalse(dd.is_valid_npm_version("1.2.3-" + "a" * 61))

    def test_font_identity(self):
        for ok in ("fonts-noto-cjk", "fonts-dejavu-core"):
            self.assertTrue(dd.is_valid_font_identity(ok), ok)
        for bad in ("noto", "fonts-", "Fonts-x", "fonts-a b"):
            self.assertFalse(dd.is_valid_font_identity(bad), bad)

    def test_profile_id(self):
        for ok in ("linux-guest", "cjk-rendering", "a" * 64):
            self.assertTrue(dd.is_valid_profile_id(ok), ok)
        for bad in ("-guest", "Linux", "a--b", "guest-", "", "a" * 65):
            self.assertFalse(dd.is_valid_profile_id(bad), bad)

    def test_lock_path(self):
        for ok in ("references/requirements.lock.txt", "references/a.txt",
                   "references/locks/prod-v2.txt"):
            self.assertTrue(dd.is_package_local_lock_path(ok), ok)
        for bad in ("requirements.txt", "references/../x.txt",
                    "references/x/../y.txt", "references/foo bar.txt",
                    "references/x.TXT", "references/",
                    "references/" + "a" * 250 + ".txt"):
            self.assertFalse(dd.is_package_local_lock_path(bad), bad)
        # "references/.txt" is accepted by the native decoder (the segment
        # ".txt" is not empty/dot/dot-dot); the mirror stays faithful.
        self.assertTrue(dd.is_package_local_lock_path("references/.txt"))

    def test_purpose(self):
        for ok in ("Read and merge PDF pages.", "中文说明", "x" * 200):
            self.assertTrue(dd.is_valid_purpose(ok), ok[:20])
        for bad in ("", " lead", "trail ", "a\tb", "a\nb", "x" * 201):
            self.assertFalse(dd.is_valid_purpose(bad), bad)


class DecodeTests(unittest.TestCase):
    def test_minimal_positive(self):
        decl = dd.validate_declaration(envelope([pip_req()]))
        self.assertEqual(decl["schemaVersion"], 1)
        self.assertEqual(len(decl["profiles"]), 1)

    def test_schema_version_strict_integer_one(self):
        for bad_version in ("1", True, 1.0, 0, 2, -1):
            doc = envelope([pip_req()])
            doc["schemaVersion"] = bad_version
            with self.assertRaises(hubcore.HubError):
                dd.validate_declaration(doc)

    def test_exact_top_keys(self):
        doc = envelope([pip_req()])
        doc["extra"] = 1
        with self.assertRaises(hubcore.HubError):
            dd.validate_declaration(doc)
        del doc["extra"]
        del doc["profiles"]
        with self.assertRaises(hubcore.HubError):
            dd.validate_declaration(doc)

    def test_empty_profiles_and_requirements_rejected(self):
        with self.assertRaises(hubcore.HubError):
            dd.validate_declaration({"schemaVersion": 1, "profiles": []})
        doc = envelope([])
        with self.assertRaises(hubcore.HubError):
            dd.validate_declaration(doc)

    def test_profile_and_requirement_limits(self):
        many_profiles = {"schemaVersion": 1, "profiles": [
            {"id": f"p{i}", "target": {"os": "linux", "architectures": ["any"]},
             "requirements": [pip_req()]} for i in range(9)]}
        with self.assertRaises(hubcore.HubError):
            dd.validate_declaration(many_profiles)
        many_reqs = envelope([pip_req(f"p{i}", f"1.0.{i}") for i in range(33)])
        with self.assertRaises(hubcore.HubError):
            dd.validate_declaration(many_reqs)

    def test_uniqueness(self):
        dup_profile = {"schemaVersion": 1, "profiles": [
            {"id": "same", "target": {"os": "linux", "architectures": ["any"]},
             "requirements": [pip_req()]},
            {"id": "same", "target": {"os": "linux", "architectures": ["any"]},
             "requirements": [pip_req()]}]}
        with self.assertRaises(hubcore.HubError):
            dd.validate_declaration(dup_profile)
        with self.assertRaises(hubcore.HubError):
            dd.validate_declaration(envelope([pip_req(), pip_req()]))

    def test_target_rules(self):
        doc = envelope([pip_req()], arch=[])
        with self.assertRaises(hubcore.HubError):
            dd.validate_declaration(doc)
        doc = envelope([pip_req()], arch=["sparc"])
        with self.assertRaises(hubcore.HubError):
            dd.validate_declaration(doc)
        doc = envelope([pip_req()], arch=["arm64", "arm64"])
        with self.assertRaises(hubcore.HubError):
            dd.validate_declaration(doc)

    def test_unknown_kind_and_unknown_fields(self):
        with self.assertRaises(hubcore.HubError):
            dd.validate_declaration(envelope([req("cargo", name="x", version="1")]))
        doc = envelope([req("apt", name="python3-scipy", version="1.15.3-1",
                            url="https://evil.example")])
        with self.assertRaises(hubcore.HubError):
            dd.validate_declaration(doc)

    def test_per_kind_key_sets(self):
        # pip without lockfile is fine; apt with a lockfile is not.
        dd.validate_declaration(envelope([pip_req()]))
        doc = envelope([req("apt", name="python3-scipy", version="1.15.3-1",
                            lockfile="references/x.txt")])
        with self.assertRaises(hubcore.HubError):
            dd.validate_declaration(doc)
        # npm name+version+purpose+required is the exact valid key set.
        dd.validate_declaration(envelope([req("npm", name="typescript",
                                              version="5.9.3")]))
        doc = envelope([req("npm", name="typescript")])
        with self.assertRaises(hubcore.HubError):
            dd.validate_declaration(doc)  # missing version
        doc = envelope([req("runtimeComponent",
                            componentDescriptorPath="references/other.json")])
        with self.assertRaises(hubcore.HubError):
            dd.validate_declaration(doc)

    def test_required_must_be_boolean(self):
        doc = envelope([pip_req()])
        doc["profiles"][0]["requirements"][0]["required"] = "yes"
        with self.assertRaises(hubcore.HubError):
            dd.validate_declaration(doc)
        doc = envelope([pip_req()])
        doc["profiles"][0]["requirements"][0]["required"] = 1
        with self.assertRaises(hubcore.HubError):
            dd.validate_declaration(doc)

    def test_parse_bytes(self):
        decl = dd.parse_declaration(json.dumps(envelope([pip_req()])).encode())
        self.assertEqual(decl["profiles"][0]["id"], "linux-guest")
        with self.assertRaises(hubcore.HubError):
            dd.parse_declaration(b"\xff\xfe")
        with self.assertRaises(hubcore.HubError):
            dd.parse_declaration(b"{not json")


class CrossValidationTests(unittest.TestCase):
    def test_lock_must_exist_in_package(self):
        decl = dd.parse_declaration(json.dumps(
            envelope([pip_req(lockfile="references/requirements.lock.txt")])).encode())
        with self.assertRaises(hubcore.HubError):
            dd.cross_validate(decl, {})
        ok = dd.cross_validate(
            decl, {"references/requirements.lock.txt": b"sympy==1.14.0 sha256=...\n"})
        self.assertEqual(ok["profiles"][0]["requirements"][0]["lockfile"],
                         "references/requirements.lock.txt")

    def test_runtime_component_descriptor_gate(self):
        decl = dd.parse_declaration(json.dumps(envelope([
            req("runtimeComponent",
                componentDescriptorPath="references/engine-dependency.json"),
        ])).encode())
        with self.assertRaises(hubcore.HubError):
            dd.cross_validate(decl, {})
        with self.assertRaises(hubcore.HubError):
            dd.cross_validate(decl, {"references/engine-dependency.json": b"{}"})
        ok = dd.cross_validate(
            decl, {"references/engine-dependency.json": REAL_DESCRIPTOR})
        self.assertEqual(ok["profiles"][0]["requirements"][0]["kind"],
                         "runtimeComponent")

    def test_main_corrected_examples_validate(self):
        examples = HERE / "docs" / "dependency-examples"
        for example in sorted(examples.glob("*.json")):
            decl = dd.parse_declaration(example.read_bytes(), str(example))
            self.assertEqual(decl["schemaVersion"], 1, example.name)


class ProducerGateTests(unittest.TestCase):
    def _entry(self, minimum):
        return {"id": "dep-fixture", "versionTarget": "1.0.0",
                "minimumAppVersion": minimum, "upstream": None}

    def _files(self, declaration=None):
        files = {
            "SKILL.md": b"---\nname: dep-fixture\n"
                        b"description: Fixture skill for the gate tests.\n"
                        b"---\n# Fixture\n",
            "floe.json": json.dumps({
                "schemaVersion": 1, "id": "dep-fixture", "version": "1.0.0",
                "capabilities": ["workspace.read"], "tools": ["skill.read"],
                "platforms": ["linux"], "scriptRuntime": "none",
            }).encode(),
        }
        if declaration is not None:
            files["references/dependencies.json"] = json.dumps(declaration).encode()
        return files

    def test_no_declaration_skips_gate(self):
        self.assertIsNone(dd.assert_declaration_gates(self._entry(None),
                                                      self._files()))

    def test_minapp_gate(self):
        decl = envelope([pip_req()])
        for bad_minimum in (None, "1.7.59", "1.6.0"):
            with self.assertRaises(hubcore.HubError, msg=bad_minimum):
                dd.assert_declaration_gates(self._entry(bad_minimum),
                                            self._files(decl))
        for ok_minimum in ("1.7.60", "1.8.0"):
            out = dd.assert_declaration_gates(self._entry(ok_minimum),
                                              self._files(decl))
            self.assertIsNotNone(out)

    def test_invalid_declaration_fails_even_with_minapp(self):
        decl = envelope([req("cargo", name="x", version="1")])
        with self.assertRaises(hubcore.HubError):
            dd.assert_declaration_gates(self._entry("1.7.60"), self._files(decl))


class BuildOneIntegrationTests(unittest.TestCase):
    """End-to-end staged-source preflight through build_packages.build_one."""

    def setUp(self):
        self._tmp = pathlib.Path(tempfile.mkdtemp(prefix="hub-dep-test-"))
        self.root = self._tmp / "tree"
        (self.root / "sources" / "dep-fixture").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self._tmp)

    def _stage(self, declaration, minimum="1.7.60"):
        folder = self.root / "sources" / "dep-fixture"
        (folder / "SKILL.md").write_bytes(
            b"---\nname: dep-fixture\n"
            b"description: Fixture skill for the build gate tests.\n---\n# F\n")
        (folder / "floe.json").write_text(json.dumps({
            "schemaVersion": 1, "id": "dep-fixture", "version": "1.0.0",
            "capabilities": ["workspace.read"], "tools": ["skill.read"],
            "platforms": ["linux"], "scriptRuntime": "none"}))
        if declaration is not None:
            ref = folder / "references"
            ref.mkdir(exist_ok=True)
            (ref / "dependencies.json").write_text(json.dumps(declaration))
        entry = {"id": "dep-fixture", "versionTarget": "1.0.0",
                 "minimumAppVersion": minimum, "upstream": None,
                 "plannedRuntime": {"installPlatforms": ["ios"]}}
        import build_packages
        return build_packages.build_one("dep-fixture", entry, False, self.root)

    def test_build_and_rebuild_identical_with_declaration(self):
        decl = envelope([pip_req()])
        written = self._stage(decl)
        self.assertEqual(len(written), 1)
        first = (self.root / written[0]).read_bytes()
        written2 = self._stage(decl)  # immutable archive: nothing rewritten
        self.assertEqual(written2, [])
        self.assertEqual((self.root / written[0]).read_bytes(), first)

    def test_low_minapp_refused_at_build(self):
        with self.assertRaises(hubcore.HubError):
            self._stage(envelope([pip_req()]), minimum="1.7.59")

    def test_tampered_declaration_refused(self):
        decl = envelope([req("cargo", name="x", version="1")])
        with self.assertRaises(hubcore.HubError):
            self._stage(decl)


if __name__ == "__main__":
    unittest.main()
