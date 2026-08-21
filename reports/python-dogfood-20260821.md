# B 阶段 Python 泛化验证报告（can-codec-python-demo → yuleOSH 平台）

> 日期: 2026-08-21 | 验证人: 小明 (Hermes 主 agent) | 项目: can-codec-python-demo (CAN 2.0 报文编解码库, 纯 stdlib Python)
> 目的: yuleOSH 24 步 pipeline 对 **Python 项目**端到端支持验证（语言泛化第二棒, A1=C++ 已冻结）
> 方法: 真实运行证据优先, 不采信预判（工程诚实第一准则）

---

## 1. 结论摘要

| 项 | 结果 |
|:--|:--|
| B-R01 载体开发 | ✅ 84→132 pytest 全绿 (src 5 文件 + 单测 119 + e2e 5 场景) |
| B-R02 pipeline 首跑实测 | ✅ 8 轮真实运行, 抓出 2 类平台缺口 + 4 轮 codex-verify 载体缺陷 |
| B-R03 平台修复 | ✅ 2 处 (repo-facts Python 用例数 + c-coverage-gate 无 C skip), 全量相关测试 90+ passed |
| B-R04 终态 | ✅ run8 `b15199f90abe` **GREEN — Errors: 0, 场景覆盖 5/5** |

**核心结论**: yuleOSH 平台对 Python 项目的支持在语言检测/源码收集/静态分析层无缺口（A1 修复已覆盖），
B 阶段真实缺口在 **① 文档步骤对仓库现状的感知（repo_facts 的 Python 测试用例数）** 与
**② C-only 步骤的跳过完整性（c-coverage-gate）**。修复后 Python 项目全流程 GREEN。

---

## 2. 平台缺口实测清单（证据链）

### GAP-B1: repo_facts 对 Python 项目输出 "Test functions: 0"（run1, claude-review 5 blockers）
- **位置**: `src/yuleosh/pipeline/repo_facts.py` — `test_func_count` 只统计 .c/.h/.cpp/.hpp 的 test_ 函数
- **实测**: can-codec 4 个测试文件列出但 `Test functions: 0` → development LLM 看到矛盾 →
  "声称仓库 0 测试、'84 全绿'为伪造" → 绿地视角重写已有实现（blocker critical ×2）
- **修复** (13a1eff4): `count_test_functions` 按后缀分发 (.py → def test_ 计数) +
  pytest 框架项目用 `pytest --collect-only` 真实用例数（含参数化展开, 84 精确）+ 3 个新测试
- **复验**: `Test functions: 84` ✅; claude-review run2 起 AGREE ✅

### GAP-B2: c-coverage-gate 对 Python 项目跑 cmake build 失败（run5）
- **位置**: `src/yuleosh/pipeline/step_handlers/c_coverage_gate.py` — 真实模式无"无 C 源码 skip"
- **实测**: qemu-verify 合并步骤, qemu-run 无 .elf skip ✅, 但 c-coverage-gate 直接
  `_phase_build_coverage` → "C coverage: build phase failed" → pipeline RED
- **修复** (f06b5bdc): `_has_c_sources()` 跳过逻辑（排除 third_party/build/.git/.osh/venv,
  与 qemu-run/autosar 同模式）+ 6 个新测试
- **复验**: run6 qemu-verify ✅

### 无缺口项（实测确认）
- 语言检测: `_detect_project_language` → 'python'（A1 已支持）
- codegen 验证: `py_compile` 语法验证（compilers.py 已支持）
- pytest/coverage: ci/stages/test.py 原生支持
- c-unit-test / misra-review / fault-injection / review-critical-safety: 均有 skip/空集处理 ✅

---

## 3. 载体缺陷闭环（codex-verify 4 轮, 全部真实）

| 轮 | 缺陷 | 修复 | 新增测试 |
|:--|:--|:--|:--|
| run2 | 4× 裸 TypeError (CanFrame(None)/decode_frame(None)/CanSignal('S','0',8)/register('1')) | 全公共 API 类型守卫 → 领域异常 | 24 |
| run3 | NaN/inf 校验缺口 (scale=NaN 接受 + round(nan)→ValueError) | scale/offset/min/max 拒 NaN + 换算拒非有限值 | 7 |
| run4 | sorted(unknown) 混合类型键 → 裸 TypeError | key=str 归一 | 1 |

载体终态: 132 pytest（119 单测 + 5 e2e 场景 + 类型守卫/NaN 覆盖）

---

## 4. 载体侧验收（can-codec-python-demo 本体）

- 24 步 pipeline GREEN: claude-review AGREE → verify-loop (codex-verify PASS) →
  c-unit-test/code-review/misra-review/integration-test ✅ → qemu-verify (skip) →
  coverage-review/review-critical-safety/fault-injection/merge-gate ✅ →
  **test-qualification PASSED (5/5 场景, 1/1 测试)** → final-report ✅
- spec v1.0.0 OpenSpec 合规 (yuleosh spec validate ✅)
- 仓库 frisky1985/can-codec-python-demo, main 已推送

---

## 5. 决策建议

- **B 阶段冻结**: R01-R04 全部验收, 语言泛化验证载体使命完成
- **C 阶段建议**: Rust/Go 语言泛化, 或平台能力深化（如 Python 覆盖率门禁接入 pipeline）
- **遗留 (Out-of-Scope)**: 真实 CAN 总线硬件对接（本载体为纯软件库）

---

*报告结束 — 全部结论基于 8 轮真实 pipeline 运行 (run-20260821-122137 → b15199f90abe) 与机器收集证据。*
