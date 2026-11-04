# Curated local iOS Bridge declaration

This authoring amendment admits only the already implemented optional
floe-ios-automation native contract. It adds no App capability or new authority.
The App's existing SkillCapability cases, SkillManifest.configuration decoder,
configuration store and IOSBridgeIntegration remain authoritative.

The curated manifest is iOS-only, scriptRuntime none, with no tools or Python
packages, and exactly credentials/device.observe/device.interact. Its only
configuration entry is bridge: connection / string / required true / sensitive
false / connectionKind ios.bridge.local, with bounded English and Simplified
Chinese display text. No ENV mapping, arbitrary native connection kind, credential
value, URL, secret export, script runtime or browser alias is accepted here.
Other generic configuration forms stay outside this narrow curated admission.

The native integration owns profile default and target local-ios regardless of
the task's default remote environment. Pairing uses ios.bridge.pair, not generic
skill.config.save/bind/declare. Declared values cannot grant native permissions;
normal installed/enabled, granted-capability, source/revision, readiness and task
runtime-authority gates still apply. This remains an optional downloadable Skill,
not a new built-in tool registration. Minimum App is 1.7.70 in the registry.

Registry/catalog/review capability enums mirror the two existing device capability
names. Guide-only review records retain os null / arch n/a / evidence unproven;
static source approval does not claim successful physical-device pairing or
control. Signed static content does not certify the external companion runtime.
