## Timeout Guard Release Notes（Evidence Timeout / Degradation 封板版）

### 背景与已解决的问题

- **Evidence timeout / degradation 风险不可控**
  - 之前：Evidence Provider 变慢或退化时，只能通过业务规则间接体现，容易出现：
    - 延迟放大：慢调用拖垮整体决策延迟。
    - HITL 风暴：在高压场景下，大量请求被“被动”升级为 HITL。
    - 行为难以解释：同样的 slow/degraded 情况下，不同调用路径表现不一致。
  - 现在：通过统一的 timeout guard 机制，将 **OK / TIMEOUT / ERROR / DEGRADED** 归一为 explain-only 标签，并在决策层以 tighten-only overlay 的方式处理，防止局部异常放大为系统性风险。

- **决策无法稳定回放 / 解释 / 灰度**
  - 之前：即便 Matrix、Risk Rules 等是可配置的，关于 “当时针对 timeout / degradation 究竟用了什么策略” 很难回答：
    - 没有独立的 policy version 概念。
    - 没有 risk tier 维度下的 overlay 行为差异。
    - 没有结构化 reason code，只能从 trace 文本中猜。
  - 现在：
    - 每次使用 timeout guard 的决策都会在 trace 中记录：
      - `timeout_guard_policy_version`（基础版本标识）
      - `timeout_guard_policy=<version> (risk_tier=R?)`
      - `risk_tier=R? (source=req|env|default)`
      - `timeout_guard_reason=<ENUM>`（仅在实际 tighten 时出现）
    - 结合 Evidence / `_meta`，可以精确重放和解释 “为什么这次是 HITL / DENY”，以及“当时用的是哪套 timeout 策略”。

---

### 新增能力（事实描述）

> 以下所有新增能力均为 **explain-only / tighten-only overlay**，不引入第二决策源，不改变 Matrix 的业务语义。

#### 1. Timeout Guard Overlays（HITL / DENY，tighten-only）

- 在 `gate.py` 中引入 timeout guard overlay 段，基于 `_meta` 中的 explain-only 标签进行决策收紧：
  - `_meta._hitl_suggested: bool`
  - `_meta._degradation_suggested: bool`
- 行为约束：
  - 仅允许在 **当前决策 index < 目标 index** 时抬高，不允许放松（tighten-only）。
  - DENY overlay 必须在 **HITL overlay 也启用** 且 `_hitl_suggested && _degradation_suggested` 条件下才可触发，严格禁止 “ALLOW 直接跳到 DENY” 的绕过路径。
  - 所有 overlay 发生在：
    - Matrix / Missing Evidence / Conflict Overrides / LoopGuard 之后，
    - Postcheck 之前。

#### 2. Risk Tier（R0–R3）差异化治理（在决策层）

- 引入 `risk_tier` 的决策层解析（不下沉到 helpers）：
  - 优先从未来的 `req.risk_tier`（如存在）读取；
  - 否则从 `AI_GATE_RISK_TIER` 环境变量获取；
  - 若均无，则默认 `R2`。
- 不改变现有 Risk Evidence 的 `risk_level` 计算逻辑，仅在 **Gate 层** 决定 timeout guard overlay 在不同 tier 下的收紧强度：
  - R0：不启用 timeout guard 收紧（即使 `_hitl_suggested` / `_degradation_suggested`），决策保持 baseline。
  - R1：允许 `_hitl_suggested` 升级到 HITL，但 **禁止 DENY**。
  - R2：保持现有 fail-closed 策略：`_hitl_suggested && _degradation_suggested` → 允许 DENY overlay。
  - R3：在 R2 行为基础上，额外允许 degraded-only（仅 `_degradation_suggested=True`）也升级到 HITL，以加强高风险下的防御。

#### 3. Timeout Guard Policy Version（可灰度 / 可回滚）

- 新增环境变量：
  - `AI_GATE_TIMEOUT_GUARD_POLICY_VERSION`（字符串，默认 `"v1"` / `"v2"` 由部署侧控制）
- 在 verbose trace 中统一暴露：
  - `timeout_guard_policy_version=<vX>`
  - `timeout_guard_policy=<vX> (risk_tier=R?)`
- 语义：
  - **不改变业务 Matrix 版本**（`policy.matrix_version` 仍由 `matrices/*.yaml` 控制）。
  - 只标记 timeout guard overlay 在本次决策中使用的“策略版本”，便于：
    - 灰度启用新策略版本；
    - 通过 env 回滚到旧行为；
    - 对比不同策略版本下的决策差异。

#### 4. Structured Reason Codes（Explain-Only）

- 在 `gate.py` 内部引入 timeout guard 的 reason code 常量（内部枚举）：
  - `NONE`
  - `HITL_SUGGESTED`
  - `DEGRADED_ONLY`
  - `HITL_AND_DEGRADED`
- 仅在 overlay 实际收紧决策时赋值，并在 verbose trace 中追加一行：
  - `timeout_guard_reason=HITL_SUGGESTED`
  - `timeout_guard_reason=DEGRADED_ONLY`
  - `timeout_guard_reason=HITL_AND_DEGRADED`
- 不写入 `DecisionResponse` 结构，也不参与任何决策计算，仅用于：
  - 后续 metrics / BI；
  - 审计与调试；
  - 精确回答 “本次为什么被 HITL / DENY（从 timeout guard 角度）”。

---

### 稳定性与不变量声明

- **单一决策源不变**
  - 仍然只有 `src/core/gate.py` 创建和写入最终 `Decision` 枚举。
  - Evidence 层（`src/evidence/*`）、helpers、demo 代码都不返回 / 不持有 `Decision`。

- **Evidence / `_meta` / Decision 分层不变**
  - Evidence 只产事实和质量标签（OK / TIMEOUT / ERROR / DEGRADED 等）。
  - `_meta` 仍然是 explain-only 输入（例如 `_hitl_suggested`, `_degradation_suggested`），在 Gate 内只读，不被回写或导出为 API 字段。
  - 决策（ALLOW / ONLY_SUGGEST / HITL / DENY）依旧只在 Gate 层产生，并最终写入 `DecisionResponse`。

- **Overlay 一律 tighten-only**
  - LoopGuard、timeout guard overlays、postcheck 等所有附加机制都遵守严格的 tighten-only 约束：
    - 只能从低风险/宽松决策走向更严格决策；
    - 绝不放松已有决策等级。
  - DENY overlay 强依赖 HITL overlay 的启用，禁止任何“跳过 HITL 直接 DENY”的路径。

- **可回放、一致性不变**
  - 在相同的：
    - 请求输入（包括 text / context / structured_input），
    - Matrix 配置（`matrices/*.yaml` 不变），
    - timeout guard 相关 env（policy_version / risk_tier / overlay 开关）不变的前提下：
  - `gate.decide` 仍然是纯函数式的、可重放的：
    - **同输入 + 同配置 = 同决策**。
  - Replay 报告与 CI 测试全部覆盖并验证了这一点。

---

### 明确“不包含什么”（Out of Scope）

> 本轮 timeout guard 发布 **刻意不做** 以下事情，这些都需要独立的后续 Task 与 policy version 才能引入。

- **不引入新业务策略**
  - 不新增或修改 Matrix 中的业务性规则（例如某类场景直接 DENY / ALLOW）。
  - 不改变 Risk Rules、Permission Policies 的语义和决策权重。

- **不改变 Matrix 语义**
  - Matrix 仍然是业务策略的唯一来源：
    - defaults、rules、type_upgrade_rules、missing_evidence_policy、conflict_resolution 等行为不变。
  - Timeout guard 只是在 Matrix 之后，作为 “护栏式 tighten overlay” 存在。

- **不引入 metrics / 自动统计**
  - 本轮只提供 trace 级别的结构化信号（policy_version / risk_tier / reason codes），**不新增任何埋点或 metrics 上报逻辑**。
  - 所有统计与 BI 行为若要引入，需在未来单独的 Observability / Metrics Task 中完成。

- **不修改 API / `DecisionResponse` 结构**
  - `DecisionResponse` 的字段、解释结构、policy 信息完全保持不变。
  - 所有新增的信息（policy_version / risk_tier / timeout_guard_reason）仅体现在 verbose trace 中，不影响对外 API 合同。

---

### 总结（一句话版本）

本次 timeout guard 版本在 **不改变业务策略、不改 API、不改核心架构不变量** 的前提下，补上了 Evidence timeout / degradation 的治理缺口：  
通过 **HITL / DENY tighten-only overlays + risk tier 分层 + policy version + structured reason codes**，让系统第一次可以 **稳定回答 “这次为什么收紧/拒绝”**，并支持 **灰度 / 回滚 / 重放审计**。 

