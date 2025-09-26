import tkinter as tk
import customtkinter as ctk
import sys
import time
import os
import numpy as np
from PIL import Image
from utils.resource_loader import ResourceLoader
from utils.tooltip import ToolTip

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import Config
from utils.speech_recognition_manager import SpeechRecognitionManager
from noman.majordomo.llm_manager import LLMManager
import threading
import tkinter.messagebox as messagebox
import asyncio

class MajordomoDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        
        # get current language configuration
        self.current_lang = Config.get_current_lang()
        
        # load icons
        self.load_icons()
        
        # set window properties
        self.title(self.current_lang["majordomo"])
        self.geometry("600x600")  # increase window size
        self.minsize(600, 600)    # set minimum window size
        self.resizable(True, True)
        
        
        # create manager instance
        self.speech_manager = SpeechRecognitionManager()
        self.recording_thread = None
        self.is_recording = False  # 录音状态标志
        
        # initial hide window
        self.withdraw()
        
        # create LLM manager
        self.llm_manager = LLMManager()
        
        # update message style configuration
        self.message_styles = {
            "user": {
                "bg_color": "transparent",
                "text_color": "black",
                "align": "right"
            },
            "system": {
                "bg_color": "#007AFF",
                "text_color": "white",
                "align": "left"
            }
        }
        
        self.setup_ui()
        
        # set window close behavior
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def load_icons(self):
        """Load all icon images used in the interface"""
        self.voice_icon = self.load_icon("voice_white.png", (20, 20))
        self.pause_icon = self.load_icon("pause_white.png", (15, 15))
        self.question_icon_white = self.load_icon("question_white.png", (15, 15))
        self.refresh_icon = self.load_icon("refresh_white.png", (20, 20))

    def load_icon(self, filename, size):
        """Helper method to load an icon with the given filename and size"""
        path = ResourceLoader.get_asset_path(os.path.join("icons", filename))
        return ctk.CTkImage(Image.open(path).convert("RGBA"), size=size)

    def show(self):
        """显示对话框"""
        # 获取主窗口位置和大小
        main_window_x = self.parent.winfo_rootx()
        main_window_y = self.parent.winfo_rooty()
        main_window_width = self.parent.winfo_width()
        
        # 计算对话框位置
        dialog_x = main_window_x + main_window_width + 10
        dialog_y = main_window_y - 30  # 与主窗口顶部对齐
        
        # 设置对话框位置
        self.geometry(f"600x400+{dialog_x}+{dialog_y}")
        
        # 显示窗口
        self.deiconify()  # 显示窗口
        self.lift()       # 将窗口提到前面
        
    def hide(self):
        """隐藏对话框"""
        self.withdraw()   # 隐藏窗口
        
    def on_closing(self):
        """窗口关闭时的清理操作"""
        try:
            # 只有在正在录音时才停止录音
            if self.is_recording:
                print("窗口关闭时停止录音...")
                self._stop_recording()
            
            # 隐藏窗口
            self.hide()
            
        except Exception as e:
            print(f"关闭窗口时出错: {str(e)}")
            self.hide()
            
    def setup_ui(self):
        # 主框架
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=15, pady=10)
        
        # 设置grid权重使其可以扩展
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)
        
        # 更新对话历史显示区域
        self.conversation_frame = ctk.CTkFrame(self.main_frame)
        self.conversation_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=5)
        self.conversation_frame.grid_columnconfigure(0, weight=1)
        
        # 使用Canvas和Frame实现可滚动的消息区域
        self.canvas = ctk.CTkCanvas(
            self.conversation_frame,
            bg=self._apply_appearance_mode(self._fg_color),
            highlightthickness=0)
        self.scrollbar = ctk.CTkScrollbar(self.conversation_frame, command=self.canvas.yview)
        self.messages_frame = ctk.CTkFrame(self.canvas, fg_color="transparent")
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # 布局滚动组件
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        
        # 创建窗口来显示消息框架
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.messages_frame, anchor="nw")
        
        # 配置网格权重
        self.conversation_frame.grid_rowconfigure(0, weight=1)
        self.conversation_frame.grid_columnconfigure(0, weight=1)
        
        # 绑定事件
        self.messages_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        
        # 输入区域框架
        self.input_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.input_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        
        # 文本输入框
        self.input_text = ctk.CTkTextbox(
            self.input_frame, 
            height=50,
            width=370
        )
        self.input_text.grid(row=0, column=0, padx=5)
        
        default_text = self.current_lang["input_placeholder"]
        self.input_text.insert("1.0", default_text)
        
        def on_focus_in(event):
            if self.input_text.get("1.0", "end-1c") == default_text:
                self.input_text.delete("1.0", "end")
                
        def on_focus_out(event):
            if not self.input_text.get("1.0", "end-1c").strip():
                self.input_text.insert("1.0", default_text)
        
        self.input_text.bind("<FocusIn>", on_focus_in)
        self.input_text.bind("<FocusOut>", on_focus_out)

         # 语音输入按钮
        self.voice_button = ctk.CTkButton(
            self.input_frame,
            text="",
            image=self.voice_icon,
            width=50,
            height = 50,
            command=self.toggle_voice_input,
            hover_color="#41d054"
        )
        self.voice_button.grid(row=0, column=1, padx=5)
        
        # 发送按钮
        self.send_button = ctk.CTkButton(
            self.input_frame,
            text=self.current_lang["send"],
            command=self.process_input,
            width=50,
            height=50,
            hover_color="#41d054"
        )
        self.send_button.grid(row=0, column=2, padx=(5,0))
        
        self.question_button = ctk.CTkButton(
            self.input_frame,
            text="",
            image=self.question_icon_white,
            width=20,
            height=20,
            fg_color="transparent",
            hover_color="#DBDBDB"
        )
        self.question_button.grid(row=0, column=3, padx=(10,0), pady=10, sticky="e")
        ToolTip(self.question_button, "Majordomo is your AI assistant, it can help you:\n1.interact with the robot\n2. answer FAQ questions\n3. provide assistance")
        
        # 设置模型选择框架
        self.setup_model_frame()
        
    def setup_model_frame(self):
        """设置模型选择框架"""
        
        self.model_frame = ctk.CTkFrame(self)
        self.model_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=10)
        self.model_frame.grid_columnconfigure(0, weight=1)
        self.model_frame.grid_rowconfigure(0, weight=1)
        
        # 添加模型来源切换器，包含设置标签页
        self.source_var = ctk.StringVar(value="OpenAI")
        self.source_switch = ctk.CTkSegmentedButton(
            self.model_frame,
            values=["OpenAI", "Deepseek", "Settings"],
            command=self.on_source_switch,
            selected_color="#41d054",
            selected_hover_color="#41d054"
        )
        self.source_switch.grid(row=0, column=0, columnspan=3, padx=5, pady=10)
        self.source_switch.set("OpenAI")
        
        # 创建不同模型源的框架
        self.openai_frame = self.create_openai_frame()
        self.deepseek_frame = self.create_deepseek_frame()
        self.settings_frame = self.create_settings_frame()
        
        # 默认显示OpenAI框架
        self.current_frame = self.openai_frame
        self.openai_frame.grid(row=2, column=0, columnspan=3, sticky="ew")
        self.deepseek_frame.grid_remove()
        self.settings_frame.grid_remove()

        # 添加加载状态标签
        self.loading_label = ctk.CTkLabel(
            self.model_frame,
            text="",
            text_color="gray"
        )
        self.loading_label.grid(row=3, column=0, columnspan=3, padx=5, pady=(0, 5))

    def create_openai_frame(self):
        """创建OpenAI设置框架"""
        frame = ctk.CTkFrame(self.model_frame, fg_color="transparent")
        
        # API密钥设置
        self.openai_key_label = ctk.CTkLabel(frame, text="API Key:")
        self.openai_key_label.grid(row=0, column=0, padx=10, pady=10)
        
        self.api_key_entry = ctk.CTkEntry(
            frame,
            placeholder_text="sk-...",
            width=300,
            show="*"
        )
        self.api_key_entry.grid(row=0, column=1, padx=5)
        
        # 模型选择
        self.openai_model_label = ctk.CTkLabel(frame, text="Select Model:")
        self.openai_model_label.grid(row=1, column=0, padx=10, pady=10)
        
        self.openai_model_var = ctk.StringVar(value="gpt-4")  # 设置默认值为 gpt-4
        self.openai_model_dropdown = ctk.CTkOptionMenu(
            frame,
            variable=self.openai_model_var,
            values=["gpt-4", "gpt-3.5-turbo"],
            width=200
        )
        self.openai_model_dropdown.grid(row=1, column=1, sticky="w", padx=5)
        
        # 应用按钮
        self.openai_apply_button = ctk.CTkButton(
            frame,
            text=self.current_lang["apply"],
            command=self.apply_openai_model,
            width=80,
            height=30,
            hover_color="#41d054"
        )
        self.openai_apply_button.grid(row=1, column=2, sticky="w", padx=(15,0), pady=10)
        
        return frame

    def create_deepseek_frame(self):
        """创建Deepseek设置框架"""
        frame = ctk.CTkFrame(self.model_frame, fg_color="transparent")
        
        # API密钥设置
        self.deepseek_key_label = ctk.CTkLabel(frame, text="API Key:")
        self.deepseek_key_label.grid(row=0, column=0, padx=10, pady=10)
        
        self.deepseek_api_key_entry = ctk.CTkEntry(
            frame,
            placeholder_text="DeepSeek API Key...",
            width=300,
            show="*"
        )
        self.deepseek_api_key_entry.grid(row=0, column=1, padx=5)
        
        # 模型选择
        self.deepseek_model_label = ctk.CTkLabel(frame, text="Select Model:")
        self.deepseek_model_label.grid(row=1, column=0, padx=10, pady=10)
        
        self.deepseek_model_var = ctk.StringVar(value="deepseek-v3")
        self.deepseek_model_dropdown = ctk.CTkOptionMenu(
            frame,
            variable=self.deepseek_model_var,
            values=["deepseek-v3", "deepseek-r1", "deepseek-coder"],
            width=200,
            height=30
        )
        self.deepseek_model_dropdown.grid(row=1, column=1, sticky="w", padx=5)
        
        # 应用按钮
        self.deepseek_apply_button = ctk.CTkButton(
            frame,
            text=self.current_lang["apply"],
            command=self.apply_deepseek_model,
            width=80,
            height=30,
            hover_color="#41d054"
        )
        self.deepseek_apply_button.grid(row=1, column=2, sticky="w", padx=(15,0), pady=10)
        
        return frame


    def create_settings_frame(self):
        """创建设置框架"""
        frame = ctk.CTkFrame(self.model_frame, fg_color="transparent")
        frame.grid_columnconfigure(1, weight=1)  # 设置第二列可以扩展
        
        # 语音模型设置标签
        self.voice_model_label = ctk.CTkLabel(frame, text="Voice Model:")
        self.voice_model_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        # 创建一个容器框架来放置模型按钮
        voice_model_buttons_frame = ctk.CTkFrame(frame, fg_color="transparent")
        voice_model_buttons_frame.grid(row=0, column=1, padx=5, pady=10, sticky="w")
        
        # 检查语音模型按钮
        self.check_voice_model_button = ctk.CTkButton(
            voice_model_buttons_frame,
            text="Check Voice Model",
            command=self.check_voice_model,
            width=150,
            height=30,
            hover_color="#41d054"
        )
        self.check_voice_model_button.grid(row=0, column=0, padx=(0, 5))
        
        # 下载语音模型按钮
        self.download_voice_model_button = ctk.CTkButton(
            voice_model_buttons_frame,
            text="Download Voice Model",
            command=self.download_voice_model,
            width=150,
            height=30,
            hover_color="#41d054"
        )
        self.download_voice_model_button.grid(row=0, column=1, padx=5)
        
        # 音频设备设置标签
        self.audio_device_label = ctk.CTkLabel(frame, text="Audio Device:")
        self.audio_device_label.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        
        # 创建一个容器框架来放置设备选择控件
        device_frame = ctk.CTkFrame(frame, fg_color="transparent")
        device_frame.grid(row=1, column=1, padx=5, pady=10, sticky="w")
        
        # 设备选择下拉菜单
        self.device_var = ctk.StringVar(value="Select Device")
        self.device_option_menu = ctk.CTkOptionMenu(
            device_frame,
            variable=self.device_var,
            values=["Select Device"],
            width=200,
            height=30,
            command=self.on_device_selected
        )
        self.device_option_menu.grid(row=0, column=0, padx=(0, 5))
        
        # 刷新设备列表按钮
        self.refresh_devices_button = ctk.CTkButton(
            device_frame,
            text="",
            image=self.refresh_icon,
            width=40,
            height=30,
            command=self.refresh_device_list,
            hover_color="#41d054"
        )
        self.refresh_devices_button.grid(row=0, column=1, padx=5)
        
        # 初始化设备列表
        self.refresh_device_list()
        
        return frame

    def on_source_switch(self, value):
        """处理模型来源切换"""
        # 隐藏当前框架
        self.current_frame.grid_remove()
        
        # 显示选中的框架
        if value == "OpenAI":
            self.current_frame = self.openai_frame
        elif value == "Deepseek":
            self.current_frame = self.deepseek_frame
        elif value == "Settings":
            self.current_frame = self.settings_frame
        
        self.current_frame.grid(row=1, column=0, columnspan=3, sticky="ew")

    def apply_openai_model(self):
        """应用OpenAI模型设置"""
        api_key = self.api_key_entry.get()
        model_name = self.openai_model_var.get()
        
        if not api_key:
            messagebox.showerror("错误", "请输入API Key")
            return
        
        if not model_name:
            messagebox.showerror("错误", "请选择模型")
            return
        
        try:
            if self.llm_manager.set_openai_model(api_key, model_name):
                messagebox.showinfo("成功", "OpenAI模型设置成功")
                # 添加欢迎消息
                self.add_to_conversation("AI助手", f"已配置OpenAI模型 {model_name}，可以开始对话了")
            else:
                messagebox.showerror("错误", "OpenAI模型设置失败")
        except Exception as e:
            messagebox.showerror("错误", f"设置OpenAI模型时出错: {str(e)}")

    def apply_deepseek_model(self):
        """应用Deepseek模型设置"""
        api_key = self.deepseek_api_key_entry.get()
        model_name = self.deepseek_model_var.get()
        
        if not api_key:
            messagebox.showerror("错误", "请输入API Key")
            return
        
        if not model_name:
            messagebox.showerror("错误", "请选择模型")
            return
        
        try:
            if self.llm_manager.set_deepseek_model(api_key, model_name):
                messagebox.showinfo("成功", "Deepseek模型设置成功")
                # 添加欢迎消息
                self.add_to_conversation("AI助手", f"已配置Deepseek模型 {model_name}，可以开始对话了")
            else:
                messagebox.showerror("错误", "Deepseek模型设置失败")
        except Exception as e:
            messagebox.showerror("错误", f"设置Deepseek模型时出错: {str(e)}")



    def update_status(self, status):
        """更新加载标签"""
        if hasattr(self, 'loading_label'):
            self.loading_label.configure(text=status)
            print(status)  # 保留日志输出
            self.update()
        else:
            print(f"Warning: loading_label not found. Status: {status}")
        
    def toggle_voice_input(self):
        """切换语音输入状态"""
        if self.is_recording:
            # 如果正在录音，停止录音
            self._stop_recording()
        else:
            # 如果未在录音，开始录音
            self._start_recording()
    
    def _start_recording(self):
        """开始录音的内部方法"""
        if self.is_recording:  # 防止重复启动
            return
            
        print("开始录音...")
        self.is_recording = True
        self.voice_button.configure(image=self.pause_icon)
        
        self.recording_thread = threading.Thread(
            target=self.start_voice_input,
            daemon=True  # 设置为守护线程，主程序退出时自动结束
        )
        self.recording_thread.start()
    
    def _stop_recording(self):
        """停止录音的内部方法"""
        if not self.is_recording:  # 防止重复停止
            return
            
        print("停止录音...")
        self.is_recording = False
        
        # 停止语音管理器
        self.speech_manager.stop_recording()
        
        # 立即更新UI状态
        self.voice_button.configure(image=self.voice_icon)
        
        # 在后台等待线程结束，不阻塞UI
        def wait_for_thread():
            try:
                # 保存线程引用，避免竞态条件
                thread_to_wait = self.recording_thread
                if thread_to_wait and hasattr(thread_to_wait, 'is_alive'):
                    thread_to_wait.join(timeout=3.0)
                    if thread_to_wait.is_alive():
                        print("警告：录音线程未能及时结束")
            except Exception as e:
                print(f"等待录音线程结束时出错: {str(e)}")
            finally:
                self.recording_thread = None
        
        # 在新线程中等待，避免阻塞UI
        threading.Thread(target=wait_for_thread, daemon=True).start()
            
    def start_voice_input(self):
        """开始语音输入"""
        try:
            print("开始语音识别...")
            text = self.speech_manager.start_recording(callback_status=self.update_status)
            print(f"语音识别返回结果: '{text}'" if text else "语音识别无返回结果")
            
            # 在主线程中安全地更新UI
            def update_ui():
                # 检查是否有有效的识别文本
                if text and text.strip() and not text.startswith("语音"):
                    print(f"插入文本到输入框: '{text.strip()}'")
                    
                    # 清除输入框现有内容
                    current_text = self.input_text.get("1.0", "end-1c")
                    if current_text == self.current_lang.get("input_placeholder", ""):
                        self.input_text.delete("1.0", "end")
                    else:
                        self.input_text.delete("1.0", "end")
                    
                    # 插入识别的文本
                    self.input_text.insert("1.0", text.strip())
                else:
                    print("没有有效文本插入")
                
                # 重置录音状态
                self.is_recording = False
                self.voice_button.configure(image=self.voice_icon)
                self.recording_thread = None  # 清空线程引用
            
            # 使用after方法在主线程中执行UI更新
            self.after(0, update_ui)
            
        except Exception as e:
            print(f"语音输入过程中出错: {str(e)}")
            # 确保在出错时也重置状态
            def reset_ui():
                self.is_recording = False
                self.voice_button.configure(image=self.voice_icon)
                self.recording_thread = None
            self.after(0, reset_ui)    
        
    def refresh_device_list(self):
        """刷新音频设备列表"""
        try:
            devices = self.speech_manager.list_audio_devices()
            device_names = []
            self.device_mapping = {}  # 存储设备名称到ID的映射
            
            for device_id, device in devices:
                device_name = device['name']
                device_names.append(device_name)
                self.device_mapping[device_name] = device_id
            
            if device_names:
                # 更新选项菜单的值
                self.device_option_menu.configure(values=device_names)
                
                # 从Config类获取保存的设备设置
                last_device = Config.get_audio_device()
                if last_device and last_device in device_names:
                    self.device_var.set(last_device)
                    self.speech_manager.set_device(self.device_mapping[last_device])
                else:
                    self.device_var.set(device_names[0])
            else:
                self.device_option_menu.configure(values=["No devices found"])
                self.device_var.set("No devices found")
                
        except Exception as e:
            print(f"刷新设备列表失败: {str(e)}")
            self.device_option_menu.configure(values=["Error loading devices"])
            self.device_var.set("Error loading devices")
    
    def on_device_selected(self, device_name):
        """当选择设备时的回调函数"""
        try:
            if device_name in self.device_mapping:
                device_id = self.device_mapping[device_name]
                self.speech_manager.set_device(device_id)
                
                # 保存选择的设备到Config类
                Config.set_audio_device(device_name)
                
                print(f"已选择音频设备: {device_name} (ID: {device_id})")
            else:
                print(f"未找到设备: {device_name}")
        except Exception as e:
            print(f"选择设备时出错: {str(e)}")
            
    def process_input(self):
        """处理用户输入"""
        text = self.input_text.get("1.0", tk.END).strip()
        if text:
            self.add_to_conversation("用户", text)
            
            if not self.llm_manager.is_ready():
                self.add_to_conversation(
                    "系统",
                    "请先加载模型"
                )
                return
                
            # 在新线程中处理指令
            threading.Thread(
                target=self._process_instruction_thread,
                args=(text,)
            ).start()
            
            self.input_text.delete("1.0", tk.END)

    def _process_instruction_thread(self, text):
        """在新线程中处理指令"""
        try:
            self.update_status("正在解析指令...")
            
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # 使用LLM处理指令，添加超时处理
                result = loop.run_until_complete(
                    self.llm_manager.process_instruction(text, timeout=60.0)
                )
                
                # 解析返回结果
                msg_type, content = result
                
                if msg_type == "error":
                    self.add_to_conversation("系统", f"错误: {content}")
                    self.update_status("")
                    return
                    
                elif msg_type == "command":
                    if not content:
                        self.add_to_conversation("系统", "未能识别有效的指令")
                        self.update_status("")
                        return
                        
                    # 执行每个命令
                    for command in content:
                        print(command)
                        cmd_name = command["command"]
                        self.update_status(f"正在执行: {cmd_name}")
                        result = self.execute_command(command)
                        self.add_to_conversation("系统", result)
                        
                elif msg_type in ["qa", "chat"]:
                    # 直接显示问答或聊天的回复
                    self.add_to_conversation("AI助手", content)
                    
                else:
                    self.add_to_conversation("系统", f"未知的响应类型: {msg_type}")
                
                self.update_status("执行完成")
                
            finally:
                # 关闭事件循环
                loop.close()
                
        except Exception as e:
            self.add_to_conversation("系统", f"处理指令时出错: {str(e)}")
            self.update_status("")

    def add_to_conversation(self, speaker, text):
        """添加简洁样式的消息到对话历史"""
        self.message_styles = {
            "user": {
                "bg_color": "transparent",
                "text_color": "#666666",
                "prefix": "$ "  # 用户消息前加入 $
            },
            "system": {
                "bg_color": "transparent",
                "text_color": "#3B8ED0",
                "prefix": "AI: "
            }
        }
        
        # 创建新的消息框架
        msg_frame = ctk.CTkFrame(self.messages_frame, fg_color="transparent")
        msg_frame.grid(sticky="ew", padx=10, pady=5)
        msg_frame.grid_columnconfigure(0, weight=1)
        
        # 确定消息样式
        style = self.message_styles["system" if speaker == "AI助手" else "user"]
        
        # 创建消息文本
        prefix = style["prefix"]
        message_label = ctk.CTkLabel(
            msg_frame,
            text=f"{prefix}{text}",
            text_color=style["text_color"],
            wraplength=520,
            justify="left"  # 所有消息都左对齐
        )
        
        # 统一使用左对齐布局
        message_label.grid(
            row=0, 
            column=0,
            sticky="w",
            padx=10
        )
        
        # 添加分隔线
        separator = ctk.CTkFrame(
            msg_frame, 
            height=1, 
            fg_color="#EEEEEE"
        )
        separator.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        
        # 立即更新布局
        msg_frame.update_idletasks()
        self.messages_frame.update_idletasks()
        
        # 更新滚动区域
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.canvas.yview_moveto(1.0)

    def _on_frame_configure(self, event=None):
        """当消息框架大小改变时更新滚动区域"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        """当画布大小改变时调整消息框架宽度"""
        self.canvas.itemconfig(self.canvas_frame, width=event.width)

    def get_current_controller(self):
        """获取当前活动的控制器框架"""
        return getattr(self.parent, 'controller_frame', None)
        
    def execute_command(self, command):
        """执行命令的桥接函数"""
        cmd_name = command["command"]
        params = command["parameters"]
        
        try:
            # 基础控制命令
            if cmd_name == "CONNECT":
                # 连接逻辑已迁移到 robot_profile_frame
                if hasattr(self.parent, 'robot_profile_frame') and hasattr(self.parent.robot_profile_frame, 'on_connect'):
                    self.parent.robot_profile_frame.on_connect()
                    return "已连接机械臂"
                return "未找到连接接口：robot_profile_frame.on_connect 不存在"
                
            elif cmd_name == "DISCONNECT":
                # 断开逻辑已迁移到 robot_profile_frame
                if hasattr(self.parent, 'robot_profile_frame') and hasattr(self.parent.robot_profile_frame, 'on_disconnect'):
                    self.parent.robot_profile_frame.on_disconnect()
                    return "已断开连接"
                return "未找到断开接口：robot_profile_frame.on_disconnect 不存在"
                
            # 关节控制命令
            elif cmd_name == "MOVE_JOINT":
                try:
                    controller = self.get_current_controller()
                    if not controller:
                        return "控制器框架未找到"
                        
                    joint_id = int(params.get("joint_id", 1))
                    angle = float(params.get("angle", 0))
                    
                    # 检查关节ID是否在有效范围内
                    if not 1 <= joint_id <= len(controller.joint_sliders):
                        return f"无效的关节ID: {joint_id}，应该在1-{len(controller.joint_sliders)}之间"
                        
                    # 获取对应的滑块控件
                    slider = controller.joint_sliders[joint_id-1]
                    
                    # 检查角度是否在限制范围内
                    joint_limits = controller.joint_limits[joint_id-1]
                    if not joint_limits[0] <= angle <= joint_limits[1]:
                        return f"角度{angle}超出关节{joint_id}的限制范围({joint_limits[0]},{joint_limits[1]})"
                        
                    # 设置滑块值
                    slider.set(angle)
                    
                    # 调用关节变化方法来更新状态和标签
                    controller.on_joint_change(joint_id-1)
                    
                    # 执行移动命令
                    controller.on_execute()
                    time.sleep(0.05)
                    
                    return f"已移动关节{joint_id}到{angle}度"
                    
                except Exception as e:
                    return f"移动关节时出错: {str(e)}"
                
            # 夹爪控制命令
            elif cmd_name == "TOOL_CONTROL":
                try:
                    controller = self.get_current_controller()
                    if not controller:
                        return "控制器框架未找到"
                        
                    state = params.get("state", "").lower()
                    
                    # 检查执行器类型并相应控制
                    if hasattr(controller, 'gripper_switch'):
                        # signal 类型 - 使用开关
                        if state == "on":
                            controller.gripper_switch.select()
                        else:
                            controller.gripper_switch.deselect()
                        controller.on_gripper_toggle()
                        return f"已设置夹爪开关状态为{state}"
                        
                    elif hasattr(controller, 'gripper_slider'):
                        # uniform movable 类型 - 使用滑块
                        # 从工具组配置获取范围值
                        if hasattr(controller, 'tool_group') and controller.tool_group:
                            joints_with_limits = [joint for joint in controller.tool_group if "limit" in joint]
                            if joints_with_limits:
                                min_val = min(joint["limit"]["lower"] for joint in joints_with_limits)
                                max_val = max(joint["limit"]["upper"] for joint in joints_with_limits)
                            else:
                                min_val, max_val = 0, 1
                        else:
                            # 如果没有工具组信息，使用默认范围
                            min_val, max_val = 0, 1
                            
                        if state == "on":
                            controller.gripper_slider.set(max_val)
                        else:
                            controller.gripper_slider.set(min_val)
                        controller.on_uniform_gripper_change(controller.gripper_slider.get())
                        return f"已设置夹爪滑块状态为{state}"
                        
                    elif hasattr(controller, 'gripper_sliders'):
                        # independent movable 类型 - 使用多个滑块
                        if hasattr(controller, 'tool_group') and controller.tool_group:
                            for i, slider in enumerate(controller.gripper_sliders):
                                if i < len(controller.tool_group):
                                    joint = controller.tool_group[i]
                                    if "limit" in joint:
                                        min_val = joint["limit"]["lower"]
                                        max_val = joint["limit"]["upper"]
                                    else:
                                        min_val, max_val = 0, 1
                                else:
                                    min_val, max_val = 0, 1
                                    
                                if state == "on":
                                    slider.set(max_val)
                                else:
                                    slider.set(min_val)
                        else:
                            # 如果没有工具组信息，使用默认范围
                            for slider in controller.gripper_sliders:
                                if state == "on":
                                    slider.set(1)  # 默认最大值
                                else:
                                    slider.set(0)  # 默认最小值
                        
                        # 调用第一个滑块的变化事件来触发更新
                        if controller.gripper_sliders:
                            controller.on_independent_gripper_change(0)
                        return f"已设置所有夹爪滑块状态为{state}"
                        
                    else:
                        return "未找到夹爪控制接口"
                        
                except Exception as e:
                    return f"夹爪控制出错: {str(e)}"
            
            elif cmd_name == "SPD":
                joint_id = int(params.get("joint_id", 1)) - 1  # 转换为0索引
                value = float(params.get("value", 100.0))
                
                # 限制值在合理范围内
                value = max(10, min(190, value))
                
                # 调用设置框架的速度设置方法
                if hasattr(self.parent, 'settings_frame'):
                    self.parent.settings_frame._handle_speed_change(joint_id, value)
                    return f"已设置关节{joint_id+1}速度为{value:.1f}%"
                else:
                    return "设置框架未找到，无法设置速度"
                
            # 运动学控制命令
            elif cmd_name == "MOVE_TO":
                x = float(params.get("x", 0))
                y = float(params.get("y", 0))
                z = float(params.get("z", 0))
                # 设置目标位置
                for entry, value in zip(self.parent.kinematics_frame.target_entries, [x, y, z]):
                    entry.delete(0, tk.END)
                    entry.insert(0, str(value))
                # 使用update_p方法进行逆运动学计算
                target_position = np.array([x, y, z])
                target_orientation = np.radians(self.parent.kinematics_frame.target_orientation.copy())
                self.parent.kinematics_frame.update_p(target_position, target_orientation)
                return f"移动到位置 (x={x}, y={y}, z={z})"
                
            # ROS相关命令
            elif cmd_name == "ROS_ENABLE":
                version = params.get("version", "ROS2")
                self.parent.ros_frame.enable_ros(version)
                return f"已启用 {version}"
                
            elif cmd_name == "ROS_DISABLE":
                self.parent.ros_frame.disable_ros()
                return "已禁用 ROS"
                
            elif cmd_name == "ROS_CHECK":
                self.parent.ros_frame.check_ros()
                return "正在检查 ROS 统"
            
            elif cmd_name == "HOME":
                controller = self.get_current_controller()
                if not controller:
                    return "控制器框架未找到"
                # 先重置滑块到归位角度
                controller.reset_sliders()
                # 执行归位动作
                controller.on_execute()
                return "机械臂正在归位"
                
            elif cmd_name == "STOP":
                controller = self.get_current_controller()
                if not controller:
                    return "控制器框架未找到"
                # 检查控制器类型并调用相应的停止/暂停方法
                if hasattr(controller, 'on_pause_resume'):
                    # controller_frame 使用 on_pause_resume
                    controller.on_pause_resume()
                    return "已暂停/恢复运动"
                elif hasattr(controller, 'on_emergency_pause_resume'):
                    # anytroller_frame 使用 on_emergency_pause_resume
                    controller.on_emergency_pause_resume()
                    return "已暂停/恢复运动"
                else:
                    return "当前控制器不支持停止命令"
            elif cmd_name == "SWITCH_FRAME":
                frame = params.get("frame", "").lower()
                if frame == "controller":
                    self.parent.show_controller()
                    return "已切换到控制器界面"
                elif frame == "firmware":
                    self.parent.show_firmware()
                    return "已切换到固件界面"
                elif frame == "help":
                    self.parent.show_help()
                    return "已切换到帮助界面"
                elif frame == "anytroller":
                    self.parent.show_anytroller()
                    return "已切换到Anytroller界面"
                elif frame == "ros":
                    self.parent.show_ros()
                    return "已切换到ROS界"
                elif frame == "kinematics":
                    self.parent.show_kinematics()
                    return "已切换到运动学界面"
                elif frame == "settings":
                    self.parent.show_settings()
                    return "已切换到设置界面"
                elif frame == "profile":
                    self.parent.show_profile()
                    return "已切换到配置文件界面"
                else:
                    return f"未知的界面: {frame}"
                
            return f"未知命令: {cmd_name}"
            
        except Exception as e:
            return f"执行命令出错: {str(e)}"

    def update_texts(self):
        """更新界面文本"""
        self.current_lang = Config.get_current_lang()
        
        # 更新窗口标题
        self.title(self.current_lang["majordomo"])
        
        # 更新按钮文本
        self.send_button.configure(text=self.current_lang["send"])
        self.openai_apply_button.configure(text=self.current_lang["apply"])
        self.deepseek_apply_button.configure(text=self.current_lang["apply"])
        
        # 更新文本框的默认文本
        if self.input_text.get("1.0", "end-1c") == self.current_lang["input_placeholder"]:
            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", self.current_lang["input_placeholder"])

    def check_voice_model(self):
        """检查语音模型是否存在"""
        try:
            if self.speech_manager.model_exists():
                messagebox.showinfo("Model Status", "Voice model is already installed and ready to use.")
                self.add_to_conversation("系统", "语音模型已安装并可用")
            else:
                messagebox.showwarning("Model Status", "Voice model is not found. Please download the model.")
                self.add_to_conversation("系统", "未找到语音模型，请下载模型")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to check voice model: {str(e)}")
            self.add_to_conversation("系统", f"检查语音模型失败: {str(e)}")

    def download_voice_model(self):
        """下载语音模型"""
        try:
            # 显示下载确认对话框
            result = messagebox.askyesno(
                "Download Voice Model", 
                "This will download the voice recognition model (approximately 40MB). Continue?"
            )
            
            if result:
                self.update_status("正在下载语音模型...")
                self.add_to_conversation("系统", "开始下载语音模型，请稍候...")
                
                # 在新线程中下载模型
                threading.Thread(target=self._download_model_thread).start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start model download: {str(e)}")
            self.add_to_conversation("系统", f"启动模型下载失败: {str(e)}")

    def _download_model_thread(self):
        """在新线程中下载模型"""
        try:
            success = self.speech_manager.download_model()
            
            if success:
                messagebox.showinfo("Success", "Voice model downloaded successfully!")
                self.add_to_conversation("系统", "语音模型下载成功")
                self.update_status("模型下载完成")
            else:
                messagebox.showerror("Error", "Failed to download voice model")
                self.add_to_conversation("系统", "语音模型下载失败")
                self.update_status("模型下载失败")
                
        except Exception as e:
            messagebox.showerror("Error", f"Model download error: {str(e)}")
            self.add_to_conversation("系统", f"模型下载错误: {str(e)}")
            self.update_status("模型下载出错")
