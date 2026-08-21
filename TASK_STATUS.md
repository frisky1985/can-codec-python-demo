# TASK_STATUS — can-codec-python-demo (B 阶段 Python 泛化验证)

> 更新: 2026-08-21 | 维护: 小明 (Hermes)

## 项目定位

**B 阶段载体**: yuleOSH 平台 Python 泛化验证（A1 = C++ motor-cpp-demo 已冻结，B = Python）。
领域: 车载 CAN 2.0 报文编解码库（帧解析 + Intel/Motorola 信号位级编解码 + 物理换算 + 高层 PDU 编解码器）。
形态: 纯 stdlib, Py3.10+, pytest, src/ layout。

## 原子需求

| 原子 | 内容 | 状态 | 证据 |
|:--|:--|:--|:--|
| B-R01 | 项目骨架 + spec (OpenSpec 合规) + seed 代码 + pytest | ✅ | 84 tests passed + spec validate ✅ |
| B-R02 | pipeline 首跑 → Python 项目支持缺口清单 | 🔄 | 待跑 |
| B-R03 | 平台缺口修复 + 回归测试 | ⬜ | |
| B-R04 | 重跑 pipeline GREEN + 泛化报告 | ⬜ | |

## 决策

- **B 阶段**: Python 泛化验证，复用 A1 (cpp-support-gaps) 三类硬编码审计模式：语言检测 / 源码收集 / 静态分析语言 flag + coverage/C-only 步骤跳过行为。
