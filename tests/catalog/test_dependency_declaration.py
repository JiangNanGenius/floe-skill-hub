#!/usr/bin/env python3
"""Mirror-accuracy and gate tests for the dependency-declaration v1 contract.

The native strict decoder (FloeAgent/Sources/FloeSkills/SkillDependency.swift,
sha256 da8e651e…) is the authority; scripts/dependency_declaration.py must
accept nothing it rejects. These tests pin that parity with a
positive/negative corpus per grammar, the structural decoder rules, the
package cross-validation, and the two producer gates (strict decode +
minimumAppVersion raise). The real frozen runtime descriptor bytes are reused
as read-only data for the runtimeComponent cross-validation positive; nothing
is executed.

2026-10-27 PROBE CORRECTION: expectations were fixed against an executable
component probe of the UNCHANGED native files (Xcode 27.1 host swiftc; the
probe copy differed by one compile-plumbing `try` token; classifiers
byte-identical), not against assumptions. Digit guards for pip/apt versions,
the whole-name 128-byte font budget, Foundation Cc∪Cf control characters for
purpose, the 65_536-byte declaration bound applied BEFORE parsing, and the
native JSON layer's refusal of unpaired surrogate escapes are pinned below.
The remaining intentional stricter choices (ASCII profile ids, literal
integer schemaVersion, canonical npm core) are asserted here AND itemised in
docs/DEPENDENCY-V1-CONTRACT.md as SAFE-AUTHORING SUBSETS.
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
        # Probe-pinned (native isValidPipVersion): the tail pattern alone is
        # not enough — at least one ASCII digit must be present, so the old
        # floating aliases never masquerade as exact pins.
        for bad in ("", "a b", "1.0|2", "1.0 " * 30, "latest", "stable",
                    "*", "**", "!"):
            self.assertFalse(dd.is_valid_pip_version(bad), bad)
        self.assertFalse(dd.is_valid_pip_version("1" + "2" * 128))
        # 128-byte boundary with a digit: accepted; one more byte: refused.
        self.assertTrue(dd.is_valid_pip_version("x" * 127 + "9"))
        self.assertFalse(dd.is_valid_pip_version("x" * 128 + "9"))

    def test_apt_name(self):
        for ok in ("python3-scipy", "fonts-noto-cjk", "a" * 128):
            self.assertTrue(dd.is_valid_apt_name(ok), ok)
        for bad in ("Python", "a b", "-a", "A"):
            self.assertFalse(dd.is_valid_apt_name(bad), bad)

    def test_apt_version(self):
        # Native requires: optional pure-digit epoch before the FIRST ':',
        # and a digit inside the BODY (after the epoch). Exact Debian pins
        # like the shipped CJK/font ones always carry body digits.
        for ok in ("1.15.3-1", "1:20240730+repack1-1", "25.03.0-5+deb13u4",
                   "3.10.1+dfsg1-4", "2.15.0-2.3", "0", "1:2:3.0", "2:0a",
                   "01:1.0", "1:1.0~rc", "a" * 127 + "1"):
            self.assertTrue(dd.is_valid_apt_version(ok), ok)
        # Probe-pinned corrections: "a" * 128 has no digit and the native
        # decoder REFUSES it (the old test expected True wrongly); floating
        # aliases are refused with or without an epoch.
        for bad in ("1:", ":", "-1", "1:é", "", "latest", "stable", "1:latest",
                    "1:stable", "a" * 128, ":", "1::2", "1.0_2"):
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
        # "-1.0.0" is a documented SAFE-AUTHORING SUBSET refusal: the native
        # split(omittingEmptySubsequences) tolerates a leading-dash core
        # (probe-verified native=accept); the producer gate and the published
        # schema require the canonical X.Y.Z start. "" is refused here while
        # the native function would trap indexing an empty split (native-side
        # flaw owned by Main; recorded in the parity report).
        for bad in ("1.2", "1.2.3.4", "1.2.3+build", "1.0.0-", "1.0.0-a b",
                    "", "1.2.x", "-1.0.0"):
            self.assertFalse(dd.is_valid_npm_version(bad), bad)
        self.assertFalse(dd.is_valid_npm_version("1.2.3-" + "a" * 61))

    def test_font_identity(self):
        for ok in ("fonts-noto-cjk", "fonts-dejavu-core",
                   # Probe-pinned native oddity: isValidFontIdentity is
                   # hasPrefix("fonts-") AND isValidAptName over the WHOLE
                   # name, and the bare prefix passes that apt grammar
                   # ('f' start, rest in charset). Grammar-valid is NOT a
                   # packaging claim — a real package needs a real identity.
                   "fonts-",
                   # 128 bytes TOTAL including the prefix:
                   "fonts-" + "n" * 122):
            self.assertTrue(dd.is_valid_font_identity(ok), ok)
        # The old FONT_IDENTITY regex gave the suffix a fresh 128-byte
        # budget (total up to 134) and accepted names native refuses.
        for bad in ("noto", "Fonts-x", "fonts-a b", "fonts-" + "n" * 123,
                    "fonts-a!", "fonts"):
            self.assertFalse(dd.is_valid_font_identity(bad), bad)

    def test_profile_id(self):
        for ok in ("linux-guest", "cjk-rendering", "a" * 64):
            self.assertTrue(dd.is_valid_profile_id(ok), ok)
        # "café" / "a٣" are probe-verified NATIVE-valid (SkillIdentifier uses
        # Unicode isLetter/isLowercase/isNumber). The mirror keeps the ASCII
        # slug as a documented SAFE-AUTHORING SUBSET — stricter, never
        # looser, itemised in docs/DEPENDENCY-V1-CONTRACT.md.
        for bad in ("-guest", "Linux", "a--b", "guest-", "", "a" * 65,
                    "café", "a٣", "a.b"):
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
        for ok in ("Read and merge PDF pages.", "\u4e2d\u6587\u8bf4\u660e",
                   "x" * 200,
                   # probe-pinned native accept sides:
                   "a\u00a0b",        # interior NBSP (only EDGE whitespace trims)
                   "a\u2028b",        # interior Zl (Foundation control == Cc+Cf only)
                   "\u00e9" * 100):   # exactly 200 UTF-8 bytes
            self.assertTrue(dd.is_valid_purpose(ok), ok[:20])
        # Probe-pinned Foundation facts: controlCharacters == Cc + Cf (so
        # ZWSP, soft hyphen, U+061C, U+2060 are refused — the old Cc-only
        # screen UNDER-refused), and Foundation trims NBSP/NEL at the edges.
        for bad in ("", " lead", "trail ", "a\tb", "a\nb", "x" * 201,
                    "a\u200bb", "a\u00adb", "a\u061cb", "a\u2060b",
                    "\u00a0abc", "abc\u00a0", "\u0085abc", "abc\u0085",
                    "a\u001fb", "a\u0000b", "a\u007fb", "a\u0080b",
                    "\u00e9" * 101):
            self.assertFalse(dd.is_valid_purpose(bad), repr(bad[:12]))


class DeclarationBoundTests(unittest.TestCase):
    """The native byte bound applied BEFORE parsing, and JSON-layer refusals."""

    def _doc_bytes(self, total):
        base = json.dumps(envelope([pip_req()])).encode()
        assert len(base) < total <= 65_537
        return base + b" " * (total - len(base))

    def test_exactly_65536_accepted(self):
        decl = dd.parse_declaration(self._doc_bytes(65_536))
        self.assertEqual(decl["schemaVersion"], 1)

    def test_65537_rejected_before_parse(self):
        with self.assertRaises(hubcore.HubError) as ctx:
            dd.parse_declaration(self._doc_bytes(65_537))
        self.assertIn("65536-byte bound", str(ctx.exception))

    def test_oversized_str_input_rejected_fail_closed(self):
        # No unbounded UTF-8 allocation for hostile string input.
        with self.assertRaises(hubcore.HubError):
            dd.parse_declaration("[" + "1" * (dd.MAX_DECLARATION_BYTES + 1))

    def test_lone_surrogate_escape_refused_not_crash(self):
        # Probe: native JSONSerialization refuses the whole document
        # ("not valid JSON"); the mirror must fail closed as HubError, never
        # as UnicodeEncodeError.
        hostile = json.dumps(envelope([dict(pip_req(), purpose="\ud800x")]))
        self.assertIn("\\ud800", hostile)
        with self.assertRaises(hubcore.HubError):
            dd.parse_declaration(hostile.encode())
        with self.assertRaises(hubcore.HubError):
            dd.parse_declaration(hostile)

    def test_non_utf8_and_bad_json_still_fail_closed(self):
        with self.assertRaises(hubcore.HubError):
            dd.parse_declaration(b"\xff\xfe")
        with self.assertRaises(hubcore.HubError):
            dd.parse_declaration(b"{not json")


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
