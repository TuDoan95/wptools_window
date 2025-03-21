import os
import json
import time
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, Union, List
from pathlib import Path
from utils.logger import logger
from config import config

class CacheEntry:
    """Đại diện cho một mục trong cache với metadata"""
    
    def __init__(self, data: Any, ttl: Optional[int] = None, metadata: Optional[Dict] = None):
        """
        Khởi tạo mục cache
        
        Args:
            data: Dữ liệu cần lưu cache
            ttl: Thời gian sống (giây), None = không hết hạn
            metadata: Thông tin bổ sung
        """
        self.data = data
        self.timestamp = time.time()
        self.ttl = ttl
        self.metadata = metadata or {}
        self.access_count = 0
        self.last_access = self.timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi sang dictionary để serialization"""
        return {
            'data': self.data,
            'timestamp': self.timestamp,
            'ttl': self.ttl,
            'metadata': self.metadata,
            'access_count': self.access_count,
            'last_access': self.last_access
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheEntry':
        """Tạo CacheEntry từ dictionary"""
        entry = cls(
            data=data.get('data'),
            ttl=data.get('ttl'),
            metadata=data.get('metadata', {})
        )
        entry.timestamp = data.get('timestamp', time.time())
        entry.access_count = data.get('access_count', 0)
        entry.last_access = data.get('last_access', entry.timestamp)
        return entry
    
    def is_expired(self) -> bool:
        """Kiểm tra xem mục cache có hết hạn không"""
        if self.ttl is None:
            return False
        return time.time() - self.timestamp > self.ttl
    
    def update_access(self):
        """Cập nhật thông tin truy cập"""
        self.access_count += 1
        self.last_access = time.time()

class Cache:
    """Quản lý cache với TTL động và chiến lược thay thế thông minh"""
    
    def __init__(self, file_path: Union[str, Path], default_ttl: Optional[int] = None, max_items: int = 1000):
        """
        Khởi tạo cache
        
        Args:
            file_path: Đường dẫn đến file cache
            default_ttl: Thời gian sống mặc định (giây), None = không hết hạn
            max_items: Số lượng mục tối đa trong cache
        """
        self.file_path = Path(file_path)
        self.default_ttl = default_ttl
        self.max_items = max_items
        self.cache_data = {}
        self.modified = False
        self.last_saved = 0
        self.auto_save_interval = 60  # Tự động lưu sau 60 giây nếu có thay đổi
        
        # Tạo thư mục cha nếu chưa tồn tại
        os.makedirs(self.file_path.parent, exist_ok=True)
        
        # Tải cache từ file
        self.load()
    
    def load(self) -> bool:
        """
        Tải cache từ file
        
        Returns:
            bool: True nếu tải thành công, False nếu thất bại
        """
        if not self.file_path.exists():
            logger.info(f"File cache không tồn tại: {self.file_path}")
            return False
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
                
            # Kiểm tra định dạng dữ liệu
            if isinstance(raw_data, dict) and '_cache_format_version' in raw_data:
                entries_dict = raw_data.get('entries', {})
                self.cache_data = {
                    key: CacheEntry.from_dict(entry_data) 
                    for key, entry_data in entries_dict.items()
                }
            else:
                # Định dạng cũ, chuyển đổi
                self.cache_data = {
                    key.lower().strip(): CacheEntry(
                        data=value,
                        ttl=self.default_ttl
                    ) for key, value in raw_data.items()
                }
                
            logger.info(f"Đã tải {len(self.cache_data)} mục từ cache {self.file_path.name}")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi tải cache từ {self.file_path}: {e}")
            
            # Tạo bản sao lưu nếu file bị hỏng
            self._backup_corrupted_file()
            
            # Khởi tạo cache trống
            self.cache_data = {}
            return False
    
    def _backup_corrupted_file(self):
        """Tạo bản sao lưu cho file cache bị hỏng"""
        if not self.file_path.exists():
            return
            
        timestamp = int(time.time())
        backup_file = self.file_path.with_name(f"{self.file_path.stem}.bak.{timestamp}{self.file_path.suffix}")
        
        try:
            shutil.copy2(self.file_path, backup_file)
            logger.info(f"Đã tạo bản sao lưu cache bị hỏng: {backup_file}")
        except Exception as e:
            logger.error(f"Không thể tạo bản sao lưu: {e}")
    
    def save(self) -> bool:
        """
        Lưu cache vào file
        
        Returns:
            bool: True nếu lưu thành công, False nếu thất bại
        """
        if not self.modified:
            return True
            
        try:
            # Chuyển đổi dữ liệu cache sang định dạng để serialization
            entries_dict = {
                key: entry.to_dict() for key, entry in self.cache_data.items()
            }
            
            # Tạo cấu trúc dữ liệu với metadata
            cache_data = {
                '_cache_format_version': 2,
                '_last_saved': time.time(),
                '_item_count': len(self.cache_data),
                'entries': entries_dict
            }
            
            # Lưu vào file tạm trước
            temp_file = self.file_path.with_name(f"{self.file_path.stem}.tmp{self.file_path.suffix}")
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            # Đổi tên file tạm thành file chính
            os.replace(temp_file, self.file_path)
            
            self.modified = False
            self.last_saved = time.time()
            logger.info(f"Đã lưu {len(self.cache_data)} mục vào cache {self.file_path.name}")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi lưu cache vào {self.file_path}: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Lấy giá trị từ cache
        
        Args:
            key: Khóa cache
            default: Giá trị mặc định nếu không tìm thấy hoặc hết hạn
            
        Returns:
            Any: Giá trị cache hoặc giá trị mặc định
        """
        key = key.lower().strip()
        
        if key not in self.cache_data:
            return default
            
        entry = self.cache_data[key]
        
        # Kiểm tra hạn sử dụng
        if entry.is_expired():
            logger.debug(f"Mục cache '{key}' đã hết hạn")
            self.delete(key)
            return default
        
        # Cập nhật thông tin truy cập
        entry.update_access()
        self.modified = True
        
        # Tự động lưu nếu đã lâu không lưu
        self._auto_save()
        
        return entry.data
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None, metadata: Optional[Dict] = None) -> bool:
        """
        Đặt giá trị vào cache
        
        Args:
            key: Khóa cache
            value: Giá trị cần lưu
            ttl: Thời gian sống (giây), None = sử dụng default_ttl
            metadata: Thông tin bổ sung
            
        Returns:
            bool: True nếu thành công
        """
        key = key.lower().strip()
        
        # Sử dụng TTL mặc định nếu không chỉ định
        if ttl is None:
            ttl = self.default_ttl
        
        # Tạo mục cache mới
        self.cache_data[key] = CacheEntry(
            data=value,
            ttl=ttl,
            metadata=metadata
        )
        
        self.modified = True
        
        # Giới hạn kích thước cache nếu cần
        self._limit_cache_size()
        
        # Tự động lưu nếu đã lâu không lưu
        self._auto_save()
        
        return True
    
    def delete(self, key: str) -> bool:
        """
        Xóa mục khỏi cache
        
        Args:
            key: Khóa cache
            
        Returns:
            bool: True nếu xóa thành công, False nếu không tìm thấy
        """
        key = key.lower().strip()
        
        if key in self.cache_data:
            del self.cache_data[key]
            self.modified = True
            return True
        
        return False
    
    def clear(self) -> bool:
        """
        Xóa toàn bộ cache
        
        Returns:
            bool: True nếu thành công
        """
        self.cache_data = {}
        self.modified = True
        self.save()
        return True
    
    def _limit_cache_size(self):
        """Giới hạn kích thước cache theo chiến lược thông minh"""
        if len(self.cache_data) <= self.max_items:
            return
            
        # Số mục cần xóa
        items_to_remove = len(self.cache_data) - self.max_items
        
        # Xếp hạng các mục theo một số tiêu chí:
        # 1. Mục đã hết hạn
        # 2. Mục ít được truy cập
        # 3. Mục được truy cập lâu nhất
        
        # Đầu tiên, xóa các mục đã hết hạn
        expired_keys = [k for k, v in self.cache_data.items() if v.is_expired()]
        for key in expired_keys:
            del self.cache_data[key]
        
        # Nếu vẫn cần xóa thêm
        if len(self.cache_data) > self.max_items:
            items_to_remove = len(self.cache_data) - self.max_items
            
            # Tính điểm cho từng mục dựa trên số lần truy cập và thời gian truy cập cuối
            current_time = time.time()
            item_scores = {}
            
            for key, entry in self.cache_data.items():
                # Công thức điểm: số lần truy cập * 10 + (1000 - thời gian kể từ lần truy cập cuối)
                time_factor = min(1000, int(current_time - entry.last_access))
                item_scores[key] = (entry.access_count * 10) + (1000 - time_factor)
            
            # Sắp xếp các mục theo điểm (thấp đến cao)
            sorted_items = sorted(item_scores.items(), key=lambda x: x[1])
            
            # Xóa các mục có điểm thấp nhất
            for key, _ in sorted_items[:items_to_remove]:
                del self.cache_data[key]
    
    def _auto_save(self):
        """Tự động lưu cache nếu đã lâu không lưu"""
        if self.modified and (time.time() - self.last_saved) > self.auto_save_interval:
            self.save()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Lấy thống kê về cache
        
        Returns:
            Dict: Thông tin thống kê
        """
        current_time = time.time()
        
        # Đếm các mục đã hết hạn
        expired_count = sum(1 for entry in self.cache_data.values() if entry.is_expired())
        
        # Tính thời gian trung bình còn lại
        ttl_items = [entry for entry in self.cache_data.values() if entry.ttl is not None]
        avg_remaining_ttl = 0
        
        if ttl_items:
            remaining_ttls = [max(0, entry.ttl - (current_time - entry.timestamp)) for entry in ttl_items]
            avg_remaining_ttl = sum(remaining_ttls) / len(remaining_ttls)
        
        # Thống kê truy cập
        access_counts = [entry.access_count for entry in self.cache_data.values()]
        avg_access_count = sum(access_counts) / len(access_counts) if access_counts else 0
        
        return {
            'total_items': len(self.cache_data),
            'expired_items': expired_count,
            'active_items': len(self.cache_data) - expired_count,
            'avg_access_count': avg_access_count,
            'avg_remaining_ttl': avg_remaining_ttl,
            'last_saved': datetime.fromtimestamp(self.last_saved).strftime('%Y-%m-%d %H:%M:%S') if self.last_saved else None,
            'file_size_kb': round(os.path.getsize(self.file_path) / 1024, 2) if self.file_path.exists() else 0
        }

class CacheManager:
    """Quản lý tập trung các cache khác nhau"""
    
    def __init__(self):
        """Khởi tạo quản lý cache"""
        self.caches = {}
        self._initialize_caches()
    
    def _initialize_caches(self):
        """Khởi tạo các cache từ cấu hình"""
        cache_configs = {
            'image_cache': {
                'file': config.IMAGE_CACHE_FILE,
                'ttl': config.CACHE_TTL * 2,  # Hình ảnh lưu lâu hơn
                'max_items': config.CACHE_MAX_ITEMS
            },
            'video_cache': {
                'file': config.VIDEO_CACHE_FILE,
                'ttl': config.CACHE_TTL * 2,  # Video lưu lâu hơn
                'max_items': config.CACHE_MAX_ITEMS
            },
            'keyword_cache': {
                'file': config.KEYWORD_CACHE_FILE,
                'ttl': config.CACHE_TTL,
                'max_items': config.CACHE_MAX_ITEMS * 2  # Từ khóa lưu nhiều hơn
            }
        }
        
        # Khởi tạo cache
        for cache_name, cache_config in cache_configs.items():
            self.caches[cache_name] = Cache(
                file_path=cache_config['file'],
                default_ttl=cache_config['ttl'],
                max_items=cache_config['max_items']
            )
    
    def get_cache(self, cache_name: str) -> Cache:
        """
        Lấy cache theo tên
        
        Args:
            cache_name: Tên cache
            
        Returns:
            Cache: Đối tượng cache
        """
        if cache_name not in self.caches:
            raise ValueError(f"Cache '{cache_name}' không tồn tại")
            
        return self.caches[cache_name]
    
    def save_all(self) -> bool:
        """
        Lưu tất cả cache
        
        Returns:
            bool: True nếu tất cả đều lưu thành công
        """
        success = True
        
        for cache_name, cache in self.caches.items():
            if not cache.save():
                logger.error(f"Không thể lưu cache {cache_name}")
                success = False
        
        return success
    
    def cleanup_all(self, force_save: bool = True) -> Dict[str, int]:
        """
        Dọn dẹp tất cả cache bằng cách xóa các mục hết hạn
        
        Args:
            force_save: Ép buộc lưu sau khi dọn dẹp
            
        Returns:
            Dict: Thống kê số mục đã xóa
        """
        cleanup_stats = {}
        
        for cache_name, cache in self.caches.items():
            # Đếm số mục trước khi dọn dẹp
            before_count = len(cache.cache_data)
            
            # Xóa các mục hết hạn
            expired_keys = [k for k, v in cache.cache_data.items() if v.is_expired()]
            for key in expired_keys:
                cache.delete(key)
            
            # Đếm số mục sau khi dọn dẹp
            after_count = len(cache.cache_data)
            removed_count = before_count - after_count
            
            # Lưu cache nếu có thay đổi
            if removed_count > 0 or force_save:
                cache.save()
            
            cleanup_stats[cache_name] = removed_count
        
        return cleanup_stats
    
    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Lấy thống kê tất cả cache
        
        Returns:
            Dict: Thông tin thống kê
        """
        stats = {}
        
        for cache_name, cache in self.caches.items():
            stats[cache_name] = cache.get_stats()
        
        return stats

# Tạo instance toàn cục
cache_manager = CacheManager()

# Hàm trợ giúp
def cleanup_all_caches(max_age_days=None, max_items=None) -> Dict[str, Dict[str, Any]]:
    """
    Dọn dẹp tất cả cache
    
    Args:
        max_age_days: Số ngày tối đa để giữ cache, None = sử dụng cấu hình mặc định
        max_items: Số lượng mục tối đa, None = sử dụng cấu hình mặc định
        
    Returns:
        Dict: Thống kê sau khi dọn dẹp
    """
    logger.info("Bắt đầu dọn dẹp tất cả cache...")
    
    # Cập nhật cấu hình tạm thời nếu có chỉ định
    if max_age_days is not None:
        for cache in cache_manager.caches.values():
            cache.default_ttl = max_age_days * 24 * 60 * 60
    
    if max_items is not None:
        for cache in cache_manager.caches.values():
            cache.max_items = max_items
    
    # Thực hiện dọn dẹp
    cleanup_stats = cache_manager.cleanup_all()
    
    # Hiển thị thống kê
    for cache_name, removed_count in cleanup_stats.items():
        if removed_count > 0:
            logger.info(f"Đã xóa {removed_count} mục từ {cache_name}")
        else:
            logger.info(f"Không có mục nào cần xóa từ {cache_name}")
    
    # Lấy thống kê cuối cùng
    return cache_manager.get_stats()