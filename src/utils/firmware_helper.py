import os
import sys
import subprocess
import requests
import tempfile
import threading
import socket
import intelhex
from urllib.parse import urlparse
from utils.resource_loader import ResourceLoader
import io
from contextlib import redirect_stdout, redirect_stderr

# 错误信息常量
ERROR_MESSAGES = {
    "network_error": "Network connection error. Please check your network settings.",
    "dependency_error": "Failed to install dependencies. Please check your network or install them manually.",
    "failed_fetch_firmware": "Failed to fetch firmware. Please check your network connection or repository address.",
    "update_failed": "Firmware update failed.",
    "unknown_error": "An unknown error occurred.",
    "update_success": "Firmware update successful."
}


class FirmwareHelper:
    def __init__(self, log_callback=None, progress_callback=None):
        """
        初始化固件助手
        
        Args:
            log_callback: 日志回调函数，用于更新UI日志
            progress_callback: 进度回调函数，用于更新UI进度
        """
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.operating_system = self._get_operating_system()
        self.proxies = None
        self.disconnected = False
        self.default_remote = "https://api.github.com/repos/NoManRobotics/minima-firmware/releases/latest"

    def _get_operating_system(self):
        """确定当前操作系统"""
        if sys.platform.startswith('win'):
            return 'Windows'
        elif sys.platform.startswith('linux'):
            return 'Linux'
        elif sys.platform.startswith('darwin'):
            return 'Darwin'
        else:
            return 'Unknown'

    def log_message(self, message):
        """记录日志消息"""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def update_progress(self, percentage):
        """更新进度"""
        if self.progress_callback:
            self.progress_callback(percentage)

    def diagnose_network(self, target_url="https://api.github.com", timeout=5):
        """
        诊断网络连接，检查目标URL是否可达，必要时设置代理
        
        Args:
            target_url: 要测试的目标URL
            timeout: 连接超时时间（秒）
            
        Returns:
            (bool, dict): 连接是否成功，诊断信息
        """
        result = {
            "success": False,
            "dns_resolved": False, 
            "connection_established": False,
            "http_response": None,
            "error": None,
            "proxies_used": None
        }
        
        try:
            self.log_message(f"正在诊断网络连接到 {target_url}...")
            
            # 解析URL获取主机名
            parsed_url = urlparse(target_url)
            hostname = parsed_url.netloc
            
            # 测试DNS解析
            try:
                ip_address = socket.gethostbyname(hostname)
                self.log_message(f"DNS解析成功: {hostname} -> {ip_address}")
                result["dns_resolved"] = True
            except socket.gaierror as dns_error:
                self.log_message(f"DNS解析失败: {str(dns_error)}")
                result["error"] = f"DNS解析失败: {str(dns_error)}"
                
            # 尝试直接连接
            try:
                test_response = requests.get(target_url, timeout=timeout)
                test_response.raise_for_status()
                self.log_message(f"网络连接正常，HTTP状态码: {test_response.status_code}")
                result["connection_established"] = True
                result["http_response"] = test_response.status_code
                result["success"] = True
                return result["success"], result
            except requests.exceptions.RequestException as e:
                self.log_message(f"直接连接失败: {str(e)}")
                result["error"] = str(e)
            
            # 尝试使用系统代理
            self.log_message("尝试使用系统代理设置...")
            try:
                self.proxies = {
                    'http': os.environ.get('HTTP_PROXY'),
                    'https': os.environ.get('HTTPS_PROXY')
                }
                
                if any(self.proxies.values()):
                    result["proxies_used"] = self.proxies
                    self.log_message(f"使用系统代理: {self.proxies}")
                    test_response = requests.get(target_url, proxies=self.proxies, timeout=timeout)
                    test_response.raise_for_status()
                    self.log_message("使用代理连接成功")
                    result["connection_established"] = True
                    result["http_response"] = test_response.status_code
                    result["success"] = True
                    return result["success"], result
                else:
                    self.log_message("未找到系统代理设置")
            except Exception as proxy_error:
                result["error"] = f"系统代理连接失败: {str(proxy_error)}"
                self.log_message(result["error"])
            
            # 所有尝试都失败
            error_msg = (
                "网络连接诊断完成，无法建立连接。请检查：\n"
                f"1. 目标URL ({target_url}) 是否可达\n"
                "2. 网络连接是否正常\n"
                "3. 是否需要配置代理\n"
                "4. 防火墙设置是否阻止了连接\n"
                f"详细错误: {result['error']}"
            )
            self.log_message(error_msg)
            return result["success"], result
            
        except Exception as e:
            result["error"] = f"网络诊断过程中发生未知错误: {str(e)}"
            self.log_message(result["error"])
            return False, result

    def get_esptool_module_path(self):
        """获取esptool模块的路径"""
        esptool_module_path = ResourceLoader.get_thirdparty_path('esptool')
        if not os.path.exists(esptool_module_path):
            raise FileNotFoundError(f"esptool 模块未在路径 {esptool_module_path} 找到，请检查安装")
        return esptool_module_path

    def get_avrdude_path(self):
        """获取avrdude可执行文件的路径"""
        try:
            if self.operating_system == 'Windows':
                # Windows下的avrdude.exe在Windows目录下
                avrdude_path = ResourceLoader.get_thirdparty_path(os.path.join('avrdude', 'Windows', 'avrdude.exe'))
            elif self.operating_system == 'Linux':
                # Linux下avrdude在Linux/bin目录中
                avrdude_path = ResourceLoader.get_thirdparty_path(os.path.join('avrdude', 'Linux', 'bin', 'avrdude'))
            elif self.operating_system == 'Darwin':  # macOS
                # macOS下avrdude在MacOS/bin目录中
                avrdude_path = ResourceLoader.get_thirdparty_path(os.path.join('avrdude', 'MacOS', 'bin', 'avrdude'))
            else:
                raise Exception(f"不支持的操作系统: {self.operating_system}")

            self.log_message(f"找到 avrdude 路径: {avrdude_path}")
            
            # 检查文件权限
            if not os.access(avrdude_path, os.X_OK):
                self.log_message("avrdude 文件不可执行，尝试添加执行权限...")
                try:
                    os.chmod(avrdude_path, 0o755)  # 添加执行权限
                    self.log_message("成功添加 avrdude 执行权限")
                except Exception as e:
                    self.log_message(f"无法添加 avrdude 执行权限: {str(e)}")
                    
            return avrdude_path
        except FileNotFoundError as e:
            self.log_message(f"avrdude 未找到: {str(e)}")
            raise FileNotFoundError(f"avrdude 未找到，请检查安装: {str(e)}")

    def get_avrdude_conf_path(self):
        """获取avrdude.conf的路径"""
        try:
            if self.operating_system == 'Windows':
                # Windows下的配置文件在Windows目录下
                conf_path = ResourceLoader.get_thirdparty_path(os.path.join('avrdude', 'Windows', 'avrdude.conf'))
            elif self.operating_system == 'Linux':
                # Linux下配置文件在Linux/etc目录中
                conf_path = ResourceLoader.get_thirdparty_path(os.path.join('avrdude', 'Linux', 'etc', 'avrdude.conf'))
            elif self.operating_system == 'Darwin':  # macOS
                # macOS下配置文件在MacOS/etc目录中
                conf_path = ResourceLoader.get_thirdparty_path(os.path.join('avrdude', 'MacOS', 'etc', 'avrdude.conf'))
            else:
                raise Exception(f"不支持的操作系统: {self.operating_system}")

            self.log_message(f"找到 avrdude.conf 路径: {conf_path}")
            
            if not os.path.exists(conf_path):
                raise FileNotFoundError(f"avrdude.conf 不存在: {conf_path}")
                
            return conf_path
        except FileNotFoundError as e:
            self.log_message(f"avrdude.conf 未找到: {str(e)}")
            raise FileNotFoundError(f"avrdude.conf 未找到，请检查安装: {str(e)}")

    def get_arduino_mcu(self, arduino_model):
        """根据Arduino型号返回对应的MCU"""
        model_to_mcu = {
            "Uno": "atmega328p",
            "Mega": "atmega2560",
            "Nano": "atmega328p",
            "Leonardo": "atmega32u4"
        }
        return model_to_mcu.get(arduino_model, "atmega328p")

    def disconnect_device(self, protocol_instance=None):
        """断开设备连接"""
        if not self.disconnected and protocol_instance:
            try:
                protocol_instance.disconnect()
                self.disconnected = True
                self.log_message("设备已断开连接，准备刷新固件")
            except Exception as e:
                self.log_message(f"断开设备时出错: {str(e)}")

    def reconnect_device(self, protocol_instance=None, port=None):
        """重新连接设备"""
        if self.disconnected and protocol_instance and port:
            try:
                protocol_instance.connect(port)
                self.disconnected = False
                self.log_message("设备重新连接成功")
            except Exception as e:
                self.log_message(f"重新连接设备时出错: {str(e)}")

    def flash_esp32(self, port, firmware_file, baud_rate, flash_mode, flash_freq, flash_size="detect"):
        """
        刷新ESP32固件
        
        Args:
            port: 串口
            firmware_file: 固件文件路径
            baud_rate: 波特率
            flash_mode: 闪存模式
            flash_freq: 闪存频率
            flash_size: 闪存大小，默认为"detect"
        """
        try:
            # 添加esptool模块到Python路径
            esptool_module_path = self.get_esptool_module_path()
            if esptool_module_path not in sys.path:
                sys.path.insert(0, esptool_module_path)
            
            # 导入esptool模块
            import esptool
            
            # 构建esptool参数
            argv = [
                "--chip", "esp32",
                "--port", port,
                "--baud", str(baud_rate),
                "--before", "default_reset",
                "--after", "hard_reset",
                "write_flash",
                "-z",
                "--flash_mode", flash_mode.lower(),
                "--flash_freq", flash_freq,
                "--flash_size", flash_size,
                "0x10000", firmware_file
            ]
            
            self.log_message(f"使用esptool模块执行: {' '.join(argv)}")
            
            # 捕获输出并解析进度
            return self._execute_esptool(argv)
            
        except Exception as e:
            self.log_message(f"ESP32刷新失败: {str(e)}")
            return False

    def flash_arduino(self, port, firmware_file, arduino_model, baud_rate, programmer="arduino"):
        """
        刷新Arduino固件
        
        Args:
            port: 串口
            firmware_file: 固件文件路径
            arduino_model: Arduino型号
            baud_rate: 波特率
            programmer: 程序员类型，默认为"arduino"
        """
        try:
            avrdude_path = self.get_avrdude_path()
            mcu = self.get_arduino_mcu(arduino_model)
            
            command = [
                avrdude_path,
                "-C", self.get_avrdude_conf_path(),
                "-v", "-p", mcu,
                "-c", programmer,
                "-P", port,
                "-b", str(baud_rate),
                "-D",
                "-U", f"flash:w:{firmware_file}:i"
            ]
            
            self.log_message(f"执行命令: {' '.join(command)}")
            return self._execute_avrdude_command(command)
            
        except Exception as e:
            self.log_message(f"Arduino刷新失败: {str(e)}")
            return False

    def _execute_esptool(self, argv):
        """使用esptool模块执行命令"""
        try:
            # 导入esptool模块
            import esptool
            
            # 创建自定义输出捕获类
            class ProgressCapture:
                def __init__(self, log_callback, progress_callback):
                    self.log_callback = log_callback
                    self.progress_callback = progress_callback
                    self.buffer = ""
                
                def write(self, text):
                    self.buffer += text
                    lines = self.buffer.split('\n')
                    self.buffer = lines[-1]  # 保留最后一个不完整的行
                    
                    for line in lines[:-1]:
                        line = line.strip()
                        if line:
                            self.log_callback(line)
                            
                            # 解析进度信息
                            if "Writing at" in line and "%" in line:
                                try:
                                    percentage = int(line.split("(")[1].split("%")[0].strip())
                                    self.progress_callback(percentage)
                                except (IndexError, ValueError):
                                    pass
                
                def flush(self):
                    if self.buffer.strip():
                        self.log_callback(self.buffer.strip())
                        self.buffer = ""
            
            # 创建输出捕获对象
            capture = ProgressCapture(self.log_message, self.update_progress)
            
            # 重定向stdout和stderr到我们的捕获对象
            with redirect_stdout(capture), redirect_stderr(capture):
                try:
                    esptool.main(argv)
                    self.update_progress(100)
                    self.log_message("esptool执行成功")
                    return True
                except SystemExit as e:
                    if e.code == 0:
                        self.update_progress(100)
                        self.log_message("esptool执行成功")
                        return True
                    else:
                        self.log_message(f"esptool执行失败，退出码: {e.code}")
                        return False
                        
        except Exception as e:
            self.log_message(f"执行esptool时出错: {str(e)}")
            return False

    def _execute_avrdude_command(self, command):
        """执行avrdude命令并监控输出"""
        try:
            process = subprocess.Popen(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW if self.operating_system == 'Windows' else 0
            )
            
            for line in process.stdout:
                line = line.strip()
                self.log_message(line)
                
                # 解析avrdude进度信息
                if "#" in line and "%" in line:
                    try:
                        # avrdude输出格式类似: Writing | ######################## | 100% 0.50s
                        parts = line.split("|")
                        if len(parts) >= 3:
                            percent_part = parts[2].strip()
                            if "%" in percent_part:
                                percentage = int(percent_part.split("%")[0].strip())
                                self.update_progress(percentage)
                    except (IndexError, ValueError) as e:
                        self.log_message(f"解析avrdude进度失败: {str(e)}")
            
            process.wait()
            
            if process.returncode == 0:
                self.log_message("avrdude命令执行成功")
                self.update_progress(100)
                return True
            else:
                self.log_message(f"avrdude命令执行失败，返回码: {process.returncode}")
                return False
                
        except Exception as e:
            self.log_message(f"执行avrdude命令时出错: {str(e)}")
            return False


    def update_firmware(self, port, board_type, params, firmware_file, protocol_instance=None):
        """
        更新固件的主函数
        
        Args:
            port: 串口
            board_type: 板类型 (ESP32 或 Arduino)
            params: 参数字典，包含板特定的参数
            firmware_file: 固件文件路径或URL
            protocol_instance: 可选，协议实例用于断开连接
        
        Returns:
            (bool, str): 成功状态和消息
        """
        temp_file_path = None
        try:
            self.update_progress(0)
                        
            # 如果firmware_file是URL，则下载文件
            if firmware_file.startswith('http'):
                self.log_message(f"正在下载固件: {firmware_file}")
                try:
                    # 使用之前测试成功的代理设置
                    request_kwargs = {'timeout': 30}
                    if self.proxies:
                        request_kwargs['proxies'] = self.proxies
                    
                    firmware_response = requests.get(firmware_file, **request_kwargs)
                    firmware_response.raise_for_status()
                    
                    # 根据URL确定文件扩展名
                    file_extension = '.bin' if firmware_file.endswith('.bin') else '.hex'
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                        temp_file.write(firmware_response.content)
                        temp_file_path = temp_file.name
                        firmware_file = temp_file_path
                        self.log_message(f"固件已下载到临时文件: {temp_file_path}")
                        
                except requests.exceptions.RequestException as e:
                    error_msg = f"下载固件失败: {str(e)}"
                    self.log_message(error_msg)
                    return False, error_msg
            
            # 断开设备连接
            self.disconnect_device(protocol_instance)
            
            # 根据板类型刷新固件
            if board_type == "ESP32":
                result = self.flash_esp32(
                    port=port,
                    firmware_file=firmware_file,
                    baud_rate=params.get("baud_rate", "115200"),
                    flash_mode=params.get("flash_mode", "QIO"),
                    flash_freq=params.get("flash_freq", "40m"),
                    flash_size=params.get("flash_size", "detect")
                )
            else:  # Arduino
                result = self.flash_arduino(
                    port=port,
                    firmware_file=firmware_file,
                    arduino_model=params.get("arduino_model", "Uno"),
                    baud_rate=params.get("baud_rate", "115200"),
                    programmer=params.get("programmer", "arduino")
                )
            
            # 尝试重新连接设备
            self.reconnect_device(protocol_instance, port)
            
            if result:
                return True, ERROR_MESSAGES["update_success"]
            else:
                return False, ERROR_MESSAGES["update_failed"]
                
        except Exception as e:
            self.log_message(f"更新固件时出错: {str(e)}")
            # 尝试重新连接设备
            self.reconnect_device(protocol_instance, port)
            return False, f"{ERROR_MESSAGES['unknown_error']}: {str(e)}"
        finally:
            # 清理临时文件
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                    self.log_message("临时文件已清理")
                except Exception as e:
                    self.log_message(f"清理临时文件失败: {str(e)}")

    def update_firmware_async(self, port, board_type, params, firmware_file, protocol_instance=None, callback=None):
        """
        异步更新固件
        
        Args:
            port: 串口
            board_type: 板类型 (ESP32 或 Arduino)
            params: 参数字典，包含板特定的参数
            firmware_file: 固件文件路径或URL
            protocol_instance: 可选，协议实例用于断开连接
            callback: 完成后的回调函数，接收(success, message)参数
        """
        def _update_thread():
            success, message = self.update_firmware(port, board_type, params, firmware_file, protocol_instance)
            if callback:
                callback(success, message)
        
        thread = threading.Thread(target=_update_thread)
        thread.daemon = True
        thread.start()
        return thread

    def fetch_remote_firmware(self, remote_url=None, timeout=10):
        """
        获取远程固件列表
        
        Args:
            remote_url: 可选，远程URL，如果不提供则使用默认URL
            timeout: 超时时间，默认10秒
            
        Returns:
            (bool, list): 成功状态和固件列表
            固件列表格式: [{'name': str, 'download_url': str, 'size': int}, ...]
        """
        try:
            if not remote_url:
                remote_url = self.default_remote
                
            self.log_message(f"正在获取远程固件列表: {remote_url}")
            
            # 使用之前测试成功的代理设置
            request_kwargs = {'timeout': timeout}
            if self.proxies:
                request_kwargs['proxies'] = self.proxies
            
            response = requests.get(remote_url, **request_kwargs)
            response.raise_for_status()
            
            release_data = response.json()
            assets = release_data.get('assets', [])
            
            # 过滤出固件文件（.bin, .hex文件）
            firmware_files = []
            for asset in assets:
                name = asset['name']
                if name.endswith('.bin') or name.endswith('.hex'):
                    firmware_files.append({
                        'name': name,
                        'download_url': asset['browser_download_url'],
                        'size': asset['size']
                    })
            
            if firmware_files:
                self.log_message(f"找到 {len(firmware_files)} 个固件文件")
                return True, firmware_files
            else:
                self.log_message("未找到可用的固件文件")
                return False, []
                
        except requests.exceptions.RequestException as e:
            error_msg = f"网络请求失败: {str(e)}"
            self.log_message(error_msg)
            return False, []
        except ValueError as e:
            error_msg = f"解析JSON数据失败: {str(e)}"
            self.log_message(error_msg)
            return False, []
        except Exception as e:
            error_msg = f"获取远程固件时发生未知错误: {str(e)}"
            self.log_message(error_msg)
            return False, []

    def fetch_remote_firmware_async(self, remote_url=None, timeout=10):
        """
        异步获取远程固件列表
        
        Args:
            remote_url: 可选，远程URL，如果不提供则使用默认URL
            timeout: 超时时间，默认10秒
            
        Returns:
            list: 固件下载URL列表，如果失败返回空列表
        """
        success, firmware_list = self.fetch_remote_firmware(remote_url, timeout)
        if success and firmware_list:
            return [fw['download_url'] for fw in firmware_list]
        return [] 