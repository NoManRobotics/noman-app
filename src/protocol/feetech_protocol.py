import serial
from enum import Enum
from typing import Any, List, Tuple
import time

class FeetechCommands(Enum):
    """Feetech协议支持的命令"""
    # 基础控制命令
    PING           = "PING"          # 检测舵机
    READ           = "READ"          # 读取数据
    WRITE          = "WRITE"         # 写入数据
    REG_WRITE      = "REG_WRITE"     # 异步写入
    ACTION         = "ACTION"        # 执行异步写入
    RESET          = "RESET"         # 重置舵机
    SYNC_WRITE     = "SYNC_WRITE"    # 同步写入多个舵机
    
    # 位置控制命令
    SET_POSITION   = "SET_POSITION"  # 设置目标位置
    GET_POSITION   = "GET_POSITION"  # 获取当前位置
    SET_SPEED      = "SET_SPEED"     # 设置移动速度
    GET_SPEED      = "GET_SPEED"     # 获取当前速度
    
    # 扭矩控制命令
    TORQUE_ENABLE  = "TORQUE_ENABLE" # 使能扭矩
    TORQUE_DISABLE = "TORQUE_DISABLE"# 禁用扭矩
    SET_TORQUE     = "SET_TORQUE"    # 设置扭矩限制
    GET_TORQUE     = "GET_TORQUE"    # 获取当前扭矩
    
    # 参数设置命令
    SET_ID         = "SET_ID"        # 设置舵机ID
    GET_ID         = "GET_ID"        # 获取舵机ID
    SET_BAUDRATE   = "SET_BAUDRATE"  # 设置波特率
    GET_BAUDRATE   = "GET_BAUDRATE"  # 获取波特率
    
    # 状态查询命令
    GET_LOAD       = "GET_LOAD"      # 获取负载
    GET_VOLTAGE    = "GET_VOLTAGE"   # 获取电压
    GET_TEMP       = "GET_TEMP"      # 获取温度
    GET_STATUS     = "GET_STATUS"    # 获取状态
    
    # 高级功能命令
    SET_ANGLE_LIMIT = "SET_ANGLE_LIMIT"  # 设置角度限制
    GET_ANGLE_LIMIT = "GET_ANGLE_LIMIT"  # 获取角度限制
    SET_COMPLIANCE  = "SET_COMPLIANCE"   # 设置柔顺性
    GET_COMPLIANCE  = "GET_COMPLIANCE"   # 获取柔顺性
    
    # 模式切换命令
    SET_SERVO_MODE  = "SET_SERVO_MODE"   # 设置舵机模式
    SET_MOTOR_MODE  = "SET_MOTOR_MODE"   # 设置电机模式
    SET_PWM_MODE    = "SET_PWM_MODE"     # 设置PWM模式

class FeetechProtocol:
    """Feetech通信协议实现"""
    
    # 协议常量
    PACKET_HEADER = [0xFF, 0xFF]
    INSTRUCTION_PING = 0x01
    INSTRUCTION_READ = 0x02
    INSTRUCTION_WRITE = 0x03
    INSTRUCTION_REG_WRITE = 0x04
    INSTRUCTION_ACTION = 0x05
    INSTRUCTION_RESET = 0x06
    INSTRUCTION_SYNC_WRITE = 0x83
    
    # 内存地址常量
    ADDR_ID = 5
    ADDR_BAUDRATE = 6
    ADDR_TORQUE_ENABLE = 24
    ADDR_GOAL_POSITION = 30
    ADDR_GOAL_SPEED = 32
    ADDR_PRESENT_POSITION = 36
    ADDR_PRESENT_SPEED = 38
    ADDR_PRESENT_LOAD = 40
    ADDR_PRESENT_VOLTAGE = 42
    ADDR_PRESENT_TEMPERATURE = 43
    
    # 默认配置
    FEETECH_BAUDRATE = 1000000
    DEFAULT_TIMEOUT = 1.0
    
    _serial = None
    port = None
    baudrate = FEETECH_BAUDRATE
    timeout = DEFAULT_TIMEOUT

    _COMMAND_MAP = {
        FeetechCommands.PING: INSTRUCTION_PING,
        FeetechCommands.READ: INSTRUCTION_READ,
        FeetechCommands.WRITE: INSTRUCTION_WRITE,
        FeetechCommands.REG_WRITE: INSTRUCTION_REG_WRITE,
        FeetechCommands.ACTION: INSTRUCTION_ACTION,
        FeetechCommands.RESET: INSTRUCTION_RESET,
        FeetechCommands.SYNC_WRITE: INSTRUCTION_SYNC_WRITE,
    }

    @classmethod
    def connect(cls, port: str, baudrate: int = 1000000) -> bool:
        """建立串口连接"""
        cls.port = port
        cls.baudrate = baudrate
        try:
            cls._serial = serial.Serial(
                port=cls.port,
                baudrate=cls.baudrate,
                timeout=cls.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            cls._serial.setDTR(False)
            cls._serial.setRTS(False)
            # 清空缓冲区
            cls._serial.reset_input_buffer()
            cls._serial.reset_output_buffer()
            return True
        except Exception as e:
            print(f"Feetech connection error: {e}")
            return False

    @classmethod
    def disconnect(cls) -> bool:
        """断开串口连接"""
        if cls._serial and cls._serial.is_open:
            try:
                cls._serial.close()
                cls._serial = None
                return True
            except Exception as e:
                print(f"Feetech disconnection error: {e}")
        return False

    @classmethod
    def _calculate_checksum(cls, packet: List[int]) -> int:
        """计算校验和"""
        checksum = 0
        for byte in packet[2:]:  # 跳过头部的两个0xFF
            checksum += byte
        return (~checksum) & 0xFF

    @classmethod
    def _create_packet(cls, servo_id: int, instruction: int, parameters: List[int] = None) -> List[int]:
        """创建数据包"""
        if parameters is None:
            parameters = []
        
        packet = cls.PACKET_HEADER.copy()
        packet.append(servo_id)
        packet.append(len(parameters) + 2)  # 长度 = 参数长度 + 指令 + 校验和
        packet.append(instruction)
        packet.extend(parameters)
        
        checksum = cls._calculate_checksum(packet)
        packet.append(checksum)
        
        return packet

    @classmethod
    def send(cls, packet: List[int], sleep_time: float = 0.005) -> bool:
        """发送数据包"""
        try:
            if cls._serial and cls._serial.is_open:
                data = bytes(packet)
                cls._serial.write(data)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                return True
            return False
        except Exception as e:
            print(f"Feetech send error: {e}")
            return False

    @classmethod
    def receive(cls, timeout: float = 5.0, expected_length: int = None) -> Tuple[List[int], bool]:
        """接收数据包"""
        if not cls._serial or not cls._serial.is_open:
            return [], False
        
        start_time = time.time()
        received_data = []
        
        while time.time() - start_time < timeout:
            if cls._serial.in_waiting > 0:
                byte = cls._serial.read(1)
                if byte:
                    received_data.append(ord(byte))
                    
                    # 检查是否接收到完整数据包
                    if len(received_data) >= 4:  # 最小包长度
                        # 检查包头
                        if received_data[0] == 0xFF and received_data[1] == 0xFF:
                            expected_packet_length = received_data[3] + 4  # 长度字段 + 头部
                            if len(received_data) >= expected_packet_length:
                                # 验证校验和
                                packet = received_data[:expected_packet_length]
                                calculated_checksum = cls._calculate_checksum(packet[:-1])
                                if packet[-1] == calculated_checksum:
                                    return packet, True
                                else:
                                    print(f"Checksum error: expected {calculated_checksum}, got {packet[-1]}")
                                    received_data = []
            time.sleep(0.001)
        
        return received_data, False

    @classmethod
    def clear_serial_buffer(cls):
        """清空串口缓冲区"""
        if cls._serial and cls._serial.is_open:
            cls._serial.reset_input_buffer()
            cls._serial.reset_output_buffer()

    @classmethod
    def is_connected(cls) -> bool:
        """检查连接状态"""
        return cls._serial is not None and cls._serial.is_open

    @classmethod
    def ping(cls, servo_id: int) -> bool:
        """发送PING命令检测舵机"""
        if not cls.is_connected():
            return False
        
        packet = cls._create_packet(servo_id, cls.INSTRUCTION_PING)
        if cls.send(packet):
            response, success = cls.receive(timeout=1.0)
            return success and len(response) >= 6
        return False

    @classmethod
    def read_data(cls, servo_id: int, address: int, length: int = 1) -> Tuple[List[int], bool]:
        """读取舵机数据"""
        if not cls.is_connected():
            return [], False
        
        parameters = [address, length]
        packet = cls._create_packet(servo_id, cls.INSTRUCTION_READ, parameters)
        
        if cls.send(packet):
            response, success = cls.receive(timeout=1.0)
            if success and len(response) >= 6:
                # 提取参数数据
                param_length = response[3] - 2  # 减去指令和校验和
                if param_length > 0:
                    return response[5:5+param_length], True
        return [], False

    @classmethod
    def write_data(cls, servo_id: int, address: int, data: List[int]) -> bool:
        """写入舵机数据"""
        if not cls.is_connected():
            return False
        
        parameters = [address] + data
        packet = cls._create_packet(servo_id, cls.INSTRUCTION_WRITE, parameters)
        
        if cls.send(packet):
            response, success = cls.receive(timeout=1.0)
            return success
        return False

    @classmethod
    def set_position(cls, servo_id: int, position: int, speed: int = 0) -> bool:
        """设置舵机位置"""
        # 位置范围通常是0-1023或0-4095，取决于舵机型号
        position = max(0, min(position, 1023))
        speed = max(0, min(speed, 1023))
        
        # 写入目标位置
        pos_data = [position & 0xFF, (position >> 8) & 0xFF]
        if not cls.write_data(servo_id, cls.ADDR_GOAL_POSITION, pos_data):
            return False
        
        # 如果指定了速度，也设置速度
        if speed > 0:
            speed_data = [speed & 0xFF, (speed >> 8) & 0xFF]
            return cls.write_data(servo_id, cls.ADDR_GOAL_SPEED, speed_data)
        
        return True

    @classmethod
    def get_position(cls, servo_id: int) -> Tuple[int, bool]:
        """获取舵机当前位置"""
        data, success = cls.read_data(servo_id, cls.ADDR_PRESENT_POSITION, 2)
        if success and len(data) >= 2:
            position = data[0] + (data[1] << 8)
            return position, True
        return 0, False

    @classmethod
    def set_torque_enable(cls, servo_id: int, enable: bool) -> bool:
        """设置扭矩使能"""
        data = [1 if enable else 0]
        return cls.write_data(servo_id, cls.ADDR_TORQUE_ENABLE, data)

    @classmethod
    def get_status(cls, servo_id: int) -> dict:
        """获取舵机状态信息"""
        status = {
            'position': 0,
            'speed': 0,
            'load': 0,
            'voltage': 0,
            'temperature': 0,
            'connected': False
        }
        
        # 检测舵机连接
        if not cls.ping(servo_id):
            return status
        
        status['connected'] = True
        
        # 读取位置
        position, success = cls.get_position(servo_id)
        if success:
            status['position'] = position
        
        # 读取速度
        data, success = cls.read_data(servo_id, cls.ADDR_PRESENT_SPEED, 2)
        if success and len(data) >= 2:
            status['speed'] = data[0] + (data[1] << 8)
        
        # 读取负载
        data, success = cls.read_data(servo_id, cls.ADDR_PRESENT_LOAD, 2)
        if success and len(data) >= 2:
            status['load'] = data[0] + (data[1] << 8)
        
        # 读取电压
        data, success = cls.read_data(servo_id, cls.ADDR_PRESENT_VOLTAGE, 1)
        if success and len(data) >= 1:
            status['voltage'] = data[0] / 10.0  # 通常电压值需要除以10
        
        # 读取温度
        data, success = cls.read_data(servo_id, cls.ADDR_PRESENT_TEMPERATURE, 1)
        if success and len(data) >= 1:
            status['temperature'] = data[0]
        
        return status

    @classmethod
    def execute_command(cls, command: Enum, *args, **kwargs) -> Any:
        """执行命令"""
        if not cls.is_connected():
            raise ConnectionError("Feetech port not connected")
        
        # 高级命令处理
        if command == FeetechCommands.SET_POSITION:
            if len(args) >= 2:
                return cls.set_position(args[0], args[1], args[2] if len(args) > 2 else 0)
            raise ValueError("SET_POSITION requires servo_id and position")
        
        elif command == FeetechCommands.GET_POSITION:
            if len(args) >= 1:
                return cls.get_position(args[0])
            raise ValueError("GET_POSITION requires servo_id")
        
        elif command == FeetechCommands.TORQUE_ENABLE:
            if len(args) >= 1:
                return cls.set_torque_enable(args[0], True)
            raise ValueError("TORQUE_ENABLE requires servo_id")
        
        elif command == FeetechCommands.TORQUE_DISABLE:
            if len(args) >= 1:
                return cls.set_torque_enable(args[0], False)
            raise ValueError("TORQUE_DISABLE requires servo_id")
        
        elif command == FeetechCommands.GET_STATUS:
            if len(args) >= 1:
                return cls.get_status(args[0])
            raise ValueError("GET_STATUS requires servo_id")
        
        elif command == FeetechCommands.PING:
            if len(args) >= 1:
                return cls.ping(args[0])
            raise ValueError("PING requires servo_id")
        
        # 基础命令处理
        elif command in cls._COMMAND_MAP:
            instruction = cls._COMMAND_MAP[command]
            if len(args) >= 1:
                servo_id = args[0]
                parameters = list(args[1:]) if len(args) > 1 else []
                packet = cls._create_packet(servo_id, instruction, parameters)
                
                if cls.send(packet):
                    response, success = cls.receive()
                    return response if success else None
            raise ValueError(f"Command {command.value} requires servo_id")
        
        else:
            raise ValueError(f"Command {command.value} not supported")
