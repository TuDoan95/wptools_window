import logging
import os
import sys
import platform
import codecs
from datetime import datetime
from logging.handlers import RotatingFileHandler
from config import config

# Thiết lập mã hóa UTF-8 cho console Windows
if platform.system() == 'Windows':
    os.system('chcp 65001 > nul')  # Chuyển sang UTF-8 và ẩn output

def setup_logger(name='wp_auto_content'):
    """
    Thiết lập hệ thống logging
    
    Args:
        name: Tên logger
        
    Returns:
        Logger instance
    """
    # Tạo logger
    logger = logging.getLogger(name)
    
    # Đặt mức log
    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)
    
    # Xóa các handler nếu đã tồn tại
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # Định dạng log
    log_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    
    # Handler cho console với bộ xử lý lỗi mã hóa
    class EncodingStreamHandler(logging.StreamHandler):
        def emit(self, record):
            try:
                msg = self.format(record)
                stream = self.stream
                stream.write(msg + self.terminator)
                self.flush()
            except UnicodeEncodeError:
                # Nếu có lỗi mã hóa, thử chuyển đổi và bỏ qua ký tự không hiển thị được
                msg = self.format(record)
                if sys.platform == 'win32':
                    try:
                        stream = self.stream
                        stream.write(msg.encode('cp1252', errors='replace').decode('cp1252') + self.terminator)
                    except:
                        pass
                self.flush()
            except Exception:
                self.handleError(record)
    
    console_handler = EncodingStreamHandler()
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)
    
    # Handler cho file với encoding UTF-8
    try:
        # Đảm bảo thư mục tồn tại
        os.makedirs(os.path.dirname(config.LOG_FILE), exist_ok=True)
        
        # Tạo rotating file handler để giới hạn kích thước file log
        file_handler = RotatingFileHandler(
            config.LOG_FILE,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=config.LOG_RETENTION_DAYS,
            encoding='utf-8'  # Thêm encoding UTF-8
        )
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.error(f"Không thể tạo file log: {e}")
    
    return logger

# Tạo instance logger toàn cục
logger = setup_logger()