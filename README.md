# WordPress Auto Content Generator

Hệ thống tự động tạo nội dung chất lượng cao và đăng lên WordPress, tối ưu cho SEO.

## Tính năng

- **Tạo nội dung thông minh** sử dụng Gemini AI
- **Nghiên cứu từ khóa** tự động để tìm hiểu về chủ đề
- **Tối ưu hoá SEO** với slug, categories, tags, meta description
- **Tìm kiếm hình ảnh** chất lượng cao liên quan đến từ khoá
- **Tìm kiếm video YouTube** để bổ sung cho bài viết
- **Tích hợp Schema Markup** (Article, FAQPage) cho SEO nâng cao
- **Xử lý thông minh** các trường hợp lỗi và auto-retry
- **Hệ thống cache** để tiết kiệm API call và nâng cao hiệu suất

## Yêu cầu hệ thống

- Python 3.7+
- Chrome Browser (cho Selenium)
- WordPress website với REST API được bật
- Gemini API key
- WordPress Application Password

## Cài đặt

### 1. Clone repository

```bash
git clone https://github.com/yourusername/wp-auto-content.git
cd wp-auto-content
```

### 2. Tạo môi trường ảo (khuyến nghị)

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 3. Cài đặt các thư viện phụ thuộc

```bash
pip install -r requirements.txt
```

### 4. Cấu hình

Sao chép file `.env.example` thành `.env` và chỉnh sửa:

```bash
cp .env.example .env
```

Mở `.env` và cấu hình các thông tin cần thiết:

```
# WordPress Configuration
WP_URL=https://example.com
WP_USERNAME=your_username
WP_APP_PASSWORD=your_app_password
```

### 5. Chuẩn bị từ khóa

Tạo file `data/keywords/myfile.txt` với danh sách từ khóa, mỗi từ khóa một dòng.

## Sử dụng

### Kiểm tra kết nối

```bash
python main.py --check
```

### Tạo bài viết từ một từ khóa

```bash
python main.py --keyword "từ khóa của bạn"
```

### Tạo nhiều bài viết từ file

```bash
python main.py --file path/to/keywords.txt --max 5
```

### Tạo bài viết từ thư mục mặc định

```bash
python main.py --max 10 --random
```

## Tham số dòng lệnh

- `--keyword "từ khóa"`: Chỉ xử lý một từ khóa cụ thể
- `--file path/to/file.txt`: Đường dẫn đến file từ khóa
- `--max N`: Giới hạn số lượng từ khóa cần xử lý
- `--random`: Xáo trộn ngẫu nhiên thứ tự từ khóa
- `--check`: Chỉ kiểm tra kết nối và thoát
- `--clean-cache`: Dọn dẹp cache trước khi bắt đầu

## Cấu trúc thư mục

```
wp-auto-content/
│
├── config.py                  # Cấu hình tổng thể
├── main.py                    # Điểm vào chính
├── requirements.txt           # Phụ thuộc
│
├── core/                      # Module cốt lõi
│   ├── wordpress_api.py       # Tương tác với WordPress REST API
│   ├── content_generator.py   # Tạo nội dung bằng Gemini AI
│   ├── seo_manager.py         # Quản lý SEO (categories, tags, slug)
│   ├── image_finder.py        # Tìm kiếm hình ảnh
│   ├── video_finder.py        # Tìm kiếm video
│   └── wp_creator.py          # Quản lý quy trình tạo nội dung
│
├── utils/                     # Tiện ích
│   ├── cache_manager.py       # Quản lý cache
│   ├── logger.py              # Hệ thống logging
│   ├── rate_limiter.py        # Kiểm soát tốc độ API
│   └── api_key_manager.py     # Quản lý API key
│
└── data/                      # Dữ liệu
    ├── cache/                 # Cache
    ├── keywords/              # Thư mục từ khóa
    └── logs/                  # Log
```

## Đăng ký Application Password trong WordPress

1. Đăng nhập vào trang quản trị WordPress
2. Vào Users > Profile
3. Cuộn xuống phần "Application Passwords"
4. Nhập tên (ví dụ: "Auto Content Generator")
5. Click "Add New Application Password"
6. Sao chép mật khẩu được tạo và đặt vào biến `WP_APP_PASSWORD` trong `.env`

## Câu hỏi thường gặp

### Tôi không thấy hình ảnh trong bài viết?

Kiểm tra:
- File `core/image_finder.py` đang hoạt động đúng
- WebDriver của Selenium đã được cài đặt
- WordPress có quyền upload media

### Có thể chạy nhiều bài cùng lúc?

Không nên chạy nhiều instance cùng lúc vì có thể gây quá tải API và dẫn đến lỗi. Thay vào đó, hãy sử dụng tham số `--max` để giới hạn số lượng bài viết trong một lần chạy.

### Tôi gặp lỗi "Rate limit exceeded" với Gemini API?

Thêm nhiều API key hơn trong file `.env` (GEMINI_API_KEY1, GEMINI_API_KEY2, etc.) và giảm `GEMINI_RATE_LIMIT` xuống thấp hơn.

## License

MIT License

3. Yếu Tố Bổ Sung

Xây dựng backlinks: Liên kết từ các trang web uy tín vẫn cực kỳ quan trọng
Core Web Vitals: Đảm bảo trang web nhanh và thân thiện với người dùng
Tạo liên kết nội bộ giữa các bài viết để tăng thời gian đọc
Mobile-first: Đảm bảo trang web hoạt động tốt trên thiết bị di động