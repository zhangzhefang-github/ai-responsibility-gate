# AI Responsibility Gate 架构审计报告

> **独立软件架构评审专家视角的结构性评估**
> 
> **评估目标：** 评估当前实现是否具备演进为 repo-agnostic 通用 Gate 的结构基础，识别潜在的结构风险和抽象边界问题。

---

## 📋 执行摘要

**核心结论：**
- ✅ **决策权唯一化**：已严格实现，无决策泄漏风险
- ✅ **证据与裁决分离**：已严格实现，证据提供者不返回决策
- ⚠️ **业务语义耦合**：存在多处隐含的业务假设，阻碍 repo-agnostic 演进
- ❌ **Loop Guard 缺失**：当前架构无循环保护机制，无法防止 AI review/coding 死循环
- ⚠️ **抽象边界问题**：部分抽象仍隐含"业务动作"而非"证据信号"

**演进可行性评分：6.5/10**

---

## 一、设计宪法对照检查

### 1.1 决策权唯一化 ✅ **已满足**

**检查结果：** ✅ **完全符合**

**证据：**
```python
# src/core/gate.py:48-246
async def decide(...) -> DecisionResponse:
    # 这是唯一创建 Decision enum 的地方
    decision = _map_index_to_decision(decision_index)  # line 161
    return DecisionResponse(decision=decision, ...)  # line 240
```

**验证：**
- ✅ `gate.py` 是唯一输出 `Decision` enum 的模块
- ✅ 所有 stage 函数返回中间状态（indices, dicts），不返回 Decision
- ✅ Evidence Providers 不包含任何决策逻辑
- ✅ Classifier 只返回 `ResponsibilityType`，不返回 Decision

**结论：** 决策权严格集中，无泄漏风险。

---

### 1.2 证据与裁决严格分离 ✅ **已满足**

**检查结果：** ✅ **完全符合**

**证据：**
```python
# src/evidence/risk.py:28-97
async def collect(ctx: GateContext) -> Evidence:
    # 只返回 Evidence，不返回决策
    return Evidence(
        provider="risk",
        available=True,
        data={"risk_level": "R1", "risk_score": 20, ...}
    )
```

**验证：**
- ✅ 所有 Evidence Providers 只返回 `Evidence` 对象
- ✅ `Evidence.data` 是纯数据字典，不包含决策值
- ✅ 证据提供者不访问或修改 Decision enum

**结论：** 证据与裁决严格分离，符合设计宪法。

---

### 1.3 Tighten-only（只紧不松） ✅ **已满足**

**检查结果：** ✅ **完全符合**

**证据：**
```python
# src/core/gate_helpers.py:21-24
def tighten_one_step(current_index: int, steps: int = 1) -> int:
    """Tighten decision by moving index forward."""
    new_index = min(current_index + steps, DECISION_IDX_MAX)
    return new_index
```

**验证：**
- ✅ 所有 tighten 操作都是 `min(current + steps, MAX)`，只能收紧
- ✅ 没有 `relax_one_step` 或类似的放松函数
- ✅ Matrix 规则匹配后，只能通过 tighten 收紧，不能放松

**结论：** Tighten-only 原则已严格实现。

---

### 1.4 Gate 不关心代码审美 ⚠️ **部分违反**

**检查结果：** ⚠️ **存在潜在违反**

**证据：**
```python
# src/core/postcheck.py:11-32
def postcheck(text: str, requires_disclaimer: bool, is_input: bool) -> PostcheckResult:
    # 检查文本内容，但这是针对"保证性承诺"的业务规则
    has_guarantee = any(kw in text for kw in GUARANTEE_KEYWORDS)
    # ...
```

**问题分析：**
- ⚠️ `postcheck` 检查的是业务语义（"保证性承诺"），而非代码审美
- ✅ 但当前实现是针对业务场景的，不是代码风格检查
- ⚠️ **潜在风险**：如果未来在 PR 场景中，`postcheck` 被误用于代码风格检查，会违反此原则

**结论：** 当前未违反，但需要明确 `postcheck` 的职责边界，防止误用。

---

### 1.5 Gate 必须 repo-agnostic ❌ **未满足**

**检查结果：** ❌ **存在多处业务语义耦合**

**详细分析见第 2 节。**

---

### 1.6 Loop Guard 是一等能力 ❌ **缺失**

**检查结果：** ❌ **完全缺失**

**证据：**
```python
# src/core/gate.py:48-246
async def decide(...) -> DecisionResponse:
    # 没有任何循环保护机制
    # 没有 round_count 或 loop_history 的概念
    # 没有 stop condition 检查
```

**问题分析：**
- ❌ 当前架构是**单次决策**，不支持多轮循环
- ❌ 没有 `round_count` 或 `loop_history` 的概念
- ❌ 没有 stop condition 机制（如"连续 N 轮只有低价值 nits，自动 ALLOW"）
- ❌ 无法防止 AI review/coding 死循环

**结论：** Loop Guard 完全缺失，这是演进到 PR/AI Review Gate 的**结构性障碍**。

---

## 二、业务语义耦合分析

### 2.1 隐含的业务动作假设 ⚠️ **严重耦合**

#### **问题 1：action_type 隐含业务语义**

**位置：** `tools/catalog.yaml`, `src/evidence/tool.py`, `src/evidence/permission.py`

**证据：**
```yaml
# tools/catalog.yaml
- tool_id: "refund.create"
  action_type: "MONEY"  # ← 隐含业务语义
  resource_type: "Payment"
```

```python
# src/core/gate_stages.py:234
if risk_level == "R3" and permission_ok and action_type in ("MONEY", "ENTITLEMENT"):
    # ← 硬编码业务动作类型
```

**问题分析：**
- ⚠️ `action_type` 是业务动作（MONEY, ENTITLEMENT, POLICY），而非通用信号
- ⚠️ Matrix 规则中硬编码了 `action_types: ["MONEY", "ENTITLEMENT"]`
- ⚠️ 在 PR 场景中，应该是 `SECURITY_BOUNDARY`, `BUILD_CHAIN`, `API_CHANGE` 等信号，而非 `MONEY`

**影响：**
- ❌ 无法直接复用到 PR 场景，需要重新定义 `action_type` 的语义
- ❌ 抽象边界不清晰：是"业务动作"还是"证据信号"？

**结论：** **必须调整** - `action_type` 需要抽象为通用的"信号类型"，而非业务动作。

---

#### **问题 2：ResponsibilityType 隐含业务语义**

**位置：** `src/core/models.py`, `src/core/classifier.py`

**证据：**
```python
# src/core/models.py:5-9
class ResponsibilityType(str, Enum):
    Information = "Information"           # ← 隐含"信息查询"业务语义
    RiskNotice = "RiskNotice"             # ← 隐含"风险提示"业务语义
    EntitlementDecision = "EntitlementDecision"  # ← 隐含"权益决策"业务语义
```

```python
# src/core/classifier.py:3-18
async def classify(text: str) -> ClassifierResult:
    operation_keywords = ["买", "卖", "操作", "执行", "交易"]  # ← 硬编码业务关键词
    is_operation = any(kw in text for kw in operation_keywords)
```

**问题分析：**
- ⚠️ `ResponsibilityType` 的命名隐含业务语义（"权益决策"）
- ⚠️ Classifier 硬编码了业务关键词（"买", "卖", "操作"）
- ⚠️ 在 PR 场景中，应该是 `DOCS_ONLY`, `CODE_CHANGE`, `CONFIG_CHANGE` 等类型

**影响：**
- ❌ 无法直接复用到 PR 场景，需要重新定义 `ResponsibilityType`
- ❌ 抽象边界不清晰：是"责任类型"还是"变更类型"？

**结论：** **必须调整** - `ResponsibilityType` 需要抽象为通用的"变更类型"或"信号类型"。

---

#### **问题 3：text 字段隐含"用户输入"假设**

**位置：** `src/core/models.py:19`, `src/core/gate.py:103`

**证据：**
```python
# src/core/models.py:19
text: str = Field(..., min_length=1, max_length=10000, description="User input text")
# ← 隐含"用户输入"假设
```

```python
# src/core/gate.py:103
classifier_result = await classify(req.text)  # ← 假设 text 是用户输入文本
```

**问题分析：**
- ⚠️ `text` 字段隐含"用户输入文本"的假设
- ⚠️ 在 PR 场景中，输入应该是 `PRMeta` + `ReviewComment[]`，而非文本
- ⚠️ Classifier 基于文本分类，PR 场景需要基于 PRMeta 分类

**影响：**
- ❌ 无法直接复用到 PR 场景，需要重新定义输入模型
- ❌ 抽象边界不清晰：是"文本输入"还是"结构化输入"？

**结论：** **必须调整** - `DecisionRequest` 需要抽象为通用的"请求模型"，支持结构化输入。

---

### 2.2 隐含的"谁在做什么"假设 ⚠️ **中等耦合**

#### **问题 4：user_id / session_id 隐含用户会话假设**

**位置：** `src/core/models.py:17-18`, `src/core/models.py:44-45`

**证据：**
```python
# src/core/models.py:17-18
session_id: Optional[str] = None
user_id: Optional[str] = None
# ← 隐含"用户会话"假设
```

**问题分析：**
- ⚠️ `user_id` / `session_id` 隐含"用户会话"的业务假设
- ⚠️ 在 PR 场景中，应该是 `pr_id`, `contributor_id`, `round_count` 等
- ⚠️ 但可以通过 `context` 传递，影响较小

**影响：**
- ⚠️ 可以通过 `context` 传递 PR 相关信息，影响较小
- ⚠️ 但字段命名仍隐含业务语义

**结论：** **可以保留** - 可以通过 `context` 传递 PR 相关信息，但字段命名需要更通用。

---

#### **问题 5：permission 隐含 RBAC 假设**

**位置：** `src/evidence/permission.py`, `config/permission_policies.yaml`

**证据：**
```python
# src/evidence/permission.py:23
user_role = ctx.context.get("role", "normal_user") if ctx.context else "normal_user"
# ← 隐含 RBAC 角色假设
```

```yaml
# config/permission_policies.yaml
roles:
  normal_user: ...
  cs_agent: ...
  finance_operator: ...
# ← 硬编码业务角色
```

**问题分析：**
- ⚠️ `permission` 证据提供者隐含 RBAC 角色假设
- ⚠️ 在 PR 场景中，应该是 `contributor_trust_level`, `repo_access_level` 等
- ⚠️ 但可以通过 `context` 传递，影响较小

**影响：**
- ⚠️ 可以通过 `context` 传递 PR 相关信息，影响较小
- ⚠️ 但角色定义仍隐含业务语义

**结论：** **可以保留** - 可以通过 `context` 传递 PR 相关信息，但需要抽象角色定义。

---

### 2.3 配置文件的业务语义耦合 ⚠️ **严重耦合**

#### **问题 6：risk_rules.yaml 硬编码业务关键词**

**位置：** `config/risk_rules.yaml`

**证据：**
```yaml
# config/risk_rules.yaml
rules:
  - rule_id: "RISK_GUARANTEE_CLAIM"
    keywords: ["保本","保证收益","稳赚不赔","百分百","一定赚钱"]
    # ← 硬编码业务关键词
```

**问题分析：**
- ⚠️ 风险规则硬编码了业务关键词（"保本", "保证收益"）
- ⚠️ 在 PR 场景中，应该是 `SECURITY_BOUNDARY`, `BUILD_CHAIN`, `API_CHANGE` 等信号
- ⚠️ 但这是配置层面的，可以通过新增配置文件解决

**影响：**
- ⚠️ 可以通过新增 `pr_risk_rules.yaml` 解决
- ⚠️ 但核心抽象（`risk_level`, `rules_hit`）仍可复用

**结论：** **可以保留** - 核心抽象可复用，但需要新增 PR 相关的配置文件。

---

#### **问题 7：tools/catalog.yaml 硬编码业务工具**

**位置：** `tools/catalog.yaml`

**证据：**
```yaml
# tools/catalog.yaml
tools:
  - tool_id: "refund.create"
    description: "发起退款申请"
    action_type: "MONEY"
    # ← 硬编码业务工具
```

**问题分析：**
- ⚠️ 工具目录硬编码了业务工具（`refund.create`, `order.query`）
- ⚠️ 在 PR 场景中，不需要工具目录，而是 `ReviewComment[]`
- ⚠️ 但这是配置层面的，可以通过新增配置文件解决

**影响：**
- ⚠️ 可以通过新增 `pr_catalog.yaml` 或直接移除工具目录
- ⚠️ 但核心抽象（`action_type`, `impact_level`）仍可复用

**结论：** **可以保留** - 核心抽象可复用，但需要新增 PR 相关的配置文件或移除工具目录。

---

## 三、抽象边界分析

### 3.1 已满足通用 Gate 定义的结构 ✅

#### **结构 1：决策流水线（Pipeline）** ✅

**位置：** `src/core/gate.py:48-246`

**抽象边界：**
```python
# 6 阶段流水线，职责清晰
1. Evidence Collection (concurrent)
2. Type Upgrade Rules (YAML)
3. Matrix Decision Lookup
4. Missing Evidence Policy (YAML)
5. Conflict Resolution & Overrides
6. Postcheck
```

**可复用性：** ✅ **完全可复用**
- 流水线设计是通用的，不依赖业务语义
- 可以新增 Stage 7: Loop Guard，不影响现有逻辑

**结论：** **可以保留** - 流水线设计是通用的，无需调整。

---

#### **结构 2：Evidence 收集机制** ✅

**位置：** `src/core/gate_helpers.py:32-76`

**抽象边界：**
```python
async def collect_all_evidence(ctx: GateContext, trace: List[str]) -> dict:
    evidence_tasks = [
        asyncio.wait_for(collect_tool(ctx), timeout=0.08),
        asyncio.wait_for(collect_routing(ctx), timeout=0.08),
        asyncio.wait_for(collect_knowledge(ctx), timeout=0.08),
        asyncio.wait_for(collect_risk(ctx), timeout=0.08),
        asyncio.wait_for(collect_permission(ctx), timeout=0.08),
    ]
```

**可复用性：** ✅ **完全可复用**
- Evidence 收集机制是通用的，不依赖业务语义
- 可以新增 `collect_review(ctx)` 证据提供者，不影响现有逻辑

**结论：** **可以保留** - Evidence 收集机制是通用的，无需调整。

---

#### **结构 3：Matrix 配置机制** ✅

**位置：** `src/core/matrix.py`, `matrices/v0.1.yaml`

**抽象边界：**
```python
# Matrix 配置是 YAML 驱动的，不依赖业务语义
defaults:
  Information: "ONLY_SUGGEST"
rules:
  - rule_id: "MATRIX_R3_MONEY_HITL"
    match:
      risk_level: "R3"
      action_types: ["MONEY"]
    decision: "HITL"
```

**可复用性：** ⚠️ **部分可复用**
- Matrix 配置机制是通用的，但规则匹配依赖业务语义（`action_types: ["MONEY"]`）
- 可以通过新增 `pr_gate.yaml` 配置文件解决

**结论：** **可以保留** - Matrix 配置机制是通用的，但需要新增 PR 相关的配置文件。

---

#### **结构 4：Decision 枚举** ✅

**位置：** `src/core/models.py:10-14`

**抽象边界：**
```python
class Decision(str, Enum):
    ALLOW = "ALLOW"
    ONLY_SUGGEST = "ONLY_SUGGEST"
    HITL = "HITL"
    DENY = "DENY"
```

**可复用性：** ✅ **完全可复用**
- Decision 枚举是通用的，不依赖业务语义
- 完全适用于 PR 场景

**结论：** **可以保留** - Decision 枚举是通用的，无需调整。

---

### 3.2 需要调整的抽象 ⚠️

#### **抽象 1：DecisionRequest 模型** ⚠️ **必须调整**

**问题：**
- `text` 字段隐含"用户输入文本"假设
- `user_id` / `session_id` 隐含"用户会话"假设

**调整方案：**
```python
# 方案 A：扩展 DecisionRequest（推荐）
class DecisionRequest(BaseModel):
    # 保留现有字段，但让 text 可选
    text: Optional[str] = None
    # 新增结构化输入
    structured_input: Optional[Dict[str, Any]] = None
    # 保留 context
    context: Optional[Dict[str, Any]] = None

# 方案 B：新增 PRDecisionRequest（不推荐，会增加复杂度）
class PRDecisionRequest(BaseModel):
    pr_meta: PRMeta
    review_comments: List[ReviewComment]
    round_count: int
```

**结论：** **必须调整** - 需要支持结构化输入，而非仅文本输入。

---

#### **抽象 2：Classifier 接口** ⚠️ **必须调整**

**问题：**
- `classify(text: str)` 假设输入是文本
- 硬编码业务关键词（"买", "卖", "操作"）

**调整方案：**
```python
# 方案 A：抽象 Classifier 接口（推荐）
async def classify(ctx: GateContext) -> ClassifierResult:
    # 从 ctx.text 或 ctx.context 中提取信号
    if ctx.context and "pr_meta" in ctx.context:
        # PR 场景：基于 PRMeta 分类
        return classify_pr(ctx.context["pr_meta"])
    else:
        # 业务场景：基于文本分类
        return classify_text(ctx.text)

# 方案 B：新增 classify_pr()（不推荐，会增加复杂度）
async def classify_pr(pr_meta: PRMeta) -> ClassifierResult:
    # PR 场景的分类逻辑
```

**结论：** **必须调整** - 需要支持结构化输入的分类，而非仅文本分类。

---

#### **抽象 3：action_type 语义** ⚠️ **必须调整**

**问题：**
- `action_type` 是业务动作（MONEY, ENTITLEMENT），而非通用信号
- Matrix 规则中硬编码了业务动作类型

**调整方案：**
```python
# 方案 A：抽象为"信号类型"（推荐）
# 在 PR 场景中，action_type 应该是：
# - SECURITY_BOUNDARY
# - BUILD_CHAIN
# - API_CHANGE
# - LOW_VALUE_NITS

# 方案 B：保留 action_type，但通过 context 传递信号（不推荐）
# 在 context 中传递 signals，action_type 作为兼容字段
```

**结论：** **必须调整** - 需要抽象为通用的"信号类型"，而非业务动作。

---

#### **抽象 4：ResponsibilityType 语义** ⚠️ **必须调整**

**问题：**
- `ResponsibilityType` 的命名隐含业务语义（"权益决策"）
- 在 PR 场景中，应该是 `DOCS_ONLY`, `CODE_CHANGE`, `CONFIG_CHANGE` 等

**调整方案：**
```python
# 方案 A：抽象为"变更类型"（推荐）
class ChangeType(str, Enum):
    DOCS_ONLY = "DOCS_ONLY"
    CODE_CHANGE = "CODE_CHANGE"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    # 保留兼容性
    Information = "Information"  # 兼容字段
    RiskNotice = "RiskNotice"     # 兼容字段
    EntitlementDecision = "EntitlementDecision"  # 兼容字段

# 方案 B：保留 ResponsibilityType，但通过 context 传递变更类型（不推荐）
```

**结论：** **必须调整** - 需要抽象为通用的"变更类型"，而非业务责任类型。

---

## 四、潜在结构风险分析

### 4.1 决策权泄漏风险 ❌ **无风险**

**检查结果：** ✅ **无风险**

**证据：**
- ✅ `gate.py` 是唯一创建 Decision enum 的地方
- ✅ 所有 stage 函数返回中间状态，不返回 Decision
- ✅ Evidence Providers 不包含任何决策逻辑

**结论：** 决策权严格集中，无泄漏风险。

---

### 4.2 AI 反向主导裁决风险 ⚠️ **中等风险**

**检查结果：** ⚠️ **存在潜在风险**

**问题分析：**

1. **Classifier 可能被 AI 主导** ⚠️
   ```python
   # src/core/classifier.py:3-18
   async def classify(text: str) -> ClassifierResult:
       # 如果未来替换为 LLM 分类器，可能被 AI 主导
   ```
   - ⚠️ 如果 Classifier 替换为 LLM，可能被 AI 主导
   - ✅ 但当前是规则匹配，无风险

2. **Routing 弱信号可能被 AI 主导** ⚠️
   ```python
   # src/evidence/routing.py:30-45
   async def collect(ctx: GateContext) -> Evidence:
       # 如果未来替换为 LLM 路由，可能被 AI 主导
   ```
   - ⚠️ 如果 Routing 替换为 LLM，可能被 AI 主导
   - ✅ 但当前是关键词匹配，无风险

3. **Risk 规则可能被 AI 主导** ⚠️
   ```python
   # src/evidence/risk.py:28-97
   async def collect(ctx: GateContext) -> Evidence:
       # 如果未来接入 ML 模型，可能被 AI 主导
   ```
   - ⚠️ 如果 Risk 规则替换为 ML 模型，可能被 AI 主导
   - ✅ 但当前是规则匹配，无风险

**结论：** 当前无风险，但未来如果接入 LLM/ML 模型，需要确保 AI 只输出证据，不输出决策。

---

### 4.3 Loop Guard 无法成立风险 ❌ **高风险**

**检查结果：** ❌ **完全缺失**

**问题分析：**

1. **单次决策架构** ❌
   ```python
   # src/core/gate.py:48-246
   async def decide(...) -> DecisionResponse:
       # 没有任何循环保护机制
       # 没有 round_count 或 loop_history 的概念
   ```
   - ❌ 当前架构是单次决策，不支持多轮循环
   - ❌ 无法跟踪循环历史

2. **无 Stop Condition 机制** ❌
   - ❌ 没有"连续 N 轮只有低价值 nits，自动 ALLOW"的机制
   - ❌ 无法防止 AI review/coding 死循环

3. **无 Loop History 跟踪** ❌
   - ❌ 没有 `round_count` 或 `loop_history` 的概念
   - ❌ 无法判断是否陷入循环

**结论：** Loop Guard 完全缺失，这是演进到 PR/AI Review Gate 的**结构性障碍**。

**必须调整：**
- 需要新增 `round_count` 和 `loop_history` 的概念
- 需要新增 Stop Condition 机制
- 需要新增 Loop Guard 阶段

---

### 4.4 抽象不可逆污染风险 ⚠️ **中等风险**

**检查结果：** ⚠️ **存在潜在风险**

**问题分析：**

1. **action_type 语义污染** ⚠️
   - ⚠️ `action_type` 是业务动作（MONEY, ENTITLEMENT），而非通用信号
   - ⚠️ 如果直接复用到 PR 场景，会导致语义混乱

2. **ResponsibilityType 语义污染** ⚠️
   - ⚠️ `ResponsibilityType` 的命名隐含业务语义（"权益决策"）
   - ⚠️ 如果直接复用到 PR 场景，会导致语义混乱

3. **text 字段语义污染** ⚠️
   - ⚠️ `text` 字段隐含"用户输入文本"假设
   - ⚠️ 如果直接复用到 PR 场景，会导致语义混乱

**结论：** 存在抽象不可逆污染风险，需要调整抽象边界。

---

## 五、演进路径分析

### 5.1 必须调整的抽象（不调会出结构性问题）

#### **调整 1：DecisionRequest 模型** ⚠️ **必须调整**

**原因：**
- `text` 字段隐含"用户输入文本"假设
- PR 场景需要结构化输入（`PRMeta` + `ReviewComment[]`）

**调整方案：**
```python
# 扩展 DecisionRequest，支持结构化输入
class DecisionRequest(BaseModel):
    text: Optional[str] = None  # 可选，兼容现有场景
    structured_input: Optional[Dict[str, Any]] = None  # 新增，支持 PR 场景
    context: Optional[Dict[str, Any]] = None
    # ...
```

**影响：** 中等 - 需要修改 `DecisionRequest` 模型，但可以保持向后兼容。

---

#### **调整 2：Classifier 接口** ⚠️ **必须调整**

**原因：**
- `classify(text: str)` 假设输入是文本
- PR 场景需要基于 `PRMeta` 分类

**调整方案：**
```python
# 抽象 Classifier 接口，支持结构化输入
async def classify(ctx: GateContext) -> ClassifierResult:
    if ctx.context and "pr_meta" in ctx.context:
        return classify_pr(ctx.context["pr_meta"])
    else:
        return classify_text(ctx.text or "")
```

**影响：** 中等 - 需要修改 `classify()` 函数，但可以保持向后兼容。

---

#### **调整 3：Loop Guard 机制** ❌ **必须新增**

**原因：**
- 当前架构无循环保护机制
- PR 场景需要 Loop Guard 防止 AI review/coding 死循环

**调整方案：**
```python
# 新增 Loop Guard 阶段
def apply_loop_guard(
    decision_index: int,
    evidence: dict,
    context: dict,
    trace: List[str]
) -> Dict[str, Any]:
    round_count = context.get("round_count", 0)
    review_ev = evidence.get("review", None)
    
    # Stop Condition: 连续 N 轮只有低价值 nits，自动 ALLOW
    if round_count >= 2 and review_ev and review_ev.data.get("only_nits", False):
        return {
            "decision_index": 0,  # ALLOW
            "primary_reason": "LOOP_GUARD_STOP_CONDITION",
            "loop_guard_applied": True
        }
    
    return {"decision_index": decision_index}
```

**影响：** 高 - 需要新增 Loop Guard 阶段，但可以不影响现有逻辑。

---

### 5.2 可以保留不动的抽象（本身已足够通用）

#### **保留 1：决策流水线（Pipeline）** ✅

**原因：**
- 流水线设计是通用的，不依赖业务语义
- 可以新增 Stage 7: Loop Guard，不影响现有逻辑

**结论：** **可以保留** - 无需调整。

---

#### **保留 2：Evidence 收集机制** ✅

**原因：**
- Evidence 收集机制是通用的，不依赖业务语义
- 可以新增 `collect_review(ctx)` 证据提供者，不影响现有逻辑

**结论：** **可以保留** - 无需调整。

---

#### **保留 3：Decision 枚举** ✅

**原因：**
- Decision 枚举是通用的，不依赖业务语义
- 完全适用于 PR 场景

**结论：** **可以保留** - 无需调整。

---

#### **保留 4：Matrix 配置机制** ✅

**原因：**
- Matrix 配置机制是通用的，不依赖业务语义
- 可以通过新增 `pr_gate.yaml` 配置文件解决

**结论：** **可以保留** - 无需调整。

---

## 六、最终评估结论

### 6.1 演进可行性评分

| 维度 | 评分 | 说明 |
|------|------|------|
| **决策权唯一化** | 10/10 | 完全符合，无风险 |
| **证据与裁决分离** | 10/10 | 完全符合，无风险 |
| **Tighten-only** | 10/10 | 完全符合，无风险 |
| **业务语义耦合** | 4/10 | 存在多处业务语义耦合 |
| **Loop Guard** | 0/10 | 完全缺失，结构性障碍 |
| **抽象边界** | 6/10 | 部分抽象需要调整 |
| **综合评分** | **6.5/10** | **中等可行性** |

### 6.2 核心结论

**当前实现可以演进为 repo-agnostic 通用 Gate，但需要调整关键抽象。**

**必须调整的抽象：**
1. ✅ **DecisionRequest 模型** - 支持结构化输入
2. ✅ **Classifier 接口** - 支持结构化输入的分类
3. ❌ **Loop Guard 机制** - 新增循环保护机制

**可以保留的抽象：**
1. ✅ **决策流水线（Pipeline）** - 完全通用
2. ✅ **Evidence 收集机制** - 完全通用
3. ✅ **Decision 枚举** - 完全通用
4. ✅ **Matrix 配置机制** - 完全通用

**潜在风险：**
1. ⚠️ **业务语义耦合** - 需要调整抽象边界
2. ❌ **Loop Guard 缺失** - 结构性障碍
3. ⚠️ **抽象不可逆污染** - 需要谨慎调整

### 6.3 演进建议

**不建议直接演进，原因：**
1. ❌ **Loop Guard 完全缺失** - 这是 PR/AI Review Gate 的核心能力
2. ⚠️ **业务语义耦合严重** - 需要大量抽象调整
3. ⚠️ **抽象不可逆污染风险** - 需要谨慎设计

**建议演进路径：**
1. **阶段 1：抽象调整** - 调整 `DecisionRequest`、`Classifier`、`action_type` 等抽象
2. **阶段 2：Loop Guard 实现** - 新增 Loop Guard 机制
3. **阶段 3：PR 场景适配** - 新增 PR 相关的证据提供者和规则配置

**或者：**
- 在 `examples/pr_gate_ai_review_loop/` 目录下实现独立示例
- 复用核心 Gate 逻辑，但保持独立的数据模型和配置
- 避免抽象不可逆污染

---

**报告完成时间：** 2024年
**评估人：** 独立软件架构评审专家
**评估结论：** ⚠️ **中等可行性，需要调整关键抽象，不建议直接演进**
