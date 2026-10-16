# 面向患者记录可靠医学计算的工具增强大语言模型

[English](README.md)

作者顺序：Yang Zhong、Ling Luo、Xuanlyu Zhu、Yanhua Wang、Yuanyuan Sun、Jian Wang、Hongfei Lin。

本公开科研仓库以最终 LaTeX 源码为论文依据；本次不修改论文。当前引用不表示论文已录用、已取得 DOI 或已在 arXiv 发布。

论文在 MedCalc-Bench Verified v1.0.7 上报告的最终答案准确率为 **86.73%**。
本仓库用于下载和复现，不发布旧运行的逐例抽取记录或大模型完整回答。
评测实现的限制和必要说明集中在[已知问题](results/KNOWN_ISSUES.md)。

本仓库实现一个工具增强的大语言模型框架，将临床文本理解与确定性医学计算解耦：系统检索并结构化计算器规则，生成和验证可复用 Python 工具，按计算器 schema 从患者记录抽取参数，最后调用冻结工具完成可审计计算。

![论文图一：方法框架](assets/figure1.png)

上图直接复制最终 LaTeX 工程的 `figures/image1.png`，以 Cockcroft-Gault 肌酐清除率计算器说明完整流程。
图片未重绘、裁剪或缩放，文件与最终源码原图逐字节一致，来源及校验值见 [figure1.source.json](assets/figure1.source.json)。

![论文图二：三个主要阶段的提示词](assets/figure2.png)

图二来自最终 LaTeX 源码的实际排版。代码已按图二统一三阶段的提示词约束，
共享模板见 [prompts.py](src/toolmed_agent/prompts.py)，[对应关系](docs/PROMPTS.md)说明实际调用入口。
图中是概括，运行时会填入规则证据、schema、三个同类示例和当前病例，不包含历史模型回答。

## 核心内容

- 规则驱动的计算器工具生成，以及基于执行反馈的验证与修复。
- 计算器专属 JSON schema 和每个计算器 3 个同类训练示例。
- 投稿实验使用的 55 个冻结 GPT-5.5 计算器工具及校验清单。
- 聚合结果、无密钥配置模板、数据下载脚本和 CPU 回归测试。
- 仓库不包含 API 密钥、模型权重、投稿论文、完整 LLM 轨迹或完整基准数据。

完整复现还需要论文实验所用的最终 SFT adapter；当前未随仓库提供。
冻结计算器可独立测试，具体环境、数据和运行命令见[复现指南](docs/REPRODUCTION.md)。

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

已拥有完整逐例原始抽取时，可不调用模型而重新统计 PMR：

```bash
python scripts/rescore_extractions.py --predictions output/private_run.steps.jsonl --output output/parameter_audit.json
```

需包含全部 1,100 条原始抽取，并使用固定版本测试集；只有旧匹配计数不能重算。
最终答案的旧判定会原样保留，重新计算参数匹配、类别汇总及错误分组。

## 引用与许可

作者采用最终源码中的七人顺序，包含 Xuanlyu Zhu，不再沿用旧 PDF 的六人名单。
引用见 [CITATION.cff](CITATION.cff) 和 [英文 README](README.md#citation)；未虚构发表信息。

大部分代码采用 [Apache License 2.0](LICENSE)；`evaluation.py` 的基准评分语义及数据集衍生文件继续受 CC BY-SA 4.0 约束，具体边界见 [NOTICE.md](NOTICE.md)。本项目仅用于科研，不是医疗器械，不得用于诊断、治疗或真实患者决策；运行任何生成代码前都应人工审查并在沙箱中执行。
