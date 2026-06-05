# Codex Runtime PRD

## 1. 模块目标

Codex Runtime 模块负责将 AwesomeFundOS 落地为 Local-first Codex OS。V1 优先使用 CLI、文件系统、Threads、Skills 和 Harness，不先建设完整 Web App。

## 2. Runtime 组成

### 2.1 Codex CLI

用于：

- 本地文件编排；
- 创建 run workspace；
- 调用 harness；
- 生成 artifacts；
- 执行工具 wrapper；
- 实现 `fundos` CLI。

### 2.2 Codex SDK

用于：

- 可编程 Agent 调用；
- 结构化输出；
- model routing；
- parallel task execution；
- tool call orchestration。

### 2.3 Threads

用于：

- Agent persistent memory；
- run workspace；
- debate transcript；
- reflection log。

### 2.4 Skills

用于：

- 角色专属分析流程；
- 研究框架；
- 数据检索和解析流程；
- Harness 检查；
- 学习源蒸馏；
- 复盘流程。

### 2.5 Codex App Server

V1 不要求；未来用于：

- Web UI；
- dashboard；
- persistent thread 管理；
- Agent 管理；
- Watchlist 浏览器。

## 3. 目录结构

```text
AwesomeFundOS/
  agents/
  configs/
  docs/prd/
  harness/
  memory/
  runs/
  skills/
  specs/
  tools/
```

V1 当前先生成 `docs/` 和 `specs/`，后续实现时再创建 runtime 目录。

## 4. ModelPolicy

每个 Agent 有 ModelPolicy：

- provider
- default_model
- reasoning_effort
- context_budget_tokens
- tool_use_allowed
- code_execution_allowed
- web_research_allowed
- max_cost_per_run
- task_overrides

每次运行必须记录：

- agent_id
- model
- reasoning_effort
- context_pack_id
- skill_versions
- tool_versions

## 5. CLI 命令

V1 目标命令：

- `fundos init`
- `fundos run --topic ...`
- `fundos run --stock ...`
- `fundos run --question ...`
- `fundos eval --run ...`
- `fundos evolve --run ...`
- `fundos inspect --run ...`
- `fundos roster list`
- `fundos memory show --agent ...`

详见 `specs/cli/commands.md`。

## 6. 验收标准

- 能用 CLI 创建 run workspace。
- 能加载默认 Agent roster。
- 能生成 EvidencePack、ContextPack、Agent outputs、DecisionMemo、EvaluationReport。
- 能将 run artifacts 归档。
- 能以文件为接口支持 Codex 后续实现和调试。
