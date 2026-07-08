# Prompt Eval CLI

一个用于对比多个提示词版本效果的纯命令行工具，不包含 UI。

它主要解决这几个问题：

- 同一批样本下，多个 prompt 谁表现更好
- 新 prompt 修复了哪些 case
- 新 prompt 又退化了哪些 case
- 每条样本的最终 prompt、模型输出、解析结果、评估结果是什么

## 快速开始

### 方式 A：Windows 一键启动

如果你是 Windows 用户，推荐直接使用根目录的一键启动脚本：

```bat
start_prompt_eval_env.cmd
```

这个脚本会在当前 PowerShell 窗口内自动完成以下步骤：

- 检测 Python 3
- 可选配置 `pip` 国内镜像
- 创建或复用 `.venv`
- 安装 `requirements.txt`
- 检查并初始化 `.env`
- 激活 `.venv`
- 直接运行 `python -m prompt_eval_cli`

运行完成后，PowerShell 窗口不会自动关闭，方便继续查看日志或手动执行其他命令。

如果你希望只配环境，不直接启动 CLI，可以加参数：

```bat
start_prompt_eval_env.cmd -SkipCliLaunch
```

常用参数：

- `-SkipMirrorConfig`: 跳过 `pip` 镜像配置
- `-SkipInstall`: 跳过依赖安装
- `-SkipCliLaunch`: 只准备环境，不自动运行 `python -m prompt_eval_cli`

### 方式 B：手动启动

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 配置 `config/prompt_eval.yaml`

```yaml
prompt_files:
  - prompts/优化版本_0707_量表.txt

datasets:
  - all

dataset_root: dataset/labeled_data_v4
output_root: outputs

sample_size: 0
seed: 42
max_workers: 10
timeout: 60
temperature: 0.1
request_delay: 0

api_url: ${PROMPT_EVAL_API_URL}
api_key: ${PROMPT_EVAL_API_KEY}
model: Qwen3-30B-A3B-Instruct-2507-prd
```

3. 创建 `.env`

```env
PROMPT_EVAL_API_URL=https://your-openai-compatible-endpoint/v1/chat/completions
PROMPT_EVAL_API_KEY=replace-with-your-token
```

4. 直接启动交互菜单

```bash
python -m prompt_eval_cli
```

启动后会看到编号菜单，直接输入数字选择功能，不需要记忆完整子命令。

交互模式下，进入子任务后可以输入 `/back` 直接返回主菜单。

如果你使用 PowerShell，也可以直接执行脚本本体：

```powershell
.\start_prompt_eval_env.ps1
```

如果是通过资源管理器双击启动，优先使用 `start_prompt_eval_env.cmd`，兼容性更好。

## 目录约定

- `config/prompt_eval.yaml`: 主配置文件
- `prompts/`: 存放 prompt 模板
- `dataset/`: 存放评估数据集
- `outputs/`: 存放每次实验的输出结果

## 配置说明

最常用的配置项如下：

- `prompt_files`: 本次实验要评估的 prompt 文件列表
- `datasets`: 要跑的数据集，可选 `green`、`yellow`、`red`、`all`
- `dataset_root`: 数据集根目录
- `output_root`: 实验输出目录
- `sample_size`: 抽样数量，`0` 表示全量
- `max_workers`: 并发请求数
- `timeout`: 单次请求超时秒数
- `temperature`: 模型温度
- `request_delay`: 每次请求前的延迟秒数
- `api_url`: 模型接口地址，建议从 `.env` 注入
- `api_key`: 模型密钥，建议从 `.env` 注入
- `model`: 模型名，当前写在 YAML 中

推荐做法：

- 把固定配置放在 `config/prompt_eval.yaml`
- 把敏感信息放在 `.env`
- 临时实验改动优先通过命令行覆盖

## Prompt 模板怎么写

推荐一个 prompt 一个文件，支持 `SYSTEM` 和 `USER` 两段：

```text
===SYSTEM===
你是一个技能复用判断助手。

===USER===
请判断当前问句是否可以复用历史技能。

用户本轮问句：{{thisQuery}}
历史问句：{{lastQuery}}
历史技能：{{lastSkill}}
```

支持的变量来源：

- 样本原始字段，如 `question`、`history_question`、`history_skill`
- 兼容变量，如 `{{lastQuery}}`、`{{thisQuery}}`、`{{lastSkill}}`
- 技能增强变量，如 `{{lastSkillDescription}}`、`{{lastSkillSpecification}}`

注意事项：

- 如果模板变量缺失，当前记录会标记为失败
- 如果不写 `===SYSTEM===`，工具也可以运行
- 一个实验里可以同时配置多个 prompt 文件进行对比

## 常用命令

如果你不想记命令，优先使用交互模式：

```bash
python -m prompt_eval_cli
```

下面这些命令更适合熟悉工具后直接调用，或者用于脚本自动化。

### 查看数据集

```bash
python -m prompt_eval_cli datasets list
```

JSON 输出：

```bash
python -m prompt_eval_cli datasets list --json
```

### 查看 prompt 列表

```bash
python -m prompt_eval_cli prompts list
```

指定目录：

```bash
python -m prompt_eval_cli prompts list --prompt-dir prompts
```

### 启动实验

按 YAML 配置直接运行：

```bash
python -m prompt_eval_cli run
```

临时覆盖 prompt 和数据集：

```bash
python -m prompt_eval_cli run --prompt prompts/严格版本_0624_baseline.txt prompts/优化版本_0707_量表.txt --dataset green yellow
```

只抽样一部分数据：

```bash
python -m prompt_eval_cli run --sample-size 20 --seed 42
```

临时改并发和超时：

```bash
python -m prompt_eval_cli run --max-workers 5 --timeout 120
```

### 查看实验列表

```bash
python -m prompt_eval_cli experiments list
```

JSON 输出：

```bash
python -m prompt_eval_cli experiments list --json
```

### 查看单个实验详情

```bash
python -m prompt_eval_cli experiments show run_20260707_120000
```

### 查看同一实验内两个 prompt 的差异 case

查看 improved case：

```bash
python -m prompt_eval_cli experiments compare run_20260707_170948 --baseline 优化版本_0706 --target 优化版本_0707_CoT --case-type improved --limit 20
```

查看 regressed case：

```bash
python -m prompt_eval_cli experiments compare run_20260707_170948 --baseline 优化版本_0706 --target 优化版本_0707_CoT --case-type regressed --limit 20
```

按数据集筛选：

```bash
python -m prompt_eval_cli experiments compare run_20260707_170948 --baseline 优化版本_0706 --target 优化版本_0707_CoT --dataset green --case-type all
```

输出 JSON：

```bash
python -m prompt_eval_cli experiments compare run_20260707_170948 --baseline 优化版本_0706 --target 优化版本_0707_CoT --json
```

## 一次完整使用流程

### 场景 1：比较两个 prompt 版本

1. 把两个 prompt 文件放到 `prompts/`
2. 在 YAML 中配置 `prompt_files`
3. 运行：

```bash
python -m prompt_eval_cli run
```

4. 查看实验列表，拿到 `run_id`

```bash
python -m prompt_eval_cli experiments list
```

5. 查看总体结果

```bash
python -m prompt_eval_cli experiments show <run_id>
```

6. 查看 improved / regressed case

```bash
python -m prompt_eval_cli experiments compare <run_id> --baseline 基线prompt名 --target 新prompt名 --case-type improved
```

### 场景 2：先小样本试跑，再全量运行

先抽样：

```bash
python -m prompt_eval_cli run --sample-size 20
```

确认结果正常后，再跑全量：

```bash
python -m prompt_eval_cli run --sample-size 0
```

### 场景 3：只看某个数据集上的效果

```bash
python -m prompt_eval_cli run --dataset green
```

或者对已有实验只筛 `green`：

```bash
python -m prompt_eval_cli experiments compare <run_id> --baseline 基线prompt名 --target 新prompt名 --dataset green
```

## 输出结果怎么看

每次运行会在 `outputs/run_时间戳/` 下生成：

- `experiment.json`: 实验元信息和状态
- `run_config.json`: 本次实验配置快照
- `records.jsonl`: 单条执行明细，适合程序处理
- `records.csv`: 单条执行明细，适合人工查看
- `summary.json` / `summary.csv`: 汇总指标
- `comparison.json` / `comparison.csv`: 同一样本在多个 prompt 下的横向对比

你最常看的通常是这三个文件：

- `summary.csv`: 看总体指标
- `comparison.csv`: 看 improved / regressed / both_wrong
- `records.csv`: 看某条样本的完整执行细节

关键字段说明：

- `final_prompt`: 最终发送给模型的 prompt
- `raw_output`: 模型原始输出
- `prediction`: 解析后的预测结果
- `parse_status`: 解析状态
- `is_correct`: 是否与 ground truth 一致
- `pair_case_type`: 双 prompt 对比时的 case 类型

## 指标口径

- `parse_rate = parsed_total / total`
- `accuracy = correct_total / total`
- `valid_accuracy = correct_total / parsed_total`

双 prompt 对比时，额外会给出：

- `both_correct`
- `both_wrong`
- `improved`
- `regressed`

## 常见问题

### 1. 为什么运行时报缺少配置

优先检查：

- `config/prompt_eval.yaml` 是否填写完整
- `.env` 是否存在
- `PROMPT_EVAL_API_URL` 和 `PROMPT_EVAL_API_KEY` 是否有效

如果你使用的是一键启动脚本：

- 脚本会在 `.env` 不存在时，自动根据 `.env.example` 创建
- 但不会自动帮你填写真实的接口地址和密钥
- 所以第一次启动后，仍然需要确认 `.env` 里的 `PROMPT_EVAL_API_URL` 和 `PROMPT_EVAL_API_KEY`

### 2. 为什么 prompt 运行失败

常见原因：

- 模板里用了不存在的变量
- 接口超时
- 接口鉴权失败
- 模型输出为空或不符合预期格式

建议先用小样本试跑：

```bash
python -m prompt_eval_cli run --sample-size 5
```

### 3. 为什么 compare 看不到结果

优先检查：

- `run_id` 是否正确
- `baseline` 和 `target` 是否与 prompt 文件名一致
- 该实验是否真的同时跑了这两个 prompt

### 4. 推荐的使用顺序是什么

推荐顺序：

1. `datasets list`
2. `prompts list`
3. `run --sample-size 20`
4. `experiments list`
5. `experiments show <run_id>`
6. `experiments compare <run_id> ...`

### 5. Windows 下一键启动脚本怎么用

最推荐的方式：

```bat
start_prompt_eval_env.cmd
```

如果你已经在 PowerShell 里，也可以执行：

```powershell
.\start_prompt_eval_env.ps1
```

启动脚本的特点：

- 在当前窗口内完成环境准备
- 不会再额外弹出新窗口
- 会直接运行 `python -m prompt_eval_cli`
- CLI 退出后，当前窗口仍然保留

常用参数示例：

```powershell
.\start_prompt_eval_env.ps1 -SkipMirrorConfig
.\start_prompt_eval_env.ps1 -SkipInstall
.\start_prompt_eval_env.ps1 -SkipCliLaunch
```

## 当前能力边界

- 这是单机、文件系统驱动的 CLI 工具
- 当前没有 UI，也没有任务调度器
- 当前输出解析主要围绕二分类 `是/否`
- 当前更适合 prompt 评估和版本对比，不是通用实验平台
