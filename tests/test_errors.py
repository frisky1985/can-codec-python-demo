"""errors 模块测试 — 异常层级与消息 (FR-011)。"""

import pytest

from can_codec import CanCodecError
from can_codec.errors import (
    FrameDecodeError,
    FrameEncodeError,
    InvalidSignalError,
    SignalEncodeError,
    SignalExtractError,
    SignalValueError,
)


@pytest.mark.parametrize(
    "exc",
    [
        FrameDecodeError,
        FrameEncodeError,
        InvalidSignalError,
        SignalEncodeError,
        SignalExtractError,
        SignalValueError,
    ],
)
def test_all_errors_subclass_can_codec_error(exc):
    assert issubclass(exc, CanCodecError)


def test_can_codec_error_is_exception():
    assert issubclass(CanCodecError, Exception)


def test_error_message_preserved():
    exc = FrameDecodeError("bad frame")
    assert str(exc) == "bad frame"


def test_catch_via_base_class():
    with pytest.raises(CanCodecError):
        raise SignalExtractError("oops")
