"""Fixed signed catalog views; paths never come from candidate metadata."""
import json

import hubcore

LAYOUTS = {
    "ios": ("ios", "catalog.json", "catalog.sig"),
    "android": ("android", "android/catalog.json", "android/catalog.sig"),
    "ios-full": ("ios", "catalog-full.json", "catalog-full.sig"),
    "android-full": ("android", "android/catalog-full.json", "android/catalog-full.sig"),
    # Signed large-source capability feeds (App consumer contract,
    # 2026-11-10): same-Y full replacements/supersets of the corresponding
    # standard full feed. Only large-source entries carry package.profile;
    # the standard feeds never carry profile keys (old strict readers reject
    # unknown package keys before any version floor).
    "ios-large-source-v1": ("ios", "catalog-large-source-v1.json",
                            "catalog-large-source-v1.sig"),
    "android-large-source-v1": ("android", "android/catalog-large-source-v1.json",
                                "android/catalog-large-source-v1.sig"),
}
LEGACY_VIEWS = ("ios", "android")
FULL_VIEWS = ("ios-full", "android-full")
# Same-Y signed capability projections, verified AFTER the standard feeds.
CAPABILITY_VIEWS = ("ios-large-source-v1", "android-large-source-v1")
VIEWS = LEGACY_VIEWS + FULL_VIEWS
ALL_VIEWS = VIEWS + CAPABILITY_VIEWS
FEED_PATHS = {view: (row[1], row[2]) for view, row in LAYOUTS.items()}
FEED_FILES = frozenset(row[1] for row in LAYOUTS.values())
ARTIFACT_FILES = frozenset(path for view in VIEWS for path in FEED_PATHS[view])


def channel_for(view):
    if view not in LAYOUTS:
        raise hubcore.HubError(f"unknown catalog view {view!r}")
    return LAYOUTS[view][0]


def full_view_for(capability_view):
    """The standard full view a capability projection must mirror."""
    if capability_view not in CAPABILITY_VIEWS:
        raise hubcore.HubError(f"unknown capability view {capability_view!r}")
    return capability_view.split("-", 1)[0] + "-full"


def validate_view(feed, view):
    hubcore.validate_catalog(feed, channel=channel_for(view),
                             capability=view in CAPABILITY_VIEWS)
    if view in LEGACY_VIEWS and any(e["planNumber"] > len(hubcore.LEGACY_PLAN_IDS)
                                    for e in feed["entries"]):
        raise hubcore.HubError("legacy catalog cannot contain appended entries")


def assert_projection(outputs):
    """Require complete views and exact legacy projections of their rows.

    When a capability feed pair is present in `outputs` (publication or
    relay members), it is verified as a signed capability view AND as an
    exact superset of the corresponding standard full feed (standard rows
    byte-identical, only large-source entries additional). Capability feeds
    are conditional: absence is a valid, expected state.
    """
    for channel in LEGACY_VIEWS:
        legacy_path = FEED_PATHS[channel][0]
        full_path = FEED_PATHS[channel + "-full"][0]
        if legacy_path not in outputs or full_path not in outputs:
            raise hubcore.HubError("both complete and legacy catalog views are required")
        legacy, full = (json.loads(outputs[path]) for path in (legacy_path, full_path))
        validate_view(legacy, channel)
        validate_view(full, channel + "-full")
        rows = [e for e in full["entries"] if e["planNumber"] <= len(hubcore.LEGACY_PLAN_IDS)]
        expected = hubcore.build_catalog({}, channel, full["feedStatus"], rows,
                                        full["sourceCommit"], full.get("generatedNote"))
        if legacy != expected:
            raise hubcore.HubError(f"{channel}: legacy catalog is not the exact complete-view projection")
    for view in CAPABILITY_VIEWS:
        feed_path = FEED_PATHS[view][0]
        if feed_path not in outputs:
            continue
        full_view = full_view_for(view)
        full_path = FEED_PATHS[full_view][0]
        if full_path not in outputs:
            raise hubcore.HubError(f"{view}: capability feed without its standard full view")
        capability = json.loads(outputs[feed_path])
        full = json.loads(outputs[full_path])
        validate_view(capability, view)
        hubcore.validate_capability_projection(capability, full)
    return True
