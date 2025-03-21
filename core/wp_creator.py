import time
import random
from typing import Dict, List, Any, Optional, Set, Tuple

from config import config
from utils.logger import logger
from core.wordpress_api import wordpress_api
from core.seo_manager import seo_manager
from core.content_generator import content_generator
from core.image_finder import image_finder
from core.video_finder import video_finder

class WordPressContentCreator:
    """Quản lý quy trình tạo và đăng bài viết WordPress tự động"""
    
    def __init__(self):
        """Khởi tạo hệ thống"""
        # Kết nối với WordPress
        if not wordpress_api.check_connection():
            raise ConnectionError("Không thể kết nối đến WordPress")
        
        # Thiết lập thống kê
        self.successful_posts = 0
        self.failed_posts = 0
        self.start_time = time.time()
        
        logger.info("WordPressContentCreator đã được khởi tạo thành công")
    
    def create_post(self, keyword: str, options: Dict[str, Any] = None) -> bool:
        """
        Tạo và đăng bài viết lên WordPress cho một từ khóa với xử lý lỗi tốt hơn
        
        Args:
            keyword: Từ khóa cần xử lý
            options: Tùy chọn bổ sung (tùy chọn)
            
        Returns:
            bool: True nếu thành công, False nếu thất bại
        """
        if options is None:
            options = {}
                
        logger.info(f"""
        ======================================================= 
        ==== BẮT ĐẦU TẠO BÀI VIẾT CHO TỪ KHÓA: {keyword} 
        =======================================================
        """)
        
        # Kiểm tra xem bài viết đã tồn tại chưa
        if wordpress_api.check_post_exists(keyword):
            logger.warning(f"Bài viết cho từ khóa '{keyword}' đã tồn tại. Bỏ qua.")
            return True
        
        try:
            # Bước 1: Nghiên cứu từ khóa và tạo nội dung - có xử lý lỗi
            logger.info("Bước 1: Đang nghiên cứu từ khóa và tạo nội dung...")
            try:
                research_data, html_content = content_generator.research_and_generate_content(keyword)
                
                if not research_data:
                    logger.error(f"Không thể nghiên cứu từ khóa: {keyword}")
                    return False
                
                if not html_content:
                    logger.error(f"Không thể tạo nội dung HTML cho từ khóa: {keyword}")
                    return False
            except Exception as e:
                logger.error(f"Lỗi trong quá trình nghiên cứu và tạo nội dung: {e}")
                return False
            
            # Bước 2: Tìm kiếm hình ảnh với retry
            logger.info("Bước 2: Đang tìm kiếm hình ảnh...")
            image_urls = []
            try:
                image_urls = image_finder.get_images(keyword)
            except Exception as e:
                logger.error(f"Lỗi khi tìm kiếm hình ảnh: {e}")
                # Tiếp tục mà không có hình ảnh

            featured_image_id = None
            if image_urls:
                # Upload ảnh đại diện với retry
                logger.info(f"Đang tải lên ảnh đại diện cho bài viết (có {len(image_urls)} ảnh)...")
                
                for i, img_url in enumerate(image_urls):
                    logger.info(f"Thử tải ảnh thứ {i+1}/{len(image_urls)}: {img_url}")
                    try:
                        featured_image_id = wordpress_api.upload_media(
                            img_url, 
                            alt_text=f"{keyword} featured image"
                        )
                        
                        if featured_image_id:
                            logger.info(f"Đã tải lên ảnh đại diện thành công. ID: {featured_image_id}")
                            break
                        else:
                            logger.warning(f"Không thể tải ảnh thứ {i+1} từ {img_url}")
                    except Exception as e:
                        logger.warning(f"Lỗi khi tải ảnh: {e}")
                        continue
                
                if not featured_image_id:
                    logger.warning("Không thể tải lên ảnh đại diện sau khi thử tất cả các URL")
            else:
                logger.warning(f"Không tìm thấy hình ảnh cho từ khóa: {keyword}")
            
            # Bước 3: Tìm kiếm video với timeout
            logger.info("Bước 3: Đang tìm kiếm video...")
            video_embed_url = None
            try:
                video_embed_url = video_finder.get_video(keyword)
                if video_embed_url:
                    logger.info(f"Đã tìm thấy video cho từ khóa: {keyword}")
                else:
                    logger.warning(f"Không tìm thấy video cho từ khóa: {keyword} (không bắt buộc)")
            except Exception as e:
                logger.error(f"Lỗi khi tìm kiếm video: {e}")
                # Tiếp tục mà không có video
            
            # Bước 4: Xây dựng HTML hoàn chỉnh
            logger.info("Bước 4: Đang xây dựng HTML hoàn chỉnh...")
            try:
                complete_html = content_generator.build_complete_html(keyword, html_content, video_embed_url, image_urls)
                
                if not complete_html:
                    logger.error(f"Không thể xây dựng HTML hoàn chỉnh cho từ khóa: {keyword}")
                    # Sử dụng HTML gốc nếu không thể xây dựng HTML hoàn chỉnh
                    complete_html = html_content
                    logger.warning("Sử dụng HTML gốc để tiếp tục")
            except Exception as e:
                logger.error(f"Lỗi khi xây dựng HTML hoàn chỉnh: {e}")
                complete_html = html_content  # Sử dụng HTML gốc
            
            # Bước 5: Chuẩn bị tiêu đề với xử lý lỗi
            title = None
            try:
                if research_data and 'suggested_title' in research_data:
                    title = research_data['suggested_title']
                    logger.info(f"Sử dụng tiêu đề SEO tối ưu: {title}")
                else:
                    title = f"{keyword.capitalize()}: Ultimate Guide & Review"
                    logger.info(f"Sử dụng tiêu đề mặc định: {title}")
            except Exception as e:
                logger.error(f"Lỗi khi chuẩn bị tiêu đề: {e}")
                title = f"{keyword.capitalize()} Guide"
            
            # Bước 6: Chuẩn bị dữ liệu SEO
            logger.info("Bước 6: Đang chuẩn bị dữ liệu SEO...")
            try:
                seo_data = seo_manager.prepare_seo_data(keyword, title, research_data)
                logger.info(f"Dữ liệu SEO: slug={seo_data['slug']}, categories={len(seo_data['category_ids'])}, tags={len(seo_data['tag_ids'])}")
            except Exception as e:
                logger.error(f"Lỗi khi chuẩn bị dữ liệu SEO: {e}")
                # Tạo dữ liệu SEO cơ bản nếu có lỗi
                seo_data = {
                    'slug': keyword.lower().replace(' ', '-'),
                    'category_ids': [],
                    'tag_ids': [],
                    'excerpt': f"Learn everything about {keyword} in this comprehensive guide.",
                    'seo_metadata': {
                        'meta_title': title,
                        'meta_description': f"Complete guide about {keyword} with tips and examples.",
                        'focus_keyword': keyword
                    }
                }
            
            # Bước 7: Đăng bài viết lên WordPress với retry
            logger.info("Bước 7: Đang đăng bài viết lên WordPress...")
            post_id = None
            max_retries = 2
            
            for retry in range(max_retries + 1):
                try:
                    post_id = wordpress_api.publish_post(
                        title=title,
                        content=complete_html,
                        slug=seo_data['slug'],
                        excerpt=seo_data['excerpt'],
                        categories=seo_data['category_ids'],
                        tags=seo_data['tag_ids'],
                        featured_media=featured_image_id,
                        seo_metadata=seo_data['seo_metadata'],
                        keyword=keyword
                    )
                    
                    if post_id:
                        break  # Thành công, thoát vòng lặp
                    
                    # Nếu không thành công, thử lại
                    logger.warning(f"Lần thử {retry+1}/{max_retries} đăng bài thất bại. Thử lại...")
                    time.sleep(5 * (retry + 1))  # Chờ lâu hơn mỗi lần thử
                except Exception as e:
                    logger.error(f"Lỗi khi đăng bài (thử lần {retry+1}): {e}")
                    if retry < max_retries:
                        time.sleep(5 * (retry + 1))
                        logger.info(f"Thử lại lần {retry+2}...")
            
            if post_id:
                logger.info(f"""
                ===========================================
                ==== ĐĂNG BÀI THÀNH CÔNG!
                ==== Từ khóa: {keyword}
                ==== Post ID: {post_id}
                ===========================================
                """)
                self.successful_posts += 1
                return True
            else:
                logger.error(f"Đăng bài thất bại cho từ khóa: {keyword} sau {max_retries+1} lần thử")
                self.failed_posts += 1
                return False
                    
        except Exception as e:
            logger.error(f"Lỗi không xác định khi xử lý từ khóa '{keyword}': {e}")
            self.failed_posts += 1
            return False
    
    def process_keywords(self, keywords: List[str], max_keywords: Optional[int] = None, 
                        random_order: bool = False) -> Dict[str, Any]:
        """
        Xử lý danh sách từ khóa
        
        Args:
            keywords: Danh sách từ khóa cần xử lý
            max_keywords: Số lượng từ khóa tối đa cần xử lý (None = không giới hạn)
            random_order: Xáo trộn thứ tự từ khóa
            
        Returns:
            Dict: Thống kê về quá trình xử lý
        """
        if not keywords:
            logger.warning("Không có từ khóa nào để xử lý")
            return {
                "total_processed": 0,
                "successful": 0,
                "failed": 0,
                "runtime_seconds": 0
            }
        
        # Tạo bản sao danh sách từ khóa
        keyword_list = keywords.copy()
        
        # Xáo trộn nếu yêu cầu
        if random_order:
            random.shuffle(keyword_list)
        
        # Giới hạn số lượng từ khóa cần xử lý
        if max_keywords is not None:
            keyword_list = keyword_list[:max_keywords]
        
        total_keywords = len(keyword_list)
        logger.info(f"Bắt đầu xử lý {total_keywords} từ khóa")
        
        # Reset bộ đếm
        self.successful_posts = 0
        self.failed_posts = 0
        self.start_time = time.time()
        
        # Xử lý từng từ khóa
        for i, keyword in enumerate(keyword_list, start=1):
            logger.info(f"Đang xử lý từ khóa {i}/{total_keywords}: {keyword}")
            
            # Xử lý từ khóa
            success = self.create_post(keyword)
            
            # Chờ một khoảng thời gian giữa các lần xử lý
            if i < total_keywords:
                # Thời gian chờ dài hơn sau mỗi lần thất bại
                if not success:
                    wait_time = random.uniform(60, 120)  # 1-2 phút nếu thất bại
                else:
                    wait_time = random.uniform(30, 60)  # 30-60 giây nếu thành công
                    
                logger.info(f"Chờ {wait_time:.2f}s trước khi xử lý từ khóa tiếp theo")
                time.sleep(wait_time)
        
        # Tính thời gian chạy
        end_time = time.time()
        runtime_seconds = int(end_time - self.start_time)
        
        # Trả về thống kê
        return {
            "total_processed": total_keywords,
            "successful": self.successful_posts,
            "failed": self.failed_posts,
            "runtime_seconds": runtime_seconds
        }
    
    def process_keywords_parallel(self, keywords: List[str], max_workers: int = 3, 
                                max_keywords: Optional[int] = None, 
                                random_order: bool = False) -> Dict[str, Any]:
        """
        Xử lý danh sách từ khóa song song
        
        Args:
            keywords: Danh sách từ khóa cần xử lý
            max_workers: Số luồng tối đa chạy song song
            max_keywords: Số lượng từ khóa tối đa cần xử lý (None = không giới hạn)
            random_order: Xáo trộn thứ tự từ khóa
            
        Returns:
            Dict: Thống kê về quá trình xử lý
        """
        import threading
        import queue
        
        if not keywords:
            logger.warning("Không có từ khóa nào để xử lý")
            return {
                "total_processed": 0,
                "successful": 0,
                "failed": 0,
                "runtime_seconds": 0
            }
        
        # Tạo bản sao danh sách từ khóa
        keyword_list = keywords.copy()
        
        # Xáo trộn nếu yêu cầu
        if random_order:
            random.shuffle(keyword_list)
        
        # Giới hạn số lượng từ khóa cần xử lý
        if max_keywords is not None:
            keyword_list = keyword_list[:max_keywords]
        
        total_keywords = len(keyword_list)
        logger.info(f"Bắt đầu xử lý {total_keywords} từ khóa song song với {max_workers} luồng")
        
        # Tạo lock và biến đếm cho thống kê
        stats_lock = threading.RLock()
        stats = {
            "successful": 0,
            "failed": 0,
            "processed": 0,
            "completed": []
        }
        
        # Tạo hàng đợi từ khóa
        keyword_queue = queue.Queue()
        for kw in keyword_list:
            keyword_queue.put(kw)
        
        # Đặt thời gian bắt đầu
        start_time = time.time()
        
        # Hàm worker xử lý từ khóa từ hàng đợi
        def worker():
            while not keyword_queue.empty():
                try:
                    # Lấy từ khóa từ hàng đợi
                    keyword = keyword_queue.get(timeout=1)
                    
                    logger.info(f"Luồng {threading.current_thread().name} đang xử lý từ khóa: {keyword}")
                    
                    # Xử lý từ khóa
                    success = self.create_post(keyword)
                    
                    # Cập nhật thống kê
                    with stats_lock:
                        if success:
                            stats["successful"] += 1
                        else:
                            stats["failed"] += 1
                        stats["processed"] += 1
                        stats["completed"].append((keyword, success))
                    
                    # Đánh dấu đã hoàn thành
                    keyword_queue.task_done()
                    
                    # Thời gian nghỉ giữa các lần xử lý trong cùng một luồng
                    wait_time = random.uniform(3, 7) if success else random.uniform(5, 10)
                    logger.info(f"Luồng {threading.current_thread().name} chờ {wait_time:.2f}s trước khi xử lý từ khóa tiếp theo")
                    time.sleep(wait_time)
                    
                except queue.Empty:
                    # Hàng đợi trống, thoát khỏi luồng
                    break
                except Exception as e:
                    # Xử lý ngoại lệ không mong muốn
                    logger.error(f"Lỗi không xử lý được trong luồng {threading.current_thread().name}: {e}")
                    time.sleep(5)  # Chờ một chút trước khi tiếp tục
        
        # Tạo và khởi chạy worker threads
        threads = []
        for i in range(min(max_workers, total_keywords)):
            thread = threading.Thread(
                target=worker,
                name=f"Worker-{i+1}"
            )
            thread.daemon = True
            threads.append(thread)
            thread.start()
            # Khởi động các luồng cách nhau 1-2 giây
            time.sleep(random.uniform(1, 2))
        
        # Chờ tất cả các công việc hoàn thành
        # Dùng timeout để phòng trường hợp treo
        for thread in threads:
            thread.join(timeout=3600)  # 1 giờ timeout
        
        # Tính thời gian chạy
        runtime_seconds = int(time.time() - start_time)
        
        # Trả về thống kê
        return {
            "total_processed": total_keywords,
            "successful": stats["successful"],
            "failed": stats["failed"],
            "runtime_seconds": runtime_seconds
        }

    def cleanup(self):
        """Dọn dẹp tài nguyên sau khi hoàn thành"""
        # Đóng Selenium WebDriver
        image_finder.cleanup()
        
        # Thống kê cuối cùng
        total_runtime = int(time.time() - self.start_time)
        
        logger.info(f"""
        ===========================================
        ==== THỐNG KÊ CUỐI CÙNG
        ==== Bài viết thành công: {self.successful_posts}
        ==== Bài viết thất bại: {self.failed_posts}
        ==== Tổng thời gian: {total_runtime} giây
        ===========================================
        """)

# Tạo instance toàn cục
wp_creator = WordPressContentCreator()