import os
import datetime
import webbrowser
import urllib.request
import json
from PIL import Image
import customtkinter as ctk
import tkinter.ttk as ttk
from tkinter import messagebox

from utils.resource_loader import ResourceLoader
from utils.config import Config

class HelpFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=0)

        self.github_icon = ctk.CTkImage(
            Image.open(ResourceLoader.get_asset_path(os.path.join("icons", "github_white.png"))).convert("RGBA"), 
            size=(30, 30)
        )
        self.website_icon = ctk.CTkImage(
            Image.open(ResourceLoader.get_asset_path(os.path.join("icons", "website_white.png"))).convert("RGBA"), 
            size=(26, 26)
        )
        self.email_icon = ctk.CTkImage(
            Image.open(ResourceLoader.get_asset_path(os.path.join("icons", "email_white.png"))).convert("RGBA"), 
            size=(26, 26)
        )
        
        self.about_items = [
            ("Version", Config.version),
            ("Release date", Config.release_date),
            ("Developer", "NoMan Robotics"),
            ("Features", "Motion Planning, Trajectory Optimisation, Simulation, G-code, Trajectory Optimization, LLM, Vision"),
            ("OS Platforms", "Windows>=10, Ubuntu>=20.04, MacOS>=13"),
            ("License", "Proprietary License (Core) / AGPL-3.0 (Non-core components)"),
            ("Language", "English, 中文，日本語"),
            ("Official Website", "https://nomanrobotics.com")
        ]
        
        self.setup_help_frame()
        self.setup_about_frame()
        self.setup_contact_frame()
        self.setup_trademark_frame()

    def setup_help_frame(self):
        self.help_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.help_frame.grid(row=0, column=0, padx=0, pady=(21,10), sticky="nsew")
        self.help_frame.grid_columnconfigure(0, weight=1)
        self.help_frame.grid_rowconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self.help_frame, fg_color="transparent")
        self.tabview.grid(row=0, column=0, padx=10, sticky="nsew")

        self.tab_general = self.tabview.add(Config.current_lang["tab_general"])
        self.tab_controller = self.tabview.add(Config.current_lang["tab_controller"])
        self.tab_kinematics = self.tabview.add(Config.current_lang["tab_kinematics"])
        self.tab_vision = self.tabview.add(Config.current_lang["tab_vision"])

        self.general_textbox = self.add_tab_content(self.tab_general, Config.current_lang["general_help"])
        self.controller_textbox = self.add_tab_content(self.tab_controller, Config.current_lang["controller_help"])
        self.kinematics_textbox = self.add_tab_content(self.tab_kinematics, Config.current_lang["kinematics_help"])
        self.vision_textbox = self.add_tab_content(self.tab_vision, Config.current_lang["vision_help"])

        self.tabview.set(Config.current_lang["tab_general"])

    def setup_about_frame(self):
        self.about_frame = ctk.CTkFrame(self, fg_color="#B3B3B3")
        self.about_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.about_label = ctk.CTkLabel(self.about_frame, text=Config.current_lang["app_information"], anchor='w')
        self.about_label.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                        background="#DBDBDB",
                        foreground="black",
                        rowheight=30,
                        fieldbackground="#DBDBDB",
                        bordercolor="#343638",
                        borderwidth=0)
        style.map('Treeview', background=[('selected', '#22559b')])
        style.configure("Treeview.Heading",
                        background="#565b5e",
                        foreground="white",
                        relief="flat")
        style.map("Treeview.Heading",
                background=[('active', '#3484F0')])

        # 计算树状视图的高度
        row_height = 30  # 每行的高度
        header_height = 30  # 表头的高度
        num_rows = len(self.about_items)  # 实际的行数
        total_height = (num_rows * row_height) + header_height

        self.about_tree = ttk.Treeview(self.about_frame, columns=("Item", "Value"), show="headings", style="Treeview", height=num_rows)
        self.about_tree.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=30, pady=(30,10))

        self.about_tree.heading("Item", text=Config.current_lang["item"])
        self.about_tree.heading("Value", text=Config.current_lang["value"])

        self.about_tree.column("Item", width=100, anchor="w")
        self.about_tree.column("Value", width=350, anchor="w")

        self.update_about_tree()

        # 设置树状视图的固定高度
        self.about_tree.configure(height=num_rows)

        # 添加检查更新按钮
        self.check_update_button = ctk.CTkButton(
            self.about_frame,
            text=Config.current_lang["check_update"],
            command=self.check_for_updates,
            width=135,
            height=30
        )
        self.check_update_button.grid(row=2, column=0, columnspan=3, pady=(10,15), sticky="e", padx=20)

        self.about_frame.grid_rowconfigure(1, weight=1)
        self.about_frame.grid_columnconfigure(0, weight=1)

    def update_about_tree(self):
        for item in self.about_tree.get_children():
            self.about_tree.delete(item)
        
        for key, value in self.about_items:
            try:
                self.about_tree.insert("", "end", values=(Config.current_lang.get(key, key), value))
            except KeyError:
                print(f"Warning: Missing translation for '{key}'")
                self.about_tree.insert("", "end", values=(key, value))

    def setup_contact_frame(self):
        self.contact_frame = ctk.CTkFrame(self, fg_color="#B3B3B3")
        self.contact_frame.grid(row=2, column=0, padx=20, pady=(21,40), sticky="ew")
        self.freques_label = ctk.CTkLabel(self.contact_frame, text=Config.current_lang["contact_us"], anchor='w')
        self.freques_label.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10)
        
        self.button_frame = ctk.CTkFrame(self.contact_frame, fg_color="transparent")
        self.button_frame.grid(row=1, column=0, columnspan=3, pady=10)
        
        self.github_button = ctk.CTkButton(
            self.button_frame, 
            image=self.github_icon, 
            text="GitHub",
            compound="left",
            width=120,
            height=40,
            fg_color="transparent",
            command=lambda: self.open_url("https://github.com/NoManRobotics")
        )
        self.github_button.pack(side="left", padx=5, pady=(10,5))
        
        self.website_button = ctk.CTkButton(
            self.button_frame, 
            image=self.website_icon, 
            text=Config.current_lang["website"],
            compound="left",
            width=120,
            height=40,
            fg_color="transparent",
            command=lambda: self.open_url("https://nomanrobotics.com/")
        )
        self.website_button.pack(side="left", padx=5, pady=(10,5))
        
        self.email_button = ctk.CTkButton(
            self.button_frame, 
            image=self.email_icon, 
            text=Config.current_lang["email"],
            compound="left",
            width=120,
            height=40,
            fg_color="transparent",
            command=lambda: self.open_email("nomanrobotics@hotmail.com")
        )
        self.email_button.pack(side="left", padx=5, pady=(10,5))

        self.contact_frame.grid_columnconfigure(0, weight=1)
        self.contact_frame.grid_columnconfigure(1, weight=1)
        self.contact_frame.grid_columnconfigure(2, weight=1)

    def setup_trademark_frame(self):
        self.trademark_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.trademark_frame.grid(row=3, column=0, padx=20, pady=10, sticky="sew")

        current_year = datetime.datetime.now().year
        self.copyright_label = ctk.CTkLabel(self.trademark_frame, text=f"© 2023-{current_year} NoMan Robotics All Rights Reserved")
        self.copyright_label.pack(side="left", padx=(0, 10), pady=10)

        self.logo_image = ctk.CTkImage(
            Image.open(ResourceLoader.get_asset_path(os.path.join("icons", "noman_logo_tm.png"))), 
            size=(100, 79)
        )
        self.logo_label = ctk.CTkLabel(self.trademark_frame, image=self.logo_image, text="")
        self.logo_label.pack(side="right", padx=10, pady=10)

    def open_url(self, url):
        webbrowser.open(url)

    def open_email(self, email):
        webbrowser.open(f"mailto:{email}")
    
    def check_for_updates(self):
        """检查 GitHub 上的最新版本"""
        try:
            # 显示检查中的状态
            self.check_update_button.configure(state="disabled", text=Config.current_lang.get("checking", "Checking..."))
            self.update()
            
            # GitHub API URL
            api_url = "https://api.github.com/repos/NoManRobotics/noman-app/releases/latest"
            
            # 创建请求
            request = urllib.request.Request(api_url)
            request.add_header('User-Agent', 'NoMan-App-Update-Checker')
            
            # 获取最新版本信息
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode())
                latest_version = data.get('tag_name', '').lstrip('v')
                release_url = data.get('html_url', 'https://github.com/NoManRobotics/noman-app/releases')
                
            # 比较版本号
            current_version = Config.version
            
            if self.compare_versions(latest_version, current_version) > 0:
                # 有新版本
                message = Config.current_lang.get(
                    "update_available", 
                    f"New version {latest_version} is available!\nYour current version: {current_version}\n\nWould you like to visit the download page?"
                ).format(latest_version=latest_version, current_version=current_version)
                
                result = messagebox.askyesno(
                    Config.current_lang.get("update_title", "Update Available"),
                    message
                )
                
                if result:
                    webbrowser.open(release_url)
            else:
                # 已是最新版本
                message = Config.current_lang.get(
                    "up_to_date",
                    f"You are using the latest version {current_version}!"
                ).format(current_version=current_version)
                
                messagebox.showinfo(
                    Config.current_lang.get("update_title", "Update Check"),
                    message
                )
                
        except urllib.error.URLError:
            messagebox.showerror(
                Config.current_lang.get("error", "Error"),
                Config.current_lang.get("network_error", "Unable to connect to GitHub. Please check your internet connection.")
            )
        except Exception as e:
            messagebox.showerror(
                Config.current_lang.get("error", "Error"),
                Config.current_lang.get("update_check_error", f"Error checking for updates: {str(e)}")
            )
        finally:
            # 恢复按钮状态
            self.check_update_button.configure(state="normal", text=Config.current_lang.get("check_update", "Check Update"))
    
    def compare_versions(self, version1, version2):
        """
        比较两个版本号
        返回: 1 if version1 > version2, -1 if version1 < version2, 0 if equal
        """
        try:
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]
            
            # 补齐长度
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))
            
            # 逐位比较
            for v1, v2 in zip(v1_parts, v2_parts):
                if v1 > v2:
                    return 1
                elif v1 < v2:
                    return -1
            return 0
        except:
            return 0

    def add_tab_content(self, tab, content):
        textbox = ctk.CTkTextbox(tab, wrap="word", fg_color="#B3B3B3", text_color="black")
        textbox.pack(expand=True, fill="both", padx=2, pady=10)
        
        # 获取底层的 Tkinter 文本小部件
        tk_textbox = textbox._textbox
        tk_textbox.configure(padx=10, pady=10)
        
        # 定义标签
        tk_textbox.tag_configure("title", font=("Arial", 16, "bold"))
        tk_textbox.tag_configure("subtitle", font=("Arial", 14, "bold"))
        tk_textbox.tag_configure("bold", font=("Arial", 12, "bold"))
        tk_textbox.tag_configure("italic", font=("Arial", 12, "italic"))
        tk_textbox.tag_configure("underline", underline=True)
        
        # 插入格式化的内容
        lines = content.split('\n')
        for line in lines:
            if line.startswith('# '):
                tk_textbox.insert("end", line[2:] + '\n', "title")
            elif line.startswith('## '):
                tk_textbox.insert("end", line[3:] + '\n', "subtitle")
            elif '**' in line:
                parts = line.split('**')
                for i, part in enumerate(parts):
                    if i % 2 == 1:
                        tk_textbox.insert("end", part, "bold")
                    else:
                        tk_textbox.insert("end", part)
                tk_textbox.insert("end", '\n')
            elif '*' in line:
                parts = line.split('*')
                for i, part in enumerate(parts):
                    if i % 2 == 1:
                        tk_textbox.insert("end", part, "italic")
                    else:
                        tk_textbox.insert("end", part)
                tk_textbox.insert("end", '\n')
            elif line.startswith('- '):
                tk_textbox.insert("end", "  • " + line[2:] + '\n')
            else:
                tk_textbox.insert("end", line + '\n')
        
        textbox.configure(state="disabled")  # 使文本框只读
        return textbox

    def update_texts(self):
        current_tab = self.tabview.get()
        current_tabs = list(self.tabview._tab_dict.keys())

        new_names = [
            Config.current_lang["tab_general"],
            Config.current_lang["tab_controller"],
            Config.current_lang["tab_kinematics"],
            Config.current_lang["tab_vision"]
        ]
        
        # 创建新的标签名称字典，确保没有重复
        updated_tabs = {}
        for old_name, new_name in zip(current_tabs, new_names):
            if old_name != new_name:
                tab = self.tabview._tab_dict[old_name]
                # 检查新名称是否已经存在于updated_tabs中
                # 如果存在则添加唯一标识
                base_name = new_name
                counter = 1
                while new_name in updated_tabs:
                    new_name = f"{base_name}_{counter}"
                    counter += 1
                updated_tabs[new_name] = tab
            else:
                updated_tabs[old_name] = self.tabview._tab_dict[old_name]
        
        # 清空并重建tab字典
        self.tabview._tab_dict.clear()
        self.tabview._tab_dict.update(updated_tabs)
        
        # 更新name_list
        self.tabview._name_list = list(updated_tabs.keys())
        
        # 更新segmented按钮
        self.tabview._segmented_button.configure(values=self.tabview._name_list)

        self.general_textbox.configure(state="normal")
        self.general_textbox._textbox.delete("1.0", "end")
        self.add_formatted_content(self.general_textbox._textbox, Config.current_lang["general_help"])
        self.general_textbox.configure(state="disabled")

        self.controller_textbox.configure(state="normal")
        self.controller_textbox._textbox.delete("1.0", "end")
        self.add_formatted_content(self.controller_textbox._textbox, Config.current_lang["controller_help"])
        self.controller_textbox.configure(state="disabled")

        self.kinematics_textbox.configure(state="normal")
        self.kinematics_textbox._textbox.delete("1.0", "end")
        self.add_formatted_content(self.kinematics_textbox._textbox, Config.current_lang["kinematics_help"])
        self.kinematics_textbox.configure(state="disabled")

        self.vision_textbox.configure(state="normal")
        self.vision_textbox._textbox.delete("1.0", "end")
        self.add_formatted_content(self.vision_textbox._textbox, Config.current_lang["vision_help"])
        self.vision_textbox.configure(state="disabled")

        self.about_tree.heading("Item", text=Config.current_lang["item"])
        self.about_tree.heading("Value", text=Config.current_lang["value"])
        self.freques_label.configure(text=Config.current_lang["contact_us"])
        self.website_button.configure(text=Config.current_lang["website"])
        self.email_button.configure(text=Config.current_lang["email"])
        self.about_label.configure(text=Config.current_lang["app_information"])
        self.check_update_button.configure(text=Config.current_lang["check_update"])

        self.update_about_tree()

        current_year = datetime.datetime.now().year
        self.copyright_label.configure(text=f"© {current_year}-{current_year+1} {Config.current_lang['copyright_text']}")

        # 尝试选择之前选中的标签页，如果不存在则选择第一个
        if current_tab in self.tabview._tab_dict:
            self.tabview.set(current_tab)
        elif len(self.tabview._name_list) > 0:
            self.tabview.set(self.tabview._name_list[0])

    def add_formatted_content(self, tk_textbox, content):
        # 设置默认字体为 Calibri
        tk_textbox.configure(font=("Calibri", 12))
        
        # 配置不同样式的标签
        tk_textbox.tag_configure("title", font=("Calibri", 18, "bold"))
        tk_textbox.tag_configure("subtitle", font=("Calibri", 16, "bold"))
        tk_textbox.tag_configure("bold", font=("Calibri", 12, "bold"))
        tk_textbox.tag_configure("underline", font=("Calibri", 12), underline=True)
        
        lines = content.split('\n')
        for line in lines:
            if line.startswith('# '):
                tk_textbox.insert("end", line[2:] + '\n', "title")
            elif line.startswith('## '):
                tk_textbox.insert("end", line[3:] + '\n', "subtitle")
            elif '**' in line:
                parts = line.split('**')
                for i, part in enumerate(parts):
                    if i % 2 == 1:
                        tk_textbox.insert("end", part, "bold")
                    else:
                        tk_textbox.insert("end", part)
                tk_textbox.insert("end", '\n')
            elif '*' in line:
                # 原来用斜体的部分现在只插入普通文本
                tk_textbox.insert("end", line.replace('*', '') + '\n')
            elif line.startswith('- '):
                tk_textbox.insert("end", "  • " + line[2:] + '\n')
            else:
                tk_textbox.insert("end", line + '\n')
