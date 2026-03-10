# Loop Governance 迁移到 Core 的设计方案

> 基于 LOOP_GUARD_SCAN_REPORT.md 的进一步分析  
> 目标：将 demo 层的 loop 收敛策略迁移到 core，使 loop governance 成为 core 的一等能力

---

## 一、核心结论：Loop 策略的本质

当前 demo 的 loop 治理逻辑本质是 **策略选择（matrix selection）**，而非决策覆盖（decision override）：

| 策略 | 实现方式 | 是否 tighten-only |
|------|----------|-------------------|
| **收敛** (nit_only_streak >= 3 → ALLOW) | 切换到 pr_loop_phase_e.yaml，该矩阵 R0 默认 ALLOW | 是（矩阵本身定义 ALLOW，非 override） |
| **Churn 升级** (max_rounds → HITL) | 切换到 pr_loop_churn.yaml，该矩阵全部默认 HITL | 是（矩阵本身定义 HITL） |
| **默认循环** | 使用 pr_loop_demo.yaml，默认 ONLY_SUGGEST | - |

因此，**loop 策略 = 根据 loop_state 选择应用哪套矩阵**。Gate 不「放松」任何决策，只是应用不同的策略（矩阵）。

---

## 二、问题 1：最合理的实现位置

### 三种方案对比

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| **扩展 evaluate_loop_guard** | 已有 hook，改动小 | 只能做 tighten；收敛（ALLOW）无法在此实现；语义上「guard」偏防御 | ⭐⭐ |
| **新增 apply_loop_policy stage** | 职责清晰，可读性好 | 需新增 stage，与现有 5.5 的 loop_guard 关系需厘清 | ⭐⭐⭐ |
| **新增 stop_condition stage** | 命名贴近「收敛」语义 | stop_condition 易被理解为「何时停止」，churn 升级是「升级」不是「停止」；与现有 loop_guard 概念重叠 | ⭐⭐ |

### 推荐：**Loop Policy 作为 Matrix 解析步骤（非独立 stage）**

**最合理位置**：在 pipeline 开始前，增加 **matrix 解析（resolve effective matrix）** 步骤，而非新增 stage。

**理由**：

1. **与现有架构一致**：已有 `resolve_matrix_path(profile, default_path)`（Phase D），loop policy 可视为其扩展——从 `profile` 扩展到 `(profile, loop_state, loop_policy)`。
2. **不破坏 tighten-only**：解析结果仍是「选哪个矩阵」，决策仍由矩阵产生，无 override。
3. **策略在 YAML**：`loop_policy` 写在矩阵中，与 `type_upgrade_rules`、`missing_evidence_policy` 同级。
4. **evaluate_loop_guard 保留**：继续作为 tighten-only 的防御 hook（如未来支持「round_index >= max_rounds 时强制 HITL」的二次保障），默认 no-op。

**实现形态**：

```
decide(req)
  → resolve_effective_matrix_path(matrix_path, loop_state, matrix)  # 新增
  → load_matrix(effective_path)
  → [现有 pipeline 不变]
  → evaluate_loop_guard(...)  # 保持，可扩展或保持 no-op
```

---

## 三、问题 2：如何让 Loop Governance 成为 Core 的一等能力

### 2.1 设计原则

1. **可选启用**：无 `loop_state` 时行为与现在完全一致（L0 兼容）。
2. **策略可配置**：`loop_policy` 在矩阵 YAML 中声明，core 不硬编码阈值。
3. **单一决策源**：所有决策仍来自 `core_decide()`，无第二套决策逻辑。
4. **域无关**：core 只理解 `round_index`、`nit_only_streak` 等抽象字段，不关心 PR、reviewer、coder。

### 2.2 具体设计

**A. Matrix 扩展：`loop_policy` 段（可选）**

```yaml
# 示例：pr_loop_demo.yaml 扩展
loop_policy:
  max_rounds: 5
  benign_streak_threshold: 3
  churn_matrix_path: "matrices/pr_loop_churn.yaml"
  converged_matrix_path: "matrices/pr_loop_phase_e.yaml"
```

**B. 解析逻辑（伪代码）**

```
resolve_effective_matrix_path(base_path, loop_state, matrix):
  if not loop_state or not matrix.data.get("loop_policy"):
    return base_path

  policy = matrix.data["loop_policy"]
  max_rounds = policy.get("max_rounds")
  threshold = policy.get("benign_streak_threshold")
  churn_path = policy.get("churn_matrix_path")
  converged_path = policy.get("converged_matrix_path")

  round_index = loop_state.round_index
  nit_only_streak = loop_state.nit_only_streak

  if max_rounds is not None and round_index >= max_rounds and churn_path:
    return churn_path
  if threshold is not None and nit_only_streak >= threshold and converged_path:
    return converged_path
  return base_path
```

**C. Gate 调用顺序**

1. 加载 base matrix（含 `loop_policy`）
2. 解析 `loop_state`
3. 若有 `loop_policy` 且 `loop_state` 存在，解析 `effective_matrix_path`
4. 用 `effective_matrix_path` 重新加载矩阵（若与 base 不同）
5. 后续 pipeline 使用 effective matrix

**D. 向后兼容**

- 无 `loop_policy`：`resolve_effective_matrix_path` 直接返回 `base_path`。
- 无 `loop_state`：同上。
- 现有非 loop 场景：不传 `loop_state`，行为不变。

---

## 四、问题 3：Demo 层 vs Core 层职责划分

### 4.1 应下沉到 Core 的逻辑

| 逻辑 | 当前位置 | 迁移目标 | 说明 |
|------|----------|----------|------|
| **根据 nit_only_streak 选择矩阵** | demo_phase_e.py L192-195 | `resolve_effective_matrix_path` | 收敛策略 |
| **根据 round_index >= max_rounds 选择矩阵** | demo_phase_e.py L295-324 | `resolve_effective_matrix_path` | churn 升级 |
| **loop_policy 配置** | demo 常量 (BENIGN_STREAK_THRESHOLD 等) | 矩阵 YAML `loop_policy` | 策略可配置化 |

### 4.2 应保留在 Orchestration 层的逻辑

| 逻辑 | 保留原因 |
|------|----------|
| **计算 nit_only_streak** | 依赖 `is_nit_only(comments)`，需要 ReviewComment 结构，属于 PR 域 |
| **计算 round_index** | 循环计数器，由编排层维护 |
| **构造 loop_state** | 将 `round_index`、`nit_only_streak` 组装成 dict 传入 context |
| **循环控制** (for round in range(max_rounds)) | 编排职责 |
| **根据决策终止循环** (ALLOW/DENY/HITL → return) | 编排职责 |
| **调用 AI Reviewer / AI Coding** | 域特定，与具体 agent 集成 |
| **extract_signals / is_nit_only** | PR 域的信号提取，非通用 |
| **validate_loop_state** | 可选保留在 examples，或作为 core 的轻量校验 |

### 4.3 边界示意

```
┌─────────────────────────────────────────────────────────────────┐
│ Orchestration (examples / 业务层)                                │
│ - 循环 for round in range(max_rounds)                            │
│ - 调用 AI Reviewer → 得到 comments                               │
│ - 调用 extract_signals, is_nit_only → 得到 nit_only_streak       │
│ - 维护 round_index                                               │
│ - 构造 loop_state = {round_index, nit_only_streak}                │
│ - 构造 DecisionRequest(context={"loop_state": loop_state})       │
│ - 调用 core_decide(req, matrix_path="matrices/pr_loop_demo")     │
│ - 根据 decision 终止或继续循环                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Core (gate.py)                                                   │
│ - 解析 loop_state                                                │
│ - 若 matrix 有 loop_policy：resolve_effective_matrix_path()      │
│ - 用 effective matrix 运行 pipeline                              │
│ - evaluate_loop_guard (可保持 no-op 或扩展)                      │
│ - 输出 Decision                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 五、问题 4：Loop State 应由谁维护

### 5.1 结论：**由 Orchestration 层维护，Core 只消费**

| 字段 | 维护者 | 说明 |
|------|--------|------|
| **round_index** | Orchestration | 循环计数器，每轮 +1 |
| **nit_only_streak** | Orchestration | 连续 benign 轮次，依赖 `is_nit_only(comments)` |
| **last_signal_fingerprint** | Orchestration（可选） | 未来用于去重、churn 检测等 |

### 5.2 真实 AI Reviewer / AI Coding 接入时

- **Orchestration**：实现「Loop Controller」
  - 每轮：调用 AI Reviewer → 得到 comments
  - 调用 `extract_signals`、`is_nit_only`（或等价逻辑）→ 更新 `nit_only_streak`
  - 维护 `round_index`
  - 构造 `loop_state`，调用 `core_decide`
  - 根据 decision 决定：继续下一轮 / 调用 AI Coding 修代码 / 终止

- **Core**：无状态，只根据当次请求的 `loop_state` + `loop_policy` 做矩阵解析和决策。

- **可选**：若希望 core 能「建议 max_rounds」，可在 `loop_policy` 中配置，由 orchestration 读取后作为循环上界。Core 不维护任何跨请求状态。

---

## 六、问题 5：最小迁移方案

### 6.1 新增 / 修改文件清单

| 操作 | 文件 | 内容 |
|------|------|------|
| **修改** | `src/core/matrix.py` | 新增 `resolve_effective_matrix_path(loop_state, matrix, base_path)`，或放在 `gate.py` / 新模块 |
| **修改** | `src/core/gate.py` | 在 load matrix 后、pipeline 前调用 `resolve_effective_matrix_path`，必要时重新 load |
| **修改** | `matrices/pr_loop_demo.yaml` | 新增 `loop_policy` 段 |
| **不改** | `src/core/loop_guard.py` | `evaluate_loop_guard` 保持 no-op（或后续扩展） |
| **不改** | `src/core/gate_stages.py` | 无变更 |

### 6.2 从 Demo 移动到 Core 的代码

| 逻辑 | 原位置 | 目标位置 |
|------|--------|----------|
| `nit_only_streak >= BENIGN_STREAK_THRESHOLD → converged_matrix` | demo_phase_e.py L192-195 | `resolve_effective_matrix_path` |
| `round_index >= max_rounds → churn_matrix` | demo_phase_e.py L295-324（第二次 core_decide 调用） | `resolve_effective_matrix_path` |
| `BENIGN_STREAK_THRESHOLD`, `MATRIX_PATH_*` 等常量 | demo_phase_e.py L44-49 | 矩阵 YAML `loop_policy` |

### 6.3 保留在 Demo 的代码

| 逻辑 | 文件 | 说明 |
|------|------|------|
| 循环 `for round_index in range(max_rounds)` | demo_phase_e.py | 编排 |
| `generate_review_comments` / `apply_fixes` | ai_reviewer_stub, ai_coding_stub | 域逻辑 |
| `extract_signals`, `is_nit_only` | signal_extractor.py | PR 域 |
| `nit_only_streak` 的更新逻辑 | demo_phase_e.py L183-186 | 依赖 comments |
| `loop_state` 的构造 | demo_phase_e.py L198-201 | 编排 |
| `validate_loop_state` | loop_state_validator.py | 可选保留 |
| `print_decision`, `log_round_state` | demo_phase_e.py | 展示与审计 |
| 根据 decision 终止循环 | demo_phase_e.py L273-293 | 编排 |

### 6.4 迁移后 Demo 的简化

**迁移前**：Demo 根据 `nit_only_streak` 和 `round_index` 选择 `matrix_path`，并在 max_rounds 时做一次额外的 `core_decide` 调用。

**迁移后**：Demo 只传 `matrix_path="matrices/pr_loop_demo.yaml"` 和 `context={"loop_state": loop_state}`，不再：
- 根据 `nit_only_streak` 切换 matrix_path
- 在 max_rounds 时单独调用 `core_decide` 并传入 churn 矩阵

Core 根据 `loop_policy` 自动完成矩阵解析。Demo 的循环逻辑可简化为：

```
for round_index in range(max_rounds):
  comments = generate_review_comments(...)
  nit_only_streak = update_streak(is_nit_only(comments), nit_only_streak)
  loop_state = {round_index, nit_only_streak}
  response = await core_decide(DecisionRequest(..., context={"loop_state": loop_state}),
                               matrix_path="matrices/pr_loop_demo.yaml")
  if response.decision in (ALLOW, DENY, HITL):
    return response
  pr_meta = apply_fixes(...)
# 若循环结束仍未 return：说明 max_rounds 时 core 已返回 HITL（因 core 内部解析到 churn 矩阵）
```

注意：若 `round_index` 在循环内取值为 `0..max_rounds-1`，则「max_rounds 达到」对应的是 `round_index == max_rounds - 1` 的下一轮。需在 `resolve_effective_matrix_path` 中明确约定：`round_index >= max_rounds` 时使用 churn 矩阵。Demo 可在最后一轮传入 `round_index=max_rounds`，或由 core 在「round_index == max_rounds - 1 且决策为 ONLY_SUGGEST」时，由 orchestration 再调一次 core 并传入 `round_index=max_rounds`。为简化，可约定：orchestration 在「循环自然结束」时，做一次 `core_decide(loop_state={round_index: max_rounds, ...}, matrix_path=...)`，此时 core 会解析到 churn 矩阵。这样 core 逻辑统一，无需区分「循环中」与「循环结束」两种调用。

**更简方案**：Orchestration 在每轮都传 `round_index`。当 `round_index == max_rounds - 1` 且 decision 为 ONLY_SUGGEST 时，不再继续循环，而是做一次「escalation 调用」：`loop_state={round_index: max_rounds}`，core 解析到 churn 矩阵并返回 HITL。这样「max_rounds 升级」仍由 core 完成，orchestration 只负责在适当时机发起这次调用。

---

## 七、总结

| 维度 | 方案 |
|------|------|
| **实现位置** | Matrix 解析步骤（`resolve_effective_matrix_path`），非独立 stage |
| **evaluate_loop_guard** | 保留，默认 no-op，可后续扩展 tighten 逻辑 |
| **策略配置** | 矩阵 YAML 的 `loop_policy` 段 |
| **Loop state 维护** | Orchestration 层维护，Core 只消费 |
| **下沉到 Core** | 矩阵选择逻辑（nit_only_streak、max_rounds） |
| **保留在 Demo** | 循环编排、信号提取、nit_only_streak 计算、AI 调用 |
| **最小改动** | 修改 matrix.py + gate.py，扩展 pr_loop_demo.yaml；demo 简化为只传 loop_state 和 base matrix_path |
