## CHANGE TASK TEMPLATE（冻结式任务说明）

> 用于描述类似 Task 2.7–4.x 这样的“冻结式任务”，帮助保持：
> - 单点责任、
> - 最小 diff、
> - 可回放 / 可复盘。

---

### 1. 元信息（Meta）

- **Task ID**：`Task X.Y`
- **模块范围**：`gate.py` / `gate_helpers.py` / `tests/...` 等
- **相关 Spec / OpenSpec Change**：`openspec/changes/...`

---

### 2. 背景（Why）

> 简要说明：
> - 当前系统已经做到哪里（能力与边界），
> - 现在暴露出的缺口是什么，
> - 这个 Task 想解决的核心“运营痛点”或“安全痛点”是什么。

示例结构：

- 已有能力：
  - Evidence：...
  - Explanation：...
  - Decision：...
- 现有缺口：
  - 例如：无法回答“为什么是 HITL / DENY？”、
  - 无法按 risk tier 做差异化治理、
  - 无法回放当时用的是哪一版策略。

---

### 3. 目标（What）

> 用 2–5 条要点描述本 Task 的**新能力**，并显式声明“不做什么”。

- **新增能力**（示例）：
  - 在 `gate.py` 中引入 XXX 开关，
  - 在 trace 中输出 YYY 信息，
  - 为 ZZZ 增加 explain-only 标签。
- **不改变的行为**：
  - 不改变既有决策结果，
  - 不改变 Evidence / helpers 的职责，
  - 不改变响应结构。

---

### 4. 冻结边界（Must / Must Not）

> 强约束清单，用于“保护已封板的能力”。

- **Must**
  - 只改哪些文件（列出精确范围），
  - 必须保持的系统不变量（单点决策、tighten-only、不改 `_meta` 语义等），
  - 默认配置下，行为必须与哪个版本完全一致（如“与 3.3/4.0 行为一致”）。

- **Must Not**
  - 明确禁止的行为：
    - 不引入新 I/O / 远程配置，
    - 不在 helpers 层引入裁决逻辑，
    - 不改变 `DecisionResponse` 结构或 matrix 语义，
    - 不让 Explanation 层获得决策权。

---

### 5. 输入与来源（Inputs & Sources）

> 清晰列出本 Task 新读/用到的输入，以及**来源优先级**。

- **Request 字段**：
  - 例如：`req.risk_tier`（若存在时的优先级），`req.context` 中的某个 key。
- **环境变量**：
  - 例如：`AI_GATE_...` 等，写明：
    - 默认值是什么，
    - 当 env 缺省时的行为。
- **合成 / 默认值**：
  - e.g. `risk_tier` 默认 `R2`。

> 若某个字段当前 Request 中尚不存在（如 `req.risk_tier`），应在这里说明本 Task 暂时只使用 env/default，并为未来扩展留钩子。

---

### 6. 规则（How：行为矩阵）

> 用**小矩阵 / 条款**描述实际行为，不写实现细节。

示例（risk tier × meta）：

| risk_tier | `_hitl_suggested` | `_degradation_suggested` | 结果（相对 baseline）       |
|----------|-------------------|--------------------------|----------------------------|
| R0       | True/False        | True/False               | 不抬高                      |
| R1       | True              | False/True               | 至少 HITL，不 DENY         |
| R2       | True              | True                     | DENY（fail-closed）        |
| R3       | False             | True                     | HITL（degraded_only→HITL） |

> 同一小节中应清楚区分：
> - “触发条件”（if），
> - “allowed 行为”（tighten-only / 不 change），
> - “禁止的跳变”（例如“禁止 ALLOW→DENY bypass HITL”）。

---

### 7. Trace / Explain 规则

> 定义本 Task 引入或依赖的 trace 行为，确保可回放。

- **必须输出的 trace**（在 `verbose=True` 时）：
  - 例如：
    - `timeout_guard_policy_version=v2`
    - `risk_tier=R2 (source=env)`
    - `timeout_guard_policy=v2 (risk_tier=R2)`
    - `timeout_guard_reason=HITL_AND_DEGRADED`
- **只解释、不裁决**：
  - 明确这些 trace / reason code 不参与决策，仅用于：
    - 调试、
    - 审计、
    - BI / metrics。

---

### 8. 单测要点（Testing）

> 列出需要新增的测试文件与核心场景。

- **测试文件**：
  - `tests/test_....py`
- **场景覆盖**（示例）：
  - 默认配置下行为与老版本完全一致，
  - 各种开关 / tier / meta 组合的最小行为矩阵，
  - 无 meta / feature flag 关闭时的回归行为，
  - trace 中是否包含/不包含特定结构化字段（version / tier / reason）。

> 测试风格建议：
> - stub pipeline 固定 baseline decision_index，
> - 只验证 Task 引入的那一层逻辑（最小切面），
> - 回归测试与新增测试分层。

---

### 9. 验收标准（Acceptance）

> 明确“什么情况下可以说 Task 完成并封板”。

- 行为保持：
  - 默认路径 = 老版本回归，
  - 新路径 = 符合规则矩阵且 tighten-only。
- 结构保持：
  - 不改 DecisionResponse / Evidence / helpers 的既有契约。
- 可回放：
  - trace 中包含 version / tier / reason 等必要信息。
- 测试：
  - 新增测试全部通过，
  - 相关回归测试全部通过。

---

### 10. 责任链收口（Closure）

> 用 2–4 句总结本 Task 完成后系统的新“责任闭环”。

示例：

- 完成本 Task 后，系统不仅能做出 ALLOW / HITL / DENY 决策，还能结构化说明：
  - 使用了哪一版策略（policy_version），
  - 在哪个风险等级下决策，
  - 是因为哪些 explain-only 标签触发了哪条 overlay 规则。
- 这一闭环是后续 metrics / audit / BI 的前提，也为未来的策略演进提供“可回放的地基”。

