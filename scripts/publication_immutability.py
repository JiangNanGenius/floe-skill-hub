#!/usr/bin/env python3
"""Publication-boundary immutability guard for signed channel feeds.

Implements the frozen publisher-CI rule from the author guide: an already
published Skill id+version is immutable — a publication that reuses an
existing (id, version) with a DIFFERENT package contentDigest is refused at
the publishing boundary, even when the publisher could produce a fresh valid
signature for the new bytes. The client-side receipt digest equality alone
cannot prove historical publication immutability, so the rule is enforced
HERE, not discovered at install time.

Trust model (by construction, fail closed):
  * the baseline is anchored to ACTUAL PUBLISHED HISTORY — never the caller's
    data checkout X (registry/ledger/reviews there are caller-replaceable),
    never catalog-advertised keys, never a local unsigned ledger;
  * a cumulative publication ledger (`catalog/publication-ledger.json`,
    tracked in the trusted tooling root T) records every publication run as
    {publication Y pin, channel, feedSha256, offers[{id, version,
    contentDigest}]}. Every row is verified at use time against the signed
    feed bytes at its pinned Y (single-object `git show` reads; no network):
    the Ed25519 signature must verify under the
    configured production trust, the feed sha256 must equal the row, and
    the complete offer set and every digest must match the feed — a caller can neither
    forge a row nor swap a digest;
  * the ledger is cumulative: versions later removed from the latest feed
    stay immutable through their retained rows, so "removed from the current
    feed, then reused with changed bytes" is still refused;
  * a bounded read of the two most recent ledger-changing commits prevents
    historical rows from being removed or rewritten; inherited Git redirects
    and replacement refs cannot substitute historical objects;
  * staleness fails closed: every offer in the independently pinned CURRENT feeds
    must be covered by the verified ledger with the equal digest. Tooling
    pinned before a publication (stale T/T3) therefore refuses instead of
    silently dropping history, and production history with a MISSING ledger
    never downgrades to "first publication";
  * per-channel identity is preserved (iOS/Android manifests may differ):
    the comparison key is (channel, id, version) -> contentDigest;
  * unchanged published bytes and genuinely new versions pass.

This module never writes, never signs or fetches. Ledger ancestry reads are
bounded to two ledger-changing commits. Preview/candidate builds are NOT compared (build_packages.py
already refuses same-version byte drift at the producer).
"""
import json
import os
import pathlib
import subprocess

import hubcore
import catalog_views as cv

REPO = pathlib.Path(__file__).resolve().parents[1]

LEDGER_REL = "catalog/publication-ledger.json"
LEDGER_SCHEMA_VERSION = 1
LEDGER_DESCRIPTION = (
    "Cumulative publication ledger of the Floe Skill Hub signed channel feeds. "
    "Each row records one publication commit Y, one channel, the SHA-256 of the "
    "signed feed bytes at that pin, and every packaged offer "
    "(id, version, contentDigest) it published. Rows are verified at use time "
    "against the signed bytes at their pin, so the ledger is an index of "
    "published history and never a source of trust by itself. It is cumulative: "
    "rows are never rewritten or removed when a version leaves the latest feed, "
    "because released bytes stay immutable forever. Append a row per channel "
    "after each coordinator publication run; do not hand-edit existing rows.")

FEED_PAIRS = tuple((view, *cv.FEED_PATHS[view]) for view in cv.VIEWS)


class PublishedBaseline(dict):
    complete_view_seen = False


def _feed_rel(channel, suffix):
    cv.channel_for(channel)
    return cv.FEED_PATHS[channel][0 if suffix == "json" else 1]


def _git_output(root, arguments, field):
    """Read local Git objects without inherited redirects or replacement refs."""
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("GIT_")}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_SYSTEM": os.devnull,
                "GIT_OPTIONAL_LOCKS": "0",
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_NO_REPLACE_OBJECTS": "1"})
    proc = subprocess.run(
        ["git", "-C", str(root), "-c", "core.hooksPath=" + os.devnull,
         "-c", "core.fsmonitor=false", *arguments],
        capture_output=True, env=env)
    if proc.returncode != 0:
        raise hubcore.HubError(
            f"{field}: trusted Git object read failed: "
            f"{proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout


def _git_show(root, commit, rel, field):
    """Read one exact committed blob; fail closed."""
    return _git_output(root, ["show", f"{commit}:{rel}"], field)


def _assert_ledger_append_only(root, raw, doc):
    """Keep earlier ledger rows even after their versions leave current feeds.

    Read at most two ledger-changing commits. Unrelated editorial commits do
    not hide the prior ledger, and a deletion/re-addition cannot bootstrap a
    fresh history. Actual signing also requires an exact clean tooling tree.
    """
    pins = _git_output(root, ["log", "-n", "2", "--format=%H", "HEAD",
                              "--", LEDGER_REL], "ledger ancestry").splitlines()
    if not pins:
        return  # First tracked ledger; signed publication rows still verify.
    head_raw = _git_show(root, "HEAD", LEDGER_REL, "committed ledger")
    if head_raw != raw:
        prior_raw = head_raw  # Also protect read-only checks of staged changes.
    elif len(pins) > 1:
        prior_raw = _git_show(root, pins[1].decode("ascii"), LEDGER_REL,
                              "previous ledger")
    else:
        return
    try:
        prior = json.loads(prior_raw)
        prior_rows = prior["publications"]
        if (hubcore.encoded(prior) != prior_raw or not isinstance(prior_rows, list)
                or prior.get("schemaVersion") != LEDGER_SCHEMA_VERSION):
            raise ValueError("invalid prior ledger")
        prefix_kept = doc["publications"][:len(prior_rows)] == prior_rows
    except (ValueError, TypeError, KeyError):
        raise hubcore.HubError("previous publication ledger cannot be verified") from None
    if not prefix_kept:
        raise hubcore.HubError(
            "publication ledger is append-only: historical rows cannot be "
            "removed or rewritten, even after a version leaves the latest feed")


def _verified_feed_table(feed_bytes, sig_bytes, channel, public_keys, field):
    """Verify one published feed pair and return {(id, version): contentDigest}."""
    key_id = hubcore.verify_envelope(feed_bytes, sig_bytes, public_keys)
    if key_id == hubcore.FIXTURE_KEY_ID:
        raise hubcore.HubError(
            f"{field}: signed with the fixture identity: forbidden")
    if hubcore.PRODUCTION_KEY_ID in public_keys \
            and key_id != hubcore.PRODUCTION_KEY_ID:
        raise hubcore.HubError(
            f"{field}: signed by unexpected identity {key_id!r}; the configured "
            f"production trust is {hubcore.PRODUCTION_KEY_ID!r}")
    try:
        feed = json.loads(feed_bytes)
    except ValueError as error:
        raise hubcore.HubError(
            f"{field}: published feed is not valid JSON: {error}") from None
    if hubcore.encoded(feed) != feed_bytes:
        raise hubcore.HubError(
            f"{field}: published feed bytes are not the canonical encoding; "
            f"refusing an untrustworthy baseline")
    cv.validate_view(feed, channel)
    table = {}
    for entry in feed["entries"]:
        package = entry.get("package")
        if package is not None:
            table[(entry["id"], entry["version"])] = package["contentDigest"]
    return table


def load_trustworthy_baseline(root=REPO, published_pin=None):
    """{(channel): {(id, version): contentDigest}} of the CURRENT publication.

    With `published_pin` (a 40-hex publication commit Y resolved
    independently by the coordinator) the feeds are read from that committed
    pin, so the baseline is anchored to the ACTUAL published history even
    when the tooling checkout is older. Without a pin the feeds are read
    from the working tree at `root`. Either way every feed's Ed25519
    signature must verify under the configured production trust; an
    incomplete or tampered publication fails closed, and an empty mapping is
    returned only when that channel was never published.
    """
    import build_catalog  # lazy: same trust loader the release builder uses

    root = pathlib.Path(root)
    public_keys = build_catalog.load_trust(root)
    if published_pin is not None and (
            not isinstance(published_pin, str)
            or not hubcore.COMMIT_PATTERN.fullmatch(published_pin)):
        raise hubcore.HubError("published pin must be a 40-hex commit")
    baseline = {}
    feed_payloads = {}
    full_paths = {p for view in cv.FULL_VIEWS for p in cv.FEED_PATHS[view]}
    if published_pin is not None:
        present_full = set(_git_output(root, ["ls-tree", "--name-only", "-r", published_pin,
                                               "--", *sorted(full_paths)], "full-view presence").decode().splitlines())
    else:
        present_full = {p for p in full_paths if (root / p).exists()}
    if present_full and present_full != full_paths:
        raise hubcore.HubError("incomplete complete-view publication: all full feeds and signatures are required")
    for channel, rel_feed, rel_sig in FEED_PAIRS:
        if channel in cv.FULL_VIEWS and not present_full:
            continue  # Historical publication before complete views existed.
        field = f"{channel} published baseline"
        if published_pin is not None:
            field = f"{channel} published baseline at {published_pin[:10]}"
            # A pinned publication must be readable in full: a pin whose feed
            # or signature object is unavailable fails closed instead of
            # degrading to "nothing published yet".
            feed_bytes = _git_show(root, published_pin, rel_feed, field)
            sig_bytes = _git_show(root, published_pin, rel_sig, field)
            baseline[channel] = _verified_feed_table(
                feed_bytes, sig_bytes, channel, public_keys, field)
            feed_payloads[rel_feed] = feed_bytes
            continue
        path = root / rel_feed
        sig_path = root / rel_sig
        if not path.exists() and not sig_path.exists():
            continue  # channel not published yet
        if not path.is_file() or not sig_path.is_file():
            raise hubcore.HubError(
                f"{field}: incomplete publication (feed or signature missing); "
                f"an absent signature never passes as unpublished")
        if not public_keys:
            raise hubcore.HubError(
                f"{field}: production artifacts exist but no public-key.json trust "
                f"is configured; a published feed without trust material must fail "
                f"the gate")
        baseline[channel] = _verified_feed_table(
            path.read_bytes(), sig_path.read_bytes(), channel, public_keys, field)
        feed_payloads[rel_feed] = path.read_bytes()
    if present_full:
        cv.assert_projection(feed_payloads)
    return baseline


def verify_ledger(ledger_path, root):
    """Parse and cryptographically verify the cumulative publication ledger.

    Every row must resolve against the SIGNED feed bytes committed at its
    pinned publication Y in `root` (the trusted tooling checkout): signature
    valid under the configured production trust, feed sha256 equal, channel
    equal, and every offered (id, version, contentDigest) present in that
    feed. Returns the list of verified publication rows. Raises HubError on
    any malformed, unverifiable or conflicting row — a tampered or partially
    deleted ledger never yields a weaker baseline.
    """
    import build_catalog

    ledger_path = pathlib.Path(ledger_path)
    raw = ledger_path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise hubcore.HubError(
            f"publication ledger must be UTF-8: {ledger_path}") from None
    try:
        doc = json.loads(text)
    except ValueError as error:
        raise hubcore.HubError(
            f"publication ledger is not valid JSON: {error}") from None
    if hubcore.encoded(doc) != raw:
        raise hubcore.HubError(
            "publication ledger bytes are not the canonical encoding; refusing "
            "an untrustworthy baseline input")
    if not isinstance(doc, dict) or set(doc) != {
            "schemaVersion", "publisher", "description", "publications"}:
        raise hubcore.HubError("publication ledger root keys mismatch")
    if doc["schemaVersion"] != LEDGER_SCHEMA_VERSION:
        raise hubcore.HubError(
            f"publication ledger schemaVersion must be {LEDGER_SCHEMA_VERSION}")
    if doc["publisher"] != "JiangNanGenius":
        raise hubcore.HubError("publication ledger publisher mismatch")
    if not isinstance(doc["publications"], list) or not doc["publications"]:
        raise hubcore.HubError("publication ledger carries no publications")
    if ledger_path.resolve() == (pathlib.Path(root) / LEDGER_REL).resolve():
        _assert_ledger_append_only(root, raw, doc)

    public_keys = build_catalog.load_trust(root)
    if not public_keys:
        raise hubcore.HubError(
            "publication ledger verification requires the configured production "
            "trust (public-key.json) in the tooling root")

    verified = []
    seen_rows = set()
    checked_complete_pins = set()
    for index, row in enumerate(doc["publications"]):
        field = f"publication ledger row {index}"
        if not isinstance(row, dict) or set(row) != {
                "publication", "channel", "feedSha256", "offers"}:
            raise hubcore.HubError(f"{field}: keys must be exactly publication, "
                                   f"channel, feedSha256, offers")
        publication = row["publication"]
        if not isinstance(publication, str) \
                or not hubcore.COMMIT_PATTERN.fullmatch(publication):
            raise hubcore.HubError(f"{field}: publication must be a 40-hex commit")
        channel = row["channel"]
        if channel not in cv.VIEWS:
            raise hubcore.HubError(f"{field}: unknown channel {channel!r}")
        identity = (publication, channel)
        if identity in seen_rows:
            raise hubcore.HubError(f"{field}: duplicate publication/view row")
        seen_rows.add(identity)
        if channel in cv.FULL_VIEWS and publication not in checked_complete_pins:
            paired = load_trustworthy_baseline(root, publication)
            if not set(cv.FULL_VIEWS) <= set(paired):
                raise hubcore.HubError(f"{field}: complete publication pairs are absent")
            checked_complete_pins.add(publication)
        hubcore.require_hex64(row["feedSha256"], f"{field}.feedSha256")
        offers = row["offers"]
        if not isinstance(offers, list) or not offers:
            raise hubcore.HubError(f"{field}: offers must be a non-empty array")
        for offer in offers:
            if not isinstance(offer, dict) \
                    or set(offer) != {"id", "version", "contentDigest"}:
                raise hubcore.HubError(
                    f"{field}: offer keys must be exactly id, version, contentDigest")
            hubcore.require_id(offer["id"], f"{field}.offer id")
            hubcore.require_version(offer["version"], f"{field}.offer version")
            hubcore.require_hex64(offer["contentDigest"],
                                  f"{field}.offer contentDigest")

        # Cryptographic anchor: the signed feed bytes at the pinned Y.
        feed_bytes = _git_show(root, publication, _feed_rel(channel, "json"), field)
        sig_bytes = _git_show(root, publication, _feed_rel(channel, "sig"), field)
        key_id = hubcore.verify_envelope(feed_bytes, sig_bytes, public_keys)
        if key_id == hubcore.FIXTURE_KEY_ID:
            raise hubcore.HubError(
                f"{field}: publication signed with the fixture identity: forbidden")
        if hubcore.PRODUCTION_KEY_ID in public_keys \
                and key_id != hubcore.PRODUCTION_KEY_ID:
            raise hubcore.HubError(
                f"{field}: signed by unexpected identity {key_id!r}")
        if hubcore.sha256_hex(feed_bytes) != row["feedSha256"]:
            raise hubcore.HubError(
                f"{field}: feed bytes at {publication[:10]} do not match the "
                f"ledger feedSha256; refusing an untrustworthy baseline")
        try:
            feed = json.loads(feed_bytes)
        except ValueError as error:
            raise hubcore.HubError(
                f"{field}: published feed is not valid JSON: {error}") from None
        if feed.get("channel") != cv.channel_for(channel):
            raise hubcore.HubError(f"{field}: ledger channel disagrees with the "
                                   f"published feed")
        if hubcore.encoded(feed) != feed_bytes:
            raise hubcore.HubError(f"{field}: noncanonical feed bytes")
        cv.validate_view(feed, channel)
        published = {}
        for entry in feed.get("entries", []):
            package = entry.get("package")
            if package is not None:
                published[(entry["id"], entry["version"])] = \
                    package["contentDigest"]
        if len(offers) != len(published) or {
                (offer["id"], offer["version"]) for offer in offers
        } != set(published):
            raise hubcore.HubError(
                f"{field}: ledger row must contain every packaged offer at its "
                "publication pin exactly once; partial historical rows are refused")
        for offer in offers:
            key = (offer["id"], offer["version"])
            if published.get(key) != offer["contentDigest"]:
                raise hubcore.HubError(
                    f"{field}: offer {offer['id']} {offer['version']} is not "
                    f"published with that contentDigest at {publication[:10]}; "
                    f"refusing an untrustworthy baseline")
        verified.append(row)
    return verified


def build_validated_baseline(root=REPO, ledger_path=None, published_pin=None,
                             provenance=None):
    """Cumulative, independently anchored {(channel, id, version): digest}.

    Merges the verified current publication (working tree at `root`, or the
    explicitly resolved publication commit `published_pin`) with the verified
    cumulative ledger (rows anchored to signed bytes at their publication
    pins). Fail closed when:
      * production history exists but the ledger is missing (no downgrade to
        "first publication");
      * any ledger row is malformed, unverifiable or conflicting;
      * the ledger fails to cover a currently published offer with the equal
        digest (stale tooling pinned before a publication).

    When `provenance` (a dict) is supplied it is filled with the audit facts
    of the baseline actually used, so a signing receipt can bind them.
    """
    root = pathlib.Path(root)
    current = load_trustworthy_baseline(root, published_pin)
    ledger_path = pathlib.Path(ledger_path) if ledger_path else root / LEDGER_REL
    if current and not ledger_path.is_file():
        raise hubcore.HubError(
            f"production history exists at {root} but the cumulative publication "
            f"ledger {ledger_path} is missing; refusing to publish without the "
            f"verified historical baseline (no downgrade to first publication)")
    merged = PublishedBaseline()
    rows = []
    if ledger_path.is_file():
        rows = verify_ledger(ledger_path, root)
        for row in rows:
            for offer in row["offers"]:
                key = (cv.channel_for(row["channel"]), offer["id"], offer["version"])
                digest = offer["contentDigest"]
                if key in merged and merged[key] != digest:
                    raise hubcore.HubError(
                        f"publication ledger conflict for {key}: two publications "
                        f"disagree on the contentDigest")
                merged[key] = digest
        merged.complete_view_seen = (any(row["channel"] in cv.FULL_VIEWS for row in rows)
                                     or bool(set(current) & set(cv.FULL_VIEWS)))
    for channel, table in current.items():
        for (skill_id, version), digest in table.items():
            if merged.get((cv.channel_for(channel), skill_id, version)) != digest:
                raise hubcore.HubError(
                    f"the publication ledger does not cover the currently "
                    f"published {channel} offer {skill_id} {version}; the tooling "
                    f"pin is stale or history was dropped — refresh the ledger "
                    f"from the signed published bytes before publishing")
    if provenance is not None:
        provenance.update({
            "ledgerPresent": ledger_path.is_file(),
            "ledgerSha256": (hubcore.sha256_hex(ledger_path.read_bytes())
                             if ledger_path.is_file() else None),
            "publicationPins": sorted({row["publication"] for row in rows}),
            "publishedPin": published_pin,
            "currentFeedChannels": sorted(current),
            "historicalFacts": len(merged),
        })
    return merged


def build_ledger_row(root, publication, channel):
    """Derive ONE verified ledger row for a publication pin (read-only).

    Used by the coordinator's publication workflow to APPEND the newly
    published (channel, offers) facts after committing a publication Y, and
    by the bootstrap that created the initial ledger. The row is only
    returned when the feed+signature at that pin verify under the configured
    production trust, the feed is canonical and schema-valid, and its channel
    matches — so a wrong pin can never mint a bogus historical fact.
    """
    import build_catalog

    if channel not in cv.VIEWS:
        raise hubcore.HubError(f"unknown channel {channel!r}")
    if not isinstance(publication, str) \
            or not hubcore.COMMIT_PATTERN.fullmatch(publication):
        raise hubcore.HubError("publication must be a 40-hex commit")
    root = pathlib.Path(root)
    public_keys = build_catalog.load_trust(root)
    if not public_keys:
        raise hubcore.HubError(
            "ledger row derivation requires the configured production trust")
    field = f"ledger row {channel}@{publication[:10]}"
    feed_bytes = _git_show(root, publication, _feed_rel(channel, "json"), field)
    sig_bytes = _git_show(root, publication, _feed_rel(channel, "sig"), field)
    key_id = hubcore.verify_envelope(feed_bytes, sig_bytes, public_keys)
    if key_id == hubcore.FIXTURE_KEY_ID:
        raise hubcore.HubError(f"{field}: fixture identity can never be a publication")
    if hubcore.PRODUCTION_KEY_ID in public_keys \
            and key_id != hubcore.PRODUCTION_KEY_ID:
        raise hubcore.HubError(f"{field}: unexpected signing identity {key_id!r}")
    try:
        feed = json.loads(feed_bytes)
    except ValueError as error:
        raise hubcore.HubError(f"{field}: feed is not valid JSON: {error}") from None
    if hubcore.encoded(feed) != feed_bytes:
        raise hubcore.HubError(f"{field}: feed bytes are not canonical")
    cv.validate_view(feed, channel)
    offers = []
    for entry in sorted(feed["entries"], key=lambda e: (e["id"], e["version"])):
        package = entry.get("package")
        if package is not None:
            offers.append({"id": entry["id"], "version": entry["version"],
                           "contentDigest": package["contentDigest"]})
    if not offers:
        raise hubcore.HubError(f"{field}: publication carries no packaged offers")
    return {"publication": publication, "channel": channel,
            "feedSha256": hubcore.sha256_hex(feed_bytes), "offers": offers}


def render_ledger(rows, description=LEDGER_DESCRIPTION):
    """Canonical bytes of a ledger document covering exactly `rows`."""
    doc = {"schemaVersion": LEDGER_SCHEMA_VERSION, "publisher": "JiangNanGenius",
           "description": description, "publications": rows}
    return hubcore.encoded(doc)


def assert_immutable_publication(candidate_outputs, baseline):
    """Refuse same-(channel,id,version) publication with a changed digest.

    candidate_outputs: {name: bytes} exactly as produced by
    build_catalog.build(). The baseline must come from
    build_validated_baseline. Unchanged published bytes and genuinely new
    versions pass; reuse of any historically published version with different
    bytes is refused even when re-signable.
    """
    full_present = set(candidate_outputs) & {cv.FEED_PATHS[v][0] for v in cv.FULL_VIEWS}
    if full_present or getattr(baseline, "complete_view_seen", False):
        cv.assert_projection(candidate_outputs)
    for name, data in candidate_outputs.items():
        if name not in cv.FEED_FILES:
            continue
        channel = "android" if name.startswith("android/") else "ios"
        if not any(key[0] == channel for key in baseline):
            continue
        try:
            feed = json.loads(data)
        except ValueError as error:
            raise hubcore.HubError(
                f"{channel} candidate feed is not valid JSON: {error}") from None
        for entry in feed.get("entries", []):
            package = entry.get("package")
            if package is None:
                continue
            key = (channel, entry["id"], entry["version"])
            published_digest = baseline.get(key)
            if published_digest is not None \
                    and package["contentDigest"] != published_digest:
                raise hubcore.HubError(
                    f"immutable publication refused: {entry['id']} "
                    f"{entry['version']} is already published on the {channel} "
                    f"channel with a different contentDigest; released bytes are "
                    f"immutable — bump the Skill package version and re-sign the "
                    f"new digest (rollback binds the exact published "
                    f"version+digest, never 'latest')")
    return True
