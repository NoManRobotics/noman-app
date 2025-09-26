import customtkinter as ctk

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind('<Enter>', self.show_tooltip)
        self.widget.bind('<Leave>', self.hide_tooltip)
        self.scheduled_hide = None  # 用于跟踪计划的隐藏操作

    def show_tooltip(self, event=None):
        # 如果有计划的隐藏操作，取消它
        if self.scheduled_hide:
            self.widget.after_cancel(self.scheduled_hide)
            self.scheduled_hide = None
            return
        
        # 如果tooltip已经存在，不要重新创建
        if self.tooltip:
            return
        
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip = ctk.CTkToplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        self.tooltip.configure(fg_color="white")

        label = ctk.CTkLabel(
            self.tooltip, 
            text=self.text,
            fg_color="white",
            padx=10,
            pady=5,
            justify='left'
        )
        label.pack()

    def hide_tooltip(self, event=None):
        # 计划100毫秒后隐藏tooltip
        if not self.scheduled_hide:
            self.scheduled_hide = self.widget.after(100, self._hide)

    def _hide(self):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None
        self.scheduled_hide = None