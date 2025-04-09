import os
import json
from typing import Dict, Any
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("chatbot")

# 配置文件路径
CONFIG_FILE = "config.json"
# 默认配置
DEFAULT_CONFIG = {
    "model": "gemma2:27b",
    "base_url": "http://gpu.credat.com.cn",
    "memory_dir": "chat_memories",
    "max_token_limit": 4000,
    "summary_threshold": 10,  # 对话轮数达到此阈值时进行总结
    "rate_limit": {
        "requests_per_minute": 20,
        "tokens_per_minute": 4000
    },
    "security": {
        "allowed_commands": [
            "ip", 
            "system_info", 
            "disk_space", 
            "process_list", 
            "network", 
            "current_dir", 
            "list_files", 
            "memory_usage", 
            "cpu_info", 
            "date_time"
        ],
        "command_execution_enabled": True,
        "command_timeout": 10  # 命令执行超时时间（秒）
    },
    "verbose": True
}

class ConfigManager:
    """配置管理类"""
    
    def __init__(self, config_file: str = CONFIG_FILE):
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    logger.info(f"配置已从 {self.config_file} 加载")
                    return config
            except Exception as e:
                logger.error(f"加载配置文件时出错: {e}")
        
        # 如果配置文件不存在或加载失败，创建默认配置
        self._save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    
    def _save_config(self, config: Dict[str, Any]) -> None:
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info(f"配置已保存到 {self.config_file}")
        except Exception as e:
            logger.error(f"保存配置文件时出错: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self.config.get(key, default)
    
    def update(self, key: str, value: Any) -> None:
        """更新配置项"""
        self.config[key] = value
        self._save_config(self.config)