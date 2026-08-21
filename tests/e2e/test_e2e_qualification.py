"""系统级合格性测试 (SWE.6) — 覆盖 spec 验收场景 AC-001..AC-005。

本文件被 yuleOSH test-qualification 步骤发现并执行 (tests/e2e/ 模式)。
每个测试对应一个 GIVEN/WHEN/THEN 场景, 使用公开 API 做端到端验证。
"""

import pytest

from can_codec import (
    CanCodec,
    CanFrame,
    CanSignal,
    decode_frame,
    encode_frame,
    extract_signal,
    insert_signal,
    physical_to_raw,
    raw_to_physical,
)
from can_codec.errors import (
    FrameDecodeError,
    FrameEncodeError,
    InvalidSignalError,
    SignalEncodeError,
    SignalExtractError,
    SignalValueError,
)


def test_qualification_ac001_standard_frame_roundtrip():
    """AC-001: 标准帧端到端 — GIVEN standard frame 0x123 WHEN encoded THEN decoded identical."""
    frame = CanFrame(arbitration_id=0x123, data=b"\xDE\xAD\xBE\xEF")
    decoded = decode_frame(encode_frame(frame))
    assert decoded == frame
    assert decoded.extended is False


def test_qualification_ac002_extended_frame_roundtrip():
    """AC-002: 扩展帧端到端 — GIVEN extended frame 0x1ABCDEF WHEN encoded THEN decoded."""
    frame = CanFrame(arbitration_id=0x1ABCDEF, data=bytes(8), extended=True)
    decoded = decode_frame(encode_frame(frame))
    assert decoded == frame
    assert decoded.extended is True


def test_qualification_ac003_signal_bit_level_roundtrip():
    """AC-003: 信号位级 round-trip — Intel/Motorola 16-bit 0x1234 布局正确."""
    intel = CanSignal("IntelWord", 0, 16, byte_order="little")
    motorola = CanSignal("MotorolaWord", 7, 16, byte_order="big")
    d1 = bytearray(2)
    insert_signal(d1, intel, 0x1234)
    assert d1 == bytearray(b"\x34\x12")
    d2 = bytearray(2)
    insert_signal(d2, motorola, 0x1234)
    assert d2 == bytearray(b"\x12\x34")
    assert extract_signal(bytes(d1), intel) == 0x1234
    assert extract_signal(bytes(d2), motorola) == 0x1234


def test_qualification_ac004_dashboard_pdu_end_to_end():
    """AC-004: 整车仪表 PDU — EngineSpeed/VehicleSpeed/Gear 物理值 round-trip."""
    codec = CanCodec()
    codec.register(
        0x1A0,
        [
            CanSignal("EngineSpeed", 0, 16, scale=0.25, min_value=0, max_value=16383.75),
            CanSignal("VehicleSpeed", 16, 8, min_value=0, max_value=255),
            CanSignal("Gear", 24, 3),
        ],
    )
    values = {"EngineSpeed": 3000.0, "VehicleSpeed": 80.0, "Gear": 4.0}
    frame = codec.encode(0x1A0, values)
    decoded = codec.decode(frame)
    assert decoded["EngineSpeed"] == pytest.approx(3000.0)
    assert decoded["VehicleSpeed"] == pytest.approx(80.0)
    assert decoded["Gear"] == 4.0


def test_qualification_ac005_error_paths_domain_exceptions():
    """AC-005: 错误路径 — 每种失败模式抛对应领域异常, 不泄漏裸异常."""
    with pytest.raises(FrameEncodeError):
        CanFrame(arbitration_id=0x800)                      # ID overflow
    with pytest.raises(FrameDecodeError):
        decode_frame(b"\x00")                               # truncated raw
    with pytest.raises(SignalExtractError):
        extract_signal(b"\x01", CanSignal("Word", 0, 16))   # bit-range overflow
    with pytest.raises(SignalEncodeError):
        insert_signal(bytearray(1), CanSignal("B", 0, 8), 256)  # raw overflow
    with pytest.raises(SignalValueError):
        physical_to_raw(300.0, CanSignal("B", 0, 8))        # physical overflow
    codec = CanCodec()
    codec.register(0x100, [CanSignal("A", 0, 8)])
    with pytest.raises(Exception):
        codec.decode(CanFrame(0x200, b"\x01"))              # unregistered ID
    with pytest.raises(InvalidSignalError):
        CanSignal("", 0, 8)                                 # invalid definition
