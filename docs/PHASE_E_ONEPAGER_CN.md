# AI 责任网关：Phase E 一页纸

---

**🌐 Language / 语言**: [English](PHASE_E_ONEPAGER.md) | [中文](PHASE_E_ONEPAGER_CN.md)

---

## 问题陈述

**AI 审查 × AI 编码循环无法收敛**

当 AI 审查者和 AI 编码代理在循环中交互时：
- 审查者建议更改（70% 是低价值的 nit/style）
- 编码者实现更改，有时引入新问题
- 循环无限持续，无法收敛
- 没有明确的权威来说"停止"或"批准"

**根本原因**：注意力调度问题 - 谁来决定循环何时"足够好"？

---

## 解决方案架构

**网关作为单一决策权威**

```
AI 审查者 → 信号 → 风险证据 → 矩阵规则 → 网关决策
     ↑                                                        │
     └────────────────────────────────────────────────────────┘
                      (唯一终止点)
```

### 核心组件

1. **信号字典**（有限的、可审计的）
   - `SECURITY_BOUNDARY`、`BUILD_CHAIN`、`BUG_RISK`、`LOW_VALUE_NITS` 等
   - 所有 AI 输出映射到这些信号
   - 未知 → `UNKNOWN_SIGNAL`（失效安全）

2. **风险证据**（仅收紧、未修改）
   - 信号 → 风险等级（R0/R1/R2/R3）
   - 语义折叠，永不放松
   - **未修改 `src/evidence/risk.py`**

3. **矩阵规则**（策略层）
   - `(risk_level, action_type) → decision`
   - R3 + READ → HITL（高风险升级）
   - R0 + READ → ALLOW（收敛，通过矩阵路径切换）
   - 默认 → ONLY_SUGGEST（继续循环）

4. **矩阵路径切换**（演示层）
   - 第 1-2 轮：`matrix_path="matrices/pr_loop_demo.yaml"` → ONLY_SUGGEST
   - 第 3+ 轮：`matrix_path="matrices/pr_loop_phase_e.yaml"` → ALLOW

5. **核心网关**（单一权威、未修改）
   - **唯一**创建 Decision 枚举的组件
   - 接受 `matrix_path` 参数（现有 API）
   - 强制仅收紧（无法放松）
   - 确定性、可审计、仓库无关

---

## 收敛策略（可配置）

### 基于阈值的收敛

```
第 1 轮：LOW_VALUE_NITS → R0 → matrix=pr_loop_demo.yaml → ONLY_SUGGEST
第 2 轮：LOW_VALUE_NITS → R0 → matrix=pr_loop_demo.yaml → ONLY_SUGGEST
第 3 轮：LOW_VALUE_NITS → R0 → matrix=pr_loop_phase_e.yaml → ALLOW
```

### 为什么有效

- **N 可配置**：更改演示代码中的 `BENIGN_STREAK_THRESHOLD`
- **决策由策略驱动**：矩阵路径 → 矩阵 → 决策
- **未修改核心**：`src/core/*` 和 `src/evidence/*` 未更改
- **网关是最终权威**：所有决策通过 `core_decide(matrix_path=...)`

---

## 演示证据

### 良性场景（收敛）

```
第 1 轮：Matrix=pr_loop_demo.yaml, Signals=[LOW_VALUE_NITS], Risk=R0, Decision=ONLY_SUGGEST
第 2 轮：Matrix=pr_loop_demo.yaml, Signals=[LOW_VALUE_NITS], Risk=R0, Decision=ONLY_SUGGEST
第 3 轮：Matrix=pr_loop_phase_e.yaml, Signals=[LOW_VALUE_NITS], Risk=R0, Decision=ALLOW
✅ 网关终止循环（3 轮良性后收敛）
```

### 高风险场景（升级）

```
第 1 轮：Matrix=pr_loop_demo.yaml, Signals=[SECURITY_BOUNDARY, BUILD_CHAIN], Risk=R3, Decision=HITL
⚠️  网关终止循环（检测到高风险信号）
```

---

## 架构不变量

| 不变量 | 如何强制执行 |
|--------|-------------|
| **单一决策权威** | 只有 `gate.py` 可以创建 Decision 枚举 |
| **仅收紧** | 如果尝试放松，`evaluate_loop_guard()` 更改将被忽略 |
| **仓库无关** | 核心不知道 PR/GitHub 概念 |
| **确定性** | 固定种子 → 可重现的行为 |
| **可审计** | 所有规则在 YAML 中，可跟踪日志 |
| **无核心修改** | 所有策略在 examples/ 层，使用现有的 `matrix_path` 参数 |

---

## 关键设计决策

### 1. 矩阵路径切换（vs Profile 或策略信号）

**问题**：如何在不修改 `src/core/*` 或 `src/evidence/*` 的情况下实现"N 轮 → ALLOW"？

**解决方案**：演示层根据 `nit_only_streak` 切换 `matrix_path`：
- `< N 轮`：`matrix_path="matrices/pr_loop_demo.yaml"` → ONLY_SUGGEST
- `>= N 轮`：`matrix_path="matrices/pr_loop_phase_e.yaml"` → ALLOW

**好处**：
- 不修改核心或证据层
- 使用现有的 `core_decide(matrix_path=...)` API
- 所有策略配置保留在 examples/

### 2. 为什么分离风险 + 策略？

**风险层**：语义折叠（信号 → 风险），域无关，**未更改**。
**策略层**：域特定规则（矩阵 → 决策），每个环境可配置。

### 3. 风险 vs 收敛：正交维度

**风险等级**（`R0`-`R3`）测量**当前更改有多危险**：
- `R0`：良性（只有低价值的 nit/style）
- `R1`：低风险（小问题）
- `R2`：中等风险（bug 风险、结构性问题）
- `R3`：高风险（安全边界、构建链妥协）

**收敛状态**（`nit_only_streak`）测量**自动化是否值得**：
- `< N` 连续良性轮：继续循环（ONLY_SUGGEST）
- `>= N` 连续良性轮：终止（ALLOW）

**关键洞察**：这些是**正交维度**：
- 高风险（`R3`）应该**始终**升级到 HITL，无论收敛状态如何
- 低风险（`R0`）如果尚未达到收敛可能仍会继续循环
- `matrix_path` 是**策略选择机制**，不是风险替代品

**不变量**（必须适用于所有矩阵）：

| 不变量 | 基本原理 |
|--------|----------|
| **R3 → HITL（永不 ALLOW）** | 高风险更改始终需要人工审查，无论经过多少轮 |
| **R2 → 默认保守** | 除非明确配置，否则中等风险更改不应自动允许 |
| **仅收紧永不违反** | 矩阵切换无法从较高风险放松到较低风险 |
| **max_rounds 是效率阈值，不是质量证明** | 达到 max_rounds 触发升级（HITL），而非自动批准 |

**决策矩阵示例**：

| 风险等级 | 收敛 | 矩阵路径 | 决策 |
|---------|------|----------|------|
| R0 | `< N` 轮 | `pr_loop_demo.yaml` | ONLY_SUGGEST |
| R0 | `>= N` 轮 | `pr_loop_phase_e.yaml` | ALLOW |
| R1 | 任何 | 任何 | ONLY_SUGGEST（保守） |
| R2 | 任何 | 任何 | ONLY_SUGGEST 或 HITL（默认永不 ALLOW） |
| R3 | 任何 | 任何 | HITL（不变量，永不 ALLOW） |
| 任何 | `max_rounds` | `pr_loop_churn.yaml` | HITL（效率升级） |

### 4. 为什么"仅收紧"？

**安全性**：永远不会自动从高风险放松到低风险。
**可审计性**：风险只能增加，使事后分析更简单。

### 5. 为什么使用有限信号字典？

**可控性**：AI 输出映射到有限集合（不会爆炸）。
**治理**：每个信号都有证据示例文档。
**可维护性**：添加新信号是结构化过程（YAML + 可选矩阵规则）。

---

## 运行演示

```bash
# 运行演示
python examples/pr_gate_ai_review_loop/demo_phase_e.py

# 运行测试
pytest tests/test_demo_contract_smoke.py -v
```

### 预期测试结果

```
tests/test_demo_contract_smoke.py::test_signals_allowlist_contains_all_used_signals PASSED
tests/test_demo_contract_smoke.py::test_reviewer_stub_produces_extractable_signals PASSED
tests/test_demo_contract_smoke.py::test_is_nit_only_correctly_identifies_benign_rounds PASSED
tests/test_demo_contract_smoke.py::test_normalize_signals_is_deterministic PASSED
tests/test_demo_contract_smoke.py::test_normalize_signals_handles_edge_cases PASSED
tests/test_demo_contract_smoke.py::test_high_risk_scenario_produces_expected_signals PASSED
tests/test_demo_contract_smoke.py::test_demo_scenario_seeds_produce_deterministic_results PASSED
```

---

## 修改/创建的文件

| 文件 | 更改 |
|------|------|
| `examples/pr_gate_ai_review_loop/demo_phase_e.py` | 新增：矩阵路径切换 |
| `matrices/pr_loop_phase_e.yaml` | 新增：收敛状态矩阵 |
| `tests/test_demo_contract_smoke.py` | 新增：信号链测试 |
| `examples/pr_gate_ai_review_loop/README.md` | 修改：Phase E 部分 |
| `examples/pr_gate_ai_review_loop/ai_reviewer_stub.py` | 修改：确定性信号生成 |
| `docs/PHASE_E_ONEPAGER_CN.md` | 新增：本文档（中文版） |

**重要**：`src/core/*` 和 `src/evidence/*` 未修改。

---

## 总结

**Phase E 证明**：即使 AI 组件震荡或回归，系统仍保持稳定，因为：
1. 网关是**唯一**决策权威
2. 收敛通过矩阵路径切换**可配置**
3. 架构强制执行**仅收紧**安全
4. 所有决策都是**确定性**和**可审计**的
5. **无需修改** `src/core/*` 或 `src/evidence/*`

**结果**：一个可扩展的 AI 自动化责任网关，同时保持对高风险决策的人工控制。
