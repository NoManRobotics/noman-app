import os
from customtkinter import CTkOptionMenu, CTkLabel, CTkImage
from PIL import Image
from utils.resource_loader import ResourceLoader

class CustomOptionMenu(CTkOptionMenu):
    def __init__(self, 
                 master: any,
                 border_width: int = 0,
                 border_color: str = "black",
                 border_hover_color: str = None,
                 **kwargs):
        
        # 在调用父类初始化之前设置属性
        self._border_width = border_width
        self._border_color = border_color
        self._border_hover_color = border_hover_color if border_hover_color else border_color
        
        super().__init__(master, **kwargs)
        
        # 设置自定义下拉图标
        icon_path = ResourceLoader.get_asset_path(os.path.join('icons', 'downarrow.png'))
        self.arrow_image = CTkImage(Image.open(icon_path), size=(18, 18))
        self.image_label = CTkLabel(self, text="", image=self.arrow_image)
        
        # 删除原有的箭头
        self._canvas.delete("dropdown_arrow")
        
        # 设置新图标的背景色
        color = self._canvas.itemcget("inner_parts_right", "fill")
        self.image_label.configure(fg_color=color, bg_color=color)
        
        # 修改放置新图标的部分
        grid_info = self._text_label.grid_info()
        # 调整padding以确保边框显示一致
        grid_info["padx"] = (self._border_width + 5, self._border_width + 5)  # 左右padding都加上border_width
        grid_info["pady"] = self._border_width  # 上下padding
        grid_info["sticky"] = "e"
        self.image_label.grid(**grid_info)
        
        # 强制更新布局
        self.update_idletasks()
        
        # 添加事件绑定
        self.image_label.bind("<Button-1>", self._clicked)
        self.image_label.bind("<Enter>", self._on_enter)
        self.image_label.bind("<Leave>", self._on_leave)
        
        self._draw()

    def _draw(self, no_color_updates=False):
        super()._draw(no_color_updates)
        
        # 修改边框绘制
        if self._border_width > 0:
            self._canvas.configure(bg=self._apply_appearance_mode(self._border_color))
            # 确保边框宽度一致
            self._canvas.itemconfig("inner_parts",
                                  outline=self._apply_appearance_mode(self._border_color),
                                  width=self._border_width)  # 确保边框宽度一致
            # 添加底部和右侧边框
            self._canvas.create_line(0, self._canvas.winfo_height(), self._canvas.winfo_width(), self._canvas.winfo_height(),
                                     fill=self._apply_appearance_mode(self._border_color), width=self._border_width*2)
            self._canvas.create_line(self._canvas.winfo_width(), 0, self._canvas.winfo_width(), self._canvas.winfo_height(),
                                     fill=self._apply_appearance_mode(self._border_color), width=self._border_width*2)

    def _on_enter(self, event=0):
        super()._on_enter(event)
        if hasattr(self, 'image_label'):
            color = self._apply_appearance_mode(self._button_hover_color)
            self.image_label.configure(fg_color=color, bg_color=color)
        if self._border_width > 0:
            self._canvas.itemconfig("inner_parts",
                                  outline=self._apply_appearance_mode(self._border_hover_color))
            # 更新底部和右侧边框颜色
            self._canvas.create_line(0, self._canvas.winfo_height(), self._canvas.winfo_width(), self._canvas.winfo_height(),
                                     fill=self._apply_appearance_mode(self._border_hover_color), width=self._border_width*2)
            self._canvas.create_line(self._canvas.winfo_width(), 0, self._canvas.winfo_width(), self._canvas.winfo_height(),
                                     fill=self._apply_appearance_mode(self._border_hover_color), width=self._border_width*2)

    def _on_leave(self, event=0):
        super()._on_leave(event)
        if hasattr(self, 'image_label'):
            color = self._apply_appearance_mode(self._button_color)
            self.image_label.configure(fg_color=color, bg_color=color)
        if self._border_width > 0:
            self._canvas.itemconfig("inner_parts",
                                  outline=self._apply_appearance_mode(self._border_color))
            # 恢复底部和右侧边框颜色
            self._canvas.create_line(0, self._canvas.winfo_height(), self._canvas.winfo_width(), self._canvas.winfo_height(),
                                     fill=self._apply_appearance_mode(self._border_color), width=self._border_width*2)
            self._canvas.create_line(self._canvas.winfo_width(), 0, self._canvas.winfo_width(), self._canvas.winfo_height(),
                                     fill=self._apply_appearance_mode(self._border_color), width=self._border_width*2) 