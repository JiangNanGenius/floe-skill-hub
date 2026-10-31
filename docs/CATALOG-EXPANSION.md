# Complete and legacy catalog views

The Hub keeps one registry and one set of immutable packages and reviews. The complete views are `catalog-full.json` / `catalog-full.sig` and `android/catalog-full.json` / `android/catalog-full.sig`. The legacy pairs keep their existing names. All four views use schema 3 and the same seven categories; their signed channel remains `ios` or `android`.

The original 43 `(planNumber,id)` identities and nine deep-adaptation identities remain protected. New optional rows append at 44+, up to 256 total registry rows. The builder binds the complete qualified selection first. It derives each legacy view by retaining only the original 43 planning slots, preserving each retained row and recomputing counts. A missing complete view or a disagreement with this projection refuses signing. The per-item archive, permission, review, execution and managed-engine gates remain in force.

Source `R` continues to mean alirezarezvani/claude-skills. `O` names another upstream and requires a pinned GitHub repository on an appended row; it cannot replace a legacy source identity or the `R` attribution. Unknown source values remain invalid. Exact authorship comes from `upstream.repository`, not a guessed label.

Every current signing run signs all four feeds, binds every output in its signed receipt and stages the union of their referenced archives/reviews. The relay and publisher authenticate the same fixed paths, rebuild from source X and publish the pairs atomically at one Y. The automatic path then appends ledger rows and verifies the public bytes. The website and App remain GitHub clients; neither uses a website catalog proxy.

The ledger labels complete views `ios-full` / `android-full`; these are internal view labels, not new execution or signed-feed channels. All artifact-history comparisons normalize to `(ios|android,id,version)`, so moving between views cannot change a published digest. Historical legacy-only publications remain readable; partial complete pairs are rejected, and complete views cannot be removed after introduction. Historical ledger rows remain an exact ordered prefix.

Android's content-floor projection is still restricted to explicitly reviewed guide IDs and rechecks the actual bound manifest and approved static review. Scripts, tools, dependencies, extra capabilities, missing Linux compatibility or execution claims never inherit the guide waiver. A content-floor value does not prove an older client's Hub UI supports the complete view.

Client activation requires the complete signed pairs to be readable at the same immutable Y. App version and consumer activation belong to the native release owner. A candidate with an unknown minimum App version is not ready for publication. The candidate inventory in `docs/curation/` is discovery/editorial evidence, not an install catalog or runtime qualification.
