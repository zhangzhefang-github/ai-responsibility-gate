# AI Responsibility Gate 使用说明书

> **作为顶级 AI 产品经理，我为你设计这份完整的使用说明书，帮助你从零开始配置和使用 AI Responsibility Gate。**

---

## 📋 目录

1. [快速理解：配置架构概览](#快速理解配置架构概览)
2. [配置文件的层次和关系](#配置文件的层次和关系)
3. [从零开始：一步步配置指南](#从零开始一步步配置指南)
4. [配置示例：实战场景](#配置示例实战场景)
5. [配置验证和测试](#配置验证和测试)
6. [常见问题和故障排查](#常见问题和故障排查)
7. [最佳实践和进阶技巧](#最佳实践和进阶技巧)

---

## 🎯 快速理解：配置架构概览

### 核心概念

AI Responsibility Gate 是一个**策略驱动的治理层**，它通过**多维度证据**（意图、风险、权限、工具）做出决策。所有策略都通过 **YAML 配置文件**定义，无需修改代码。

### 配置文件的层次结构

```
项目根目录/
├── matrices/          # 决策矩阵（核心决策规则）
│   └── v0.1.yaml      # 决策矩阵：定义何时 ALLOW/DENY/HITL/ONLY_SUGGEST
├── config/            # 策略配置（风险、权限、知识库）
│   ├── risk_rules.yaml        # 风险规则：定义什么情况是高风险
│   ├── permission_policies.yaml  # 权限策略：定义谁可以做什么
│   ├── kb_meta.yaml           # 知识库元数据：定义知识库状态
│   └── risk_keywords.yaml     # 风险关键词（内部使用）
└── tools/             # 工具目录（工具定义和路由提示）
    └── catalog.yaml   # 工具目录：定义工具、动作类型、路由关键词
```

### 配置的决策流程

```
用户请求
    ↓
1. Classifier（意图识别）→ Information / RiskNotice / EntitlementDecision
    ↓
2. Evidence Collection（并发收集证据）
    ├─ Tool Evidence（从 tools/catalog.yaml）
    ├─ Risk Evidence（从 config/risk_rules.yaml）
    ├─ Permission Evidence（从 config/permission_policies.yaml）
    ├─ Knowledge Evidence（从 config/kb_meta.yaml）
    └─ Routing Evidence（从 tools/catalog.yaml 的 routing_hints）
    ↓
3. Matrix Lookup（从 matrices/v0.1.yaml）
    ├─ Type Upgrade Rules（类型升级）
    ├─ Rules Matching（规则匹配）
    ├─ Defaults（默认决策）
    ├─ Missing Evidence Policy（缺失证据策略）
    └─ Conflict Resolution（冲突解决）
    ↓
4. Decision（最终决策：ALLOW / ONLY_SUGGEST / HITL / DENY）
```

---

## 📁 配置文件的层次和关系

### 1. Matrix（决策矩阵）- `matrices/v0.1.yaml`

**作用：** 核心决策规则，定义在什么条件下做出什么决策。

**包含内容：**
- `defaults`: 按责任类型的默认决策
- `rules`: 基于 risk_level + action_types 的决策规则
- `type_upgrade_rules`: 类型升级规则（Information → EntitlementDecision）
- `missing_evidence_policy`: 证据缺失时的策略
- `conflict_resolution`: 冲突解决策略
- `confidence_thresholds`: 置信度阈值

**依赖关系：**
- 依赖 `config/risk_rules.yaml`（获取 risk_level）
- 依赖 `tools/catalog.yaml`（获取 action_type）

### 2. Risk Rules（风险规则）- `config/risk_rules.yaml`

**作用：** 定义什么情况是高风险，返回 risk_level (R1/R2/R3)。

**包含内容：**
- `defaults`: 默认值（如 high_amount_threshold）
- `rules`: 风险规则列表
  - `type: keyword`: 关键词匹配
  - `type: threshold`: 阈值匹配（如金额 >= 5000）
  - `type: missing_fields`: 缺失字段检测

**依赖关系：**
- 依赖 `tools/catalog.yaml`（获取 tool_id，用于 applies_when）

### 3. Tool Catalog（工具目录）- `tools/catalog.yaml`

**作用：** 定义工具、动作类型、路由关键词。

**包含内容：**
- `tools`: 工具列表（tool_id, action_type, impact_level, required_role）
- `routing_hints`: 路由提示（关键词 → tool_id 映射）

**依赖关系：**
- 被 Matrix 和 Risk Rules 使用

### 4. Permission Policies（权限策略）- `config/permission_policies.yaml`

**作用：** 定义基于角色的权限控制（RBAC）。

**包含内容：**
- `roles`: 角色定义（normal_user, cs_agent, finance_operator）
- `action_permissions`: 动作类型到权限的映射

**依赖关系：**
- 独立，不依赖其他配置

### 5. Knowledge Base Meta（知识库元数据）- `config/kb_meta.yaml`

**作用：** 定义知识库的状态和版本。

**包含内容：**
- `kb_id`: 知识库 ID
- `expired`: 是否过期
- `last_updated`: 最后更新时间
- `supported_topics`: 支持的主题

**依赖关系：**
- 独立，不依赖其他配置

---

## 🚀 从零开始：一步步配置指南

### 步骤 1: 定义工具和动作类型（`tools/catalog.yaml`）

**为什么先配置这个？** 因为其他配置都依赖工具定义。

**配置步骤：**

1. **定义工具列表**：
```yaml
tools:
  - tool_id: "refund.create"
    description: "发起退款申请"
    action_type: "MONEY"        # 动作类型：READ / WRITE / MONEY / ENTITLEMENT / POLICY
    impact_level: "I3"          # 影响级别：I1（低） / I2（中） / I3（高）
    required_role: "normal_user" # 所需角色
```

2. **定义路由提示**（可选，用于弱信号）：
```yaml
routing_hints:
  - tool_id: "refund.create"
    keywords: ["退款", "退钱", "退货退款"]
```

**关键概念：**
- `action_type`: 决定决策矩阵的匹配规则
- `impact_level`: 影响级别（当前未直接使用，可扩展）
- `required_role`: 用于权限检查

### 步骤 2: 定义风险规则（`config/risk_rules.yaml`）

**为什么配置这个？** 风险级别（R1/R2/R3）是决策矩阵匹配的关键条件。

**配置步骤：**

1. **定义默认值**：
```yaml
defaults:
  high_amount_threshold: 5000  # 高额阈值
```

2. **定义关键词规则**：
```yaml
rules:
  - rule_id: "RISK_GUARANTEE_CLAIM"
    type: "keyword"
    risk_level: "R3"
    keywords: ["保本", "保证收益", "稳赚不赔"]
```

3. **定义阈值规则**：
```yaml
  - rule_id: "RISK_HIGH_AMOUNT_REFUND"
    type: "threshold"
    risk_level: "R3"
    field: "amount"
    op: ">="
    value_from_default: "high_amount_threshold"
    applies_when:
      tool_ids: ["refund.create", "refund.approve"]
```

4. **定义缺失字段规则**：
```yaml
  - rule_id: "RISK_MISSING_KEY_FIELDS"
    type: "missing_fields"
    risk_level: "R1"
    required_fields: ["order_id"]
    applies_when:
      tool_ids: ["refund.create"]
```

**关键概念：**
- `risk_level`: R1（低风险）/ R2（中风险）/ R3（高风险）
- `applies_when`: 规则生效的条件（基于 tool_id）

### 步骤 3: 定义权限策略（`config/permission_policies.yaml`）

**为什么配置这个？** 权限检查是决策的重要依据。

**配置步骤：**

1. **定义角色**：
```yaml
roles:
  normal_user:
    can_actions:
      - "READ"
      - "WRITE"
      - "MONEY:limited"  # 有限制的 MONEY 操作
```

2. **定义动作权限映射**：
```yaml
action_permissions:
  MONEY:
    default_roles: ["normal_user", "finance_operator"]
    restricted: ["cs_agent"]
```

**关键概念：**
- `can_actions`: 角色可以执行的动作类型
- `MONEY:limited` vs `MONEY:all`: 有限制 vs 无限制

### 步骤 4: 定义决策矩阵（`matrices/v0.1.yaml`）

**为什么最后配置这个？** 因为决策矩阵依赖前面所有的配置。

**配置步骤：**

1. **定义默认决策**：
```yaml
defaults:
  Information: "ONLY_SUGGEST"      # 信息查询 → 仅建议
  RiskNotice: "ONLY_SUGGEST"       # 风险提示 → 仅建议
  EntitlementDecision: "HITL"      # 权益决策 → 人工介入
```

2. **定义类型升级规则**：
```yaml
type_upgrade_rules:
  - when:
      tool_action: "MONEY"
    upgrade_to: "EntitlementDecision"
```

3. **定义决策规则**：
```yaml
rules:
  - rule_id: "MATRIX_R3_MONEY_HITL"
    match:
      risk_level: "R3"
      action_types: ["MONEY", "ENTITLEMENT"]
    decision: "HITL"
    primary_reason: "MATRIX_R3_MONEY"
```

4. **定义缺失证据策略**：
```yaml
missing_evidence_policy:
  missing_risk: "tighten"      # 风险证据缺失 → 收紧 1 步
  missing_permission: "hitl"   # 权限证据缺失 → HITL
  missing_knowledge: "tighten" # 知识库证据缺失 → 收紧 1 步
```

5. **定义冲突解决策略**：
```yaml
conflict_resolution:
  risk_high_overrides_permission_ok: true  # 高风险覆盖权限 OK
  r3_with_permission_action: "hitl"        # R3 + 权限 OK → HITL
```

**关键概念：**
- `match`: 匹配条件（risk_level + action_types）
- `decision`: 决策结果（ALLOW / ONLY_SUGGEST / HITL / DENY）
- `tighten`: 收紧决策（ALLOW → ONLY_SUGGEST → HITL → DENY）

### 步骤 5: 配置知识库元数据（`config/kb_meta.yaml`）

**为什么配置这个？** 知识库状态影响决策（过期知识库需要收紧）。

**配置步骤：**

```yaml
version: "2024-01-01"
kb_id: "production_kb"
expired: false
last_updated: "2024-01-01T00:00:00Z"
supported_topics:
  - "product_info"
  - "fee_structure"
```

---

## 💡 配置示例：实战场景

### 场景 1: 防止保证性承诺

**需求：** 当用户询问"这个产品保本吗？"时，应该 DENY。

**配置步骤：**

1. **在 `config/risk_rules.yaml` 中定义风险规则**：
```yaml
rules:
  - rule_id: "RISK_GUARANTEE_CLAIM"
    type: "keyword"
    risk_level: "R3"
    keywords: ["保本", "保证收益", "稳赚不赔"]
```

2. **在 `matrices/v0.1.yaml` 中定义决策规则**（可选，因为 RISK_GUARANTEE_CLAIM 会自动触发 DENY）：
```yaml
# RISK_GUARANTEE_CLAIM 在 gate_stages.py 中自动触发 DENY（最高优先级）
# 无需额外配置
```

**验证：**
```bash
curl -X POST http://localhost:8000/decision \
  -H "Content-Type: application/json" \
  -d '{"text": "这个产品保本吗？稳赚不赔？", "debug": true}'
# 预期：decision: DENY, primary_reason: RISK_GUARANTEE_OVERRIDE
```

### 场景 2: 高额退款需要人工审核

**需求：** 当退款金额 >= 5000 时，需要 HITL。

**配置步骤：**

1. **在 `config/risk_rules.yaml` 中定义阈值规则**：
```yaml
defaults:
  high_amount_threshold: 5000

rules:
  - rule_id: "RISK_HIGH_AMOUNT_REFUND"
    type: "threshold"
    risk_level: "R3"
    field: "amount"
    op: ">="
    value_from_default: "high_amount_threshold"
    applies_when:
      tool_ids: ["refund.create", "refund.approve"]
```

2. **在 `matrices/v0.1.yaml` 中定义决策规则**：
```yaml
rules:
  - rule_id: "MATRIX_R3_MONEY_HITL"
    match:
      risk_level: "R3"
      action_types: ["MONEY", "ENTITLEMENT"]
    decision: "HITL"
    primary_reason: "MATRIX_R3_MONEY"
```

**验证：**
```bash
curl -X POST http://localhost:8000/decision \
  -H "Content-Type: application/json" \
  -d '{"text": "我要退款", "context": {"amount": 8000}, "debug": true}'
# 预期：decision: HITL, primary_reason: MATRIX_R3_MONEY
```

### 场景 3: 缺少关键字段时收紧决策

**需求：** 当退款请求缺少 order_id 时，收紧决策。

**配置步骤：**

1. **在 `config/risk_rules.yaml` 中定义缺失字段规则**：
```yaml
rules:
  - rule_id: "RISK_MISSING_KEY_FIELDS"
    type: "missing_fields"
    risk_level: "R1"
    required_fields: ["order_id"]
    applies_when:
      tool_ids: ["refund.create"]
```

2. **在 `matrices/v0.1.yaml` 中定义缺失证据策略**：
```yaml
missing_evidence_policy:
  missing_risk: "tighten"  # 风险证据缺失 → 收紧 1 步
```

**验证：**
```bash
curl -X POST http://localhost:8000/decision \
  -H "Content-Type: application/json" \
  -d '{"text": "我要退款", "context": {"tool_id": "refund.create"}}'
# 预期：decision 会被收紧（如 ALLOW → ONLY_SUGGEST）
```

---

## ✅ 配置验证和测试

### 1. 语法验证

**YAML 语法检查：**
```bash
# 使用 Python 验证 YAML 语法
python3 -c "import yaml; yaml.safe_load(open('matrices/v0.1.yaml'))"
python3 -c "import yaml; yaml.safe_load(open('config/risk_rules.yaml'))"
python3 -c "import yaml; yaml.safe_load(open('tools/catalog.yaml'))"
```

### 2. 配置完整性检查

**检查必需字段：**
- Matrix: `version`, `defaults`, `rules`
- Risk Rules: `version`, `rules`
- Tool Catalog: `tools`
- Permission Policies: `roles`, `action_permissions`

### 3. 功能测试

**运行测试套件：**
```bash
make test
```

**回放案例验证：**
```bash
make replay
# 预期：100% accuracy
```

**对比不同矩阵版本：**
```bash
make replay-diff
# 预期：显示决策变化率
```

### 4. 配置验证清单

- [ ] 所有 YAML 文件语法正确
- [ ] Matrix 中的 `action_types` 与 Tool Catalog 中的 `action_type` 一致
- [ ] Risk Rules 中的 `tool_ids` 与 Tool Catalog 中的 `tool_id` 一致
- [ ] Permission Policies 中的 `action_types` 与 Tool Catalog 中的 `action_type` 一致
- [ ] 所有测试通过
- [ ] 案例回放 100% 准确

---

## 🔧 常见问题和故障排查

### 问题 1: Matrix 文件未找到

**错误信息：**
```
System configuration error: Matrix file not found: matrices/v0.1.yaml
```

**解决方案：**
1. 检查文件路径：确保 `matrices/v0.1.yaml` 存在于项目根目录
2. 检查环境变量：如果设置了 `AI_RESPONSIBILITY_GATE_MATRICES_DIR`，确保路径正确
3. 检查文件权限：确保文件可读

### 问题 2: YAML 语法错误

**错误信息：**
```
Invalid YAML in matrix file: ...
```

**解决方案：**
1. 使用 YAML 验证工具检查语法
2. 检查缩进（YAML 对缩进敏感）
3. 检查特殊字符（引号、冒号等）

### 问题 3: 配置不生效

**可能原因：**
1. 配置加载顺序错误
2. 规则匹配条件不满足
3. 优先级被其他规则覆盖

**排查步骤：**
1. 启用 `verbose: true` 查看详细追踪
2. 检查 `rules_fired` 字段，确认哪些规则被触发
3. 检查 `primary_reason` 字段，确认决策原因

### 问题 4: 决策不符合预期

**排查步骤：**
1. **检查证据收集**：
   ```bash
   curl -X POST http://localhost:8000/decision \
     -H "Content-Type: application/json" \
     -d '{"text": "...", "verbose": true}'
   ```

2. **检查规则匹配**：
   - 确认 `risk_level` 是否正确
   - 确认 `action_type` 是否正确
   - 确认 `permission_ok` 是否正确

3. **检查优先级**：
   - RISK_GUARANTEE_CLAIM → DENY（最高优先级）
   - Permission denied → HITL
   - Matrix rule match
   - Missing evidence → tighten
   - Conflict resolution
   - Low confidence → tighten
   - Routing weak signal → tighten
   - Postcheck → tighten

---

## 🎓 最佳实践和进阶技巧

### 1. 配置版本管理

**建议：**
- 使用版本号命名 Matrix 文件（如 `v0.1.yaml`, `v0.2.yaml`）
- 在配置文件中添加 `version` 字段
- 使用 Git 管理配置变更历史

### 2. 配置分层策略

**建议：**
- **基础配置**：定义通用规则（如默认决策）
- **业务配置**：定义业务特定规则（如高额阈值）
- **环境配置**：使用环境变量覆盖（如测试环境 vs 生产环境）

### 3. 配置测试策略

**建议：**
- 为每个配置变更创建测试案例
- 使用 `make replay` 验证配置变更的影响
- 使用 `make replay-diff` 对比不同版本的决策差异

### 4. 配置文档化

**建议：**
- 在配置文件中添加注释说明规则目的
- 维护配置变更日志
- 记录每个规则的业务背景

### 5. 配置优化技巧

**建议：**
- **避免过度配置**：优先使用默认决策，只在必要时添加规则
- **规则优先级**：理解规则优先级，避免冲突
- **性能考虑**：关键词规则按频率排序，高频规则在前

---

## 📚 总结

### 配置流程总结

1. **定义工具**（`tools/catalog.yaml`）→ 定义动作类型和路由
2. **定义风险规则**（`config/risk_rules.yaml`）→ 定义什么情况是高风险
3. **定义权限策略**（`config/permission_policies.yaml`）→ 定义谁可以做什么
4. **定义决策矩阵**（`matrices/v0.1.yaml`）→ 定义决策规则
5. **配置知识库**（`config/kb_meta.yaml`）→ 定义知识库状态

### 配置原则

- **Fail-Closed（失败关闭）**：证据缺失时默认收紧决策
- **只紧不松（Tighten-Only）**：Override 只能收紧，不能放松
- **证据分离**：证据提供者只返回证据，不返回决策
- **决策集中**：只有 `gate.py` 能输出最终决策

### 下一步

- 阅读 [README.md](README.md) 了解系统架构
- 查看 [案例库](cases/) 了解实际使用场景
- 运行 `make replay` 验证配置

---

**祝你配置顺利！如有问题，请查看 [故障排查](#常见问题和故障排查) 部分。**
