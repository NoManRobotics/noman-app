import tkinter as tk

class CircularProgress(tk.Canvas):
    """A custom circular progress bar widget.
    
    Attributes:
        size (int): The size of the widget in pixels
        bg_color (str): Background circle color
        fg_color (str): Progress arc color
        text_color (str): Percentage text color
        width (int): Line width of the circles
    """
    
    def __init__(self, parent, size=130, bg_color='#CCCCCC', fg_color='red', 
                 text_color='black', width=3, **kwargs):
        """Initialize the CircularProgress widget.
        
        Args:
            parent: The parent widget
            size (int): Size of the widget in pixels
            bg_color (str): Color of the background circle
            fg_color (str): Color of the progress arc
            text_color (str): Color of the percentage text
            width (int): Line width of the circles
            **kwargs: Additional arguments passed to the Canvas widget
        """
        super().__init__(parent, width=size, height=size, bg='#dbdbdb', 
                        highlightthickness=0, **kwargs)
        
        # Store parameters
        self.size = size
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.text_color = text_color
        self.line_width = width
        
        self.angle = 0
        self._value = 0
        
        # Initialize the widget
        self._draw_background()
        self._create_text()
        
    def _draw_background(self):
        """Draw the background circle."""
        padding = self.line_width + 2
        self.create_arc(
            padding, padding,
            self.size - padding, self.size - padding,
            start=0, extent=359.9,
            outline=self.bg_color,
            style='arc',
            width=self.line_width
        )
        
    def _create_text(self):
        """Create the percentage text display."""
        self.text_item = self.create_text(
            self.size // 2, 
            self.size // 2,
            text="0%",
            fill=self.text_color,
            font=('Arial', int(self.size / 10))
        )
        
    def _draw_progress_arc(self):
        """Draw the progress arc."""
        self.delete("progress")
        
        if self.angle > 0:
            padding = self.line_width + 2
            self.create_arc(
                padding, padding,
                self.size - padding, self.size - padding,
                start=90, 
                extent=-self.angle,
                outline=self.fg_color,
                style='arc',
                width=self.line_width,
                tags="progress"
            )
            
    def set(self, value):
        """Set the progress value (0-100).
        
        Args:
            value (float): Progress value between 0 and 100
        """
        # Ensure value is between 0 and 100
        self._value = min(100, max(0, float(value)))
        
        # Convert value to angle (360 degrees = 100%)
        self.angle = int(360 * (self._value / 100))
        
        # Update the display
        self._draw_progress_arc()
        self.itemconfig(self.text_item, text=f"{int(self._value)}%")
        
    def get(self):
        """Get the current progress value.
        
        Returns:
            float: Current progress value (0-100)
        """
        return self._value 