"""
Python 代码执行模块
自动执行 AI 生成的 Python 画图代码
"""

import os
import sys
import subprocess
import tempfile
import re
from typing import Tuple, List, Optional


class PythonExecutor:
    """Python 代码执行器"""
    
    def __init__(self, work_dir: str):
        """
        初始化执行器
        
        Args:
            work_dir: 工作目录（图片将保存在此目录的 Fig 子目录）
        """
        self.work_dir = work_dir
        self.fig_dir = os.path.join(work_dir, 'Fig')
        os.makedirs(self.fig_dir, exist_ok=True)
    
    def execute_plotting_code(self, code: str, data_code: str = None) -> Tuple[bool, str, List[str]]:
        """
        执行画图代码
        
        Args:
            code: Python 画图代码
            data_code: 数据定义代码（可选，如 transcribed_data.py 的内容）
            
        Returns:
            (成功标志, 消息, 生成的图片文件列表)
        """
        # 预处理代码
        processed_code = self._preprocess_code(code, data_code)
        
        # 写入临时文件
        script_path = os.path.join(self.work_dir, 'plot_script.py')
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(processed_code)
        
        try:
            # 执行脚本
            result = subprocess.run(
                [sys.executable, script_path],
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                timeout=60,
                encoding='utf-8',
                errors='replace'
            )
            
            # 检查生成的图片
            generated_images = self._find_generated_images()
            
            if result.returncode == 0:
                return True, f"代码执行成功，生成了 {len(generated_images)} 张图片", generated_images
            else:
                error_msg = result.stderr or result.stdout or "未知错误"
                return False, f"代码执行失败: {error_msg[:500]}", generated_images
                
        except subprocess.TimeoutExpired:
            return False, "代码执行超时（60秒）", []
        except Exception as e:
            return False, f"执行错误: {str(e)}", []
    
    def _preprocess_code(self, code: str, data_code: str = None) -> str:
        """预处理代码，设置保存路径等"""
        
        # 添加导入和配置
        header = f'''# Auto-generated plotting script
import os
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
from matplotlib import font_manager
from scipy.optimize import curve_fit

# 尝试加载当前目录下的字体文件
work_dir = r"{self.work_dir}"
for f in os.listdir(work_dir):
    if f.lower().endswith('.ttf'):
        try:
            font_path = os.path.join(work_dir, f)
            font_manager.fontManager.addfont(font_path)
            # print(f"Registered font: {{f}}")
        except:
            pass

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'SimSun', 'Songti', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 12

# 输出目录
save_dir = r"{self.fig_dir}"
os.makedirs(save_dir, exist_ok=True)

'''
        
        # 如果有数据代码，添加到开头
        if data_code:
            header += f"# === 数据定义 ===\n{data_code}\n\n# === 画图代码 ===\n"
        
        # 处理代码中的保存路径
        processed = code
        
        # 替换 plt.show() 为空（我们不需要显示）
        processed = re.sub(r'plt\.show\(\)', '# plt.show()  # Disabled', processed)
        
        # 确保 savefig 使用正确的路径
        # 如果代码中有相对路径的 savefig，替换为绝对路径
        def replace_savefig(match):
            original = match.group(0)
            path_match = re.search(r"savefig\(['\"]([^'\"]+)['\"]", original)
            if path_match:
                old_path = path_match.group(1)
                filename = os.path.basename(old_path)
                new_path = os.path.join(self.fig_dir, filename).replace('\\', '/')
                return original.replace(old_path, new_path)
            return original
        
        processed = re.sub(r'plt\.savefig\([^)]+\)', replace_savefig, processed)
        processed = re.sub(r'savefig\([^)]+\)', replace_savefig, processed)
        
        return header + processed
    
    def _find_generated_images(self) -> List[str]:
        """查找生成的图片文件"""
        images = []
        if os.path.exists(self.fig_dir):
            for f in os.listdir(self.fig_dir):
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf', '.svg')):
                    images.append(os.path.join(self.fig_dir, f))
        return sorted(images)


def extract_python_code_from_ai_response(response: str) -> Tuple[Optional[str], Optional[str]]:
    """
    从 AI 响应中提取 Python 代码
    
    Args:
        response: AI 的完整响应
        
    Returns:
        (数据代码, 画图代码) 或 (None, None)
    """
    if not response:
        return None, None

    # 1. 查找所有 Python 代码块
    code_blocks = re.findall(r'```(?:python)?\n(.*?)```', response, re.DOTALL | re.IGNORECASE)
    
    # 2. 如果没找到带反引号的，检查是否全是代码（比如后端已经清理过但没提取好的情况）
    if not code_blocks:
        # 如果包含明显的 python 绘图特征且没有反引号，尝试作为单一块处理
        if 'import matplotlib' in response or 'plt.' in response:
            # 移除可能存在的 "python" 单词头
            clean_response = re.sub(r'^python\s*\n', '', response.strip(), flags=re.IGNORECASE)
            code_blocks = [clean_response]
            
    if not code_blocks:
        return None, None
    
    # 分类代码块
    data_code_list = []
    plot_code_list = []
    
    for code in code_blocks:
        # 检查是否是数据定义 (包含数组定义)
        if 'np.array' in code or 'data =' in code or 'data_' in code:
            if 'plt.' not in code or code.count('np.array') > 1:
                data_code_list.append(code)
        
        # 检查是否是画图代码
        if 'plt.' in code or 'matplotlib' in code:
            plot_code_list.append(code)
    
    # 合并代码块
    data_code = '\n\n'.join(data_code_list) if data_code_list else None
    plot_code = '\n\n'.join(plot_code_list) if plot_code_list else None
             
    return data_code, plot_code


def generate_figure_latex(image_paths: List[str], work_dir: str) -> str:
    """
    生成图片的 LaTeX 代码
    
    Args:
        image_paths: 图片路径列表
        work_dir: 工作目录
        
    Returns:
        LaTeX 代码
    """
    latex_parts = []
    
    for i, img_path in enumerate(image_paths):
        # 使用相对路径
        rel_path = os.path.relpath(img_path, work_dir).replace('\\', '/')
        filename = os.path.splitext(os.path.basename(img_path))[0]
        
        # 生成标题
        title = filename.replace('_', ' ').title()
        
        latex_parts.append(f"""\\begin{{figure}}[H]
    \\centering
    \\includegraphics[width=0.8\\textwidth]{{{rel_path}}}
    \\caption{{{title}}}
\\end{{figure}}
""")
    
    return '\n'.join(latex_parts)
