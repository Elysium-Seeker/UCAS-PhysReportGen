"""
PDF 文本提取模块
从实验指导书 PDF 中提取文字内容
"""

import os
from typing import Optional

try:
    from PyPDF2 import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


def extract_text_from_pdf(pdf_path: str, max_pages: int = 20) -> Optional[str]:
    """
    从 PDF 文件中提取文本
    
    Args:
        pdf_path: PDF 文件路径
        max_pages: 最大提取页数
        
    Returns:
        提取的文本内容，失败返回 None
    """
    if not PDF_AVAILABLE:
        print("PyPDF2 未安装，无法提取 PDF 文本")
        return None
    
    if not os.path.exists(pdf_path):
        print(f"PDF 文件不存在: {pdf_path}")
        return None
    
    try:
        reader = PdfReader(pdf_path)
        text_parts = []
        
        # 限制页数
        pages_to_read = min(len(reader.pages), max_pages)
        
        for i in range(pages_to_read):
            page = reader.pages[i]
            text = page.extract_text()
            if text:
                text_parts.append(f"=== 第 {i+1} 页 ===\n{text}")
        
        if text_parts:
            return "\n\n".join(text_parts)
        else:
            return None
            
    except Exception as e:
        print(f"PDF 提取失败: {e}")
        return None


def extract_guide_content(pdf_path: str) -> dict:
    """
    从实验指导书中提取结构化内容
    
    Args:
        pdf_path: 实验指导书 PDF 路径
        
    Returns:
        包含各部分内容的字典
    """
    text = extract_text_from_pdf(pdf_path)
    
    if not text:
        return {}
    
    result = {
        'full_text': text,
        'experiment_purpose': '',
        'equipment': '',
        'principle': '',
        'steps': '',
        'notes': ''
    }
    
    # 尝试识别各部分（基于常见标题）
    sections = {
        'experiment_purpose': ['实验目的', '一、实验目的', '1.实验目的', '1、实验目的'],
        'equipment': ['实验仪器', '实验器材', '仪器设备', '二、实验仪器', '2.实验仪器'],
        'principle': ['实验原理', '三、实验原理', '3.实验原理', '原理简介'],
        'steps': ['实验步骤', '实验内容', '操作步骤', '四、实验步骤', '4.实验步骤'],
        'notes': ['注意事项', '思考题', '要求', '预习要求']
    }
    
    # 简单的段落分割
    lines = text.split('\n')
    current_section = None
    current_content = []
    
    for line in lines:
        line_stripped = line.strip()
        
        # 检查是否是新的章节标题
        found_section = None
        for section_key, titles in sections.items():
            for title in titles:
                if title in line_stripped and len(line_stripped) < 50:
                    found_section = section_key
                    break
            if found_section:
                break
        
        if found_section:
            # 保存前一个章节的内容
            if current_section and current_content:
                result[current_section] = '\n'.join(current_content).strip()
            current_section = found_section
            current_content = []
        elif current_section:
            current_content.append(line)
    
    # 保存最后一个章节
    if current_section and current_content:
        result[current_section] = '\n'.join(current_content).strip()
    
    return result
