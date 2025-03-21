#!/usr/bin/env python3
"""
WordPress Auto Content Generator

Chương trình tự động tạo nội dung và đăng bài lên WordPress dựa trên danh sách từ khóa.
Sử dụng Gemini AI để tạo nội dung chất lượng cao và tối ưu SEO.
"""

import os
import sys
import time
import argparse
from datetime import datetime
from typing import List, Set, Dict, Any

from config import config
from utils.logger import logger
from utils.cache_manager import cache_manager, cleanup_all_caches
from core.wordpress_api import wordpress_api
from core.content_generator import content_generator, gemini_key_manager
from core.wp_creator import wp_creator

def format_time(seconds: int) -> str:
    """
    Định dạng thời gian thành HH:MM:SS
    
    Args:
        seconds: Số giây
        
    Returns:
        str: Chuỗi thời gian định dạng HH:MM:SS
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02}:{minutes:02}:{secs:02}"

def read_keywords_from_file(file_path: str) -> Set[str]:
    """
    Đọc danh sách từ khóa từ file văn bản
    
    Args:
        file_path: Đường dẫn đến file từ khóa
        
    Returns:
        Set[str]: Tập hợp các từ khóa
    """
    keywords = set()
    
    try:
        if not os.path.exists(file_path):
            logger.error(f"File không tồn tại: {file_path}")
            return keywords
            
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):  # Bỏ qua comment và dòng trống
                    keywords.add(line)
                    
        logger.info(f"Đã đọc {len(keywords)} từ khóa từ file: {file_path}")
    except Exception as e:
        logger.error(f"Lỗi khi đọc file từ khóa: {e}")
    
    return keywords

def read_keywords_from_folder(folder_path: str) -> Set[str]:
    """
    Đọc danh sách từ khóa từ tất cả các file .txt trong thư mục
    
    Args:
        folder_path: Đường dẫn đến thư mục chứa file từ khóa
        
    Returns:
        Set[str]: Tập hợp các từ khóa
    """
    keywords = set()
    
    try:
        if not os.path.exists(folder_path):
            logger.error(f"Thư mục không tồn tại: {folder_path}")
            return keywords
            
        # Lấy tất cả file .txt trong thư mục
        txt_files = [f for f in os.listdir(folder_path) if f.endswith('.txt')]
        
        for txt_file in txt_files:
            file_path = os.path.join(folder_path, txt_file)
            file_keywords = read_keywords_from_file(file_path)
            keywords.update(file_keywords)
            
        logger.info(f"Tổng cộng: {len(keywords)} từ khóa từ {len(txt_files)} file")
    except Exception as e:
        logger.error(f"Lỗi khi đọc thư mục từ khóa: {e}")
    
    return keywords

def initialize_system() -> bool:
    """
    Khởi tạo và kiểm tra hệ thống
    
    Returns:
        bool: True nếu khởi tạo thành công, False nếu thất bại
    """
    logger.info("=== KHỞI TẠO HỆ THỐNG ===")
    
    # 1. Kiểm tra kết nối WordPress
    logger.info("Kiểm tra kết nối WordPress...")
    if not wordpress_api.check_connection():
        logger.critical("Không thể kết nối đến WordPress. Vui lòng kiểm tra cấu hình.")
        return False
    
    logger.info("Kết nối WordPress thành công!")
    
    # 2. Kiểm tra API keys Gemini
    logger.info("Kiểm tra Gemini API keys...")
    if not gemini_key_manager.keys:
        logger.critical("Không tìm thấy Gemini API key nào. Vui lòng cấu hình trong file .env")
        return False
    
    logger.info(f"Tìm thấy {len(gemini_key_manager.keys)} Gemini API key")
    
    # 3. Dọn dẹp cache
    logger.info("Dọn dẹp cache...")
    cleanup_all_caches()
    
    return True

def main():
    """Hàm chính để chạy chương trình"""
    # Phân tích tham số dòng lệnh
    parser = argparse.ArgumentParser(description='Hệ thống tạo nội dung WordPress tự động')
    parser.add_argument('--keyword', type=str, help='Chỉ xử lý một từ khóa cụ thể')
    parser.add_argument('--file', type=str, help='Đường dẫn đến file từ khóa')
    parser.add_argument('--max', type=int, help='Số lượng từ khóa tối đa cần xử lý')
    parser.add_argument('--random', action='store_true', help='Xáo trộn thứ tự từ khóa')
    parser.add_argument('--check', action='store_true', help='Chỉ kiểm tra kết nối rồi thoát')
    parser.add_argument('--clean-cache', action='store_true', help='Dọn dẹp cache trước khi bắt đầu')
    parser.add_argument('--workers', type=int, help='Số luồng xử lý song song (mặc định: 3)')

    args = parser.parse_args()
    
    # Hiển thị banner và thông tin
    print("""
    ┌──────────────────────────────────────────────┐
    │         WordPress Auto Content Creator        │
    │    Tự động tạo nội dung chất lượng cao SEO    │
    └──────────────────────────────────────────────┘
    """)
    
    # Dọn dẹp cache nếu yêu cầu
    if args.clean_cache:
        logger.info("Dọn dẹp cache theo yêu cầu...")
        cleanup_all_caches()
    
    # Khởi tạo hệ thống
    if not initialize_system():
        logger.critical("Không thể khởi tạo hệ thống. Thoát.")
        return 1
    
    # Nếu chỉ kiểm tra kết nối
    if args.check:
        logger.info("Kiểm tra kết nối thành công. Thoát.")
        return 0
    
    # Lấy danh sách từ khóa
    keywords = set()
    
    # Ưu tiên từ khóa từ tham số --keyword
    if args.keyword:
        keywords.add(args.keyword)
        logger.info(f"Sử dụng từ khóa đơn: {args.keyword}")
    
    # Nếu có file từ khóa
    elif args.file:
        keywords = read_keywords_from_file(args.file)
    
    # Mặc định đọc từ thư mục keywords
    else:
        keywords = read_keywords_from_folder(config.KEYWORDS_DIR)
    
    # Kiểm tra nếu không có từ khóa nào
    if not keywords:
        logger.error("Không có từ khóa nào để xử lý. Thoát.")
        return 1
    
    # Bắt đầu xử lý
    logger.info("=== BẮT ĐẦU XỬ LÝ TỪ KHÓA ===")
    start_time = time.time()
    
    # Xử lý danh sách từ khóa
    if hasattr(wp_creator, 'process_keywords_parallel') and config.ENABLE_PARALLEL:
        workers = args.workers if args.workers is not None else config.PARALLEL_WORKERS
        
        stats = wp_creator.process_keywords_parallel(
            keywords=list(keywords),
            max_workers=config.PARALLEL_WORKERS,
            max_keywords=args.max,
            random_order=args.random
        )
    else:
        stats = wp_creator.process_keywords(
            keywords=list(keywords),
            max_keywords=args.max,
            random_order=args.random
        )
    
    # Hiển thị thống kê
    logger.info(f"=== KẾT THÚC XỬ LÝ TỪ KHÓA ===")
    runtime_formatted = format_time(stats["runtime_seconds"])
    logger.info(f"Tổng số từ khóa đã xử lý: {stats['total_processed']}")
    
    if stats['total_processed'] > 0:
        success_rate = stats['successful'] / stats['total_processed'] * 100
        failure_rate = stats['failed'] / stats['total_processed'] * 100
    else:
        success_rate = 0
        failure_rate = 0
        
    logger.info(f"Thành công: {stats['successful']}/{stats['total_processed']} ({success_rate:.1f}%)")
    logger.info(f"Thất bại: {stats['failed']}/{stats['total_processed']} ({failure_rate:.1f}%)")
    logger.info(f"Thời gian chạy: {runtime_formatted}")
    
    # Dọn dẹp tài nguyên
    logger.info("Dọn dẹp tài nguyên...")
    wp_creator.cleanup()
    
    # Lưu cache
    cache_manager.save_all()
    
    # Tính tổng thời gian chạy
    total_time = time.time() - start_time
    logger.info(f"Tổng thời gian chạy chương trình: {format_time(int(total_time))}")
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.warning("Chương trình bị dừng bởi người dùng")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Lỗi không xử lý được: {e}")
        sys.exit(1)