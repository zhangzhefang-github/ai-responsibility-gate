## Timeout Guard Stability Statement（稳定性与演进边界声明）

> 本声明适用于 timeout guard 责任阶段（Tasks 2.7–4.3），描述当前行为的稳定范围、可演进边界以及明确禁止事项。

---

### 1. 已封板（Stable）的内容

#### 1.1 Timeout Guard 行为（在同一 policy_version 内）

- `_meta._hitl_suggested` / `_meta._degradation_suggested` 的语义已经 **冻结**：
  - `_hitl_suggested=True`：建议将当前请求升级到至少 HITL。
  - `_degradation_suggested=True`：当前 Evidence 处于 degraded 状态（质量下降，有退化/降级使用）。
- 在给定的：
  - `AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED`
  - `AI_GATE_TIMEOUT_GUARD_HITL_OVERLAY_ENABLED`
  - `AI_GATE_TIMEOUT_GUARD_DENY_OVERLAY_ENABLED`
  - `AI_GATE_TIMEOUT_GUARD_POLICY_VERSION`
  - `AI_GATE_RISK_TIER`（或未来等价 request 字段）  
  组合固定时，timeout guard overlays 的行为是 **稳定且可重放** 的：
  - 同一 policy_version 内，不允许“静默改变 overlay 行为”。

#### 1.2 Risk Tier 行为矩阵

在当前版本中，Gate 层针对 timeout guard 的 tier 行为矩阵已经封板：

| risk_tier | `_hitl_suggested` | `_degradation_suggested` | 相对 baseline 的行为                     |
|----------|-------------------|--------------------------|------------------------------------------|
| R0       | 任意              | 任意                     | 不收紧（baseline 决策保持不变）         |
| R1       | True              | False/True               | 至少 HITL，不触发 DENY                  |
| R2       | True              | True                     | 允许从 ALLOW/HITL 收紧到 DENY（fail-closed） |
| R3       | False             | True                     | degraded-only 也升级到 HITL（tighten-only） |

- 此表定义了 **timeout guard overlay 在各 tier 下的最大“收紧强度”**，属于稳定契约。
- 在不改变 policy_version 的前提下，不允许随意更改此矩阵。

#### 1.3 Reason Code 语义

Timeout guard 专用 reason code 集合已经封板为以下枚举（explain-only）：

- `NONE`：timeout guard 未对本次决策产生实际 tighten 效果。
- `HITL_SUGGESTED`：因 `_hitl_suggested=True` 将决策从低于 HITL 收紧到 HITL。
- `DEGRADED_ONLY`：在 R3 下，因 degraded-only（`_hitl_suggested=False, _degradation_suggested=True`）将决策收紧到 HITL。
- `HITL_AND_DEGRADED`：因 `_hitl_suggested=True && _degradation_suggested=True` 且 tier 允许，最终收紧到 DENY。

并通过 verbose trace 暴露为一行：

```text
[TRACE]   - timeout_guard_reason=<ENUM>
```

Reason code：

- **不参与决策计算**，只用于解释与后续统计；
- 在 overlay 实际改变 `decision_index` 时才会被设置；
- 如果多次 tighten，则以最终结果为准（如先 HITL 后 DENY → `HITL_AND_DEGRADED`）。

#### 1.4 Trace 字段契约

在 `verbose=true` 时，timeout guard 相关 trace 字段契约如下，已封板：

- **版本与策略**
  - `timeout_guard_policy_version=<vX>`
  - `timeout_guard_policy=<vX> (risk_tier=R?)`
- **风险分层**
  - `risk_tier=R? (source=req|env|default)`
- **Explain-only 标签可视化**
  - `timeout_guard: HITL suggested (hitl_suggested=True)`
  - `timeout_guard: degraded (degradation_suggested=True)`
- **DENY 决策说明**
  - `gate_decision=DENY (timeout_guard: hitl+degraded)`
- **结构化理由**
  - `timeout_guard_reason=<ENUM>`

以上字段的 **存在与含义** 均被视为稳定契约，不允许在同一 policy_version 内发生“静默含义变更”。

---

### 2. 只能通过新 policy_version 改变的内容

以下内容若需要改变，**必须通过引入新的 `AI_GATE_TIMEOUT_GUARD_POLICY_VERSION` 并配套文档、测试与 Release Notes**，禁止直接改现有行为：

- **Overlay 触发条件**
  - 例如：
    - 是否允许某些 tier 在 `_degradation_suggested=True` 时自动升到 HITL。
    - 是否引入新的 `_meta` 触发条件（如 `_force_deny_suggested` 等）。
  - 这些都属于策略行为变更，必须通过新 policy_version 生效。

- **Tier 行为矩阵**
  - R0–R3 对 overlay 的允许程度（如 R1 是否允许某些场景 DENY）属于风险策略变更：
    - 若要调整上述矩阵，必须声明一个新的 policy_version（如 `"v3"`），并在 `POLICY_VERSIONING.md` 中增补说明。

- **Reason Code 扩展**
  - 引入新的 timeout guard reason code（例如 `TIMEOUT_BUDGET_EXCEEDED` 等）亦属于策略变更：
    - 必须明示哪些 version 开始支持；
    - 明确新枚举的语义与使用条件；
    - 并保持向后兼容（旧版本的 reason code 语义不变）。

---

### 3. Extension Points（未来可扩展，但本轮不做）

以下能力在当前 timeout guard 阶段 **不会实现**，只是被明确标记为未来可能的扩展方向；任何实现都必须走新的 Task + 新 policy_version 流程：

- **Metrics / BI**
  - 基于 `timeout_guard_reason` / `risk_tier` / policy_version 等字段的：
    - 聚合指标（HITL/DENY 的来源分布）、
    - Dashboard、
    - 自动化报告等。

- **自动化审计**
  - 利用结构化 trace 自动检测策略回退、策略漂移或异常 tighten 模式。

- **`req.risk_tier` 正式字段化**
  - 将 risk tier 显式加入 `DecisionRequest` schema，由调用方明确传入；
  - 需要系统级的 schema 变更与迁移计划，不在本轮范围内。

- **新责任阶段**
  - 例如：
    - 更高层的“策略路由”（不同业务/租户使用不同超时策略）；
    - 更细粒度的 per‑provider timeout governance；
    - 非 timeout 维度的额外责任 overlay（例如人群分层策略）。

---

### 4. 核心承诺（不变量）

以下条款在 timeout guard 阶段被视为**强不变量**，任何未来 Task 若要触碰，必须在文档中显式声明并更新 contract：

- **Tighten-Only**
  - LoopGuard、timeout guard overlays、postcheck 等所有附加机制只能向更严格的决策移动 index，绝不放松。
  - 任何绕过 tighten-only 的行为（例如因 timeout 将决策从 HITL 放松到 ALLOW）都是严格禁止的。

- **Explain-Only**
  - `_meta`、policy_version、risk_tier、reason codes 均为 explain-only / config-only：
    - 不直接成为新的决策枚举或 primary_reason。
    - 不在 Evidence 层回写或反向驱动 Evidence。

- **No Silent Behavior Change**
  - 在现有 policy_version 下：
    - 不允许“上线代码后，timeout guard 行为悄悄改变一丢丢”这类修改。
    - 任何行为变更必须：
      - 明确 policy_version bump，
      - 更新 `POLICY_VERSIONING.md` / Release Notes，
      - 补充对应测试。

- **可回滚、可对比、可复盘**
  - 通过：
    - Matrix 版本 + timeout guard policy_version + risk_tier，
    - 回放工具与测试套件，
  - 必须能够：
    - 回滚到旧策略（仅通过调整 env / 配置，而非热 patch 代码逻辑）；
    - 对比新旧策略在同一案例集上的差异；
    - 给出清晰的 “为什么 tighten / 为什么 DENY” 的结构化解释。

---

### 5. 明确禁止事项（对后来维护者）

> 若要改变以下任何一条，请先写新的 Task + 新的 policy_version 说明，再改代码；禁止“随手改一下就合了”。

- **禁止在 Evidence / helpers 层做决策**
  - 不允许在 `src/evidence/*` 或 `gate_helpers.py` 中引用 `Decision` 或实现任何形式的“直接 DENY / HITL”。

- **禁止在 Gate 之外复制 timeout guard 逻辑**
  - Timeout guard overlays 必须集中在 `gate.py` 内部统一管理，禁止在其他模块“手抄一套”逻辑。

- **禁止在现有 policy_version 下悄悄调整 overlay 行为或 tier 矩阵**
  - 包括但不限于：
    - 改变 `_hitl_suggested` / `_degradation_suggested` 的触发条件；
    - 改变某个 tier 是否允许 DENY；
    - 改变 degraded-only 是否升级到 HITL。

- **禁止在未更新文档的情况下扩展 reason codes / trace 字段语义**
  - 新的 reason code / 新的 trace 字段必须：
    - 在文档中定义语义，
    - 在测试中被覆盖，
    - 在 Release Notes / POLICY_VERSIONING 中被提及。

---

**一句总结**：  
在 timeout guard 阶段，我们已经将 “Evidence timeout / degradation → explain-only 标签 → risk tier 感知的 tighten-only overlays → 结构化 reason + trace” 这一责任链完整封板。  
后续任何修改，都必须通过 **“新 Task + 新 policy_version + 文档 + 测试”** 的形式显式进入，而不能在现有行为上“悄悄加规则”。 

