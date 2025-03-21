import re
import unidecode
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from utils.logger import logger
from core.wordpress_api import wordpress_api

class SEOManager:
    """Quản lý các yếu tố SEO cho bài viết WordPress"""
    
    def __init__(self):
        """Khởi tạo quản lý SEO"""
        self.wp = wordpress_api
        self.max_slug_length = 60
        self.max_meta_title_length = 60
        self.max_meta_desc_length = 160
        
        # Ánh xạ danh mục chính
        self.main_categories_map = {
            "Fashion": ["Fashion", "Style", "Clothing", "Outfits", "Accessories"],
            "Technology": ["Technology", "Tech", "Digital", "Gadgets", "Electronics"],
            "Health": ["Health", "Wellness", "Fitness", "Medical", "Nutrition"],
            "Travel": ["Travel", "Tourism", "Vacation", "Trip", "Adventure"],
            "Food": ["Food", "Cooking", "Recipe", "Culinary", "Dining"],
            "Business": ["Business", "Finance", "Money", "Investment", "Entrepreneurship"],
            "Education": ["Education", "Learning", "Study", "School", "Training"],
            "Entertainment": ["Entertainment", "Movies", "TV", "Music", "Games"],
            "Sports": ["Sports", "Fitness", "Athletics", "Exercise", "Games"],
            "Lifestyle": ["Lifestyle", "Life", "Living", "Family", "Home"],
            "Automotive": ["Automotive", "Cars", "Vehicles", "Driving", "Auto"],
            "Beauty": ["Beauty", "Makeup", "Skincare", "Cosmetics", "Hair"],
        }
        
        logger.info("SEOManager đã được khởi tạo")
    
    def generate_slug(self, keyword: str, title: str = None) -> str:
        """
        Tạo slug URL từ từ khóa hoặc tiêu đề
        
        Args:
            keyword: Từ khóa gốc
            title: Tiêu đề bài viết (nếu có)
            
        Returns:
            str: Slug URL hợp lệ
        """
        # Ưu tiên sử dụng tiêu đề nếu có
        text = title if title else keyword
        
        # Chuyển đổi dấu thành không dấu
        slug = unidecode.unidecode(text.lower())
        
        # Loại bỏ ký tự đặc biệt
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        
        # Thay thế khoảng trắng bằng dấu gạch ngang
        slug = re.sub(r'\s+', '-', slug)
        
        # Loại bỏ nhiều dấu gạch ngang liên tiếp
        slug = re.sub(r'-+', '-', slug)
        
        # Cắt bớt nếu slug quá dài
        if len(slug) > self.max_slug_length:
            slug = slug[:self.max_slug_length].rstrip('-')
        
        logger.debug(f"Đã tạo slug: {slug} từ {'tiêu đề' if title else 'từ khóa'}")
        return slug.strip('-')
    
    def generate_meta_title(self, keyword: str, research_data: Dict = None) -> str:
        """
        Tạo thẻ meta title tối ưu SEO
        
        Args:
            keyword: Từ khóa chính
            research_data: Dữ liệu nghiên cứu từ khóa (nếu có)
            
        Returns:
            str: Meta title tối ưu
        """
        if research_data and 'suggested_title' in research_data:
            # Sử dụng tiêu đề gợi ý từ nghiên cứu
            meta_title = research_data['suggested_title']
        else:
            # Tạo meta title tốt dựa trên từ khóa
            current_year = datetime.now().year
            meta_title = f"{keyword.title()}: Complete Guide & Tips [{current_year}]"
        
        # Đảm bảo độ dài hợp lý
        if len(meta_title) > self.max_meta_title_length:
            meta_title = meta_title[:self.max_meta_title_length-3].rstrip() + "..."
        
        logger.debug(f"Đã tạo meta title: {meta_title}")
        return meta_title
    
    def generate_meta_description(self, keyword: str, research_data: Dict = None) -> str:
        """
        Tạo thẻ meta description tối ưu SEO
        
        Args:
            keyword: Từ khóa chính
            research_data: Dữ liệu nghiên cứu từ khóa (nếu có)
            
        Returns:
            str: Meta description tối ưu
        """
        if research_data and 'meta_description' in research_data:
            # Sử dụng meta description từ nghiên cứu
            meta_desc = research_data['meta_description']
        else:
            # Tạo meta description tự động
            meta_desc = f"Looking for information about {keyword}? Our comprehensive guide covers everything you need to know about {keyword} including tips, examples, and expert advice."
        
        # Đảm bảo độ dài hợp lý
        if len(meta_desc) > self.max_meta_desc_length:
            meta_desc = meta_desc[:self.max_meta_desc_length-3].rstrip() + "..."
        
        logger.debug(f"Đã tạo meta description với độ dài {len(meta_desc)} ký tự")
        return meta_desc
    
    def detect_main_category(self, keyword: str, research_data: Dict = None) -> str:
        """
        Xác định danh mục chính dựa trên từ khóa và dữ liệu nghiên cứu
        
        Args:
            keyword: Từ khóa chính
            research_data: Dữ liệu nghiên cứu từ khóa (nếu có)
            
        Returns:
            str: Tên danh mục chính
        """
        keyword_lower = keyword.lower()
        scores = {}
        
        # Tính điểm cho từng danh mục
        for category, keywords in self.main_categories_map.items():
            score = 0
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower == keyword_lower:
                    score += 10  # Trùng khớp hoàn toàn
                elif kw_lower in keyword_lower:
                    score += 5   # Từ khóa là một phần
                elif keyword_lower in kw_lower:
                    score += 3   # Một phần của từ khóa
            
            scores[category] = score
        
        # Sử dụng thông tin từ nghiên cứu nếu có
        if research_data:
            # Từ topic_type
            if 'topic_type' in research_data:
                topic_type = research_data['topic_type'].lower()
                
                for category, keywords in self.main_categories_map.items():
                    for kw in keywords:
                        if kw.lower() in topic_type:
                            scores[category] += 5
            
            # Từ từ khóa liên quan
            if 'related_keywords' in research_data and isinstance(research_data['related_keywords'], list):
                for related in research_data['related_keywords']:
                    if not isinstance(related, str):
                        continue
                        
                    related_lower = related.lower()
                    for category, keywords in self.main_categories_map.items():
                        for kw in keywords:
                            if kw.lower() in related_lower:
                                scores[category] += 2
            
            # Từ WordPress category suggestions
            if 'wordpress_category_suggestions' in research_data and isinstance(research_data['wordpress_category_suggestions'], list):
                for suggested_cat in research_data['wordpress_category_suggestions']:
                    if not isinstance(suggested_cat, str):
                        continue
                        
                    suggested_cat_lower = suggested_cat.lower()
                    for category in self.main_categories_map.keys():
                        if category.lower() == suggested_cat_lower:
                            scores[category] += 10
        
        # Lấy danh mục có điểm cao nhất
        if scores and max(scores.values()) > 0:
            main_category = max(scores.items(), key=lambda x: x[1])[0]
            logger.info(f"Đã xác định danh mục chính: {main_category} cho từ khóa '{keyword}'")
            return main_category
        
        # Nếu không tìm thấy danh mục phù hợp, trả về "General"
        logger.info(f"Không tìm thấy danh mục phù hợp cho '{keyword}', sử dụng General")
        return "General"
    
    def extract_seo_tags(self, keyword: str, research_data: Dict = None) -> List[str]:
        """
        Trích xuất tags liên quan cho SEO
        
        Args:
            keyword: Từ khóa chính
            research_data: Dữ liệu nghiên cứu từ khóa (nếu có)
            
        Returns:
            List[str]: Danh sách tags
        """
        tags = []
        
        # Thêm keyword chính làm tag đầu tiên
        tags.append(keyword.title())
        
        # Lấy tags từ dữ liệu nghiên cứu
        if research_data:
            # Từ related_keywords
            if 'related_keywords' in research_data and isinstance(research_data['related_keywords'], list):
                for related in research_data['related_keywords'][:5]:  # Giới hạn 5 từ khóa liên quan
                    if isinstance(related, str) and related.lower() != keyword.lower():
                        tags.append(related.title())
            
            # Từ WordPress tag suggestions
            if 'wordpress_tag_suggestions' in research_data and isinstance(research_data['wordpress_tag_suggestions'], list):
                for suggested_tag in research_data['wordpress_tag_suggestions']:
                    if isinstance(suggested_tag, str) and suggested_tag.lower() not in [t.lower() for t in tags]:
                        tags.append(suggested_tag.title())
        
        # Tạo các biến thể tags phổ biến
        common_variants = [
            f"{keyword} guide",
            f"{keyword} tips",
            f"best {keyword}"
        ]
        
        for variant in common_variants:
            if variant.lower() not in [t.lower() for t in tags]:
                tags.append(variant.title())
        
        # Loại bỏ trùng lặp và giới hạn số lượng tags
        unique_tags = []
        for tag in tags:
            if tag.lower() not in [t.lower() for t in unique_tags]:
                unique_tags.append(tag)
        
        logger.info(f"Đã trích xuất {len(unique_tags)} tags từ từ khóa '{keyword}'")
        return unique_tags[:10]  # Giới hạn tối đa 10 tags
    
    def prepare_categories_and_tags(self, keyword: str, research_data: Dict = None) -> Tuple[List[int], List[int]]:
        """
        Chuẩn bị danh sách ID categories và tags cho WordPress
        
        Args:
            keyword: Từ khóa chính
            research_data: Dữ liệu nghiên cứu từ khóa (nếu có)
            
        Returns:
            Tuple[List[int], List[int]]: (Danh sách ID categories, Danh sách ID tags)
        """
        # Xác định danh mục chính
        main_category = self.detect_main_category(keyword, research_data)
        
        # Lấy hoặc tạo category
        category_ids = []
        main_cat_id = self.wp.get_or_create_category(main_category)
        if main_cat_id:
            category_ids.append(main_cat_id)
            
            # Thêm danh mục phụ nếu cần
            if research_data and 'topic_type' in research_data:
                sub_category = research_data['topic_type'].title()
                if sub_category.lower() != main_category.lower():
                    sub_cat_id = self.wp.get_or_create_category(sub_category)
                    if sub_cat_id:
                        category_ids.append(sub_cat_id)
        
        # Trích xuất tags
        tag_names = self.extract_seo_tags(keyword, research_data)
        tag_ids = []
        
        # Lấy hoặc tạo tags
        for tag_name in tag_names:
            tag_id = self.wp.get_or_create_tag(tag_name)
            if tag_id:
                tag_ids.append(tag_id)
        
        logger.info(f"Đã chuẩn bị {len(category_ids)} categories và {len(tag_ids)} tags")
        return category_ids, tag_ids
    
    def prepare_seo_data(self, keyword: str, title: str, research_data: Dict = None) -> Dict[str, Any]:
        """
        Chuẩn bị đầy đủ dữ liệu SEO cho bài viết WordPress
        
        Args:
            keyword: Từ khóa chính
            title: Tiêu đề bài viết
            research_data: Dữ liệu nghiên cứu từ khóa (nếu có)
            
        Returns:
            Dict: Dữ liệu SEO đầy đủ
        """
        # Tạo slug
        slug = self.generate_slug(keyword, title)
        
        # Chuẩn bị categories và tags
        category_ids, tag_ids = self.prepare_categories_and_tags(keyword, research_data)
        
        # Tạo meta title và description
        meta_title = self.generate_meta_title(keyword, research_data)
        meta_desc = self.generate_meta_description(keyword, research_data)
        
        # Tạo excerpt từ meta description
        excerpt = meta_desc
        
        # SEO metadata cho plugin (Yoast SEO, Rank Math, v.v.)
        seo_metadata = {
            'meta_title': meta_title,
            'meta_description': meta_desc,
            'focus_keyword': keyword
        }
        
        logger.info(f"Đã chuẩn bị dữ liệu SEO cho từ khóa '{keyword}'")
        return {
            'slug': slug,
            'category_ids': category_ids,
            'tag_ids': tag_ids,
            'excerpt': excerpt,
            'seo_metadata': seo_metadata
        }

# Tạo instance toàn cục
seo_manager = SEOManager()