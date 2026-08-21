# CAN 报文编解码库 (CAN Message Codec)

> Version: 1.0.0 | Status: Draft
> v1.0.0 (2026-08-21): 初始契约 — 帧模型/标准扩展帧/位级信号提取 (Intel/Motorola)/物理换算/高层编解码器/异常层级。载体项目: yuleOSH 平台 Python 泛化验证 (B 阶段)。

---

## 1. System Requirements

### SR-001: 模块化架构
- The system SHALL decompose into focused modules by domain responsibility: `frame` (帧模型与线格式编解码), `signal` (信号位级提取/插入与物理值换算), `codec` (高层 PDU 编解码器), `errors` (领域异常类型层级)
- The system SHALL name modules by domain purpose (禁 utils/helpers/common 泛化命名)
- The system SHALL expose a narrow public interface for each module via `__init__.py`
- The system SHALL be importable as `can_codec` package from `src/` layout

### SR-002: 运行约束
- The system SHALL run on Python >= 3.10
- The system SHALL depend only on the Python standard library (零第三方运行时依赖)
- The system SHALL use type hints on all public functions and dataclass fields

### SR-003: 测试
- The system SHALL be covered by pytest unit tests in `tests/`
- The system SHALL have tests for every FR-xxx requirement with at least one RED-path (错误路径) case

---

## 2. Functional Requirements

### FR-001: 帧模型
- The system SHALL provide a `CanFrame` dataclass with fields: `arbitration_id` (int), `data` (bytes, 0..8), `extended` (bool, default False), `timestamp_us` (int, default 0)
- The system SHALL provide a `dlc` property equal to `len(data)`
- The system SHALL make `CanFrame` immutable (frozen dataclass) and equality-comparable for round-trip assertions

### FR-002: 标准帧
- The system SHALL support standard-frame arbitration IDs in range 0x000..0x7FF (11 bit)
- The system SHALL raise `FrameEncodeError` when constructing a `CanFrame` with standard ID > 0x7FF

### FR-003: 扩展帧
- The system SHALL support extended-frame arbitration IDs in range 0x00000000..0x1FFFFFFF (29 bit)
- The system SHALL raise `FrameEncodeError` when constructing a `CanFrame` with extended ID > 0x1FFFFFFF

### FR-004: 帧线格式编解码
- The system SHALL encode a `CanFrame` to a documented byte format: 4-byte big-endian header (bit31 = extended flag, bits30..0 = arbitration_id) + 1-byte DLC + payload
- The system SHALL make `encode_frame(frame)` return bytes and `decode_frame(raw)` return the identical `CanFrame` (round-trip)
- The system SHALL raise `FrameDecodeError` from `decode_frame` on: raw shorter than 5 bytes, DLC > 8, payload length ≠ DLC, or ID out of range

### FR-005: Intel 信号提取
- The system SHALL provide `extract_signal(data, signal)` returning the raw integer value for little-endian (Intel) signals
- The system SHALL interpret Intel `start_bit` as the LSB bit index counted from byte0 bit0=0 upward, with multi-byte signals little-endian (low byte first)
- The system SHALL raise `SignalExtractError` when extracting a signal whose bit range exceeds the frame data

### FR-006: Motorola 信号提取
- The system SHALL provide Motorola (big-endian) signal extraction using CANdb++ MSB numbering: bit n maps to byte n//8, bit n%8 (byte0 bit7=7 ... byte0 bit0=0, byte1 bit7=15 ... byte1 bit0=8)
- The system SHALL extend the signal from the MSB position downward within its byte, and when crossing a byte boundary continue at bit7 of the next higher byte (MSB-containing byte is the most significant)
- The system SHALL raise `SignalExtractError` when extracting beyond the frame data

### FR-007: 信号写入
- The system SHALL provide `insert_signal(data, signal, raw_value)` mutating a `bytearray` in place
- The system SHALL reject raw values outside the signal's raw range (signed/unsigned) with `SignalEncodeError`
- The system SHALL reject bit ranges beyond the frame capacity with `SignalEncodeError`
- The system SHALL make Intel insert little-endian and Motorola insert use the same numbering as FR-006

### FR-008: 物理换算
- The system SHALL provide `raw_to_physical(raw, signal)` = raw × scale + offset
- The system SHALL provide `physical_to_raw(physical, signal)` = round((physical − offset) / scale)
- The system SHALL raise `SignalValueError` from both when the result is outside the signal's declared domain (`min_value`/`max_value` for physical, raw_min/raw_max for raw)
- The system SHALL require positive `scale`; non-positive scale or min_value > max_value SHALL raise `InvalidSignalError` at signal construction

### FR-009: 高层编解码器
- The system SHALL provide a `CanCodec` class mapping arbitration IDs to signal lists
- The system SHALL make `codec.register(id, signals)` store the mapping and raise `CanCodecError` for empty signal list or negative ID
- The system SHALL make `codec.decode(frame)` return `{signal_name: physical_value}` for the frame's registered ID
- The system SHALL make `codec.encode(id, values)` return a `CanFrame` sized to cover the registered signals' bit ranges, with all values inserted
- The system SHALL raise `UnknownFrameError` (subclass of `CanCodecError`) on decode/encode of an unregistered ID

### FR-010: 错误路径与部分失败
- The system SHALL validate all values before mutating output in `CanCodec.encode` (no half-built frames on failure)
- The system SHALL raise `CanCodecError` when encoding an unknown signal name (not in the registered list)
- The system SHALL fail decode with an extract error (subclass of `CanCodecError`) when a frame's data is too short for a registered signal

### FR-011: 异常层级
- The system SHALL define `CanCodecError(Exception)` as the domain base
- The system SHALL define subclasses: `FrameDecodeError`, `FrameEncodeError`, `SignalExtractError`, `SignalEncodeError`, `SignalValueError`, `InvalidSignalError` — each SHALL subclass `CanCodecError`
- The system SHALL raise only domain exceptions (or `UnknownFrameError`) from public APIs, never bare `Exception`

---

## 3. Acceptance Scenarios

### Scenario: 标准帧端到端 (AC-001)
- GIVEN a standard frame with ID 0x123 and payload b"\xDE\xAD\xBE\xEF"
- WHEN the frame is encoded then decoded
- THEN the resulting frame SHALL be equal to the original (ID, data, extended=False preserved)

### Scenario: 扩展帧端到端 (AC-002)
- GIVEN an extended frame with ID 0x1ABCDEF and 8-byte payload
- WHEN the frame is encoded then decoded
- THEN the resulting frame SHALL be equal to the original with extended=True preserved

### Scenario: 信号位级 round-trip (AC-003)
- GIVEN a 16-bit Intel signal and a 16-bit Motorola signal (MSB at byte0)
- WHEN inserting value 0x1234 into fresh bytearrays and extracting back
- THEN both SHALL return 0x1234 with correct byte layouts (Intel b"\x34\x12", Motorola b"\x12\x34")

### Scenario: 整车仪表 PDU 端到端 (AC-004)
- GIVEN a codec registered with EngineSpeed (16-bit, scale 0.25), VehicleSpeed (8-bit), Gear (3-bit) on ID 0x1A0
- WHEN encoding {EngineSpeed: 3000, VehicleSpeed: 80, Gear: 4} and decoding the result
- THEN all three physical values SHALL round-trip within floating tolerance

### Scenario: 错误路径 (AC-005)
- GIVEN invalid inputs for each failure mode
- WHEN each failure mode is triggered
- THEN the system SHALL raise the corresponding domain exception: ID overflow → FrameEncodeError; truncated raw → FrameDecodeError; bit-range overflow → SignalExtractError; raw overflow → SignalEncodeError; physical overflow → SignalValueError; unregistered ID → UnknownFrameError; invalid definition → InvalidSignalError

---

## 4. 决策记录

- v1.0.0 (2026-08-21): 初始契约。帧线格式自文档化 (4B 头 + DLC + payload) 以便确定性单测；Motorola 采用 CANdb++ MSB 编号（业界 DBC 标准）；编解码器按"先校验后写"保证部分失败原子性。
