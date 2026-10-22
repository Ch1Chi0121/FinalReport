# 快速使用

先在项目根目录创建虚拟环境，并安装 README 中锁定的依赖。运行高速版本需要
C 编译器；首次调用时会自动编译。包里没有本机编译出来的二进制文件。

建议按这个顺序阅读：

1. `examples/single_avalanche.py`：用一个 3×3 例子看输入、雪崩和返回值。
2. `sandpile/reference.py`：每次只做一次倒塌，最容易对照数学定义。
3. `sandpile/engine.py`：同一规则的 Python 队列实现。
4. `sandpile/kernel.c`、`fast.py`：长实验使用的 C 循环和 Python 接口。
5. `sandpile/experiment.py`：随机输入、预热、正式采样和断点恢复。
6. `sandpile/statistics.py`、`analysis.py`：统计方法与实验比较。

先执行 `python run_project.py check` 和 `python run_project.py smoke`。
前者跑测试，后者在临时目录中把四个模型各跑两遍并比较结果，不需要 LaTeX。
`python run_project.py all` 按顺序运行全部实验、分析、画图和表格生成。
如果还要编译报告，执行 `python run_project.py all --pdf`，需要额外安装
Tectonic 和 pdfinfo。

这是代码包，原始实验的大体积逐事件数据没有放进来。`reference_results/`
保留原报告、主要汇总和数值来源，方便比较；重跑产生的数据另存到 `data/`。

本版把文件检查简化为源码副本比对、文件长度和 NPZ 自带的 CRC 检查。
不要混用旧版检查点。原始实验代码和数据仍完整保留。
停止后重新执行相同的运行命令，会从本版本的稳定检查点继续。

运行记录在 `logs/workflow.json`，每一步的详细输出在对应的
`logs/workflow_*.txt` 中。测试或计算失败时流程会停下，不会把失败步骤记为完成。
