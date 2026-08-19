# ChatDSL 综合指南

## 概述

ChatDSL（Chat Domain-Specific Language，聊天领域特定语言）是一种强大的脚本语言，专门用于自动化与大语言模型（LLM）的交互。本指南提供了使用 ChatDSL 进行操作的完整参考，包括功能特性、入门教程、常见任务指南以及详尽的关键字参考。

> *最后更新日期：2026年7月23日*
>
> *版本：1.0*
>
> *兼容 Chatybot v0.6.4+*

---

# 功能特性

## 核心能力

### 1. 多语言支持
ChatDSL 支持 6 种语言并具有完整的命令别名映射：
- **英语 (EN)** - 主要语言
- **西班牙语 (ES)** - 所有命令的西班牙语翻译
- **法语 (FR)** - 所有命令的法语翻译
- **中文 (ZH)** - 所有命令的中文翻译
- **意大利语 (IT)** - 所有命令的意大利语翻译
- **阿拉伯语 (AR)** - 所有命令的阿拉伯语翻译

### 2. 脚本特性
- **变量系统**：使用 `${名称}` 语法的脚本作用域变量
- **条件逻辑**：使用 `==`、`!=` 和 `not` 运算符的 `if` 语句（使用 `then` 执行命令）
- **缓冲区管理**：主缓冲区和 5 个文件库以实现持久上下文
- **多行输入**：跨越两行或多行的复杂提示词
- **文件操作**：加载、查看、清空和保存文件
- **脚本参数**：自定义脚本的 `x`、`y`、`z` 参数
- **宏**：利用 Parsley PEG 语法解析的可复用提示词模板
- **历史查找快捷操作**：使用 `!` 运算符搜索命令历史记录

### 3. LLM 集成
- **模型管理**：在 8 个服务商配置的 20 多个模型之间切换
- **系统提示**：设置核心行为规则
- **温度控制**：`0.0-2.0` 以控制回复的随机性
- **Token 限制**：控制补全生成的长度限制
- **采样控制**：`top_p`、`top_k`、`freq_penalty`（频率惩罚）、`pres_penalty`（存在惩罚）
- **推理控制**：`reasoning`（推理模式）、`effort`（推理强度）和 `thinking`（显示思考）控制
- **服务商专项优化**：针对 NVIDIA、Mistral、Google、OpenAI 的适配

### 4. 高级特性
- **工具循环**：支持工具调用（本地 + MCP）的自主执行循环
- **图像生成**：支持 OpenAI、Mistral、OpenRouter、Ollama
- **数据库集成**：基于 TinyDB 的向量数据库和重排（Rerank）支持
- **配置文件系统**：使用 `.chatdsl` 文件作为持久化会话配置文件
- **MCP 集成**：支持模型上下文协议（Model Context Protocol）服务器

### 5. 诊断与监控
- **追踪输出**：TPS（每秒 token 数）、原始 Payload、图像调试、重排以及智能体循环追踪
- **调试命令**：查看原始回复和虚拟内存使用情况
- **日志记录**：文件日志记录与错误跟踪
- **缓冲区审查**：检查内存和变量状态

---

# 项目结构

## 源码结构图

```
src/chatybot/                    # 主包目录
├── __init__.py                  # 版本："0.6.4"
├── main.py                      # 程序入口点 → chatybot_app.run()
├── chatybot_app.py              # 核心应用程序（5,887 行）
├── buffer_manager.py            # 文件库、图片库和脚本变量管理
├── chatydb.py                   # TinyDB 数据库集成
├── chaty_help.py                # 结构化帮助系统
├── chatdsl_parse.py             # ChatDSL 语法解析器
├── config_manager.py            # TOML 配置文件加载
├── config_model.py              # Pydantic 配置验证
├── config_sync.py               # 配置文件同步
├── config_tui.py                # 用于配置的终端 UI（TUI）
├── dispatcher.py                # 工具执行网关
├── extract_code.py              # 代码块提取器
├── image_generator.py           # 多服务商图像生成器
├── image_manager.py             # 图片加载工具类
├── localization.py              # i18n / 多语言支持
├── logging_manager.py           # 聊天日志记录器
├── macro.chatdsl                # 默认宏定义文件
├── mcp_client.py                # MCP 协议集成
├── menu.chatdsl                 # 菜单 DSL 脚本
├── pattern.py                   # 命令模式匹配器
├── profile_editor.py            # 基于 Curses 的配置文件编辑器
├── profile_manager.py           # 配置文件的 CRUD 操作
├── vendors.py                   # 服务商预设定义
├── chat_config.toml             # 默认模型配置
├── tools_config.toml            # 智能体模式的工具定义
├── translations.json            # 多语言翻译文件
├── profiles/                    # 预设配置文件脚本
├── tinydb1/corpus_manager.py    # TinyDB 封装器
└── tools/
    ├── __init__.py
    ├── file_utils.py            # 文件工具类：列出、读取、写入、搜索、运行、替换
    └── tool_config_tui.py       # 工具配置 TUI
```

## 入口点命令

```bash
chatybot                  # 主 CLI 入口点
chatdsl_parse             # DSL 解析器实用程序
chatybot-config           # 配置 TUI 编辑器
```

---

# 入门教程

## 教程 1：基础翻译工作流

本教程演示了如何使用 ChatDSL 在不同语言之间翻译文件。

### 准备工作
- 一个源文本文件 (`english.txt`)
- 已在 `~/.config/chatybot/chat_config.toml` 中配置好 API 密钥

### 逐步指南

1. **配置脚本参数**
   ```dsl
   # 使用方法：/脚本 translate.chatdsl x=english.txt y=spanish z=output.txt
   if ${x} != "" then 设置 source_file = ${x}
   if ${source_file} == "" then 设置 source_file = "english.txt"
   
   if ${y} != "" then 设置 target_lang = ${y}
   if ${target_lang} == "" then 设置 target_lang = "spanish"
   
   if ${z} != "" then 设置 output_file = ${z}
   if ${output_file} == "" then 设置 output_file = "output.txt"
   ```

2. **加载源文件**
   ```dsl
   /文件 ${source_file}
   ```

3. **执行翻译**
   ```dsl
   /回显 "Translating to ${target_lang}..."
   
   /模型 gemini_flash
   Translate ${target_lang}:
   
   /保存 ${output_file}
   ```

4. **查看结果**
   - 目标文件创建于 `${output_file}`
   - 翻译结果已以目标语言保存

### 完整脚本

```dsl
# translate.chatdsl
# 使用方法：/脚本 translate.chatdsl x=english.txt y=spanish z=output.txt

# 参数处理
if ${x} != "" then 设置 source_file = ${x}
if ${source_file} == "" then 设置 source_file = "english.txt"

if ${y} != "" then 设置 target_lang = ${y}
if ${target_lang} == "" then 设置 target_lang = "spanish"

if ${z} != "" then 设置 output_file = ${z}
if ${output_file} == "" then 设置 output_file = "output.txt"

# 加载源文件
/文件 ${source_file}

# 执行翻译
/回显 "Translating to ${target_lang}..."

/模型 gemini_flash
Translate ${target_lang}:

/保存 ${output_file}

/回显 "Translation saved to ${output_file}"
```

---

## 教程 2：使用 ChatDSL 进行文件对比

学习如何对比两个文件并找出关键差异。

### 使用方法
```bash
chatybot
chat --> /脚本 compare_articles.chatdsl x=article1.txt y=article2.txt z=comparison.txt
```

### 完整脚本

```dsl
# compare_articles.chatdsl
# 使用方法：/脚本 compare_articles.chatdsl x=article1.txt y=article2.txt z=comparison.txt

# 参数处理
if ${x} != "" then 设置 file1 = ${x}
if ${file1} == "" then 设置 file1 = "default1.txt"

if ${y} != "" then 设置 file2 = ${y}
if ${file2} == "" then 设置 file2 = "default2.txt"

if ${z} != "" then 设置 output = ${z}
if ${output} == "" then 设置 output = "comparison.txt"

# 加载文件到文件库中
/文件库1 ${file1}
/文件库2 ${file2}

/回显 "Comparing ${file1} and ${file2}"

# 生成对比分析
/系统提示 "You are a precise text comparison expert."

/多行输入
Compare these two articles and identify:
1. Structural differences
2. Content differences
3. Style differences

Article A:
{filebank1}

Article B:
{filebank2}

Provide a detailed comparison.
;;
/多行输入

# 保存结果
/保存 ${output}

/回显 "Comparison saved to ${output}"
```

### 预期输出
脚本将生成一份包含以下内容的详细对比：
- **结构差异**：章节顺序、标题、排版格式
- **内容差异**：事实、数据、主要观点
- **风格差异**：词汇、句式结构、语气

---

## 教程 3：多模型评估

评估不同的模型对相同提示词的回复质量。

### 使用方法
```bash
chatybot
chat --> /脚本 evaluate.chatdsl x=prompt.txt y=output_dir
```

### 完整脚本

```dsl
# evaluate.chatdsl
# 使用方法：/脚本 evaluate.chatdsl x=prompt_file y=output_dir

设置 prompt_file = ${x}
设置 output_dir = ${y}

# 模型 1 - GPT-4
/回显 "Processing with GPT-4..."
/模型 openai_gpt4
/prompt ${prompt_file}
/保存 ${output_dir}/gpt4_response.txt

# 模型 2 - Claude
/回显 "Processing with Claude..."
/模型 claude
/prompt ${prompt_file}
/保存 ${output_dir}/claude_response.txt

# 对比回复内容
/回显 "Comparing models..."

/文件库1 ${output_dir}/gpt4_response.txt
/文件库2 ${output_dir}/claude_response.txt

/多行输入
Compare these two responses to the same prompt:

Model A (GPT-4):
{filebank1}

Model B (Claude):
{filebank2}

Which is better and why?
;;
/多行输入
/保存 ${output_dir}/comparison.txt

/回显 "Evaluation complete! Results in ${output_dir}"
```

### 输出文件
- `${output_dir}/gpt4_response.txt` - GPT-4 回复内容
- `${output_dir}/claude_response.txt` - Claude 回复内容
- `${output_dir}/comparison.txt` - 旁对旁对比文件

---

# 常见任务指南 (HowTos)

## 如何：配置 Chatybot

### 配置文件位置
```bash
~/.config/chatybot/chat_config.toml    # 用户配置文件（会覆盖默认值）
src/chatybot/chat_config.toml          # 预装的默认配置文件
```

### 配置文件格式 (TOML)

```toml
# ============================================================================
# 图像生成设置
# ============================================================================

[image_generation]
default_dir = "~/chatybot_images"
default_size = "1024x1024"
default_quality = "standard"

# ============================================================================
# 聊天模型列表
# ============================================================================

[models.mistral_1]
name = "mistral-large-2512"
temperature = 0.7
top_k = 1
base_url = "https://api.mistral.ai/v1"
api_key = "MISTRAL_API_KEY"
image_generation = true
image_endpoint = "/images/generations"
vendor = "mistral"

[models.gemini_flash]
name = "gemini-2.5-flash"
temperature = 0.0
top_k = 1
base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
api_key = "GEMINI_API_KEY"
image_generation = true
vendor = "google"

[models.openai_gpt4]
name = "gpt-4o"
temperature = 0.1
top_k = 1
base_url = "https://api.openai.com/v1"
api_key = "OPENAI_API_KEY"
image_generation = true
vendor = "openai"

[models.ollama_llama3]
name = "llama3.2"
temperature = 0.7
top_k = 1
base_url = "http://localhost:11434/v1"
api_key = "OLLAMA"
```

### 模型配置项属性

| 属性名称 | 类型 | 说明描述 |
|-----------|------|-------------|
| `name` | string | 模型标识符 (API 专属) |
| `temperature` | float | 回复的随机性 (0.0-2.0) |
| `top_k` | integer | Top-K 采样范围数 |
| `base_url` | string | API 接口基地址 URL |
| `api_key` | string | 存放 API 密钥的环境变量名称 |
| `image_generation` | boolean | 是否启用图片生成能力支持 |
| `image_endpoint` | string | 图片生成的 API 端点路径 |
| `vendor` | string | 服务商标识符 |

### 支持的服务商列表

| 服务商标识 | 说明 |
|-----------|-------------|
| `mistral` | Mistral AI 官方 API |
| `google` | 谷歌生成式 AI API |
| `openai` | OpenAI 官方 API |
| `openrouter` | OpenRouter 聚合 API |
| `nvidia` | NVIDIA NIM API |
| `publicai` | PublicAI API |
| `bytez` | Bytez API |
| `ollama` | 本地 Ollama 服务 |

### 工具调用配置

文件位置：`src/chatybot/tools_config.toml`

```toml
[config]
tool_timeout = 60
rate_limit_delay = 2.0
max_turns = 25
strip_thinking_from_filebanks = true
shell = true
default_profile = ""
profile_dir = "~/.config/chatybot/profiles"
enable_profile_edit = true

agentic_instructions = """
IMPORTANT: You are executing in an autonomous, multi-turn tool-calling loop.
Use tools ONLY when necessary to perform actions on the system or fetch external information.
1. You can output one or more tool calls in a single turn if they can be executed in parallel or sequence. Use the JSON format enclosed in ```json ... ```.
2. Do NOT output any conversational text, descriptions, planning thoughts, or explanations before or after the tool calls.
3. Only output natural language when you have finished all tool executions and are ready to present the final result.
"""

[tools.list_directory]
enabled = true
description = "List contents of a directory"
module = "chatybot.tools.file_utils"
function = "list_directory"

[tools.read_file]
enabled = true
description = "Read the contents of a file"
module = "chatybot.tools.file_utils"
function = "read_file"
```

---

## 如何：批量处理文件

由于 ChatDSL 本身不支持显式循环，我们可以通过手动重复逻辑来处理多个文件：

### 脚本模板

```dsl
# batch.chatdsl
# 使用方法：/脚本 batch.chatdsl x=input_dir y=output_dir

设置 input_dir = ${x}
设置 output_dir = ${y}

# 文件 a
设置 file = "a.txt"
/文件 ${input_dir}/${file}
Analyze ${file}
/保存 ${output_dir}/${file}_processed.txt

# 文件 b
设置 file = "b.txt"
/文件 ${input_dir}/${file}
Analyze ${file}
/保存 ${output_dir}/${file}_processed.txt

# 文件 c
设置 file = "c.txt"
/文件 ${input_dir}/${file}
Analyze ${file}
/保存 ${output_dir}/${file}_processed.txt
```

---

## 如何：配置工具调用执行循环

### 开启工具模式
```dsl
# 在系统提示词中加载工具定义框架
/开启工具模式

# 启用所有可用工具
/启用工具 all

# 启用自动交互循环模式
/自动工具

# 设置默认的最大工具调用轮次
/最大工具轮次 10
```

### 执行工具循环
```dsl
/工具循环 50 force
```

### 检查工具状态
```dsl
/工具列表
/工具提示语
```

### 支持的系统工具列表

| 工具名称 | 工具描述 |
|-------------|-------------|
| `list_directory` | 列出目录下的子目录及文件列表 |
| `read_file` | 读取文件的全部文本内容 |
| `find_files` | 根据通配符模式搜索匹配的文件 |
| `run_command` | 执行本地 Shell 系统命令 |
| `write_file` | 写入或向指定文件追加文本内容 |
| `change_dir` | 改变当前的工作目录路径 |
| `grep_search` | 在指定路径的文件中进行文本行正则表达式检索 |
| `replace_file_content` | 对文件中的特定字符串内容进行查找并替换 |

### MCP 协议外部工具集成

MCP 工具会使用 `mcp__<服务名>__<工具名>` 作为命令空间标识符：
```dsl
# 查看从已连接服务器上自动发现的 MCP 工具
/工具列表

# 执行 MCP 工具
# (通过工具循环自主执行 - LLM 会生成对应的 JSON 块结构)
```

---

## 如何：图像生成工作流

### 基础图片生成操作
```dsl
# 设置图片输出参数
/图片目录 output/
/图片尺寸 1024x1024
/图片质量 hd

# 生成图片
/生图 a beautiful sunset over mountains

# 查看生成的历史图片列表
/列出图片

# 显示指定图片的生成元数据参数
/显示图片信息
```

### 保存生成的图片
```dsl
# 生成并保存图片
/生图 a cat playing with yarn
/saveimage images/cat_toy.jpg
```

### 加载图片到图片库中
```dsl
# 加载图片以便将其加入到后续提示词上下文
/加载图片 images/cat_toy.jpg imagebank1

# 在聊天输入中引用
Describe this image: {imagebank1}
```

### 图片库内存管理
```dsl
# 直接加载到特定图片库
/图片库1 path/to/image.jpg

# 显示当前图片库中的内容
/图片库1 show

# 清空图片库内存
/图片库1 clear
```

### 支持的图像生成模型与服务商

| 服务商名 | 模型简称 | 说明备注 |
|-----------|--------|-------|
| OpenAI | gpt-4o | 原生内置 DALL-E 图片生成支持 |
| Mistral | mistral-large-2512 | 通过 OpenAI 兼容格式接口生图 |
| Google | gemini-2.5-flash, gemini-2.5-pro | 通过 OpenAI 兼容接口生成图像 |
| OpenRouter | google/gemini-2.5-flash-image | 聊天补全模式的多模态生图支持 |
| OpenRouter | black-forest-labs/flux.2-klein-4b | 专属图像生成模型 |
| Ollama | 本地模型 | 通过 `/api/generate` 接口实现 |

---

## 如何：向量数据库集成

### 连接与多轮查询操作
```dsl
# 设置并打开目标数据库
/设置数据库 knowledge_base

# 搜索相关的知识文档条目
/搜索数据库 "machine learning algorithms 2024"

# 导入所有查询记录到变量中
/加载var ml_results ALL

# 将内容嵌入至提示词上下文中
/系统提示 "You are an AI expert with access to 2024 ML research."

Based on: ${ml_results}

What are the key developments in ML in 2024?

# 将聊天记录及结果同步存入数据库
/数据库日志
```

### 查询结果重排 (Rerank)
```dsl
# 执行一次数据库搜索并对结果进行二次重排
/搜索数据库 "climate change economics"
/重排

# 从重排结果中加载前 5 条记录到变量中
/加载var ranked_results TOP5
```

### 重排文档数据源选项

| 数据源类型 | 命令语法 | 说明描述 |
|--------|----------|-------------|
| 数据库 | `/文档源 db=<数据库名>` | 从 TinyDB 数据库中提取记录 |
| 变量 | `/文档源 var=<变量名>` | 从脚本变量中读取内容 |
| 文件库 | `/文档源 filebank=<1-5>` | 从指定文件库中读取缓存文本 |
| 目录路径 | `/文档源 dir="<路径>"` | 扫描并读取指定目录下的全部文本文件 |

### 向量数据库相关的全部命令

| 命令别名 | 功能描述 |
|---------|-------------|
| `/设置数据库 <数据库名>` | 创建或切换目标数据库 |
| `/设置数据库 Null` | 关闭/断开当前的向量数据库连接 |
| `/数据库列表` | 列出系统中可用的全部向量数据库列表 |
| `/搜索数据库 <查询关键字>` | 在数据库中执行基于文本的语义向量检索 |
| `/数据库日志` | 将上一次的完整问答记录保存到数据库中 |
| `/打印数据库 [输出文件名]` | 将数据库的全部内容转储输出 |
| `/加载var <变量名> [ALL\|条目ID\|范围]` | 将数据库查询记录读取到目标变量中 |
| `/保存var <变量名> <保存路径>` | 将变量中的记录信息保存到硬盘文件 |
| `/设置var <变量名> <变量值>` | 手动直接声明或设置一个脚本变量 |

---

## 如何：会话配置文件管理

### 会话配置文件控制命令

```dsl
# 列出可用的所有会话配置文件
/配置 list

# 加载并应用指定的配置文件
/配置 use my_profile

# 将当前的会话状态克隆另存为新配置文件
/配置 clone new_profile

# 删除已有的配置文件
/配置 delete old_profile

# 导出配置文件到指定位置
/配置 export my_profile export_path/

# 从硬盘位置导入已有的配置文件
/配置 import import_path/

# 显示当前激活的配置文件信息
/配置 show

# 在终端交互界面中直接编辑配置文件内容
/配置 edit
```

### 配置文件存储位置
```bash
~/.config/chatybot/profiles/    # 用户配置文件目录
src/chatybot/profiles/          # 系统预装的配置文件模板目录
```

---

## 如何：历史记录查找

```dsl
# 在终端提示符下使用 ! 加关键字搜索以往的指令历史
! machine learning

# 精确搜索某条特定命令的执行记录
! /模型
```

---

# 命令参考

# ChatDSL 关键字参考

## 命令关键字

### 系统与界面控制指令

| 命令别名 | 类别 | 语法说明 | 功能说明描述 |
|---------------|-----------|----------|-------------|
| `/帮助` | 核心 | `/帮助 [指令别名\|查询关键字]` | 调出命令帮助信息界面 |
| `/退出` | 核心 | `/退出` | 结束当前会话并写入历史记录 |
| `/exit` | 核心 | `/exit` | 结束当前会话并写入历史记录 (英文别名) |
| `/回显` | 核心 | `/回显 文本信息` | 打印输出文本信息（支持变量替换） |
| `/加载脚本` | 核心 | `/加载脚本 脚本路径.dsl` | 读取并顺序执行一个 ChatDSL 脚本文件 |
| `/脚本` | 核心 | `/脚本 脚本路径.dsl [x=值 y=值 z=值]` | 带入全局参数运行脚本文件 |
| `/计算` | 核心 | `/计算 <数学表达式>` | 计算并返回数学表达式结果 |
| `/查找文本` | 核心 | `/查找文本 <关键字> [源]` | 在文本或活动缓冲区中搜索子字符串 |
| `/proc` | 核心 | `/proc <名称> [参数]` | 调用执行已定义的过程函数 |
| `/会话` | 核心 | `/会话 <子命令> [参数]` | 会话管理（保存、列表、修剪、压缩等） |
| `/reloadmacros` | 核心 | `/reloadmacros [宏定义文件路径]` | 重新加载并更新所有的宏模板定义 |

### 模型与大模型控制指令

| 命令别名 | 类别 | 语法说明 | 功能说明描述 |
|---------------|-----------|----------|-------------|
| `/模型` | 模型 | `/模型 [模型配置名]` | 切换当前使用的聊天模型或显示当前配置 |
| `/列出模型` | 模型 | `/列出模型` | 显示当前系统中可配置的所有模型别名列表 |
| `/环境变量` | 模型 | `/环境变量 [过滤词]` | 显示已定义的环境变量与 API 密钥 (`set \| grep -i api`) |
| `/系统提示` | 模型 | `/系统提示 [系统规则内容]` | 获取或更新主系统行为指令提示词 (System Prompt) |
| `/温度` | 模型 | `/温度 [数值]` | 设置模型的生成随机温度值参数 (0.0 - 2.0) |
| `/最大Token` | 模型 | `/最大Token [数值]` | 设置模型单词输出的长度上限限制数 |
| `/上下文限制` | 模型 | `/上下文限制 [数值\|off]` | 设置严格的上下文 Token 上限 |
| `/自动截断` | 模型 | `/自动截断 [on\|off\|10-100]` | 超出设定比例时自动截断早期上下文 |
| `/top_p` | 模型 | `/top_p [数值]` | 设置核采样概率分布阈值数 (0.0 - 1.0) |
| `/top_k` | 模型 | `/top_k [数值]` | 设置 Top-K 采样的候选 Token 数 |
| `/频率惩罚` | 模型 | `/频率惩罚 [数值]` | 设置基于频率重复的惩罚系数值 (-2.0 至 2.0) |
| `/存在惩罚` | 模型 | `/存在惩罚 [数值]` | 设置基于存在重复的惩罚系数值 (-2.0 至 2.0) |
| `/seed` | 模型 | `/seed [数值]` | 设置生成文本的随机种子数以实现结果对齐 |
| `/stream` | 模型 | `/stream` | 开启或关闭模型回复内容的打字机流式输出 |
| `/推理模式` | 模型 | `/推理模式 [on\|off]` | 开/关模型推理能力（仅在推理模型下生效） |
| `/推理强度` | 模型 | `/推理强度 [low\|medium\|high\|none]` | 调整思考推理的程度强度级别 (Reasoning Effort) |
| `/显示思考` | 模型 | `/显示思考 [on\|off]` | 开启或隐藏模型推理步骤思考文字块的展示 |
| `/思考样式` | 模型 | `/思考样式 [样式名称]` | 设定推理思考文字块在终端下的呈现排版样式 |

### 文件与缓冲区管理指令

| 命令别名 | 类别 | 语法说明 | 功能说明描述 |
|---------------|-----------|----------|-------------|
| `/文件` | 文件 | `/文件 文件路径` | 读取磁盘中的文本文件到主内存缓冲区 |
| `/显示文件` | 文件 | `/显示文件 [all]` | 打印当前缓冲区中的文本信息 |
| `/清空文件` | 文件 | `/清空文件` | 擦除当前缓冲区中的文本（不影响硬盘文件） |
| `/文件库{1-5}` | 文件 | `/文件库N 路径\|clear\|show [all]` | 读写和管理 1-5 号持久化辅助文件缓冲区 |
| `/图片库{1-5}` | 文件 | `/图片库N 路径\|clear\|show` | 读写和管理 1-5 号图像文件库缓冲区 |
| `/加载图片` | 文件 | `/加载图片 路径 <图片库别名>` | 将本地图片进行 Base64 编码并载入对应图片库 |
| `/笔记模式` | 文件 | `/笔记模式 [on\|off]` | 切换在使用保存命令时是否仅提取 Markdown 代码块 |
| `/仅代码` | 文件 | `/仅代码` | 要求模型后续仅生成干净的源码，无需闲聊前言 |
| `/关闭仅代码` | 文件 | `/关闭仅代码` | 关闭上述“仅代码”格式回复限制 |
| `/多行输入` | 文件 | `/多行输入` | 开启或结束支持换行输入的代码块模式 |
| `/保存` | 文件 | `/保存 文件路径 [all] [nothink\|withthink]` | 将上一次的模型回复内容输出并写入磁盘文件 |
| `/prompt` | 文件 | `/prompt 文件路径` | 将指定文件内容作为下一轮直接发送的提示词 |

### 图像生成控制指令

| 命令别名 | 类别 | 语法说明 | 功能说明描述 |
|---------------|-----------|----------|-------------|
| `/生图` | 图像 | `/生图 图像风格提示词` | 召唤指定的模型生成对应的图像 |
| `/图片尺寸` | 图像 | `/图片尺寸 [宽x高]` | 设置或显示输出图片的宽高分辨率大小 |
| `/图片质量` | 图像 | `/图片质量 [standard\|hd]` | 调整生成图片的精度细节质量级别 |
| `/saveimage` | 图像 | `/saveimage [本地保存路径]` | 导出保存上一次刚刚生成的图片文件 |
| `/图片目录` | 图像 | `/图片目录 [文件夹路径]` | 设置图像生成的默认导出存放目录路径 |
| `/列出图片` | 图像 | `/列出图片` | 按照时间列出在此系统下所生成的图片清单 |
| `/显示图片信息` | 图像 | `/显示图片信息 [日期\|文件名]` | 显示对应图片的详细生成配置参数数据 |

### 本地 Shell 控制指令

| 命令别名 | 类别 | 语法说明 | 功能说明描述 |
|---------------|-----------|----------|-------------|
| `/运行` | Shell | `/运行 系统命令 [参数]` | 执行本地 Shell 指令并在终端打印输出 |
| `/安全运行` | Shell | `/安全运行` | 开启每次在运行外部 Shell 时的用户安全确认询问提示 |
| `/危险运行` | Shell | `/危险运行` | 切换为静默无提示模式，跳过所有 Shell 安全验证询问 |

### 工具调用循环管理指令

| 命令别名 | 类别 | 语法说明 | 功能说明描述 |
|---------------|-----------|----------|-------------|
| `/工具` | 工具 | `/工具 [子命令] [参数]` | 管理工具调用模式的各类状态配置 |
| `/工具 on` | 工具 | `/工具 on` | 在提示词定义中开启对系统工具 Schema 的描述 |
| `/工具 off` | 工具 | `/工具 off` | 对模型隐藏所有工具定义以进入普通文本交流模式 |
| `/工具列表` | 工具 | `/工具列表` | 查看当前已加载的全部外部与内部工具及其开关状态 |
| `/启用工具` | 工具 | `/启用工具 <工具名称\|all>` | 开启特定工具调用使模型在循环中可以调用它 |
| `/禁用工具` | 工具 | `/禁用工具 <工具名称\|all>` | 锁定特定工具使模型无法在交互中调用它 |
| `/自动工具` | 工具 | `/自动工具` | 开启对模型所产生工具调用命令的自动运行并返回结果 |
| `/工具循环` | 工具 | `/工具循环 [次数限制] [force]` | 自主调用并运行多轮工具执行循环知道任务终结 |
| `/最大工具轮次` | 工具 | `/最大工具轮次 [轮次上限]` | 查询或更新系统默认的最大工具流转次数 |
| `/工具 速率限制` | 工具 | `/工具 速率限制 [秒数]` | 设置智能体工具调用轮次间的速率延迟暂停（秒） |
| `/工具提示语` | 工具 | `/工具提示语` | 查看和修改用于约束智能体行为的背景约束指示 |

### 诊断与追踪调试指令

| 命令别名 | 类别 | 语法说明 | 功能说明描述 |
|---------------|-----------|----------|-------------|
| `/追踪` | 调试 | `/追踪 <追踪子项> [on\|off]` | 开/关不同部分的运行时数据统计输出 |
| `/追踪 rawpayload` | 调试 | `/追踪 rawpayload [on\|off]` | 输出每次网络请求发送给 API 的 JSON 净载荷 |
| `/追踪 tps` | 调试 | `/追踪 tps [on\|off]` | 统计并输出每次推理生成的 TPS 信息 |
| `/追踪 tpsperf` | 调试 | `/追踪 tpsperf [on\|off]` | 展示高精度的 Tokens 生成速度耗时折线细节 |
| `/追踪 imagedbg` | 调试 | `/追踪 imagedbg [on\|off]` | 跟踪并记录第三方图片生成的调试详情信息 |
| `/追踪 rerank` | 调试 | `/追踪 rerank [on\|off]` | 跟踪在检索重排计算时的指标和数据变化 |
| `/追踪 agentic_loop` | 调试 | `/追踪 agentic_loop [on\|off]` | 在屏幕上详细打印智能体交互周期的具体步骤 |
| `/调试` | 调试 | `/调试 <payload\|response\|vmem>` | 控制高级别调试模式的拦截器级别配置 |
| `/记录日志` | 调试 | `/记录日志 [start\|end]` | 将本会话的全部日志实时输入到本地磁盘日志文件中 |
| `/内存` | 调试 | `/内存 [detail\|debug]` | 查看缓存、运行变量及底层解释器内存占用详情 |
| `/dump` | 调试 | `/dump [变量名\|all]` | 查看和转储当前解释器内已保存的变量字面值 |

### 向量数据库指令

| 命令别名 | 类别 | 语法说明 | 功能说明描述 |
|---------------|-----------|----------|-------------|
| `/设置数据库` | 数据库 | `/设置数据库 <数据库名\|Null>` | 创建/连接/关闭目标 TinyDB 向量数据库 |
| `/数据库列表` | 数据库 | `/数据库列表` | 显示系统检测到的本地全部向量库清单 |
| `/搜索数据库` | 数据库 | `/搜索数据库 <搜索文本>` | 对关联数据库执行向量搜索 |
| `/数据库日志` | 数据库 | `/数据库日志` | 将上一次的完整聊天问答作为一条索引存入数据库中 |
| `/打印数据库` | 数据库 | `/打印数据库 [输出文件名]` | 将向量数据库的全部记录明文转储打印出来 |
| `/文档源` | 数据库 | `/文档源 <源类型>=<标识值>` | 为后面的重排指定分析文档范围源 |
| `/重排` | 数据库 | `/重排 "<检索要求词>"` | 执行针对指定源的多文档重排打分分析 |

### 解释器变量控制指令

| 命令别名 | 类别 | 语法说明 | 功能说明描述 |
|---------------|-----------|----------|-------------|
| `/设置var` | 变量 | `/设置var <变量名> <内容值>` | 定义或更新一个解释器生命周期内的局部变量 |
| `/加载var` | 变量 | `/加载var <变量名> [ALL\|条目ID\|范围]` | 将向量数据库检索记录载入并赋给脚本变量 |
| `/保存var` | 变量 | `/保存var <变量名> <文件路径>` | 将对应变量所含的内容输出并写入磁盘文件 |

### 配置文件相关指令

| 命令别名 | 类别 | 语法说明 | 功能说明描述 |
|---------------|-----------|----------|-------------|
| `/配置` | 配置 | `/配置 <子命令> [参数]` | 会话配置文件的保存、恢复与 TUI 直接编辑管理 |

### 终端历史查找指令

| 关键字 | 类别 | 语法说明 | 功能说明描述 |
|---------|----------|--------|-------------|
| `!` | 历史 | `! <搜索关键字>` | 在当前命令执行历史记录中过滤出包含该关键字的命令行 |

## 解释器保留关键字

| 英文原词 | 中文翻译 | 语法结构格式 | 用途说明 |
|--------|---------|----------|-------------|
| `set` | `设置` | `设置 变量名 = 变量值` | 进行变量定义与赋值运算 |
| `local` | `局部` | `局部 变量名 = 变量值` | 过程作用域局部变量 |
| `if` | `如果` | `如果 逻辑条件 则 对应指令` | 执行分支条件逻辑运算判断 |
| `then` | `则` | (条件判断的连接子关键字) | 条件逻辑执行体引导符 |
| `wait` | `wait` | `wait 秒数` | 阻塞并挂起脚本指定的秒数时间 |
| `defproc` | `定义过程` | `defproc 过程名(形参列表)` | 声明并定义可复用的过程块 |
| `endproc` | `结束过程` | `endproc` | 结束过程块定义 |
| `foreach` | `循环` | `循环 变量名 in 数组/范围/行` | 多行块循环控制 |
| `endfor` | `结束循环` | `endfor` | 结束循环块 |
| `break` | `中断` | `中断` | 提前跳出循环 |
| `range` | `范围` | `range(1:10)` | 数值序列生成器 |
| `lines` | `行` | `lines(文本)` | 文本分行生成器 |
| `#` | `#` | `# 注释描述信息` | 脚本代码的单行注释引导符 |
| `def` | `def` | `def 宏名称(形参列表) = "模板内容"` | 声明并定义一个提示词宏模板 |
| `%` | `%` | `%宏名称(实参值列表)` | 扩展并运行之前定义的宏模板内容 |

## 解释器变量语法规范

| 语法标识 | 说明 |
|----------|-------------|
| `${变量名}` | 变量引用替换符号（在执行时会将内容注入所在行） |
| `设置 变量名 = "变量值"` | 将双引号包围的文本内容赋给该变量 |
| `"带空格的内容值"` | 使用双引号包围带有空格或特殊字符的字符串 |
| `'带空格的内容值'` | 使用单引号包围带有空格或特殊字符的字符串 |
| `{filebankN}` | 在发送聊天提示词时将文件库（1-5号）的全部文本内容注入该位置 |
| `{imagebankN}` | 在发送多模态提示词时将图片库（1-5号）的数据作为多模态载荷注入 |

## 条件运算符

| 运算符 | 描述 | 使用示例 |
|----------|-------------|---------|
| `==` | 等于关系判断 | `if ${x} == "yes" then` |
| `!=` | 不等于关系判断 | `if ${x} != "" then` |
| `>` | 大于关系判断 | `如果 "${AGE}" > 18 则` |
| `<` | 小于关系判断 | `如果 "${VAL}" < 10 则` |
| `>=` | 大于等于关系判断 | `如果 "${AGE}" >= 18 则` |
| `<=` | 小于等于关系判断 | `如果 "${VAL}" <= 5 则` |
| `not` | 逻辑非操作 | `if not ${debug} then` |

## 控制流语法

| 流程控制 | 语法格式 | 说明 |
|---------|----------|-------------|
| `if` | `if 条件表达式 then 命令/指令` | 根据条件表达式成立与否执行后面的命令 |
| `wait` | `wait 秒数` | 挂起当前脚本运行，并在挂起期间等待指定秒数 |
| `设置` | `设置 变量名 = 表达式内容` | 声明局部运行变量并为其赋值 |
| `#` | `# 文本注释描述内容` | 忽略本行文本（注释行） |

## 多行块输入模式语法

| 起始/结束标识 | 语法 | 描述 |
|---------------|----------|-------------|
| `/多行输入` | `/多行输入` | 开启多行换行录入状态 |
| `;;` | `;;` | 结束多行换行录入状态 |

## 宏语法描述

| 关键字类型 | 格式定义 | 描述 |
|----------|----------|-------------|
| 宏声明定义 | `def 宏名(参数A, 参数B) = "模板文本内容"` | 在脚本中声明带有参数的宏定义 |
| 无参宏声明 | `def 宏名() = "模板文本内容"` | 在脚本中声明无参数的宏定义 |
| 宏引用调用 | `%宏名(实参A, 实参B)` | 调用并展开对应的宏模板内容 |
| 宏模板变量 | `{形参名}` | 用来标识在宏文本中被参数值替换的位置 |

### 提示词宏定义使用示例

```dsl
# 无参数的简单替换宏
def regen() = "Regenerate all source code"
def build() = "Build the project with optimized settings"

# 包含参数的多行宏定义
def expert_prompt(topic) = "Act as an expert in {topic}. Provide detailed, accurate, and insightful information about {topic}."

def language_comparison(lang1, lang2) = "Compare {lang1} and {lang2} programming languages. Discuss their similarities, differences, syntax variations, performance characteristics, and typical use cases."
```

## 预定义系统报错信息

| 错误类别 | 英文报错内容 | 西班牙文 | 法文 | 中文报错内容 | 意大利文 |
|-------|---------|---------|--------|---------|---------|
| 找不到硬盘文件 | "Error: File not found" | "Error: Archivo no encontrado" | "Erreur: Fichier introuvable" | "错误: 文件没有找到" | "Errore: File non trovato" |
| 未定义的宏模板 | "ERROR: Macro 'X' not defined" | "ERROR: Macro 'X' no definido" | "ERREUR: Macro 'X' non définie" | "错误: 宏 'X' 未定义" | "ERRORE: Macro 'X' non definita" |
| 宏形参与实参数量不匹配 | "ERROR: Macro 'X' expects N arguments, got M" | "ERROR: Macro 'X' espera N argumentos, obtuvo M" | "ERREUR: Macro 'X' attend N arguments, reçu M" | "错误: 宏 'X' 需要 N 个参数，得到 M 个" | "ERRORE: Macro 'X' aspetta N argomenti, ottenuti M" |

---

# 最佳实践

## 编写脚本的黄金法则

### 1. 变量命名规范
- 使用 **snake_case**（蛇形命名法）定义具有描述性的变量名，例如：`article_num`、`model_name`
- 单字母变量（`x`、`y`、`z`）专为脚本外部带入参数保留
- 常量建议使用全大写字母表示

### 2. 代码注释规范
```dsl
# 整行式单行注释说明
设置 var = "value"  # 行内尾随式局部注释

# 大模块分类分割线样式
# ============================================
# 翻译工作流代码块
# ============================================
```

### 3. 标准的脚本架构顺序
```dsl
# 脚本名称与使用描述
# 脚本：自动文档处理脚本
# 使用方法：/脚本 process.chatdsl [参数详情]

# 1. 外部导入参数安全处理判断
if ${x} != "" then 设置 param1 = ${x}
if ${param1} == "" then 设置 param1 = "default"

# 2. 模型与运行参数的初始化配置
设置 base_dir = "output"
/模型 gemini_flash

# 3. 核心业务处理流程代码
/文件 input.txt
process this...
/保存 output.txt

# 4. 内存及状态的销毁还原
/清空文件
/回显 "Done"
```

### 4. 核心功能组合模板

#### 设置参数的默认回退值
```dsl
if ${x} != "" then 设置 var = ${x}
if ${var} == "" then 设置 var = "default"
```

#### 条件判定模型分流逻辑
```dsl
if ${fast} then /模型 gemini_flash
if not ${fast} then /模型 openai_gpt4
```

## 异常问题排查指南

### 常见报错现象与修复方案

| 问题现象 | 推荐的修复方案 |
|----------|----------|
| 脚本变量没有被求值替换 | 检查变量是否严格使用 `${名称}` 格式（注意大括号内外均不能有空格） |
| 系统提示找不到文件 | 使用 `/回显` 指令打印路径变量，观察拼接后的路径是否符合磁盘结构 |
| 多行块输入模式无法结束 | 检查是否将 `;;` 独立放在了一行，然后再在下一行打上 `/多行输入` |
| 设置的变量值中包含空格报错 | 为带空格的值套上双引号，例如：`设置 var = "value with spaces"` |
| 变量值中包含反斜杠导致转义错误 | ChatDSL 变量中不支持反斜杠，请使用斜杠 `/` 表示路径层级 |
| 控制台报错“命令未识别” | 确认命令前是否打上了 `/` 符号，并仔细检查是否存在拼写错误 |

## 运行性能调优

### 接口防限流 (Rate Limiting) 处理
```dsl
# 在调用不同大模型进行高强度计算之间合理挂起脚本
/模型 gemini_flash
prompt 1
/保存 response1.txt
wait 2  # 阻塞脚本挂起等待 2 秒钟，腾出 API 频次

/模型 openai_gpt4
prompt 2
/保存 response2.txt
```

### 缓冲区状态清理
```dsl
# 在执行两轮完全不相关的对话处理之前清理主缓冲区
/清空文件

# 防止多余的残留上下文污染新一轮的提示词理解
/文件 new_context.txt
```

### 节约模型 Token 开销
```dsl
# 在执行编程任务时，开启“仅代码”输出控制
/仅代码
Write Python code to solve this problem.
/关闭仅代码
```

---

# 快捷参考手册

## 指令功能归类

### 系统相关
- `/帮助` - 调出命令帮助
- `/回显` - 打印控制台调试文本
- `/退出` - 保存历史并断开会话
- `/脚本` - 带入参数执行脚本
- `/加载脚本` - 静默运行一个脚本文件

### 模型控制
- `/模型 [别名]` - 切换当前的聊天模型
- `/系统提示 [系统指令]` - 更新系统背景人设
- `/温度 [数值]` - 设置回复温度系数
- `/最大Token [数值]` - 设置输出的最大长度限制
- `/推理模式 [on|off]` - 开启/关闭推理模式
- `/推理强度 [强度等级]` - 设置思考的深度级别

### 文件操作
- `/文件 文件路径` - 加载文本到缓冲区中
- `/文件库1-5` - 辅助持久化文件缓存区管理
- `/保存 文件路径 [all] [nothink|withthink]` - 保存上一次模型回复到磁盘文件
- `/多行输入` - 开启复杂的换行提示词录入
- `/prompt 文件路径` - 发送外部文件的提示词内容

### 图像生图
- `/生图 绘图描述词` - 运行图像生成模型
- `/图片尺寸 宽x高` - 设置要输出的分辨率大小
- `/saveimage [保存文件路径]` - 保存刚才生成的图片到本地
- `/图片库1-5` - 辅助持久化图像缓存区管理

### 向量检索
- `/设置数据库 向量库名称` - 打开指定的本地向量数据库
- `/搜索数据库 "查询文本"` - 进行语义向量数据库检索
- `/数据库日志` - 备份保存刚才的问答到数据库
- `/重排` - 对检索到的文档执行二次相关性重排打分

### 工具调用
- `/工具 on` - 加载工具定义到提示词上下文
- `/工具循环 [轮次上限] [force]` - 启动智能体多步执行循环
- `/工具列表` - 查看已加载的可用工具列表
- `/启用工具 all` - 启用全部系统工具供模型调用

### 系统诊断
- `/追踪 <子项> [on|off]` - 跟踪和观察具体的系统参数运行细节
- `/内存 [detail|debug]` - 显示底层的内存以及缓存状态信息
- `/dump [变量名|all]` - 导出打印出当前的脚本运行变量值

### 会话配置
- `/配置 list` - 列出本地可用的所有会话配置
- `/配置 use 配置名称` - 加载已有的配置
- `/配置 clone 新别名` - 复制当前状态到新配置下

## 基础语法单元

### 变量管理
```dsl
设置 变量名 = "变量内容值"
${变量名}
```

### 局部变量（过程）
```dsl
局部 变量名 = "变量内容值"
```

### 分支条件判定
```dsl
if ${x} == "yes" then /命令
if not ${debug} then /回显 "quiet"
```

### 循环遍历
```dsl
循环 文件 in ${文件列表}
    /回显 正在处理 ${文件}...
    # 处理逻辑
结束循环
```

### 跳出循环
```dsl
循环 数字 in range(1:10)
    if ${数字} == "5" then 跳出
    /回显 ${数字}
结束循环
```

### 生成器
```dsl
# 数字范围（包含端点）
循环 i in range(1:5)
    /回显 ${i}
结束循环

# 带步长的范围
循环 i in range(1:10:2)
    /回显 ${i}
结束循环

# 文本行
循环 行 in ${文本}
    /回显 ${行}
结束循环
```

### 挂起脚本
```dsl
wait 2
```

### 换行录入
```dsl
/多行输入
Your prompt here
;;
/多行输入
```

### 宏模板
```dsl
# 声明定义
def expert_prompt(topic) = "Act as an expert in {topic}."

# 展开运行
%expert_prompt(Python)
```

---

# 资源链接

## 相关文档列表

- **ChatDSL 语言指南** (`chatdsl_language.md`) - 命令到翻译对照以及详尽变量语法的完全参考
- **ChatDSL 技能设计手册** (`chatdsl_skill.md`) - 面向中高级脚本的开发设计模式参考
- **ChatDSL 宏解析器实现说明书** (`chatdsl_macro_implementation.md`) - PEG 语法解析与底层宏替换报告

## 相关配置文件说明

- `~/.config/chatybot/chat_config.toml` - 存放用户自定义的大模型接入密钥及参数配置
- `~/.config/chatybot/profiles/` - 存放用户保存的各个应用会话配置信息目录
- `src/chatybot/chat_config.toml` - 存放系统打包自带的模型默认连接配置
- `src/chatybot/tools_config.toml` - 本地及全局工具的启用权限及超时时间配置
- `src/chatybot/macro.chatdsl` - 开箱即用的系统默认宏模板库文件
- `src/chatybot/translations.json` - 存放 5 国命令对照关系的本地化翻译字典库

## 项目辅助文件

- `chatdsl_bnf.txt` - 解释器采用的 BNF 规范格式语法定义文件
- `script_param_implementation.md` - 参数安全边界与内存生命周期说明书
- `dsl_test/` - 演示 ChatDSL 全功能的完整测试脚本文件夹

---

# 安装与运行

## 快速上手流程

1. **安装 Chatybot 程序**
   ```bash
   pip install chatybot
   ```

2. **配置您的 API 密钥信息**
   ```bash
   # 创建用户配置文件夹并将默认文件拷贝过去
   mkdir -p ~/.config/chatybot
   cp src/chatybot/chat_config.toml ~/.config/chatybot/
   
   # 启动终端用户配置界面进行可视化编辑保存
   chatybot-config
   ```

3. **进入 Chatybot 会话终端**
   ```bash
   chatybot
   ```

4. **执行一个 ChatDSL 脚本**
   ```bash
   chat --> /脚本 my_script.chatdsl x=value1 y=value2
   ```

## 最常用聊天命令

- `/帮助` - 调出包含详细参数说明的系统指令列表
- `/模型` - 方便地切换不同的后台服务大模型
- `/文件 文本路径` - 读取磁盘中的文本文件到内存上下文
- `/回显 "文本内容"` - 在控制台上输出调试行
- `/保存 本地路径` - 将上一轮的问答记录以文本格式导出到本地文件

## 官方示例脚本推荐

在系统的 `dsl_test/` 文件夹下提供了很多可以直接运行分析的脚本：
- `translate.chatdsl` - 用于多语言交互翻译的脚本
- `compare.chatdsl` - 对比两个文档内容差异并生成分析的脚本
- `evaluate.chatdsl` - 让多个模型评估同一个提示词的分析脚本
- `batch.chatdsl` - 连续读取目录处理文件的示例脚本

---

*(ChatDSL 综合指南终)*

---

## 历史版本记录

| 版本号 | 发布日期 | 修改变更说明 |
|---------|-------|---------|
| 1.0 | 2025-07-23 | 基于 v0.6.4 底层源码审查并修正的最初发行版 |

---

## 作者的话

本手册是根据 Chatybot v0.6.4 实装底层源码进行严谨核对后的最终校准版。所有的命令别名拼写、系统配置 TOML 字段格式以及脚本上下文变量引用规则均已经在真实开发环境中得到了验证。
