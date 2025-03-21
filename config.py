import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Tải biến môi trường từ file .env
load_dotenv()

class Config:
    """Quản lý cấu hình tập trung cho WordPress Auto Content Generator"""
    
    def __init__(self):
        # Đường dẫn cơ sở của dự án
        self.BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
        
        # Tạo các thư mục cần thiết
        self.DATA_DIR = self.BASE_DIR / 'data'
        os.makedirs(self.DATA_DIR, exist_ok=True)
        
        self.CACHE_DIR = self.DATA_DIR / 'cache'
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        
        self.KEYWORDS_DIR = self.DATA_DIR / 'keywords'
        os.makedirs(self.KEYWORDS_DIR, exist_ok=True)
        
        self.LOGS_DIR = self.DATA_DIR / 'logs'
        os.makedirs(self.LOGS_DIR, exist_ok=True)
        
        self.SECURE_DIR = self.BASE_DIR / '.secure'
        os.makedirs(self.SECURE_DIR, exist_ok=True)
        
        # Tải tất cả cấu hình
        self._load_config()
    
    def _load_config(self):
        """Tải tất cả cấu hình từ các nguồn khác nhau"""
        # Cấu hình WordPress
        self._load_wordpress_config()
        
        # Cấu hình API Gemini
        self._load_gemini_config()
        
        # Cấu hình tìm kiếm media
        self._load_media_config()
        
        # Cấu hình cache
        self._load_cache_config()
        
        # Cấu hình logging
        self._load_logging_config()

        # Cấu hình song song
        self._load_parallel_config()
    
    def _load_wordpress_config(self):
        """Tải cấu hình WordPress"""
        # WordPress API URL và xác thực
        self.WP_URL = os.getenv('WP_URL', '').rstrip('/')
        self.WP_USERNAME = os.getenv('WP_USERNAME', '')
        self.WP_APP_PASSWORD = os.getenv('WP_APP_PASSWORD', '')
        
        # Lưu trữ thông tin bài viết đã đăng
        self.WP_POSTS_FILE = self.DATA_DIR / 'published_posts.json'
        
        # Cấu hình SEO
        self.WP_USE_YOAST_SEO = os.getenv('WP_USE_YOAST_SEO', 'true').lower() == 'true'
        self.WP_DEFAULT_CATEGORY = os.getenv('WP_DEFAULT_CATEGORY', 'General')
        
        # Giới hạn API call
        self.WP_API_RATE_LIMIT = int(os.getenv('WP_API_RATE_LIMIT', 30))  # calls/minute
    
    def _load_gemini_config(self):
        """Tải cấu hình Gemini AI API"""
        # API Keys
        self.GEMINI_API_KEYS = []
        
        # Đọc từ file .env
        for i in range(1, 11):  # Hỗ trợ tối đa 10 API keys
            key = os.getenv(f'GEMINI_API_KEY{i}', '')
            if key:
                self.GEMINI_API_KEYS.append(key)
        
        # Nếu không có key trong .env, kiểm tra file bảo mật
        if not self.GEMINI_API_KEYS:
            api_keys_file = self.SECURE_DIR / 'gemini_api_keys.json'
            if os.path.exists(api_keys_file):
                try:
                    with open(api_keys_file, 'r') as f:
                        keys_data = json.load(f)
                        if isinstance(keys_data, list):
                            self.GEMINI_API_KEYS = keys_data
                        elif isinstance(keys_data, dict) and 'api_keys' in keys_data:
                            self.GEMINI_API_KEYS = keys_data['api_keys']
                except Exception as e:
                    print(f"Lỗi khi đọc file API keys: {e}")
        
        # Số lần thử tối đa cho mỗi key trước khi chuyển sang key khác
        self.GEMINI_MAX_KEY_ERRORS = int(os.getenv('GEMINI_MAX_KEY_ERRORS', 5))
        
        # Thời gian nghỉ cho key bị lỗi (giây)
        self.GEMINI_KEY_ERROR_COOLDOWN = int(os.getenv('GEMINI_KEY_ERROR_COOLDOWN', 300))
        
        # Cấu hình model
        self.GEMINI_MODEL_NAME = os.getenv('GEMINI_MODEL_NAME', 'gemini-pro')
        
        # Rate limiter
        self.GEMINI_RATE_LIMIT = int(os.getenv('GEMINI_RATE_LIMIT', 5))  # calls/minute
    
    def _load_media_config(self):
        """Tải cấu hình tìm kiếm phương tiện"""
        # Cấu hình ảnh
        self.IMAGE_MAX_COUNT = int(os.getenv('IMAGE_MAX_COUNT', 5))
        self.IMAGE_CACHE_FILE = self.CACHE_DIR / 'image_cache.json'
        self.IMAGE_RATE_LIMIT = int(os.getenv('IMAGE_RATE_LIMIT', 2))  # calls/minute
        
        # Cấu hình Selenium cho tìm kiếm hình ảnh
        self.SELENIUM_HEADLESS = os.getenv('SELENIUM_HEADLESS', 'true').lower() == 'true'
        self.SELENIUM_TIMEOUT = int(os.getenv('SELENIUM_TIMEOUT', 10))
        self.SELENIUM_MAX_SCROLLS = int(os.getenv('SELENIUM_MAX_SCROLLS', 3))
        
        # Cấu hình video
        self.VIDEO_MAX_COUNT = int(os.getenv('VIDEO_MAX_COUNT', 1))
        self.VIDEO_CACHE_FILE = self.CACHE_DIR / 'video_cache.json'
        self.VIDEO_RATE_LIMIT = int(os.getenv('VIDEO_RATE_LIMIT', 2))  # calls/minute
    
    def _load_cache_config(self):
        """Tải cấu hình cache"""
        self.CACHE_TTL = int(os.getenv('CACHE_TTL', 604800))  # 7 ngày mặc định
        self.CACHE_MAX_ITEMS = int(os.getenv('CACHE_MAX_ITEMS', 1000))
        self.KEYWORD_CACHE_FILE = self.CACHE_DIR / 'keyword_cache.json'
    
    def _load_logging_config(self):
        """Tải cấu hình logging"""
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        self.LOG_FILE = self.LOGS_DIR / 'wp_auto_content.log'
        self.LOG_RETENTION_DAYS = int(os.getenv('LOG_RETENTION_DAYS', 7))

    def _load_parallel_config(self):
        """Tải cấu hình xử lý song song"""
        self.ENABLE_PARALLEL = os.getenv('ENABLE_PARALLEL', 'true').lower() == 'true'
        self.PARALLEL_WORKERS = int(os.getenv('PARALLEL_WORKERS', 3))
        # Số lượng driver Selenium tối đa
        self.SELENIUM_MAX_CONCURRENT = int(os.getenv('SELENIUM_MAX_CONCURRENT', 2))

# Tạo instance toàn cục
config = Config()