# CAN 报文编解码库 — 规范聚合文档（CI 视图）

> 本文档是 CI/合规检查的规范视图。**权威规范源**：
> - 聚合索引（pipeline 入口）：仓库根 `spec.md`（v1.0.0）
> - 结构化规范（OpenSpec）：`.osh/specs/can-codec/spec.md`
>
> 本视图保持与根 spec.md 同步；新增需求先改 `.osh/specs/`，再同步根 spec.md 与本视图。

## 需求与契约

| capability | 内容 | req ID |
|:--|:--|:--|
| `can-codec` | FR-001..FR-011 功能需求（帧模型/标准扩展帧/线格式/Intel·Motorola 信号/物理换算/高层编解码器/异常层级）+ SR-001..SR-003 系统需求 + 验收场景 AC-001..AC-005 | FR-001..FR-011, SR-001..SR-003 |

需求总计 14（SR-001..003 + FR-001..011），验收场景 5。

## 需求关键词分布

规范正文含 SHALL（必须）、SHOULD（应该）、MAY（可以）三类需求关键词，
语义遵循 RFC 2119。所有 SHALL 语句均有可测试的验收场景支撑。

## 一致性校验

```text
yuleosh spec validate .osh/specs/ --json          # error_count = 0
```
