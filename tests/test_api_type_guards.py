"""FR-011 类型守卫测试 — 公共 API 非法输入必须抛领域异常, 不泄漏 TypeError。

2026-08-21 B dogfood run2: codex-verify 抓 4 条 TypeError 泄漏
(CanFrame(None)/decode_frame(None)/CanSignal('S','0',8)/register('1', ...))。
本套件锁定: 所有公共 API 的错误类型输入 → CanCodecError 子类。
"""

import pytest

from can_codec import (
    CanCodec,
    CanCodecError,
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

SIG = CanSignal("S", 0, 8)


class TestFrameTypeGuards:
    def test_frame_none_data(self):
        with pytest.raises(FrameEncodeError):
            CanFrame(0x123, None)

    def test_frame_str_data(self):
        with pytest.raises(FrameEncodeError):
            CanFrame(0x123, "abc")

    def test_frame_str_id(self):
        with pytest.raises(FrameEncodeError):
            CanFrame("0x123")

    def test_encode_frame_wrong_type(self):
        with pytest.raises(FrameEncodeError):
            encode_frame("not a frame")

    def test_decode_frame_none(self):
        with pytest.raises(FrameDecodeError):
            decode_frame(None)

    def test_decode_frame_str(self):
        with pytest.raises(FrameDecodeError):
            decode_frame("001122")

    def test_decode_frame_accepts_bytearray(self):
        raw = encode_frame(CanFrame(0x100, b"\x01"))
        assert decode_frame(bytearray(raw)) == CanFrame(0x100, b"\x01")


class TestSignalTypeGuards:
    def test_signal_str_start_bit(self):
        with pytest.raises(InvalidSignalError):
            CanSignal("S", "0", 8)

    def test_signal_bool_length(self):
        with pytest.raises(InvalidSignalError):
            CanSignal("S", 0, True)

    def test_signal_str_scale(self):
        with pytest.raises(InvalidSignalError):
            CanSignal("S", 0, 8, scale="1.0")

    def test_signal_float_start_bit(self):
        with pytest.raises(InvalidSignalError):
            CanSignal("S", 0.0, 8)

    def test_extract_wrong_data(self):
        with pytest.raises(SignalExtractError):
            extract_signal("b'\\x01'", SIG)

    def test_extract_wrong_signal(self):
        with pytest.raises(SignalExtractError):
            extract_signal(b"\x01", "S")

    def test_insert_wrong_data(self):
        with pytest.raises(SignalEncodeError):
            insert_signal(b"\x00", SIG, 1)  # bytes 不可变

    def test_insert_wrong_raw(self):
        with pytest.raises(SignalEncodeError):
            insert_signal(bytearray(1), SIG, "1")

    def test_raw_to_physical_wrong_raw(self):
        with pytest.raises(SignalValueError):
            raw_to_physical("100", SIG)

    def test_physical_to_raw_wrong_physical(self):
        with pytest.raises(SignalValueError):
            physical_to_raw(None, SIG)

    def test_conversion_wrong_signal(self):
        with pytest.raises(SignalValueError):
            raw_to_physical(1, "S")


class TestNaNGuard:
    """FR-008/FR-011: NaN/inf 必须被领域异常拒绝, 不泄漏裸 ValueError。"""

    def test_scale_nan_rejected(self):
        with pytest.raises(InvalidSignalError):
            CanSignal("S", 0, 8, scale=float("nan"))

    def test_offset_nan_rejected(self):
        with pytest.raises(InvalidSignalError):
            CanSignal("S", 0, 8, offset=float("nan"))

    def test_min_value_nan_rejected(self):
        with pytest.raises(InvalidSignalError):
            CanSignal("S", 0, 8, min_value=float("nan"))

    def test_physical_to_raw_nan(self):
        with pytest.raises(SignalValueError):
            physical_to_raw(float("nan"), SIG)

    def test_physical_to_raw_inf(self):
        with pytest.raises(SignalValueError):
            physical_to_raw(float("inf"), SIG)

    def test_raw_to_physical_nan(self):
        with pytest.raises(SignalValueError):
            raw_to_physical(float("nan"), SIG)

    def test_codec_encode_nan_value(self):
        codec = CanCodec()
        codec.register(0x100, [SIG])
        with pytest.raises(SignalValueError):
            codec.encode(0x100, {"S": float("nan")})


class TestCodecTypeGuards:
    def test_register_str_id(self):
        codec = CanCodec()
        with pytest.raises(CanCodecError):
            codec.register("1", [SIG])

    def test_register_non_signal(self):
        codec = CanCodec()
        with pytest.raises(CanCodecError):
            codec.register(0x100, ["S"])

    def test_decode_wrong_frame(self):
        codec = CanCodec()
        codec.register(0x100, [SIG])
        with pytest.raises(CanCodecError):
            codec.decode("0x100")

    def test_encode_str_id(self):
        codec = CanCodec()
        codec.register(0x100, [SIG])
        with pytest.raises(CanCodecError):
            codec.encode("0x100", {"S": 1})

    def test_encode_non_dict_values(self):
        codec = CanCodec()
        codec.register(0x100, [SIG])
        with pytest.raises(CanCodecError):
            codec.encode(0x100, [1, 2])

    def test_encode_str_value(self):
        codec = CanCodec()
        codec.register(0x100, [SIG])
        with pytest.raises(SignalValueError):
            codec.encode(0x100, {"S": "1"})


@pytest.mark.parametrize(
    "fn",
    [
        lambda: CanFrame(0x123, None),
        lambda: decode_frame(None),
        lambda: CanSignal("S", "0", 8),
        lambda: CanCodec().register("1", [SIG]),
        lambda: extract_signal("bad", SIG),
        lambda: insert_signal(b"\x00", SIG, 1),
        lambda: raw_to_physical("bad", SIG),
    ],
)
def test_no_bare_exception_leaks(fn):
    """所有非法输入路径都抛 CanCodecError 子类, 绝不泄漏 TypeError。"""
    with pytest.raises(CanCodecError):
        fn()
