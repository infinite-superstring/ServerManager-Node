import logging
import os.path
import sys
import inspect
from logging.handlers import TimedRotatingFileHandler

# 添加自定义的日志级别SUCCESS，并设置其颜色为蓝色
logging.SUCCESS = 15
logging.addLevelName(logging.SUCCESS, "SUCCESS")

class ColoredFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: '34',  # Blue
        logging.INFO: '37',   # White
        logging.WARNING: '33',  # Yellow
        logging.ERROR: '31',  # Red
        logging.CRITICAL: '31',  # Red
        logging.SUCCESS: '34'  # Blue
    }

    def __init__(self, fmt=None, datefmt=None, style='%', use_color=True):
        super().__init__(fmt, datefmt, style)
        self.use_color = use_color

    def format(self, record):
        if self.use_color and record.levelno in self.COLORS:
            log_color = self.COLORS.get(record.levelno)
            record.msg = f"\033[{log_color}m{record.msg}\033[0m"
        return super().format(record)

class MyFormatter(logging.Formatter):
    def format(self, record):
        if record.levelno == logging.SUCCESS:
            caller_frame = inspect.currentframe().f_back
            record.filename = caller_frame.f_globals.get('__file__')
            record.lineno = caller_frame.f_lineno
        return super().format(record)

class MyLogger(logging.Logger):
    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)
        self.SUCCESS = logging.SUCCESS

# 创建日志记录器
logger = MyLogger(__name__)
logger.setLevel(logging.DEBUG)

# 创建 TimedRotatingFileHandler
if not os.path.exists("logs"):
    os.mkdir("logs")
file_handler = TimedRotatingFileHandler(filename="logs/latest.log", when="midnight", interval=1, backupCount=15)
file_formatter = MyFormatter("%(asctime)s | %(levelname)s | %(filename)s:%(funcName)s:%(lineno)d - %(message)s")
file_handler.setFormatter(file_formatter)

# 添加文件 handler 到 logger
logger.addHandler(file_handler)

# 创建控制台输出的 handler 和 formatter
console_handler = logging.StreamHandler(sys.stdout)
console_formatter = ColoredFormatter("%(asctime)s | %(levelname)s | %(filename)s:%(funcName)s:%(lineno)d - %(message)s", use_color=True)
console_handler.setFormatter(console_formatter)

# 添加控制台 handler 到 logger
logger.addHandler(console_handler)
