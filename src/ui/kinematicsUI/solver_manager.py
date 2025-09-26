import os
import shutil
import inspect
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
from tkinter import ttk

from utils.config import Config

class SolverManager(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        
        self.title("Custom Solver Manager")
        
        # 计算窗口位置
        main_window_x = parent.winfo_rootx()
        main_window_y = parent.winfo_rooty()
        main_window_width = parent.winfo_width()
        
        solver_x = main_window_x + main_window_width + 10
        solver_y = main_window_y - 38
        
        self.geometry(f"400x300+{solver_x}+{solver_y}")
        self.resizable(False, False)
        
        self.parent = parent
        
        # 使用Config获取基础目录，设置自定义求解器目录
        base_dir = Config.get_path()
        self.custom_solvers_dir = os.path.join(base_dir, 'custom_solvers')
        print(f"自定义求解器目录: {self.custom_solvers_dir}")
        
        # 确保自定义求解器目录存在
        if not os.path.exists(self.custom_solvers_dir):
            os.makedirs(self.custom_solvers_dir, exist_ok=True)
        
        self.setup_ui()
        self.load_solvers()

    def setup_ui(self):
        # 求解器列表
        self.list_frame = ctk.CTkFrame(self)
        self.list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 使用 Treeview 替代 Listbox
        self.solver_tree = ttk.Treeview(
            self.list_frame, 
            columns=("name", "path"),
            show="headings",
            height=6
        )
        
        # 设置列标题和宽度
        self.solver_tree.heading("name", text="求解器名称")
        self.solver_tree.heading("path", text="保存位置")
        self.solver_tree.column("name", width=120)
        self.solver_tree.column("path", width=240)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(
            self.list_frame,
            orient="vertical",
            command=self.solver_tree.yview
        )
        self.solver_tree.configure(yscrollcommand=scrollbar.set)
        
        # 布局
        self.solver_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0), pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
        # 按钮区域
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.add_button = ctk.CTkButton(
            self.button_frame,
            text="添加求解器",
            command=self.add_solver,
            width=120
        )
        self.add_button.pack(side=tk.LEFT, padx=5)
        
        self.delete_button = ctk.CTkButton(
            self.button_frame,
            text="删除求解器",
            command=self.delete_solver,
            width=120
        )
        self.delete_button.pack(side=tk.LEFT, padx=5)
        
        self.example_button = ctk.CTkButton(
            self.button_frame,
            text="下载示例代码",
            command=self.download_example,
            width=120
        )
        self.example_button.pack(side=tk.LEFT, padx=5)

    def load_solvers(self):
        """加载所有自定义求解器"""
        # 清空现有项目
        for item in self.solver_tree.get_children():
            self.solver_tree.delete(item)
            
        if os.path.exists(self.custom_solvers_dir):
            for file in os.listdir(self.custom_solvers_dir):
                if file.endswith('.py'):
                    solver_name = file[:-3]
                    self.solver_tree.insert(
                        "",
                        tk.END,
                        values=(solver_name, self.custom_solvers_dir)
                    )

    def validate_solver_file(self, file_path: str) -> bool:
        """验证求解器文件是否有效"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
                
            # 创建临时命名空间
            namespace = {}
            exec(code, namespace)
            
            # 检查必要的函数
            if 'solve' not in namespace:
                messagebox.showerror("错误", "未找到solve函数定义")
                return False
                
            # 验证函数签名
            sig = inspect.signature(namespace['solve'])
            required_params = ['solver', 'target_position', 'init_joint_angles', 'orientation']
            for param in required_params:
                if param not in sig.parameters:
                    messagebox.showerror("错误", f"solve函数缺少必要的参数: {param}")
                    return False
            
            return True
            
        except Exception as e:
            messagebox.showerror("错误", f"验证求解器文件失败: {str(e)}")
            return False

    def add_solver(self):
        """添加新的求解器文件"""
        file_path = filedialog.askopenfilename(
            title="选择求解器文件",
            filetypes=[("Python文件", "*.py")]
        )
        
        if file_path:
            try:
                # 验证求解器文件
                if not self.validate_solver_file(file_path):
                    return
                
                # 复制文件到自定义求解器目录
                filename = os.path.basename(file_path)
                dest_path = os.path.join(self.custom_solvers_dir, filename)
                
                if os.path.exists(dest_path):
                    if not messagebox.askyesno("确认", "求解器已存在，是否覆盖？"):
                        return
                
                shutil.copy2(file_path, dest_path)
                self.load_solvers()
                messagebox.showinfo("成功", "求解器添加成功")
                
                # 更新父窗口的求解器列表
                self.parent.solver_menu.configure(
                    values=self.parent.get_available_solvers()
                )
                
            except Exception as e:
                messagebox.showerror("错误", f"添加求解器失败: {str(e)}")

    def delete_solver(self):
        """删除选中的求解器"""
        selection = self.solver_tree.selection()
        if not selection:
            messagebox.showerror("错误", "请先选择一个求解器")
            return
            
        item = self.solver_tree.item(selection[0])
        name = item['values'][0]
        if messagebox.askyesno("确认", f"确定要删除求解器 {name} 吗？"):
            file_path = os.path.join(self.custom_solvers_dir, f"{name}.py")
            os.remove(file_path)
            self.load_solvers()
            
            # 更新父窗口的求解器列表
            self.parent.solver_menu.configure(
                values=self.parent.get_available_solvers()
            )

    def download_example(self):
        """复制求解器模板文件"""
        try:
            # 获取模板文件路径
            template_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                'assets', 'examples', 'solver_template.py'
            )
            
            # 选择保存位置
            save_path = filedialog.asksaveasfilename(
                title="保存求解器模板",
                defaultextension=".py",
                filetypes=[("Python文件", "*.py")],
                initialfile="custom_solver.py"
            )
            
            if save_path:
                shutil.copy2(template_path, save_path)
                messagebox.showinfo("成功", "模板文件已保存")
                
        except Exception as e:
            messagebox.showerror("错误", f"下载模板失败: {str(e)}") 
