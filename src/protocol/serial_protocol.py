import serial
from enum import Enum
from typing import Any
import time

class SerialCommands(Enum):
    """串口协议支持的命令"""
    # 串口特有的命令
    EXEC           = "EXEC"
    HOME           = "HOME"
    MOVEONCE       = "MOVEONCE"
    RECONCE        = "RECONCE"
    SPDSLOW        = "SPDSLOW"
    SPDNORMAL      = "SPDNORMAL"
    SPDFAST        = "SPDFAST"
    RECSTART       = "RECSTART"
    RECSTOP        = "RECSTOP"
    REP            = "REP"
    REPSTART       = "REPSTART"
    REPSTOP        = "REPSTOP"
    REPPAUSE       = "REPPAUSE"
    POTON          = "POTON"
    POTOFF         = "POTOFF"
    VERC           = "VERC"
    CALIBRATE      = "CALIBRATE"
    TOROS          = "TOROS"
    TOCTR          = "TOCTR"
    TOOLGRIPPER    = "TOOL[GRIPPER]"
    TOOLPENHOLDER  = "TOOL[PEN_HOLDER]"
    TOOLVACUUMPUMP = "TOOL[VACUUM_PUMP]"
    DELAY          = "DELAY"
    RESET_ALARM    = "RESET_ALARM"
    GET_ALARM      = "GET_ALARM"

class SerialProtocol:
    """串口通信协议实现"""
    
    SERIAL_BAUDRATE = 115200
    _serial = None
    port = None
    baudrate = SERIAL_BAUDRATE
    timeout = 1.0

    _COMMAND_MAP = {
        SerialCommands.EXEC: "EXEC",
        SerialCommands.HOME: "HOME",
        SerialCommands.MOVEONCE: "MOVEONCE",
        SerialCommands.RECONCE: "RECONCE",
        SerialCommands.SPDSLOW: "SPDSLOW",
        SerialCommands.SPDNORMAL: "SPDNORMAL",
        SerialCommands.SPDFAST: "SPDFAST",
        SerialCommands.RECSTART: "RECSTART",
        SerialCommands.RECSTOP: "RECSTOP",
        SerialCommands.REP: "REP",
        SerialCommands.REPSTART: "REPSTART",
        SerialCommands.REPSTOP: "REPSTOP",
        SerialCommands.REPPAUSE: "REPPAUSE",
        SerialCommands.POTON: "POTON",
        SerialCommands.POTOFF: "POTOFF",
        SerialCommands.VERC: "VERC",
        SerialCommands.CALIBRATE: "CALIBRATE",
        SerialCommands.TOROS: "TOROS",
        SerialCommands.TOCTR: "TOCTR",
        SerialCommands.TOOLGRIPPER: "TOOL[GRIPPER]",
        SerialCommands.TOOLPENHOLDER: "TOOL[PEN_HOLDER]",
        SerialCommands.TOOLVACUUMPUMP: "TOOL[VACUUM_PUMP]",
        SerialCommands.DELAY: "DELAY",
        SerialCommands.RESET_ALARM: "RESET_ALARM",
        SerialCommands.GET_ALARM: "GET_ALARM"
    }

    @classmethod
    def connect(cls, port: str, baudrate: int = 115200) -> bool:
        """建立串口连接"""
        cls.port = port
        cls.baudrate = baudrate
        try:
            cls._serial = serial.Serial(
                port=cls.port,
                baudrate=cls.baudrate,
                timeout=cls.timeout
            )
            cls._serial.setDTR(False)
            cls._serial.setRTS(False)
            return True
        except Exception as e:
            print(f"Serial connection error: {e}")
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
                print(f"Serial disconnection error: {e}")
        return False

    @classmethod
    def send(cls, data, sleep_time=0.005) -> bool:
        """向串口写入数据"""
        try:
            if cls._serial and cls._serial.is_open:
                if isinstance(data, str):
                    data = data.encode()
                cls._serial.write(data)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                return True
            return False
        except Exception as e:
            print(f"Serial write error: {e}")
            return False

    @classmethod
    def receive(cls, timeout=5, expected_signal=None):
        """接收串口数据并返回"""
        if not cls._serial or not cls._serial.is_open:
            return [], False
            
        buffer = ""
        received_lines = []
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if cls._serial.in_waiting:
                buffer += cls._serial.read(cls._serial.in_waiting).decode()
                lines = buffer.split('\n')
                buffer = lines.pop()  # 保留不完整的行在缓冲区
                
                for line in lines:
                    line = line.strip()
                    if line:  # 忽略空行
                        received_lines.append(line)
                        
                        if expected_signal and line == expected_signal:
                            return received_lines, True
                            
            time.sleep(0.001)
        
        return received_lines, False

    @classmethod
    def clear_serial_buffer(cls):
        """清空串口缓冲区"""
        if cls._serial and cls._serial.is_open:
            cls._serial.reset_input_buffer()
            cls._serial.reset_output_buffer()

    @classmethod
    def is_connected(cls) -> bool:
        return cls._serial is not None and cls._serial.is_open

    @classmethod
    def execute_command(cls, command: Enum, *args, **kwargs) -> Any:
        if not cls.is_connected():
            raise ConnectionError("Serial port not connected")
            
        if command not in cls._COMMAND_MAP:
            raise ValueError(f"Command {command.value} not supported")
            
        cmd_str = f"{cls._COMMAND_MAP[command]}"
        if args:
            cmd_str += "," + ",".join(map(str, args))
        cmd_str += "\n"
        
        try:
            cls._serial.write(cmd_str.encode())
            response = cls._serial.readline().decode().strip()
            return response
        except Exception as e:
            raise RuntimeError(f"Serial communication error: {e}") 