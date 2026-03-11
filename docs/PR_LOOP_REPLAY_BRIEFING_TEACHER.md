# PR Loop 治理验证汇报（老师版）

**AI Responsibility Gate – 问题 → 机制 → 验证**

> 3 页精简版，面向快速阅读场景；完整技术版（含架构、实现状态、8 问）见 [PR_LOOP_REPLAY_BRIEFING.md](PR_LOOP_REPLAY_BRIEFING.md)。

---

## 第 1 页：问题

### PR Loop 为什么会卡住？

AI coding + AI reviewer 会产生 **review churn**：

```
AI Coding → 提 PR
AI Reviewer → nit（小问题）
AI Coding → 改
AI Reviewer → 新 nit
AI Coding → 改
AI Reviewer → 新 nit
...
```

**结果**：PR 无限循环、reviewer 吹毛求疵、maintainer 被迫介入。

**现实例子**：我统计过 OpenClaw 的 PR 活跃情况，高峰期单日曾观测到 900+ PR；在这种规模下，如果每个 PR 都由人工做同层级 review，成本会很快失控。

### 为什么不能让 AI 判断是否通过？

实践发现：AI reviewer 容易 nit picking、endless refinement、decision instability。

**所以**：AI 不适合做 pass / fail 决策。

### 我的设计

把决策权从 AI 抽离：

| 角色 | 职责 |
|------|------|
| AI | 只负责发现问题（signal provider） |
| Gate | 负责裁决（decision authority） |

**决策规则**（确定性，非 AI 判断）：

| 风险 | 决策 |
|------|------|
| 低风险 | ALLOW |
| 中风险 | ONLY_SUGGEST |
| 高风险 | HITL（必须人工） |

### 关键创新：PR loop 是状态机

PR 不是单次决策，而是多轮状态：

| 条件 | 治理策略 |
|------|----------|
| nit_only_streak ≥ 3 | 收敛 → 在 converged 条件下可放行 |
| round_index ≥ 5 | 卡住 → 升级 HITL |

Gate 根据 loop 状态自动切换治理策略（round_index ≥ 5 优先）。

---

## 第 2 页：机制

### 规则会不会爆炸？

**不会。** 规则不是穷举，而是只定义**治理边界**：

| 必须人工 | 在 converged 条件下可放行 | 其他 |
|----------|--------------------------|------|
| CI fail | nit only（连续 3 轮） | suggest |
| permission change | | |
| infra change | | |

**规则数量**：通常几十条以内，工程上有限且稳定。

### 架构（简化）

```
AI / Reviewer / CI → 信号
       ↓
   Gate（唯一裁决点）
       ↓
  ALLOW / SUGGEST / HITL
```

**类比**：类似 Kubernetes 的 Admission Controller——AI 只负责发现问题，是否继续执行由 Gate 决定。

### 如果 Reviewer 信号不可信？

可标记为 `unverifiable`，自动升级为 HITL。Gate 不直接信任 signal，通过 policy 对冲噪音。

---

## 第 3 页：验证

### Replay 结果

| 域 | Rounds | 通过 |
|----|--------|------|
| PR loop | 8 | 8/8 ✓ |
| Permission | 2 | 2/2 ✓ |
| **Tests** | — | **116 passed** |

- **case_001**：真实 OpenClaw PR #27286
- **case_002**：nit churn 机制验证（连续 nit → 放行；round ≥ 5 → HITL）

### Governance CI（独特价值）

传统 AI 系统没有这个能力。

**我的系统可以**：

```
policy 变更 → replay 历史 case → 验证决策稳定性
```

治理策略做成了**可回归测试系统**，策略演进不破坏已有行为。

### 本质一句话

> 我做的不是 AI reviewer，而是 **AI 系统的治理层**。  
> AI 只负责发现问题，是否继续执行由 Gate 决定。

---

## 2 分钟讲稿

**开场**：我最近在验证 AI coding 和 AI reviewer 多轮协作里的循环治理问题。

**问题**：真实 PR 已经是多 agent 环境，AI reviewer 容易吹毛求疵、无限循环。李老师您之前提到的「AI 抓住小辫子反复让改、越改越糟」正是这个问题。

**设计**：我把决策权从 AI 抽离。AI 只负责发现问题，Gate 负责裁决。规则是确定性的，不交给 AI 判断 pass/fail。

**机制**：规则不是穷举，只定义治理边界，通常几十条以内。PR loop 是状态机：连续 nit 可放行，轮次过多升级人工。

**验证**：两个 replay case，8/8 通过。治理策略可回归测试，相当于 governance CI。

**收尾**：本质是 AI 系统的治理层，类似 K8s Admission Controller。目前先完成了最小验证，后面如果再积累到更多真实 case，我再继续向您汇报。

---

## 李老师可能问的 3 个问题（精简版）

| 问题 | 一句话回答 |
|------|------------|
| 规则开发工作量大吗？ | 不大。只定义治理边界，不穷举，通常几十条以内。 |
| AI 不稳定能兜住吗？ | 能。决策权在 Gate，AI 只提供信号，不做 pass/fail。 |
| 实际可用吗？ | 已用真实 OpenClaw PR 验证，8/8 rounds 通过。 |

---

## 参考

- 完整架构：[PR_LOOP_REPLAY_BRIEFING.md](PR_LOOP_REPLAY_BRIEFING.md)
- 真实 PR：[openclaw/openclaw#27286](https://github.com/openclaw/openclaw/pull/27286)
