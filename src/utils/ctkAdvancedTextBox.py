import tkinter as tk
import customtkinter as ctk
import re
from tkinter import font as tkfont

class TextLineNumbers(ctk.CTkCanvas):
    """显示行号的Canvas组件"""
    def __init__(self, *args, **kwargs):
        # 提取fg_color参数并转换为bg参数
        if "fg_color" in kwargs:
            bg_color = kwargs.pop("fg_color")
            kwargs["bg"] = bg_color
            
        # 处理border_width参数
        if "border_width" in kwargs:
            border_width = kwargs.pop("border_width")
            kwargs["borderwidth"] = border_width
            
        ctk.CTkCanvas.__init__(self, *args, **kwargs)
        self.textwidget = None
        self.font = None
        self.line_height = 0
        
    def attach(self, text_widget, font):
        """关联文本组件"""
        self.textwidget = text_widget
        self.font = font
        
        # 计算行高
        test_text = tk.Text(font=self.font)
        self.line_height = test_text.tk.call("font", "metrics", self.font, "-linespace")
        test_text.destroy()
        
    def redraw(self, *args):
        """重绘行号"""
        self.delete("all")
        
        i = self.textwidget.index("@0,0")
        while True:
            dline = self.textwidget.dlineinfo(i)
            if dline is None: 
                break
            
            y = dline[1]
            linenum = str(i).split(".")[0]
            self.create_text(2, y, anchor="nw", text=linenum, font=self.font, fill="gray50")  # 改为更深的灰色
            i = self.textwidget.index(f"{i}+1line")

class CTkAdvancedTextBox(ctk.CTkFrame):
    """
    高级文本框组件，支持动态添加和删除带参数选择功能的代码行
    """
    def __init__(self, master, font=None, code_templates=None, text_color="black", show_line_numbers=True, **kwargs):
        """
        初始化高级文本框组件
        
        Args:
            master: 父容器
            font: 字体设置
            code_templates: 代码模板字典，形如 {'函数名称': {'params': [参数列表], 'options': {参数名: [选项列表]}}}
            text_color: 文本颜色
            show_line_numbers: 是否显示行号
            **kwargs: 其他CTkFrame参数
        """
        super().__init__(master, **kwargs)
        
        # 配置参数
        self.font = font or ctk.CTkFont(family="Consolas", size=14)
        self.code_templates = code_templates or {}
        self.text_color = text_color
        self.show_line_numbers = show_line_numbers
        
        # 当前激活的下拉菜单
        self.active_dropdown = None
        self.dropdown_index = None
        
        # 代码行管理
        self.code_lines = {}  # 存储每行的信息: {line_number: {'function': func_name, 'args': dict}}
        self.next_line_id = 1  # 下一个行ID
        
        # 创建水平布局
        self.horizontal_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.horizontal_frame.pack(fill="both", expand=True)
        
        # 创建行号显示 (如果启用)
        if self.show_line_numbers:
            self.linenumbers = TextLineNumbers(
                self.horizontal_frame, 
                width=40,
                bg="white",  # 使用bg替代fg_color
                borderwidth=0,
                highlightthickness=0
            )
            self.linenumbers.pack(side="left", fill="y")
        
        # 创建内部的文本框
        self.text = tk.Text(
            self.horizontal_frame,
            font=self.font,
            wrap="word",
            fg=self.text_color,
            insertbackground=self.text_color,
            highlightthickness=0,
            relief="flat",
            state="normal"
        )
        self.text.pack(side="left", fill="both", expand=True)
        
        # 创建右侧滚动条
        self.scrollbar = ctk.CTkScrollbar(self.horizontal_frame, command=self.text.yview)
        self.scrollbar.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=self.on_textbox_scroll)
        
        # 设置标签样式
        self.text.tag_configure("param_highlight", foreground="blue", underline=True)
        
        # 设置Python语法高亮标签
        self.setup_syntax_highlighting()
        
        # 绑定事件
        self.text.bind("<Button-1>", self.on_click)
        self.text.bind("<KeyRelease>", self.on_key_release)
        self.text.bind("<<Modified>>", self.on_text_modified)
        self.text.bind("<FocusOut>", self.on_focus_out)
        
        # 添加键盘事件绑定
        self.text.bind("<Down>", self.on_key_down)
        self.text.bind("<Up>", self.on_key_up)
        self.text.bind("<Return>", self.on_key_return)
        self.text.bind("<Escape>", self.on_key_escape)
        
        # 绑定鼠标滚轮事件到文本框
        self.text.bind("<MouseWheel>", self.on_mousewheel)
        self.text.bind("<Button-4>", self.on_mousewheel)  # Linux滚轮向上
        self.text.bind("<Button-5>", self.on_mousewheel)  # Linux滚轮向下
        
        # 关联行号显示
        if self.show_line_numbers:
            self.linenumbers.attach(self.text, self.font)
            self.text.bind("<<Change>>", self.on_change)
            self.text.bind("<Configure>", self.on_change)
            # 为行号区域也绑定滚轮事件
            self.linenumbers.bind("<MouseWheel>", self.on_mousewheel)
            self.linenumbers.bind("<Button-4>", self.on_mousewheel)
            self.linenumbers.bind("<Button-5>", self.on_mousewheel)
        
        # 为整个组件绑定滚轮事件
        self.bind("<MouseWheel>", self.on_mousewheel)
        self.bind("<Button-4>", self.on_mousewheel)
        self.bind("<Button-5>", self.on_mousewheel)
        
        # 初始化标记参数的正则表达式
        self.param_patterns = self._build_param_patterns()
        
        # 当前选中的菜单项索引
        self.current_menu_index = 0
    
    def add_line(self, function_name, args=None, position="end"):
        """
        动态添加代码行
        
        Args:
            function_name: 函数名称
            args: 参数字典，形如 {'param_name': 'default_value'}
            position: 插入位置，可以是 "end", "start", 或者具体的行号索引（如 "2.0"）
        
        Returns:
            int: 添加的行ID
        """
        if function_name not in self.code_templates:
            raise ValueError(f"函数 '{function_name}' 不在代码模板中")
        
        template = self.code_templates[function_name]
        params = template.get('params', [])
        options = template.get('options', {})
        
        # 如果没有提供参数，使用默认值
        if args is None:
            args = {}
            for param in params:
                if param in options and options[param]:
                    args[param] = options[param][0]  # 使用第一个选项作为默认值
                else:
                    args[param] = ""
        
        # 构建函数调用字符串
        # 检查是否有自定义格式
        custom_format = template.get('format', None)
        
        if custom_format:
            # 使用自定义格式
            # 将args中的参数值替换到格式字符串中
            format_args = {}
            for param in params:
                value = args.get(param, "")
                if param in options:
                    # 确保值在选项中
                    if value not in options[param]:
                        value = options[param][0] if options[param] else ""
                format_args[param] = value
            
            try:
                function_call = custom_format.format(**format_args) + "\n"
            except KeyError as e:
                # 如果格式字符串中有未提供的参数，回退到默认格式
                print(f"Warning: Missing parameter {e} in format string, using default format")
                function_call = self._build_default_function_call(function_name, params, args, options)
        else:
            # 使用默认格式
            function_call = self._build_default_function_call(function_name, params, args, options)
        
        # 确定插入位置
        if position == "end":
            insert_index = "end"
        elif position == "start":
            insert_index = "1.0"
        else:
            insert_index = position
        
        # 插入代码行
        self.text.insert(insert_index, function_call)
        
        # 记录行信息
        line_id = self.next_line_id
        self.next_line_id += 1
        
        # 获取实际插入的行号
        if position == "end":
            actual_line = int(float(self.text.index("end-1c")))
        else:
            actual_line = int(float(self.text.index(insert_index)))
        
        self.code_lines[line_id] = {
            'function': function_name,
            'args': args.copy(),
            'line_number': actual_line
        }
        
        # 更新高亮和行号
        self.highlight_parameters()
        self.on_change()  # 更新行号显示
        
        # 自动滚动到新添加的行
        if position == "end":
            self.text.see("end-1c")
        else:
            self.text.see(insert_index)
        
        return line_id
    
    def _build_default_function_call(self, function_name, params, args, options):
        """构建默认格式的函数调用字符串"""
        arg_strings = []
        for param in params:
            value = args.get(param, "")
            if param in options:
                # 确保值在选项中
                if value not in options[param]:
                    value = options[param][0] if options[param] else ""
            arg_strings.append(f"{param}={value}")
        
        return f"{function_name}({', '.join(arg_strings)})\n"
    
    def delete_line(self, line_identifier):
        """
        删除代码行
        
        Args:
            line_identifier: 可以是行ID（int）或行号（str，如 "3.0"）
        
        Returns:
            bool: 是否成功删除
        """
        if isinstance(line_identifier, int):
            # 按行ID删除
            if line_identifier not in self.code_lines:
                return False
            
            line_info = self.code_lines[line_identifier]
            line_number = line_info['line_number']
            
            # 删除行
            start_index = f"{line_number}.0"
            end_index = f"{line_number + 1}.0"
            
            try:
                self.text.delete(start_index, end_index)
                del self.code_lines[line_identifier]
                
                # 更新其他行的行号
                for other_id, other_info in self.code_lines.items():
                    if other_info['line_number'] > line_number:
                        other_info['line_number'] -= 1
                
                self.highlight_parameters()
                return True
            except:
                return False
        
        elif isinstance(line_identifier, str):
            # 按行号删除
            try:
                line_number = int(float(line_identifier))
                start_index = f"{line_number}.0"
                end_index = f"{line_number + 1}.0"
                
                # 查找并删除对应的行ID记录
                line_id_to_delete = None
                for line_id, line_info in self.code_lines.items():
                    if line_info['line_number'] == line_number:
                        line_id_to_delete = line_id
                        break
                
                self.text.delete(start_index, end_index)
                
                if line_id_to_delete:
                    del self.code_lines[line_id_to_delete]
                
                # 更新其他行的行号
                for other_id, other_info in self.code_lines.items():
                    if other_info['line_number'] > line_number:
                        other_info['line_number'] -= 1
                
                self.highlight_parameters()
                return True
            except:
                return False
        
        return False
    
    def get_line_info(self, line_id):
        """
        获取指定行的信息
        
        Args:
            line_id: 行ID
        
        Returns:
            dict: 行信息，包含 'function', 'args', 'line_number'
        """
        return self.code_lines.get(line_id, None)
    
    def update_line_args(self, line_id, new_args):
        """
        更新指定行的参数
        
        Args:
            line_id: 行ID
            new_args: 新的参数字典
        
        Returns:
            bool: 是否成功更新
        """
        if line_id not in self.code_lines:
            return False
        
        line_info = self.code_lines[line_id]
        function_name = line_info['function']
        
        if function_name not in self.code_templates:
            return False
        
        template = self.code_templates[function_name]
        params = template.get('params', [])
        
        # 更新参数
        line_info['args'].update(new_args)
        
        # 重新构建函数调用
        custom_format = template.get('format', None)
        options = template.get('options', {})
        
        if custom_format:
            # 使用自定义格式
            format_args = {}
            for param in params:
                value = line_info['args'].get(param, "")
                if param in options:
                    # 确保值在选项中
                    if value not in options[param]:
                        value = options[param][0] if options[param] else ""
                format_args[param] = value
            
            try:
                function_call = custom_format.format(**format_args)
            except KeyError as e:
                # 如果格式字符串中有未提供的参数，回退到默认格式
                function_call = self._build_default_function_call(function_name, params, line_info['args'], options).rstrip('\n')
        else:
            # 使用默认格式
            function_call = self._build_default_function_call(function_name, params, line_info['args'], options).rstrip('\n')
        
        # 替换文本
        line_number = line_info['line_number']
        start_index = f"{line_number}.0"
        end_index = f"{line_number}.end"
        
        self.text.delete(start_index, end_index)
        self.text.insert(start_index, function_call)
        
        self.highlight_parameters()
        return True
    
    def clear_all_lines(self):
        """清空所有代码行记录（但不清空文本内容）"""
        self.code_lines.clear()
        self.next_line_id = 1
    
    def get_all_lines(self):
        """获取所有代码行信息"""
        return self.code_lines.copy()
    
    def rebuild_from_text(self):
        """从当前文本内容重新构建代码行记录"""
        self.code_lines.clear()
        self.next_line_id = 1
        
        content = self.text.get("1.0", "end")
        lines = content.split('\n')
        
        for line_num, line_content in enumerate(lines, 1):
            if not line_content.strip():
                continue
            
            # 尝试解析函数调用
            for func_name, pattern in self.param_patterns.items():
                match = re.search(pattern, line_content)
                if match:
                    param_text = match.group(1)
                    params = self._parse_params(param_text)
                    
                    # 构建参数字典
                    args = {}
                    for param_name, param_value in params:
                        args[param_name] = param_value
                    
                    # 添加到记录中
                    line_id = self.next_line_id
                    self.next_line_id += 1
                    
                    self.code_lines[line_id] = {
                        'function': func_name,
                        'args': args,
                        'line_number': line_num
                    }
                    break
    
    def on_textbox_scroll(self, *args):
        """文本框滚动事件处理 - 更新滚动条位置"""
        # 更新滚动条位置
        self.scrollbar.set(*args)
        # 如果启用了行号，则重绘行号
        if self.show_line_numbers:
            self.on_change()
    
    def on_mousewheel(self, event):
        """鼠标滚轮事件处理"""
        # Windows和macOS的滚轮事件
        if event.num == 4 or event.delta > 0:
            # 向上滚动
            self.text.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            # 向下滚动
            self.text.yview_scroll(1, "units")
        
        # 更新行号显示
        if self.show_line_numbers:
            self.on_change()
        
        return "break"  # 防止事件继续传播
    
    def update_scrollbar_visibility(self):
        """更新滚动条的显示状态"""
        try:
            # 获取滚动条的状态信息
            scroll_info = self.text.yview()
            # 如果内容超出可视区域，确保滚动条可见
            if scroll_info[0] > 0.0 or scroll_info[1] < 1.0:
                # 内容需要滚动，确保滚动条显示
                if not self.scrollbar.winfo_viewable():
                    self.scrollbar.pack(side="right", fill="y")
            # 当内容完全可见时也保持滚动条显示（类似于CTk的行为）
        except:
            # 如果出现错误，确保滚动条仍然显示
            pass
    
    def on_change(self, event=None):
        """文本变化事件处理，更新行号"""
        if self.show_line_numbers and hasattr(self, 'linenumbers'):
            self.linenumbers.redraw()
        
        # 确保滚动条状态正确更新
        self.update_scrollbar_visibility()
    
    def setup_syntax_highlighting(self):
        """设置Python语法高亮"""
        # 设置Python关键字高亮
        self.text.tag_configure("keyword", foreground="#0000FF")  # 蓝色
        self.text.tag_configure("function", foreground="#7F0055")  # 棕色
        self.text.tag_configure("string", foreground="#008000")   # 绿色
        self.text.tag_configure("comment", foreground="#808080")  # 灰色
        self.text.tag_configure("number", foreground="#FF8000")   # 橙色
        
        # Python关键字列表
        self.keywords = [
            "and", "as", "assert", "break", "class", "continue", "def", 
            "del", "elif", "else", "except", "False", "finally", "for", 
            "from", "global", "if", "import", "in", "is", "lambda", "None", 
            "nonlocal", "not", "or", "pass", "raise", "return", "True", 
            "try", "while", "with", "yield"
        ]
        
        # 函数名列表 (包括内置函数和模板中的函数)
        builtin_functions = [
            "print", "len", "range", "int", "float", "str", "list", "dict", "set",
            "tuple", "abs", "all", "any", "bool", "enumerate", "filter", "map", "max",
            "min", "round", "sorted", "sum", "zip"
        ]
        
        # 添加代码模板中的函数
        template_functions = list(self.code_templates.keys())
        self.functions = builtin_functions + template_functions
    
    def _build_param_patterns(self):
        """构建匹配参数的正则表达式"""
        patterns = {}
        for func_name, template in self.code_templates.items():
            if 'params' in template:
                # 为每个函数创建模式，匹配函数名和参数
                pattern = fr'{re.escape(func_name)}\((.*?)\)'
                patterns[func_name] = pattern
        return patterns
    
    def update_code_templates(self, new_templates):
        """更新代码模板"""
        self.code_templates = new_templates
        self.param_patterns = self._build_param_patterns()
        
        # 更新函数列表
        builtin_functions = [
            "print", "len", "range", "int", "float", "str", "list", "dict", "set",
            "tuple", "abs", "all", "any", "bool", "enumerate", "filter", "map", "max",
            "min", "round", "sorted", "sum", "zip"
        ]
        template_functions = list(self.code_templates.keys())
        self.functions = builtin_functions + template_functions
        
        self.highlight_parameters()
    
    def on_text_modified(self, event):
        """文本修改时的回调函数"""
        self.text.edit_modified(False)  # 重置修改标志
        self.highlight_parameters()
        self.highlight_syntax()
        self.on_change()  # 更新行号显示
    
    def highlight_syntax(self):
        """实现Python语法高亮"""
        # 清除现有的语法高亮标记
        for tag in ["keyword", "function", "string", "comment", "number"]:
            self.text.tag_remove(tag, "1.0", "end")
        
        # 获取文本内容
        content = self.text.get("1.0", "end")
        
        # 处理注释 (# 开头到行尾)
        comment_pattern = r'#.*?$'
        for match in re.finditer(comment_pattern, content, re.MULTILINE):
            start_pos = match.start()
            end_pos = match.end()
            # 转换为行列格式
            start_line, start_col = self._get_line_col(content, start_pos)
            end_line, end_col = self._get_line_col(content, end_pos)
            self.text.tag_add("comment", f"{start_line}.{start_col}", f"{end_line}.{end_col}")
        
        # 处理字符串 (单引号和双引号)
        string_patterns = [r'"(?:[^"\\]|\\.)*"', r"'(?:[^'\\]|\\.)*'"]
        for pattern in string_patterns:
            for match in re.finditer(pattern, content):
                start_pos = match.start()
                end_pos = match.end()
                # 转换为行列格式
                start_line, start_col = self._get_line_col(content, start_pos)
                end_line, end_col = self._get_line_col(content, end_pos)
                self.text.tag_add("string", f"{start_line}.{start_col}", f"{end_line}.{end_col}")
        
        # 处理关键字
        for keyword in self.keywords:
            keyword_pattern = r'\b' + re.escape(keyword) + r'\b'
            for match in re.finditer(keyword_pattern, content):
                start_pos = match.start()
                end_pos = match.end()
                # 检查是否在字符串或注释中
                if not self._is_in_tag(start_pos, "string") and not self._is_in_tag(start_pos, "comment"):
                    # 转换为行列格式
                    start_line, start_col = self._get_line_col(content, start_pos)
                    end_line, end_col = self._get_line_col(content, end_pos)
                    self.text.tag_add("keyword", f"{start_line}.{start_col}", f"{end_line}.{end_col}")
        
        # 处理函数名
        for func in self.functions:
            func_pattern = r'\b' + re.escape(func) + r'\s*\('
            for match in re.finditer(func_pattern, content):
                # 只高亮函数名部分，不包括括号
                start_pos = match.start()
                end_pos = start_pos + len(func)
                # 检查是否在字符串或注释中
                if not self._is_in_tag(start_pos, "string") and not self._is_in_tag(start_pos, "comment"):
                    # 转换为行列格式
                    start_line, start_col = self._get_line_col(content, start_pos)
                    end_line, end_col = self._get_line_col(content, end_pos)
                    self.text.tag_add("function", f"{start_line}.{start_col}", f"{end_line}.{end_col}")
        
        # 处理数字
        number_pattern = r'\b\d+(?:\.\d+)?\b'
        for match in re.finditer(number_pattern, content):
            start_pos = match.start()
            end_pos = match.end()
            # 检查是否在字符串或注释中
            if not self._is_in_tag(start_pos, "string") and not self._is_in_tag(start_pos, "comment"):
                # 转换为行列格式
                start_line, start_col = self._get_line_col(content, start_pos)
                end_line, end_col = self._get_line_col(content, end_pos)
                self.text.tag_add("number", f"{start_line}.{start_col}", f"{end_line}.{end_col}")
    
    def _is_in_tag(self, pos, tag_name):
        """检查位置是否在指定标签范围内"""
        line, col = self._get_line_col(self.text.get("1.0", "end"), pos)
        index = f"{line}.{col}"
        tag_ranges = self.text.tag_ranges(tag_name)
        
        for i in range(0, len(tag_ranges), 2):
            start = tag_ranges[i]
            end = tag_ranges[i+1]
            if self.text.compare(start, "<=", index) and self.text.compare(index, "<", end):
                return True
        return False
    
    def highlight_parameters(self):
        """高亮显示可选择的参数"""
        # 清除所有现有的高亮标记
        self.text.tag_remove("param_highlight", "1.0", "end")
        
        # 获取所有文本
        text_content = self.text.get("1.0", "end")
        
        # 查找和高亮每个函数的参数
        for func_name, pattern in self.param_patterns.items():
            template = self.code_templates.get(func_name, {})
            params = template.get('params', [])
            options = template.get('options', {})
            
            # 如果有可选参数，搜索匹配并高亮
            if params and options:
                for match in re.finditer(pattern, text_content):
                    # 获取参数部分
                    param_text = match.group(1)
                    start_pos = match.start(1)
                    
                    # 计算每个参数的位置
                    param_parts = self._parse_params(param_text)
                    
                    # 重新精确解析参数位置
                    param_text_without_spaces = param_text.replace(' ', '')
                    
                    # 在原始参数文本中查找每个参数值的精确位置
                    search_pos = 0
                    for param_name, param_value in param_parts:
                        if param_name in options:
                            # 在参数文本中查找 param_name=param_value 的位置
                            param_pattern = param_name.strip() + '=' + param_value.strip()
                            
                            # 在原始参数文本中查找这个模式
                            param_index = param_text.find(param_pattern, search_pos)
                            if param_index != -1:
                                # 计算参数值在整个文本中的位置
                                value_start_in_param = param_index + len(param_name.strip()) + 1  # +1 for '='
                                value_end_in_param = value_start_in_param + len(param_value.strip())
                                
                                # 转换为在整个文本中的绝对位置
                                abs_value_start = start_pos + value_start_in_param
                                abs_value_end = start_pos + value_end_in_param
                                
                                # 转换为行列格式
                                start_line, start_col = self._get_line_col(text_content, abs_value_start)
                                end_line, end_col = self._get_line_col(text_content, abs_value_end)
                                
                                # 应用高亮标记
                                self.text.tag_add("param_highlight", f"{start_line}.{start_col}", f"{end_line}.{end_col}")
                                
                                # 更新搜索位置
                                search_pos = param_index + len(param_pattern)
        
        # 应用语法高亮
        self.highlight_syntax()
    
    def _parse_params(self, param_text):
        """解析参数文本为参数名和值的列表"""
        params = []
        # 处理空参数情况
        if not param_text.strip():
            return params
        
        # 基本情况，按逗号分隔
        parts = param_text.split(',')
        for part in parts:
            part = part.strip()
            if '=' in part:
                # 命名参数
                name, value = part.split('=', 1)
                params.append((name.strip(), value.strip()))
            else:
                # 位置参数，使用索引作为名称
                params.append((f"arg{len(params)}", part))
        
        return params
    
    def _get_line_col(self, text, pos):
        """将字符位置转换为行列格式"""
        text_up_to_pos = text[:pos]
        lines = text_up_to_pos.split('\n')
        line = len(lines)
        col = len(lines[-1])
        return line, col
    
    def on_click(self, event):
        """鼠标点击事件处理"""
        # 关闭任何现有的下拉菜单
        self.close_dropdown()
        
        # 获取当前点击位置
        index = self.text.index(f"@{event.x},{event.y}")
        
        # 检查该位置是否有高亮标记
        tags = self.text.tag_names(index)
        if "param_highlight" in tags:
            # 获取参数值的开始和结束索引
            start = self.text.index(f"{index} linestart")
            line_text = self.text.get(start, f"{index} lineend")
            line_pos = int(self.text.index(index).split('.')[1])
            
            # 查找包含该位置的函数调用
            for func_name, pattern in self.param_patterns.items():
                for match in re.finditer(pattern, line_text):
                    param_text = match.group(1)
                    param_start = match.start(1)
                    
                    # 如果点击位置在参数部分
                    if param_start <= line_pos < param_start + len(param_text):
                        # 解析参数确定具体点击的是哪个参数
                        param_parts = self._parse_params(param_text)
                        
                        # 精确查找每个参数值的位置
                        search_pos = 0
                        for param_name, param_value in param_parts:
                            if param_name in self.code_templates[func_name]['options']:
                                # 在参数文本中查找 param_name=param_value 的位置
                                param_pattern = param_name.strip() + '=' + param_value.strip()
                                param_index = param_text.find(param_pattern, search_pos)
                                
                                if param_index != -1:
                                    # 计算参数值的开始和结束位置
                                    value_start_in_param = param_index + len(param_name.strip()) + 1  # +1 for '='
                                    value_end_in_param = value_start_in_param + len(param_value.strip())
                                    
                                    # 转换为行中的绝对位置
                                    value_start = param_start + value_start_in_param
                                    value_end = param_start + value_end_in_param
                                    
                                    # 如果点击位置在参数值范围内
                                    if value_start <= line_pos < value_end:
                                        # 获取该参数的选项
                                        options = self.code_templates[func_name]['options'].get(param_name)
                                        if options:
                                            # 创建下拉菜单
                                            self.show_dropdown(index, options, param_value)
                                        break
                                    
                                    # 更新搜索位置
                                    search_pos = param_index + len(param_pattern)
    
    def show_dropdown(self, index, options, current_value):
        """显示下拉菜单"""
        # 获取文本框中的坐标
        bbox = self.text.bbox(index)
        if not bbox:
            return
        
        x, y, width, height = bbox
        
        # 创建标准的Tk菜单并配置样式
        self.dropdown = tk.Menu(self, tearoff=0, relief="flat", borderwidth=1)
        
        # 创建更大的字体用于菜单
        menu_font = tkfont.Font(family=self.font.cget("family"), size=14)  # 使用更大的字体
        
        # 配置菜单样式
        self.dropdown.config(
            font=menu_font,
            background="white",
            foreground="black",
            activebackground="#0078D7",
            activeforeground="white"
        )
        
        # 增加菜单项的间距
        self.dropdown["selectcolor"] = "#0078D7"  # 选中项的颜色
        
        # 添加选项到菜单
        for option in options:
            # 使用lambda创建回调函数，需要使用默认参数避免闭包问题
            self.dropdown.add_command(
                label=option, 
                command=lambda opt=option: self.on_option_selected(opt)
            )
            # 如果是当前值，添加标记
            if option == current_value:
                # 找到最后添加的选项索引
                last_index = self.dropdown.index("end")
                # 给当前选中的值添加特殊标记（可以是特殊字体或其他视觉指示）
                self.dropdown.entryconfig(last_index, background="#E5F1FB")
        
        # 保存当前选择的索引范围
        self.dropdown_index = self.text.index(f"@{x},{y}")
        
        # 获取参数值的范围
        start = None
        end = None
        
        # 向左搜索参数值的开始
        curr = self.dropdown_index
        while True:
            char = self.text.get(curr)
            if char in "=,()":
                start = self.text.index(f"{curr}+1c")
                break
            curr = self.text.index(f"{curr}-1c")
        
        # 向右搜索参数值的结束
        curr = self.dropdown_index
        while True:
            char = self.text.get(curr)
            if char in ",)":
                end = curr
                break
            elif self.text.compare(curr, "==", "end-1c"):
                end = "end-1c"
                break
            curr = self.text.index(f"{curr}+1c")
        
        self.dropdown_range = (start, end)
        
        # 在文本位置显示菜单
        # 获取文本组件在屏幕上的绝对坐标
        x_root = self.text.winfo_rootx() + x
        y_root = self.text.winfo_rooty() + y + height
        
        # 弹出菜单在鼠标位置
        self.dropdown.post(x_root, y_root)
        self.active_dropdown = self.dropdown
    
    def on_option_selected(self, option):
        """下拉选项选择处理"""
        if self.dropdown_range:
            start, end = self.dropdown_range
            self.text.delete(start, end)
            self.text.insert(start, option)
        
        self.close_dropdown()
    
    def close_dropdown(self):
        """关闭下拉菜单"""
        if self.active_dropdown:
            if isinstance(self.active_dropdown, tk.Menu):
                self.active_dropdown.unpost()
            else:
                self.active_dropdown.destroy()
            self.active_dropdown = None
            self.dropdown_index = None
            self.dropdown_range = None
            # 重置当前菜单索引
            self.current_menu_index = 0
    
    def on_focus_out(self, event):
        """失去焦点时关闭下拉菜单"""
        # 检查鼠标位置是否在菜单区域内
        if self.active_dropdown and isinstance(self.active_dropdown, tk.Menu):
            # 不立即关闭，因为用户可能正在点击菜单项
            return
        
        # 对于其他情况或自定义CTk组件，使用延迟关闭
        self.after(150, self.close_dropdown)
    
    def on_key_release(self, event):
        """按键释放事件处理"""
        # 当用户编辑文本时更新高亮
        self.highlight_parameters()
    
    def on_key_down(self, event):
        """处理向下键事件"""
        if self.active_dropdown and isinstance(self.active_dropdown, tk.Menu):
            # 获取菜单项数量
            menu_length = self.active_dropdown.index("end")
            if menu_length is not None:  # 确保菜单有项目
                # 更新当前选中的索引
                self.current_menu_index = (self.current_menu_index + 1) % (menu_length + 1)
                # 激活对应的菜单项
                self.active_dropdown.activate(self.current_menu_index)
            return "break"  # 防止事件传播
    
    def on_key_up(self, event):
        """处理向上键事件"""
        if self.active_dropdown and isinstance(self.active_dropdown, tk.Menu):
            # 获取菜单项数量
            menu_length = self.active_dropdown.index("end")
            if menu_length is not None:  # 确保菜单有项目
                # 更新当前选中的索引
                self.current_menu_index = (self.current_menu_index - 1) % (menu_length + 1)
                # 激活对应的菜单项
                self.active_dropdown.activate(self.current_menu_index)
            return "break"  # 防止事件传播
    
    def on_key_return(self, event):
        """处理回车键事件"""
        if self.active_dropdown and isinstance(self.active_dropdown, tk.Menu):
            # 获取当前激活的菜单项
            try:
                # 获取当前选中的菜单项标签
                selected_option = self.active_dropdown.entrycget(self.current_menu_index, "label")
                # 调用选项选择处理函数
                self.on_option_selected(selected_option)
            except:
                # 如果出错，关闭下拉菜单
                self.close_dropdown()
            return "break"  # 防止事件传播
    
    def on_key_escape(self, event):
        """处理ESC键事件"""
        if self.active_dropdown:
            self.close_dropdown()
            return "break"  # 防止事件传播
    
    # 代理Text组件的常用方法
    def get(self, start="1.0", end="end"):
        """获取文本内容"""
        return self.text.get(start, end)
    
    def insert(self, index, text):
        """插入文本"""
        self.text.insert(index, text)
        self.highlight_parameters()
        self.on_change()  # 更新行号显示
    
    def delete(self, start, end=None):
        """删除文本"""
        self.text.delete(start, end)
        self.highlight_parameters()
        self.on_change()  # 更新行号显示
    
    def clear(self):
        """清空文本框"""
        self.text.delete("1.0", "end")
        self.on_change()  # 更新行号显示
    
    def see(self, index):
        """滚动到指定位置"""
        self.text.see(index)
    
    def mark_set(self, markName, index):
        """设置标记"""
        self.text.mark_set(markName, index)
    
    def index(self, index):
        """获取索引"""
        return self.text.index(index)


# 主函数，用于测试CTkAdvancedTextBox组件
def main():
    """测试CTkAdvancedTextBox组件"""
    root = ctk.CTk()
    root.title("CTkAdvancedTextBox 动态代码行测试")
    root.geometry("1000x700")
    
    # 定义一些测试用的代码模板
    code_templates = {
        "get_data": {
            "params": ["source_id", "limit", "format"],
            "options": {
                "source_id": ["0", "1", "2", "main"],
                "limit": ["10", "50", "100", "500"],
                "format": ["json", "xml", "csv", "text"]
            }
        },
        "process_image": {
            "params": ["width", "height", "quality"],
            "options": {
                "width": ["640", "800", "1024", "1280"],
                "height": ["480", "600", "768", "1024"],
                "quality": ["low", "medium", "high", "ultra"]
            }
        },
        "calculate": {
            "params": ["x", "y", "operation"],
            "options": {
                "x": ["0", "10", "100"],
                "y": ["0", "20", "200"],
                "operation": ["add", "subtract", "multiply", "divide"]
            }
        },
        "send_email": {
            "params": ["to", "subject", "priority"],
            "options": {
                "to": ["admin@example.com", "user@example.com", "support@example.com"],
                "subject": ["Alert", "Report", "Notification"],
                "priority": ["low", "normal", "high", "urgent"]
            }
        }
    }
    
    # 创建主框架
    main_frame = ctk.CTkFrame(root)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # 创建标题
    title_label = ctk.CTkLabel(
        main_frame, 
        text="CTkAdvancedTextBox 动态代码行测试",
        font=ctk.CTkFont(size=18, weight="bold")
    )
    title_label.pack(pady=10)
    
    # 创建说明标签
    info_label = ctk.CTkLabel(
        main_frame, 
        text="使用下方按钮动态添加/删除代码行，点击蓝色下划线参数可以选择选项",
        font=ctk.CTkFont(size=14)
    )
    info_label.pack(pady=5)
    
    # 创建控制面板
    control_frame = ctk.CTkFrame(main_frame)
    control_frame.pack(fill="x", padx=5, pady=5)
    
    # 创建CTkAdvancedTextBox
    editor = CTkAdvancedTextBox(
        main_frame,
        code_templates=code_templates,
        font=ctk.CTkFont(family="Consolas", size=14),
        fg_color="white",
        text_color="black",
        border_width=1,
        border_color="gray",
        show_line_numbers=True
    )
    editor.pack(fill="both", expand=True, padx=5, pady=5)
    
    # 存储添加的行ID，用于删除测试
    added_lines = []
    
    # 添加代码行的函数
    def add_get_data_line():
        line_id = editor.add_line("get_data", {"source_id": "1", "limit": "100", "format": "json"})
        added_lines.append(line_id)
        print(f"添加了 get_data 行，ID: {line_id}")
    
    def add_process_image_line():
        line_id = editor.add_line("process_image", {"width": "1024", "height": "768", "quality": "high"})
        added_lines.append(line_id)
        print(f"添加了 process_image 行，ID: {line_id}")
    
    def add_calculate_line():
        line_id = editor.add_line("calculate")  # 使用默认参数
        added_lines.append(line_id)
        print(f"添加了 calculate 行，ID: {line_id}")
    
    def add_email_line():
        line_id = editor.add_line("send_email", {
            "to": "admin@example.com", 
            "subject": "Alert", 
            "priority": "high"
        })
        added_lines.append(line_id)
        print(f"添加了 send_email 行，ID: {line_id}")
    
    # 删除最后添加的行
    def delete_last_line():
        if added_lines:
            line_id = added_lines.pop()
            success = editor.delete_line(line_id)
            if success:
                print(f"删除了行 ID: {line_id}")
            else:
                print(f"删除行 ID: {line_id} 失败")
        else:
            print("没有可删除的行")
    
    # 删除指定行号
    def delete_line_by_number():
        try:
            line_num = line_entry.get()
            if line_num:
                success = editor.delete_line(line_num)
                if success:
                    print(f"删除了第 {line_num} 行")
                else:
                    print(f"删除第 {line_num} 行失败")
            else:
                print("请输入行号")
        except Exception as e:
            print(f"删除行时出错: {e}")
    
    # 显示所有行信息
    def show_all_lines():
        lines = editor.get_all_lines()
        print("\n当前所有代码行:")
        print("-" * 50)
        for line_id, info in lines.items():
            print(f"ID: {line_id}, 行号: {info['line_number']}, 函数: {info['function']}, 参数: {info['args']}")
        print("-" * 50)
    
    # 清空编辑器
    def clear_editor():
        editor.clear()
        editor.clear_all_lines()
        added_lines.clear()
        print("清空了编辑器")
    
    # 重建行记录
    def rebuild_lines():
        editor.rebuild_from_text()
        print("重建了行记录")
        show_all_lines()
    
    # 第一行控制按钮
    row1_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
    row1_frame.pack(fill="x", pady=2)
    
    add_data_btn = ctk.CTkButton(row1_frame, text="添加 get_data", command=add_get_data_line, width=120)
    add_data_btn.pack(side="left", padx=2)
    
    add_image_btn = ctk.CTkButton(row1_frame, text="添加 process_image", command=add_process_image_line, width=140)
    add_image_btn.pack(side="left", padx=2)
    
    add_calc_btn = ctk.CTkButton(row1_frame, text="添加 calculate", command=add_calculate_line, width=120)
    add_calc_btn.pack(side="left", padx=2)
    
    add_email_btn = ctk.CTkButton(row1_frame, text="添加 send_email", command=add_email_line, width=120)
    add_email_btn.pack(side="left", padx=2)
    
    # 第二行控制按钮
    row2_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
    row2_frame.pack(fill="x", pady=2)
    
    delete_last_btn = ctk.CTkButton(row2_frame, text="删除最后一行", command=delete_last_line, width=120)
    delete_last_btn.pack(side="left", padx=2)
    
    # 按行号删除的组件
    line_label = ctk.CTkLabel(row2_frame, text="行号:")
    line_label.pack(side="left", padx=(10, 2))
    
    line_entry = ctk.CTkEntry(row2_frame, width=50, placeholder_text="1")
    line_entry.pack(side="left", padx=2)
    
    delete_num_btn = ctk.CTkButton(row2_frame, text="删除指定行", command=delete_line_by_number, width=100)
    delete_num_btn.pack(side="left", padx=2)
    
    show_lines_btn = ctk.CTkButton(row2_frame, text="显示行信息", command=show_all_lines, width=100)
    show_lines_btn.pack(side="left", padx=2)
    
    # 第三行控制按钮
    row3_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
    row3_frame.pack(fill="x", pady=2)
    
    clear_btn = ctk.CTkButton(row3_frame, text="清空", command=clear_editor, width=80)
    clear_btn.pack(side="left", padx=2)
    
    rebuild_btn = ctk.CTkButton(row3_frame, text="重建行记录", command=rebuild_lines, width=100)
    rebuild_btn.pack(side="left", padx=2)
    
    def print_content():
        content = editor.get()
        print("\n编辑器内容:")
        print("-" * 40)
        print(content)
        print("-" * 40)
    
    print_btn = ctk.CTkButton(row3_frame, text="打印内容", command=print_content, width=100)
    print_btn.pack(side="left", padx=2)
    
    # 添加一些初始示例代码
    sample_code = """# CTkAdvancedTextBox 动态代码行演示
# 使用上方按钮动态添加代码行
# 点击蓝色下划线的参数可以选择选项

# 下面是一些示例代码（非动态管理）
print("欢迎使用 CTkAdvancedTextBox!")
for i in range(3):
    print(f"示例循环: {i}")

"""
    editor.insert("1.0", sample_code)
    
    # 添加一些初始的动态代码行
    editor.add_line("get_data", {"source_id": "0", "limit": "50", "format": "json"})
    editor.add_line("calculate", {"x": "10", "y": "20", "operation": "multiply"})
    
    root.mainloop()

# 如果直接运行此文件，执行主函数
if __name__ == "__main__":
    main() 