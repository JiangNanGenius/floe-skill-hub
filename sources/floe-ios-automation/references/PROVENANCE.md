# Floe iOS automation source provenance

Optional first-party Skill, version 1.0.2; minimum App 1.7.70 is declared in the
Hub registry. Derived from JiangNanGenius/floe-agent commit `3a10cf97666b750fe135978ca8c8127c236f45d1`,
`skill-hub/optional/floe-ios-automation` version 1.0.1. Mozilla Public License
2.0 is retained under references/LICENSE-MPL-2.0.txt. No companion binary,
pairing key, private configuration, device data or executable script is bundled.

The 1.0.2 content delta aligns Simplified Chinese setup guidance with the
already-implemented chat-led pairing route, includes exact native tool/config
examples and preserves credentials/device.observe/device.interact. There is no
browser capability substitution, remote execution route or new native grant.

The App already declares the device capabilities and configuration schema;
its IOSBridgeIntegration owns the exact Skill ID, bridge connection, local-ios
scope and profile. Pairing/control use the existing task permission/runtime
authority and protected-surface rules. Source/static approval does not assert
pairing success, physical-device actions or App end-to-end acceptance.
