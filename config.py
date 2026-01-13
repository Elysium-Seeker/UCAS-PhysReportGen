import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 目录配置
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'output')
TEMPLATE_FOLDER = os.path.join(BASE_DIR, 'latex_template')
FONTS_FOLDER = os.path.join(TEMPLATE_FOLDER, 'fonts')

# 允许的文件类型
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# LaTeX 编译配置
XELATEX_PATH = 'xelatex'  # 假设在 PATH 中，否则指定完整路径
COMPILE_TIMEOUT = 120  # 编译超时时间（秒）

# AI 配置（预留）
AI_API_URL = os.getenv('AI_API_URL', '')
AI_API_KEY = os.getenv('AI_API_KEY', '')
AI_MODEL = os.getenv('AI_MODEL', 'gpt-4')

# Flask 配置
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB 最大上传大小

# 学生默认信息 (请根据实际情况修改)
DEFAULT_STUDENT_INFO = {
    'name': '张三',
    'student_id': '202XXXXXXXX',
    'class_num': '1',
    'group_num': '01',
    'seat_num': '1'
}
