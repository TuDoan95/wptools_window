import os
import json
import requests
import tempfile
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urlparse

from config import config
from utils.logger import logger
from utils.rate_limiter import RateLimiter

class WordPressAPI:
    """Quản lý kết nối và tương tác với WordPress thông qua REST API"""
    
    def __init__(self):
        """Khởi tạo kết nối WordPress"""
        self.wp_url = config.WP_URL.rstrip('/')  # Loại bỏ dấu / ở cuối
        self.username = config.WP_USERNAME
        self.app_password = config.WP_APP_PASSWORD
        self.session = requests.Session()
        self.use_yoast_seo = config.WP_USE_YOAST_SEO
        
        # Thiết lập xác thực cơ bản
        self.session.auth = (self.username, self.app_password)
        
        # Rate limiter
        self.rate_limiter = RateLimiter(config.WP_API_RATE_LIMIT)
        
        # Cache data
        self.categories_cache = {}  # Cache danh mục
        self.tags_cache = {}  # Cache tags
        
        # File theo dõi bài đã đăng
        self.published_posts_file = config.WP_POSTS_FILE
        self.published_posts = self._load_published_posts()
        
        logger.info(f"Khởi tạo WordPress API với URL: {self.wp_url}")
    
    def _load_published_posts(self) -> Dict[str, Any]:
        """Tải danh sách bài đã đăng từ file"""
        if os.path.exists(self.published_posts_file):
            try:
                with open(self.published_posts_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Lỗi khi tải file bài đã đăng: {e}")
        
        # Tạo mới nếu chưa có file
        return {'posts': {}, 'last_updated': datetime.now().isoformat()}
    
    def _save_published_post(self, keyword: str, post_id: int, post_data: Dict[str, Any]) -> None:
        """Lưu thông tin bài đăng vào file theo dõi"""
        if not isinstance(post_data, dict):
            logger.error("Dữ liệu post không hợp lệ")
            return
            
        # Extract title from rendered title if needed
        title = post_data.get('title', {})
        if isinstance(title, dict) and 'rendered' in title:
            title = title['rendered']
        elif not isinstance(title, str):
            title = str(post_data.get('id', 'Unknown'))
        
        # Thêm thông tin bài viết
        self.published_posts['posts'][keyword] = {
            'post_id': post_id,
            'permalink': post_data.get('link', ''),
            'title': title,
            'published_date': post_data.get('date', datetime.now().isoformat()),
            'categories': post_data.get('categories', []),
            'tags': post_data.get('tags', [])
        }
        
        # Cập nhật thời gian
        self.published_posts['last_updated'] = datetime.now().isoformat()
        
        try:
            # Đảm bảo thư mục tồn tại
            os.makedirs(os.path.dirname(self.published_posts_file), exist_ok=True)
            
            # Lưu file
            with open(self.published_posts_file, 'w', encoding='utf-8') as f:
                json.dump(self.published_posts, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Đã lưu thông tin bài '{keyword}' vào file theo dõi")
        except Exception as e:
            logger.error(f"Lỗi khi lưu thông tin bài đăng: {e}")
    
    def check_connection(self) -> bool:
        """
        Kiểm tra kết nối đến WordPress
        
        Returns:
            bool: True nếu kết nối thành công, False nếu thất bại
        """
        endpoint = f"{self.wp_url}/wp-json/wp/v2/users/me"
        
        try:
            # Đảm bảo giới hạn tốc độ
            self.rate_limiter.wait_if_needed()
            
            response = self.session.get(endpoint)
            
            if response.status_code == 200:
                user_data = response.json()
                logger.info(f"Kết nối WordPress thành công với user: {user_data.get('name', 'Unknown')}")
                return True
            else:
                logger.error(f"Lỗi kết nối WordPress: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Lỗi khi kiểm tra kết nối WordPress: {e}")
            return False
    
    def get_categories(self, force_refresh: bool = False) -> Dict[str, int]:
        """
        Lấy danh sách categories từ WordPress
        
        Args:
            force_refresh: Bắt buộc refresh cache nếu True
            
        Returns:
            Dict[str, int]: Dictionary với key là tên category, value là ID
        """
        if self.categories_cache and not force_refresh:
            return self.categories_cache
            
        endpoint = f"{self.wp_url}/wp-json/wp/v2/categories?per_page=100"
        
        try:
            # Đảm bảo giới hạn tốc độ
            self.rate_limiter.wait_if_needed()
            
            response = self.session.get(endpoint)
            
            if response.status_code == 200:
                categories = response.json()
                self.categories_cache = {cat['name'].lower(): cat['id'] for cat in categories}
                logger.info(f"Đã tải {len(self.categories_cache)} categories từ WordPress")
                return self.categories_cache
            else:
                logger.error(f"Lỗi khi lấy categories: {response.status_code} - {response.text}")
                return {}
        except Exception as e:
            logger.error(f"Lỗi khi lấy danh sách categories: {e}")
            return {}
    
    def get_tags(self, force_refresh: bool = False) -> Dict[str, int]:
        """
        Lấy danh sách tags từ WordPress
        
        Args:
            force_refresh: Bắt buộc refresh cache nếu True
            
        Returns:
            Dict[str, int]: Dictionary với key là tên tag, value là ID
        """
        if self.tags_cache and not force_refresh:
            return self.tags_cache
            
        endpoint = f"{self.wp_url}/wp-json/wp/v2/tags?per_page=100"
        
        try:
            # Đảm bảo giới hạn tốc độ
            self.rate_limiter.wait_if_needed()
            
            response = self.session.get(endpoint)
            
            if response.status_code == 200:
                tags = response.json()
                self.tags_cache = {tag['name'].lower(): tag['id'] for tag in tags}
                logger.info(f"Đã tải {len(self.tags_cache)} tags từ WordPress")
                return self.tags_cache
            else:
                logger.error(f"Lỗi khi lấy tags: {response.status_code} - {response.text}")
                return {}
        except Exception as e:
            logger.error(f"Lỗi khi lấy danh sách tags: {e}")
            return {}
    
    def create_category(self, name: str, description: str = '', parent: int = 0) -> Optional[int]:
        """
        Tạo category mới
        
        Args:
            name: Tên category
            description: Mô tả category (tùy chọn)
            parent: ID của category cha (0 = không có cha)
            
        Returns:
            int: ID của category mới tạo hoặc None nếu thất bại
        """
        endpoint = f"{self.wp_url}/wp-json/wp/v2/categories"
        
        data = {
            'name': name,
            'description': description,
            'parent': parent
        }
        
        try:
            # Đảm bảo giới hạn tốc độ
            self.rate_limiter.wait_if_needed()
            
            response = self.session.post(endpoint, json=data)
            
            if response.status_code in (200, 201):
                category = response.json()
                logger.info(f"Đã tạo category mới: {name} (ID: {category['id']})")
                
                # Cập nhật cache
                self.categories_cache[name.lower()] = category['id']
                
                return category['id']
            else:
                logger.error(f"Lỗi khi tạo category: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Lỗi khi tạo category mới: {e}")
            return None
    
    def create_tag(self, name: str, description: str = '') -> Optional[int]:
        """
        Tạo tag mới
        
        Args:
            name: Tên tag
            description: Mô tả tag (tùy chọn)
            
        Returns:
            int: ID của tag mới tạo hoặc None nếu thất bại
        """
        endpoint = f"{self.wp_url}/wp-json/wp/v2/tags"
        
        data = {
            'name': name,
            'description': description
        }
        
        try:
            # Đảm bảo giới hạn tốc độ
            self.rate_limiter.wait_if_needed()
            
            response = self.session.post(endpoint, json=data)
            
            if response.status_code in (200, 201):
                tag = response.json()
                logger.info(f"Đã tạo tag mới: {name} (ID: {tag['id']})")
                
                # Cập nhật cache
                self.tags_cache[name.lower()] = tag['id']
                
                return tag['id']
            else:
                logger.error(f"Lỗi khi tạo tag: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Lỗi khi tạo tag mới: {e}")
            return None
    
    def get_or_create_category(self, name: str) -> Optional[int]:
        """
        Lấy ID category hoặc tạo mới nếu chưa tồn tại
        
        Args:
            name: Tên category
            
        Returns:
            int: ID của category hoặc None nếu thất bại
        """
        # Đảm bảo cache đã được tải
        if not self.categories_cache:
            self.get_categories()
        
        # Kiểm tra xem category đã tồn tại chưa
        name_lower = name.lower()
        if name_lower in self.categories_cache:
            return self.categories_cache[name_lower]
        
        # Nếu chưa tồn tại, tạo mới
        return self.create_category(name)
    
    def get_or_create_tag(self, name: str) -> Optional[int]:
        """
        Lấy ID tag hoặc tạo mới nếu chưa tồn tại
        
        Args:
            name: Tên tag
            
        Returns:
            int: ID của tag hoặc None nếu thất bại
        """
        # Đảm bảo cache đã được tải
        if not self.tags_cache:
            self.get_tags()
        
        # Kiểm tra xem tag đã tồn tại chưa
        name_lower = name.lower()
        if name_lower in self.tags_cache:
            return self.tags_cache[name_lower]
        
        # Nếu chưa tồn tại, tạo mới
        return self.create_tag(name)
    
    def upload_media(self, image_url: str, alt_text: str = '') -> Optional[int]:
        """Tải lên hình ảnh với phương pháp đơn giản"""
        logger.info(f"Bắt đầu tải lên hình ảnh từ URL: {image_url}")
        
        try:
            # Tải hình ảnh với timeout ngắn
            img_response = requests.get(image_url, stream=True, timeout=10)
            if img_response.status_code != 200:
                logger.error(f"Không thể tải hình ảnh từ URL {image_url}: {img_response.status_code}")
                return None
            
            # Xử lý tên file
            parsed_url = urlparse(image_url)
            image_filename = os.path.basename(parsed_url.path)
            if not image_filename or '.' not in image_filename:
                image_filename = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            
            # Lưu vào file tạm
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(image_filename)[1]) as temp_file:
                for chunk in img_response.iter_content(chunk_size=8192):  # Chunk lớn hơn
                    temp_file.write(chunk)
                temp_filepath = temp_file.name
            
            # Upload lên WordPress
            endpoint = f"{self.wp_url}/wp-json/wp/v2/media"
            headers = {'Content-Disposition': f'attachment; filename="{image_filename}"'}
            
            self.rate_limiter.wait_if_needed()
            
            with open(temp_filepath, 'rb') as img_file:
                files = {'file': (image_filename, img_file)}
                data = {'alt_text': alt_text} if alt_text else {}
                response = self.session.post(endpoint, headers=headers, files=files, data=data)
            
            # Xóa file tạm
            os.unlink(temp_filepath)
            
            if response.status_code in (200, 201):
                media = response.json()
                media_id = media['id']
                logger.info(f"Đã tải lên hình ảnh thành công. Media ID: {media_id}")
                return media_id
            else:
                logger.error(f"Lỗi khi tải lên hình ảnh: {response.status_code}")
                return None
        
        except Exception as e:
            logger.error(f"Lỗi khi tải lên hình ảnh: {e}")
            return None
    
    def publish_post(self, title: str, content: str, slug: str = None, 
                    excerpt: str = None, categories: List[int] = None,
                    tags: List[int] = None, featured_media: int = None,
                    seo_metadata: Dict[str, Any] = None, keyword: str = None) -> Optional[int]:
        """
        Đăng bài viết mới lên WordPress
        
        Args:
            title: Tiêu đề bài viết
            content: Nội dung HTML của bài viết
            slug: Slug URL (tùy chọn)
            excerpt: Tóm tắt bài viết (tùy chọn)
            categories: Danh sách ID các danh mục (tùy chọn)
            tags: Danh sách ID các thẻ (tùy chọn)
            featured_media: ID của ảnh đại diện (tùy chọn)
            seo_metadata: Metadata SEO (tùy chọn)
            keyword: Từ khóa gốc để theo dõi (tùy chọn)
            
        Returns:
            int: ID của bài viết mới hoặc None nếu thất bại
        """
        endpoint = f"{self.wp_url}/wp-json/wp/v2/posts"
        
        # Chuẩn bị dữ liệu bài viết
        data = {
            'title': title,
            'content': content,
            'status': 'publish'
        }
        
        if slug:
            data['slug'] = slug
        
        if excerpt:
            data['excerpt'] = excerpt
        
        if categories:
            data['categories'] = categories
        
        if tags:
            data['tags'] = tags
        
        if featured_media:
            data['featured_media'] = featured_media
        
        # Xử lý metadata SEO nếu có
        if seo_metadata and self.use_yoast_seo:
            # Xây dựng metadata cho Yoast SEO
            meta = {}
            
            if 'meta_title' in seo_metadata:
                meta['_yoast_wpseo_title'] = seo_metadata['meta_title']
            
            if 'meta_description' in seo_metadata:
                meta['_yoast_wpseo_metadesc'] = seo_metadata['meta_description']
            
            if 'focus_keyword' in seo_metadata:
                meta['_yoast_wpseo_focuskw'] = seo_metadata['focus_keyword']
            
            # Thêm meta vào data
            if meta:
                data['meta'] = meta
        
        try:
            logger.info(f"Đang đăng bài viết: {title}")
            
            # Đảm bảo giới hạn tốc độ
            self.rate_limiter.wait_if_needed()
            
            response = self.session.post(endpoint, json=data)
            
            if response.status_code in (200, 201):
                post_data = response.json()
                post_id = post_data['id']
                
                logger.info(f"Đã đăng bài viết thành công. Post ID: {post_id}")
                
                # Lưu thông tin bài đăng nếu có từ khóa
                if keyword:
                    self._save_published_post(keyword, post_id, post_data)
                
                return post_id
            else:
                logger.error(f"Lỗi khi đăng bài viết: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Lỗi khi đăng bài viết: {e}")
            return None
    
    def check_post_exists(self, keyword: str) -> bool:
        """
        Kiểm tra xem bài viết cho từ khóa đã tồn tại chưa
        
        Args:
            keyword: Từ khóa cần kiểm tra
            
        Returns:
            bool: True nếu bài viết đã tồn tại, False nếu chưa
        """
        return keyword in self.published_posts.get('posts', {})
    
    def get_published_posts(self) -> Dict[str, Any]:
        """
        Lấy danh sách bài đã đăng
        
        Returns:
            Dict: Thông tin về các bài đã đăng
        """
        return self.published_posts

# Tạo instance toàn cục
wordpress_api = WordPressAPI()