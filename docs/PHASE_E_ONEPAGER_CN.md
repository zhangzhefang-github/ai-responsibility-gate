# AI 责任网关：Phase E 一页纸（老师阅读版）

---

**🌐 Language / 语言**: [English](PHASE_E_ONEPAGER.md) | [中文](PHASE_E_ONEPAGER_CN.md)

---

## 核心问题

**当概率系统（LLM）进入核心工程系统后，问题不再是"它能不能生成代码"，而是——**

### 谁对自动化结果负责？

在 AI Reviewer ↔ AI Coding 的自动循环中：

- 循环可能无限持续
- 风险可能在震荡中被忽视
- 没有人拥有"停止"的权威

**这不是代码质量问题，这是责任边界与注意力调度问题。**

---

## 1️⃣ 痛点：三种失控场景

### 自嗨型循环
70% 是低价值 nit/style，AI 能无限挑刺、无限修改，没有终止条件。

### 震荡型循环
反复出现中等风险（R2）问题，几轮后仍不下降，自动化持续震荡。

### 越界型改动
触碰 build/auth/security 边界（R3），但自动化还在继续，没有强制升级机制。

---

## 2️⃣ 与传统方案对比

| 传统 CI / Lint / Guardrails | AI 责任网关 |
|---------------------------|-------------|
| 判断对错 | 判断是否继续自动化 |
| 静态规则 | 风险语义折叠（tighten-only） |
| 不管循环 | 控制循环收敛 |
| 没有责任模型 | 单一裁决源 |

**这不是"又一个工具"，而是责任工程层面的架构升级。**

---

## 3️⃣ 核心设计理念

### 3.1 三权分立 + 二层结构

**三层权责**：

| 层级 | 角色 | 职责 | 禁止 |
|------|------|------|------|
| **证据层** | AI + Risk/Evidence | 生成 signals → 风险等级（R0-R3） | 禁止裁决 |
| **责任层** | Gate | 输出 ALLOW / ONLY_SUGGEST / HITL / DENY | 唯一裁决者 |
| **策略层** | Matrix Rules | 配置收敛阈值、风险策略 | 禁止修改 Decision |

**关键洞察**：Risk 层是"证据层"，Gate 是"责任层"。自动化系统再怎么循环，都不会把责任"漂移"给模型。

### 3.2 风险与收敛正交

| 维度 | 衡量 | 示例 |
|------|------|------|
| **风险** | 这轮改动"危险不危险" | R0（良性）→ R3（高风险） |
| **收敛** | 自动化是否还值得继续 | `< N` 轮 / `>= N` 轮 / `max_rounds` |

**二者不是一回事**：
- R3 永远 HITL（无论收敛与否）
- R0 也可能继续循环（如果未达收敛阈值）
- `max_rounds` 是效率阈值，不是"质量证明"

### 3.3 Tighten-only（风险单调，只能收紧）

风险与策略只能"更严"，不能"为了收敛而放松"。

**防止**：AI 循环把系统越跑越松，最终误放高风险。

---

## 4️⃣ Phase E 要证明什么

Phase E 是一套**治理演示（Governance Demonstration）**，证明 3 件事：

### 证明 1：单一决策源
所有决策都来自 `core_decide()`，Demo 层不产生第二套 Decision。

### 证明 2：收敛点可配置
通过 matrix 切换实现 "N 轮 benign 后 ALLOW"，无需改 core。

### 证明 3：震荡不失控
即使 AI 自嗨挑刺，系统也会在 `max_rounds` 或高风险时终止。

**硬约束**：✅ 不修改 `src/core/*`、✅ 不修改 `src/evidence/*`

---

## 5️⃣ 架构与数据流

```
AI Reviewer comments
        ↓ (extract)
Signals (有限集合 + allowlist)
        ↓ (risk evidence: tighten-only)
Risk Level (R0-R3) [Explain-only, 证据层]
        ↓ (policy in YAML)
Decision Matrix (matrix_path)
        ↓ (唯一裁决, 责任层)
core_decide() → ALLOW / ONLY_SUGGEST / HITL / DENY
```

---

## 6️⃣ 三步设计路径

### Step 1：信号有限化
AI 输出 → 有限信号集合 → allowlist 过滤 → UNKNOWN_SIGNAL（失效安全）

### Step 2：风险语义折叠
Signals → Risk（R0-R3），tighen-only，只解释不裁决

### Step 3：裁决权抽离到 Gate
只有 Gate 可以创建 Decision 枚举，所有决策必须通过 `core_decide()`

---

## 7️⃣ 三类典型场景

### 场景 A：Benign
**signals**: LOW_VALUE_NITS → **risk**: R0 → **策略**: N 轮后 ALLOW

### 场景 B：Loop-churn
**特征**: R2 震荡不降 → **策略**: max_rounds → HITL（强制止损）

### 场景 C：High-risk
**signals**: SECURITY_BOUNDARY / BUILD_CHAIN → **risk**: R3 → **策略**: 立即 HITL

---

## 8️⃣ 测试到底证明什么

### Policy-lint（矩阵不变量）
- `test_r3_never_allows_*`: R3 永远不 ALLOW（遍历所有矩阵）
- `test_churn_matrix_escapes_r0`: max_rounds 是效率阈值，强制升级 HITL

### Demo Contract Tests（链路契约）
- `test_demo_scenario_seeds_*`: 固定 seed → 可复现
- `test_signals_allowlist_*`: 防止信号漂移

### 审计日志（可观测性）
每轮 JSON 日志：round、signals、risk、matrix_path、decision、reason

---

## 9️⃣ 痛点 → 解决方案（3 行）

| 痛点 | 解决方案 |
|------|---------|
| AI 生成越来越多，review 看不过来 | 收敛阈值可配置，低风险自动收敛 |
| 不能把责任交给 AI | Gate 是唯一裁决源，AI 只建议 |
| 自动化无限循环 / 误放高风险 | R3 永不 ALLOW + max_rounds 强制升级 |

**一句话总结**：

> 把"是否继续自动化"的权力，从 AI prompt 中抽离出来，交给可审计、tighten-only 的 Gate。AI 只负责建议；Gate 负责止损；人类负责最终责任。

---

## 🔟 快速验证

```bash
# 运行演示（3 个场景，约 30 秒）
python examples/pr_gate_ai_review_loop/demo_phase_e.py

# 运行不变量测试（13 个测试，约 5 秒）
pytest tests/test_policy_invariants.py -v
```

**预期**：Scenario 1（3 轮收敛）、Scenario 2（5 轮升级）、Scenario 3（立即 HITL）

---

## 1️⃣1️⃣ 架构不变量（7 条）

| 不变量 | 强度 |
|--------|------|
| 单一裁决源 | 强 |
| 三权分立（证据层/责任层/策略层） | 强 |
| Tighten-Only | 强 |
| R3 永不 ALLOW | 强 |
| R2 默认保守 | 中 |
| 确定性 | 强 |
| 域无关 | 强 |

---

**Phase E 证明**：即使 AI 组件震荡或回归，只要**责任边界清晰**、**裁决权单一**、**风险收紧**，系统就保持稳定。
