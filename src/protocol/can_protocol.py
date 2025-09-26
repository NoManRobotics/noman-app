import can
from enum import Enum
from typing import Any

class CANCommands(Enum):
    """CAN协议支持的命令"""
    # CAN特有的命令
    HOME = "home"
    SYNC = "sync"
    GET_TORQUE = "get_torque"
    SET_MODE = "set_mode"

class CanProtocol:
    """CAN通信协议实现"""
    
    _COMMAND_MAP = {
        CANCommands.HOME: "0x100",
        CANCommands.SYNC: "0x210",
        CANCommands.GET_TORQUE: "0x211",
        CANCommands.SET_MODE: "0x212",
    }
    
    _bus = None
    channel = None
    bitrate = 500000

    @classmethod
    def connect(cls, channel: str, bitrate: int = 500000) -> bool:
        """建立CAN总线连接"""
        cls.channel = channel
        cls.bitrate = bitrate
        try:
            cls._bus = can.interface.Bus(
                channel=cls.channel,
                bustype='socketcan',
                bitrate=cls.bitrate
            )
            return True
        except Exception as e:
            print(f"CAN connection failed: {e}")
            return False

    @classmethod
    def disconnect(cls) -> bool:
        """断开CAN总线连接"""
        if cls._bus:
            try:
                cls._bus.shutdown()
                cls._bus = None
                return True
            except Exception as e:
                print(f"CAN disconnection failed: {e}")
        return False

    @classmethod
    def is_connected(cls) -> bool:
        """检查CAN总线是否已连接"""
        return cls._bus is not None

    @classmethod
    def send(cls, data, sleep_time=0.005) -> bool:
        """向CAN总线发送数据"""
        if not cls.is_connected():
            raise ConnectionError("CAN bus not connected")
        
        try:
            msg = can.Message(
                arbitration_id=0x123,  # 示例ID
                data=data,
                is_extended_id=False
            )
            cls._bus.send(msg)
            return True
        except Exception as e:
            print(f"CAN send failed: {e}")
            return False

    @classmethod
    def receive(cls, timeout=5, expected_signal=None):
        """从CAN总线接收数据"""
        if not cls.is_connected():
            raise ConnectionError("CAN bus not connected")
        
        try:
            msg = cls._bus.recv(timeout=timeout)
            if msg is None:
                print("No message received within timeout")
                return None
            if expected_signal and msg.arbitration_id != expected_signal:
                print(f"Unexpected signal: {msg.arbitration_id}")
                return None
            return msg.data
        except Exception as e:
            print(f"CAN receive failed: {e}")
            return None

    @classmethod
    def execute_command(cls, command: Enum, *args, **kwargs) -> Any:
        """执行CAN命令"""
        if not cls.is_connected():
            raise ConnectionError("CAN bus not connected")
            
        if command not in cls._COMMAND_MAP:
            raise ValueError(f"Command {command.value} not supported")
            
        try:
            can_id = int(cls._COMMAND_MAP[command], 16)
            data = []
            for arg in args:
                if isinstance(arg, (list, tuple)):
                    data.extend(arg)
                else:
                    data.append(arg)
                    
            msg = can.Message(
                arbitration_id=can_id,
                data=data,
                is_extended_id=False
            )
            cls._bus.send(msg)
            
            if kwargs.get('wait_response', True):
                return cls._bus.recv(timeout=1.0)
                
        except Exception as e:
            raise RuntimeError(f"CAN communication error: {e}")