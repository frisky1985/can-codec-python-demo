"""frame 模块测试 — CAN 帧解析/构造 (FR-001..FR-004)。"""

import pytest

from can_codec.errors import FrameDecodeError, FrameEncodeError
from can_codec.frame import CanFrame, decode_frame, encode_frame


class TestCanFrameValidation:
    def test_standard_frame_default(self):
        frame = CanFrame(arbitration_id=0x123)
        assert frame.extended is False
        assert frame.dlc == 0
        assert frame.timestamp_us == 0

    def test_standard_id_upper_bound_ok(self):
        assert CanFrame(arbitration_id=0x7FF).arbitration_id == 0x7FF

    def test_standard_id_overflow_rejected(self):
        with pytest.raises(FrameEncodeError):
            CanFrame(arbitration_id=0x800)

    def test_extended_id_upper_bound_ok(self):
        assert CanFrame(arbitration_id=0x1FFFFFFF, extended=True).arbitration_id == 0x1FFFFFFF

    def test_extended_id_overflow_rejected(self):
        with pytest.raises(FrameEncodeError):
            CanFrame(arbitration_id=0x20000000, extended=True)

    def test_negative_id_rejected(self):
        with pytest.raises(FrameEncodeError):
            CanFrame(arbitration_id=-1)

    def test_data_too_long_rejected(self):
        with pytest.raises(FrameEncodeError):
            CanFrame(arbitration_id=0x100, data=bytes(9))

    def test_data_8_bytes_ok(self):
        assert CanFrame(arbitration_id=0x100, data=bytes(8)).dlc == 8

    def test_dlc_matches_data_len(self):
        frame = CanFrame(arbitration_id=0x100, data=b"\x01\x02")
        assert frame.dlc == 2


class TestFrameRoundTrip:
    def test_standard_frame_roundtrip(self):
        frame = CanFrame(arbitration_id=0x123, data=b"\xDE\xAD\xBE\xEF", extended=False)
        assert decode_frame(encode_frame(frame)) == frame

    def test_extended_frame_roundtrip(self):
        frame = CanFrame(arbitration_id=0x1ABCDEF, data=bytes(8), extended=True)
        assert decode_frame(encode_frame(frame)) == frame

    def test_zero_id_roundtrip(self):
        frame = CanFrame(arbitration_id=0, data=b"")
        assert decode_frame(encode_frame(frame)) == frame

    def test_max_standard_id_roundtrip(self):
        frame = CanFrame(arbitration_id=0x7FF, data=b"\xFF")
        assert decode_frame(encode_frame(frame)) == frame

    def test_max_extended_id_roundtrip(self):
        frame = CanFrame(arbitration_id=0x1FFFFFFF, data=bytes(8), extended=True)
        assert decode_frame(encode_frame(frame)) == frame

    def test_roundtrip_preserves_payload(self):
        payload = bytes(range(8))
        frame = CanFrame(arbitration_id=0x456, data=payload)
        assert decode_frame(encode_frame(frame)).data == payload

    def test_extended_flag_preserved(self):
        raw = encode_frame(CanFrame(arbitration_id=0x456, data=b"", extended=True))
        assert decode_frame(raw).extended is True


class TestFrameDecodeErrors:
    def test_too_short_raises(self):
        with pytest.raises(FrameDecodeError):
            decode_frame(b"\x00")

    def test_empty_raises(self):
        with pytest.raises(FrameDecodeError):
            decode_frame(b"")

    def test_truncated_payload_raises(self):
        # DLC=8 但只有 3 字节负载
        raw = bytes([0, 0, 0x01, 0x01]) + b"\xAA\xBB\xCC"
        with pytest.raises(FrameDecodeError):
            decode_frame(raw)

    def test_invalid_dlc_raises(self):
        # DLC=9 > 8
        raw = bytes([0, 0, 0x01, 0x09]) + bytes(9)
        with pytest.raises(FrameDecodeError):
            decode_frame(raw)

    def test_extended_flag_with_overflow_id_raises(self):
        # 29-bit 帧但 ID 超 0x1FFFFFFF
        raw = (0x80000000 | 0x20000000).to_bytes(4, "big") + b"\x00"
        with pytest.raises(FrameDecodeError):
            decode_frame(raw)

    def test_standard_flag_with_overflow_id_raises(self):
        # 标准帧标志但 ID > 0x7FF
        raw = (0x00000800).to_bytes(4, "big") + b"\x00"
        with pytest.raises(FrameDecodeError):
            decode_frame(raw)
