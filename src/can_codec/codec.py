"""can_codec.codec — 高层 PDU 编解码器。

CanCodec 将「仲裁 ID ↔ 信号列表」映射封装为高层 API:
    decode(frame)  → {signal_name: physical_value, ...}   帧 → 物理值字典
    encode(id, values) → CanFrame                         物理值字典 → 帧

语义 (spec FR-009..FR-010):
    - decode 只提取该帧 ID 已注册的信号; 未注册帧 ID 抛 KeyError 语义的
      LookupError (CanCodecError 子类见 errors.py)。
    - encode 对每个信号做 physical_to_raw → insert_signal; 任一信号越界
      即抛 SignalValueError/SignalEncodeError, 不产生半成品帧。
    - 多信号可重叠位域 (如 8-bit 拆两个 4-bit), 按注册顺序写入。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import CanCodecError, SignalEncodeError, SignalValueError
from .frame import CanFrame
from .signal import CanSignal, extract_signal, insert_signal, physical_to_raw, raw_to_physical


class UnknownFrameError(CanCodecError):
    """编解码器未注册该仲裁 ID 的帧。"""


@dataclass
class CanCodec:
    """仲裁 ID → 信号列表 映射的编解码器。

    Attributes:
        frame_signals: {arbitration_id: [CanSignal, ...]} 帧信号注册表。
        extended: 该编解码器默认是否按扩展帧处理注册的 ID (默认 False)。
    """

    frame_signals: dict[int, list[CanSignal]] = field(default_factory=dict)
    extended: bool = False

    def register(self, arbitration_id: int, signals: list[CanSignal]) -> None:
        """注册一个帧 ID 的信号列表 (覆盖同名 ID 的旧注册)。

        Raises:
            CanCodecError: 仲裁 ID 非 int/为负, 或信号列表为空/非 CanSignal。
        """
        if not isinstance(arbitration_id, int) or isinstance(arbitration_id, bool):
            raise CanCodecError(f"仲裁 ID 必须为 int, got {type(arbitration_id).__name__}")
        if arbitration_id < 0:
            raise CanCodecError(f"仲裁 ID {arbitration_id} 不能为负")
        if not signals:
            raise CanCodecError(f"仲裁 ID {arbitration_id} 的信号列表不能为空")
        for sig in signals:
            if not isinstance(sig, CanSignal):
                raise CanCodecError(
                    f"信号必须为 CanSignal, got {type(sig).__name__}"
                )
        self.frame_signals[arbitration_id] = list(signals)

    def decode(self, frame: CanFrame) -> dict[str, float]:
        """帧 → {信号名: 物理值}。

        Raises:
            UnknownFrameError: 帧仲裁 ID 未注册。
            CanCodecError: frame 非 CanFrame。
            SignalExtractError: 信号位越界 (帧数据过短)。
        """
        if not isinstance(frame, CanFrame):
            raise CanCodecError(f"frame 必须为 CanFrame, got {type(frame).__name__}")
        signals = self.frame_signals.get(frame.arbitration_id)
        if signals is None:
            raise UnknownFrameError(f"未注册仲裁 ID 0x{frame.arbitration_id:X} 的信号")
        return {sig.name: raw_to_physical(extract_signal(frame.data, sig), sig) for sig in signals}

    def encode(self, arbitration_id: int, values: dict[str, float]) -> CanFrame:
        """物理值字典 → CanFrame (数据长度按需扩展至信号位域上限)。

        Raises:
            UnknownFrameError: 仲裁 ID 未注册。
            CanCodecError: 参数类型非法 / 含未注册信号名。
            SignalValueError / SignalEncodeError: 值越界或位域越界。
        """
        if not isinstance(arbitration_id, int) or isinstance(arbitration_id, bool):
            raise CanCodecError(f"仲裁 ID 必须为 int, got {type(arbitration_id).__name__}")
        if not isinstance(values, dict):
            raise CanCodecError(f"values 必须为 dict, got {type(values).__name__}")
        signals = self.frame_signals.get(arbitration_id)
        if signals is None:
            raise UnknownFrameError(f"未注册仲裁 ID 0x{arbitration_id:X} 的信号")
        unknown = set(values) - {sig.name for sig in signals}
        if unknown:
            # 2026-08-21 B run4: sorted() 对 int/str 混合键抛裸 TypeError →
            # key=str 归一, 保证 FR-011 只抛领域异常
            raise CanCodecError(
                f"编码值含未注册信号 {sorted(unknown, key=str)} (ID 0x{arbitration_id:X})"
            )
        needed_bytes = 0
        for sig in signals:
            if sig.byte_order == "little":
                # Intel: start_bit 为 LSB 位索引, 所需字节 = ceil((start+len)/8)
                needed_bytes = max(needed_bytes, -(-(sig.start_bit + sig.length) // 8))
            else:
                # Motorola: 信号从 msb_pos 向高编号字节延伸。
                # 起始字节内可用位 = msb%8+1; 超出后每 8 位一个额外字节。
                start_byte = sig.start_bit // 8
                in_byte_bits = sig.start_bit % 8 + 1
                extra = 0
                if sig.length > in_byte_bits:
                    extra = -(-(sig.length - in_byte_bits) // 8)
                needed_bytes = max(needed_bytes, start_byte + 1 + extra)
        data = bytearray(needed_bytes or 1)
        for sig in signals:
            if sig.name in values:
                raw = physical_to_raw(values[sig.name], sig)
                insert_signal(data, sig, raw)
        return CanFrame(arbitration_id=arbitration_id, data=bytes(data), extended=self.extended)
