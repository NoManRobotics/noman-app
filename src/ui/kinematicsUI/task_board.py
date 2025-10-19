import tkinter as tk
import customtkinter as ctk
import json
import numpy as np
import time
from dataclasses import dataclass
from typing import List, Union, Any

from utils.config import Config

@dataclass
class Worker:
    """工作流单元数据类"""
    work_type: str  # "plan", "delay", "loop", "tool"
    data: Union[List[np.ndarray], int, dict, Any]  # 轨迹数组、延时时间、循环数据或工具状态
    
    def __post_init__(self):
        """验证数据类型的一致性"""
        if self.work_type == "plan" and not isinstance(self.data, list):
            raise ValueError("plan类型的data必须是轨迹列表")
        elif self.work_type == "delay" and not isinstance(self.data, (int, float)):
            raise ValueError("delay类型的data必须是数字")
        elif self.work_type == "loop" and not isinstance(self.data, dict):
            raise ValueError("loop类型的data必须是字典")
        elif self.work_type == "tool":
            # tool类型可以是任何数据类型，不做限制
            pass

class TaskPosition(ctk.CTkFrame):
    """单个任务框架"""
    def __init__(self, parent, task_data, index, delete_callback=None, move_to_callback=None, update_callback=None, task_board=None):
        super().__init__(parent)
        self.configure(fg_color="white", corner_radius=0)
        self.task_data = task_data
        self.index = index
        self.delete_callback = delete_callback
        self.move_to_callback = move_to_callback
        self.update_callback = update_callback
        self.task_board = task_board
        
        # 创建内容
        self.create_widgets()
        
    def create_widgets(self):
        # 标题栏
        self.title_frame = ctk.CTkFrame(self, fg_color="#B3B3B3", corner_radius=0)
        self.title_frame.pack(fill="x", padx=0, pady=0)
        
        # 动作标题 (Action + ID + Type)
        action_type = self.task_data.get('type', 'position')
        title_label = ctk.CTkLabel(self.title_frame, 
                                 text=f"Action {self.index} ({action_type})")
        title_label.pack(side="left", padx=5, pady=2)
        
        # 创建圆形执行指示器（初始隐藏）
        self.indicator = ctk.CTkFrame(self.title_frame, 
                                    fg_color="#41d054", 
                                    corner_radius=8,
                                    width=10, 
                                    height=10)
        # 不立即pack，保持隐藏状态
        
        # 按钮区域
        btn_frame = ctk.CTkFrame(self.title_frame, fg_color="transparent")
        btn_frame.pack(side="right", padx=5)
        
        # 如果不是延时点，才显示移动按钮
        if action_type != 'delay' and action_type != 'repeat':
            move_btn = ctk.CTkButton(btn_frame, 
                                   text="→",
                                   width=20,
                                   height=20,
                                   hover_color="#41d054",
                                   command=self.move_to_position)
            move_btn.pack(side="left", padx=2, pady=2)
        
        # 删除按钮
        delete_btn = ctk.CTkButton(btn_frame, 
                                 text="×",
                                 width=20,
                                 height=20,
                                 hover_color="#41d054",
                                 command=self.delete_position)
        delete_btn.pack(side="left", padx=2, pady=2)
        
        # 信息显示区域
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(fill="x", padx=5, pady=2)
        
        # 根据类型显示不同的信息
        if action_type == 'delay':
            # 延时输入框和标签
            delay_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
            delay_frame.pack(fill="x")
            
            delay_label = ctk.CTkLabel(delay_frame, text="延时(秒):")
            delay_label.pack(side="left", padx=5)
            
            self.delay_entry = ctk.CTkEntry(delay_frame, width=60)
            self.delay_entry.pack(side="left", padx=5)
            self.delay_entry.insert(0, str(self.task_data['time']))
            
            # 添加确认按钮
            confirm_btn = ctk.CTkButton(delay_frame,
                                       text="确认",
                                       width=50,
                                       height=24,
                                       hover_color="#41d054",
                                       command=lambda: self.update_delay(None))
            confirm_btn.pack(side="left", padx=5)
        elif action_type == 'tool':
            # 工具状态显示和编辑
            tool_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
            tool_frame.pack(fill="x")
            
            tool_label = ctk.CTkLabel(tool_frame, text="工具状态:")
            tool_label.pack(side="left", padx=5)
            
            # 根据actuation类型创建不同的控件
            actuation = self.task_board.kinematics_frame.actuation if self.task_board else None
            
            if actuation == "independent movable":
                # 独立可移动型：创建多个输入框
                self.tool_entries = []
                tool_values = self.task_data.get('tool_value', [])
                if not isinstance(tool_values, list):
                    tool_values = [tool_values]
                
                for i, value in enumerate(tool_values):
                    entry_frame = ctk.CTkFrame(tool_frame, fg_color="transparent")
                    entry_frame.pack(side="left", padx=2)
                    
                    # 添加标签显示工具索引
                    index_label = ctk.CTkLabel(entry_frame, text=f"T{i+1}:", font=("Arial", 10))
                    index_label.pack(side="left")
                    
                    # 创建输入框
                    tool_entry = ctk.CTkEntry(entry_frame, width=50)
                    tool_entry.pack(side="left", padx=2)
                    tool_entry.insert(0, str(value))
                    self.tool_entries.append(tool_entry)
                
                # 添加确认按钮
                confirm_btn = ctk.CTkButton(tool_frame,
                                           text="确认",
                                           width=50,
                                           height=24,
                                           hover_color="#41d054",
                                           command=lambda: self.update_tool(None))
                confirm_btn.pack(side="left", padx=5)
            else:
                # 信号控制型或统一可移动型：创建单个输入框
                self.tool_entry = ctk.CTkEntry(tool_frame, width=60)
                self.tool_entry.pack(side="left", padx=5)
                self.tool_entry.insert(0, str(self.task_data['tool_value']))
                
                # 添加确认按钮
                confirm_btn = ctk.CTkButton(tool_frame,
                                           text="确认",
                                           width=50,
                                           height=24,
                                           hover_color="#41d054",
                                           command=lambda: self.update_tool(None))
                confirm_btn.pack(side="left", padx=5)
        elif action_type == 'repeat':
            # 重复次数输入框和标签
            repeat_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
            repeat_frame.pack(fill="x")
            
            repeat_label = ctk.CTkLabel(repeat_frame, text="重复次数:")
            repeat_label.pack(side="left", padx=5)
            
            self.repeat_entry = ctk.CTkEntry(repeat_frame, width=60)
            self.repeat_entry.pack(side="left", padx=5)
            
            # 添加确认按钮
            confirm_btn = ctk.CTkButton(repeat_frame,
                                       text="确认",
                                       width=50,
                                       height=24,
                                       hover_color="#41d054",
                                       command=lambda: self.update_repeat(None))
            confirm_btn.pack(side="left", padx=5)
            
            # 显示当前重复次数,默认为0
            count = self.task_data.get('count', 0)
            self.repeat_entry.insert(0, str(count))
            
            # 在标签中添加提示
            hint_label = ctk.CTkLabel(repeat_frame, text="(-1 = 无限循环)", font=("Arial", 10))
            hint_label.pack(side="left", padx=5)
            
            # 显示要重复的动作范围
            range_text = f"重复动作 {self.task_data['start_index'] + 1} 到 {self.task_data['end_index']}"
            range_label = ctk.CTkLabel(info_frame, text=range_text)
            range_label.pack(fill="x", pady=(5,0))
        else:
            # 显示位置信息
            joints_str = ", ".join([f"{j:.1f}°" for j in self.task_data['joints']])
            joints_label = ctk.CTkLabel(info_frame, text=f"Joints: [{joints_str}]", anchor="w")
            joints_label.pack(fill="x", padx=5)
            
            pos = self.task_data['position']
            pos_label = ctk.CTkLabel(info_frame, text=f"TCP: X={pos[0]:.3f}, Y={pos[1]:.3f}, Z={pos[2]:.3f}", anchor="w")
            pos_label.pack(fill="x", padx=5)
            
            if 'orientation' in self.task_data:
                ori = self.task_data['orientation']
                ori_label = ctk.CTkLabel(info_frame, text=f"RPY: R={ori[0]:.1f}°, P={ori[1]:.1f}°, Y={ori[2]:.1f}°", anchor="w")
                ori_label.pack(fill="x", padx=5)
    
    def update_delay(self, event=None):
        """更新延时值"""
        try:
            new_delay = float(self.delay_entry.get())
            if new_delay > 0:
                self.task_data['time'] = new_delay
                if self.update_callback:
                    self.update_callback(self.index - 1, self.task_data)
            else:
                # 恢复原值
                self.delay_entry.delete(0, tk.END)
                self.delay_entry.insert(0, str(self.task_data['time']))
        except ValueError:
            # 恢复原值
            self.delay_entry.delete(0, tk.END)
            self.delay_entry.insert(0, str(self.task_data['time']))
    
    def delete_position(self):
        if self.delete_callback:
            self.delete_callback(self.index)
            
    def move_to_position(self):
        if self.move_to_callback:
            self.move_to_callback(self.task_data)

    def update_repeat(self, event=None):
        """更新重复次数"""
        try:
            count = int(self.repeat_entry.get())
            if count > 0 or count == -1:  # 允许正数或-1
                self.task_data['count'] = count
                if self.update_callback:
                    self.update_callback(self.index - 1, self.task_data)
            else:
                raise ValueError
        except ValueError:
            # 恢复原值
            self.repeat_entry.delete(0, tk.END)
            count = self.task_data.get('count', -1)
            self.repeat_entry.insert(0, str(count))

    def update_tool(self, event=None):
        """更新工具状态"""
        try:
            # 根据actuation类型获取值
            actuation = self.task_board.kinematics_frame.actuation if self.task_board else None
            
            if actuation == "independent movable":
                # 独立可移动型：获取所有滑块的值
                tool_values = [float(entry.get()) for entry in self.tool_entries]
                self.task_data['tool_value'] = tool_values
            else:
                # 信号控制型或统一可移动型：获取单个输入框的值
                new_tool_value = float(self.tool_entry.get())
                self.task_data['tool_value'] = new_tool_value
            
            if self.update_callback:
                self.update_callback(self.index - 1, self.task_data)
        except ValueError:
            # 恢复原值
            if actuation == "independent movable":
                tool_values = self.task_data.get('tool_value', [])
                if not isinstance(tool_values, list):
                    tool_values = [tool_values]
                for i, entry in enumerate(self.tool_entries):
                    if i < len(tool_values):
                        entry.delete(0, tk.END)
                        entry.insert(0, str(tool_values[i]))
            else:
                self.tool_entry.delete(0, tk.END)
                self.tool_entry.insert(0, str(self.task_data['tool_value']))
    
    def get_tool_units(self):
        """获取工具的单位"""
        if self.task_board:
            return self.task_board.get_tool_units()
        else:
            return "°"  # 默认单位
    
    def show_indicator(self):
        """显示执行指示器"""
        self.indicator.pack(side="right", padx=(5, 10), pady=2)
    
    def hide_indicator(self):
        """隐藏执行指示器"""
        self.indicator.pack_forget()

class TaskBoard:
    def __init__(self, kinematics_frame):
        self.kinematics_frame = kinematics_frame
        self.task_sequence = []
        self.dialog = None
        self.create_window()
        
    def create_window(self):
        """创建任务板窗口"""
        self.dialog = ctk.CTkToplevel(self.kinematics_frame)
        self.dialog.title("Task Board")
        
        # 设置窗口位置
        self.dialog_x = self.kinematics_frame.winfo_rootx() + self.kinematics_frame.winfo_width() + 10
        self.dialog_y = self.kinematics_frame.winfo_rooty() - 45
        
        config_geometry = Config.geometry
        height = config_geometry.split('x')[1]  # 提取高度部分
        self.dialog.geometry(f"420x{height}+{self.dialog_x}+{self.dialog_y}")
        
        # 主框架
        self.main_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 顶部控制区
        self.control_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.control_frame.pack(fill="x", padx=5, pady=5)
        
        # 添加延时按钮
        self.add_delay_btn = ctk.CTkButton(self.control_frame,
                                    text="Add Delay",
                                    width=80,
                                    hover_color="#41d054",
                                    command=self.add_delay)
        self.add_delay_btn.pack(side="right", padx=5)
        
        # 添加位置按钮
        self.add_btn = ctk.CTkButton(self.control_frame,
                               text="Add Position",
                               width=90,
                               hover_color="#41d054",
                               command=self.add_position)
        self.add_btn.pack(side="right", padx=5)
        
        # 添加重复按钮
        self.repeat_btn = ctk.CTkButton(self.control_frame,
                                text="Repeat",
                                width=80,
                                hover_color="#41d054",
                                command=self.add_repeat)
        self.repeat_btn.pack(side="right", padx=5)
        
        # 添加工具按钮
        self.add_tool_btn = ctk.CTkButton(self.control_frame,
                                text="Add Tool",
                                width=80,
                                hover_color="#41d054",
                                command=self.add_tool)
        self.add_tool_btn.pack(side="right", padx=5)
        
        # 位置列表区域
        self.positions_frame = ctk.CTkScrollableFrame(self.main_frame, fg_color="transparent")
        self.positions_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 底部按钮区
        self.bottom_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.bottom_frame.pack(fill="x", padx=5, pady=5)
        
        # 导入/导出按钮
        self.import_btn = ctk.CTkButton(self.bottom_frame,
                                 text="Import",
                                 width=80,
                                 hover_color="#41d054",
                                 command=self.import_task)
        self.import_btn.pack(side="left", padx=5)
        
        self.export_btn = ctk.CTkButton(self.bottom_frame,
                                 text="Export",
                                 width=80,
                                 hover_color="#41d054",
                                 command=self.export_task)
        self.export_btn.pack(side="left", padx=5)

        # 执行任务按钮
        self.execute_btn = ctk.CTkButton(self.bottom_frame,
                                  text="Execute Task",
                                  width=100,
                                  hover_color="#41d054",
                                  command=self.execute_task)
        self.execute_btn.pack(side="right", padx=5)
        
        # 加载已有序列
        self.refresh_sequence()
        
        # 窗口关闭处理
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def refresh_sequence(self):
        """刷新任务序列显示"""
        # 清除现有显示
        for widget in self.positions_frame.winfo_children():
            widget.destroy()
            
        # 重新加载所有任务
        for i, task in enumerate(self.task_sequence, 1):
            position_frame = TaskPosition(
                self.positions_frame,
                task,
                i,
                self.delete_position,
                self.move_to_position,
                self.update_task,
                self
            )
            position_frame.pack(fill="x", padx=5, pady=2)
            
    def add_position(self):
        """添加当前位置"""
        current_angles = self.kinematics_frame.joint_angles.copy()  # 创建副本
        current_pos = self.kinematics_frame.target_position
        current_orientation = self.kinematics_frame.target_orientation
        
        if current_pos is not None and len(current_pos) > 0:
            position_data = {
                'type': 'position',
                'id': len(self.task_sequence),
                'joints': current_angles,  # 使用副本
                'position': current_pos.tolist() if isinstance(current_pos, np.ndarray) else current_pos.copy(),  # 创建副本
                'orientation': current_orientation.tolist() if isinstance(current_orientation, np.ndarray) else current_orientation.copy(),  # 创建副本
            }
            
            # 添加到序列
            self.task_sequence.append(position_data)
            
            # 刷新显示
            self.refresh_sequence()

    def add_tool(self):
        """添加工具状态"""
        current_tool = self.get_current_tool_value()  # 获取当前工具值
        
        # 根据actuation类型确定工具值的格式
        actuation = self.kinematics_frame.actuation
        if actuation == "independent movable":
            # 确保返回的是列表格式
            if not isinstance(current_tool, list):
                current_tool = [current_tool] if current_tool is not None else []
        else:
            # 确保返回的是单个值
            if isinstance(current_tool, list):
                current_tool = current_tool[0] if current_tool else 0.0
        
        tool_data = {
            'type': 'tool',
            'id': len(self.task_sequence),
            'tool_value': current_tool
        }
        
        # 添加到序列
        self.task_sequence.append(tool_data)
        
        # 刷新显示
        self.refresh_sequence()

    def add_delay(self):
        """添加延时点"""
        delay_data = {
            'type': 'delay',
            'time': 1.0,  # 默认1秒
            'id': len(self.task_sequence)  # 添加ID
        }
        
        # 添加到序列
        self.task_sequence.append(delay_data)
        
        # 刷新显示
        self.refresh_sequence()

    def add_repeat(self):
        """添加重复动作"""
        if len(self.task_sequence) == 0:
            self.kinematics_frame.update_terminal("没有可重复的动作")
            return
            
        repeat_data = {
            'type': 'repeat',
            'id': len(self.task_sequence),
            'count': 0,  # 默认重复次数为0
            'start_index': 0,
            'end_index': len(self.task_sequence) - 1
        }
        
        # 添加到序列
        self.task_sequence.append(repeat_data)
        
        # 刷新显示
        self.refresh_sequence()
        
        # 更新日志
        self.kinematics_frame.update_terminal(
            f"已添加重复动作 Action {len(self.task_sequence)}:\n"
            f"重复范围: Action {repeat_data['start_index'] + 1} 到 {repeat_data['end_index'] + 1}"
        )
            
    def delete_position(self, index):
        """删除指定任务"""
        real_index = index - 1
        if 0 <= real_index < len(self.task_sequence):
            # 删除任务
            self.task_sequence.pop(real_index)
            
            # 更新剩余任务的ID
            for i, task in enumerate(self.task_sequence):
                task['id'] = i
            
            # 刷新显示
            self.refresh_sequence()
            self.kinematics_frame.update_terminal(f"已删除任务 Action {index}")
            
    def move_to_position(self, task_data):
        """移动到指定位置"""
        if task_data.get('type') == 'position':
            # 获取位置和姿态数据
            position = np.array(task_data['position'])
            orientation = np.array(task_data['orientation'])
            
            # 先更新kinematics_frame的目标位置和姿态属性
            self.kinematics_frame.target_position = position
            self.kinematics_frame.target_orientation = orientation
            
            # 调用update_p方法更新关节角度（传入弧度制姿态）
            self.kinematics_frame.update_p(position, np.radians(orientation))
            
            # 更新工具角度
            if 'tool' in task_data:
                self.set_tool_value(task_data['tool'])

    def import_task(self):
        """导入任务数据"""
        try:
            filename = tk.filedialog.askopenfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")]
            )
            
            if filename:
                with open(filename, 'r') as f:
                    data = json.load(f)
                    
                self.task_sequence.clear()
                
                # 加载新序列并确保每个任务都有正确的id
                for i, task in enumerate(data['sequence']):
                    task['id'] = i  # 确保id正确
                    self.task_sequence.append(task)
                
                # 刷新显示
                self.refresh_sequence()
                    
                self.kinematics_frame.update_terminal(f"已导入任务数据，共{len(data['sequence'])}个任务")
                
        except Exception as e:
            self.kinematics_frame.update_terminal(f"导入失败: {str(e)}")
            
    def export_task(self):
        """导出任务数据"""
        if not self.task_sequence:
            self.kinematics_frame.update_terminal("没有可导出的任务")
            return
            
        try:
            filename = tk.filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")]
            )
            
            if filename:
                # 创建任务数据的深拷贝
                task_data = {'sequence': []}
                
                # 转换每个任务数据
                for task in self.task_sequence:
                    task_copy = task.copy()
                    # 确保所有 NumPy 数组都被转换为列表
                    for key, value in task_copy.items():
                        if isinstance(value, np.ndarray):
                            task_copy[key] = value.tolist()
                    task_data['sequence'].append(task_copy)
                
                with open(filename, 'w') as f:
                    json.dump(task_data, f, indent=2)
                    
                self.kinematics_frame.update_terminal(f"任务数据已导出到: {filename}")
                
        except Exception as e:
            self.kinematics_frame.update_terminal(f"导出失败: {str(e)}")
            
    def on_closing(self):
        """窗口关闭处理"""
        self.kinematics_frame.task_var.set(False)
        self.dialog.destroy()
        # 不删除实例，让kinematics_frame负责通过winfo_exists()检查来管理
        
    def destroy(self):
        """销毁窗口"""
        if self.dialog:
            self.dialog.destroy()
        
    def update_task(self, index, new_data):
        """更新任务数据"""
        if 0 <= index < len(self.task_sequence):
            self.task_sequence[index] = new_data

    def get_current_tool_value(self):
        """获取当前工具值，根据执行器类型返回适当的值"""
        try:
            actuation = getattr(self.kinematics_frame, 'actuation', None)
            
            if actuation == "signal":
                # 信号控制型：开关状态（0或1）
                if hasattr(self.kinematics_frame, 'gripper_switch'):
                    return 1.0 if self.kinematics_frame.gripper_switch.get() else 0.0
                else:
                    return 0.0  # 默认关闭状态
                    
            elif actuation == "uniform movable":
                # 统一可移动型：单个滑块
                if hasattr(self.kinematics_frame, 'gripper_slider'):
                    return float(self.kinematics_frame.gripper_slider.get())
                else:
                    return 0.0
                    
            elif actuation == "independent movable":
                # 独立可移动型：返回所有滑块的值
                if hasattr(self.kinematics_frame, 'gripper_sliders') and self.kinematics_frame.gripper_sliders:
                    return [float(slider.get()) for slider in self.kinematics_frame.gripper_sliders]
                else:
                    return []
            else:
                return 0.0  # 无工具或未知类型
        except Exception:
            return 0.0  # 出错时返回默认值



    def set_tool_value(self, value):
        """设置工具值，根据执行器类型设置相应的控件"""
        try:
            actuation = getattr(self.kinematics_frame, 'actuation', None)
            
            if actuation == "signal":
                # 信号控制型：设置工具命令值并同步开关状态
                if hasattr(self.kinematics_frame, 'tool_command') and self.kinematics_frame.tool_command:
                    # 对于信号控制型，大于0.5认为是打开状态
                    if isinstance(value, (int, float)):
                        tool_value = 1 if value > 0.5 else 0
                    else:
                        tool_value = 0  # 默认关闭
                    
                    # 设置工具命令值
                    self.kinematics_frame.tool_command[0] = tool_value
                    
                    # 同步开关的视觉状态
                    if hasattr(self.kinematics_frame, 'gripper_switch'):
                        # 临时禁用回调，避免重复触发
                        current_command = self.kinematics_frame.gripper_switch.cget("command")
                        self.kinematics_frame.gripper_switch.configure(command=None)
                        
                        # 根据工具值设置开关状态
                        if tool_value > 0.5:
                            if not self.kinematics_frame.gripper_switch.get():
                                self.kinematics_frame.gripper_switch.toggle()
                        else:
                            if self.kinematics_frame.gripper_switch.get():
                                self.kinematics_frame.gripper_switch.toggle()
                        
                        # 恢复回调
                        self.kinematics_frame.gripper_switch.configure(command=current_command)
                    
                    # 更新机器人状态
                    self.kinematics_frame.robot_state.update_state('tool_state', self.kinematics_frame.tool_command, sender=self.kinematics_frame)
                    
            elif actuation == "uniform movable":
                # 统一可移动型：设置单个滑块
                if hasattr(self.kinematics_frame, 'gripper_slider'):
                    if isinstance(value, (int, float)):
                        self.kinematics_frame.gripper_slider.set(value)
                        self.kinematics_frame.on_uniform_gripper_change(value)
                    
            elif actuation == "independent movable":
                # 独立可移动型：根据值的类型决定如何设置
                if hasattr(self.kinematics_frame, 'gripper_sliders') and self.kinematics_frame.gripper_sliders:
                    if isinstance(value, list):
                        # 值是列表，分别设置每个滑块
                        for i, (slider, val) in enumerate(zip(self.kinematics_frame.gripper_sliders, value)):
                            slider.set(val)
                            self.kinematics_frame.on_independent_gripper_change(i)
                    else:
                        # 值是单个数字，设置所有滑块到相同的值
                        for i, slider in enumerate(self.kinematics_frame.gripper_sliders):
                            slider.set(value)
                            self.kinematics_frame.on_independent_gripper_change(i)
                        
        except Exception as e:
            self.kinematics_frame.update_terminal(f"设置工具值时出错: {str(e)}")

    def get_tool_units(self):
        """获取工具的单位，根据工具类型返回相应的单位"""
        def get_unit_for_joint(joint_type):
            """根据关节类型返回对应的单位"""
            if joint_type == "revolute":
                return "°"
            elif joint_type == "prismatic":
                return "m"
            else:
                return ""  # 其他类型无单位
        
        try:
            # 首先检查执行器类型
            actuation = getattr(self.kinematics_frame, 'actuation', None)
            if actuation == "signal":
                # 信号控制型（toggle）无单位
                return ""
            
            if hasattr(self.kinematics_frame, 'tool_group') and self.kinematics_frame.tool_group:
                tool_group = self.kinematics_frame.tool_group
                if len(tool_group) == 1:
                    # 单个工具关节
                    joint_type = tool_group[0]["type"]
                    return get_unit_for_joint(joint_type)
                else:
                    # 多个工具关节，返回每个关节的单位
                    return [get_unit_for_joint(joint["type"]) for joint in tool_group]
            else:
                return "°"  # 默认单位
        except Exception:
            return "°"  # 出错时返回默认单位

    def sequence_to_waypoints(self, position_tasks: List[dict]) -> List[List[List[float]]]:
        """将位置任务序列转换为waypoints格式
        
        Args:
            position_tasks: 位置任务列表，每个任务包含position和orientation
            
        Returns:
            waypoints: 格式为 [[[x,y,z],[r,p,y]], ...] 的路径点列表
        """
        waypoints = []
        
        for task in position_tasks:
            if task.get('type') != 'position':
                continue
                
            # 提取位置信息 [x, y, z]
            position = task.get('position', [0.0, 0.0, 0.0])
            if isinstance(position, np.ndarray):
                position = position.tolist()
            
            # 提取姿态信息 [r, p, y] (度数)
            orientation = task.get('orientation', [0.0, 0.0, 0.0])
            orientation = np.radians(orientation).tolist()
            
            # 构建单个waypoint: [[x,y,z], [r,p,y]]
            waypoint = [position, orientation]
            waypoints.append(waypoint)
        
        return waypoints

    def workflow_decompose(self, init_solution: np.ndarray = None) -> List[Worker]:
        """将任务序列分解为独立的工作流单元
        
        Args:
            init_solution: 初始关节角度解，如果为None则使用当前关节角度
            
        Returns:
            List[Worker]: 工作流单元列表，每个单元包含work_type和对应的data
        """
        if not self.task_sequence:
            return []
        
        # 如果没有提供初始解，使用当前关节角度
        if init_solution is None:
            init_solution = np.radians(self.kinematics_frame.joint_angles)
        
        workflows = []
        i = 0
        current_solution = init_solution.copy()  # 跟踪当前的关节角度解
        
        while i < len(self.task_sequence):
            current_task = self.task_sequence[i]
            task_type = current_task.get('type', 'position')
            
            if task_type == 'delay':
                # 延时任务：创建delay类型的worker
                delay_time = current_task.get('time', 1.0)
                worker = Worker(work_type="delay", data=delay_time)
                workflows.append(worker)
                i += 1
                
            elif task_type == 'tool':
                # 工具任务：创建tool类型的worker
                tool_value = current_task.get('tool_value', 0.0)
                worker = Worker(work_type="tool", data=tool_value)
                workflows.append(worker)
                i += 1
                
            elif task_type == 'repeat':
                # 循环任务：创建loop类型的worker
                loop_data = {
                    'count': current_task.get('count', 1),
                    'start_index': current_task.get('start_index', 0),
                    'end_index': current_task.get('end_index', 0),
                    'sub_workflows': []  # 递归分解循环内的任务
                }
                
                # 提取循环范围内的任务并递归分解
                start_idx = current_task.get('start_index', 0)
                end_idx = current_task.get('end_index', 0)
                
                if start_idx <= end_idx < len(self.task_sequence):
                    sub_sequence = self.task_sequence[start_idx:end_idx + 1]
                    # 创建临时TaskBoard实例来递归分解子序列
                    temp_task_board = TaskBoard.__new__(TaskBoard)
                    temp_task_board.task_sequence = sub_sequence
                    temp_task_board.kinematics_frame = self.kinematics_frame  # 需要共享kinematics_frame
                    loop_data['sub_workflows'] = temp_task_board.workflow_decompose(current_solution)
                
                worker = Worker(work_type="loop", data=loop_data)
                workflows.append(worker)
                i += 1
                
            elif task_type == 'position':
                # 位置任务：收集连续的位置任务形成plan
                position_tasks = []
                
                # 收集从当前位置开始的连续位置任务（直到遇到非position任务为止）
                while (i < len(self.task_sequence) and 
                       self.task_sequence[i].get('type', 'position') == 'position'):
                    position_tasks.append(self.task_sequence[i])
                    i += 1
                
                # 处理位置任务序列
                if position_tasks:
                    waypoints = self.sequence_to_waypoints(position_tasks)
                    
                    # 使用planner生成轨迹
                    if len(waypoints) > 1:
                        # 多个waypoints
                        target_pos = np.array(waypoints[-1][0])
                        target_orn = np.array(waypoints[-1][1])
                        middle_waypoints = waypoints[1:-1] if len(waypoints) > 2 else None
                        
                        result = self.kinematics_frame.planner.plan(
                            init_solution=current_solution,
                            target_position=target_pos,
                            target_orientation=target_orn,
                            waypoints=middle_waypoints
                        )
                        
                        if result.success:
                            plan_worker = Worker(work_type="plan", data=result.trajectory)
                            workflows.append(plan_worker)
                            # 更新current_solution为轨迹的最后一个关节角度
                            current_solution = result.trajectory[-1].copy()
                    else:
                        # 单个waypoint
                        target_pos = np.array(waypoints[0][0])
                        target_orn = np.radians(waypoints[0][1])
                        
                        result = self.kinematics_frame.planner.solve(
                            init_solution=current_solution,
                            target_position=target_pos,
                            target_orientation=target_orn
                        )
                        
                        if result.success:
                            plan_worker = Worker(work_type="plan", data=result.trajectory)
                            workflows.append(plan_worker)
                            # 更新current_solution为轨迹的最后一个关节角度
                            current_solution = result.trajectory[-1].copy()
                # 注意：这里不需要再次递增i，因为while循环已经处理了
            else:
                # 未知任务类型，跳过
                i += 1
        
        return workflows

    def execute_task(self):
        """执行任务序列 - 使用workflow_decompose"""
        try:
            if not self.task_sequence:
                self.kinematics_frame.update_terminal("没有可执行的任务")
                return

            # 获取当前关节角度作为初始解
            init_solution = np.radians(self.kinematics_frame.joint_angles)
            
            # 分解工作流
            workflows = self.workflow_decompose(init_solution)
            
            if not workflows:
                self.kinematics_frame.update_terminal("工作流分解失败，没有可执行的任务")
                return

            self.kinematics_frame.update_terminal(f"开始执行工作流，共 {len(workflows)} 个工作单元")
            
            # 执行每个工作流单元
            for i, worker in enumerate(workflows):
                self.kinematics_frame.update_terminal(f"执行工作单元 {i+1}/{len(workflows)}: {worker.work_type}")
                
                if worker.work_type == "plan":
                    self._execute_plan_worker(worker)
                elif worker.work_type == "delay":
                    self._execute_delay_worker(worker)
                elif worker.work_type == "tool":
                    self._execute_tool_worker(worker)
                elif worker.work_type == "loop":
                    self._execute_loop_worker(worker)
                else:
                    self.kinematics_frame.update_terminal(f"未知的工作类型: {worker.work_type}")

            self.kinematics_frame.update_terminal("任务序列执行完成")
            
        except Exception as e:
            self.kinematics_frame.update_terminal(f"执行任务时出错: {str(e)}")

    def _execute_plan_worker(self, worker):
        """执行plan类型的工作单元"""
        try:
            trajectory = worker.data
            if not trajectory:
                self.kinematics_frame.update_terminal("轨迹为空，跳过执行")
                return

            self.kinematics_frame.update_terminal(f"执行轨迹，包含 {len(trajectory)} 个路径点")
            
            # 检查协议连接状态（只检查一次）
            is_connected = self.kinematics_frame.protocol_class.is_connected()
            
            # 执行轨迹中的每个路径点
            for i, waypoint in enumerate(trajectory):
                # 转换为度数
                joint_angles_deg = np.degrees(waypoint)
                
                if is_connected:
                    # 准备命令
                    joint_command = ",".join(f"{angle:.2f}" for angle in joint_angles_deg) + "\n"
                    
                    # 重试机制：如果队列满，等待并重试
                    max_retries = 2  # 最多重试100次
                    retry_count = 0
                    command_sent = False
                    
                    while retry_count < max_retries:
                        # 发送关节运动命令
                        self.kinematics_frame.protocol_class.send("EXEC\n")
                        self.kinematics_frame.protocol_class.send(joint_command)
                        
                        # 等待执行完成
                        response, isReplied = self.kinematics_frame.protocol_class.receive(timeout=5, expected_signal="CP0")
                        
                        if isReplied:
                            # 命令成功进入队列
                            command_sent = True
                            break
                        elif response and any("QFULL" in str(r) for r in response):
                            # 队列满，等待后重试
                            retry_count += 1
                            time.sleep(0.05)  # 等待50ms让队列有机会处理
                        else:
                            # 其他错误
                            self.kinematics_frame.update_terminal(f"关节执行超时，路径点 {i+1}")
                            return
                    
                    if not command_sent:
                        self.kinematics_frame.update_terminal(f"队列持续满载，无法执行路径点 {i+1}")
                        return
                else:
                    # 模拟执行延时
                    time.sleep(0.1)  # 模拟执行时间
                
                # 更新关节滑块显示当前位置（无论是否连接协议都需要更新）
                self._update_joint_sliders(joint_angles_deg)
                
                self.kinematics_frame.update_terminal(f"路径点 {i+1}/{len(trajectory)}: {[f'{angle:.2f}°' for angle in joint_angles_deg]}")
                
        except Exception as e:
            self.kinematics_frame.update_terminal(f"执行轨迹时出错: {str(e)}")

    def _execute_delay_worker(self, worker):
        """执行delay类型的工作单元"""
        delay_time = worker.data
        self.kinematics_frame.update_terminal(f"延时 {delay_time} 秒")
        time.sleep(delay_time)

    def _execute_tool_worker(self, worker):
        """执行tool类型的工作单元"""
        try:
            tool_value = worker.data
            self.kinematics_frame.update_terminal(f"设置工具状态: {tool_value}")
            
            # 设置工具状态
            self.set_tool_value(tool_value)
            
            # 检查协议连接状态
            is_connected = self.kinematics_frame.protocol_class.is_connected()
            
            if not is_connected:
                self.kinematics_frame.update_terminal("未连接协议，模拟设置工具状态")
                return

            # 根据actuation类型发送不同的工具命令
            actuation = self.kinematics_frame.actuation
            
            if actuation == "independent movable" and isinstance(tool_value, list):
                # 独立可移动型：发送多个值
                tool_command = f"M280,{','.join(str(v) for v in tool_value)}\n"
            else:
                # 信号控制型或统一可移动型：发送单个值
                tool_command = f"M280,{tool_value}\n"
            
            self.kinematics_frame.protocol_class.send(tool_command)

            _, isReplied = self.kinematics_frame.protocol_class.receive(timeout=5, expected_signal="TP0")
            if not isReplied:
                self.kinematics_frame.update_terminal("工具命令执行超时")
            else:
                self.kinematics_frame.update_terminal(f"工具命令执行完成: {tool_command.strip()}")
                
        except Exception as e:
            self.kinematics_frame.update_terminal(f"执行工具命令时出错: {str(e)}")

    def _execute_loop_worker(self, worker):
        """执行loop类型的工作单元"""
        try:
            loop_data = worker.data
            count = loop_data.get('count', 1)
            sub_workflows = loop_data.get('sub_workflows', [])
            
            if count == -1:
                self.kinematics_frame.update_terminal("开始无限循环执行")
                current_count = 0
                while True:  # 无限循环，需要用户手动停止
                    current_count += 1
                    self.kinematics_frame.update_terminal(f"开始第 {current_count} 次循环")
                    self._execute_sub_workflows(sub_workflows)
                    self.kinematics_frame.update_terminal(f"完成第 {current_count} 次循环")
            else:
                self.kinematics_frame.update_terminal(f"开始循环执行，重复 {count} 次")
                for i in range(count):
                    self.kinematics_frame.update_terminal(f"开始第 {i+1}/{count} 次循环")
                    self._execute_sub_workflows(sub_workflows)
                    self.kinematics_frame.update_terminal(f"完成第 {i+1}/{count} 次循环")
                    
        except Exception as e:
            self.kinematics_frame.update_terminal(f"执行循环时出错: {str(e)}")

    def _execute_sub_workflows(self, sub_workflows):
        """执行子工作流"""
        for i, sub_worker in enumerate(sub_workflows):
            if sub_worker.work_type == "plan":
                self._execute_plan_worker(sub_worker)
            elif sub_worker.work_type == "delay":
                self._execute_delay_worker(sub_worker)
            elif sub_worker.work_type == "tool":
                self._execute_tool_worker(sub_worker)
            # 注意：这里不处理嵌套的loop，避免无限递归

    def _update_joint_sliders(self, joint_angles_deg):
        """更新kinematics_frame的关节滑块显示"""
        try:
            # 更新kinematics_frame的joint_angles
            self.kinematics_frame.joint_angles = np.array(joint_angles_deg)
            
            # 更新关节滑块和标签
            for i, (slider, value_label) in enumerate(self.kinematics_frame.joint_entries):
                if i < len(joint_angles_deg):
                    slider.set(joint_angles_deg[i])
                    value_label.configure(text=f"{joint_angles_deg[i]:.1f}°")
            
            # 更新机器人状态
            self.kinematics_frame.robot_state.update_state('joint_angles', joint_angles_deg, sender=self.kinematics_frame)
            
        except Exception as e:
            self.kinematics_frame.update_terminal(f"更新关节滑块时出错: {str(e)}")
