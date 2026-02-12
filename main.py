import tkinter as tk
from tkinter import Canvas
import psutil
import threading
import time
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item
import sys

try:
    import GPUtil
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False


class ResourceBubble:
    """Visual bubble indicator for a single resource metric"""
    
    def __init__(self, canvas, x, y, width, height, label, max_value=100, unit="%", is_temperature=False):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.label = label
        self.max_value = max_value
        self.unit = unit
        self.value = 0
        self.is_temperature = is_temperature
        
        # Create bubble background - dark theme
        self.bg_rect = canvas.create_rectangle(
            x, y, x + width, y + height,
            fill="#2b2b2b", outline="#404040", width=1
        )
        
        # Create fill rectangle (will be colored based on value)
        self.fill_rect = canvas.create_rectangle(
            x, y, x, y + height,
            fill="#4CAF50", outline=""
        )
        
        # Create label text - light text for dark theme
        text_y = y + height // 2
        self.label_text = canvas.create_text(
            x + 5, text_y,
            text=label, anchor="w",
            font=("Segoe UI", 8, "bold"), fill="#e0e0e0"
        )
        
        # Create value text - light text for dark theme
        self.value_text = canvas.create_text(
            x + width - 5, text_y,
            text=f"0{unit}", anchor="e",
            font=("Segoe UI", 8, "bold"), fill="#e0e0e0"
        )
    
    def interpolate_color(self, value_percent):
        """Calculate gradient color from green to yellow to red based on percentage"""
        # 0-50%: green to yellow
        # 50-100%: yellow to red
        
        if value_percent <= 50:
            # Green to Yellow
            ratio = value_percent / 50.0
            r = int(76 + (255 - 76) * ratio)
            g = int(175 + (235 - 175) * ratio)
            b = int(80 - 80 * ratio)
        else:
            # Yellow to Red
            ratio = (value_percent - 50) / 50.0
            r = 255
            g = int(235 - (235 - 82) * ratio)
            b = int(59 * (1 - ratio))
        
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def interpolate_temperature_color(self, temp_celsius):
        """Calculate color for GPU temperature (different thresholds than percentage)"""
        # < 50°C: green
        # 50-60°C: yellow
        # 60-70°C: orange
        # > 70°C: red
        
        if temp_celsius < 50:
            # Green
            return "#4CAF50"
        elif temp_celsius < 60:
            # Green to Yellow transition
            ratio = (temp_celsius - 50) / 10.0
            r = int(76 + (255 - 76) * ratio)
            g = int(175 + (235 - 175) * ratio)
            b = int(80 - 80 * ratio)
            return f"#{r:02x}{g:02x}{b:02x}"
        elif temp_celsius < 70:
            # Yellow to Orange transition
            ratio = (temp_celsius - 60) / 10.0
            r = 255
            g = int(235 - (235 - 165) * ratio)  # 235 to 165
            b = int(59 * (1 - ratio))
            return f"#{r:02x}{g:02x}{b:02x}"
        else:
            # Orange to Red (70°C+)
            ratio = min((temp_celsius - 70) / 30.0, 1.0)  # Cap at 100°C
            r = 255
            g = int(165 - (165 - 82) * ratio)  # 165 to 82
            b = int(59 * (1 - ratio))
            return f"#{r:02x}{g:02x}{b:02x}"
    
    def update(self, value):
        """Update bubble with new value"""
        self.value = min(value, self.max_value)
        value_percent = (self.value / self.max_value) * 100
        
        # Calculate fill width
        fill_width = (self.value / self.max_value) * self.width
        
        # Update fill rectangle
        self.canvas.coords(
            self.fill_rect,
            self.x, self.y, self.x + fill_width, self.y + self.height
        )
        
        # Update color - use temperature-specific coloring if this is a temperature metric
        if self.is_temperature:
            color = self.interpolate_temperature_color(self.value)
        else:
            color = self.interpolate_color(value_percent)
        self.canvas.itemconfig(self.fill_rect, fill=color)
        
        # Update value text
        if self.unit == "°C":
            text = f"{int(self.value)}{self.unit}"
        else:
            text = f"{self.value:.0f}{self.unit}"
        self.canvas.itemconfig(self.value_text, text=text)


class ResourceMonitor:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Resource Monitor")
        
        # Window configuration - no title bar, always on top
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.wm_attributes('-transparentcolor', '#1e1e1e')
        
        # Compact size to fit in taskbar area
        self.window_width = 450
        self.window_height = 40  # Reduced height to fit taskbar
        screen_width = self.root.winfo_screenwidth()
        x = screen_width - self.window_width - 10
        y = 10
        self.root.geometry(f'{self.window_width}x{self.window_height}+{x}+{y}')

        self.force_topmost()

        # Variables for dragging
        self.offset_x = 0
        self.offset_y = 0
        
        # Running flag
        self.running = True
        self.window_visible = True
        
        # Tray icon
        self.tray_icon = None
        
        self.create_widgets()
        self.setup_dragging()
        self.create_tray_icon()
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self.update_stats, daemon=True)
        self.monitor_thread.start()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        
    def create_widgets(self):
        """Create UI elements"""
        # Main canvas for drawing bubbles - dark theme
        self.canvas = Canvas(
            self.root, 
            width=self.window_width, 
            height=self.window_height,
            bg='#1e1e1e',
            highlightthickness=0
        )
        self.canvas.pack(fill='both', expand=True)
        
        # Create resource bubbles - 5 metrics in a row
        bubble_width = 85
        bubble_height = 30
        bubble_y = 5
        spacing = 3
        
        start_x = 5
        
        # CPU Bubble
        self.cpu_bubble = ResourceBubble(
            self.canvas, start_x, bubble_y, bubble_width, bubble_height, 
            "CPU", 100, "%"
        )
        
        # RAM Bubble
        self.ram_bubble = ResourceBubble(
            self.canvas, start_x + (bubble_width + spacing) * 1, bubble_y, 
            bubble_width, bubble_height, "RAM", 100, "%"
        )
        
        # GPU Bubble
        self.gpu_bubble = ResourceBubble(
            self.canvas, start_x + (bubble_width + spacing) * 2, bubble_y, 
            bubble_width, bubble_height, "GPU", 100, "%"
        )
        
        # VRAM Bubble
        self.vram_bubble = ResourceBubble(
            self.canvas, start_x + (bubble_width + spacing) * 3, bubble_y, 
            bubble_width, bubble_height, "VRAM", 100, "%"
        )
        
        # GPU Temperature Bubble (with special temperature coloring)
        self.temp_bubble = ResourceBubble(
            self.canvas, start_x + (bubble_width + spacing) * 4, bubble_y, 
            bubble_width, bubble_height, "Temp", 100, "°C", is_temperature=True
        )
        
    def setup_dragging(self):
        """Setup window dragging"""
        def start_move(event):
            self.offset_x = event.x
            self.offset_y = event.y
            
        def do_move(event):
            x = self.root.winfo_x() + event.x - self.offset_x
            y = self.root.winfo_y() + event.y - self.offset_y
            self.root.geometry(f'+{x}+{y}')
        
        self.canvas.bind('<Button-1>', start_move)
        self.canvas.bind('<B1-Motion>', do_move)
    
    def create_tray_icon(self):
        """Create system tray icon"""
        # Create simple icon
        image = Image.new('RGB', (64, 64), color='#4CAF50')
        draw = ImageDraw.Draw(image)
        draw.rectangle([8, 8, 56, 56], fill='white')
        draw.text((16, 20), 'RM', fill='#4CAF50')
        
        # Tray menu
        menu = pystray.Menu(
            item('Show/Hide', self.toggle_window, default=True),
            item('Exit', self.quit_app)
        )
        
        self.tray_icon = pystray.Icon("resource_monitor", image, "Resource Monitor", menu)
        
        # Run icon in separate thread
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
    
    def toggle_window(self, icon=None, item=None):
        """Toggle window visibility"""
        if self.window_visible:
            self.hide_window()
        else:
            self.show_window()
    
    def hide_window(self):
        """Hide window to tray"""
        self.root.withdraw()
        self.window_visible = False
    
    def show_window(self):
        """Show window from tray"""
        self.root.deiconify()
        self.window_visible = True
    
    def get_gpu_stats(self):
        """Get GPU statistics including temperature"""
        if not GPU_AVAILABLE:
            return None, None, None
        
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]  # First GPU
                gpu_load = gpu.load * 100
                vram_load = gpu.memoryUtil * 100
                temperature = gpu.temperature if hasattr(gpu, 'temperature') else None
                return gpu_load, vram_load, temperature
        except Exception as e:
            print(f"GPU stats error: {e}")
        
        return None, None, None
    
    def update_stats(self):
        """Update statistics in separate thread"""
        while self.running:
            try:
                # CPU
                cpu_percent = psutil.cpu_percent(interval=1)
                
                # RAM
                ram = psutil.virtual_memory()
                ram_percent = ram.percent
                
                # GPU, VRAM, Temperature
                gpu_percent, vram_percent, gpu_temp = self.get_gpu_stats()
                
                # Update UI
                self.root.after(0, self.update_bubbles, 
                               cpu_percent, ram_percent, 
                               gpu_percent, vram_percent, gpu_temp)
                
                time.sleep(1)  # Update every second
            except Exception as e:
                print(f"Update error: {e}")
                time.sleep(1)
    
    def update_bubbles(self, cpu, ram, gpu, vram, temp):
        """Update all bubble displays"""
        self.cpu_bubble.update(cpu)
        self.ram_bubble.update(ram)
        
        if gpu is not None:
            self.gpu_bubble.update(gpu)
        else:
            self.gpu_bubble.update(0)
        
        if vram is not None:
            self.vram_bubble.update(vram)
        else:
            self.vram_bubble.update(0)
        
        if temp is not None:
            self.temp_bubble.update(temp)
        else:
            self.temp_bubble.update(0)
    
    def force_topmost(self):
        self.root.attributes('-topmost', False)  # Toggle off briefly
        self.root.attributes('-topmost', True)   # Toggle back on
        self.root.lift()  # Force raise in z-order
        self.root.after(100, self.force_topmost)  # Repeat every 0.5 sec; adjust if needed

    def quit_app(self, icon=None, item=None):
        """Exit application"""
        self.running = False
        
        # Properly stop and remove tray icon
        if self.tray_icon:
            self.tray_icon.visible = False
            self.tray_icon.stop()
        
        # Give tray icon time to cleanup
        time.sleep(0.1)
        
        # Destroy window and exit
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass
        
        sys.exit(0)
    
    def run(self):
        """Run application"""
        self.root.mainloop()


if __name__ == "__main__":
    app = ResourceMonitor()
    app.run()