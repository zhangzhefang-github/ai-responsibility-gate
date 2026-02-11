# AI 责任网关：Phase E 一页纸（老师阅读版）

---

**🌐 Language / 语言**: [English](PHASE_E_ONEPAGER.md) | [中文](PHASE_E_ONEPAGER_CN.md)

---

## 目标一句话

**在 AI Reviewer ↔ AI Coding 的自动循环里，解决"谁来负责说停"的问题。**

Gate 不是判断代码对不对，而是判断**"还值不值得继续自动化"**。

这不是代码质量问题，是**责任边界问题**。

---

## 1️⃣ 痛点：三种失控场景

### 自嗨型循环
70% 是低价值 nit/style，AI 能无限挑刺、无限修改，没有终止条件。

### 震荡型循环
反复出现中等风险（R2）问题，几轮后仍不下降，自动化持续震荡。

### 越界型改动
触碰 build/auth/security 边界（R3），但自动化还在继续，没有强制升级机制。

**核心问题**：什么时候继续自动化？什么时候必须升级人工？这叫**注意力调度 / 责任边界**问题。

---

## 2️⃣ 核心设计理念

### 2.1 三权分立：生成权 / 证据权 / 裁决权

| 角色 | 权力 | 禁止 |
|------|------|------|
| **AI** | 产生 signals 与 evidence | 禁止裁决 |
| **Risk/Evidence** | 信号 → 风险等级（R0-R3） | 只解释，不裁决 |
| **Gate** | 输出 ALLOW / ONLY_SUGGEST / HITL / DENY | 唯一裁决者 |

**保证**：自动化系统再怎么循环，都不会把责任"漂移"给模型。

### 2.2 风险与收敛正交（最关键洞察）

| 维度 | 衡量 | 示例 |
|------|------|------|
| **风险** | 这轮改动"危险不危险" | R0（良性）→ R3（高风险） |
| **收敛** | 自动化是否还值得继续 | `< N` 轮 / `>= N` 轮 / `max_rounds` |

**二者不是一回事**：
- R3 永远 HITL（无论收敛与否）
- R0 也可能继续循环（如果未达收敛阈值）
- `max_rounds` 是效率阈值，不是"质量证明"

### 2.3 Tighten-only（风险单调，只能收紧）

风险与策略只能"更严"，不能"为了收敛而放松"。

**防止**：AI 循环把系统越跑越松，最终误放高风险。

---

## 3️⃣ Phase E 要证明什么

Phase E 是一套**治理演示（Governance Demonstration）**，证明 3 件事：

### 证明 1：单一决策源
所有决策都来自 `core_decide()`，Demo 层不产生第二套 Decision。

### 证明 2：收敛点可配置
通过 matrix 切换实现 "N 轮 benign 后 ALLOW"，无需改 core。

### 证明 3：震荡不失控
即使 AI 自嗨挑刺，系统也会在 `max_rounds` 或高风险时终止。

**硬约束**：
- ✅ 不修改 `src/core/*`
- ✅ 不修改 `src/evidence/*`

---

## 4️⃣ 架构与数据流

```
AI Reviewer comments
        ↓ (extract)
Signals (有限集合 + allowlist)
        ↓ (risk evidence: tighten-only)
Risk Level (R0-R3) [Explain-only]
        ↓ (policy in YAML)
Decision Matrix (matrix_path)
        ↓ (唯一裁决)
core_decide() → ALLOW / ONLY_SUGGEST / HITL / DENY
```

**关键点**：
- Risk 层只解释，不裁决
- Policy 层可配置（YAML 矩阵）
- Gate 层唯一裁决

---

## 5️⃣ 三步设计路径

### Step 1：信号有限化（Containment）

**问题**：AI 输出是无限的自然语言，无法枚举所有情况。

**解决**：review comments → extract → normalize（allowlist）

```
AI 原始评论 → 信号提取器 → {SECURITY_BOUNDARY, BUILD_CHAIN, BUG_RISK, LOW_VALUE_NITS}
未知 → UNKNOWN_SIGNAL（fail-closed）
```

**为什么这样设计**：
- 有限集合 → 可枚举、可审计、可治理
- 失效安全 → 未知信号不会"钻空子"

### Step 2：风险语义折叠（Tighten-Only）

**问题**：信号是平面的，无法表达"严重程度"。

**解决**：signals → risk evidence（R0~R3）

```
SECURITY_BOUNDARY / BUILD_CHAIN → R3（高风险）
BUG_RISK → R2（中风险）
LOW_VALUE_NITS → R0（良性）
```

**为什么这样设计**：
- **语义折叠**：无限信号 → 有限风险等级（域无关）
- **Tighten-Only**：风险只能上升，不会因为"看起来好转"就降级
- **可审计**：事后分析时，风险曲线单调递增，一目了然

### Step 3：裁决权抽离到 Gate（Single Authority）

**问题**：谁有权说"停止"或"批准"？

**解决**：**只有 Gate 可以创建 Decision 枚举**，所有决策必须通过 `core_decide()`。

```
AI Reviewer → 信号 → 风险 → 矩阵规则 → Gate Decision
                                 ↑
                            唯一裁决点
```

**为什么这样设计**：
- **单一权威**：没有"第二套决策逻辑"，避免责任分散
- **策略外置**：矩阵规则是 YAML 文件，可审计、可配置
- **域无关**：Gate 不知道 PR/GitHub，只知道"风险等级 + 动作类型"

---

## 6️⃣ 三类典型场景（痛点覆盖）

### 场景 A：Benign（低风险风格问题）

**signals**：LOW_VALUE_NITS
**risk**：R0
**策略**：连续 N 轮 benign 才 ALLOW（治理阈值，而非风险逻辑）

**价值**：减少人力浪费，避免"第一轮就自嗨放行"。

### 场景 B：Loop-churn（中风险震荡）

**特征**：多轮仍 R2，不下降
**策略**：不自动放行；达到 `max_rounds` → HITL

**价值**：让系统能"强制止损"，不无限循环。

### 场景 C：High-risk（触碰关键边界）

**signals**：SECURITY_BOUNDARY / BUILD_CHAIN
**risk**：R3
**策略**：立即 HITL

**价值**：明确责任边界，模型不承担高风险决策。

---

## 7️⃣ 测试到底证明了什么

### 7.1 Policy-lint（矩阵不变量测试）

**目的**：证明任何矩阵都无法把高风险放行。

| 测试 | 证明的不变量 |
|------|-------------|
| `test_r3_never_allows_*` | R3 永远不 ALLOW（遍历所有矩阵） |
| `test_r2_default_conservative_*` | R2 默认不 ALLOW（除非显式配置） |
| `test_matrix_switching_*` | matrix 切换不放松风险底线 |
| `test_churn_matrix_escapes_r0` | `max_rounds` 是效率阈值，强制升级 HITL |

### 7.2 Demo Contract Tests（链路契约测试）

**目的**：证明演示脚本没有旁路 core、且全链路可复现。

| 测试 | 证明什么 |
|------|---------|
| `test_reviewer_stub_produces_extractable_signals` | reviewer stub 输出可被 extractor 抽取 |
| `test_normalize_signals_is_deterministic` | normalize 相同输入相同输出 |
| `test_is_nit_only_correctly_identifies_benign_rounds` | 能正确识别 benign round |
| `test_demo_scenario_seeds_produce_deterministic_results` | 三个 seed（42/43/44）可复现 |
| `test_signals_allowlist_contains_all_used_signals` | allowlist 覆盖所有 demo 信号 |

### 7.3 审计日志（可观测性）

每轮输出 JSON（sorted keys），记录：
- round、signals、risk、benign_streak
- matrix_path、decision、reason

**目的**：给老师/评审一个"能回放、能追责"的证据面板。

---

## 8️⃣ 为什么能解决老师的痛点

| 痛点 | 解决方案 |
|------|---------|
| AI 生成越来越多，review 看不过来 | 收敛阈值可配置，低风险自动收敛 |
| 不能把责任交给 AI | Gate 是唯一裁决源，AI 只建议 |
| 自动化无限循环 | `max_rounds` 强制升级 HITL |
| 误放高风险 | R3 永不 ALLOW，不变量保护 |

**一句话总结**：

> 把"是否继续自动化"的权力，从 AI prompt 中抽离出来，交给可审计、tighten-only 的 Gate。AI 只负责建议；Gate 负责止损；人类负责最终责任。

---

## 9️⃣ 快速验证

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

## 🔟 架构不变量总结

| 不变量 | 强度 | 如何强制 |
|--------|------|---------|
| **单一裁决源** | 强 | 只有 `gate.py` 可创建 Decision 枚举 |
| **三权分立** | 强 | AI 生成、Risk 解释、Gate 裁决 |
| **Tighten-Only** | 强 | 风险只能上升，无法通过矩阵切换降级 |
| **R3 永不 ALLOW** | 强 | 所有矩阵的高风险规则都是 HITL |
| **R2 默认保守** | 中 | 矩阵需显式配置才能允许 R2 |
| **确定性** | 强 | 固定 seed → 可复现 |
| **域无关** | 强 | Gate 不知道 PR/GitHub，只看风险等级 |

---

## 1️⃣1️⃣ 可选演进方向（非 Phase E 目标）

- **Phase F**：把 convergence 从 `nit_only_streak` 升级为 ConvergenceSignals（趋势/重复/下降性）
- **Property-based fuzz**：随机信号序列验证"max_rounds 必终止"
- **Matrix schema 校验**：防止 YAML 写错导致策略误配

---

**Phase E 证明**：即使 AI 组件震荡或回归，只要**责任边界清晰**、**裁决权单一**、**风险收紧**，系统就保持稳定。
