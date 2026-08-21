"""can_codec.errors — CAN 编解码领域异常类型。

异常层级:
    CanCodecError (基类)
    ├── FrameDecodeError      帧解码失败 (长度不足/非法 ID/数据超长)
    ├── FrameEncodeError      帧编码失败 (帧字段非法)
    ├── SignalExtractError    信号提取越界 (位偏移超出帧数据范围)
    ├── SignalEncodeError     信号写入越界 (位偏移/长度超出帧容量)
    ├── SignalValueError      物理值换算越界 (超出信号 min/max 或原始值域)
    └── InvalidSignalError    信号定义非法 (start_bit/length/scale/offset 违反约束)
"""

from __future__ import annotations


class CanCodecError(Exception):
    """CAN 编解码领域错误基类。"""


class FrameDecodeError(CanCodecError):
    """CAN 帧解码失败。"""


class FrameEncodeError(CanCodecError):
    """CAN 帧编码失败。"""


class SignalExtractError(CanCodecError):
    """信号提取越界 — 位偏移超出帧数据可表示范围。"""


class SignalEncodeError(CanCodecError):
    """信号写入越界 — 位偏移/长度超出帧容量。"""


class SignalValueError(CanCodecError):
    """信号物理值越界 — 换算结果超出信号定义值域。"""


class InvalidSignalError(CanCodecError):
    """信号定义非法 — start_bit/length/scale/offset 违反约束。"""
