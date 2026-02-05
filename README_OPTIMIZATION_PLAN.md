# README 国际化规范优化计划

## 当前 README 评估

### ✅ 已符合国际规范的部分

1. **项目标题和描述** ✅
   - 清晰的标题：AI Responsibility Gate
   - What & Why 章节说明项目价值

2. **快速开始（Quickstart）** ✅
   - 安装步骤
   - 启动命令
   - 测试命令
   - cURL 示例

3. **架构说明** ✅
   - 详细的架构流程图
   - Evidence Providers 说明

4. **配置说明** ✅
   - Matrix 配置
   - Risk Rules 配置
   - Tool Catalog 配置

5. **案例库** ✅
   - 详细的 Case 卡片格式
   - 可回放的案例

6. **Roadmap** ✅
   - PoC → MVP → Production 路线图

7. **扩展性说明** ✅
   - 如何新增 Evidence Provider
   - 如何接入 LLM Classifier

8. **验收与自检** ✅
   - 决策权集中性扫描
   - 功能验收命令

### ❌ 缺失的国际规范部分

1. **目录（Table of Contents）** ❌
   - 缺少导航目录，长文档难以浏览

2. **特性列表（Features）** ❌
   - 缺少清晰的功能特性列表

3. **徽章（Badges）** ❌
   - 缺少项目状态、版本、测试覆盖率等徽章

4. **贡献指南（Contributing）** ❌
   - 缺少如何贡献代码的指南

5. **完整的 API 文档** ⚠️
   - 只有 Feedback API，缺少完整的 `/decision` API 文档

6. **依赖说明** ⚠️
   - requirements.txt 存在，但 README 中缺少依赖版本说明

7. **故障排查（Troubleshooting）** ❌
   - 缺少常见问题和解决方案

8. **项目状态/版本信息** ❌
   - 缺少版本号、项目状态（PoC/MVP/Production）

9. **英文版本** ⚠️
   - 当前为中文，国际化项目通常需要英文版本

10. **代码示例的语言标识** ⚠️
    - 部分代码块缺少语言标识

## 优化建议

### 优先级 P0（必须添加）

1. **添加目录（Table of Contents）**
   - 在 README 开头添加完整的目录导航
   - 使用 Markdown 锚点链接

2. **添加特性列表（Features）**
   - 在 What & Why 之后添加 Features 章节
   - 列出核心功能特性

3. **完善 API 文档**
   - 添加完整的 `/decision` API 文档
   - 包含请求/响应格式、状态码、错误处理

### 优先级 P1（强烈建议）

4. **添加贡献指南（Contributing）**
   - 说明如何提交 PR
   - 代码风格要求
   - 测试要求

5. **添加故障排查（Troubleshooting）**
   - 常见问题（如配置路径错误、矩阵加载失败等）
   - 解决方案

6. **添加项目状态信息**
   - 在标题下方添加版本号和状态徽章
   - 说明当前是 PoC 阶段

### 优先级 P2（可选优化）

7. **添加徽章（Badges）**
   - Python 版本
   - 测试状态
   - 许可证

8. **添加依赖说明**
   - 在 Quickstart 之前添加 Requirements 章节
   - 说明 Python 版本要求

9. **代码示例优化**
   - 为所有代码块添加语言标识
   - 统一代码格式

10. **考虑英文版本**
    - 创建 README_EN.md 或使用双语 README

## 具体优化方案

### 1. 添加目录

在 README 开头（What & Why 之前）添加：

```markdown
## Table of Contents

- [What & Why](#what--why)
- [Hard Constraints](#hard-constraints-三条铁律)
- [Architecture](#architecture)
- [Features](#features)
- [Quickstart](#quickstart)
- [Case Library](#案例库case-library)
- [API Documentation](#api-documentation)
- [Policy Configuration](#policy-配置说明)
- [Roadmap](#roadmap-poc--mvp--production)
- [Extensibility](#extensibility)
- [Contributing](#contributing)
- [Troubleshooting](#troubleshooting)
- [License](#license)
```

### 2. 添加 Features 章节

在 What & Why 之后添加：

```markdown
## Features

- 🎯 **Decision Centralization** - Single source of truth for all decisions
- 🔍 **Evidence-Based** - Multi-dimensional evidence collection (risk, permission, knowledge, routing, tool)
- 🔒 **Fail-Closed** - Default deny when evidence is missing or ambiguous
- ⚙️ **YAML-Driven** - Policy configuration without code changes
- 🔄 **Replay & Diff** - Reproducible decision verification
- 📊 **Audit Trail** - Verbose mode for complete decision trace
- 🚀 **Extensible** - Easy to add new evidence providers
- ⚡ **Concurrent** - Async evidence collection with timeout (80ms)
```

### 3. 完善 API 文档

添加完整的 API 文档章节：

```markdown
## API Documentation

### POST /decision

Make a decision on whether AI can answer the user's request.

**Request:**
```json
{
  "text": "这个产品收益率多少？",
  "session_id": "optional",
  "user_id": "optional",
  "context": {"optional": "fields"},
  "debug": false,
  "verbose": false
}
```

**Response:**
```json
{
  "request_id": "uuid",
  "decision": "ONLY_SUGGEST",
  "responsibility_type": "Information",
  "primary_reason": "DEFAULT_DECISION",
  "suggested_action": "handoff",
  "explanation": {...},
  "policy": {...},
  "latency_ms": 45
}
```

**Status Codes:**
- 200: Success
- 400: Invalid request (e.g., empty text)
- 500: System configuration error (e.g., matrix file not found)
```

### 4. 添加 Contributing 章节

```markdown
## Contributing

We welcome contributions! Please follow these guidelines:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Follow code style**
   - Use type hints
   - Follow PEP 8
   - Add docstrings
4. **Add tests** for new features
5. **Ensure all tests pass** (`make test`)
6. **Ensure replay accuracy** remains 100% (`make replay`)
7. **Commit changes** (`git commit -m 'Add amazing feature'`)
8. **Push to branch** (`git push origin feature/amazing-feature`)
9. **Open a Pull Request**

**Important:** All changes must maintain the three hard constraints:
- Decision centralization
- Evidence-based (no decision leakage)
- Fail-closed principle
```

### 5. 添加 Troubleshooting 章节

```markdown
## Troubleshooting

### Matrix file not found

**Error:** `System configuration error: Matrix file not found`

**Solution:** Ensure matrix files exist in `matrices/` directory. Check file paths in `src/core/config.py`.

### Configuration path errors

**Error:** `Config file not found`

**Solution:** Ensure you're running from project root directory, or set environment variables:
- `AI_RESPONSIBILITY_GATE_CONFIG_DIR`
- `AI_RESPONSIBILITY_GATE_MATRICES_DIR`

### Tests fail with import errors

**Error:** `ImportError: cannot import name 'X'`

**Solution:** Ensure you're running tests with `PYTHONPATH=.` or use `make test`.
```

## 优化后的 README 结构建议

```markdown
# AI Responsibility Gate

[Badges: Python 3.10+, PoC Status, MIT License]

## Table of Contents
[...]

## What & Why
[...]

## Features
[...]

## Hard Constraints (三条铁律)
[...]

## Architecture
[...]

## Quickstart
[...]

## Requirements
- Python 3.10+
- See `requirements.txt` for dependencies

## Case Library
[...]

## API Documentation
[...]

## Policy Configuration
[...]

## Roadmap
[...]

## Extensibility
[...]

## Contributing
[...]

## Troubleshooting
[...]

## License
MIT License
```

## 总结

当前 README 在**内容完整性**方面做得很好，但在**国际化规范**方面还有改进空间：

**优势：**
- ✅ 内容详细、可复现
- ✅ 架构说明清晰
- ✅ 案例库完整

**需要改进：**
- ❌ 缺少目录导航
- ❌ 缺少特性列表
- ❌ 缺少贡献指南
- ⚠️ API 文档不完整
- ❌ 缺少故障排查

**建议优先级：**
1. P0: 添加目录、特性列表、完善 API 文档
2. P1: 添加贡献指南、故障排查
3. P2: 添加徽章、考虑英文版本
