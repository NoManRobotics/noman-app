import tkinter as tk
import customtkinter as ctk

class RangeSlider(ctk.CTkFrame):
    def __init__(self, master, from_=0, to=180, canvas_bg='#dbdbdb', slider_width=280, home=90, circle_size=6, track_color='#939ba2', number_of_steps=None, button_step=1, **kwargs):
        super().__init__(master, **kwargs)
        
        # 移除固定高度，改用最小高度
        self.min_height = 50
        self.canvas_height = self.min_height
        self.slider_width = slider_width
        self.canvas_width = self.slider_width + 30
        self.canvas_bg = canvas_bg
        self.circle_size = circle_size  # 存储自定义圆形大小
        self.track_color = track_color  # 存储滑块轨道颜色
        
        # 添加步进相关属性
        self.from_ = from_
        self.to = to
        self.number_of_steps = number_of_steps
        self.button_step = max(1, int(button_step))  # 按钮步长，至少为1
        
        if self.number_of_steps is not None:
            # 如果指定了步数，计算步长
            # number_of_steps是指在from_和to之间等分的段数，所以总共有number_of_steps+1个点
            self.step_size = (to - from_) / number_of_steps if number_of_steps > 0 else 0
            self.use_steps = True
        else:
            # 如果没有指定步数，使用连续值模式
            self.step_size = 1
            self.use_steps = False
        
        self.range = to - from_
        
        self.configure(fg_color="transparent")
        self.grid_columnconfigure((0, 2), weight=0)  # 按钮列
        self.grid_columnconfigure(1, weight=1)       # 让中间列可以伸展
        
        # 左侧按钮Frame
        self.button_frame_left = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame_left.grid(row=0, column=0, padx=(0,5))
        
        # 左侧按钮在同一行
        self.lower_minus_btn = ctk.CTkButton(self.button_frame_left, text="-", width=25, height=25)
        self.lower_minus_btn.pack(side="left", padx=2)
        
        self.lower_plus_btn = ctk.CTkButton(self.button_frame_left, text="+", width=25, height=25)
        self.lower_plus_btn.pack(side="left", padx=2)
        
        # Canvas放在中间，移除sticky
        self.canvas = tk.Canvas(
            self, 
            height=self.canvas_height,
            width=self.canvas_width,
            bg=self.canvas_bg,
            highlightthickness=0, 
            cursor="arrow"
        )
        self.canvas.grid(row=0, column=1, sticky="nsew")  # 添加 ns 使其垂直填充
        
        # 绑定重绘事件
        self.canvas.bind('<Configure>', self.on_resize)
        
        # 右侧按钮Frame
        self.button_frame_right = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame_right.grid(row=0, column=2, padx=(5,0))
        
        # 右侧按钮在同一行
        self.upper_minus_btn = ctk.CTkButton(self.button_frame_right, text="-", width=25, height=25)
        self.upper_minus_btn.pack(side="left", padx=2)
        
        self.upper_plus_btn = ctk.CTkButton(self.button_frame_right, text="+", width=25, height=25)
        self.upper_plus_btn.pack(side="left", padx=2)
        
        # 修改初始值以适应新范围和步进
        if self.use_steps:
            # 对于步进模式，确保初始值对齐到有效步进值
            self.lower_val = self.snap_to_step(from_)  # 起始值本身就是一个有效步进值
            self.upper_val = self.snap_to_step(to)
            self.home_val = self.snap_to_step(home)
        else:
            self.lower_val = from_
            self.upper_val = to
            self.home_val = home
        
        self.selected = None
        self.offset = 0
        
        # 添加重复点击相关的属性
        self.repeat_action = None
        self.repeat_delay = 100  # 重复间隔(毫秒)
        self.after_id = None
        
        # 添加比例常量
        self.MARGIN_RATIO = 0.07  # 边距比例
        self.BAR_HEIGHT_RATIO = 0.33  # 条形高度比例
        self.BAR_WIDTH_RATIO = 0.014  # 条形宽度比例
        self.HIT_AREA_RATIO = 0.05  # 点击区域比例
        self.HOME_RADIUS_RATIO = 0.035  # Home点半径比例
        self.TEXT_OFFSET_RATIO = 0.35  # 垂直偏移比例
        self.TEXT_SIZE_RATIO = 0.15   # 文本大小比例
        self.TEXT_H_OFFSET_RATIO = -0.05  # 水平偏移比例

        self.draw_slider()
        self.bind_events()
        self.callback = None
        
        # 修改按钮绑定事件
        self.lower_minus_btn.bind('<Button-1>', lambda e: self.start_repeat(self.lower_minus))
        self.lower_minus_btn.bind('<ButtonRelease-1>', self.stop_repeat)
        
        self.lower_plus_btn.bind('<Button-1>', lambda e: self.start_repeat(self.lower_plus))
        self.lower_plus_btn.bind('<ButtonRelease-1>', self.stop_repeat)
        
        self.upper_minus_btn.bind('<Button-1>', lambda e: self.start_repeat(self.upper_minus))
        self.upper_minus_btn.bind('<ButtonRelease-1>', self.stop_repeat)
        
        self.upper_plus_btn.bind('<Button-1>', lambda e: self.start_repeat(self.upper_plus))
        self.upper_plus_btn.bind('<ButtonRelease-1>', self.stop_repeat)
    
    def snap_to_step(self, value):
        """将值对齐到最近的有效步进值"""
        if not self.use_steps:
            return value
        
        # 计算最接近的步进索引（从0开始，包括起始值）
        step_index = round((value - self.from_) / self.step_size)
        step_index = max(0, min(self.number_of_steps, step_index))
        
        # 返回对应的步进值
        return self.from_ + step_index * self.step_size
    
    def get_valid_values(self):
        """获取所有有效的步进值"""
        if not self.use_steps:
            return None
        
        return [self.from_ + i * self.step_size for i in range(self.number_of_steps + 1)]
    
    def set_callback(self, func):
        self.callback = func
    
    def to_screen_coord(self, value):
        margin = int(self.canvas_width * self.MARGIN_RATIO)
        if self.range == 0:
            return margin
        return margin + ((value - self.from_) / self.range) * (self.canvas_width - 2 * margin)
    
    def to_angle(self, x):
        margin = int(self.canvas_width * self.MARGIN_RATIO)
        if self.canvas_width - 2 * margin == 0:
            return self.from_
        
        # 计算比例值
        ratio = (x - margin) / (self.canvas_width - 2 * margin)
        value = ratio * self.range + self.from_
        
        # 确保值在范围内
        value = max(self.from_, min(self.to, value))
        
        # 如果使用步进模式，对齐到最近的步进值
        if self.use_steps:
            value = self.snap_to_step(value)
        else:
            # 对于非步进模式，根据范围决定精度
            if self.range < 1:
                # 小范围时保持更高精度
                value = round(value, 6)
            else:
                # 大范围时使用整数
                value = int(value)
        
        return value
    
    def draw_slider(self):
        self.canvas.delete("all")
        
        # 计算动态尺寸
        margin = int(self.canvas_width * self.MARGIN_RATIO)
        y = self.canvas_height // 2
        bar_height = int(self.canvas_height * self.BAR_HEIGHT_RATIO)
        bar_width = int(self.canvas_width * self.BAR_WIDTH_RATIO)
        hit_area = int(self.canvas_width * self.HIT_AREA_RATIO)
        # 使用自定义圆形大小
        home_radius = self.circle_size
        text_offset = int(self.canvas_height * self.TEXT_OFFSET_RATIO)
        text_size = int(self.canvas_height * self.TEXT_SIZE_RATIO)
        text_h_offset = int(self.canvas_width * self.TEXT_H_OFFSET_RATIO)  # 水平偏移
        
        # 绘制整个范围的背景
        self.canvas.create_line(
            margin, y, 
            self.canvas_width - margin, y,
            fill=self.track_color,
            width=4
        )
        
        # 绘制有效范围
        x1 = self.to_screen_coord(self.lower_val)
        x2 = self.to_screen_coord(self.upper_val)
        self.canvas.create_line(
            x1, y, x2, y, 
            fill='#1f538d', 
            width=4
        )
        
        # 下限点 - 改为条形
        self.canvas.create_rectangle(
            x1-hit_area, y-hit_area, x1+hit_area, y+hit_area, 
            fill='', outline='', 
            tags=('lower_hit',)
        )
        self.canvas.create_rectangle(
            x1-bar_width, y-bar_height//2, 
            x1+bar_width, y+bar_height//2,
            fill='#3b8ed0', 
            outline='',
            tags=('lower', 'lower_hit')
        )
        
        # 上限点 - 改为条形
        self.canvas.create_rectangle(
            x2-hit_area, y-hit_area, x2+hit_area, y+hit_area,
            fill='', outline='', 
            tags=('upper_hit',)
        )
        self.canvas.create_rectangle(
            x2-bar_width, y-bar_height//2, 
            x2+bar_width, y+bar_height//2,
            fill='#3b8ed0', 
            outline='',
            tags=('upper', 'upper_hit')
        )
        
        # Home点 - 保持圆形
        x_home = self.to_screen_coord(self.home_val)
        self.canvas.create_oval(
            x_home-hit_area, y-hit_area, x_home+hit_area, y+hit_area,
            fill='', outline='', 
            tags=('home_hit',)
        )
        self.canvas.create_oval(
            x_home-home_radius, y-home_radius, 
            x_home+home_radius, y+home_radius,
            fill='#36719f', 
            outline='',
            tags=('home', 'home_hit')
        )
        
        # 显示数值 - 改进数值格式显示
        def format_value(val):
            if self.use_steps and self.range < 1:
                # 小数值时显示更多精度
                return f'{val:.6f}'.rstrip('0').rstrip('.')
            elif self.range < 1:
                return f'{val:.6f}'.rstrip('0').rstrip('.')
            else:
                return str(int(val)) if val == int(val) else f'{val:.2f}'
        
        self.canvas.create_text(
            x1 - text_h_offset, y-text_offset,  # 左侧文本向左偏移
            text=format_value(self.lower_val) + ('°' if self.range >= 1 else ''),
            fill='#333333',
            font=('TkDefaultFont', text_size)
        )
        self.canvas.create_text(
            x2 + text_h_offset, y-text_offset,  # 右侧文本向右偏移
            text=format_value(self.upper_val) + ('°' if self.range >= 1 else ''),
            fill='#333333',
            font=('TkDefaultFont', text_size)
        )
        self.canvas.create_text(
            x_home, y+text_offset, 
            text=format_value(self.home_val) + ('°' if self.range >= 1 else ''),
            fill='#333333',
            font=('TkDefaultFont', text_size)
        )
    
    def bind_events(self):
        # 绑定鼠标进入/离开事件来改变光标
        for tag in ['lower_hit', 'upper_hit', 'home_hit']:
            self.canvas.tag_bind(tag, '<Enter>', lambda e, t=tag: self.on_enter(t))
            self.canvas.tag_bind(tag, '<Leave>', self.on_leave)
            self.canvas.tag_bind(tag, '<Button-1>', self.on_press)
        
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)
    
    def on_enter(self, tag):
        self.canvas.configure(cursor="hand2")
        # 可以在这里添加视觉反馈，比如改变控制点的颜色
        if 'lower' in tag:
            self.canvas.itemconfig('lower', fill='#5badec')
        elif 'upper' in tag:
            self.canvas.itemconfig('upper', fill='#5badec')
        elif 'home' in tag:
            self.canvas.itemconfig('home', fill='#4a8cbf')
    
    def on_leave(self, event):
        if not self.selected:  # 只在没有选中控制点时改变光标
            self.canvas.configure(cursor="arrow")
        # 恢复原始颜色
        self.canvas.itemconfig('lower', fill='#3b8ed0')
        self.canvas.itemconfig('upper', fill='#3b8ed0')
        self.canvas.itemconfig('home', fill='#36719f')
    
    def on_press(self, event):
        closest = self.canvas.find_closest(event.x, event.y)[0]
        tags = self.canvas.gettags(closest)
        
        if 'lower_hit' in tags:
            self.selected = 'lower'
        elif 'upper_hit' in tags:
            self.selected = 'upper'
        elif 'home_hit' in tags:
            self.selected = 'home'
        
        self.offset = event.x
        
    def on_drag(self, event):
        if not self.selected:
            return
            
        x = event.x
        value = self.to_angle(x)
        value = max(self.from_, min(self.to, value))  # 限制在from_到to范围内
        
        if self.selected == 'lower':
            if value <= self.home_val:
                self.lower_val = value
        elif self.selected == 'upper':
            if value >= self.home_val:
                self.upper_val = value
        elif self.selected == 'home':
            if self.lower_val <= value <= self.upper_val:
                self.home_val = value
        
        self.draw_slider()
        if self.callback:
            self.callback(self.lower_val, self.upper_val, self.home_val)
    
    def on_release(self, event):
        self.selected = None
        self.canvas.configure(cursor="arrow")  # 释放时恢复默认光标

    def lower_minus(self):
        if self.use_steps:
            # 步进模式：移动指定的button_step个步进值
            current_index = round((self.lower_val - self.from_) / self.step_size)
            if current_index > 0:  # 最小为第0个步进值（即from_值）
                new_index = max(0, current_index - self.button_step)
                new_val = self.from_ + new_index * self.step_size
                if new_val <= self.home_val:
                    self.lower_val = new_val
                    self.draw_slider()
                    if self.callback:
                        self.callback(self.lower_val, self.upper_val, self.home_val)
        else:
            # 连续模式：移动指定的button_step倍数
            if self.lower_val > self.from_ and self.lower_val <= self.home_val:
                new_val = max(self.from_, self.lower_val - (self.step_size * self.button_step))
                if new_val <= self.home_val:
                    self.lower_val = new_val
                    self.draw_slider()
                    if self.callback:
                        self.callback(self.lower_val, self.upper_val, self.home_val)

    def lower_plus(self):
        if self.use_steps:
            # 步进模式：移动指定的button_step个步进值
            current_index = round((self.lower_val - self.from_) / self.step_size)
            if current_index < self.number_of_steps:  # 最大为第number_of_steps个步进值
                new_index = min(self.number_of_steps, current_index + self.button_step)
                new_val = self.from_ + new_index * self.step_size
                if new_val <= self.home_val:
                    self.lower_val = new_val
                    self.draw_slider()
                    if self.callback:
                        self.callback(self.lower_val, self.upper_val, self.home_val)
        else:
            # 连续模式：移动指定的button_step倍数
            if self.lower_val < self.home_val:
                new_val = min(self.home_val, self.lower_val + (self.step_size * self.button_step))
                self.lower_val = new_val
                self.draw_slider()
                if self.callback:
                    self.callback(self.lower_val, self.upper_val, self.home_val)

    def upper_minus(self):
        if self.use_steps:
            # 步进模式：移动指定的button_step个步进值
            current_index = round((self.upper_val - self.from_) / self.step_size)
            if current_index > 0:  # 最小为第0个步进值（即from_值）
                new_index = max(0, current_index - self.button_step)
                new_val = self.from_ + new_index * self.step_size
                if new_val >= self.home_val:
                    self.upper_val = new_val
                    self.draw_slider()
                    if self.callback:
                        self.callback(self.lower_val, self.upper_val, self.home_val)
        else:
            # 连续模式：移动指定的button_step倍数
            if self.upper_val > self.home_val:
                new_val = max(self.home_val, self.upper_val - (self.step_size * self.button_step))
                self.upper_val = new_val
                self.draw_slider()
                if self.callback:
                    self.callback(self.lower_val, self.upper_val, self.home_val)

    def upper_plus(self):
        if self.use_steps:
            # 步进模式：移动指定的button_step个步进值
            current_index = round((self.upper_val - self.from_) / self.step_size)
            if current_index < self.number_of_steps:  # 最大为第number_of_steps个步进值
                new_index = min(self.number_of_steps, current_index + self.button_step)
                new_val = self.from_ + new_index * self.step_size
                if new_val >= self.home_val:
                    self.upper_val = new_val
                    self.draw_slider()
                    if self.callback:
                        self.callback(self.lower_val, self.upper_val, self.home_val)
        else:
            # 连续模式：移动指定的button_step倍数
            if self.upper_val < self.to and self.upper_val >= self.home_val:
                new_val = min(self.to, self.upper_val + (self.step_size * self.button_step))
                self.upper_val = new_val
                self.draw_slider()
                if self.callback:
                    self.callback(self.lower_val, self.upper_val, self.home_val)

    def start_repeat(self, action):
        """开始重复执行动作"""
        action()  # 执行一次动作
        self.repeat_action = action
        self.after_id = self.after(self.repeat_delay, self.repeat)
    
    def stop_repeat(self, event=None):
        """停止重复执行动作"""
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        self.repeat_action = None
    
    def repeat(self):
        """重复执行动作"""
        if self.repeat_action:
            self.repeat_action()
            self.after_id = self.after(self.repeat_delay, self.repeat)

    def set_range(self, from_val, to_val, number_of_steps=None):
        """设置滑块的范围和步数"""
        if from_val >= to_val:
            raise ValueError("起始值必须小于结束值")
        
        self.from_ = from_val
        self.to = to_val
        self.range = to_val - from_val
        
        # 更新步进设置
        if number_of_steps is not None:
            self.number_of_steps = number_of_steps
            self.step_size = (to_val - from_val) / number_of_steps if number_of_steps > 0 else 0
            self.use_steps = True
        elif self.number_of_steps is not None:
            # 保持现有步数，重新计算步长
            self.step_size = (to_val - from_val) / self.number_of_steps if self.number_of_steps > 0 else 0
        
        # 对齐现有值到新的步进值
        if self.use_steps:
            self.lower_val = self.snap_to_step(self.lower_val)
            self.upper_val = self.snap_to_step(self.upper_val)
            self.home_val = self.snap_to_step(self.home_val)
        
        self.draw_slider()

    def set_values(self, lower, upper, home):
        """设置滑块的当前值"""
        # 验证值的合法性
        if lower > upper:
            raise ValueError("下限值必须小于或等于上限值")
        if home < lower or home > upper:
            raise ValueError("归位值必须在上下限范围内")
        if lower < self.from_ or upper > self.to:
            raise ValueError("值必须在滑块范围内")

        # 如果使用步进模式，对齐到有效步进值
        if self.use_steps:
            self.lower_val = self.snap_to_step(lower)
            self.upper_val = self.snap_to_step(upper)
            self.home_val = self.snap_to_step(home)
        else:
            self.lower_val = lower
            self.upper_val = upper
            self.home_val = home
            
        self.draw_slider()
        
        if self.callback:
            self.callback(self.lower_val, self.upper_val, self.home_val)

    def get_values(self):
        """获取当前的所有值"""
        return {
            "lower": self.lower_val,
            "upper": self.upper_val,
            "home": self.home_val
        }

    def set_circle_size(self, size):
        """设置圆形的大小"""
        if size <= 0:
            raise ValueError("圆形大小必须大于0")
        self.circle_size = size
        self.draw_slider()

    def set_track_color(self, color):
        """设置滑块轨道的颜色"""
        if not color:
            raise ValueError("颜色值不能为空")
        self.track_color = color
        self.draw_slider()

    def enable(self):
        """启用滑块的所有交互功能"""
        # 启用所有按钮
        self.lower_minus_btn.configure(state="normal")
        self.lower_plus_btn.configure(state="normal")
        self.upper_minus_btn.configure(state="normal")
        self.upper_plus_btn.configure(state="normal")
        
        # 重新绑定按钮事件
        self.lower_minus_btn.bind('<Button-1>', lambda e: self.start_repeat(self.lower_minus))
        self.lower_minus_btn.bind('<ButtonRelease-1>', self.stop_repeat)
        
        self.lower_plus_btn.bind('<Button-1>', lambda e: self.start_repeat(self.lower_plus))
        self.lower_plus_btn.bind('<ButtonRelease-1>', self.stop_repeat)
        
        self.upper_minus_btn.bind('<Button-1>', lambda e: self.start_repeat(self.upper_minus))
        self.upper_minus_btn.bind('<ButtonRelease-1>', self.stop_repeat)
        
        self.upper_plus_btn.bind('<Button-1>', lambda e: self.start_repeat(self.upper_plus))
        self.upper_plus_btn.bind('<ButtonRelease-1>', self.stop_repeat)
        
        # 重新绑定画布事件
        self.bind_events()
        
        # 恢复画布的交互状态
        self.canvas.configure(cursor="arrow")

    def disable(self):
        """禁用滑块的所有交互功能"""
        # 禁用所有按钮
        self.lower_minus_btn.configure(state="disabled")
        self.lower_plus_btn.configure(state="disabled")
        self.upper_minus_btn.configure(state="disabled")
        self.upper_plus_btn.configure(state="disabled")
        
        # 解绑按钮事件
        self.lower_minus_btn.unbind('<Button-1>')
        self.lower_minus_btn.unbind('<ButtonRelease-1>')
        
        self.lower_plus_btn.unbind('<Button-1>')
        self.lower_plus_btn.unbind('<ButtonRelease-1>')
        
        self.upper_minus_btn.unbind('<Button-1>')
        self.upper_minus_btn.unbind('<ButtonRelease-1>')
        
        self.upper_plus_btn.unbind('<Button-1>')
        self.upper_plus_btn.unbind('<ButtonRelease-1>')
        
        # 解绑所有画布事件
        for tag in ['lower_hit', 'upper_hit', 'home_hit']:
            self.canvas.tag_unbind(tag, '<Enter>')
            self.canvas.tag_unbind(tag, '<Leave>')
            self.canvas.tag_unbind(tag, '<Button-1>')
        
        self.canvas.unbind('<B1-Motion>')
        self.canvas.unbind('<ButtonRelease-1>')
        
        # 设置画布为禁用状态
        self.canvas.configure(cursor="arrow")
        
        # 停止任何正在进行的重复动作
        self.stop_repeat()

    def on_resize(self, event):
        """处理 Canvas 大小变化"""
        self.canvas_width = event.width
        self.canvas_height = max(event.height, self.min_height)  # 确保最小高度
        self.draw_slider()