"""signal 模块测试 — 位级提取/插入 + 物理换算 (FR-005..FR-008)。"""

import pytest

from can_codec.errors import (
    InvalidSignalError,
    SignalEncodeError,
    SignalExtractError,
    SignalValueError,
)
from can_codec.signal import (
    CanSignal,
    extract_signal,
    insert_signal,
    physical_to_raw,
    raw_to_physical,
)


class TestSignalDefinition:
    def test_defaults(self):
        sig = CanSignal("Speed", 0, 8)
        assert sig.byte_order == "little"
        assert sig.is_signed is False
        assert sig.scale == 1.0
        assert sig.offset == 0.0
        assert sig.raw_min == 0
        assert sig.raw_max == 255

    def test_signed_raw_range(self):
        sig = CanSignal("Temp", 0, 8, is_signed=True)
        assert sig.raw_min == -128
        assert sig.raw_max == 127

    def test_empty_name_rejected(self):
        with pytest.raises(InvalidSignalError):
            CanSignal("", 0, 8)

    def test_negative_start_bit_rejected(self):
        with pytest.raises(InvalidSignalError):
            CanSignal("S", -1, 8)

    def test_zero_length_rejected(self):
        with pytest.raises(InvalidSignalError):
            CanSignal("S", 0, 0)

    def test_length_over_64_rejected(self):
        with pytest.raises(InvalidSignalError):
            CanSignal("S", 0, 65)

    def test_invalid_byte_order_rejected(self):
        with pytest.raises(InvalidSignalError):
            CanSignal("S", 0, 8, byte_order="middle")

    def test_nonpositive_scale_rejected(self):
        with pytest.raises(InvalidSignalError):
            CanSignal("S", 0, 8, scale=0)

    def test_min_above_max_rejected(self):
        with pytest.raises(InvalidSignalError):
            CanSignal("S", 0, 8, min_value=10, max_value=5)


class TestIntelExtract:
    def test_single_byte_low_nibble(self):
        sig = CanSignal("Nib", 0, 4)
        assert extract_signal(b"\xA5", sig) == 0x5

    def test_single_byte_high_nibble(self):
        sig = CanSignal("Nib", 4, 4)
        assert extract_signal(b"\xA5", sig) == 0xA

    def test_single_byte_full(self):
        sig = CanSignal("Byte", 0, 8)
        assert extract_signal(b"\x7F", sig) == 0x7F

    def test_16bit_little_cross_byte(self):
        # little-endian: 低位字节在前
        sig = CanSignal("Word", 0, 16)
        assert extract_signal(b"\x34\x12", sig) == 0x1234

    def test_start_bit_offset_cross_byte(self):
        # start_bit=8 → 取第二个字节
        sig = CanSignal("Hi", 8, 8)
        assert extract_signal(b"\xAA\x55", sig) == 0x55

    def test_signed_negative(self):
        sig = CanSignal("Temp", 0, 8, is_signed=True)
        assert extract_signal(b"\xFE", sig) == -2

    def test_signed_positive(self):
        sig = CanSignal("Temp", 0, 8, is_signed=True)
        assert extract_signal(b"\x02", sig) == 2

    def test_extract_beyond_frame_raises(self):
        sig = CanSignal("Word", 0, 16)
        with pytest.raises(SignalExtractError):
            extract_signal(b"\x01", sig)


class TestMotorolaExtract:
    def test_byte0_full(self):
        # msb_pos=7 → byte0 全 8 位
        sig = CanSignal("B0", 7, 8, byte_order="big")
        assert extract_signal(b"\x12\x34", sig) == 0x12

    def test_byte1_full(self):
        # msb_pos=15 → byte0 bit7..; 取 8 位 → byte0? 按规则 msb_pos=15=byte1 bit7
        sig = CanSignal("B1", 15, 8, byte_order="big")
        assert extract_signal(b"\x12\x34", sig) == 0x34

    def test_16bit_big_whole_bytes(self):
        # msb_pos=7 (byte0 bit7, MSB 在 byte0) → 两完整字节: 0x1234
        sig = CanSignal("Word", 7, 16, byte_order="big")
        assert extract_signal(b"\x12\x34", sig) == 0x1234

    def test_byte0_high_nibble(self):
        # msb_pos=7, length=4 → byte0 高 4 位: 0x1
        sig = CanSignal("Nib", 7, 4, byte_order="big")
        assert extract_signal(b"\x12", sig) == 0x1

    def test_cross_byte_alignment(self):
        # msb_pos=11 (byte1 bit3), length=8 → byte1 低 4 位 + byte2 高 4 位
        # 0x5A 低4位=1010, 0x0F 高4位=0000 → 1010 0000 = 0xA0
        sig = CanSignal("Cross", 11, 8, byte_order="big")
        assert extract_signal(b"\xA5\x5A\x0F", sig) == 0xA0

    def test_cross_byte_16bit_msb_byte1(self):
        # msb_pos=15 (byte1 bit7), length=16 → byte1 + byte2 (MSB 在 byte1)
        sig = CanSignal("W", 15, 16, byte_order="big")
        assert extract_signal(b"\x00\x12\x34", sig) == 0x1234

    def test_motorola_beyond_frame_raises(self):
        sig = CanSignal("W", 15, 8, byte_order="big")
        with pytest.raises(SignalExtractError):
            extract_signal(b"\x01", sig)  # 1 字节只有 8 位

    def test_motorola_mid_byte_cross_multi_byte(self):
        # msb_pos=19 (byte2 bit3), length=12 → byte2 bit3..0 + byte3 全部
        sig = CanSignal("Deep", 19, 12, byte_order="big")
        data = b"\x00\x00\x0A\xBC"
        # byte2=0x0A bit3..0 = 1010; byte3=0xBC = 1011 1100 → 1010 1011 1100
        assert extract_signal(data, sig) == 0xABC

    def test_motorola_insert_extract_roundtrip_varied(self):
        """跨字节 Motorola round-trip 矩阵 (mid-byte 起始 / 多字节延伸)。"""
        cases = [
            (7, 8),    # byte0 整字节
            (15, 8),   # byte1 整字节
            (7, 16),   # byte0+byte1 (MSB 在 byte0)
            (15, 16),  # byte1+byte2 (MSB 在 byte1)
            (11, 8),   # byte1 bit3 起始, 跨 byte2
            (19, 12),  # byte2 bit3 起始, 跨 byte3
            (3, 6),    # 单字节内中段
        ]
        for msb_pos, length in cases:
            sig = CanSignal(f"S{msb_pos}_{length}", msb_pos, length, byte_order="big")
            data = bytearray(4)
            value = 0b101010101010  # 12 位以内固定值 (含跨字节)
            # 只测 length 位能容纳的值域内随机值
            import random
            rng = random.Random(msb_pos * 100 + length)
            value = rng.randint(0, (1 << length) - 1)
            insert_signal(data, sig, value)
            assert extract_signal(bytes(data), sig) == value, (
                f"round-trip failed msb={msb_pos} len={length}"
            )


class TestInsert:
    def test_insert_low_nibble(self):
        sig = CanSignal("Nib", 0, 4)
        data = bytearray(b"\x00")
        insert_signal(data, sig, 0xA)
        assert data == bytearray(b"\x0A")

    def test_insert_high_nibble_preserves_low(self):
        sig = CanSignal("Nib", 4, 4)
        data = bytearray(b"\x05")
        insert_signal(data, sig, 0xA)
        assert data == bytearray(b"\xA5")

    def test_insert_16bit_little(self):
        sig = CanSignal("Word", 0, 16)
        data = bytearray(2)
        insert_signal(data, sig, 0x1234)
        assert data == bytearray(b"\x34\x12")

    def test_insert_motorola_16bit(self):
        # MSB 在 byte0 (msb_pos=7): 0x12 存 byte0, 0x34 存 byte1
        sig = CanSignal("Word", 7, 16, byte_order="big")
        data = bytearray(2)
        insert_signal(data, sig, 0x1234)
        assert data == bytearray(b"\x12\x34")

    def test_insert_signed_negative(self):
        sig = CanSignal("Temp", 0, 8, is_signed=True)
        data = bytearray(1)
        insert_signal(data, sig, -2)
        assert data == bytearray(b"\xFE")

    def test_insert_unsigned_overflow_rejected(self):
        sig = CanSignal("Byte", 0, 8)
        data = bytearray(1)
        with pytest.raises(SignalEncodeError):
            insert_signal(data, sig, 256)

    def test_insert_signed_overflow_rejected(self):
        sig = CanSignal("Temp", 0, 8, is_signed=True)
        data = bytearray(1)
        with pytest.raises(SignalEncodeError):
            insert_signal(data, sig, 128)

    def test_insert_beyond_frame_raises(self):
        sig = CanSignal("Word", 0, 16)
        data = bytearray(1)
        with pytest.raises(SignalEncodeError):
            insert_signal(data, sig, 1)


class TestPhysicalConversion:
    def test_scale_only(self):
        sig = CanSignal("Voltage", 0, 8, scale=0.1)
        assert raw_to_physical(100, sig) == pytest.approx(10.0)
        assert physical_to_raw(10.0, sig) == 100

    def test_scale_offset(self):
        sig = CanSignal("Temp", 0, 8, scale=0.5, offset=-40.0)
        assert raw_to_physical(200, sig) == pytest.approx(60.0)
        assert physical_to_raw(60.0, sig) == 200

    def test_physical_roundtrip(self):
        sig = CanSignal("Speed", 0, 16, scale=0.01)
        for phys in (0.0, 12.34, 100.0, 650.00):
            raw = physical_to_raw(phys, sig)
            assert raw_to_physical(raw, sig) == pytest.approx(phys, abs=0.005)

    def test_physical_above_max_raises(self):
        sig = CanSignal("Speed", 0, 8, min_value=0, max_value=100)
        with pytest.raises(SignalValueError):
            raw_to_physical(200, sig)

    def test_physical_raw_out_of_range_raises(self):
        sig = CanSignal("Byte", 0, 8)
        with pytest.raises(SignalValueError):
            physical_to_raw(300, sig)

    def test_signed_physical_negative(self):
        sig = CanSignal("Temp", 0, 8, is_signed=True, scale=1.0, offset=0.0)
        assert raw_to_physical(-10, sig) == pytest.approx(-10.0)
        assert physical_to_raw(-10, sig) == -10
