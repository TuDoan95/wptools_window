import re
import time
import random
import logging
import requests
import threading
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from config import config
from utils.logger import logger
from utils.rate_limiter import RateLimiter
from utils.cache_manager import cache_manager

# Khởi tạo cache và rate limiter
image_cache = cache_manager.get_cache('image_cache')
image_rate_limiter = RateLimiter(config.IMAGE_RATE_LIMIT)
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36 Edg/94.0.992.47",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
]

selenium_semaphore = threading.Semaphore(2)  # Giới hạn mặc định là 2 phiên song song

class ImageFinder:
    """Tìm kiếm hình ảnh chất lượng cao cho bài viết WordPress"""
    
    def __init__(self):
        """Khởi tạo công cụ tìm kiếm hình ảnh"""
        global selenium_semaphore
        selenium_semaphore = threading.Semaphore(config.SELENIUM_MAX_CONCURRENT)
        self.driver = None
        self.driver_service = None
        self.driver_lock = threading.RLock()  # Thêm lock này
        self.search_count = 0
        self.max_searches_before_restart = 10
        
        # Hình ảnh dự phòng khi không tìm được
        self.fallback_images = {
            'general': [
                'https://images.pexels.com/photos/3861969/pexels-photo-3861969.jpeg',
                'https://images.pexels.com/photos/7688336/pexels-photo-7688336.jpeg',
                'https://images.pexels.com/photos/590041/pexels-photo-590041.jpeg',
                'https://images.pexels.com/photos/3293148/pexels-photo-3293148.jpeg',
                'https://images.pexels.com/photos/3048527/pexels-photo-3048527.jpeg'
            ],
            'technology': [
                'https://images.pexels.com/photos/1714208/pexels-photo-1714208.jpeg',
                'https://images.pexels.com/photos/2582937/pexels-photo-2582937.jpeg',
                'https://images.pexels.com/photos/3861969/pexels-photo-3861969.jpeg',
                'https://images.pexels.com/photos/1181244/pexels-photo-1181244.jpeg',
                'https://images.pexels.com/photos/3861943/pexels-photo-3861943.jpeg'
            ],
            'health': [
                'https://images.pexels.com/photos/3771836/pexels-photo-3771836.jpeg',
                'https://images.pexels.com/photos/4498362/pexels-photo-4498362.jpeg',
                'https://images.pexels.com/photos/3759657/pexels-photo-3759657.jpeg',
                'https://images.pexels.com/photos/4047148/pexels-photo-4047148.jpeg',
                'https://images.pexels.com/photos/3766210/pexels-photo-3766210.jpeg'
            ],
            'business': [
                'https://images.pexels.com/photos/3184325/pexels-photo-3184325.jpeg',
                'https://images.pexels.com/photos/3182826/pexels-photo-3182826.jpeg',
                'https://images.pexels.com/photos/3184339/pexels-photo-3184339.jpeg',
                'https://images.pexels.com/photos/327540/pexels-photo-327540.jpeg',
                'https://images.pexels.com/photos/3184338/pexels-photo-3184338.jpeg'
            ],
            'travel': [
                'https://images.pexels.com/photos/2437291/pexels-photo-2437291.jpeg',
                'https://images.pexels.com/photos/2258536/pexels-photo-2258536.jpeg',
                'https://images.pexels.com/photos/2245436/pexels-photo-2245436.jpeg',
                'https://images.pexels.com/photos/2507025/pexels-photo-2507025.jpeg',
                'https://images.pexels.com/photos/1659438/pexels-photo-1659438.jpeg'
            ]
        }
        
        logger.info("ImageFinder đã được khởi tạo")
    
    def _initialize_driver(self) -> None:
        """Khởi tạo Selenium WebDriver với xử lý đa luồng tốt hơn"""
        # Đóng driver cũ nếu có
        try:
            self._close_driver()
            
            user_agent = random.choice(user_agents)
            
                # Cấu hình Chrome options với tối ưu cho hiệu suất
            options = Options()
            options.add_argument(f"user-agent={user_agent}")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])               
            options.add_experimental_option("useAutomationExtension", False)    
            # Tối ưu hóa bộ nhớ và CPU
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-software-rasterizer")
            options.add_argument("--no-sandbox")
                
            # Chạy ẩn nếu cấu hình yêu cầu
            if config.SELENIUM_HEADLESS:
                options.add_argument("--headless=new")
                
            # Bật chế độ ẩn danh
            options.add_argument("--incognito")
                
            # Tắt tải hình ảnh để tăng tốc
            prefs = {"profile.managed_default_content_settings.images": 2}
            options.add_experimental_option("prefs", prefs)
                
            # Khởi tạo WebDriver với timeout ngắn hơn
            self.driver_service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=self.driver_service, options=options)
                
            # Thiết lập timeout ngắn để tăng tốc
            self.driver.set_page_load_timeout(10)  # Giảm xuống 15 giây
            self.driver.implicitly_wait(3)  # Giảm xuống 5 giây
                
            logger.info("Đã khởi tạo Chrome WebDriver thành công")
        except Exception as e:
            logger.error(f"Không thể khởi tạo WebDriver: {e}")
            # Thêm thời gian chờ trước khi luồng khác thử
            self.driver = None
            self.driver_service = None
            time.sleep(2)
            raise
    
    def _close_driver(self) -> None:
        """Đóng và giải phóng WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Đã đóng WebDriver")
            except Exception as e:
                logger.error(f"Lỗi khi đóng WebDriver: {e}")
            finally:
                self.driver = None
                self.driver_service = None
    
    def _sanitize_keyword(self, keyword: str) -> str:
        """Xử lý từ khóa cho an toàn khi tìm kiếm"""
        # Loại bỏ ký tự đặc biệt
        keyword = re.sub(r'[\\/:*?"<>|\'"]', ' ', keyword)
        
        # Chuẩn hóa khoảng trắng
        keyword = re.sub(r'\s+', ' ', keyword).strip()
        
        return keyword
    
    def _extract_images_with_selenium(self) -> List[str]:
        """Trích xuất URL hình ảnh trực tiếp bằng Selenium"""
        image_urls = []
        try:
            # Tìm các phần tử img với các thuộc tính khác nhau
            for selector in ["img[src*='https']", "img[data-src*='https']", "img.rg_i", "img.Q4LuWd"]:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for img in elements:
                    # Lấy các thuộc tính có thể chứa URL
                    for attr in ["src", "data-src", "data-iurl", "data-source"]:
                        url = img.get_attribute(attr)
                        if url and url.startswith("https://"):
                            image_urls.append(url)
            
            # Loại bỏ trùng lặp
            return list(set(image_urls))
        except Exception as e:
            logger.error(f"Lỗi khi trích xuất hình ảnh với Selenium: {e}")
            return []
        
    def _extract_image_urls(self, html_content: str) -> List[str]:
        """Trích xuất URL hình ảnh chất lượng cao từ HTML Google"""
        # Mẫu regex cho hình ảnh chất lượng cao
        high_quality_patterns = [
            # JSON data pattern - thường chứa hình ảnh gốc
            r'ou":"(https://[^"]+)"',
            
            # URLs trong thẻ có thuộc tính kích thước lớn
            r'<img[^>]+src="(https://[^"]+)"[^>]+data-sz="[l|xl]"',
            
            # Pattern cơ bản cho các URL hình ảnh
            r'<img[^>]+src="(https://[^"]+\.(jpg|jpeg|png))"',
            r'<img[^>]+data-src="(https://[^"]+\.(jpg|jpeg|png))"'
        ]
        
        # Trích xuất tất cả URLs
        all_urls = []
        for pattern in high_quality_patterns:
            urls = re.findall(pattern, html_content)
            if isinstance(urls[0], tuple) if urls else False:
                urls = [url[0] for url in urls]  # Lấy phần tử đầu tiên nếu là tuple
            all_urls.extend(urls)
        
        # Lọc URLs
        filtered_urls = []
        for url in all_urls:
            url_lower = url.lower()
            
            # Loại bỏ thumbnails, icons và các URL không liên quan
            if any(exclude in url_lower for exclude in ['favicon', 'icon', 'thumb', 'small']):
                continue
                
            # Ưu tiên URL có dấu hiệu của hình ảnh chất lượng cao
            priority = 0
            if any(term in url_lower for term in ['large', 'original', 'full', 'high', 'quality']):
                priority = 2
            elif any(ext in url_lower for ext in ['.jpg', '.jpeg', '.png']):
                priority = 1
                
            filtered_urls.append((url, priority))
        
        # Sắp xếp theo ưu tiên và loại bỏ trùng lặp
        sorted_urls = sorted(filtered_urls, key=lambda x: x[1], reverse=True)
        unique_urls = []
        seen_urls = set()
        
        for url, _ in sorted_urls:
            if url not in seen_urls:
                unique_urls.append(url)
                seen_urls.add(url)
        
        return unique_urls
    
    def _validate_image_url(self, image_url: str) -> bool:
        """Xác thực đơn giản URL hình ảnh"""
        # Loại bỏ favicon và URL quá ngắn
        if 'favicon' in image_url.lower() or len(image_url) < 40:
            return False
        
        # Nếu URL có dạng Google thumbnail, chúng thường không có kích thước đủ lớn
        if "encrypted-tbn" in image_url and "google" in image_url:
            # Nhưng chúng ta vẫn chấp nhận nếu không có hình ảnh khác
            return True  # Chấp nhận thumbnail khi cần
        
        # Chấp nhận hầu hết các URL khác mà không cần kiểm tra kích thước
        return True
    
    def _get_category_from_keyword(self, keyword: str) -> str:
        """Xác định danh mục từ từ khóa"""
        keyword_lower = keyword.lower()
        
        # Kiểm tra từng danh mục
        if any(word in keyword_lower for word in ["technology", "tech", "digital", "gadget", "software", "computer"]):
            return "technology"
        elif any(word in keyword_lower for word in ["health", "fitness", "exercise", "diet", "wellness", "medical"]):
            return "health"
        elif any(word in keyword_lower for word in ["business", "finance", "money", "investment", "entrepreneur"]):
            return "business"
        elif any(word in keyword_lower for word in ["travel", "tourism", "vacation", "trip", "destination", "hotel"]):
            return "travel"
        
        # Mặc định là general
        return "general"
    
    def search_google_images(self, keyword: str, max_images: int = 5) -> List[str]:
        """
        Tìm kiếm hình ảnh từ Google Images
        
        Args:
            keyword: Từ khóa tìm kiếm
            max_images: Số lượng tối đa hình ảnh cần lấy
            
        Returns:
            List[str]: Danh sách URL hình ảnh
        """
        # Đảm bảo giới hạn tốc độ
        image_rate_limiter.wait_if_needed()
        
        # Xử lý từ khóa
        keyword = self._sanitize_keyword(keyword)
        search_query = quote_plus(keyword)
        
        logger.info(f"Tìm kiếm hình ảnh cho từ khóa: '{keyword}'")
        
        with selenium_semaphore:
            try:
                with self.driver_lock:
                    # Khởi động lại WebDriver định kỳ để tránh rò rỉ bộ nhớ
                    self.search_count += 1
                    if self.search_count >= self.max_searches_before_restart:
                        logger.info("Khởi động lại WebDriver theo định kỳ...")
                        self._close_driver()
                        self.search_count = 0
                    # Khởi tạo Selenium
                    if self.driver is None:
                        try:
                            self._initialize_driver()
                        except Exception as e:
                            logger.error(f"Không thể khởi tạo driver: {e}")
                            return []
        
        
                # Tìm kiếm hình ảnh cơ bản không cần các tham số phức tạp
                search_url = f"https://www.google.com/search?q={search_query}&tbm=isch&hl=en&gl=US"
                
                # Truy cập URL
                logger.info(f"Đang truy cập URL: {search_url}")
                self.driver.get(search_url)
                time.sleep(1.5)  # Đợt ngắn
                
                # Chỉ cuộn 1-2 lần để lấy kết quả nhanh
                self.driver.execute_script("window.scrollTo(0, 800);")  # Cuộn xuống một chút
                time.sleep(0.5)
                
                # Lấy HTML và trích xuất URL
                page_source = self.driver.page_source
                image_urls = self._extract_image_urls(page_source)
                
                # Nếu không đủ hình ảnh, thử phương pháp trực tiếp
                if len(image_urls) < max_images:
                    selenium_urls = self._extract_images_with_selenium()
                    # Kết hợp cả hai phương pháp và loại bỏ trùng lặp
                    combined_urls = list(set(image_urls + selenium_urls))
                    image_urls = combined_urls
                
                # Giới hạn số lượng
                if image_urls and len(image_urls) > max_images:
                    image_urls = image_urls[:max_images]
                
                logger.info(f"Tìm thấy {len(image_urls)} hình ảnh cho từ khóa: '{keyword}'")
                return image_urls
                
            except Exception as e:
                logger.error(f"Lỗi khi tìm kiếm hình ảnh: {e}")
                self._close_driver()
                return []
        
    def _generate_quality_image_keywords(self, base_keyword: str) -> List[str]:
        """Tạo các biến thể từ khóa để tìm hình ảnh chất lượng cao"""
        quality_keywords = [
            f"{base_keyword} high resolution",
            f"{base_keyword} hd",
            f"{base_keyword} 4K",
            f"{base_keyword} wallpaper",
            f"{base_keyword} professional photo",
            f"{base_keyword} stock image"
        ]
        
        # Trả về từ khóa gốc và các biến thể
        return [base_keyword] + quality_keywords
        
    def get_fallback_images(self, keyword: str, count: int = 5) -> List[str]:
        """
        Lấy hình ảnh dự phòng cho từ khóa
        
        Args:
            keyword: Từ khóa
            count: Số lượng hình ảnh cần lấy
            
        Returns:
            List[str]: Danh sách URL hình ảnh
        """
        # Xác định danh mục
        category = self._get_category_from_keyword(keyword)
        
        logger.info(f"Sử dụng {count} hình ảnh dự phòng cho danh mục: {category}")
        
        # Lấy hình ảnh từ danh mục
        image_pool = self.fallback_images.get(category, self.fallback_images['general'])
        
        # Giới hạn số lượng
        count = min(count, len(image_pool))
        
        # Lấy ngẫu nhiên từ pool
        return random.sample(image_pool, count)
    
    def get_images(self, keyword: str, max_images: int = None) -> List[str]:
        """Lấy hình ảnh với phương pháp đơn giản và nhanh"""
        if max_images is None:
            max_images = config.IMAGE_MAX_COUNT
        
        # Chuẩn hóa từ khóa
        keyword_normalized = keyword.lower().strip()
        
        # 1. Kiểm tra cache
        cached_images = image_cache.get(keyword_normalized)
        if cached_images:
            logger.info(f"Sử dụng hình ảnh từ cache cho từ khóa: '{keyword}'")
            return cached_images[:max_images]
        
        # 2. Tìm kiếm hình ảnh
        image_urls = self.search_google_images(keyword, max_images + 2)  # Lấy thêm 2 hình phòng trường hợp
        
        # 3. Lọc nhanh các URL
        valid_images = []
        for url in image_urls:
            if self._validate_image_url(url):
                valid_images.append(url)
                if len(valid_images) >= max_images:
                    break
        
        # 4. Nếu tìm được hình ảnh
        if valid_images:
            logger.info(f"Tìm thấy {len(valid_images)} hình ảnh cho từ khóa: '{keyword}'")
            image_cache.set(keyword_normalized, valid_images)
            return valid_images
        
        # 5. Thử với từ khóa đơn giản hóa nếu từ khóa gốc quá dài
        words = keyword.split()
        if len(words) > 2:
            simplified_keyword = ' '.join(words[:2])
            logger.info(f"Thử với từ khóa đơn giản hóa: '{simplified_keyword}'")
            return self.get_images(simplified_keyword, max_images)
        
        # 6. Sử dụng hình ảnh dự phòng
        logger.warning(f"Không tìm thấy hình ảnh cho từ khóa '{keyword}'. Sử dụng hình ảnh dự phòng")
        return self.get_fallback_images(keyword, max_images)
    
    def cleanup(self):
        """Giải phóng tài nguyên"""
        self._close_driver()

# Tạo instance toàn cục
image_finder = ImageFinder()