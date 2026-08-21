"""codec 模块测试 — 高层 PDU 编解码 (FR-009..FR-010)。"""

import pytest

from can_codec import CanCodec, CanFrame, CanSignal
from can_codec.codec import UnknownFrameError
from can_codec.errors import CanCodecError, SignalValueError


class TestRegister:
    def test_register_and_decode_roundtrip(self):
        codec = CanCodec()
        codec.register(
            0x123,
            [CanSignal("EngineSpeed", 0, 16, scale=0.25)],
        )
        frame = codec.encode(0x123, {"EngineSpeed": 1000.0})
        assert frame.arbitration_id == 0x123
        assert codec.decode(frame) == {"EngineSpeed": 1000.0}

    def test_negative_id_rejected(self):
        codec = CanCodec()
        with pytest.raises(CanCodecError):
            codec.register(-1, [CanSignal("S", 0, 8)])

    def test_empty_signals_rejected(self):
        codec = CanCodec()
        with pytest.raises(CanCodecError):
            codec.register(0x100, [])

    def test_register_overwrites(self):
        codec = CanCodec()
        codec.register(0x100, [CanSignal("A", 0, 8)])
        codec.register(0x100, [CanSignal("B", 8, 8)])
        assert list(codec.decode(CanFrame(0x100, b"\x00\x01"))) == ["B"]


class TestDecode:
    def test_unknown_frame_id_raises(self):
        codec = CanCodec()
        codec.register(0x100, [CanSignal("S", 0, 8)])
        with pytest.raises(UnknownFrameError):
            codec.decode(CanFrame(0x200, b"\x01"))

    def test_decode_multi_signal(self):
        codec = CanCodec()
        codec.register(
            0x123,
            [
                CanSignal("Speed", 0, 16, scale=0.01),
                CanSignal("Dir", 16, 1),
            ],
        )
        frame = CanFrame(0x123, b"\x10\x27\x01")
        result = codec.decode(frame)
        assert result["Speed"] == pytest.approx(100.0)
        assert result["Dir"] == 1.0

    def test_decode_short_data_raises_extract(self):
        codec = CanCodec()
        codec.register(0x100, [CanSignal("Word", 0, 16)])
        with pytest.raises(CanCodecError):
            codec.decode(CanFrame(0x100, b"\x01"))


class TestEncode:
    def test_encode_grows_data_to_signal_width(self):
        codec = CanCodec()
        codec.register(0x100, [CanSignal("Word", 0, 16)])
        frame = codec.encode(0x100, {"Word": 0x1234})
        assert frame.data == b"\x34\x12"
        assert frame.dlc == 2

    def test_encode_motorola_layout(self):
        codec = CanCodec()
        codec.register(0x200, [CanSignal("Word", 7, 16, byte_order="big")])
        frame = codec.encode(0x200, {"Word": 0x1234})
        assert frame.data == b"\x12\x34"

    def test_encode_unknown_value_rejected(self):
        codec = CanCodec()
        codec.register(0x100, [CanSignal("A", 0, 8)])
        with pytest.raises(CanCodecError):
            codec.encode(0x100, {"A": 1, "Ghost": 2})

    def test_encode_value_out_of_range_raises(self):
        codec = CanCodec()
        codec.register(0x100, [CanSignal("A", 0, 8, min_value=0, max_value=100)])
        with pytest.raises(SignalValueError):
            codec.encode(0x100, {"A": 200})

    def test_encode_unknown_frame_id_raises(self):
        codec = CanCodec()
        codec.register(0x100, [CanSignal("A", 0, 8)])
        with pytest.raises(UnknownFrameError):
            codec.encode(0x200, {"A": 1})

    def test_extended_codec_roundtrip(self):
        codec = CanCodec(extended=True)
        codec.register(0x1ABCDEF, [CanSignal("A", 0, 8)])
        frame = codec.encode(0x1ABCDEF, {"A": 42})
        assert frame.extended is True
        assert codec.decode(frame) == {"A": 42.0}

    def test_encode_motorola_msb_byte1_needs_three_bytes(self):
        """start_bit=15/len=16: 覆盖 byte1+byte2, 数组长度 3 (byte0 空闲) — 锁定 needed_bytes 公式。"""
        codec = CanCodec()
        codec.register(0x300, [CanSignal("W", 15, 16, byte_order="big")])
        frame = codec.encode(0x300, {"W": 0x1234})
        assert len(frame.data) == 3
        assert frame.data[1:] == b"\x12\x34"
        decoded = codec.decode(frame)
        assert decoded["W"] == 0x1234

    def test_encode_motorola_mid_byte_start_needs_two_bytes(self):
        """start_bit=11/len=8: 覆盖 byte1 低4位 + byte2 高4位, 数组长度 3。"""
        codec = CanCodec()
        codec.register(0x301, [CanSignal("X", 11, 8, byte_order="big")])
        frame = codec.encode(0x301, {"X": 0xA0})
        assert len(frame.data) == 3
        decoded = codec.decode(frame)
        assert decoded["X"] == 0xA0


class TestEndToEnd:
    def test_vehicle_dashboard_pdu_roundtrip(self):
        """整车仪表 PDU 端到端: 发动机转速 + 车速 + 档位打包/解包。"""
        codec = CanCodec()
        codec.register(
            0x1A0,
            [
                CanSignal("EngineSpeed", 0, 16, scale=0.25, min_value=0, max_value=16383.75),
                CanSignal("VehicleSpeed", 16, 8, scale=1.0, min_value=0, max_value=255),
                CanSignal("Gear", 24, 3),
            ],
        )
        values = {"EngineSpeed": 3000.0, "VehicleSpeed": 80.0, "Gear": 4.0}
        frame = codec.encode(0x1A0, values)
        assert frame.dlc == 4
        decoded = codec.decode(frame)
        assert decoded["EngineSpeed"] == pytest.approx(3000.0)
        assert decoded["VehicleSpeed"] == pytest.approx(80.0)
        assert decoded["Gear"] == 4.0

    def test_motorola_pdu_roundtrip(self):
        """博世风格 Motorola 字节序 PDU 端到端。"""
        codec = CanCodec()
        codec.register(
            0x0C4,
            [
                CanSignal("Torque", 15, 16, byte_order="big", scale=0.1, min_value=-3276.8, max_value=3276.7),
                CanSignal("Temp", 7, 8, byte_order="big"),
            ],
        )
        values = {"Torque": 123.4, "Temp": 85.0}
        frame = codec.encode(0x0C4, values)
        decoded = codec.decode(frame)
        assert decoded["Torque"] == pytest.approx(123.4, abs=0.05)
        assert decoded["Temp"] == pytest.approx(85.0)
