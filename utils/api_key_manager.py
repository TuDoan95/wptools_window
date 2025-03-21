import time
from datetime import datetime
from typing import List, Dict, Any
from utils.logger import logger

class APIKeyManager:
    """Quản lý nhiều API key với khả năng tự động xoay vòng và phục hồi"""
    
    def __init__(self, api_keys: List[str], max_errors: int = 5, error_cooldown: int = 300):
        """
        Khởi tạo quản lý API key
        
        Args:
            api_keys: Danh sách API key
            max_errors: Số lần lỗi tối đa trước khi vô hiệu hóa key
            error_cooldown: Thời gian làm mát trước khi thử lại key bị vô hiệu hóa (giây)
        """
        if not api_keys:
            raise ValueError("Danh sách API key không được để trống")
        
        self.keys = api_keys
        self.max_errors = max_errors
        self.error_cooldown = error_cooldown
        
        # Theo dõi trạng thái các key
        self.current_index = 0
        self.error_counts = {i: 0 for i in range(len(api_keys))}
        self.call_counts = {i: 0 for i in range(len(api_keys))}
        self.disabled_keys = set()
        self.last_error_time = {i: 0 for i in range(len(api_keys))}
        self.error_types = {i: {} for i in range(len(api_keys))}
        
        logger.info(f"Khởi tạo APIKeyManager với {len(api_keys)} API key")
    
    def get_current_key(self) -> str:
        """
        Lấy API key hiện tại, tự động chuyển sang key khác nếu key hiện tại bị vô hiệu hóa
        
        Returns:
            str: API key hiện tại
        """
        # Kiểm tra các key đã hết thời gian làm mát
        self._reactivate_cooled_keys()
        
        # Nếu key hiện tại bị vô hiệu hóa, chuyển sang key khác
        if self.current_index in self.disabled_keys:
            return self.next_key()
        
        # Nếu tất cả key đều bị vô hiệu hóa, reset tất cả
        if len(self.disabled_keys) == len(self.keys):
            logger.warning("Tất cả API key đều bị vô hiệu hóa! Reset tất cả key.")
            self.reset_all_keys()
        
        return self.keys[self.current_index]
    
    def _reactivate_cooled_keys(self):
        """Kích hoạt lại các key đã hết thời gian làm mát"""
        current_time = time.time()
        
        for key_idx in list(self.disabled_keys):
            if current_time - self.last_error_time[key_idx] > self.error_cooldown:
                logger.info(f"API key {key_idx + 1} đã hết thời gian làm mát. Kích hoạt lại.")
                self.disabled_keys.remove(key_idx)
                # Reset lỗi một nửa để key có cơ hội thử lại
                self.error_counts[key_idx] = max(int(self.error_counts[key_idx] // 2), 0)
    
    def next_key(self) -> str:
        """
        Chuyển sang API key tiếp theo không bị vô hiệu hóa
        
        Returns:
            str: API key tiếp theo
        """
        old_index = self.current_index
        
        # Tìm key tiếp theo không bị vô hiệu hóa
        for _ in range(len(self.keys)):
            self.current_index = (self.current_index + 1) % len(self.keys)
            
            if self.current_index not in self.disabled_keys:
                break
        
        # Nếu không tìm thấy key khả dụng, reset tất cả
        if self.current_index in self.disabled_keys:
            logger.warning("Không còn API key khả dụng! Reset tất cả key.")
            self.reset_all_keys()
            self.current_index = 0
        
        logger.info(f"Chuyển từ API key {old_index + 1} sang API key {self.current_index + 1}")
        return self.keys[self.current_index]
    
    def mark_success(self):
        """Đánh dấu lần gọi API thành công và giảm điểm lỗi nếu có"""
        self.call_counts[self.current_index] += 1
        
        # Giảm số lỗi nếu key đang hoạt động tốt
        if self.error_counts[self.current_index] > 0:
            self.error_counts[self.current_index] = max(0, self.error_counts[self.current_index] - 0.5)
    
    def mark_error(self, error_msg: str) -> bool:
        """
        Đánh dấu lỗi cho API key hiện tại và phân tích lỗi
        
        Args:
            error_msg: Thông báo lỗi
            
        Returns:
            bool: True nếu đã chuyển sang key mới, False nếu không
        """
        # Cập nhật thống kê
        self.last_error_time[self.current_index] = time.time()
        self.call_counts[self.current_index] += 1
        
        # Phân tích chi tiết về lỗi
        error_details = self._analyze_error(error_msg)
        
        # Cập nhật thống kê lỗi
        if error_details["type"] not in self.error_types[self.current_index]:
            self.error_types[self.current_index][error_details["type"]] = 1
        else:
            self.error_types[self.current_index][error_details["type"]] += 1
        
        # Tăng điểm lỗi dựa trên mức độ nghiêm trọng
        error_increment = 2 if error_details["severity"] == "high" else 1 if error_details["severity"] == "medium" else 0.5
        self.error_counts[self.current_index] += error_increment
        
        logger.warning(f"API key {self.current_index + 1} gặp lỗi {error_details['type']} "
                      f"(mức {error_details['severity']}). "
                      f"Điểm lỗi: {self.error_counts[self.current_index]}/{self.max_errors}. "
                      f"Chi tiết: {error_msg}")
        
        # Xử lý tùy theo loại lỗi và mức độ nghiêm trọng
        if error_details["should_switch"]:
            logger.warning(f"API key {self.current_index + 1} cần được chuyển ngay lập tức do lỗi {error_details['type']}.")
            
            # Nếu là lỗi nghiêm trọng hoặc vượt quá ngưỡng, vô hiệu hóa key
            if error_details["severity"] == "high" or self.error_counts[self.current_index] >= self.max_errors:
                self.disabled_keys.add(self.current_index)
                
                # Đặt thời gian nghỉ dài hơn cho các lỗi nghiêm trọng
                if "cooldown" in error_details:
                    logger.warning(f"API key {self.current_index + 1} sẽ nghỉ trong {error_details['cooldown']}s.")
            
            self.next_key()
            return True
        
        # Nếu vượt quá số lỗi cho phép
        if self.error_counts[self.current_index] >= self.max_errors:
            logger.error(f"API key {self.current_index + 1} đã vượt quá giới hạn lỗi. Vô hiệu hóa key này.")
            self.disabled_keys.add(self.current_index)
            self.next_key()
            return True
        
        return False
    
    def _analyze_error(self, error_msg: str) -> Dict[str, Any]:
        """
        Phân tích lỗi để xác định loại lỗi
        
        Args:
            error_msg: Thông báo lỗi
            
        Returns:
            Dict: Chi tiết về lỗi
        """
        error_details = {
            "type": "unknown",
            "severity": "normal",
            "should_switch": False
        }
        
        error_msg_lower = error_msg.lower()
        
        # Phân tích loại lỗi dựa trên nội dung
        if any(term in error_msg_lower for term in ["quota", "rate limit", "ratelimit", "too many requests", "429"]):
            error_details["type"] = "rate_limit"
            error_details["severity"] = "high"
            error_details["should_switch"] = True
            error_details["cooldown"] = self.error_cooldown * 2  # Nghỉ lâu hơn cho rate limit
        
        elif any(term in error_msg_lower for term in ["invalid key", "unauthorized", "not authorized", "auth", "403", "401"]):
            error_details["type"] = "authentication"
            error_details["severity"] = "high"
            error_details["should_switch"] = True
            error_details["cooldown"] = self.error_cooldown * 5  # Key không hợp lệ cần nghỉ rất lâu
        
        elif any(term in error_msg_lower for term in ["timeout", "timed out", "connection", "network"]):
            error_details["type"] = "network"
            error_details["severity"] = "medium"
            error_details["should_switch"] = self.error_counts[self.current_index] >= 2
        
        elif any(term in error_msg_lower for term in ["server", "500", "502", "503", "504"]):
            error_details["type"] = "server"
            error_details["severity"] = "medium"
            error_details["should_switch"] = self.error_counts[self.current_index] >= 2
        
        elif any(term in error_msg_lower for term in ["content", "inappropriate", "blocked", "rejected"]):
            error_details["type"] = "content_policy"
            error_details["severity"] = "high"
            error_details["should_switch"] = True
        
        return error_details
    
    def reset_key(self, index: int):
        """Reset một API key cụ thể"""
        if 0 <= index < len(self.keys):
            self.error_counts[index] = 0
            self.error_types[index] = {}
            if index in self.disabled_keys:
                self.disabled_keys.remove(index)
                logger.info(f"Đã kích hoạt lại API key {index + 1}")
    
    def reset_all_keys(self):
        """Reset tất cả API key về trạng thái ban đầu"""
        self.error_counts = {i: 0 for i in range(len(self.keys))}
        self.error_types = {i: {} for i in range(len(self.keys))}
        self.disabled_keys = set()
        logger.info("Đã reset tất cả API key về trạng thái ban đầu")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Lấy thống kê về sử dụng API key
        
        Returns:
            Dict: Thống kê chi tiết
        """
        key_stats = []
        for i in range(len(self.keys)):
            key_stat = {
                "index": i,
                "active": i not in self.disabled_keys,
                "errors": self.error_counts[i],
                "calls": self.call_counts[i],
                "error_types": self.error_types[i]
            }
            
            if self.last_error_time[i] > 0:
                key_stat["last_error"] = datetime.fromtimestamp(
                    self.last_error_time[i]
                ).strftime("%Y-%m-%d %H:%M:%S")
            else:
                key_stat["last_error"] = "None"
            
            key_stats.append(key_stat)
        
        return {
            "total_keys": len(self.keys),
            "active_keys": len(self.keys) - len(self.disabled_keys),
            "disabled_keys": list(self.disabled_keys),
            "current_key": self.current_index,
            "key_stats": key_stats
        }