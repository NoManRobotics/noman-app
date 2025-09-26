import os
import sys
from pathlib import Path

class ResourceLoader:
    @staticmethod
    def get_project_root():
        """get project root directory path"""
        if getattr(sys, 'frozen', False):
            return Path(sys._MEIPASS)
        return Path(__file__).parent.parent  # return src directory
    
    @staticmethod
    def get_asset_path(relative_path):
        """get asset file path
        
        Args:
            relative_path: relative path to assets directory
            
        Returns:
            str: full path to asset file
        """
        root_dir = ResourceLoader.get_project_root()
        asset_path = os.path.join(root_dir, 'assets', relative_path)
        
        if not os.path.exists(asset_path):
            raise FileNotFoundError(f"Asset file not found: {asset_path}")
            
        return asset_path
    
    @staticmethod
    def get_code_path(relative_path):
        """get controller code file path
        
        Args:
            relative_path: relative path to ControllerCode directory
            
        Returns:
            str: full path to controller code file
        """
        root_dir = ResourceLoader.get_project_root()
        code_path = os.path.join(root_dir, 'ControllerCode', relative_path)
        
        if not os.path.exists(code_path):
            raise FileNotFoundError(f"Code file not found: {code_path}")
            
        return code_path

    @staticmethod
    def get_thirdparty_path(relative_path):
        """get thirdparty tool path
        
        Args:
            relative_path: relative path to thirdparty directory
            
        Returns:
            str: full path to thirdparty tool
        """
        root_dir = ResourceLoader.get_project_root()
        thirdparty_path = os.path.join(root_dir, 'thirdparty', relative_path)
        
        if not os.path.exists(thirdparty_path):
            raise FileNotFoundError(f"Thirdparty tool not found: {thirdparty_path}")
            
        return thirdparty_path

    @staticmethod
    def get_config_path(relative_path):
        """get config file path
        
        Args:
            relative_path: relative path to config directory
            
        Returns:
            str: full path to config file
        """
        root_dir = ResourceLoader.get_project_root()
        config_path = os.path.join(root_dir, 'config', relative_path)
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
            
        return config_path