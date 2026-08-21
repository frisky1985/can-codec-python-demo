"""can_codec.frame — CAN 2.0 帧解析与构造。

帧线格式（本库文档化契约，spec FR-001..FR-004）:
    4 字节头 + 1 字节 DLC + 0..8 字节数据
    - 头: 4 字节大端无符号整数
        bit31       = extended 标志 (1=扩展帧 29-bit ID, 0=标准帧 11-bit ID)
        bit30..0    = arbitration_id (标准帧 ≤ 0x7FF, 扩展帧 ≤ 0x1FFFFFFF)
    - DLC: 1 字节数据长度 (0..8)
    - data: DLC 字节数据

约束:
    - 标准帧 ID 范围 0x000..0x7FF (11 bit)
    - 扩展帧 ID 范围 0x00000000..0x1FFFFFFF (29 bit)
    - DLC 上限 8 (经典 CAN), 超过抛 FrameEncodeError/FrameDecodeError
"""

from __future__ import annotations

from dataclasses import dataclass, field
from struct import pack, unpack

from .errors import FrameDecodeError, FrameEncodeError

_STANDARD_ID_MAX = 0x7FF
_EXTENDED_ID_MAX = 0x1FFFFFFF
_DLC_MAX = 8
_EXTENDED_FLAG = 0x80000000
_HEADER_LEN = 4
_DLC_LEN = 1


@dataclass(frozen=True)
class CanFrame:
    """CAN 2.0 帧。

    Attributes:
        arbitration_id: 仲裁 ID (标准帧 11-bit / 扩展帧 29-bit)。
        data: 负载数据 (0..8 字节)。
        extended: True=扩展帧 (29-bit ID), False=标准帧 (11-bit ID)。
        timestamp_us: 时间戳 (微秒), 默认 0。
    """

    arbitration_id: int
    data: bytes = b""
    extended: bool = False
    timestamp_us: int = field(default=0)

    @property
    def dlc(self) -> int:
        """数据长度计数 (Data Length Code)。"""
        return len(self.data)

    def __post_init__(self) -> None:
        _validate_id(self.arbitration_id, self.extended)
        _validate_data(self.data)


def _validate_id(arbitration_id: int, extended: bool) -> None:
    if not isinstance(arbitration_id, int):
        raise FrameEncodeError(f"arbitration_id 必须为 int, got {type(arbitration_id).__name__}")
    limit = _EXTENDED_ID_MAX if extended else _STANDARD_ID_MAX
    if not (0 <= arbitration_id <= limit):
        kind = "扩展" if extended else "标准"
        raise FrameEncodeError(
            f"{kind}帧仲裁 ID {arbitration_id} 超出范围 0..0x{limit:X}"
        )


def _validate_data(data: bytes) -> None:
    if len(data) > _DLC_MAX:
        raise FrameEncodeError(f"数据长度 {len(data)} 超过 CAN 上限 {_DLC_MAX} 字节")
    if not isinstance(data, bytes):
        raise FrameEncodeError(f"data 必须为 bytes, got {type(data).__name__}")


def encode_frame(frame: CanFrame) -> bytes:
    """将 CanFrame 编码为线格式字节流。

    Raises:
        FrameEncodeError: 帧字段非法 (ID 超范围/数据超长)。
    """
    header = frame.arbitration_id | (_EXTENDED_FLAG if frame.extended else 0)
    return pack(">I", header) + pack(">B", frame.dlc) + bytes(frame.data)


def decode_frame(raw: bytes) -> CanFrame:
    """从线格式字节流解析 CanFrame。

    Raises:
        FrameDecodeError: 字节流过短/头非法/DLC 与实际数据不匹配。
    """
    if len(raw) < _HEADER_LEN + _DLC_LEN:
        raise FrameDecodeError(
            f"帧字节流过短: {len(raw)} 字节 (最小 {_HEADER_LEN + _DLC_LEN})"
        )
    (header,) = unpack(">I", raw[:_HEADER_LEN])
    (dlc,) = unpack(">B", raw[_HEADER_LEN : _HEADER_LEN + _DLC_LEN])
    extended = bool(header & _EXTENDED_FLAG)
    arbitration_id = header & ~_EXTENDED_FLAG
    payload = raw[_HEADER_LEN + _DLC_LEN :]

    limit = _EXTENDED_ID_MAX if extended else _STANDARD_ID_MAX
    if arbitration_id > limit:
        kind = "扩展" if extended else "标准"
        raise FrameDecodeError(f"{kind}帧仲裁 ID 0x{arbitration_id:X} 超出范围")
    if dlc > _DLC_MAX:
        raise FrameDecodeError(f"DLC {dlc} 超过 CAN 上限 {_DLC_MAX}")
    if len(payload) != dlc:
        raise FrameDecodeError(
            f"DLC={dlc} 但实际负载 {len(payload)} 字节不匹配"
        )
    return CanFrame(arbitration_id=arbitration_id, data=payload, extended=extended)
