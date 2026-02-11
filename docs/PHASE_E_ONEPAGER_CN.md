# AI 责任网关：Phase E 一页纸（老师阅读版）

---

**🌐 Language / 语言**: [English](PHASE_E_ONEPAGER.md) | [中文](PHASE_E_ONEPAGER_CN.md)

---

## 1️⃣ 核心价值（一句话）

**Gate 解决的不是代码质量问题，而是自动化责任调度问题。**

当多个 AI 组件在循环中协作时，谁来决定"可以继续自动化"还是"必须人工介入"？这不是质量问题，是**责任边界问题**。

---

## 2️⃣ 老师的痛点

### 痛点 1：AI 循环失控
```
AI Reviewer: "建议修改这里..."
AI Coder: "已修改，但引入新问题..."
AI Reviewer: "又发现问题..."
AI Coder: "再修..."
(无限循环，没有终止条件)
```

### 痛点 2：自动化无限震荡
AI A 挑毛病 → AI B 改 → AI A 再挑 → AI B 再改，但改进越来越小（70% 是低价值 nit）。

### 痛点 3：高风险误放
敏感代码（安全边界、构建链）被 AI 自动批准，因为没有明确的"高风险必须人工审查"规则。

### 痛点 4：责任边界模糊
- 谁来决定停止？AI Reviewer？AI Coder？还是外部调度器？
- 如果出问题，谁负责？

**根本原因**：缺少**单一的责任调度权威**。

---

## 3️⃣ 三步设计路径

### Step 1: 信号有限化（Containment）

**问题**：AI 输出是无限的自然语言，无法枚举所有情况。

**解决**：将所有 AI 输出映射到**有限的信号集合**。
```
AI 原始评论 → 信号提取器 → {SECURITY_BOUNDARY, BUILD_CHAIN, BUG_RISK, LOW_VALUE_NITS}
未知 → UNKNOWN_SIGNAL（失效安全）
```

**为什么这样设计**：
- 有限集合 → 可枚举、可审计、可治理
- 失效安全 → 未知信号不会"钻空子"

### Step 2: 风险语义折叠（Tighten-Only）

**问题**：信号是平面的，无法表达"严重程度"。

**解决**：将信号折叠为**风险等级**（R0/R1/R2/R3），且**只收紧不放松**。

```
SECURITY_BOUNDARY / BUILD_CHAIN → R3（高风险）
BUG_RISK → R2（中风险）
LOW_VALUE_NITS → R0（良性）
```

**为什么这样设计**：
- **语义折叠**：无限信号 → 有限风险等级（域无关）
- **Tighten-Only**：风险只能上升，不会因为"看起来好转"就降级
- **可审计**：事后分析时，风险曲线单调递增，一目了然

### Step 3: 裁决权抽离到 Gate（Single Authority）

**问题**：谁有权说"停止"或"批准"？

**解决**：**只有 Gate 可以创建 Decision 枚举**，所有决策必须通过 `core_decide()`。

```
AI Reviewer → 信号 → 风险 → 矩阵规则 → Gate Decision（ALLOW / HITL / ONLY_SUGGEST / DENY）
                                 ↑
                            唯一裁决点
```

**为什么这样设计**：
- **单一权威**：没有"第二套决策逻辑"，避免责任分散
- **策略外置**：矩阵规则是 YAML 文件，可审计、可配置
- **域无关**：Gate 不知道 PR、GitHub、Git，只知道"风险等级 + 动作类型"

---

## 4️⃣ 风险 vs 收敛：正交的两个维度

### 风险等级（R0-R3）
**衡量**：当前改动有多危险

| 等级 | 含义 | 示例信号 |
|------|------|---------|
| R0 | 良性 | LOW_VALUE_NITS |
| R1 | 低风险 | - |
| R2 | 中风险 | BUG_RISK |
| R3 | 高风险 | SECURITY_BOUNDARY, BUILD_CHAIN |

### 收敛状态（nit_only_streak）
**衡量**：自动化是否值得继续

| 状态 | 含义 | 决策 |
|------|------|------|
| `< N` 轮良性 | 还未收敛 | ONLY_SUGGEST（继续） |
| `>= N` 轮良性 | 已收敛 | ALLOW（停止） |
| `max_rounds` | 效率耗尽 | HITL（升级） |

### 关键洞察：二者正交

**正交** = 相互独立，一个不决定另一个。

| 风险等级 | 收敛状态 | 决策 | 原因 |
|---------|---------|------|------|
| R3 | 任何 | **HITL** | 高风险不变量，永远不自动批准 |
| R2 | 任何 | ONLY_SUGGEST / HITL | 默认保守 |
| R0 | `< N` 轮 | ONLY_SUGGEST | 未收敛，继续 |
| R0 | `>= N` 轮 | **ALLOW** | 已收敛，可以批准 |
| R0 | `max_rounds` | **HITL** | 效率阈值，升级而非批准 |

**不变量**：
- R3 在任何矩阵下都 **HITL**，永远不 **ALLOW**
- R2 默认不 **ALLOW**（除非矩阵明确配置）
- `max_rounds` 触发的是 **升级**（HITL），不是 **批准**（ALLOW）

---

## 5️⃣ 测试到底证明什么

### 不变量 1：R3 永不 ALLOW
**测试**：`test_r3_never_allows_in_*_matrix`
**证明**：即使经过 100 轮收敛，高风险（R3）也必须人工审查，不会自动批准。

### 不变量 2：R2 默认保守
**测试**：`test_r2_default_conservative_*`
**证明**：中风险（R2）不会自动放行，保持 ONLY_SUGGEST 或 HITL。

### 不变量 3：矩阵切换不降风险
**测试**：`test_matrix_switching_does_not_relax_risk`
**证明**：从默认矩阵切换到收敛矩阵，不会把 R3 变成 ALLOW。

### 不变量 4：max_rounds 是效率阈值
**测试**：`test_churn_matrix_escapes_r0`
**证明**：即使低风险（R0），达到 max_rounds 后也升级到 HITL（效率耗尽），而非 ALLOW（质量证明）。

### 不变量 5：Deterministic Seed
**测试**：`test_demo_scenario_seeds_produce_deterministic_results`
**证明**：固定 seed → 可复现行为，每次运行 demo 输出相同。

### 不变量 6：Allowlist 防信号漂移
**测试**：`test_signals_allowlist_contains_all_used_signals`
**证明**：所有 demo 使用的信号都在 allowlist 中，防止"未知信号钻空子"。

---

## 6️⃣ 架构不变量总结

| 不变量 | 强度 | 如何强制 |
|--------|------|---------|
| **单一裁决源** | 强 | 只有 `gate.py` 可创建 Decision 枚举 |
| **Tighten-Only** | 强 | 风险只能上升，无法通过矩阵切换降级 |
| **R3 永不 ALLOW** | 强 | 所有矩阵的高风险规则都是 HITL |
| **R2 默认保守** | 中 | 矩阵需显式配置才能允许 R2 |
| **确定性** | 强 | 固定 seed → 可复现 |
| **域无关** | 强 | Gate 不知道 PR/GitHub，只看风险等级 |

---

## 7️⃣ 快速验证

```bash
# 运行演示（3 个场景，约 30 秒）
python examples/pr_gate_ai_review_loop/demo_phase_e.py

# 运行不变量测试（13 个测试，约 5 秒）
pytest tests/test_policy_invariants.py -v
```

**预期结果**：
- Scenario 1（良性）：3 轮后收敛 → ALLOW
- Scenario 2（震荡）：5 轮后效率耗尽 → HITL
- Scenario 3（高风险）：立即 → HITL

---

## 8️⃣ 设计原则总结

1. **责任边界清晰**：Gate 是唯一裁决源，没有"第二套决策逻辑"
2. **策略外置**：矩阵规则是 YAML，可审计、可配置
3. **风险收紧**：风险只能上升，不会自动"好转"
4. **正交设计**：风险（危险度）与收敛（是否值得继续）独立
5. **失效安全**：未知信号 → UNKNOWN_SIGNAL，不会钻空子
6. **零核心修改**：`src/core/*` 和 `src/evidence/*` 未修改，所有策略在 `examples/` 层

---

**Phase E 证明**：即使 AI 组件震荡或回归，只要**责任边界清晰**、**裁决权单一**，系统就保持稳定。
