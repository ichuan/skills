> 📖 [English](./README.md) | 中文

# 个人 Skills 集合

适用于 Claude Code、Cursor、Windsurf 等 AI 编程助手的可复用 Skill 集合。

## 概述

本仓库包含遵循 Agent Skills 规范的技能模块，可通过 `npx skills add` 安装到任意支持该规范的 AI 助手中。

## 安装

### 从 GitHub 安装

```bash
# 安装全部 skill
npx skills add ichuan/skills

# 安装指定 skill
npx skills add ichuan/skills --skill roadmap-management
npx skills add ichuan/skills --skill iterative-code-review
npx skills add ichuan/skills --skill deploy-caddy-reverse-proxy
npx skills add ichuan/skills --skill searxng-search
npx skills add ichuan/skills --skill crawl4ai-fetch
npx skills add ichuan/skills --skill repo-deploy-capture
npx skills add ichuan/skills --skill prod-readiness-audit
npx skills add ichuan/skills --skill multi-agent-review

# 全局安装（在所有项目中可用）
npx skills add ichuan/skills --skill roadmap-management --global
npx skills add ichuan/skills --skill iterative-code-review --global
npx skills add ichuan/skills --skill deploy-caddy-reverse-proxy --global
npx skills add ichuan/skills --skill searxng-search --global
npx skills add ichuan/skills --skill crawl4ai-fetch --global
npx skills add ichuan/skills --skill repo-deploy-capture --global
npx skills add ichuan/skills --skill prod-readiness-audit --global
npx skills add ichuan/skills --skill multi-agent-review --global
```

### 手动安装

```bash
# 克隆仓库
git clone https://github.com/ichuan/skills.git

# 复制到全局 skills 目录
cp -r skills/skills/roadmap-management ~/.claude/skills/
cp -r skills/skills/iterative-code-review ~/.claude/skills/
cp -r skills/skills/deploy-caddy-reverse-proxy ~/.claude/skills/
cp -r skills/skills/searxng-search ~/.claude/skills/
cp -r skills/skills/crawl4ai-fetch ~/.claude/skills/
cp -r skills/skills/repo-deploy-capture ~/.claude/skills/
cp -r skills/skills/prod-readiness-audit ~/.claude/skills/
cp -r skills/skills/multi-agent-review ~/.claude/skills/

# 或复制到项目本地目录
mkdir -p ./.claude/skills
cp -r skills/skills/roadmap-management ./.claude/skills/
cp -r skills/skills/iterative-code-review ./.claude/skills/
cp -r skills/skills/deploy-caddy-reverse-proxy ./.claude/skills/
cp -r skills/skills/searxng-search ./.claude/skills/
cp -r skills/skills/crawl4ai-fetch ./.claude/skills/
cp -r skills/skills/repo-deploy-capture ./.claude/skills/
cp -r skills/skills/prod-readiness-audit ./.claude/skills/
cp -r skills/skills/multi-agent-review ./.claude/skills/
```

## Skills 详情

### roadmap-management

基于位置优先级的极简项目路线图管理。

**适用场景：**
- 个人开发者和小团队的项目管理
- 快速捕获和整理任务
- 无需复杂优先级评分的轻量工作流

**功能特性：**
- 📥 **Inbox**：快速记录想法和任务
- 🟢 **Doing**：当前进行中（限 2-3 项）
- 🟡 **Next Up**：手动排序的待办列表
- ⚪ **Backlog**：未来任务
- 📔 **Done**：最近完成项（最新 5 条）
- 📜 **CHANGELOG.md**：含日期和 commit 的完整完成历史

**使用示例：**
```
"为当前项目创建路线图"
"把这个 bug 加入 roadmap"
"更新 roadmap，标记功能为完成"
"把完成的任务归档到 CHANGELOG"
```

**详情：** 见 [skills/roadmap-management](./skills/roadmap-management)

---

### iterative-code-review

多 Agent 并发 code review + 自动修复，循环迭代直到收敛。

**适用场景：**
- 完成 feature 或 fix 后的自动化质量门禁
- 合并前发现 bug、安全问题和可靠性隐患
- 自愈循环：review → 修复 → 再 review，直到无问题为止

**功能特性：**
- 🤖 **5 个并行 sub-agent**：逻辑正确性、安全性、性能、可靠性、代码质量，各自在独立上下文中 review
- 🔁 **迭代循环**：修复后自动触发下一轮 review，收敛或达到 `max_iterations` 后停止
- 🧹 **主 session 上下文隔离**：sub-agent 自行 fetch `git diff`，主 session 不被 diff 内容污染
- 🎯 **噪音过滤**：仅 Critical / High + Confidence ≥ 0.70 的问题才触发自动修复
- 💣 **影响范围保护**：高影响修复（公开 API 变更）需要更高置信度才执行
- 📋 **结构化最终报告**：已修复/跳过问题表、遗留风险、合并建议

**使用示例：**
```
"使用 iterative-code-review skill 做 code review"
"review and fix my changes"
"做 code review，max_iterations=5"
```

**详情：** 见 [skills/iterative-code-review](./skills/iterative-code-review)

---

### deploy-caddy-reverse-proxy

在远程服务器上自动部署 Caddy 反向代理，含 SSL 证书和 systemd 服务配置。

**适用场景：**
- 为本地 Web 服务配置反向代理
- 自动申请和管理 Let's Encrypt SSL 证书
- 配置开机自启的 systemd 服务
- 代理 HTTP/WebSocket 流量

**功能特性：**
- 🔒 **自动 SSL**：Let's Encrypt 证书申请与自动续期
- 🔄 **反向代理**：HTTP/WebSocket 流量转发
- ⚙️ **Systemd 集成**：自动启动与崩溃恢复
- 🎯 **智能检测**：自动识别系统环境，选择最优配置
- 📋 **交互式配置**：通过问答收集部署参数
- ✅ **部署验证**：自动验证证书、端口和 HTTPS 访问

**使用示例：**
```
"部署 caddy 反向代理"
"给我的 web 服务配置 caddy"
"配置带 SSL 的 caddy"
```

**详情：** 见 [skills/deploy-caddy-reverse-proxy](./skills/deploy-caddy-reverse-proxy)

---

### searxng-search

通过自托管的 [SearXNG](https://github.com/searxng/searxng) 聚合搜索服务器进行网页搜索。

**适用场景：**
- 在 AI Agent 中直接搜索网络
- 研究话题、查找 URL、在线查询信息
- 自托管、保护隐私的商业搜索 API 替代方案

**功能特性：**
- 🔍 **NDJSON 输出**：每行一条结构化 `{url, title, snippet}` 结果
- 🔑 **Bearer 认证支持**：可为受保护实例配置 token
- 📄 **分页支持**：`--page` / `--limit` 参数获取更多结果
- 🗂️ **`.env` 自动加载**：若环境变量未设置，自动从项目根目录的 `.env` 读取 `SEARXNG_URL` / `SEARXNG_TOKEN`

**使用示例：**
```
"搜索 Python 3.13 最新发布说明"
"查找 Caddy 服务器的文档"
"搜索 LLM 基准测试最新动态"
```

**详情：** 见 [skills/searxng-search](./skills/searxng-search)

#### 使用 Caddy Bearer Auth 部署 SearXNG

SearXNG 本身不带认证功能。以下 Caddy 配置片段为实例添加 Bearer token 认证：

```caddy
# Caddyfile

(auth_bearer) {
    handle {
        @valid_token header Authorization "Bearer {args[0]}"
        route @valid_token {
            reverse_proxy {args[1]} {
                header_up Host {http.reverse_proxy.upstream.hostport}
            }
        }

        @invalid_token not header Authorization "Bearer {args[0]}"
        respond @invalid_token "Unauthorized" 401
    }
}

search.example.com {
    encode gzip
    import auth_bearer YOUR_SECRET_TOKEN http://127.0.0.1:8001
}
```

将 `search.example.com`、`YOUR_SECRET_TOKEN` 和 `http://127.0.0.1:8001`（SearXNG 监听地址）替换为你自己的值，Caddy 会自动申请 Let's Encrypt TLS 证书。

然后配置 skill：

```
# .env（项目根目录）
SEARXNG_URL=https://search.example.com
SEARXNG_TOKEN=YOUR_SECRET_TOKEN
```

---

### crawl4ai-fetch

通过自托管的 [crawl4ai](https://github.com/unclecode/crawl4ai) 服务器将任意 URL 转换为干净的 Markdown。

**适用场景：**
- 为 LLM 读取和总结网页内容
- 将文章或文档内容提取为 Markdown
- 抓取普通 HTTP 客户端无法读取的 JavaScript 渲染页面

**功能特性：**
- 📄 **Markdown 输出**：将任意 URL 转换为 LLM 友好的干净 Markdown
- 🎯 **过滤模式**：`fit`（智能提取）、`raw`（完整页面）、`bm25`（相关性过滤）
- 🔑 **Bearer 认证支持**：可为受保护实例配置 token
- 🗂️ **`.env` 自动加载**：若环境变量未设置，自动从项目根目录的 `.env` 读取 `CRAWL4AI_URL` / `CRAWL4AI_TOKEN`

**使用示例：**
```
"抓取 https://docs.example.com/api 并总结内容"
"获取这篇新闻文章的内容：https://..."
"读取这个页面并回答我关于它的问题"
```

**详情：** 见 [skills/crawl4ai-fetch](./skills/crawl4ai-fetch)

#### 使用 Caddy Bearer Auth 部署 crawl4ai

启动 crawl4ai Docker 容器：

```bash
docker stop crawl4ai
docker run --rm -itd \
  -p 8002:11235 \
  --name crawl4ai \
  --shm-size=1g \
  unclecode/crawl4ai:latest
```

在 Caddyfile 中复用上方 SearXNG 的 `auth_bearer` 片段，添加站点块：

```caddy
crawl.example.com {
    encode gzip
    import auth_bearer YOUR_SECRET_TOKEN http://127.0.0.1:8002
}
```

配置 skill：

```
# .env（项目根目录）
CRAWL4AI_URL=https://crawl.example.com
CRAWL4AI_TOKEN=YOUR_SECRET_TOKEN
```

### repo-deploy-capture

在一次真实部署成功后，把可复用的部署流程记录到项目文档或记忆中。

**适用场景：**
- 记录刚刚验证通过的部署路径
- 保存 health check、smoke check 和回滚命令
- 记录部署踩坑，同时避免泄露 secret

**功能特性：**
- 📋 **操作化记录**：聚焦命令、目录、检查项和成功信号
- 🔐 **敏感信息清理**：避免把 secret 和私有基础设施写进通用说明
- 🎯 **单一事实来源**：优先维护一个权威部署文档

**使用示例：**
```
"记录一下刚刚用过的部署流程"
"把这次正确的服务器更新步骤保存下来"
"把部署踩坑写到项目文档里"
```

**详情：** 见 [skills/repo-deploy-capture](./skills/repo-deploy-capture)

### prod-readiness-audit

上线前审计并加固项目，在安全范围内直接修复发现的问题。

**适用场景：**
- 最终上线前检查
- 响应式、明暗主题、SEO 和性能收尾
- 安全、测试、部署准备和生产 smoke 验证

**功能特性：**
- 🧭 **结构化审计**：覆盖基线、功能完整性、响应式、主题、SEO、性能、安全和部署
- 🛠️ **修复导向**：优先修复具体问题，而不是只做报告
- ✅ **验证闭环**：要求在可行时执行测试、构建、浏览器检查、Lighthouse 或 smoke check

**使用示例：**
```
"上线前整体审计这个项目"
"处理响应式、暗黑模式、SEO、性能和安全问题"
"看看这个项目能不能部署上线，并修复阻塞项"
```

**详情：** 见 [skills/prod-readiness-audit](./skills/prod-readiness-audit)

---

### multi-agent-review

基于本地 Claude Code / Codex CLI 进程的可配置多模型 code review 工作流。

**适用场景：**
- commit / merge 前审查未提交改动或 feature branch
- 让多个模型独立 review，再汇总为人工可勾选的 `summary.md`
- 一个模型修复选中的问题，另一个模型独立验证

**功能特性：**
- 🤖 **3 个配置化 review 模型**：默认使用 `review_models` 前三个模型独立审查
- 🧾 **Runner 管理产物**：最终 stdout 写入 `.review-forge/artifacts/<feature>/reviews/`，过程日志写入 `logs/`
- 🧹 **主 session 隔离**：大 prompt 和 diff 写入被忽略的 `.review-forge/runs/`，不污染开发对话
- ✋ **人工决策门**：生成 `summary.md` 后停止，由用户勾选值得修的问题
- 🛠️ **修复 / 验证分离**：分别使用配置的 `fix_model` 和独立 `verify_model`
- 🔐 **单一本地工作区**：配置、运行时 prompt 和 review 产物都放在被忽略的 `.review-forge/`
- 🧷 **首次运行配置门禁**：`init` 默认生成 `config_ready: false`，用户确认模型配置前不会运行 review/fix
- 🔌 **可选连通性检查**：`check-config` 可在正式流程前测试各角色模型是否能跑通

**使用示例：**
```
"使用 multi-agent-review 审查未提交改动"
"用 multi-agent-review review 当前分支相对 origin/main 的修改"
"使用 multi-agent-review，生成 summary 后停下来让我选择要修的问题"
```

**详情：** 见 [skills/multi-agent-review](./skills/multi-agent-review)

---

## 使用验证

安装后，在 Claude Code 中测试：

```
"为当前项目创建路线图"
```

如果 Claude 开始执行操作，说明安装成功。

## 支持的 AI 助手

| 助手 | 项目路径 | 全局路径 |
|------|----------|----------|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |
| Windsurf | `.windsurf/skills/` | `~/.codeium/windsurf/skills/` |
| Cline | `.cline/skills/` | `~/.cline/skills/` |
| OpenCode | `.opencode/skills/` | `~/.config/opencode/skills/` |
| GitHub Copilot | `.github/skills/` | `~/.copilot/skills/` |

更多支持的助手见 [skills 文档](https://github.com/vercel-labs/skills#available-agents)。

## 全局安装 vs 本地安装

- **全局安装**（`~/.claude/skills/`）：在所有项目中可用
- **本地安装**（`./.claude/skills/`）：仅限当前项目，优先级高于全局

## 更新与卸载

### 更新 Skills

```bash
# 重新安装即可更新
npx skills add ichuan/skills --skill roadmap-management
npx skills add ichuan/skills --skill iterative-code-review
npx skills add ichuan/skills --skill searxng-search
npx skills add ichuan/skills --skill crawl4ai-fetch
npx skills add ichuan/skills --skill repo-deploy-capture
npx skills add ichuan/skills --skill prod-readiness-audit
npx skills add ichuan/skills --skill multi-agent-review
```

### 卸载 Skills

```bash
# 全局卸载
rm -rf ~/.claude/skills/roadmap-management
rm -rf ~/.claude/skills/iterative-code-review
rm -rf ~/.claude/skills/deploy-caddy-reverse-proxy
rm -rf ~/.claude/skills/searxng-search
rm -rf ~/.claude/skills/crawl4ai-fetch
rm -rf ~/.claude/skills/repo-deploy-capture
rm -rf ~/.claude/skills/prod-readiness-audit
rm -rf ~/.claude/skills/multi-agent-review

# 本地卸载
rm -rf ./.claude/skills/roadmap-management
rm -rf ./.claude/skills/iterative-code-review
rm -rf ./.claude/skills/deploy-caddy-reverse-proxy
rm -rf ./.claude/skills/searxng-search
rm -rf ./.claude/skills/crawl4ai-fetch
rm -rf ./.claude/skills/repo-deploy-capture
rm -rf ./.claude/skills/prod-readiness-audit
rm -rf ./.claude/skills/multi-agent-review
```

## 许可证

MIT License — 详见 [LICENSE](LICENSE) 文件。

## 相关链接

- [Agent Skills 规范](https://github.com/anthropics/skills)
- [skills 工具](https://github.com/vercel-labs/skills)
- [Claude Code 文档](https://github.com/anthropics/claude-code)
