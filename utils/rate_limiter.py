import time
import threading
from datetime import datetime
from utils.logger import logger

class RateLimiter:
    """Kiểm soát tốc độ gọi API để tránh bị giới hạn rate limit"""
    
    def __init__(self, calls_per_minute):
        """
        Khởi tạo rate limiter
        
        Args:
            calls_per_minute: Số lần gọi tối đa cho phép mỗi phút
        """
        self.rate = calls_per_minute
        self.interval = 60.0 / calls_per_minute  # Tính thời gian nghỉ giữa các lần gọi
        self.last_call_time = 0
        self.lock = threading.Lock()  # Đảm bảo thread-safe
        
        logger.debug(f"Khởi tạo RateLimiter: {calls_per_minute} lần gọi/phút "
                     f"(mỗi lần gọi cách nhau {self.interval:.2f}s)")
    
    def wait_if_needed(self):
        """
        Chờ đợi nếu cần thiết để đảm bảo tốc độ gọi API
        
        Returns:
            float: Thời gian đã chờ (giây)
        """
        with self.lock:
            current_time = time.time()
            elapsed_time = current_time - self.last_call_time
            
            wait_time = 0
            
            # Nếu chưa đủ thời gian nghỉ, chờ thêm
            if elapsed_time < self.interval:
                wait_time = self.interval - elapsed_time
                time.sleep(wait_time)
            
            # Cập nhật thời gian gọi cuối cùng
            self.last_call_time = time.time()
            
            if wait_time > 0:
                logger.debug(f"Đã chờ {wait_time:.2f}s để đảm bảo rate limit")
            
            return wait_time
    
    def update_rate(self, new_calls_per_minute):
        """
        Cập nhật tốc độ gọi API
        
        Args:
            new_calls_per_minute: Số lần gọi mới tối đa cho phép mỗi phút
        """
        with self.lock:
            self.rate = new_calls_per_minute
            self.interval = 60.0 / new_calls_per_minute
            logger.info(f"Đã cập nhật RateLimiter: {new_calls_per_minute} lần gọi/phút")