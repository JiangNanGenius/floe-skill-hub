# Chat-led local Bridge setup / 聊天引导本机配对

Minimum App for the future Hub registry entry: 1.7.70. Keep this floor in the
Hub entry, not as an unknown field inside floe.json. This source candidate is
1.0.2; the prior optional 1.0.1 source remains unchanged.

1. Inspect configuration with the existing `skill.config` tool:
   `{"action":"inspect","skillID":"floe-ios-automation","profile":"default","target":"local-ios"}`.
2. Call `ios.bridge.status` with `{"include_configuration":true}`. If installed,
   enabled, authorized and eligible for pairing, call `ios.bridge.pair` once,
   for example `{"client_name":"Floe","replace_existing":false}`.
3. Explain Bridge's native owner confirmation; wait for that actual decision.
   Never solicit pairing tokens/passcodes or approve the protected UI through
   automation. A configuration page is optional, not a required chat detour.
4. After returning, recheck status and use `skill.config` with
   `{"action":"validate","skillID":"floe-ios-automation","profile":"default","target":"local-ios","fields":["bridge"]}`.
   Only current, validated readiness permits observe/control. Configuration,
   pairing and execution are distinct results; never invent success.

Do not use `skill.config.save`, `bind`, or a variable/secret `declare` to make
the bridge connection. The native pairing service owns this connection. Do not
replace device.observe/device.interact with browser capabilities or request a
remote Linux/Mac connection when a remote machine is the task default.

聊天流程：安装并启用后先检查配置和 `ios.bridge.status`，符合条件才调用一次
`ios.bridge.pair`。向用户说明 Bridge 中的原生确认，等实际批准并回到聊天后，重新
检查状态并验证 `bridge` 当前 revision。只有真实 ready 才观察或控制。不要要求用户
为了聊天配对先找配置页面；不在对话里索要密钥，不用 browser 权限代替设备权限。
