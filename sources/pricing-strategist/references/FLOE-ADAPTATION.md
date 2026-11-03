# Pricing Strategist — Floe runtime and product copy

## English

**Name:** Pricing Strategist

**Description:** Design or revisit product pricing: choose a model, analyze willingness to
pay and shape Good/Better/Best tiers with deterministic, reviewable calculations.

**What it does**

- Ranks five pricing models (subscription seat-based, usage-based, value-based, freemium,
  hybrid) from a pricing brief and shows the trade-offs.
- Computes Van Westendorp PSM intersections and a Range of Acceptable Prices from complete
  survey responses.
- Assigns features to Good/Better/Best tiers and flags packaging anti-patterns.
- Recommends a model and a range, never a single price; the commercial owner decides.

**Runtime and safety**

- The three calculators are standard-library Python and run only in the task's resolved
  Linux environment through `exec.shell`, with explicit workspace/environment ownership.
  There is no host-interpreter fallback, language alias, package install or network call.
- Input is one JSON file inside the workspace root; symlinks, hard links, directories,
  traversal, oversized files, duplicate keys and non-finite numbers are refused.
- Reports are printed to stdout; the scripts do not create or overwrite files.
- The built-in `--sample` data is synthetic. It is not market research and must not be used
  as evidence of willingness to pay.

**Limits**

- PSM is directional: N ≥ 30 minimum, N ≥ 100 preferred; below 30 the tool warns.
- The tool does not run conjoint, NMS, A/B tests or any live pricing experiment.
- Guest execution evidence: this build passed the shipped 12-check verifier and the three
  fixture CLIs in a real Linux/riscv64 component guest (see `PROVENANCE.md`). This is component
  evidence only — not App install, Simulator, physical-device, Android or remote-Linux proof.

## 简体中文

**名称：** 定价策略

**说明：** 设计或重新审视产品定价：选择定价模型、分析支付意愿，并用可复核的确定性计算设计
Good/Better/Best 套餐。

**功能**

- 根据定价简报为五种定价模型（按席位订阅、按用量、按价值、免费增值、混合）排序，并说明取舍。
- 基于完整的调研回答计算 Van Westendorp PSM 的四个交点和可接受价格区间。
- 将功能分配到 Good/Better/Best 三档，并标记常见的套餐设计问题。
- 只建议模型与价格区间，不给出单一价格；最终价格由业务负责人决定。

**运行与安全**

- 三个计算脚本仅使用 Python 标准库，只在任务已解析的 Linux 环境中通过 `exec.shell` 运行，
  并遵循明确的工作区与环境归属。不存在宿主解释器回退、语言别名、自动安装或网络调用。
- 输入是工作区根目录内的一个 JSON 文件；符号链接、硬链接、目录、路径穿越、超大文件、
  重复键和非有限数字都会被拒绝。
- 报告只输出到标准输出；脚本不会创建或覆盖文件。
- 内置 `--sample` 数据是合成数据，不是市场调研，不能作为支付意愿证据。

**限制**

- PSM 是方向性工具：最少 N ≥ 30，建议 N ≥ 100；低于 30 时脚本会警告。
- 工具不执行联合分析、NMS、A/B 测试或任何真实定价实验。
- 运行证据：本构建已在真实 Linux/riscv64 组件访客中通过自带 12 项校验与三个 fixture CLI
  （见 `PROVENANCE.md`）。仅为组件证据，不构成 App 安装、模拟器、真机、Android 或远程
  Linux 证明。

## Execution contract / 执行契约

| Field | Value |
| --- | --- |
| Script runtime | `remote` |
| Capabilities | `execution.remote`, `workspace.read`, `workspace.write` |
| Tools | `exec.shell` |
| Python packages | none (`pythonPackages: []`) |
| Declared execution target | Linux / riscv64 / component-guest qualified |
| Install channel proposed | iOS first; Android arm64/x86 source-portable but requires separate guest evidence |
| Network | none |
| File output | none (stdout only) |

The App owns workspace file staging and saving. The Linux guest owns calculation execution.
There is no second execution path: the same scripts must not be run through a host Python,
`python.local`, a language alias or an implicit fallback.

## App-native vs external target / 应用原生与外部目标

| Surface | Owner | What it does | What it does not do |
| --- | --- | --- | --- |
| iPad/iOS App | App-native | Presents the skill, stages/reads workspace files, saves the returned report, owns permissions and history | It does not run the Python scripts on iOS |
| Resolved Linux guest (iOS riscv64) | External target via `exec.shell` | Runs the three CLIs and the verifier with the guest CPython (real riscv64 component-guest run recorded for this build; CPython 3.13.5) | It does not make network/model calls or install packages |
| Android arm64 / x86_64 Linux guest | External target (unqualified) | Source is architecture-independent standard-library Python; no native extension is shipped | No Android guest run was performed for this build; do not claim it verified |
| Remote x86_64 / aarch64 Linux | External target (unqualified) | Same standard-library source is portable | No remote Linux run was performed for this build |
| Native host interpreter / `python.local` / language alias | Not used | Nothing | It is not an allowed execution path and is not evidence |

## Dependency and preflight contract / 依赖与预检契约

- This package ships **no** `references/dependencies.json`. The V1 contract says a skill with
  no dependencies ships no declaration; an empty profile would be invalid. Every script is
  standard-library only, so `pythonPackages` is `[]` and no wheel/apt/npm/font/engine
  requirement is invented.
- If a later version adds a third-party package, it must add a V1 `references/dependencies.json`
  with exact pins, real Debian/architecture profiles and (for pip) a full hash-pinned closure,
  then raise `minimumAppVersion` to the first capable App build. That is a future contract,
  not a claim in this package.
- Preflight for the release owner: (1) install the package in a task with an explicit writable workspace;
  (2) run `python3 scripts/verify_pricing_skills.py` in the resolved Linux guest; (3) run the
  three CLIs on one synthetic fixture each; (4) only then consider flipping execution evidence.
  A host run is developer evidence and must not be recorded as guest qualification.
