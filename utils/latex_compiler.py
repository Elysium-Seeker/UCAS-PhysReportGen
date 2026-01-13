"""
LaTeX 编译器模块
使用 XeLaTeX 编译 .tex 文件生成 PDF
"""

import os
import subprocess
import shutil
import tempfile
from typing import Tuple, Optional


class LaTeXCompiler:
    """LaTeX 编译器类"""
    
    def __init__(self, xelatex_path: str = 'xelatex', timeout: int = 120):
        """
        初始化编译器
        
        Args:
            xelatex_path: XeLaTeX 可执行文件路径
            timeout: 编译超时时间（秒）
        """
        self.xelatex_path = xelatex_path
        self.timeout = timeout
    
    def compile(self, tex_file: str, output_dir: str, fonts_dir: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        """
        编译 LaTeX 文件
        
        Args:
            tex_file: .tex 文件路径
            output_dir: 输出目录
            fonts_dir: 字体目录（可选）
            
        Returns:
            (成功标志, 消息, PDF路径)
        """
        if not os.path.exists(tex_file):
            return False, f"文件不存在: {tex_file}", None
        
        # 获取文件名
        tex_dir = os.path.dirname(tex_file)
        tex_basename = os.path.basename(tex_file)
        tex_name = os.path.splitext(tex_basename)[0]
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 如果有字体目录，复制字体到 tex 文件目录
        if fonts_dir and os.path.exists(fonts_dir):
            for font_file in os.listdir(fonts_dir):
                if font_file.endswith('.ttf'):
                    src = os.path.join(fonts_dir, font_file)
                    dst = os.path.join(tex_dir, font_file)
                    if not os.path.exists(dst):
                        shutil.copy2(src, dst)
        
        # 编译命令
        cmd = [
            self.xelatex_path,
            '-interaction=nonstopmode',
            '-output-directory=' + tex_dir,
            tex_basename
        ]
        
        try:
            # 运行两次以解决引用问题
            for i in range(2):
                result = subprocess.run(
                    cmd,
                    cwd=tex_dir,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    encoding='utf-8',
                    errors='replace'
                )
            
            # 检查 PDF 是否生成
            pdf_path = os.path.join(tex_dir, f"{tex_name}.pdf")
            if os.path.exists(pdf_path):
                # 移动到输出目录
                final_pdf = os.path.join(output_dir, f"{tex_name}.pdf")
                
                # 只有当路径不同时才复制
                if os.path.abspath(pdf_path).lower() != os.path.abspath(final_pdf).lower():
                    try:
                        shutil.copy2(pdf_path, final_pdf)
                    except PermissionError:
                        return False, "无法写入 PDF 文件，请检查文件是否被打开（如 PDF 阅读器）", None
                    except OSError as e:
                        if hasattr(e, 'winerror') and e.winerror == 32:
                             return False, "PDF 文件正被占用，请关闭相关的阅读器程序后重试", None
                        return False, f"复制 PDF 失败: {str(e)}", None
                
                return True, "编译成功", final_pdf
            else:
                # 提取错误信息
                log_file = os.path.join(tex_dir, f"{tex_name}.log")
                error_msg = self._extract_errors(log_file)
                return False, f"编译失败: {error_msg}", None
                
        except subprocess.TimeoutExpired:
            return False, f"编译超时（{self.timeout}秒）", None
        except FileNotFoundError:
            return False, f"找不到 XeLaTeX: {self.xelatex_path}，请确保已安装 TeX Live 或 MikTeX", None
        except Exception as e:
            msg = str(e)
            if "WinError 32" in msg:
                return False, "编译错误: 文件正被占用，请关闭 PDF 阅读器后重试", None
            return False, f"编译错误: {msg}", None
    
    def _extract_errors(self, log_file: str) -> str:
        """从日志文件中提取错误信息"""
        if not os.path.exists(log_file):
            return "无法读取日志文件"
        
        errors = []
        try:
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
                for i, line in enumerate(lines):
                    if line.startswith('!') or 'Error' in line:
                        # 获取错误及其上下文
                        start = max(0, i - 1)
                        end = min(len(lines), i + 3)
                        errors.extend(lines[start:end])
                        if len(errors) > 20:  # 限制错误信息长度
                            break
        except:
            return "无法解析日志文件"
        
        if errors:
            return '\n'.join(errors[:20])
        return "未知错误，请检查 LaTeX 代码"
    
    def check_installation(self) -> Tuple[bool, str]:
        """检查 XeLaTeX 是否已安装"""
        try:
            result = subprocess.run(
                [self.xelatex_path, '--version'],
                capture_output=True,
                text=True,
                timeout=10,
                encoding='utf-8',
                errors='replace'
            )
            if result.returncode == 0 and result.stdout:
                version = result.stdout.split('\n')[0]
                return True, f"XeLaTeX 已安装: {version}"
            return False, "XeLaTeX 返回错误"
        except FileNotFoundError:
            return False, f"找不到 XeLaTeX: {self.xelatex_path}"
        except Exception as e:
            return False, f"检查失败: {str(e)}"


# 单例实例
compiler = LaTeXCompiler()


def compile_latex(tex_file: str, output_dir: str, fonts_dir: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
    """便捷函数：编译 LaTeX 文件"""
    return compiler.compile(tex_file, output_dir, fonts_dir)
