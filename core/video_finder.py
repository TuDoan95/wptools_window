import re
import time
import random
import requests
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus, urlparse

from config import config
from utils.logger import logger
from utils.rate_limiter import RateLimiter
from utils.cache_manager import cache_manager

# Khởi tạo cache và rate limiter
video_cache = cache_manager.get_cache('video_cache')
video_rate_limiter = RateLimiter(config.VIDEO_RATE_LIMIT)

class VideoFinder:
    """Tìm kiếm video YouTube cho bài viết WordPress"""
    
    def __init__(self):
        """Khởi tạo công cụ tìm kiếm video"""
        # User-Agent để giả lập trình duyệt
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        
        logger.info("VideoFinder đã được khởi tạo")
    
    def _get_random_user_agent(self):
        """Lấy ngẫu nhiên một User-Agent"""
        return random.choice(self.user_agents)
    
    def _sanitize_keyword(self, keyword: str) -> str:
        """Xử lý từ khóa cho an toàn khi tìm kiếm"""
        # Loại bỏ ký tự đặc biệt
        keyword = re.sub(r'[\\/:*?"<>|\'"]', ' ', keyword)
        
        # Chuẩn hóa khoảng trắng
        keyword = re.sub(r'\s+', ' ', keyword).strip()
        
        return keyword
    
    def _convert_to_embed_url(self, youtube_url: str) -> Optional[str]:
        """Chuyển URL YouTube thành URL embed"""
        if not youtube_url:
            return None
            
        # Kiểm tra định dạng URL
        if "youtube.com/watch?v=" in youtube_url:
            video_id = youtube_url.split("v=")[1].split("&")[0]
            return f"https://www.youtube.com/embed/{video_id}"
        elif "youtu.be/" in youtube_url:
            video_id = youtube_url.split("youtu.be/")[1].split("?")[0]
            return f"https://www.youtube.com/embed/{video_id}"
        elif "youtube.com/embed/" in youtube_url:
            return youtube_url  # Đã là URL embed
        
        return None
    
    def _extract_video_id(self, video_url: str) -> Optional[str]:
        """Trích xuất ID video từ URL YouTube"""
        if not video_url:
            return None
            
        try:
            # Regex tìm ID video
            pattern = r'(?:v=|embed\/|youtu\.be\/)([^&\?\/]+)'
            match = re.search(pattern, video_url)
            if match:
                return match.group(1)
        except Exception as e:
            logger.error(f"Lỗi khi trích xuất video ID: {e}")
        
        return None
    
    def search_youtube(self, keyword: str, max_results: int = 3) -> List[str]:
        """
        Tìm kiếm video YouTube bằng cách truy vấn trực tiếp
        
        Args:
            keyword: Từ khóa tìm kiếm
            max_results: Số lượng kết quả tối đa
            
        Returns:
            List[str]: Danh sách URL video
        """
        # Đảm bảo giới hạn tốc độ
        video_rate_limiter.wait_if_needed()
        
        # Xử lý từ khóa
        keyword = self._sanitize_keyword(keyword)
        search_query = quote_plus(keyword)
        
        logger.info(f"Tìm kiếm video cho từ khóa: '{keyword}'")
        
        try:
            # Chuẩn bị URL và headers
            search_url = f"https://www.youtube.com/results?search_query={search_query}"
            headers = {
                'User-Agent': self._get_random_user_agent(),
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
            }
            
            # Gửi request
            response = requests.get(search_url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Lỗi khi truy vấn YouTube: {response.status_code}")
                return []
                
            # Tìm kiếm ID video trong kết quả
            # YouTube lưu dữ liệu trong JS variable với format "videoId":"ID_HERE"
            video_ids = re.findall(r'"videoId":"([^"]+)"', response.text)
            
            # Loại bỏ trùng lặp
            unique_video_ids = []
            for video_id in video_ids:
                if video_id not in unique_video_ids:
                    unique_video_ids.append(video_id)
                    if len(unique_video_ids) >= max_results:
                        break
            
            # Tạo URL đầy đủ
            video_urls = [f"https://www.youtube.com/watch?v={video_id}" for video_id in unique_video_ids]
            
            logger.info(f"Đã tìm thấy {len(video_urls)} video cho từ khóa: '{keyword}'")
            return video_urls
            
        except Exception as e:
            logger.error(f"Lỗi khi tìm kiếm YouTube: {e}")
            return []
    
    def search_with_variants(self, keyword: str, max_results: int = 3) -> List[str]:
        """
        Tìm kiếm video với các biến thể từ khóa
        
        Args:
            keyword: Từ khóa gốc
            max_results: Số lượng kết quả tối đa
            
        Returns:
            List[str]: Danh sách URL video
        """
        # Thử tìm với từ khóa gốc
        video_urls = self.search_youtube(keyword, max_results)
        
        # Nếu không tìm thấy, thử các biến thể
        if not video_urls:
            # Tạo các biến thể
            variants = [
                f"{keyword} tutorial",
                f"{keyword} guide",
                f"{keyword} explained",
                f"{keyword} review"
            ]
            
            for variant in variants:
                logger.info(f"Thử tìm với biến thể: '{variant}'")
                video_urls = self.search_youtube(variant, max_results)
                if video_urls:
                    break
        
        return video_urls
    
    def get_video(self, keyword: str) -> Optional[str]:
        """
        Lấy video cho từ khóa với cache thông minh
        
        Args:
            keyword: Từ khóa tìm kiếm
            
        Returns:
            str: URL embed video hoặc None nếu không tìm thấy
        """
        # Chuẩn hóa từ khóa
        keyword_normalized = keyword.lower().strip()
        
        # 1. Kiểm tra cache
        cached_data = video_cache.get(keyword_normalized)
        if cached_data:
            logger.info(f"Sử dụng video từ cache cho từ khóa: '{keyword}'")
            # Chuyển sang URL embed nếu cần
            video_id = cached_data.get('video_id')
            if video_id:
                return f"https://www.youtube.com/embed/{video_id}"
            return None
        
        # 2. Tìm kiếm video mới
        video_urls = self.search_with_variants(keyword)
        
        if not video_urls:
            logger.warning(f"Không tìm thấy video nào cho từ khóa: '{keyword}'")
            # Lưu vào cache để tránh tìm kiếm lại (7 ngày)
            video_cache.set(keyword_normalized, {'video_id': None}, ttl=7*24*60*60)
            return None
        
        # 3. Chọn video phù hợp
        # Heuristic: Có thể chọn video thứ 2 hoặc ngẫu nhiên giữa top 3 để tăng tính đa dạng
        if random.random() < 0.7:  # 70% khả năng chọn video đầu tiên
            selected_video = video_urls[0]
        else:
            # 30% khả năng chọn ngẫu nhiên từ tất cả các video tìm được
            selected_video = random.choice(video_urls)
        
        # 4. Trích xuất ID và tạo URL embed
        video_id = self._extract_video_id(selected_video)
        if not video_id:
            logger.error(f"Không thể trích xuất video ID từ URL: {selected_video}")
            return None
        
        # 5. Lưu vào cache (30 ngày)
        video_cache.set(keyword_normalized, {'video_id': video_id}, ttl=30*24*60*60)
        
        # 6. Trả về URL embed
        embed_url = f"https://www.youtube.com/embed/{video_id}"
        logger.info(f"Đã tìm thấy video (ID: {video_id}) cho từ khóa: '{keyword}'")
        return embed_url

# Tạo instance toàn cục
video_finder = VideoFinder()