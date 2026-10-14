# 面向患者记录可靠医学计算的工具增强大语言模型

[English](README.md)

> **双盲审稿提醒：**本代码正在双盲审稿期间整理。审稿结果公布前，请保持仓库为私有状态，不要从可识别作者身份的个人账号公开或镜像。作者与正式引用信息将在审稿期结束后补充。

本仓库实现一个工具增强的大语言模型框架，将临床文本理解与确定性医学计算解耦：系统检索并结构化计算器规则，生成和验证可复用 Python 工具，按计算器 schema 从患者记录抽取参数，最后调用冻结工具完成可审计计算。

![论文图一：方法框架](assets/figure1.png)

上图直接采用投稿论文第 3 页的图一，以 Cockcroft-Gault 肌酐清除率计算器说明完整流程。
图片未重绘、裁剪或缩放，来源及校验值见 [figure1.source.json](assets/figure1.source.json)。

## 核心内容

- 规则驱动的计算器工具生成，以及基于执行反馈的验证与修复。
- 计算器专属 JSON schema 和每个计算器 3 个同类训练示例。
- 投稿实验使用的 55 个冻结 GPT-5.5 计算器工具及校验清单。
- 聚合结果、无密钥配置模板、数据下载脚本和 CPU 回归测试。
- 仓库不包含 API 密钥、模型权重、投稿论文、完整 LLM 轨迹或完整基准数据。

## 投稿结果口径

投稿论文在 MedCalc-Bench Verified v1.0.7 的 1,100 个测试病例上报告：

| 方法 | 最终准确率 |
|---|---:|
| Qwen3-8B one-shot prompting | 62.73% |
| Qwen3-8B SFT-only | 69.46% |
| 工具增强框架 + Qwen3-8B-SFT 抽取器 | **86.73%** |

主运行正确 954/1,100 例，参数匹配率为 5,241/5,377（97.47%）；GPT-5.5 检索与修复工具的工具级准确率为 94.91%。

本仓库保留投稿时的答案解析与评分口径，已撤回投稿后对 calculator 69 的解析修改，论文原始结果保持不变。项目的前置答案解析并非官方评分函数的原样复制；两者的区别见 [评测口径说明](results/KNOWN_ISSUES.md)。

发布的计算工具与下载后的基准可复现工具级 94.91%。完整复现 86.73% 还需要投稿时的
SFT 权重和训练、运行记录，这些材料尚未发布。对照导师论文代码仓库的审计结果见
[仓库审计报告](docs/REPOSITORY_AUDIT_zh.md)。

## 快速开始

完整实验面向 Linux、Python 3.10、CUDA 和 NVIDIA GPU；仓库检查及计算器执行可在 CPU 上完成。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
python scripts/download_data.py
cp configs/runtime.env.example runtime.env
```

下载脚本会校验 MedCalc-Bench Verified v1.0.7 的 SHA-256，并从不含病例正文的模板重建本地少样本库；完整病例正文不会进入 Git。

只做无网络、无 GPU 检查：

```bash
python scripts/validate_artifacts.py
python -m unittest discover -s tests -v
```

无需 GPU、API 密钥或基准下载，即可运行一个计算器示例：

```bash
python scripts/run_calculator.py --input examples/mean_arterial_pressure/input.json
```

示例输入为收缩压 120 mmHg、舒张压 80 mmHg，输出平均动脉压
93.33333333333333 mmHg。[examples/README.md](examples/README.md) 提供输入、
预期输出和使用范围。

按模板配置 central 与 extraction 模型后运行一个病例：

```bash
LIMIT=1 bash scripts/run_pipeline.sh
```

完整环境、模型和复现限制见 [docs/REPRODUCTION.md](docs/REPRODUCTION.md)。数据许可与第三方归属见 [NOTICE.md](NOTICE.md)。

## 引用与许可

双盲审稿期间暂不加入作者和 BibTeX；审稿结束后将补充正式引用及 `CITATION.cff`。

大部分代码采用 [Apache License 2.0](LICENSE)；`evaluation.py` 的基准评分语义及数据集衍生文件继续受 CC BY-SA 4.0 约束，具体边界见 [NOTICE.md](NOTICE.md)。本项目仅用于科研，不是医疗器械，不得用于诊断、治疗或真实患者决策；运行任何生成代码前都应人工审查并在沙箱中执行。
