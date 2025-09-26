import os
import math
import time
import numpy as np
import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog
import threading
import queue
import ast
from PIL import Image

from utils.resource_loader import ResourceLoader
from utils.ctkAdvancedTextBox import CTkAdvancedTextBox

class BlocklyEditor:
    def __init__(self, parent_frame, vision_frame):
        """
        初始化Blockly编辑器
        
        Args:
            parent_frame: 父容器框架
            vision_frame: VisionFrame
        """
        self.parent_frame = parent_frame
        self.vision_frame = vision_frame
        
        # 执行控制
        self.execution_thread = None
        self.is_executing = False
        self.stop_execution = False
        self.output_queue = queue.Queue()
        
        # 创建内容框架（将包含代码编辑器和终端）
        self.content_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=5, pady=0)
        
        # 显示状态（默认显示代码编辑器）
        self.show_editor = True
        
        # 创建代码编辑器和终端框架（最初只显示编辑器）
        self.code_editor_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.code_editor_frame.pack(fill="both", expand=True)

        self.terminal_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        # 不要立即pack终端框架，因为默认显示代码编辑器
        
        self.setup_code_editor()
        self.setup_terminal_interface()
        
        # 启动输出处理
        self.process_output_queue()

    def setup_code_editor(self):
        """设置代码编辑器界面"""     
        # 创建Blockly功能选择器
        selector_frame = ctk.CTkFrame(self.code_editor_frame, fg_color="transparent")
        selector_frame.pack(fill="x", padx=0, pady=5)
        
        blockly_label = ctk.CTkLabel(selector_frame, text="Blockly功能:")
        blockly_label.pack(side="left", padx=(0, 10))
        
        # 定义Blockly功能选项
        self.blockly_options = {
            "--- 检测功能 ---": "",
            "获取检测结果": "get_detection_result",
            "获取边界框": "get_bounding_box", 
            "获取中心点": "get_bounding_box_center",
            "获取世界坐标": "get_world_coordinates",
            "--- 机器人控制 ---": "",
            "移动到位置": "move_to",
            "移动到位置(含姿态)": "move_to_with_orientation",
            "打开夹爪": "open_gripper",
            "关闭夹爪": "close_gripper",
            "回到初始位置": "go_home",
            "--- 流程控制 ---": "",
            "等待": "wait",
            "--- 工具函数 ---": "",
            "打印信息": "print_message",
            "计算距离": "calculate_distance"
        }
        
        # 创建下拉菜单
        option_keys = list(self.blockly_options.keys())
        self.selected_blockly_var = tk.StringVar(value=option_keys[1])  # 默认选择第一个非分隔符选项
        
        self.blockly_selector = ctk.CTkOptionMenu(
            selector_frame,
            variable=self.selected_blockly_var,
            values=option_keys,
            width=150
        )
        self.blockly_selector.pack(side="left", padx=5)
        
        # 添加按钮
        self.add_options_button = ctk.CTkButton(
            selector_frame,
            text="+",
            command=self.add_selected_blockly_code,
            width=30,
            height=30,
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.add_options_button.pack(side="left", padx=5)

        # 添加切换按钮
        self.toggle_button = ctk.CTkButton(
            selector_frame, 
            text="切换到终端", 
            command=self.toggle_view,
            width=100,
            fg_color="transparent",  # 透明背景
            border_color="black",    # 黑色边框
            border_width=2,          # 边框宽度
            text_color="black"       # 黑色文字
        )
        self.toggle_button.pack(side="right", padx=(5,0))
        
        # 按钮框架 - 先创建按钮框架
        buttons_frame = ctk.CTkFrame(self.code_editor_frame, fg_color="transparent")
        buttons_frame.pack(side="bottom", fill="x", pady=5)
        
        # 创建CTkAdvancedTextBox代替原来的代码编辑器，使用空的代码模板
        self.code_editor = CTkAdvancedTextBox(
            self.code_editor_frame,
            code_templates={},  # 开始时使用空模板
            font=ctk.CTkFont(family="Consolas", size=15),
            fg_color="white",
            text_color="black",
            border_width=1,
            border_color="gray",
            show_line_numbers=True
        )
        self.code_editor.pack(fill="both", expand=True, padx=0, pady=5)
        
        # 显示使用说明
        info_text = """# Blockly Code Example(Pump Tool) - Looped detection and placement

# 目标放置位置
target_x = 37.525
target_y = 49.252
target_z = 15
distance_threshold = 10  # 距离阈值(毫米)

# 循环5次，持续抓取和放置
for i in range(5):
    print(f"循环第 {i+1} 次")
    
    # 获取检测结果
    objects = get_detection_result(0)
    if len(objects) == 0:
        print("没有检测到物体，跳过此次循环")
        continue
    
    # 获取第一个物体的信息
    bbox = get_bounding_box(objects[0])
    center = get_bounding_box_center(bbox)
    x_mm, y_mm, z_mm = get_world_coordinates(pixel_x=center['x'], pixel_y=center['y'], z_depth_mm=15)
    
    # 计算当前物体与目标位置的距离
    distance = calculate_distance({'x': x_mm, 'y': y_mm}, {'x': target_x, 'y': target_y})
    print(f"物体位置: ({x_mm:.2f}, {y_mm:.2f}), 距离目标: {distance:.2f}mm")
    
    # 如果物体已经在目标位置附近，跳过操作
    if distance <= distance_threshold:
        print("物体已在目标位置附近，跳过操作")
        continue
    
    # 执行抓取和放置操作
    print("开始抓取物体...")
    move_to(x=x_mm, y=y_mm, z=target_z, pitch=90)
    open_gripper()
    close_gripper()
    
    print("放置物体到目标位置...")
    move_to(x=target_x, y=target_y, z=target_z, pitch=90)
    open_gripper()
    
    print("返回初始位置")
    go_home()
    
    # 等待一下再进行下一次循环
    wait(1)

print("所有循环完成")"""
        
        self.code_editor.insert("1.0", info_text)
        
        # 创建按钮
        self.run_btn = ctk.CTkButton(buttons_frame, text="运行", command=self.run_blockly_code, width=60)
        self.run_btn.pack(side="left", padx=(0,5))
        
        self.stop_btn = ctk.CTkButton(buttons_frame, text="停止", command=self.stop_blockly_code, width=60, 
                                     fg_color="red", hover_color="darkred", state="disabled")
        self.stop_btn.pack(side="left", padx=5)
        
        clear_btn = ctk.CTkButton(buttons_frame, text="清空", command=self.clear_code_editor, width=60)
        clear_btn.pack(side="left", padx=5)
        
        save_btn = ctk.CTkButton(buttons_frame, text="保存", command=self.save_blockly_code, width=60)
        save_btn.pack(side="right", padx=5)
        
        load_btn = ctk.CTkButton(buttons_frame, text="加载", command=self.load_blockly_code, width=60)
        load_btn.pack(side="right", padx=5)

    def setup_terminal_interface(self):
        """设置终端界面"""
        
        # 创建顶部工具栏
        terminal_toolbar = ctk.CTkFrame(self.terminal_frame, fg_color="transparent")
        terminal_toolbar.pack(fill="x", padx=5, pady=5)
        
        # 添加切换按钮
        terminal_toggle_btn = ctk.CTkButton(
            terminal_toolbar, 
            text="切换到代码", 
            command=self.toggle_view,
            width=100,
            fg_color="transparent",  # 透明背景
            border_color="black",    # 黑色边框
            border_width=1,          # 边框宽度
            text_color="black"       # 黑色文字
        )
        terminal_toggle_btn.pack(side="right", padx=(5,0))
        
        # 终端输出区域
        output_frame = ctk.CTkFrame(self.terminal_frame, fg_color="transparent")
        output_frame.pack(fill="both", expand=True)
        
        self.terminal_output = ctk.CTkTextbox(
            output_frame, 
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="lightgreen",
            fg_color="black"
        )
        self.terminal_output.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 在终端底部添加一个按钮框架
        terminal_buttons_frame = ctk.CTkFrame(output_frame, fg_color="transparent")
        terminal_buttons_frame.pack(side="bottom", fill="x", padx=5, pady=5)
        
        # 添加清除终端按钮
        clear_terminal_btn = ctk.CTkButton(
            terminal_buttons_frame, 
            text="清除终端", 
            command=self.clear_terminal,
            width=100
        )
        clear_terminal_btn.pack(side="left", padx=5)
        
    def get_detection_results(self, camera_index):
        """获取指定相机的检测结果
        
        Args:
            camera_index: 相机索引
            
        Returns:
            list: 检测结果列表
        """
        try:
            if camera_index < len(self.vision_frame.detection_results):
                results = self.vision_frame.detection_results[camera_index]
                # 根据检测器类型处理不同的数据结构
                if isinstance(results, dict) and 'detected' in results:
                    return results['detected'], results['label']  # 处理频域检测器格式
                else:
                    return [], "unknown"
            return [], "unknown"
        except Exception as e:
            print(f"获取检测结果失败: {str(e)}")
            return [], "unknown"
        
    def process_output_queue(self):
        """处理输出队列中的消息"""
        try:
            while True:
                message = self.output_queue.get_nowait()
                self.terminal_output.insert("end", message + "\n")
                self.terminal_output.see("end")
        except queue.Empty:
            pass
        
        # 每100ms检查一次队列
        self.parent_frame.after(100, self.process_output_queue)
    
    def add_selected_blockly_code(self):
        """添加选中的Blockly代码到编辑器"""
        try:
            selected_option = self.selected_blockly_var.get()
            
            # 检查是否是分隔符（以"---"开头和结尾）
            if selected_option.startswith("---") and selected_option.endswith("---"):
                self.log_to_terminal("请选择具体的功能选项")
                return
            
            # 获取对应的函数名
            function_name = self.blockly_options.get(selected_option, "")
            
            if function_name:
                # 调用对应的添加函数
                if hasattr(self, f"add_{function_name}_line"):
                    add_function = getattr(self, f"add_{function_name}_line")
                    line_id = add_function()
                    if line_id:
                        self.log_to_terminal(f"已添加: {selected_option}")
                    else:
                        self.log_to_terminal(f"添加 {selected_option} 失败")
                else:
                    self.log_to_terminal(f"未找到对应的添加函数: add_{function_name}_line")
            else:
                self.log_to_terminal("未找到对应的函数名")
                
        except Exception as e:
            self.log_to_terminal(f"错误: 添加代码失败 - {str(e)}")
    
    # Blockly代码行添加函数
    def add_get_detection_result_line(self):
        """添加获取检测结果代码行"""
        try:
            # 获取可用的相机ID
            active_cameras = self.vision_frame.controller.get_active_cameras()
            camera_ids = [str(i) for i in range(len(active_cameras))]
            if not camera_ids:
                camera_ids = ["0"]
            
            # 动态更新代码模板，包含可编辑的变量名
            templates = {
                "get_detection_result": {
                    "params": ["variable_name", "camera_id"],
                    "options": {
                        "variable_name": ["objects"],
                        "camera_id": camera_ids
                    },
                    "format": "{variable_name} = get_detection_result({camera_id})"
                }
            }
            
            # 更新编辑器的代码模板
            self.code_editor.update_code_templates(templates)
            
            # 添加代码行
            line_id = self.code_editor.add_line("get_detection_result", {"variable_name": "objects", "camera_id": camera_ids[0]})
            return line_id
        except Exception as e:
            self.log_to_terminal(f"添加get_detection_result失败: {str(e)}")
            return None
    
    def add_get_bounding_box_line(self):
        """添加获取边界框代码行"""
        try:
            # 获取检测到的对象选项
            all_objects = []
            active_cameras = self.vision_frame.controller.get_active_cameras()
            for camera_index in active_cameras:
                detection_results = self.get_detection_results(camera_index)
                for i, _ in enumerate(detection_results):
                    all_objects.append(f"objects[{i}]")
            
            if not all_objects:
                all_objects = ["objects[0]"]
            
            templates = {
                "get_bounding_box": {
                    "params": ["variable_name", "obj"],
                    "options": {
                        "variable_name": ["bbox"],
                        "obj": all_objects
                    },
                    "format": "{variable_name} = get_bounding_box({obj})"
                }
            }
            
            self.code_editor.update_code_templates(templates)
            line_id = self.code_editor.add_line("get_bounding_box", {"variable_name": "bbox", "obj": all_objects[0]})
            return line_id
        except Exception as e:
            self.log_to_terminal(f"添加get_bounding_box失败: {str(e)}")
            return None
    
    def add_get_bounding_box_center_line(self):
        """添加获取边界框中心点代码行"""
        try:
            templates = {
                "get_bounding_box_center": {
                    "params": ["variable_name", "bbox"],
                    "options": {
                        "variable_name": ["center"],
                        "bbox": ["bbox"]
                    },
                    "format": "{variable_name} = get_bounding_box_center({bbox})"
                }
            }
            
            self.code_editor.update_code_templates(templates)
            line_id = self.code_editor.add_line("get_bounding_box_center", {"variable_name": "center", "bbox": "bbox"})
            return line_id
        except Exception as e:
            self.log_to_terminal(f"添加get_bounding_box_center失败: {str(e)}")
            return None
    
    def add_get_world_coordinates_line(self):
        """添加获取世界坐标代码行"""
        try:
            templates = {
                "x_mm, y_mm, z_mm = get_world_coordinates": {
                    "params": ["pixel_x", "pixel_y", "z_depth_mm"],
                    "options": {},
                    "format": "x_mm, y_mm, z_mm = get_world_coordinates(pixel_x={pixel_x}, pixel_y={pixel_y}, z_depth_mm={z_depth_mm})"
                }
            }
            
            self.code_editor.update_code_templates(templates)
            line_id = self.code_editor.add_line("x_mm, y_mm, z_mm = get_world_coordinates", {
                "pixel_x": "center['x']", 
                "pixel_y": "center['y']", 
                "z_depth_mm": "0"
            })
            return line_id
        except Exception as e:
            self.log_to_terminal(f"添加get_world_coordinates失败: {str(e)}")
            return None
    
    def add_move_to_line(self):
        """添加移动到位置代码行"""
        try:
            templates = {
                "move_to": {
                    "params": ["x", "y", "z"],
                    "options": {},
                    "format": "move_to(x={x}, y={y}, z={z})"
                }
            }
            
            self.code_editor.update_code_templates(templates)
            line_id = self.code_editor.add_line("move_to", {"x": "x_mm", "y": "y_mm", "z": "10"})
            return line_id
        except Exception as e:
            self.log_to_terminal(f"添加move_to失败: {str(e)}")
            return None
    
    def add_move_to_with_orientation_line(self):
        """添加带姿态的移动代码行"""
        try:
            templates = {
                "move_to": {
                    "params": ["x", "y", "z", "roll", "pitch", "yaw"],
                    "options": {},
                    "format": "move_to(x={x}, y={y}, z={z}, roll={roll}, pitch={pitch}, yaw={yaw})"
                }
            }
            
            self.code_editor.update_code_templates(templates)
            line_id = self.code_editor.add_line("move_to", {
                "x": "x_mm", "y": "y_mm", "z": "10", 
                "roll": "0", "pitch": "0", "yaw": "0"
            })
            return line_id
        except Exception as e:
            self.log_to_terminal(f"添加move_to_with_orientation失败: {str(e)}")
            return None
    
    def add_open_gripper_line(self):
        """添加打开夹爪代码行"""
        try:
            templates = {
                "open_gripper": {
                    "params": [],
                    "options": {}
                }
            }
            
            self.code_editor.update_code_templates(templates)
            line_id = self.code_editor.add_line("open_gripper", {})
            return line_id
        except Exception as e:
            self.log_to_terminal(f"添加open_gripper失败: {str(e)}")
            return None
    
    def add_close_gripper_line(self):
        """添加关闭夹爪代码行"""
        try:
            templates = {
                "close_gripper": {
                    "params": [],
                    "options": {}
                }
            }
            
            self.code_editor.update_code_templates(templates)
            line_id = self.code_editor.add_line("close_gripper", {})
            return line_id
        except Exception as e:
            self.log_to_terminal(f"添加close_gripper失败: {str(e)}")
            return None
    
    def add_go_home_line(self):
        """添加回到初始位置代码行"""
        try:
            templates = {
                "go_home": {
                    "params": [],
                    "options": {}
                }
            }
            
            self.code_editor.update_code_templates(templates)
            line_id = self.code_editor.add_line("go_home", {})
            return line_id
        except Exception as e:
            self.log_to_terminal(f"添加go_home失败: {str(e)}")
            return None
    
    def add_wait_line(self):
        """添加等待代码行"""
        try:
            templates = {
                "wait": {
                    "params": ["seconds"],
                    "options": {},
                    "format": "wait({seconds})"
                }
            }
            
            self.code_editor.update_code_templates(templates)
            line_id = self.code_editor.add_line("wait", {"seconds": "1.0"})
            return line_id
        except Exception as e:
            self.log_to_terminal(f"添加wait失败: {str(e)}")
            return None
    
    def add_print_message_line(self):
        """添加打印信息代码行"""
        try:
            templates = {
                "print": {
                    "params": ["message"],
                    "options": {},
                    "format": "print({message})"
                }
            }
            
            self.code_editor.update_code_templates(templates)
            line_id = self.code_editor.add_line("print", {"message": "'Hello World'"})
            return line_id
        except Exception as e:
            self.log_to_terminal(f"添加print失败: {str(e)}")
            return None
    
    def add_calculate_distance_line(self):
        """添加计算距离代码行"""
        try:
            templates = {
                "calculate_distance": {
                    "params": ["variable_name", "point1", "point2"],
                    "options": {
                        "variable_name": ["distance"],
                        "point1": ["center1"],
                        "point2": ["center2"]
                    },
                    "format": "{variable_name} = calculate_distance({point1}, {point2})"
                }
            }
            
            self.code_editor.update_code_templates(templates)
            line_id = self.code_editor.add_line("calculate_distance", {
                "variable_name": "distance",
                "point1": "center1", 
                "point2": "center2"
            })
            return line_id
        except Exception as e:
            self.log_to_terminal(f"添加calculate_distance失败: {str(e)}")
            return None
    
    def clear_terminal(self):
        """清除终端内容"""
        self.terminal_output.delete("1.0", "end")
        self.terminal_output.insert("1.0", ">>> ")

    def toggle_view(self):
        """切换视图，在代码编辑器和终端之间切换"""
        if self.show_editor:
            # 切换到终端视图
            self.code_editor_frame.pack_forget()
            self.terminal_frame.pack(fill="both", expand=True)
            self.toggle_button.configure(text="切换到代码")
            self.show_editor = False
        else:
            # 切换到代码编辑器视图
            self.terminal_frame.pack_forget()
            self.code_editor_frame.pack(fill="both", expand=True)
            self.toggle_button.configure(text="切换到终端")
            self.show_editor = True
    
    def run_blockly_code(self):
        """运行Blockly代码"""
        if self.is_executing:
            self.queue_log("代码正在执行中，请等待完成或点击停止")
            return
            
        try:
            code = self.code_editor.get("1.0", "end").strip()
            if not code:
                self.queue_log("代码为空，无法执行")
                return
                
            self.queue_log("开始执行代码:")
            self.queue_log("-" * 40)
            
            # 设置执行状态
            self.is_executing = True
            self.stop_execution = False
            self.run_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            
            # 在新线程中执行代码
            self.execution_thread = threading.Thread(target=self.execute_blockly_code_threaded, args=(code,))
            self.execution_thread.daemon = True
            self.execution_thread.start()
            
        except Exception as e:
            self.queue_log(f"错误: 启动代码执行失败 - {str(e)}")
            self.reset_execution_state()
    
    def stop_blockly_code(self):
        """停止代码执行"""
        if self.is_executing:
            self.stop_execution = True
            self.queue_log("正在停止代码执行...")
            
            # 等待线程结束（最多等待2秒）
            if self.execution_thread and self.execution_thread.is_alive():
                self.execution_thread.join(timeout=2.0)
            
            self.reset_execution_state()
            self.queue_log("代码执行已停止")
    
    def reset_execution_state(self):
        """重置执行状态"""
        self.is_executing = False
        self.stop_execution = False
        self.run_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def clear_code_editor(self):
        """清空代码编辑器"""
        self.code_editor.delete("1.0", "end")

    def save_blockly_code(self):
        """保存Blockly代码到文件"""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".py",
                filetypes=[("Python 文件", "*.py"), ("所有文件", "*.*")],
                initialfile="blockly_code.py"
            )
            
            if file_path:
                code = self.code_editor.get("1.0", "end")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(code)
                self.log_to_terminal(f"代码已保存到: {file_path}")
                
        except Exception as e:
            self.log_to_terminal(f"错误: 保存代码失败 - {str(e)}")

    def load_blockly_code(self):
        """从文件加载Blockly代码"""
        try:
            file_path = filedialog.askopenfilename(
                filetypes=[("Python 文件", "*.py"), ("所有文件", "*.*")]
            )
            
            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                
                self.code_editor.delete("1.0", "end")
                self.code_editor.insert("1.0", code)
                self.log_to_terminal(f"代码已从文件加载: {file_path}")
                
        except Exception as e:
            self.log_to_terminal(f"错误: 加载代码失败 - {str(e)}")

    def log_to_terminal(self, message):
        """向终端输出日志消息（主线程调用）"""
        self.terminal_output.insert("end", message + "\n")
        self.terminal_output.see("end")  # 滚动到底部
    
    def queue_log(self, message):
        """线程安全的日志输出方法"""
        self.output_queue.put(message)

    def execute_blockly_code_threaded(self, code):
        """在线程中执行Blockly代码"""
        try:
            # 解析代码为AST，以便逐行执行
            try:
                tree = ast.parse(code)
            except SyntaxError as e:
                self.queue_log(f"语法错误: {str(e)}")
                self.reset_execution_state()
                return
            
            # 创建自定义执行环境
            exec_globals = {
                '__builtins__': __builtins__,
                'print': self.blockly_print_threaded,
                'get_detection_result': self.blockly_get_detection_result_threaded,
                'get_bounding_box': self.get_bounding_box_threaded,
                'get_bounding_box_center': self.get_bounding_box_center_threaded,
                'get_world_coordinates': self.get_world_coordinates_threaded,
                'move_to': self.blockly_move_to_threaded,
                'open_gripper': self.blockly_open_gripper_threaded,
                'close_gripper': self.blockly_close_gripper_threaded,
                'go_home': self.blockly_go_home_threaded,
                'calculate_distance': self.blockly_calculate_distance_threaded,
                'wait': self.blockly_wait_threaded,
                'math': math,
                'time': time,
            }
            
            exec_locals = {}
            
            # 执行代码
            exec(code, exec_globals, exec_locals)
            
            self.queue_log("代码执行完成")
            
        except Exception as e:
            self.queue_log(f"执行错误: {str(e)}")
            import traceback
            error_details = traceback.format_exc()
            self.queue_log(f"详细错误信息:\n{error_details}")
        finally:
            # 重置执行状态（在主线程中执行）
            self.parent_frame.after(0, self.reset_execution_state)
    
    def blockly_print_threaded(self, *args, **kwargs):
        """线程安全的自定义print函数"""
        message = " ".join(str(arg) for arg in args)
        self.queue_log(message)

    def blockly_get_detection_result_threaded(self, camera_id=0):
        """线程安全的获取检测结果函数"""
        try:
            # 检查检测是否启用
            if not self.vision_frame.detection_enabled:
                self.queue_log("检测功能未启用")
                return []
            
            # 获取当前激活的相机
            active_cameras = self.vision_frame.controller.get_active_cameras()
            if not active_cameras:
                self.queue_log("没有激活的相机")
                return []
            
            # 确定要使用的相机索引
            if camera_id < len(active_cameras):
                camera_index = active_cameras[camera_id]
            else:
                # 如果指定的camera_id超出范围，使用第一个激活的相机
                camera_index = active_cameras[0]
                self.queue_log(f"相机ID {camera_id} 超出范围，使用相机 {camera_index}")
            
            # 获取保存的检测结果
            detection_results, label = self.get_detection_results(camera_index)

            if detection_results:
                objects = []
                for i, result in enumerate(detection_results):
                    # 根据实际检测器返回的数据结构进行适配
                    obj = {
                        'id': i,
                        'label': label,
                        'confidence': result.get('confidence', 0.0),
                        'bbox': result.get('bbox', [0, 0, 0, 0]),  # 检测器返回的是'box'字段
                        'center': result.get('center', None)
                    }
                    
                    # 如果没有center信息，从bbox计算
                    if obj['center'] is None and len(obj['bbox']) >= 4:
                        x1, y1, x2, y2 = obj['bbox']
                        obj['center'] = ((x1 + x2) / 2, (y1 + y2) / 2)
                    
                    objects.append(obj)
                
                self.queue_log(f"相机 {camera_index} 检测到 {len(objects)} 个对象")
                return objects
            else:
                self.queue_log(f"相机 {camera_index} 没有检测到对象")
                return []
                
        except Exception as e:
            self.queue_log(f"获取检测结果失败: {str(e)}")
            return []

    def get_bounding_box_threaded(self, obj):
        """线程安全的获取边界框函数"""
        try:
            if isinstance(obj, dict):
                if 'bbox' in obj:
                    bbox = obj['bbox']
                    self.queue_log(f"对象边界框: {bbox}")
                    return bbox
                elif 'box' in obj:
                    # 如果直接从检测器获取，可能是'box'字段
                    bbox = obj['box']
                    self.queue_log(f"对象边界框: {bbox}")
                    return bbox
                else:
                    self.queue_log("对象中没有边界框信息")
                    return [0, 0, 0, 0]
            else:
                self.queue_log("无效的对象格式")
                return [0, 0, 0, 0]
                
        except Exception as e:
            self.queue_log(f"获取边界框失败: {str(e)}")
            return [0, 0, 0, 0]

    def get_bounding_box_center_threaded(self, bbox):
        """线程安全的计算边界框中心点函数"""
        try:
            if len(bbox) >= 4:
                x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
                
                # 计算中心点
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                
                center = {'x': center_x, 'y': center_y}
                self.queue_log(f"边界框 [x1={x1}, y1={y1}, x2={x2}, y2={y2}] 中心: {center}")
                return center
            else:
                self.queue_log("无效的边界框格式")
                return {'x': 0, 'y': 0}
                
        except Exception as e:
            self.queue_log(f"计算中心点失败: {str(e)}")
            return {'x': 0, 'y': 0}

    def get_world_coordinates_threaded(self, pixel_x, pixel_y, z_depth_mm=0):
        """线程安全的世界坐标转换函数"""
        try:
            # 检查是否有手眼标定结果
            if self.vision_frame.calibration_result is None:
                self.queue_log("警告: 未完成手眼标定，无法获取准确的世界坐标")
                return 0, 0, z_depth_mm
            
            # 获取当前机器人位置和姿态
            target_position = self.vision_frame.kinematics_frame.target_position
            target_orientation = np.radians(self.vision_frame.kinematics_frame.target_orientation)
            
            # 获取当前帧的图像尺寸
            image_size = None
            if self.vision_frame.current_frame is not None:
                height, width = self.vision_frame.current_frame.shape[:2]
                image_size = (width, height)
            
            # 使用controller的project_to_plane方法计算世界坐标
            success, x_mm, y_mm, z_mm = self.vision_frame.controller.project_to_plane(
                target_position, target_orientation, 
                pixel_x=pixel_x, pixel_y=pixel_y, 
                image_size=image_size
            )
            
            if success:
                self.queue_log(f"世界坐标: x={x_mm:.3f}mm, y={y_mm:.3f}mm, z={z_mm:.3f}mm")
                return x_mm, y_mm, z_mm
            else:
                self.queue_log("世界坐标转换失败")
                return 0, 0, z_depth_mm
                
        except Exception as e:
            self.queue_log(f"获取世界坐标失败: {str(e)}")
            return 0, 0, z_depth_mm

    def blockly_move_to_threaded(self, x, y, z, roll=None, pitch=None, yaw=None):
        """线程安全的机器人移动函数"""
        try:
            # 检查是否需要停止执行
            if self.stop_execution:
                self.queue_log("移动操作被中断")
                return False
            
            # 处理姿态参数：如果没有提供，使用NaN表示没有约束
            roll = np.nan if roll is None else roll
            pitch = np.nan if pitch is None else pitch
            yaw = np.nan if yaw is None else yaw
            
            self.queue_log(f"移动到位置: x={x:.2f}mm, y={y:.2f}mm, z={z:.2f}mm")
            
            # 根据是否有姿态约束来显示不同的日志
            orientation_constraints = []
            if not np.isnan(roll):
                orientation_constraints.append(f"roll={roll:.1f}°")
            if not np.isnan(pitch):
                orientation_constraints.append(f"pitch={pitch:.1f}°")
            if not np.isnan(yaw):
                orientation_constraints.append(f"yaw={yaw:.1f}°")
            
            if orientation_constraints:
                self.queue_log(f"姿态约束: {', '.join(orientation_constraints)}")
            else:
                self.queue_log("姿态约束: 无约束")
            
            # 将毫米转换为米，并更新运动学框架的目标位置和姿态
            if hasattr(self.vision_frame, 'kinematics_frame'):
                # 更新目标位置（转换为米）
                target_position = np.array([x/1000, y/1000, z/1000])
                self.vision_frame.kinematics_frame.target_position = target_position
                
                # 使用after方法在主线程中更新UI
                def update_ui():
                    try:
                        # 更新UI中的位置输入框
                        for i, entry in enumerate(self.vision_frame.kinematics_frame.target_entries):
                            entry.delete(0, tk.END)
                            entry.insert(0, f"{target_position[i]:.6f}")
                        
                        # 包含NaN的角度值
                        orientation_rad = np.array([roll, pitch, yaw])
                        # 只对非NaN值进行弧度转换
                        mask = ~np.isnan(orientation_rad)
                        orientation_rad[mask] = np.radians(orientation_rad[mask])
                        
                        # 调用update_p方法
                        self.vision_frame.kinematics_frame.update_p(
                            target_position, 
                            orientation_rad
                        )
                        self.vision_frame.kinematics_frame.send_to_robot()
                    except Exception as e:
                        self.queue_log(f"UI更新失败: {str(e)}")
                
                self.parent_frame.after(0, update_ui)
                
                self.queue_log("移动操作完成")
                return True
            else:
                self.queue_log("警告: 运动学框架不可用")
                return False
                
        except Exception as e:
            self.queue_log(f"移动操作失败: {str(e)}")
            return False
    
    def blockly_wait_threaded(self, seconds):
        """线程安全的等待函数"""
        try:
            self.queue_log(f"等待 {seconds} 秒...")
            
            # 分段等待，以便能够响应停止信号
            total_time = 0
            step = 0.1  # 每次等待0.1秒
            while total_time < seconds and not self.stop_execution:
                time.sleep(min(step, seconds - total_time))
                total_time += step
            
            if self.stop_execution:
                self.queue_log("等待被中断")
            else:
                self.queue_log("等待完成")
            
        except Exception as e:
            self.queue_log(f"等待操作失败: {str(e)}")

    def blockly_open_gripper_threaded(self):
        """线程安全的打开夹爪函数"""
        try:
            if self.stop_execution:
                self.queue_log("夹爪操作被中断")
                return False
                
            self.queue_log("打开夹爪")
            
            # 使用after方法在主线程中更新UI
            def update_gripper_ui():
                try:
                    kinematics_frame = self.vision_frame.kinematics_frame
                    
                    # 根据工具控制类型设置夹爪状态
                    if hasattr(kinematics_frame, 'gripper_switch'):
                        # Signal控制类型
                        kinematics_frame.gripper_switch.select()
                        kinematics_frame.on_gripper_toggle()
                    elif hasattr(kinematics_frame, 'gripper_slider'):
                        # Uniform movable控制类型
                        open_value = kinematics_frame.tool_group[0]["limit"]["upper"]
                        kinematics_frame.gripper_slider.set(open_value)
                        kinematics_frame.on_uniform_gripper_change(open_value)
                    elif hasattr(kinematics_frame, 'gripper_sliders'):
                        # Independent movable控制类型
                        for i, slider in enumerate(kinematics_frame.gripper_sliders):
                            if i < len(kinematics_frame.tool_group):
                                joint = kinematics_frame.tool_group[i]
                                open_value = joint["limit"]["upper"]
                                slider.set(open_value)
                                kinematics_frame.on_independent_gripper_change(i)
                    
                    # 发送命令到机器人
                    kinematics_frame.send_to_robot()
                except Exception as e:
                    self.queue_log(f"夹爪UI更新失败: {str(e)}")
            
            self.parent_frame.after(0, update_gripper_ui)
            
            self.queue_log("夹爪已设置为打开状态")
            return True
                
        except Exception as e:
            self.queue_log(f"打开夹爪失败: {str(e)}")
            return False

    def blockly_close_gripper_threaded(self):
        """线程安全的关闭夹爪函数"""
        try:
            if self.stop_execution:
                self.queue_log("夹爪操作被中断")
                return False
                
            self.queue_log("关闭夹爪")
            
            # 使用after方法在主线程中更新UI
            def update_gripper_ui():
                try:
                    kinematics_frame = self.vision_frame.kinematics_frame
                    
                    # 根据工具控制类型设置夹爪状态
                    if hasattr(kinematics_frame, 'gripper_switch'):
                        # Signal控制类型
                        kinematics_frame.gripper_switch.deselect()
                        kinematics_frame.on_gripper_toggle()
                    elif hasattr(kinematics_frame, 'gripper_slider'):
                        # Uniform movable控制类型
                        close_value = kinematics_frame.tool_group[0]["limit"]["lower"]
                        kinematics_frame.gripper_slider.set(close_value)
                        kinematics_frame.on_uniform_gripper_change(close_value)
                    elif hasattr(kinematics_frame, 'gripper_sliders'):
                        # Independent movable控制类型
                        for i, slider in enumerate(kinematics_frame.gripper_sliders):
                            if i < len(kinematics_frame.tool_group):
                                joint = kinematics_frame.tool_group[i]
                                close_value = joint["limit"]["lower"]
                                slider.set(close_value)
                                kinematics_frame.on_independent_gripper_change(i)
                    
                    # 发送命令到机器人
                    kinematics_frame.send_to_robot()
                except Exception as e:
                    self.queue_log(f"夹爪UI更新失败: {str(e)}")
            
            self.parent_frame.after(0, update_gripper_ui)
            
            self.queue_log("夹爪已设置为关闭状态")
            return True
                
        except Exception as e:
            self.queue_log(f"关闭夹爪失败: {str(e)}")
            return False

    def blockly_go_home_threaded(self):
        """线程安全的回到初始位置函数"""
        try:
            if self.stop_execution:
                self.queue_log("回到初始位置操作被中断")
                return False
                
            self.queue_log("机器人回到初始位置")
            
            # 使用after方法在主线程中调用home方法
            def go_home():
                try:
                    self.vision_frame.kinematics_frame.home()
                    self.vision_frame.kinematics_frame.send_to_robot()
                except Exception as e:
                    self.queue_log(f"回到初始位置失败: {str(e)}")
            
            self.parent_frame.after(0, go_home)
                
            self.queue_log("已到达初始位置")
            return True
            
        except Exception as e:
            self.queue_log(f"回到初始位置失败: {str(e)}")
            return False

    def blockly_calculate_distance_threaded(self, point1, point2):
        """线程安全的计算距离函数"""
        try:
            # 处理不同格式的点坐标
            if isinstance(point1, dict):
                x1, y1 = point1.get('x', 0), point1.get('y', 0)
            elif isinstance(point1, (list, tuple)) and len(point1) >= 2:
                x1, y1 = point1[0], point1[1]
            else:
                x1, y1 = 0, 0
                
            if isinstance(point2, dict):
                x2, y2 = point2.get('x', 0), point2.get('y', 0)
            elif isinstance(point2, (list, tuple)) and len(point2) >= 2:
                x2, y2 = point2[0], point2[1]
            else:
                x2, y2 = 0, 0
            
            # 计算欧几里得距离
            distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            
            self.queue_log(f"距离计算: 点1({x1:.2f}, {y1:.2f}) 到 点2({x2:.2f}, {y2:.2f}) = {distance:.2f}")
            return distance
            
        except Exception as e:
            self.queue_log(f"计算距离失败: {str(e)}")
            return 0 
