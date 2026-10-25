#!/usr/bin/env python3
"""Render the legacy four-item schemaVersion-2 compatibility view.

The App's historical JiangNanGenius/floe-agent skill-hub feed stays byte-
immutable for old clients; this script only produces the exact OLD SHAPE
(schemaVersion 2, publisher, packages[] with the 'skill-hub/packages/...'
prefix, zh-Hans/en releaseNotes) from qualified builtin entries so the main
publish owner can refresh the compatibility view when a builtin is actually
republished from this hub. New candidates can never enter the four-item
decoder. No signature is produced here: the publication owner signs with the
production key in their own run.

python3 scripts/build_legacy_view.py --catalog catalog.json --out DIR/view.json
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import hubcore

REPO = pathlib.Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", default=str(REPO / "catalog.json"))
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    path = pathlib.Path(args.catalog)
    if not path.is_file():
        raise SystemExit(f"no production feed at {path}; the compatibility view "
                         "exists only after the hub publishes a qualified catalog")
    try:
        view = hubcore.build_legacy_view(path.read_bytes())
    except hubcore.HubError as error:
        if "no qualified package" in str(error):
            raise SystemExit("legacy view pending: builtin entries are staged but "
                             "not yet qualified; the old four-item feed must keep its "
                             "released bytes unchanged until then") from error
        raise
    print("legacy four-item view bytes verified deterministic")
    if args.out:
        target = pathlib.Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(view)
        print("wrote " + str(target))
    else:
        sys.stdout.buffer.write(view)
    parsed = json.loads(view)
    ids = sorted(p["id"] for p in parsed["packages"])
    assert ids == sorted(hubcore.RESERVED_BUILTIN_IDS), "decoder invariant violated"
    assert parsed["schemaVersion"] == hubcore.LEGACY_CATALOG_SCHEMA_VERSION
    assert all(p["path"].startswith("skill-hub/packages/") for p in parsed["packages"])
    print("decoder invariants hold: exactly the four reserved guides")


if __name__ == "__main__":
    main()
