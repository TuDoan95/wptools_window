import json
import time
import re
import random
import markdown
from typing import Dict, List, Any, Optional, Tuple
from bs4 import BeautifulSoup
import google.generativeai as genai

from config import config
from utils.logger import logger
from utils.rate_limiter import RateLimiter
from utils.api_key_manager import APIKeyManager
from utils.cache_manager import cache_manager

# Khởi tạo cache
keyword_cache = cache_manager.get_cache('keyword_cache')

# Khởi tạo rate limiter
gemini_limiter = RateLimiter(config.GEMINI_RATE_LIMIT)

# Khởi tạo API key manager
gemini_key_manager = APIKeyManager(
    config.GEMINI_API_KEYS,
    config.GEMINI_MAX_KEY_ERRORS,
    config.GEMINI_KEY_ERROR_COOLDOWN
)

class ContentGenerator:
    """Tạo nội dung WordPress chất lượng cao sử dụng Gemini AI"""
    
    def __init__(self):
        """Khởi tạo generator"""
        self.model_name = config.GEMINI_MODEL_NAME
        self.initialized = False
        self.last_reset_time = time.time()
        self.reset_interval = 3600  # Reset cấu hình mỗi giờ
        
        logger.info(f"Khởi tạo ContentGenerator với model: {self.model_name}")
    
    def configure_gemini(self, api_key: Optional[str] = None) -> bool:
        """
        Cấu hình Gemini AI API
        
        Args:
            api_key: API key cụ thể để cấu hình
            
        Returns:
            bool: True nếu cấu hình thành công, False nếu thất bại
        """
        # Reset cấu hình định kỳ
        current_time = time.time()
        if current_time - self.last_reset_time > self.reset_interval:
            self.initialized = False
            self.last_reset_time = current_time
            logger.info("Reset cấu hình Gemini định kỳ")
        
        # Nếu đã khởi tạo rồi, không cần cấu hình lại
        if self.initialized:
            return True
        
        if api_key is None:
            api_key = gemini_key_manager.get_current_key()
        
        # Kiểm tra API key có hợp lệ không
        if not api_key or len(api_key) < 20:
            logger.error(f"API key không hợp lệ hoặc trống")
            gemini_key_manager.mark_error("API key không hợp lệ")
            return False
            
        try:
            genai.configure(api_key=api_key)
            logger.info(f"Đã cấu hình Gemini AI API thành công với key {gemini_key_manager.current_index + 1}")
            self.initialized = True
            return True
        except Exception as e:
            logger.error(f"Lỗi khi cấu hình Gemini AI API: {e}")
            gemini_key_manager.mark_error(f"Lỗi cấu hình: {e}")
            self.initialized = False
            return False
    
    def research_and_generate_content(self, keyword: str, max_attempts: int = 3) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Nghiên cứu từ khóa và tạo nội dung trong một lần gọi API
        
        Args:
            keyword: Từ khóa cần xử lý
            max_attempts: Số lần thử tối đa
            
        Returns:
            Tuple[Dict, str]: (Dữ liệu nghiên cứu, Nội dung HTML) hoặc (Dict trống, None) nếu thất bại
        """
        # Kiểm tra cache
        keyword_lower = keyword.lower().strip()
        cached_data = keyword_cache.get(keyword_lower)
        
        if cached_data and isinstance(cached_data, dict) and 'research' in cached_data and 'content' in cached_data:
            logger.info(f"Sử dụng nghiên cứu và nội dung từ cache cho từ khóa: {keyword}")
            return cached_data['research'], cached_data['content']
        
        # Kiểm tra nếu chỉ có nghiên cứu trong cache
        if cached_data and isinstance(cached_data, dict) and 'research' in cached_data:
            research_data = cached_data['research']
            logger.info(f"Sử dụng nghiên cứu từ cache cho từ khóa: {keyword}, tạo mới nội dung")
        else:
            research_data = {}
        
        # Thiết lập biến theo dõi các key đã thử
        attempts = 0
        tried_keys = set()
        
        while attempts < max_attempts:
            attempts += 1
            
            # Đảm bảo giới hạn tốc độ
            gemini_limiter.wait_if_needed()
            
            # Lấy key hiện tại và cấu hình Gemini
            current_key = gemini_key_manager.get_current_key()
            current_key_index = gemini_key_manager.current_index
            
            if current_key_index in tried_keys and len(tried_keys) < len(gemini_key_manager.keys):
                logger.info(f"Đã thử API key {current_key_index + 1}, chuyển sang key khác")
                current_key = gemini_key_manager.next_key()
                current_key_index = gemini_key_manager.current_index
            
            tried_keys.add(current_key_index)
            
            if not self.configure_gemini(current_key):
                continue
            
            logger.info(f"Thử lần {attempts}/{max_attempts}: Đang nghiên cứu và tạo nội dung cho từ khóa: {keyword} (API key {current_key_index + 1})")
            
            # 1. Xây dựng prompt cho cả nghiên cứu và tạo nội dung
            prompt = self._build_prompt(keyword, research_data)
            
            # 2. Cấu hình generation
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
            }
            
            try:
                # 3. Gọi API
                model = genai.GenerativeModel(
                    model_name=self.model_name,
                    generation_config=generation_config,
                )
                
                response = model.generate_content(prompt)
                
                # Đánh dấu thành công
                gemini_key_manager.mark_success()
                
                # 4. Xử lý phản hồi
                if hasattr(response, 'text'):
                    response_text = response.text
                    
                    # Phân tích kết quả ra thành nghiên cứu và nội dung
                    research_data, html_content = self._parse_response(response_text, keyword)
                    
                    if research_data and html_content:
                        # Lưu vào cache
                        cache_data = {
                            'research': research_data,
                            'content': html_content,
                            'timestamp': time.time()
                        }
                        keyword_cache.set(keyword_lower, cache_data)
                        
                        logger.info(f"Đã nghiên cứu và tạo nội dung thành công cho từ khóa: {keyword}")
                        return research_data, html_content
                
                logger.warning("Không nhận được phản hồi hợp lệ")
                    
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Lỗi khi nghiên cứu và tạo nội dung: {error_msg}")
                
                if "429" in error_msg or "quota" in error_msg.lower() or "exhausted" in error_msg.lower():
                    logger.warning(f"Rate limit hoặc hết quota, chuyển sang API key khác")
                    gemini_key_manager.mark_error(f"Rate limit hoặc hết quota: {error_msg}")
                    if gemini_key_manager.current_index in tried_keys and len(tried_keys) < len(gemini_key_manager.keys):
                        gemini_key_manager.next_key()
                else:
                    gemini_key_manager.mark_error(f"Lỗi: {error_msg}")
                
                wait_time = random.uniform(2, 5)
                logger.info(f"Chờ {wait_time:.2f}s trước khi thử lại")
                time.sleep(wait_time)
            
            # In thống kê sử dụng key sau mỗi lần thử
            stats = gemini_key_manager.get_stats()
            logger.info(f"Thống kê sử dụng API key: {stats['active_keys']}/{stats['total_keys']} key hoạt động")
        
        logger.error(f"Đã thử {attempts} lần nhưng không thành công cho từ khóa: {keyword}")
        return {}, None
    
    def _build_prompt(self, keyword: str, existing_research: Dict[str, Any] = None) -> str:
        """
        Xây dựng prompt cho nghiên cứu từ khóa và tạo nội dung
        
        Args:
            keyword: Từ khóa cần xử lý
            existing_research: Dữ liệu nghiên cứu hiện có (nếu có)
            
        Returns:
            str: Prompt hoàn chỉnh
        """
        if existing_research and existing_research:
            # Nếu đã có dữ liệu nghiên cứu, chỉ cần tạo nội dung
            research_json = json.dumps(existing_research, indent=2)
            
            prompt = f"""
            I'll help you create comprehensive content for a WordPress blog post about the keyword "{keyword}".
            
            I already have research data for this keyword, which I'll use to create optimized content:
            ```json
            {research_json}
            ```
            
            Please write a comprehensive, well-researched, and engaging WordPress article based on this research data.
            
            REQUIREMENTS:
            1. Write in English, using clear and professional language
            2. Create SEO-optimized content with proper heading structure (H1, H2, H3)
            3. Include an engaging introduction that explains the topic's importance and demonstrates expertise
            4. Write detailed sections covering all major aspects of the topic
            5. Include practical examples, data points or case studies when relevant
            6. Add a FAQ section with at least 5 questions and detailed answers
            7. Conclude with a summary and call-to-action
            8. Write at least 1500 words of valuable content
            9. Format using Markdown with proper headings, paragraphs, lists and emphasis
            10. Structure content specifically for WordPress (be mindful of how WordPress will render the content)
            
            FORMAT THE ARTICLE IN PROPER MARKDOWN, WITH:
            - # for H1 (main title)
            - ## for H2 (section headings)
            - ### for H3 (subsections)
            - **bold** for emphasis
            - - for bullet points
            - 1. for numbered lists
            
            I need the response in a specific format:
            
            1. FIRST, return "===CONTENT_START===" on a line by itself
            2. THEN, write the article in markdown format
            3. FINALLY, end with "===CONTENT_END===" on a line by itself
            """
        else:
            # Nếu không có dữ liệu nghiên cứu, kết hợp cả hai nhiệm vụ
            prompt = f"""
            I'll help you with two tasks: First, analyze the keyword "{keyword}" for WordPress SEO content, and second, create comprehensive content based on that analysis.
            
            TASK 1: KEYWORD RESEARCH FOR WORDPRESS
            Analyze the keyword "{keyword}" and return detailed information in JSON format, including:
            - topic_type: Type of topic (product, service, information, comparison, etc.)
            - user_intent: Search intent (informational, transactional, navigational)
            - suggested_title: SEO title suggestion (under 60 characters)
            - meta_description: Meta description suggestion (under 160 characters)
            - subtopics: List of 5-7 subtopics to cover
            - related_keywords: List of 5-10 related keywords
            - suggested_headings: Suggested article structure with H1, H2, H3
            - faq_questions: 5-8 common FAQ questions with answers
            - target_audience: Who this content is for
            - wordpress_category_suggestions: 1-3 suggested WordPress categories
            - wordpress_tag_suggestions: 5-10 suggested WordPress tags
            
            TASK 2: WORDPRESS CONTENT CREATION
            After completing the research, write a comprehensive, well-researched, and engaging WordPress article based on that research.
            
            REQUIREMENTS:
            1. Write in English, using clear and professional language
            2. Create SEO-optimized content with proper heading structure (H1, H2, H3)
            3. Include an engaging introduction that explains the topic's importance and demonstrates expertise
            4. Write detailed sections covering all aspects of the topic from the research
            5. Include practical examples, data points or case studies when relevant
            6. Add a FAQ section with at least 5 questions and detailed answers from research
            7. Conclude with a summary and call-to-action
            8. Write at least 1500 words of valuable content
            9. Format using Markdown with proper headings, paragraphs, lists and emphasis
            10. Structure content specifically for WordPress (be mindful of how WordPress will render the content)
            
            FORMAT THE ARTICLE IN PROPER MARKDOWN, WITH:
            - # for H1 (main title)
            - ## for H2 (section headings)
            - ### for H3 (subsections)
            - **bold** for emphasis
            - - for bullet points
            - 1. for numbered lists
            
            I need the response in a specific format:
            
            1. FIRST, return "===RESEARCH_START===" on a line by itself
            2. THEN, return the keyword research in clean JSON format
            3. THEN, return "===RESEARCH_END===" on a line by itself
            4. THEN, return "===CONTENT_START===" on a line by itself
            5. THEN, write the article in markdown format
            6. FINALLY, end with "===CONTENT_END===" on a line by itself
            """
        
        return prompt
    
    def _parse_response(self, response_text: str, keyword: str) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Phân tích phản hồi để tách dữ liệu nghiên cứu và nội dung HTML
        
        Args:
            response_text: Văn bản phản hồi
            keyword: Từ khóa cần xử lý
            
        Returns:
            Tuple[Dict, str]: (Dữ liệu nghiên cứu, Nội dung HTML) hoặc (Dict trống, None) nếu thất bại
        """
        research_data = {}
        html_content = None
        
        try:
            # Trường hợp 1: Có cả nghiên cứu và nội dung
            if "===RESEARCH_START===" in response_text and "===CONTENT_START===" in response_text:
                # Trích xuất phần nghiên cứu
                research_match = re.search(r'===RESEARCH_START===\s*(.*?)\s*===RESEARCH_END===', 
                                        response_text, re.DOTALL)
                
                if research_match:
                    research_json = research_match.group(1).strip()
                    try:
                        research_data = json.loads(research_json)
                    except json.JSONDecodeError:
                        # Thử tìm và trích xuất JSON từ phần nghiên cứu
                        json_match = re.search(r'({[\s\S]*})', research_json)
                        if json_match:
                            try:
                                research_data = json.loads(json_match.group(1))
                            except:
                                logger.error("Không thể phân tích JSON từ nghiên cứu")
                
                # Trích xuất phần nội dung
                content_match = re.search(r'===CONTENT_START===\s*(.*?)\s*===CONTENT_END===', 
                                        response_text, re.DOTALL)
                
                if content_match:
                    content_markdown = content_match.group(1).strip()
                    html_content = self._convert_markdown_to_html(content_markdown, keyword, research_data)
            
            # Trường hợp 2: Chỉ có nội dung
            elif "===CONTENT_START===" in response_text:
                content_match = re.search(r'===CONTENT_START===\s*(.*?)\s*===CONTENT_END===', 
                                        response_text, re.DOTALL)
                
                if content_match:
                    content_markdown = content_match.group(1).strip()
                    # Kiểm tra nếu nội dung đang nằm trong thẻ markdown hoặc code blocks
                    if content_markdown.startswith("```markdown") or content_markdown.startswith("```"):
                        # Tìm vị trí kết thúc dòng đầu tiên
                        first_newline = content_markdown.find("\n")
                        if first_newline > 0:
                            # Loại bỏ dòng đầu tiên chứa ```markdown
                            content_markdown = content_markdown[first_newline+1:]
                        
                        # Loại bỏ dấu đóng ở cuối nếu có
                        if content_markdown.endswith("```"):
                            content_markdown = content_markdown[:-3].strip()
                    
                    html_content = self._convert_markdown_to_html(content_markdown, keyword, research_data)
            
            # Trường hợp 3: Không có cấu trúc rõ ràng, thử xử lý toàn bộ là nội dung
            else:
                # Kiểm tra xem có phải là JSON không
                try:
                    json_data = json.loads(response_text)
                    research_data = json_data
                    # Không có nội dung HTML trong trường hợp này
                except json.JSONDecodeError:
                    # Không phải JSON, xử lý như markdown
                    html_content = self._convert_markdown_to_html(response_text, keyword, research_data)
            
            # Kiểm tra xem đã có đủ dữ liệu chưa
            if html_content is None and research_data:
                logger.warning("Chỉ nhận được dữ liệu nghiên cứu, thiếu nội dung")
            elif html_content and not research_data:
                logger.warning("Chỉ nhận được nội dung, thiếu dữ liệu nghiên cứu")
                # Tạo dữ liệu nghiên cứu cơ bản
                research_data = {
                    "topic_type": "informational",
                    "user_intent": "informational",
                    "suggested_title": f"{keyword.title()}: Complete Guide",
                    "meta_description": f"Learn everything about {keyword} in this comprehensive guide.",
                    "subtopics": [],
                    "related_keywords": [],
                    "suggested_headings": {},
                    "faq_questions": [],
                    "wordpress_category_suggestions": ["General"],
                    "wordpress_tag_suggestions": [keyword]
                }
            
            return research_data, html_content
            
        except Exception as e:
            logger.error(f"Lỗi khi phân tích phản hồi: {e}")
            return {}, None
    
    def _convert_markdown_to_html(self, markdown_text: str, keyword: str, research_data: Dict[str, Any]) -> Optional[str]:
        """
        Chuyển đổi Markdown sang HTML và tối ưu hóa
        
        Args:
            markdown_text: Văn bản Markdown
            keyword: Từ khóa chính
            research_data: Dữ liệu nghiên cứu
            
        Returns:
            str: HTML đã tối ưu hoặc None nếu thất bại
        """
        if not markdown_text:
            return None
        
        try:
            # Loại bỏ các thẻ <pre> và <code> nếu đã có trong nội dung
            if markdown_text.startswith("```") or markdown_text.startswith("~~~"):
                # Tìm điểm kết thúc của dòng đầu tiên và bỏ qua nó
                first_line_end = markdown_text.find("\n")
                if first_line_end > 0:
                    markdown_text = markdown_text[first_line_end+1:]
                    
                # Tìm và loại bỏ dấu đóng code block ở cuối
                if markdown_text.endswith("```") or markdown_text.endswith("~~~"):
                    markdown_text = markdown_text[:-3].strip()
                # Sử dụng extensions để hỗ trợ nhiều tính năng markdown hơn
            try:
                html_content = markdown.markdown(markdown_text, extensions=['extra', 'tables'])
            except:
                # Fallback nếu extensions không khả dụng
                html_content = markdown.markdown(markdown_text)
            
            logger.info("Đã chuyển đổi Markdown sang HTML")
            
            # Tối ưu hóa HTML cho SEO
            enhanced_html = self._enhance_html_for_wordpress(html_content, keyword, research_data)
            
            return enhanced_html
            
        except Exception as e:
            logger.error(f"Lỗi khi chuyển đổi Markdown sang HTML: {e}")
            return None
    
    def _enhance_html_for_wordpress(self, html_content: str, keyword: str, research_data: Dict[str, Any] = None) -> str:
        """
        Tối ưu hóa HTML cho WordPress và SEO
        
        Args:
            html_content: Nội dung HTML
            keyword: Từ khóa chính
            research_data: Dữ liệu nghiên cứu
            
        Returns:
            str: HTML đã tối ưu
        """
        if not html_content:
            return None
        
        logger.info("Đang tối ưu hóa HTML cho WordPress")
        
        try:
            # Phân tích HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            if soup.pre and soup.pre.code and len(soup.find_all()) <= 3:  # Chỉ có vài thẻ, có thể toàn bộ nội dung trong pre>code
                pre_content = soup.pre.extract()
                code_content = pre_content.code.extract()
                # Phân tích lại nội dung từ code
                inner_html = markdown.markdown(code_content.get_text(), extensions=['extra', 'tables'])
                new_soup = BeautifulSoup(inner_html, 'html.parser')
                for tag in new_soup:
                    soup.append(tag)
            # 1. Đảm bảo tiêu đề H1
            h1_tags = soup.find_all('h1')
            if not h1_tags:
                if research_data and 'suggested_title' in research_data:
                    title = research_data['suggested_title']
                else:
                    title = f"{keyword.title()}: Complete Guide and Review"
                    
                # Tạo H1 mới và đặt ở đầu
                h1 = soup.new_tag('h1')
                h1.string = title
                if soup.body:
                    soup.body.insert(0, h1)
                else:
                    soup.insert(0, h1)
            
            # 2. Thêm ID cho các tiêu đề để tạo ToC
            for idx, heading in enumerate(soup.find_all(['h2', 'h3'])):
                if not heading.get('id'):
                    heading_text = heading.get_text().strip()
                    heading_id = re.sub(r'[^\w\s-]', '', heading_text).lower().replace(' ', '-')
                    heading['id'] = f"section-{heading_id}-{idx}"
                    
                # Thêm class WordPress
                heading['class'] = heading.get('class', []) + ['wp-block-heading']
            
            # 3. Thêm Table of Contents nếu có đủ headings
            h2_tags = soup.find_all('h2')
            if len(h2_tags) >= 3:
                toc_html = '<div class="wp-block-table-of-contents"><h3 class="wp-block-heading">Table of Contents</h3><ul>'
                for h2 in h2_tags:
                    h2_id = h2.get('id')
                    h2_text = h2.get_text().strip()
                    if h2_id:
                        toc_html += f'<li><a href="#{h2_id}">{h2_text}</a></li>'
                toc_html += '</ul></div>'
                
                # Chèn ToC sau đoạn đầu tiên
                first_p = soup.find('p')
                if first_p:
                    toc_soup = BeautifulSoup(toc_html, 'html.parser')
                    first_p.insert_after(toc_soup)
            
            # 4. Thêm schema markup cho FAQ nếu có
            faq_heading = None
            for heading in soup.find_all(['h2', 'h3']):
                if 'faq' in heading.get_text().lower() or 'frequently asked questions' in heading.get_text().lower():
                    faq_heading = heading
                    break
            
            if faq_heading:
                # Tạo div cha cho phần FAQ với lớp CSS phù hợp
                faq_div = soup.new_tag('div')
                faq_div['class'] = ['wp-block-faq']
                faq_heading.wrap(faq_div)
                
                # Tìm tất cả câu hỏi và câu trả lời sau faq_heading
                # Giả định H3 là câu hỏi và sau mỗi H3 là đoạn văn với câu trả lời
                current = faq_heading.next_sibling
                
                # Tạo schema JSON-LD cho FAQ
                faq_schema = {
                    "@context": "https://schema.org",
                    "@type": "FAQPage",
                    "mainEntity": []
                }
                
                last_question = None
                answer_parts = []
                
                while current:
                    if isinstance(current, str) and current.strip() == '':
                        current = current.next_sibling
                        continue
                        
                    # Nếu là tiêu đề H2, thoát khỏi vòng lặp
                    if current.name == 'h2':
                        break
                    
                    # Nếu là H3 hoặc strong, xem như là câu hỏi mới
                    if current.name in ['h3', 'strong'] or (current.name == 'p' and current.find('strong')):
                        # Nếu đã có câu hỏi trước đó, hoàn thành và thêm vào schema
                        if last_question and answer_parts:
                            answer_text = ' '.join([p.get_text().strip() for p in answer_parts])
                            faq_schema["mainEntity"].append({
                                "@type": "Question",
                                "name": last_question.get_text().strip(),
                                "acceptedAnswer": {
                                    "@type": "Answer",
                                    "text": answer_text
                                }
                            })
                        
                        # Cập nhật câu hỏi mới
                        if current.name == 'p' and current.find('strong'):
                            last_question = current.find('strong')
                        else:
                            last_question = current
                        answer_parts = []
                        
                        # Thêm vào div FAQ
                        faq_div.append(current)
                    
                    # Nếu là đoạn văn và đã có câu hỏi, xem như là phần câu trả lời
                    elif current.name == 'p' and last_question:
                        answer_parts.append(current)
                        faq_div.append(current)
                    
                    # Nếu là phần tử khác, cũng thêm vào div FAQ
                    else:
                        faq_div.append(current)
                    
                    # Di chuyển đến phần tử tiếp theo
                    next_elem = current.next_sibling
                    current = next_elem
                
                # Xử lý câu hỏi cuối cùng
                if last_question and answer_parts:
                    answer_text = ' '.join([p.get_text().strip() for p in answer_parts])
                    faq_schema["mainEntity"].append({
                        "@type": "Question",
                        "name": last_question.get_text().strip(),
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": answer_text
                        }
                    })
                
                # Thêm schema FAQPage nếu có câu hỏi
                if faq_schema["mainEntity"]:
                    schema_script = soup.new_tag('script')
                    schema_script['type'] = 'application/ld+json'
                    schema_script.string = json.dumps(faq_schema, ensure_ascii=False, indent=2)
                    soup.append(schema_script)
                    
                    logger.info(f"Đã thêm FAQ Schema với {len(faq_schema['mainEntity'])} câu hỏi")
            
            # 5. Thêm các lớp WordPress cho các phần tử
            # a. Đoạn văn
            for p in soup.find_all('p'):
                p['class'] = p.get('class', []) + ['wp-block-paragraph']
            
            # b. Danh sách
            for ul in soup.find_all('ul'):
                ul['class'] = ul.get('class', []) + ['wp-block-list']
            
            for ol in soup.find_all('ol'):
                ol['class'] = ol.get('class', []) + ['wp-block-list']
            
            # 6. Thêm phần kết luận rõ ràng nếu chưa có
            conclusion_headings = soup.find_all(string=re.compile(r'Conclusion|Summary|Final Thoughts', re.IGNORECASE))
            if not conclusion_headings:
                last_h2 = soup.find_all('h2')[-1] if soup.find_all('h2') else None
                if last_h2 and not re.search(r'Conclusion|Summary|Final', last_h2.get_text(), re.IGNORECASE):
                    conclusion_h2 = soup.new_tag('h2')
                    conclusion_h2['class'] = ['wp-block-heading']
                    conclusion_h2.string = "Conclusion"
                    conclusion_h2['id'] = 'section-conclusion'
                    
                    conclusion_p = soup.new_tag('p')
                    conclusion_p['class'] = ['wp-block-paragraph']
                    conclusion_p.string = f"In conclusion, understanding {keyword} is essential for making informed decisions. This guide has covered the key aspects you need to know. If you have any questions, feel free to leave them in the comments below."
                    
                    # Thêm vào cuối
                    soup.append(conclusion_h2)
                    soup.append(conclusion_p)
            
            # 7. Lưu schema Article
            # Tạo schema cho Article
            article_schema = {
                "@context": "https://schema.org",
                "@type": "Article",
                "headline": soup.find('h1').get_text() if soup.find('h1') else f"{keyword}: Complete Guide",
                "description": research_data.get('meta_description', f"Learn everything about {keyword} in this comprehensive guide.") if research_data else f"Complete guide about {keyword}",
                "author": {
                    "@type": "Person",
                    "name": "Expert Author"
                },
                "publisher": {
                    "@type": "Organization",
                    "name": "Website Name",
                    "logo": {
                        "@type": "ImageObject",
                        "url": "https://example.com/logo.png"
                    }
                },
                "datePublished": time.strftime("%Y-%m-%d"),
                "dateModified": time.strftime("%Y-%m-%d")
            }
            
            # Thêm schema Article
            schema_script = soup.new_tag('script')
            schema_script['type'] = 'application/ld+json'
            schema_script.string = json.dumps(article_schema, ensure_ascii=False, indent=2)
            soup.insert(0, schema_script)
            
            logger.info("Đã tối ưu hóa HTML cho WordPress thành công")
            return str(soup)
            
        except Exception as e:
            logger.error(f"Lỗi khi tối ưu hóa HTML: {e}")
            return html_content  # Trả về nội dung gốc nếu có lỗi
    
    def build_complete_html(self, keyword: str, html_content: str, video_embed_url: Optional[str] = None, 
                          image_urls: Optional[List[str]] = None) -> str:
        """
        Xây dựng HTML hoàn chỉnh với hình ảnh và video
        
        Args:
            keyword: Từ khóa chính
            html_content: Nội dung HTML cơ bản
            video_embed_url: URL nhúng video (tùy chọn)
            image_urls: Danh sách URL hình ảnh (tùy chọn)
            
        Returns:
            str: HTML hoàn chỉnh
        """
        logger.info("Đang xây dựng HTML hoàn chỉnh cho bài viết")
        
        if not html_content:
            logger.error("Không có nội dung HTML để xây dựng bài viết hoàn chỉnh")
            return None
        
        try:
            # Phân tích HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Tìm tất cả tiêu đề và đoạn văn trong HTML
            headers = soup.find_all(['h2', 'h3'])
            paragraphs = soup.find_all('p')
            
            # 1. Thêm hình ảnh thumbnail vào đầu bài viết nếu có
            if image_urls and len(image_urls) > 0:
                logger.info("Đang thêm hình ảnh thumbnail vào đầu bài viết")
                
                # Tạo WordPress figure block
                figure_div = soup.new_tag('figure')
                figure_div['class'] = ['wp-block-image', 'size-large', 'is-style-default']
                
                img = soup.new_tag('img')
                img['src'] = image_urls[0]
                img['alt'] = f"{keyword} - Featured Image"
                img['class'] = ['wp-image-featured']
                img['loading'] = 'lazy'
                
                # Thêm figcaption
                figcaption = soup.new_tag('figcaption')
                figcaption['class'] = ['wp-element-caption']
                figcaption.string = f"{keyword}"
                
                # Tổng hợp
                figure_div.append(img)
                figure_div.append(figcaption)
                
                # Tìm h1 và chèn sau nó
                h1 = soup.find('h1')
                if h1:
                    h1.insert_after(figure_div)
                else:
                    # Hoặc thêm vào đầu
                    first_elem = next((c for c in soup.children if c.name is not None), None)
                    if first_elem:
                        first_elem.insert_before(figure_div)
                    else:
                        soup.append(figure_div)
            
            # 2. Thêm video YouTube sau đoạn văn đầu tiên
            if video_embed_url:
                logger.info("Đang thêm video vào bài viết")
                
                # Tạo WordPress figure block cho video nhúng
                video_div = soup.new_tag('figure')
                video_div['class'] = ['wp-block-embed', 'is-type-video', 'is-provider-youtube', 'wp-block-embed-youtube']
                
                # Tạo wrapper div
                wrapper_div = soup.new_tag('div')
                wrapper_div['class'] = ['wp-block-embed__wrapper']
                
                # Tạo iframe
                iframe = soup.new_tag('iframe')
                iframe['src'] = video_embed_url
                iframe['width'] = '560'
                iframe['height'] = '315'
                iframe['frameborder'] = '0'
                iframe['allowfullscreen'] = True
                iframe['title'] = f"{keyword} video"
                
                # Tổng hợp các phần tử
                wrapper_div.append(iframe)
                video_div.append(wrapper_div)
                
                # Chèn sau đoạn văn đầu tiên nếu có
                if paragraphs:
                    paragraphs[0].insert_after(video_div)
                else:
                    # Hoặc sau ảnh thumbnail
                    first_figure = soup.find('figure', class_='wp-block-image')
                    if first_figure:
                        first_figure.insert_after(video_div)
                    else:
                        # Hoặc sau H1
                        h1 = soup.find('h1')
                        if h1:
                            h1.insert_after(video_div)
            
            # 3. Thêm hình ảnh vào các tiêu đề và đoạn văn
            if image_urls and len(image_urls) > 1:
                logger.info("Đang thêm hình ảnh bổ sung vào bài viết")
                
                # Số lượng hình ảnh còn lại
                remaining_images = image_urls[1:]
                
                # Xen kẽ giữa các tiêu đề hoặc đoạn văn
                insertion_points = headers if headers else paragraphs[1:] if len(paragraphs) > 1 else []
                
                # Chọn ngẫu nhiên 50% các điểm chèn để thêm ảnh
                if insertion_points and remaining_images:
                    # Chọn số lượng điểm chèn không quá số ảnh còn lại
                    num_points = min(len(remaining_images), len(insertion_points))
                    selected_points = random.sample(insertion_points, num_points)
                    
                    for i, point in enumerate(selected_points):
                        if i < len(remaining_images):
                            # Tạo WordPress figure block
                            figure_div = soup.new_tag('figure')
                            figure_div['class'] = ['wp-block-image', 'size-large']
                            
                            img = soup.new_tag('img')
                            img['src'] = remaining_images[i]
                            img['alt'] = f"{keyword} - {i+1}"
                            img['class'] = ['wp-image-content']
                            img['loading'] = 'lazy'
                            
                            # Thêm figcaption
                            figcaption = soup.new_tag('figcaption')
                            figcaption['class'] = ['wp-element-caption']
                            figcaption.string = f"{keyword} - {i+1}"
                            
                            # Tổng hợp
                            figure_div.append(img)
                            figure_div.append(figcaption)
                            
                            # Chèn sau điểm chèn
                            point.insert_after(figure_div)
            
            logger.info("Đã xây dựng xong HTML hoàn chỉnh cho bài viết")
            return str(soup)
            
        except Exception as e:
            logger.error(f"Lỗi khi xây dựng HTML hoàn chỉnh: {e}")
            return html_content  # Trả về nội dung gốc nếu có lỗi

# Tạo instance toàn cục
content_generator = ContentGenerator()