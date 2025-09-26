import os
from threading import Thread
import tkinter as tk
import serial.tools.list_ports
import customtkinter as ctk
from tkinter import messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
from PIL import Image

from utils.tooltip import ToolTip
from utils.config import Config
from utils.resource_loader import ResourceLoader
from utils.circular_progress import CircularProgress
from utils.firmware_helper import FirmwareHelper
from protocol.serial_protocol import SerialProtocol, SerialCommands
from protocol.can_protocol import CanProtocol, CANCommands
from noman.profile_manager import ProfileManager

class FirmwareFrame(ctk.CTkFrame):
    def __init__(self, master, app=None):
        super().__init__(master)
        self.app = app
        self.current_profile = ProfileManager.current_profile
        self.protocol_class = SerialProtocol if self.current_profile["robot_type"] == "PWM/I2C" else CanProtocol

        self.selected_file = None
        self.refresh_icon_path = ResourceLoader.get_asset_path(os.path.join("icons", "refresh_white.png"))
        self.refresh_icon = ctk.CTkImage(Image.open(self.refresh_icon_path).convert("RGBA"), size=(20, 20))

        self.question_icon_path = ResourceLoader.get_asset_path(os.path.join("icons", "question_white.png"))
        self.question_icon = ctk.CTkImage(Image.open(self.question_icon_path).convert("RGBA"), size=(15, 15))

        # 初始化FirmwareHelper实例 - 稍后设置progress_callback
        self.firmware_helper = FirmwareHelper(
            log_callback=self.log_message,
            progress_callback=None  # 将在setup_firmware_frame中设置
        )
        
        # 存储远程固件信息
        self.remote_firmware_list = []
        self.selected_firmware_file = None

        self.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(0, weight=1)
        
        self.setup_banner()
        self.setup_indicators()
        self.setup_connection_frame()
        self.setup_param_frame()
        self.setup_firmware_frame()
        self.setup_terminal()

    def setup_banner(self):
        # 添加标题框架
        self.title_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.title_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10,0))
        self.title_frame.grid_columnconfigure(0, weight=1)
        
        # 添加标题标签
        self.title_label = ctk.CTkLabel(self.title_frame, text=Config.current_lang["firmware_update"], 
                                   font=("Arial", 16))
        self.title_label.grid(row=0, column=0, padx=10, pady=(8,0), sticky="w")
        
        # 添加分隔线
        self.separator = ctk.CTkFrame(self.title_frame, height=2, width=180, fg_color="black") 
        self.separator.grid(row=1, column=0, sticky="w", padx=10, pady=(5,10))

    def setup_connection_frame(self):
        self.connection_frame = ctk.CTkFrame(self, fg_color="#B3B3B3")
        self.connection_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        self.network_label = ctk.CTkLabel(self.connection_frame, text=Config.current_lang["remote"], anchor='w')
        self.network_label.pack(side="top", padx=10, pady=(10,5), anchor='w')
        
        # 远程地址测试框架
        self.remote_test_frame = ctk.CTkFrame(self.connection_frame, fg_color="transparent")
        self.remote_test_frame.pack(side="top", padx=15, pady=(10,0), anchor='w')
        
        self.remote_address_label = ctk.CTkLabel(self.remote_test_frame, text=Config.current_lang["network_diagnosis"] + ":", anchor='w', width=120)
        self.remote_address_label.pack(side="left", padx=5)
        
        # 使用FirmwareHelper的default_remote作为默认值
        default_remote = getattr(self.firmware_helper, 'default_remote', 
                                'https://api.github.com/repos/NoManRobotics/minima-firmware/releases/latest')
        self.remote_address_var = ctk.StringVar(value=default_remote)
        self.remote_address_entry = ctk.CTkEntry(self.remote_test_frame, textvariable=self.remote_address_var, width=300)
        self.remote_address_entry.pack(side="left", padx=(0,5))
        
        # 测试按钮
        self.test_network_button = ctk.CTkButton(self.remote_test_frame, text=Config.current_lang["check"], 
                                               command=self.test_network_connection, 
                                               hover_color="#41d054",
                                               width=100)
        self.test_network_button.pack(side="left", padx=(5,0))

        # 远程固件获取框架
        self.remote_firmware_frame = ctk.CTkFrame(self.connection_frame, fg_color="transparent")
        self.remote_firmware_frame.pack(side="top", padx=15, pady=10, anchor='w')
        
        # 选择固件标签
        self.select_firmware_label = ctk.CTkLabel(self.remote_firmware_frame, text=Config.current_lang["select_firmware"], anchor='w', width=120)
        self.select_firmware_label.pack(side="left", padx=5)
        
        # 远程固件选择下拉菜单
        self.remote_firmware_var = ctk.StringVar(value="Select firmware...")
        self.remote_firmware_dropdown = ctk.CTkOptionMenu(self.remote_firmware_frame, 
                                                         variable=self.remote_firmware_var,
                                                         values=["No firmware available"],
                                                         command=self.on_firmware_selection,
                                                         state="disabled",
                                                         width=300)
        self.remote_firmware_dropdown.pack(side="left", padx=(0,10))
        
        # Fetch Remote按钮
        self.fetch_remote_button = ctk.CTkButton(self.remote_firmware_frame, text=Config.current_lang["fetch_remote"], 
                                               command=self.fetch_remote_firmware, 
                                               hover_color="#41d054",
                                               width=100)
        self.fetch_remote_button.pack(side="left", padx=(0,0))

    def setup_param_frame(self):
        self.param_frame = ctk.CTkFrame(self, fg_color="#B3B3B3")
        self.param_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        self.param_frame.grid_columnconfigure(0, weight=1)
        self.param_frame.grid_rowconfigure(0, weight=1)

        # 创建 tabview
        self.board_tabview = ctk.CTkTabview(self.param_frame, fg_color="transparent", anchor="w")
        self.board_tabview.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        # 添加标签页
        self.esp32_tab = self.board_tabview.add("ESP32")
        self.arduino_tab = self.board_tabview.add("Arduino")

        # ESP32 参数框架
        self.esp32_frame = ctk.CTkFrame(self.esp32_tab, fg_color="transparent")
        self.esp32_frame.pack(fill="both", expand=True, pady=10)

        # 波特率
        self.baud_rate_label = ctk.CTkLabel(self.esp32_frame, text=Config.current_lang["baud_rate"])
        self.baud_rate_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.baud_rate_var = ctk.StringVar(value="115200")
        self.baud_rate_options = ["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"]
        self.baud_rate_menu = ctk.CTkOptionMenu(self.esp32_frame, variable=self.baud_rate_var, values=self.baud_rate_options, width=120)
        self.baud_rate_menu.grid(row=1, column=1, padx=(5, 10), pady=5, sticky="w")

        # 闪存模式
        self.flash_mode_label = ctk.CTkLabel(self.esp32_frame, text=Config.current_lang["flash_mode"])
        self.flash_mode_label.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.flash_mode_var = ctk.StringVar(value="QIO")
        self.flash_mode_options = ["QIO", "QOUT", "DIO", "DOUT"]
        self.flash_mode_menu = ctk.CTkOptionMenu(self.esp32_frame, variable=self.flash_mode_var, values=self.flash_mode_options, width=120)
        self.flash_mode_menu.grid(row=2, column=1, padx=(5, 10), pady=5, sticky="w")

        # 闪存频率
        self.flash_freq_label = ctk.CTkLabel(self.esp32_frame, text=Config.current_lang["flash_frequency"])
        self.flash_freq_label.grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.flash_freq_var = ctk.StringVar(value="40m")
        self.flash_freq_options = ["20m", "26m", "40m", "80m"]
        self.flash_freq_menu = ctk.CTkOptionMenu(self.esp32_frame, variable=self.flash_freq_var, values=self.flash_freq_options, width=120)
        self.flash_freq_menu.grid(row=3, column=1, padx=(5, 10), pady=5, sticky="w")

        # 闪存大小
        self.flash_size_label = ctk.CTkLabel(self.esp32_frame, text=Config.current_lang.get("flash_size", "Flash Size"))
        self.flash_size_label.grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.flash_size_var = ctk.StringVar(value="detect")
        self.flash_size_options = ["detect", "1MB", "2MB", "4MB", "8MB", "16MB"]
        self.flash_size_menu = ctk.CTkOptionMenu(self.esp32_frame, variable=self.flash_size_var, values=self.flash_size_options, width=120)
        self.flash_size_menu.grid(row=4, column=1, padx=(5, 10), pady=5, sticky="w")

        # Arduino 参数框架
        self.arduino_frame = ctk.CTkFrame(self.arduino_tab, fg_color="transparent")
        self.arduino_frame.pack(fill="both", expand=True, pady=10)

        # Arduino型号
        self.arduino_model_label = ctk.CTkLabel(self.arduino_frame, text=Config.current_lang["arduino_model"])
        self.arduino_model_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.arduino_model_var = ctk.StringVar(value="Uno")
        self.arduino_model_options = ["Uno", "Mega", "Nano", "Leonardo"]
        self.arduino_model_menu = ctk.CTkOptionMenu(self.arduino_frame, variable=self.arduino_model_var, values=self.arduino_model_options, width=120)
        self.arduino_model_menu.grid(row=1, column=1, padx=(5, 10), pady=5, sticky="w")

        # Arduino波特率
        self.arduino_baud_rate_label = ctk.CTkLabel(self.arduino_frame, text=Config.current_lang["baud_rate"])
        self.arduino_baud_rate_label.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.arduino_baud_rate_var = ctk.StringVar(value="115200")
        self.arduino_baud_rate_options = ["9600", "19200", "38400", "57600", "115200"]
        self.arduino_baud_rate_menu = ctk.CTkOptionMenu(self.arduino_frame, variable=self.arduino_baud_rate_var, values=self.arduino_baud_rate_options, width=120)
        self.arduino_baud_rate_menu.grid(row=2, column=1, padx=(5, 10), pady=5, sticky="w")

        # Arduino编程器类型
        self.programmer_label = ctk.CTkLabel(self.arduino_frame, text=Config.current_lang.get("programmer", "Programmer"))
        self.programmer_label.grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.programmer_var = ctk.StringVar(value="arduino")
        self.programmer_options = ["arduino", "usbasp", "stk500", "avrisp"]
        self.programmer_menu = ctk.CTkOptionMenu(self.arduino_frame, variable=self.programmer_var, values=self.programmer_options, width=120)
        self.programmer_menu.grid(row=3, column=1, padx=(5, 10), pady=5, sticky="w")

        # 设置默认选中的标签页
        self.board_tabview.set("ESP32")

        # 确认按钮
        self.update_button = ctk.CTkButton(self.param_frame, text=Config.current_lang["confirm"], command=self.update_params, width=150, hover_color="#41d054")
        self.update_button.grid(row=1, column=0, padx=(10, 30), pady=(0, 10), sticky="e")

    def setup_firmware_frame(self):
        self.firmware_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.firmware_frame.grid(row=5, column=0, padx=20, pady=10, sticky="ew")
        self.firmware_frame.grid_columnconfigure(1, weight=1)  # 让第二列可以扩展
        
        self.progress_frame = ctk.CTkFrame(self.firmware_frame, fg_color="transparent")
        self.progress_frame.grid(row=0, column=0, sticky="w")

        # CircularProgress
        self.progress_circle = CircularProgress(
            self.progress_frame,
            size=120,
            bg_color='#CCCCCC',  # 背景圆环颜色
            fg_color='#41d054',  # 进度条颜色
            text_color='black'   # 文字颜色
        )
        self.progress_circle.pack(padx=5)
        self.progress_circle.set(0)
        
        # 现在设置FirmwareHelper的进度回调
        self.firmware_helper.progress_callback = self.progress_circle.set

        self.updater_frame = ctk.CTkFrame(self.firmware_frame, fg_color="#B3B3B3")
        self.updater_frame.grid(row=0, column=1, padx=(30,0), pady=10, sticky="nsew")
        self.updater_frame.grid_columnconfigure(0, weight=1)  # 让自定义固件更新部分可以扩展
        self.updater_frame.grid_columnconfigure(1, weight=0)  # 固定固件更新按钮的宽度

        # 添加更新标题
        self.update_label = ctk.CTkLabel(self.updater_frame, text=Config.current_lang["upload"], anchor='w')
        self.update_label.grid(row=0, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        self.custom_updater_frame = ctk.CTkFrame(self.updater_frame, fg_color="transparent")
        self.custom_updater_frame.grid(row=1, column=0, padx=(10,10), pady=10, sticky="nsew")
        self.custom_updater_frame.grid_columnconfigure(0, weight=1)  # 让文件选择框可以扩展

        self.firmware_selection_frame = ctk.CTkFrame(self.custom_updater_frame, fg_color="transparent")
        self.firmware_selection_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.firmware_selection_frame.grid_columnconfigure(0, weight=1)  # 让文件选择输入框可以扩展

        self.selected_file_entry = ctk.CTkEntry(self.firmware_selection_frame)
        self.selected_file_entry.grid(row=0, column=0, padx=(5, 5), sticky="ew")
        self.selected_file_entry.configure(state="readonly")

        self.select_firmware_button = ctk.CTkButton(self.firmware_selection_frame, text="...", width=30, command=self.select_firmware_file)
        self.select_firmware_button.grid(row=0, column=1)

        self.update_custom_firmware_button = ctk.CTkButton(self.custom_updater_frame, text=Config.current_lang["update_custom_firmware"], command=self.update_custom_firmware, hover_color="#41d054")
        self.update_custom_firmware_button.grid(row=1, column=0, padx=(10, 7), pady=5, sticky="ew")

        self.fixed_updater_frame = ctk.CTkFrame(self.updater_frame, fg_color="#B3B3B3")
        self.fixed_updater_frame.grid(row=1, column=1, padx=(10, 20), pady=10, sticky="nsew")

        self.update_firmware_button = ctk.CTkButton(self.fixed_updater_frame, text=Config.current_lang["update_firmware"], command=self.update_firmware, width=180, height=65, hover_color="#41d054")
        self.update_firmware_button.pack(expand=True, padx=10, pady=(5,10))
        # 初始状态下禁用所有固件更新相关的控件
        self.disable_firmware_controls()

    def disable_firmware_controls(self):
        self.select_firmware_button.configure(state=ctk.DISABLED)
        self.update_custom_firmware_button.configure(state=ctk.DISABLED)
        self.update_firmware_button.configure(state=ctk.DISABLED)

    def enable_firmware_controls(self):
        self.select_firmware_button.configure(state=ctk.NORMAL)
        self.update_custom_firmware_button.configure(state=ctk.NORMAL)
        self.update_firmware_button.configure(state=ctk.NORMAL)

    def setup_indicators(self):
        self.indicator_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.serial_indicator = self.create_indicator(2)
        self.param_indicator = self.create_indicator(4)

    def create_indicator(self, row):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=row, column=0, padx=10)
        
        indicator1 = ctk.CTkButton(frame, text="", width=6, height=6, 
                                  corner_radius=3, fg_color="grey", 
                                             hover_color="grey", border_width=0)
        indicator2 = ctk.CTkButton(frame, text="", width=6, height=6, 
                                  corner_radius=3, fg_color="grey", 
                                  hover_color="grey", border_width=0)

        indicator1.configure(state="disabled")
        indicator1.pack(pady=(3, 1))
        indicator2.configure(state="disabled")
        indicator2.pack(pady=(3, 1))
        
        return indicator1, indicator2

    def update_indicator(self, indicators, color):
        indicator1, indicator2 = indicators
        indicator1.configure(fg_color=color)
        indicator2.configure(fg_color=color)



    def enable_frame(self, frame):
        for child in frame.winfo_children():
            child.configure(state='normal')

    def disable_frame(self, frame):
        for child in frame.winfo_children():
            if isinstance(child, ctk.CTkLabel):
                continue
            child.configure(state='disabled')

    def setup_terminal(self):
        self.command_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.command_frame.grid(row=6, column=0, padx=20, pady=10, sticky="nsew")
        self.log_text = ScrolledText(self.command_frame, state=tk.DISABLED, wrap=tk.WORD, 
                                     background="#000000", foreground="#41d054",
                                     width=50, height=10)
        self.log_text.pack(fill="both", expand=True)

    def enumerate_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def update_params(self):
        current_tab = self.board_tabview.get()
        if current_tab == "ESP32":
            self.baud_rate = self.baud_rate_var.get()
            self.flash_mode = self.flash_mode_var.get()
            self.flash_freq = self.flash_freq_var.get()
            self.flash_size = self.flash_size_var.get()
            self.log_message(f"Updating ESP32 parameters: Baud Rate={self.baud_rate}, Flash Mode={self.flash_mode}, Flash Frequency={self.flash_freq}, Flash Size={self.flash_size}")
        else:  # Arduino
            self.arduino_model = self.arduino_model_var.get()
            self.arduino_baud_rate = self.arduino_baud_rate_var.get()
            self.programmer = self.programmer_var.get()
            self.log_message(f"Updating Arduino parameters: Model={self.arduino_model}, Baud Rate={self.arduino_baud_rate}, Programmer={self.programmer}")

        self.update_indicator(self.param_indicator, "#41d054")
        self.enable_firmware_controls()

    def select_firmware_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Firmware Files", "*.bin *.hex")])
        if file_path:
            self.selected_file = file_path
            # 清除远程固件选择，因为用户选择了本地文件
            self.selected_firmware_file = None
            self.selected_file_entry.configure(state="normal")
            self.selected_file_entry.delete(0, tk.END)
            self.selected_file_entry.insert(0, os.path.basename(file_path))
            self.selected_file_entry.configure(state="readonly")
        else:
            self.selected_file = None
            self.selected_file_entry.configure(state="normal")
            self.selected_file_entry.delete(0, tk.END)
            self.selected_file_entry.configure(state="readonly")

    def update_custom_firmware(self):
        if not self.selected_file:
            messagebox.showerror(Config.current_lang["error"], Config.current_lang["no_firmware_selected"])
            return

        self.progress_circle.set(0)
        self.update_custom_firmware_button.configure(state=ctk.DISABLED)

        Thread(target=self._update_custom_firmware, args=(self.protocol_class.port, self.selected_file)).start()

    def _update_custom_firmware(self, port, firmware_file):
        """使用FirmwareHelper更新自定义固件"""
        try:
            self.progress_circle.set(0)
            
            # 准备参数
            board_type = self.board_tabview.get()
            if board_type == "ESP32":
                params = {
                    "baud_rate": self.baud_rate,
                    "flash_mode": self.flash_mode,
                    "flash_freq": self.flash_freq,
                    "flash_size": self.flash_size
                }
            else:  # Arduino
                params = {
                    "arduino_model": self.arduino_model,
                    "baud_rate": self.arduino_baud_rate,
                    "programmer": self.programmer
                }
            
            # 定义完成回调
            def on_update_complete(success, message):
                if success:
                    self.after(0, lambda: messagebox.showinfo(Config.current_lang["success"], message))
                else:
                    self.after(0, lambda: messagebox.showerror(Config.current_lang["error"], message))
                self.after(0, lambda: self.update_custom_firmware_button.configure(state=ctk.NORMAL))
            
            # 使用FirmwareHelper异步更新固件
            self.firmware_helper.update_firmware_async(
                port=port,
                board_type=board_type,
                params=params,
                firmware_file=firmware_file,
                protocol_instance=self.protocol_class,
                callback=on_update_complete
            )
            
        except Exception as e:
            self.log_message(f"启动固件更新失败: {str(e)}")
            self.after(0, lambda: messagebox.showerror(Config.current_lang["error"], f"{Config.current_lang['unknown_error']}: {str(e)}"))
            self.after(0, lambda: self.update_custom_firmware_button.configure(state=ctk.NORMAL))

    def update_firmware(self):
        self.progress_circle.set(0)
        self.update_firmware_button.configure(state=ctk.DISABLED)

        Thread(target=self._update_firmware, args=(self.protocol_class.port,)).start()

    def _update_firmware(self, port):
        """使用FirmwareHelper更新官方固件"""
        try:
            self.progress_circle.set(0)
            
            # 检查是否已选择固件
            if not self.selected_firmware_file:
                self.log_message("请先获取并选择固件")
                self.after(0, lambda: messagebox.showerror(Config.current_lang["error"], "请先获取并选择固件"))
                self.after(0, lambda: self.update_firmware_button.configure(state=ctk.NORMAL))
                return
            
            # 准备参数
            board_type = self.board_tabview.get()
            if board_type == "ESP32":
                params = {
                    "baud_rate": self.baud_rate,
                    "flash_mode": self.flash_mode,
                    "flash_freq": self.flash_freq,
                    "flash_size": self.flash_size
                }
            else:  # Arduino
                params = {
                    "arduino_model": self.arduino_model,
                    "baud_rate": self.arduino_baud_rate,
                    "programmer": self.programmer
                }
            
            # 使用已选择的固件文件
            firmware_file = self.selected_firmware_file
            self.log_message(f"使用选择的固件: {firmware_file}")
            
            # 定义完成回调
            def on_update_complete(success, message):
                if success:
                    self.after(0, lambda: messagebox.showinfo(Config.current_lang["success"], message))
                else:
                    self.after(0, lambda: messagebox.showerror(Config.current_lang["error"], message))
                self.after(0, lambda: self.update_firmware_button.configure(state=ctk.NORMAL))
            
            # 使用FirmwareHelper异步更新固件
            self.firmware_helper.update_firmware_async(
                port=port,
                board_type=board_type,
                params=params,
                firmware_file=firmware_file,
                protocol_instance=self.protocol_class,
                callback=on_update_complete
            )
            
        except Exception as e:
            self.log_message(f"启动固件更新失败: {str(e)}")
            self.after(0, lambda: messagebox.showerror(Config.current_lang["error"], f"{Config.current_lang['unknown_error']}: {str(e)}"))
            self.after(0, lambda: self.update_firmware_button.configure(state=ctk.NORMAL))

    def load_current_profile(self):
        self.current_profile = ProfileManager.current_profile
        self.protocol_class = SerialProtocol if self.current_profile["robot_type"] == "PWM/I2C" else CanProtocol

    def test_network_connection(self):
        """测试网络连接"""
        target_url = self.remote_address_var.get()
        self.log_message(f"正在测试网络连接到: {target_url}")
        
        # 禁用测试按钮，防止重复点击
        self.test_network_button.configure(state=ctk.DISABLED)
        
        # 创建一个线程来执行网络诊断，防止UI冻结
        def _test_thread():
            try:
                success, result = self.firmware_helper.diagnose_network(target_url=target_url)
                
                if success:
                    self.log_message("网络连接测试成功!")
                    self.log_message(f"HTTP状态码: {result['http_response']}")
                    if result['proxies_used']:
                        self.log_message(f"使用代理: {result['proxies_used']}")
                    # 网络测试成功，serial_indicator变绿
                    self.after(0, lambda: self.update_indicator(self.serial_indicator, "#41d054"))
                else:
                    error_msg = (
                        f"网络连接测试失败: {result['error']}\n"
                        "请检查:\n"
                        f"1. 目标URL ({target_url}) 是否可达\n"
                        "2. 网络连接是否正常\n"
                        "3. 是否需要配置代理"
                    )
                    self.log_message(error_msg)
                    # 网络测试失败，serial_indicator变红
                    self.after(0, lambda: self.update_indicator(self.serial_indicator, "#ff3333"))
            except Exception as e:
                self.log_message(f"测试过程中发生错误: {str(e)}")
                # 发生异常，serial_indicator变红
                self.after(0, lambda: self.update_indicator(self.serial_indicator, "#ff3333"))
            finally:
                # 重新启用测试按钮
                self.after(0, lambda: self.test_network_button.configure(state=ctk.NORMAL))
        
        # 启动测试线程
        Thread(target=_test_thread).start()

    def fetch_remote_firmware(self):
        """获取远程固件列表"""
        target_url = self.remote_address_var.get()
        
        # 禁用按钮，防止重复点击
        self.fetch_remote_button.configure(state=ctk.DISABLED)
        
        def _fetch_thread():
            try:
                # 使用 FirmwareHelper 获取远程固件信息
                success, firmware_list = self.firmware_helper.fetch_remote_firmware(
                    remote_url=target_url,
                    timeout=10
                )
                
                if success and firmware_list:
                    self.remote_firmware_list = firmware_list
                    firmware_names = [f"{fw['name']} ({fw['size']} bytes)" for fw in firmware_list]
                    
                    # 更新UI
                    self.after(0, lambda: self._update_firmware_dropdown(firmware_names))
                else:
                    # 处理失败情况
                    if not success:
                        error_message = ["Failed to fetch firmware"]
                    else:  # success but empty list
                        error_message = ["No firmware files found"]
                    self.after(0, lambda: self._update_firmware_dropdown(error_message))
            except Exception as e:
                self.log_message(f"获取远程固件时发生错误: {str(e)}")
                self.after(0, lambda: self._update_firmware_dropdown(["Error fetching firmware"]))
            finally:
                # 重新启用按钮
                self.after(0, lambda: self.fetch_remote_button.configure(state=ctk.NORMAL))
        
        # 启动获取线程
        Thread(target=_fetch_thread).start()

    def _update_firmware_dropdown(self, firmware_names):
        """更新固件下拉菜单"""
        if firmware_names and not firmware_names[0].startswith(("No firmware", "Failed", "Error")):
            self.remote_firmware_dropdown.configure(values=firmware_names, state="normal")
            self.remote_firmware_var.set(firmware_names[0])
            # 自动选择第一个固件
            self.on_firmware_selection(firmware_names[0])
        else:
            self.remote_firmware_dropdown.configure(values=firmware_names, state="disabled")
            self.remote_firmware_var.set(firmware_names[0] if firmware_names else "No firmware available")
            # 清除选中的固件
            self.selected_firmware_file = None

    def on_firmware_selection(self, selected_firmware):
        """固件选择改变时的回调"""
        if not selected_firmware or selected_firmware.startswith(("No firmware", "Select firmware", "Failed", "Error")):
            self.selected_firmware_file = None
            return
        
        # 从显示名称中提取实际文件名
        firmware_name = selected_firmware.split(' (')[0]
        
        # 查找对应的固件信息
        selected_firmware_info = None
        for fw in self.remote_firmware_list:
            if fw['name'] == firmware_name:
                selected_firmware_info = fw
                break
        
        if selected_firmware_info:
            # 设置选中的固件文件URL
            self.selected_firmware_file = selected_firmware_info['download_url']
            
            # 同时设置为自定义固件更新显示
            self.selected_file = selected_firmware_info['download_url']
            
            self.log_message(f"选择远程固件: {firmware_name}")
            self.log_message(f"下载URL: {selected_firmware_info['download_url']}")
        else:
            self.selected_firmware_file = None
            self.log_message("找不到选中的固件信息")

    def log_message(self, message):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.yview(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def update_texts(self):
        self.title_label.configure(text=Config.current_lang["firmware_update"])
        self.update_button.configure(text=Config.current_lang["confirm"])
        self.update_firmware_button.configure(text=Config.current_lang["update_firmware"])
        self.update_custom_firmware_button.configure(text=Config.current_lang["update_custom_firmware"])
        self.update_label.configure(text=Config.current_lang["upload"])
        
        # 更新网络诊断相关文本
        self.network_label.configure(text=Config.current_lang["remote"])
        self.remote_address_label.configure(text=Config.current_lang["network_diagnosis"] + ":")
        self.test_network_button.configure(text=Config.current_lang["check"])
        self.select_firmware_label.configure(text=Config.current_lang["select_firmware"])
        self.fetch_remote_button.configure(text=Config.current_lang["fetch_remote"])
        
        # 更新 ESP32 框架的文本
        self.baud_rate_label.configure(text=Config.current_lang["baud_rate"])
        self.flash_mode_label.configure(text=Config.current_lang["flash_mode"])
        self.flash_freq_label.configure(text=Config.current_lang["flash_frequency"])
        
        # 更新 Arduino 框架的文本
        self.arduino_model_label.configure(text=Config.current_lang["arduino_model"])
        self.arduino_baud_rate_label.configure(text=Config.current_lang["baud_rate"])
