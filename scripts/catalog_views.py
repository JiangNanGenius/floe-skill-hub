"""Fixed signed catalog views; paths never come from candidate metadata."""
import json

import hubcore

LAYOUTS = {
    "ios": ("ios", "catalog.json", "catalog.sig"),
    "android": ("android", "android/catalog.json", "android/catalog.sig"),
    "ios-full": ("ios", "catalog-full.json", "catalog-full.sig"),
    "android-full": ("android", "android/catalog-full.json", "android/catalog-full.sig"),
}
LEGACY_VIEWS = ("ios", "android")
FULL_VIEWS = ("ios-full", "android-full")
VIEWS = tuple(LAYOUTS)
FEED_PATHS = {view: (row[1], row[2]) for view, row in LAYOUTS.items()}
FEED_FILES = frozenset(row[1] for row in LAYOUTS.values())
ARTIFACT_FILES = frozenset(path for row in LAYOUTS.values() for path in row[1:])


def channel_for(view):
    if view not in LAYOUTS:
        raise hubcore.HubError(f"unknown catalog view {view!r}")
    return LAYOUTS[view][0]


def validate_view(feed, view):
    hubcore.validate_catalog(feed, channel=channel_for(view))
    if view in LEGACY_VIEWS and any(e["planNumber"] > len(hubcore.LEGACY_PLAN_IDS)
                                    for e in feed["entries"]):
        raise hubcore.HubError("legacy catalog cannot contain appended entries")


def assert_projection(outputs):
    """Require complete views and exact legacy projections of their rows."""
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
    return True
