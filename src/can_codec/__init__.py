"""can_codec — CAN 2.0 报文编解码库。

模块按领域职责拆分（禁 utils/helpers/common 泛化命名）:
- frame:  CAN 帧解析/构造 (标准帧 11-bit / 扩展帧 29-bit)
- signal: 信号位级提取/插入 + 原始值 ↔ 物理值换算 (Intel/Motorola 字节序)
- codec:  高层 PDU 编解码器 (帧 ↔ 信号字典)
- errors: 领域异常类型

设计约束: 纯标准库, Python >= 3.10, 无第三方依赖。
"""

from .codec import CanCodec
from .errors import (
    CanCodecError,
    FrameDecodeError,
    InvalidSignalError,
    SignalEncodeError,
    SignalExtractError,
    SignalValueError,
)
from .frame import CanFrame, decode_frame, encode_frame
from .signal import CanSignal, extract_signal, insert_signal, physical_to_raw, raw_to_physical

__all__ = [
    "CanCodec",
    "CanCodecError",
    "CanFrame",
    "CanSignal",
    "FrameDecodeError",
    "InvalidSignalError",
    "SignalEncodeError",
    "SignalExtractError",
    "SignalValueError",
    "decode_frame",
    "encode_frame",
    "extract_signal",
    "insert_signal",
    "physical_to_raw",
    "raw_to_physical",
]

__version__ = "0.1.0"
