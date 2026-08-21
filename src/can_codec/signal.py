"""can_codec.signal — CAN 信号位级提取/插入与物理值换算。

位序契约 (spec FR-005..FR-007):
    - Intel (little-endian): start_bit 为信号 LSB 在帧数据中的位索引
      (从 byte0 bit0=0 开始递增, 低字节在前)。跨字节时低位字节在前。
    - Motorola (big-endian, Vector MSB 编号): start_bit 为信号 MSB 的
      MSB 编号。MSB 编号规则: byte0 bit7=7, byte0 bit0=0; byte1 bit7=15,
      byte1 bit0=8; byte2 bit7=23 ... 信号从 MSB 位置向下连续取 length 位。

物理换算 (spec FR-008):
    physical = raw * scale + offset
    raw      = round((physical - offset) / scale)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .errors import (
    InvalidSignalError,
    SignalEncodeError,
    SignalExtractError,
    SignalValueError,
)

ByteOrder = Literal["little", "big"]

_LITTLE = "little"
_BIG = "big"


@dataclass(frozen=True)
class CanSignal:
    """信号定义。

    Attributes:
        name: 信号名 (如 "EngineSpeed")。
        start_bit: 起始位 (Intel=LSB 位索引; Motorola=MSB 编号)。
        length: 信号位宽 (1..64)。
        byte_order: "little" (Intel) / "big" (Motorola)。
        is_signed: True=二进制补码有符号, False=无符号。
        scale: 物理换算缩放系数 (默认 1.0)。
        offset: 物理换算偏移量 (默认 0.0)。
        min_value / max_value: 物理值域 (默认 ±inf, 不校验)。
    """

    name: str
    start_bit: int
    length: int
    byte_order: ByteOrder = _LITTLE
    is_signed: bool = False
    scale: float = 1.0
    offset: float = 0.0
    min_value: float = float("-inf")
    max_value: float = float("inf")

    def __post_init__(self) -> None:
        if not self.name:
            raise InvalidSignalError("信号名不能为空")
        if self.start_bit < 0:
            raise InvalidSignalError(f"start_bit {self.start_bit} 不能为负")
        if not (1 <= self.length <= 64):
            raise InvalidSignalError(f"length {self.length} 超出 1..64")
        if self.byte_order not in (_LITTLE, _BIG):
            raise InvalidSignalError(f"byte_order 必须为 'little'/'big', got {self.byte_order!r}")
        if self.scale <= 0:
            raise InvalidSignalError(f"scale {self.scale} 必须为正")
        if self.min_value > self.max_value:
            raise InvalidSignalError(
                f"min_value {self.min_value} 大于 max_value {self.max_value}"
            )

    @property
    def raw_min(self) -> int:
        """原始值下界。"""
        return -(1 << (self.length - 1)) if self.is_signed else 0

    @property
    def raw_max(self) -> int:
        """原始值上界。"""
        return (1 << (self.length - 1)) - 1 if self.is_signed else (1 << self.length) - 1


def _little_extract(data: bytes, start_bit: int, length: int) -> int:
    buf = int.from_bytes(data, "little")
    return (buf >> start_bit) & ((1 << length) - 1)


def _motorola_extract(data: bytes, msb_pos: int, length: int) -> int:
    """Motorola (CANdb++ 编号) 信号提取。

    编号规则: bit n 的物理位置 = byte n//8, bit_in_byte n%8
    (byte0 bit7=7 ... byte0 bit0=0, byte1 bit7=15 ... byte1 bit0=8)。
    信号从 MSB 编号向低方向取位; 同字节内 bit 递减; 跨字节时跳到
    下一个更低字节的 bit7 (MSB 所在字节为最高有效字节)。
    """
    value = 0
    pos = msb_pos
    for _ in range(length):
        byte_idx = pos // 8
        bit_in_byte = pos % 8
        if not (0 <= byte_idx < len(data)):
            raise SignalExtractError(
                f"Motorola 信号位编号 {pos} 超出帧 {len(data) * 8} 位范围 "
                f"(msb_pos={msb_pos}, length={length})"
            )
        value = (value << 1) | ((data[byte_idx] >> bit_in_byte) & 1)
        if bit_in_byte == 0:
            pos = (byte_idx + 1) * 8 + 7
        else:
            pos -= 1
    return value


def _little_insert(data: bytearray, start_bit: int, length: int, raw_value: int) -> None:
    buf = int.from_bytes(data, "little")
    mask = (1 << length) - 1
    if raw_value < 0 or raw_value > mask:
        raise SignalEncodeError(
            f"原始值 {raw_value} 超出 {length} 位无符号值域 0..{mask}"
        )
    buf = (buf & ~(mask << start_bit)) | (raw_value << start_bit)
    data[:] = buf.to_bytes(len(data), "little")


def _motorola_insert(data: bytearray, msb_pos: int, length: int, raw_value: int) -> None:
    mask = (1 << length) - 1
    if raw_value < 0 or raw_value > mask:
        raise SignalEncodeError(
            f"原始值 {raw_value} 超出 {length} 位无符号值域 0..{mask}"
        )
    pos = msb_pos
    for i in range(length):
        byte_idx = pos // 8
        bit_in_byte = pos % 8
        if not (0 <= byte_idx < len(data)):
            raise SignalEncodeError(
                f"Motorola 信号位编号 {pos} 超出帧 {len(data) * 8} 位范围 "
                f"(msb_pos={msb_pos}, length={length})"
            )
        bit = (raw_value >> (length - 1 - i)) & 1
        if bit:
            data[byte_idx] |= 1 << bit_in_byte
        else:
            data[byte_idx] &= ~(1 << bit_in_byte)
        if bit_in_byte == 0:
            pos = (byte_idx + 1) * 8 + 7
        else:
            pos -= 1


def extract_signal(data: bytes, signal: CanSignal) -> int:
    """从帧数据提取信号原始值 (raw)。

    Raises:
        SignalExtractError: 位偏移超出帧数据可表示范围。
    """
    if signal.byte_order == _LITTLE:
        buf_bits = len(data) * 8
        if signal.start_bit + signal.length > buf_bits:
            raise SignalExtractError(
                f"Intel 信号 {signal.name}: start_bit={signal.start_bit} + length={signal.length} "
                f"超出帧 {buf_bits} 位"
            )
        raw = _little_extract(data, signal.start_bit, signal.length)
    else:
        raw = _motorola_extract(data, signal.start_bit, signal.length)
    if signal.is_signed and raw & (1 << (signal.length - 1)):
        raw -= 1 << signal.length
    return raw


def insert_signal(data: bytearray, signal: CanSignal, raw_value: int) -> None:
    """将信号原始值写入帧数据 (原地修改)。

    Raises:
        SignalEncodeError: 位越界或原始值超出信号值域。
    """
    if raw_value < signal.raw_min or raw_value > signal.raw_max:
        raise SignalEncodeError(
            f"信号 {signal.name}: 原始值 {raw_value} 超出 {signal.raw_min}..{signal.raw_max}"
        )
    unsigned = raw_value & ((1 << signal.length) - 1)
    if signal.byte_order == _LITTLE:
        buf_bits = len(data) * 8
        if signal.start_bit + signal.length > buf_bits:
            raise SignalEncodeError(
                f"Intel 信号 {signal.name}: start_bit={signal.start_bit} + length={signal.length} "
                f"超出帧 {buf_bits} 位"
            )
        _little_insert(data, signal.start_bit, signal.length, unsigned)
    else:
        _motorola_insert(data, signal.start_bit, signal.length, unsigned)


def raw_to_physical(raw: int, signal: CanSignal) -> float:
    """原始值 → 物理值: physical = raw * scale + offset。"""
    physical = raw * signal.scale + signal.offset
    if physical < signal.min_value or physical > signal.max_value:
        raise SignalValueError(
            f"信号 {signal.name}: 物理值 {physical} 超出 {signal.min_value}..{signal.max_value}"
        )
    return physical


def physical_to_raw(physical: float, signal: CanSignal) -> int:
    """物理值 → 原始值: raw = round((physical - offset) / scale)。

    Raises:
        SignalValueError: 物理值超出信号物理值域, 或换算后原始值超出信号原始值域。
    """
    if physical < signal.min_value or physical > signal.max_value:
        raise SignalValueError(
            f"信号 {signal.name}: 物理值 {physical} 超出 {signal.min_value}..{signal.max_value}"
        )
    raw = round((physical - signal.offset) / signal.scale)
    if raw < signal.raw_min or raw > signal.raw_max:
        raise SignalValueError(
            f"信号 {signal.name}: 物理值 {physical} 换算原始值 {raw} "
            f"超出 {signal.raw_min}..{signal.raw_max}"
        )
    return raw
