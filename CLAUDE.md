# 星期五 (Friday) 项目

## 已安装的技能

本项目已集成两个强大的 Claude Code 技能插件：

### 🎯 gstack - 虚拟工程团队
- **版本**: 1.58.3.0
- **功能**: 提供完整的工程团队工作流，包含 23+ 专业技能
- **仓库**: https://github.com/garrytan/gstack

### ⚡ superpowers - 完整开发方法论
- **版本**: 6.0.3
- **功能**: 提供系统化的软件开发流程
- **仓库**: https://github.com/obra/superpowers

---

## 技能使用指南

### gstack 技能命令

在 Claude Code 对话中使用斜杠命令：

```bash
# 代码审查（Staff 工程师级别）
/gstack review

# QA 测试（真实浏览器测试）
/gstack qa

# 发布管理
/gstack ship

# 调查调试
/gstack investigate

# 安全审查
/gstack cso

# CEO 战略审查
/gstack plan-ceo-review

# 设计审查
/gstack plan-design-review

# 工程管理审查
/gstack plan-eng-review
```

### superpowers 技能命令

```bash
# 头脑风暴（必须在任何创造性工作前使用）
/superpowers brainstorming

# 测试驱动开发
/superpowers test-driven-development

# 系统调试
/superpowers systematic-debugging

# 计划制定
/superpowers writing-plans

# 计划执行
/superpowers executing-plans

# Git 工作流
/superpowers using-git-worktrees

# 完成开发分支
/superpowers finishing-a-development-branch
```

### 实际使用示例

#### 示例 1：代码审查
```
用户: 帮我审查一下 Friday 的 agent.py 代码
Claude: 我将使用 gstack 的 review 技能进行专业代码审查...
[自动调用 /gstack review]
```

#### 示例 2：头脑风暴新功能
```
用户: 帮我想想 Friday 还能加什么功能
Claude: 我将使用 superpowers 的 brainstorming 技能来系统化地探索想法...
[自动调用 /superpowers brainstorming]
```

#### 示例 3：TDD 开发
```
用户: 用测试驱动的方式实现一个新的工具
Claude: 我将使用 superpowers 的 test-driven-development 技能...
[自动调用 /superpowers test-driven-development]
```

---

## 项目架构

本项目采用 Agent 架构，分为 5 个逻辑层：

1. **桌面壳** (`desktop.py`) - pywebview 窗口管理
2. **API 服务** (`server.py` + `api/`) - FastAPI 后端
3. **Agent 引擎** (`agent.py` + `brain.py`) - 对话和工具调用
4. **工具系统** (`tools/`) - 28+ 本地工具
5. **安全与审批** (`safety.py`) - 三级风险分类

## 技术栈

- **后端**: Python 3.11+, FastAPI, Uvicorn
- **前端**: 纯 HTML + CSS + JavaScript
- **桌面**: pywebview (Edge WebView2)
- **AI**: OpenAI 兼容 API (DeepSeek, 火山方舟等)

## 快速开始

```bash
# 启动开发服务器
python run.py

# 运行测试
pytest tests/

# 构建应用
scripts/build.ps1
```

---

*最后更新: 2026-06-19*
