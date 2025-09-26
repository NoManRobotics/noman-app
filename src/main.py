import sys
import os
import traceback
import logging
import multiprocessing

from utils.config import Config
from ui.home_frame import RobotArmApp
from noman.activation_core import ActivationManager

pyi_splash = None
if getattr(sys, 'frozen', False) and Config.operating_system == "Windows":
    try:
        import pyi_splash
    except ImportError:
        pyi_splash = None

# Setup logging
def setup_logging():
    # Use Config class to get base directory and create logs subdirectory
    base_dir = Config.get_path()
    log_dir = os.path.join(base_dir, 'logs')
    log_file = os.path.join(log_dir, 'app.log')
    
    try:
        # Ensure log directory exists
        os.makedirs(log_dir, exist_ok=True)
        
        # Clear existing logging configuration
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8', mode='a'),
                logging.StreamHandler()  # log on terminal
            ],
            force=True  # Force reconfigure logging
        )
        
        # Set third-party library log levels to WARNING to reduce noise
        logging.getLogger('transformers').setLevel(logging.WARNING)
        logging.getLogger('pybullet').setLevel(logging.WARNING)
        logging.getLogger('bullet').setLevel(logging.WARNING)
        
        # Set root logger to INFO level to reduce debug noise
        logging.getLogger().setLevel(logging.INFO)
        
        logging.info("Logging system initialized successfully")
        logging.info(f"Log file location: {log_file}")
        
    except Exception as e:
        print(f"Error setting up logging system: {str(e)}")
        # Fallback configuration: only output to console (last resort when error occurs)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()],
            force=True
        )
        logging.warning("Unable to create log file, using console output only")
        logging.error(f"Log configuration error details: {str(e)}")



def main():
    try:
        # Ensure freeze_support is called for PyInstaller compatibility with multiprocessing
        multiprocessing.freeze_support()
        
        setup_logging()
        logging.info("Initializing application...")
        
        # Check activation status
        if pyi_splash:
            pyi_splash.update_text('checking activation status...')
        
        logging.info("Checking activation status...")
        activation_manager = ActivationManager()
        is_activated = activation_manager.check_activation()
        
        if is_activated:
            logging.info("Software is activated - proceeding with startup")
        else:
            logging.warning("Software is not activated")
            print("Warning: Software is not activated. Some features may be limited.")
            print("Please activate the software through Settings > License tab.")
        
        # update Splash status
        if pyi_splash:
            pyi_splash.update_text('creating UI...')
        
        logging.info("Creating application...")
        app = RobotArmApp()
        
        if pyi_splash:
            pyi_splash.close()
        
        logging.info("Starting main loop...")
        app.mainloop()
        
    except Exception as e:
        # ensure Splash is closed when error occurs
        if pyi_splash:
            pyi_splash.close()
            
        logging.error(f"Program startup failed: {str(e)}")
        logging.error(f"Detailed error information:\n{traceback.format_exc()}")
        print(f"Error: {str(e)}")
        try:
            log_file = os.path.join(Config.get_path(), 'logs', 'app.log')
            print(f"Details have been logged to {log_file}")
        except:
            print("Details have been logged to the application log file")

if __name__ == "__main__":
    main()