"""
LaTeX 模板处理器
处理变量替换和内容填充
"""

import os
import re
from typing import Dict, Any, Optional
from datetime import datetime


class TemplateProcessor:
    """LaTeX 模板处理器"""
    
    # 模板变量映射
    VARIABLE_MAP = {
        'experiment_name': 'experiName',
        'supervisor': 'supervisor',
        'name': 'name',
        'student_id': 'studentNum',
        'class_num': 'class',
        'group_num': 'group',
        'seat_num': 'seat',
        'year': 'dateYear',
        'month': 'dateMonth',
        'day': 'dateDay',
        'room': 'room',
        'is_makeup': 'others'
    }
    
    def __init__(self, template_path: str):
        """
        初始化处理器
        
        Args:
            template_path: 模板文件路径
        """
        self.template_path = template_path
        self.template_content = None
        self._load_template()
    
    def _load_template(self):
        """加载模板文件"""
        if os.path.exists(self.template_path):
            with open(self.template_path, 'r', encoding='utf-8') as f:
                self.template_content = f.read()
    
    def process(self, data: Dict[str, Any]) -> str:
        """
        处理模板，替换变量
        
        Args:
            data: 变量数据字典
            
        Returns:
            处理后的 LaTeX 内容
        """
        if not self.template_content:
            raise ValueError("模板未加载")
        
        content = self.template_content
        
        # 替换 LaTeX newcommand 定义
        for key, latex_var in self.VARIABLE_MAP.items():
            if key in data:
                value = str(data[key])
                # 转义 LaTeX 特殊字符（除非是已转义的LaTeX命令）
                if not value.startswith('$') and not value.startswith('\\'):
                    value = self._escape_latex(value)
                # 转义 replacement 中的反斜杠，避免 regex 错误
                value_escaped = value.replace('\\', '\\\\')
                # 替换 \newcommand{\varName}{...}
                pattern = rf'(\\newcommand{{\\{latex_var}}}{{)[^}}]*(}})'
                content = re.sub(pattern, rf'\g<1>{value_escaped}\g<2>', content)
        
        # 替换内容区块
        if 'sections' in data:
            content = self._replace_sections(content, data['sections'])
        
        return content
    
    def _escape_latex(self, text: str) -> str:
        """转义 LaTeX 特殊字符"""
        # 不转义已经是 LaTeX 命令的内容
        if text.startswith('$') or text.startswith('\\'):
            return text
        
        # 转义特殊字符
        replacements = {
            '&': r'\&',
            '%': r'\%',
            '#': r'\#',
            '_': r'\_',
        }
        
        for char, escaped in replacements.items():
            # 避免重复转义
            if escaped not in text:
                text = text.replace(char, escaped)
        
        return text
    
    def _replace_sections(self, content: str, sections: Dict[str, str]) -> str:
        """替换内容区块"""
        # 区块标记格式: % BEGIN:section_name ... % END:section_name
        for section_name, section_content in sections.items():
            pattern = rf'(% BEGIN:{section_name})(.*?)(% END:{section_name})'
            replacement = rf'\g<1>\n{section_content}\n\g<3>'
            content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        return content
    
    def generate_report(self, 
                       student_info: Dict[str, str],
                       experiment_info: Dict[str, str],
                       content_sections: Dict[str, str],
                       image_paths: Dict[str, list] = None) -> str:
        """
        生成完整报告
        
        Args:
            student_info: 学生信息 (name, student_id, class_num, group_num, seat_num)
            experiment_info: 实验信息 (experiment_name, supervisor, date, room)
            content_sections: 内容区块 (purpose, equipment, principle, steps, results, questions, summary)
            image_paths: 图片路径 (data_sheets, preview_report)
            
        Returns:
            完整的 LaTeX 内容
        """
        # 合并数据
        data = {}
        data.update(student_info)
        data.update(experiment_info)
        
        # 处理日期
        if 'date' in experiment_info:
            date_str = experiment_info['date']
            try:
                # 尝试解析日期
                if '-' in date_str:
                    parts = date_str.split('-')
                    data['year'] = parts[0]
                    data['month'] = parts[1]
                    data['day'] = parts[2]
                elif '/' in date_str:
                    parts = date_str.split('/')
                    data['year'] = parts[0]
                    data['month'] = parts[1]
                    data['day'] = parts[2]
            except:
                # 使用当前日期
                now = datetime.now()
                data['year'] = str(now.year)
                data['month'] = str(now.month)
                data['day'] = str(now.day)
        
        # 处理补课标记
        data['is_makeup'] = '$\\square$\\hspace{-1em}$\\surd$' if experiment_info.get('is_makeup') else '$\\square$'
        
        # 处理内容区块
        data['sections'] = content_sections
        
        return self.process(data)


def create_report_from_template(template_path: str, 
                                output_path: str,
                                student_info: Dict[str, str],
                                experiment_info: Dict[str, str],
                                content_sections: Dict[str, str]) -> bool:
    """
    从模板创建报告文件
    
    Args:
        template_path: 模板路径
        output_path: 输出路径
        student_info: 学生信息
        experiment_info: 实验信息
        content_sections: 内容区块
        
    Returns:
        是否成功
    """
    try:
        processor = TemplateProcessor(template_path)
        content = processor.generate_report(student_info, experiment_info, content_sections)
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True
    except Exception as e:
        print(f"创建报告失败: {e}")
        return False
