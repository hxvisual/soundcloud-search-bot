import logging
import sys
import datetime
import os
from typing import Optional

class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"
    
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

class ColoredFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: Colors.BRIGHT_CYAN,
        logging.INFO: Colors.BRIGHT_GREEN,
        logging.WARNING: Colors.BRIGHT_YELLOW,
        logging.ERROR: Colors.BRIGHT_RED,
        logging.CRITICAL: Colors.BG_RED + Colors.WHITE
    }
    
    MODULE_COLORS = {
        "soundcloud_api": Colors.BRIGHT_MAGENTA,
        "handlers": Colors.BRIGHT_BLUE,
        "main": Colors.BRIGHT_CYAN,
        "__main__": Colors.BRIGHT_CYAN,
    }
    
    def format(self, record):
        msg = super().format(record)
        
        levelname = record.levelname
        level_color = self.LEVEL_COLORS.get(record.levelno, Colors.RESET)
        
        module_name = record.name.split('.')[-1]
        module_color = self.MODULE_COLORS.get(module_name, Colors.BRIGHT_WHITE)
        
        timestamp = datetime.datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        prefix = f"{Colors.BRIGHT_BLACK}[{timestamp}]{Colors.RESET} {level_color}[{levelname:^8}]{Colors.RESET} {module_color}[{module_name}]{Colors.RESET}"
        
        if record.levelno == logging.DEBUG:
            emoji = "🔍"
        elif record.levelno == logging.INFO:
            emoji = "ℹ️"
        elif record.levelno == logging.WARNING:
            emoji = "⚠️"
        elif record.levelno == logging.ERROR:
            emoji = "❌"
        elif record.levelno == logging.CRITICAL:
            emoji = "🚨"
        else:
            emoji = "•"
        
        message = record.getMessage()
        return f"{prefix} {emoji} {message}"

def setup_logger(name: Optional[str] = None, log_to_file: bool = True, log_file: str = "logs/bot.log"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    logger.propagate = False
    
    if log_to_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        file_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredFormatter())
    logger.addHandler(console_handler)
    
    return logger

logging.basicConfig = lambda **kwargs: None

def setup_root_logger(log_to_file: bool = True, log_file: str = "logs/bot.log"):
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    logging.root.setLevel(logging.INFO)
    
    if log_to_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        file_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(file_format)
        logging.root.addHandler(file_handler)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredFormatter())
    logging.root.addHandler(console_handler) 