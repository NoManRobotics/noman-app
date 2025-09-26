import re
import numpy as np
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from noman.workspace_analyzer import WorkspaceAnalyzer
from utils.config import Config


class WorkspaceFrame:
    """工作空间分析器前端UI类"""
    
    def __init__(self, kinematics_frame):
        self.kinematics_frame = kinematics_frame
        
        # 创建后端分析器实例，只传递planner
        self.workspace_analyzer = WorkspaceAnalyzer(kinematics_frame.planner)
        
        self.workspace_dialog = None
        self.figure = None
        self.canvas = None
        self.joint_entries = []
        self.progress_bar = None
        self.progress_label = None
        self.volume_label = None
        self.density_label = None
        self.analyze_button = None
        self.resolution_var = None
        self.alpha_var = None
        
        # 存储当前工作空间数据
        self.current_workspace_data = None

    def create_window(self):
        """创建工作空间分析器窗口"""
        self.workspace_dialog = ctk.CTkToplevel(self.kinematics_frame)
        self.workspace_dialog.title("Workspace Analyzer")
        
        # 设置窗口位置和大小
        dialog_x = self.kinematics_frame.winfo_rootx() + self.kinematics_frame.winfo_width() + 10
        dialog_y = self.kinematics_frame.winfo_rooty() - 30
        self.workspace_dialog.geometry(f"980x780+{dialog_x}+{dialog_y}")

        # 创建主框架
        main_frame = ctk.CTkFrame(self.workspace_dialog, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 左侧控制面板
        control_frame = ctk.CTkFrame(main_frame, width=300, fg_color="transparent")
        control_frame.pack(side="left", fill="y", padx=(0,10))
        
        # 右侧图形面板
        figure_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        figure_frame.pack(side="right", fill="both", expand=True)
        
        self._setup_control_panel(control_frame)
        self._setup_figure_panel(figure_frame)

    def _setup_control_panel(self, parent):
        """设置控制面板"""
        # 关节范围设置
        joint_ranges_frame = ctk.CTkFrame(parent, fg_color="transparent")
        joint_ranges_frame.pack(fill="x", padx=5, pady=5)
        
        self.joint_ranges_label = ctk.CTkLabel(joint_ranges_frame, text=Config.current_lang["joint_ranges"])
        self.joint_ranges_label.pack(pady=5)
        
        # 使用已有的joint_limits
        for i, (lower_limit, upper_limit) in enumerate(self.kinematics_frame.joint_limits):
            joint_frame = ctk.CTkFrame(joint_ranges_frame, fg_color="transparent")
            joint_frame.pack(fill="x", padx=5, pady=2)
            
            ctk.CTkLabel(joint_frame, text=f"Joint {i+1}:").pack(side="left", padx=5)
            
            min_var = tk.StringVar(value=str(lower_limit))
            max_var = tk.StringVar(value=str(upper_limit))
            
            min_entry = ctk.CTkEntry(joint_frame, width=60, textvariable=min_var)
            min_entry.pack(side="left", padx=5)
            ctk.CTkLabel(joint_frame, text="-").pack(side="left", padx=5)
            max_entry = ctk.CTkEntry(joint_frame, width=60, textvariable=max_var)
            max_entry.pack(side="left", padx=5)
            
            self.joint_entries.append((i, min_var, max_var))

        # 分析设置
        settings_frame = ctk.CTkFrame(parent, fg_color="transparent")
        settings_frame.pack(fill="x", padx=5, pady=5)
        
        self.analysis_settings_label = ctk.CTkLabel(settings_frame, text=Config.current_lang["analysis_settings"])
        self.analysis_settings_label.pack(pady=5)
        
        # 分辨率设置
        resolution_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        resolution_frame.pack(fill="x", padx=5, pady=2)
        self.sampling_resolution_label = ctk.CTkLabel(resolution_frame, text=Config.current_lang["sampling_resolution"])
        self.sampling_resolution_label.pack(side="left", padx=5)
        self.resolution_var = tk.StringVar(value="25")
        resolution_entry = ctk.CTkEntry(resolution_frame, width=60, textvariable=self.resolution_var)
        resolution_entry.pack(side="left", padx=5)

        # 添加Alpha值设置
        alpha_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        alpha_frame.pack(fill="x", padx=5, pady=2)
        self.alpha_value_label = ctk.CTkLabel(alpha_frame, text=Config.current_lang["alpha_value"])
        self.alpha_value_label.pack(side="left", padx=5)
        self.alpha_var = tk.StringVar(value="0.3")
        alpha_entry = ctk.CTkEntry(alpha_frame, width=60, textvariable=self.alpha_var)
        alpha_entry.pack(side="left", padx=5)

        # 分析按钮
        self.analyze_button = ctk.CTkButton(parent, 
                                          text=Config.current_lang["analyze_workspace"],
                                          command=self.start_analysis,
                                          hover_color="#41d054")
        self.analyze_button.pack(pady=(10,30))

        # 进度条区域
        progress_frame = ctk.CTkFrame(parent, fg_color="transparent")
        progress_frame.pack(fill="x", padx=5, pady=5)
        
        self.progress_label = ctk.CTkLabel(progress_frame, text=Config.current_lang["ready_to_analyze"])
        self.progress_label.pack(pady=2)
        
        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(pady=2)
        self.progress_bar.set(0)
        
        # 结果显示区域
        results_frame = ctk.CTkFrame(parent)
        results_frame.pack(fill="x", padx=5, pady=5)
        
        self.analysis_results_label = ctk.CTkLabel(results_frame, text=Config.current_lang["analysis_results"])
        self.analysis_results_label.pack(pady=5)
        
        self.volume_label = ctk.CTkLabel(results_frame, text=Config.current_lang["workspace_volume"] + " 0.000 m³")
        self.volume_label.pack(pady=2)
        
        self.density_label = ctk.CTkLabel(results_frame, text=Config.current_lang["reachable_density"] + " 0.000%")
        self.density_label.pack(pady=2)

    def _setup_figure_panel(self, parent):
        """设置图形面板"""
        # 创建按钮框架
        view_buttons_frame = ctk.CTkFrame(parent, fg_color="transparent")
        view_buttons_frame.pack(fill="x", padx=(0,5), pady=5)
        
        # 添加视角切换按钮
        ctk.CTkButton(view_buttons_frame, text="X-Y View", 
                      command=lambda: self.change_view('xy'),
                      hover_color="#41d054").pack(side="left", padx=(0,5))
        ctk.CTkButton(view_buttons_frame, text="X-Z View", 
                      command=lambda: self.change_view('xz'),
                      hover_color="#41d054").pack(side="left", padx=5)
        ctk.CTkButton(view_buttons_frame, text="Y-Z View", 
                      command=lambda: self.change_view('yz'),
                      hover_color="#41d054").pack(side="left", padx=5)
        ctk.CTkButton(view_buttons_frame, text="Reset View", 
                      command=lambda: self.change_view('reset'),
                      hover_color="#41d054").pack(side="left", padx=5)

        # 创建3D图形
        self.figure = Figure(figsize=(12, 8))
        self.ax_3d = self.figure.add_subplot(111, projection='3d', computed_zorder=False)
        
        self.canvas = FigureCanvasTkAgg(self.figure, parent)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def start_analysis(self):
        """开始工作空间分析"""
        try:
            # 获取用户输入的参数
            joint_ranges = []
            for joint_idx, min_var, max_var in self.joint_entries:
                min_val = float(min_var.get())
                max_val = float(max_var.get())
                joint_ranges.append((min_val, max_val))
            
            resolution = int(self.resolution_var.get())
            alpha = float(self.alpha_var.get())
            
            # 禁用分析按钮
            self.analyze_button.configure(state="disabled")
            
            # 调用后端分析，传递进度回调
            is_success, workspace_data, error_msg = self.workspace_analyzer.analyze_workspace(
                joint_ranges, resolution, alpha, progress_callback=self.update_progress
            )
            
            if is_success:
                # 保存工作空间数据
                self.current_workspace_data = workspace_data
                
                # 更新kinematics_frame的工作空间信息
                self.kinematics_frame.workspace['bounds'] = workspace_data['bounds'].copy()
                self.kinematics_frame.workspace['analyzed'] = True
                
                # 更新UI显示
                self.update_results(workspace_data['volume'], workspace_data['density'], workspace_data['bounds'])
                self.update_plots(workspace_data['points'], workspace_data['alpha_shape'])
                
            else:
                self.show_error(error_msg)
            
        except ValueError as e:
            self.show_error(f"输入参数错误: {str(e)}")
        except Exception as e:
            self.show_error(f"分析启动失败: {str(e)}")
        finally:
            # 重新启用分析按钮
            self.analyze_button.configure(state="normal")

    def change_view(self, view_type):
        """改变视图类型（2D投影或3D）"""
        if self.current_workspace_data and len(self.current_workspace_data['points']) > 0:
            points = self.current_workspace_data['points']
            if view_type in ['xy', 'xz', 'yz']:
                self._plot_2d_projection(points, plane=view_type)
            elif view_type == 'reset':
                self._update_view('reset')

    def _update_view(self, view_type):
        """更新3D视图的视角并显示平面轨迹"""
        if not self.current_workspace_data:
            return
            
        self.figure.clf()
        self.ax_3d = self.figure.add_subplot(111, projection='3d', computed_zorder=False)
        # 清除当前图形
        self.ax_3d.clear()
        
        points = self.current_workspace_data['points']
        bounds = self.current_workspace_data['bounds']
        
        # 重新绘制所有点
        self.ax_3d.scatter(points[:,0], points[:,1], points[:,2], 
                          c='r', marker='.', alpha=0.1, s=1)
        
        self.ax_3d.view_init(30, -60)  # 默认等轴测视图
        
        # 绘制机器人基座位置
        self.ax_3d.scatter(self.kinematics_frame.end_effector_home[0], 
                          self.kinematics_frame.end_effector_home[1],
                          self.kinematics_frame.end_effector_home[2], 
                          c='g', marker='s', s=100, label='Robot Base')
        
        # 设置轴标签
        self.ax_3d.set_xlabel('X (m)')
        self.ax_3d.set_ylabel('Y (m)')
        self.ax_3d.set_zlabel('Z (m)')
        self.ax_3d.set_title('3D Workspace')
        self.ax_3d.set_box_aspect([1,1,1])
        self.ax_3d.legend()
        
        self.canvas.draw()

    def _plot_2d_projection(self, points, plane='xy'):
        """绘制2D投影图"""
        self.figure.clf()
        ax = self.figure.add_subplot(111)
        if plane == 'xy':
            ax.scatter(points[:, 0], points[:, 1], c='r', s=1, alpha=0.3)
            ax.set_xlabel('X (m)')
            ax.set_ylabel('Y (m)')
            ax.set_title('Workspace XY Projection')
        elif plane == 'xz':
            ax.scatter(points[:, 0], points[:, 2], c='g', s=1, alpha=0.3)
            ax.set_xlabel('X (m)')
            ax.set_ylabel('Z (m)')
            ax.set_title('Workspace XZ Projection')
        elif plane == 'yz':
            ax.scatter(points[:, 1], points[:, 2], c='b', s=1, alpha=0.3)
            ax.set_xlabel('Y (m)')
            ax.set_ylabel('Z (m)')
            ax.set_title('Workspace YZ Projection')
        ax.axis('equal')
        self.canvas.draw()

    def update_progress(self, progress, message):
        """更新进度条和消息"""
        self.progress_bar.set(progress)
        self.progress_label.configure(text=message)
        if self.workspace_dialog:
            self.workspace_dialog.update()

    def update_results(self, volume, density, bounds):
        """更新分析结果显示"""
        self.volume_label.configure(text=f"工作空间体积: {volume:.3f} m³")
        self.density_label.configure(text=f"可达点密度: {density:.1f}%")
        
        # 在终端显示详细信息
        self.kinematics_frame.update_terminal(
            f"\nWorkspace analysis completed:\n" +
            f"Volume: {volume:.3f} m³\n" +
            f"Reachable point density: {density:.1f}%\n" +
            f"Bounds:\n" +
            f"X: {bounds['x']['min']:.3f} to {bounds['x']['max']:.3f}m\n" +
            f"Y: {bounds['y']['min']:.3f} to {bounds['y']['max']:.3f}m\n" +
            f"Z: {bounds['z']['min']:.3f} to {bounds['z']['max']:.3f}m"
        )

    def update_plots(self, points, alpha_shape):
        """更新3D视图"""
        # 清除图形
        self.ax_3d.clear()
        
        # 绘制3D工作空间
        self._plot_3d_workspace(points, alpha_shape)
        
        # 刷新画布
        self.canvas.draw()

    def _plot_3d_workspace(self, points, alpha_shape):
        """绘制3D工作空间"""
        # 绘制散点
        self.ax_3d.scatter(points[:,0], points[:,1], points[:,2], 
                          c='r', marker='.', alpha=0.1, s=1)
        
        # 尝试绘制Alpha Shape表面（如果支持）
        try:
            if hasattr(alpha_shape, 'plot'):
                alpha_shape.plot(ax=self.ax_3d, alpha=0.2)
        except:
            pass
        
        # 绘制机器人基座位置
        self.ax_3d.scatter(self.kinematics_frame.end_effector_home[0], 
                          self.kinematics_frame.end_effector_home[1],
                          self.kinematics_frame.end_effector_home[2], 
                          c='g', marker='s', s=100, label='Robot Base')
        
        # 设置轴标签和标题
        self.ax_3d.set_xlabel('X (m)')
        self.ax_3d.set_ylabel('Y (m)')
        self.ax_3d.set_zlabel('Z (m)')
        self.ax_3d.set_title('3D Workspace (Alpha Shape)')
        
        # 设置相等的坐标轴比例
        self.ax_3d.set_box_aspect([1,1,1])

    def show_error(self, message):
        """显示错误消息"""
        messagebox.showerror("错误", message)

    def on_closing(self):
        """窗口关闭处理"""
        if self.workspace_dialog:
            self.workspace_dialog.destroy() 

    def update_texts(self):
        """更新所有文本标签"""
        # 更新控制面板的文本标签
        self.joint_ranges_label.configure(text=Config.current_lang["joint_ranges"])
        
        self.analysis_settings_label.configure(text=Config.current_lang["analysis_settings"])
        
        self.sampling_resolution_label.configure(text=Config.current_lang["sampling_resolution"])
        
        self.alpha_value_label.configure(text=Config.current_lang["alpha_value"])
        
        self.analyze_button.configure(text=Config.current_lang["analyze_workspace"])
        
        current_text = self.progress_label.cget("text")
        if "准备分析" in current_text or "Ready to analyze" in current_text:
            self.progress_label.configure(text=Config.current_lang["ready_to_analyze"])
        
        self.analysis_results_label.configure(text=Config.current_lang["analysis_results"])
        
        # 更新结果标签 - 保持数值部分，只更新标签文本
        current_text = self.volume_label.cget("text")

        # 提取数值部分
        volume_match = re.search(r'(\d+\.\d+)', current_text)
        if volume_match:
            volume_value = volume_match.group(1)
            self.volume_label.configure(text=f"{Config.current_lang['workspace_volume']} {volume_value} m³")
        else:
            self.volume_label.configure(text=f"{Config.current_lang['workspace_volume']} 0.000 m³")
    
        current_text = self.density_label.cget("text")

        # 提取数值部分
        density_match = re.search(r'(\d+\.\d+)', current_text)
        if density_match:
            density_value = density_match.group(1)
            self.density_label.configure(text=f"{Config.current_lang['reachable_density']} {density_value}%")
        else:
            self.density_label.configure(text=f"{Config.current_lang['reachable_density']} 0.000%")
