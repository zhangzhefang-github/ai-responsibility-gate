# 小循环治理 / Loop Guard / Reviewer-Coder Loop 相关实现扫描报告

> 扫描时间：2025-03-10  
> 扫描范围：loop, loop_guard, loop policy, tighten, repeated issue, reopen, iteration, multi-turn, reviewer, coder, churn, convergence, stop condition, escalation, hitl

---

## 1. 相关文件列表

| 文件 | 相关度 | 关键词命中 |
|------|--------|------------|
| `src/core/loop_guard.py` | 高 | loop, loop_guard, loop_state, nit_only_streak, round_index |
| `src/core/gate.py` | 高 | loop_guard, loop_state, tighten, HITL, escalation |
| `src/core/gate_helpers.py` | 中 | tighten_one_step, _hitl_suggested |
| `src/core/gate_stages.py` | 中 | tighten_one_step |
| `src/evidence/risk.py` | 中 | loop_state, signals (R0-R3 for loop) |
| `examples/pr_gate_ai_review_loop/*` | 高 | 整个目录为 loop 治理 demo |
| `matrices/pr_loop_demo.yaml` | 高 | PR loop 默认矩阵 |
| `matrices/pr_loop_phase_e.yaml` | 高 | 收敛后矩阵 |
| `matrices/pr_loop_churn.yaml` | 高 | churn 升级矩阵 |
| `docs/PHASE_E_ONEPAGER_CN.md` | 高 | loop-churn, convergence, tighten |
| `docs/PHASE_E_ONEPAGER.md` | 高 | convergence, stop condition |
| `tests/test_loop_guard_no_relax.py` | 高 | loop_guard, tighten-only |
| `tests/test_policy_invariants.py` | 高 | churn, convergence |
| `tests/test_demo_contract_smoke.py` | 高 | nit_only, churn |
| `cases/hitl_multi_turn.json` | 中 | multi-turn |
| `ARCHITECTURAL_AUDIT_REPORT.md` | 中 | stop condition（建议） |
| `PR_GATE_FEASIBILITY_ASSESSMENT.md` | 中 | stop condition（建议） |

---

## 2. 各文件相关代码大意

### 2.1 Core 层

#### `src/core/loop_guard.py`（约 92 行）

- **LoopState**：`round_index`, `nit_only_streak`, `last_signal_fingerprint`
- **parse_loop_state()**：将 `context["loop_state"]` 解析为 `LoopState`，失败返回 None
- **evaluate_loop_guard()**：默认实现为 **no-op**，直接返回 `decision_index`，仅写 trace
- 设计：域无关、tighten-only 安全、L0 可用

#### `src/core/gate.py`（约 262–278 行）

- 从 `req.context["loop_state"]` 解析 `loop_state`
- Stage 5.5：调用 `evaluate_loop_guard(decision_index, loop_state, trace)`
- 调用点强制 tighten-only：若 `new_decision_index < decision_index` 则忽略 relax
- HITL 相关：Timeout Guard 的 HITL overlay（证据超时升级），与 loop 无关

#### `src/core/gate_helpers.py`

- **tighten_one_step()**：`min(current_index + steps, 3)`，用于收紧决策
- **_hitl_suggested**：证据超时聚合标签，用于 Timeout Guard，非 loop 逻辑

#### `src/core/gate_stages.py`

- **tighten_one_step**：在 missing evidence、conflict resolution、routing weak signal 等阶段使用
- 无 loop 相关逻辑

#### `src/evidence/risk.py`（约 79–99 行）

- 支持 `structured_input["signals"]`：`SECURITY_BOUNDARY`, `BUILD_CHAIN` → R3；`BUG_RISK` → R2；`LOW_VALUE_NITS` → R0
- 注释说明：Evidence 层不读取 `loop_state`，不承载收敛策略

---

### 2.2 Examples 层（`examples/pr_gate_ai_review_loop/`）

#### `pr_gate.py`

- **decide_pr()**：独立 PR 决策逻辑，**不调用 core_decide**
- 规则：Stop Condition（连续 N 轮 nit_only → ALLOW）、Security/Build → HITL、Bug → HITL、nit_only → ONLY_SUGGEST
- `stop_condition_applied` 字段：当前始终为 False（未实现收敛判断）

#### `demo_phase_e.py`

- **run_scenario()**：完整 review → coding → review 循环
- 收敛策略：`nit_only_streak >= BENIGN_STREAK_THRESHOLD` 时切换 `matrix_path` 到 `pr_loop_phase_e.yaml`
- max_rounds 达到时：切换 `matrix_path` 到 `pr_loop_churn.yaml`，强制 HITL
- 所有决策来自 `core_decide()`，demo 层只做 matrix 切换

#### `demo.py`

- 早期 demo，同样用 `loop_state` + `core_decide`，收敛逻辑在 demo 层

#### `signal_extractor.py`

- **extract_signals()**：ReviewComment → AISignal
- **is_nit_only()**：判断是否全是 style/nit 且 severity ≤ 2

#### `loop_state_validator.py`

- **validate_loop_state()**：校验 `round_index`, `nit_only_streak` 类型与范围
- 仅 examples 层使用，不改 core

#### `ai_reviewer_stub.py`

- **generate_review_comments()**：`round_index` 越高 nit 越多（模拟越改越糟）

#### `models.py`

- PRMeta, ReviewComment, AISignal, PRDecision, PRDecisionResponse
- `stop_condition_applied` 字段（当前未真正使用）

---

### 2.3 矩阵配置

| 矩阵 | 用途 | defaults |
|------|------|----------|
| `pr_loop_demo.yaml` | 默认循环 | Information: ONLY_SUGGEST |
| `pr_loop_phase_e.yaml` | 收敛后 | Information: ALLOW（R0 可 ALLOW） |
| `pr_loop_churn.yaml` | max_rounds 达到 | 全部 HITL |

---

### 2.4 测试

- **test_loop_guard_no_relax.py**：验证 LoopGuard 尝试 relax 时，gate 调用点会拦截
- **test_policy_invariants.py**：R3 永不 ALLOW、churn 矩阵 R0 也升级 HITL、收敛矩阵 R0 可 ALLOW
- **test_demo_contract_smoke.py**：`is_nit_only`、churn 矩阵升级 HITL
- **cases/hitl_multi_turn.json**：多轮对话（信息查询 → 操作请求）升级到 HITL

---

## 3. 已可复用的部分

| 组件 | 位置 | 复用方式 |
|------|------|----------|
| **LoopState 模型** | `src/core/loop_guard.py` | 通过 `context["loop_state"]` 传入，含 `round_index`, `nit_only_streak` |
| **parse_loop_state** | `src/core/loop_guard.py` | 解析 dict → LoopState，失败返回 None |
| **evaluate_loop_guard 钩子** | `src/core/loop_guard.py` + `gate.py` | 可替换为自定义实现，gate 强制 tighten-only |
| **tighten_one_step** | `src/core/gate_helpers.py` | 决策收紧工具函数 |
| **信号 → 风险映射** | `src/evidence/risk.py` | `structured_input["signals"]` → R0/R2/R3 |
| **pr_loop 矩阵** | `matrices/pr_loop_*.yaml` | 默认 / 收敛 / churn 三阶段策略 |
| **demo_phase_e 流程** | `examples/pr_gate_ai_review_loop/demo_phase_e.py` | 完整 loop 编排：nit_only_streak、matrix 切换、max_rounds 升级 |
| **signal_extractor** | `signal_extractor.py` | ReviewComment → AISignal，`is_nit_only()` |
| **loop_state_validator** | `loop_state_validator.py` | 调用 core 前校验 loop_state |

---

## 4. 雏形 / 占位 / no-op 部分

| 组件 | 状态 | 说明 |
|------|------|------|
| **evaluate_loop_guard** | **no-op** | 默认实现直接返回 `decision_index`，不根据 loop_state 做任何收紧 |
| **pr_gate.decide_pr** | **独立实现** | 不调用 core_decide，与 core 决策流水线脱节 |
| **stop_condition_applied** | **占位** | 在 pr_gate 和 models 中存在，但始终为 False |
| **core 内 stop condition** | **未实现** | `gate_stages` 无 `apply_stop_condition`，收敛逻辑全在 demo 层 |
| **last_signal_fingerprint** | **预留** | LoopState 中有字段，当前未使用 |

---

## 5. 做 coding-reviewer loop governance 时，现有基础最接近哪一部分

**最接近：`examples/pr_gate_ai_review_loop/demo_phase_e.py` + 三套 pr_loop 矩阵**

原因：

1. **完整闭环**：review → coding → review 循环、`nit_only_streak`、matrix 切换、max_rounds 升级
2. **策略在矩阵**：收敛 / churn 通过 YAML 配置，不改 core
3. **单一决策源**：全部通过 `core_decide()`
4. **风险与收敛正交**：R3 永远 HITL，R0 在收敛矩阵可 ALLOW，churn 矩阵强制 HITL

**差距与扩展点：**

1. **core 内 Loop Guard 为 no-op**：收敛逻辑在 demo 层通过 matrix 切换实现，core 的 `evaluate_loop_guard` 未参与
2. **收敛策略在 demo 层**：`nit_only_streak >= 3` 切换 matrix 是硬编码，若要在 core 内实现，需扩展 `evaluate_loop_guard` 或新增 stage
3. **pr_gate.py 与 core 脱节**：`decide_pr` 是另一套决策逻辑，若要用 core 做 PR loop，应参考 demo_phase_e 的调用方式，而不是 pr_gate

**推荐路径：**

- 短期：直接复用 `demo_phase_e.py` 的流程和矩阵，接入真实 AI Reviewer/Coder
- 中期：在 core 中实现 `evaluate_loop_guard` 的非 no-op 版本（如根据 `nit_only_streak`、`round_index` 做收紧），或新增 `apply_stop_condition` stage，使收敛策略可配置且可审计
