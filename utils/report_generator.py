"""
AI 报告生成器模块
支持多种 AI 后端（OpenAI API、本地 Ollama 等）
"""

import os
import json
import base64
import requests
import io
from PIL import Image
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod


def resize_image_for_api(image_path, max_size=1024):
    """
    调整图片大小以适应 API 限制并提高速度
    """
    try:
        with Image.open(image_path) as img:
            # 转换为 RGB (防止 RGBA 问题)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            width, height = img.size
            if width > max_size or height > max_size:
                ratio = min(max_size / width, max_size / height)
                new_size = (int(width * ratio), int(height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # 转为 JPEG 字节流
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            return buffer.getvalue()
    except Exception as e:
        print(f"图片处理出错: {e}, 将使用原始图片")
        with open(image_path, "rb") as f:
            return f.read()


class AIBackend(ABC):
    """AI 后端抽象基类"""
    
    @staticmethod
    def clean_content(content: str) -> str:
        """统一清理 AI 生成的内容，移除 Markdown 代码块和冗余文字"""
        if not content:
            return ""
            
        # 1. 尝试直接提取 ```latex ... ``` 之间的内容
        import re
        code_block_match = re.search(r'```(?:latex)?\s*(.*?)\s*```', content, re.DOTALL | re.IGNORECASE)
        if code_block_match:
            content = code_block_match.group(1)
        else:
            # 2. 如果没找到代码块，则通过行过滤掉 ``` 标记
            lines = content.split('\n')
            clean_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('```'):
                    continue
                clean_lines.append(line)
            content = '\n'.join(clean_lines)
        
        # 3. 移除常见的前言废话 (如 "好的，这是生成的...")
        # 如果第一行不是 \section, \subsection, \item 等 LaTeX 命令，尝试寻找第一个 LaTeX 命令的位置
        content = content.strip()
        first_slash = content.find('\\')
        if first_slash > 0 and first_slash < 200: # 如果前面有不到 200 字的废话
            # 检查废话里是否包含中文字符，如果包含且没有反斜杠，很有可能是前言
            prefix = content[:first_slash]
            if any('\u4e00' <= char <= '\u9fff' for char in prefix):
                content = content[first_slash:]
        
        return content.strip()


class OpenAIBackend(AIBackend):
    """OpenAI API 后端"""
    
    def __init__(self, api_key: str, api_url: str = "https://api.openai.com/v1/chat/completions", model: str = "gpt-4"):
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
    
    def generate(self, prompt: str, images: List[str] = None) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = [{"role": "user", "content": []}]
        messages[0]["content"].append({"type": "text", "text": prompt})
        
        if images:
            for img_path in images:
                if os.path.exists(img_path):
                    img_data_bytes = resize_image_for_api(img_path)
                    img_data = base64.b64encode(img_data_bytes).decode()
                    messages[0]["content"].append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_data}"}
                    })
        
        data = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 32768
        }
        
        response = requests.post(self.api_url, headers=headers, json=data, timeout=300)
        response.raise_for_status()
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        # 后端不再自动清理，由调用方决定何时清理
        return content


class OllamaBackend(AIBackend):
    """本地 Ollama 后端"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        self.base_url = base_url
        self.model = model
    
    def generate(self, prompt: str, images: List[str] = None) -> str:
        url = f"{self.base_url}/api/generate"
        data = {"model": self.model, "prompt": prompt, "stream": False}
        
        if images:
            data["images"] = []
            for img_path in images:
                if os.path.exists(img_path):
                    img_data_bytes = resize_image_for_api(img_path)
                    img_data = base64.b64encode(img_data_bytes).decode()
                    data["images"].append(img_data)
        
        response = requests.post(url, json=data, timeout=300)
        response.raise_for_status()
        
        result = response.json()
        return result.get("response", "")


class MockBackend(AIBackend):
    """模拟后端（用于测试）"""
    
    def generate(self, prompt: str, images: List[str] = None) -> str:
        return """
\\section{实验目的}
\\begin{enumerate}
    \\item 请根据实验指导书填写实验目的
\\end{enumerate}

\\section{实验器材}
请根据实验指导书填写实验器材

\\section{实验原理}
请根据实验指导书填写实验原理

\\section{实验步骤}
\\begin{enumerate}
    \\item 请根据实验指导书填写实验步骤
\\end{enumerate}

\\section{实验结果与数据处理}
请根据数据记录表填写实验数据

\\section{思考题}
\\begin{enumerate}
    \\item 思考题1
    
    答: 请填写答案
\\end{enumerate}

\\section{总结}
请填写实验总结
"""


class ReportGenerator:
    """实验报告生成器"""
    
    SYSTEM_PROMPT = """你是一个专业的物理实验报告撰写助手。
    
    【核心指令 - 必须严格遵守】
    1. **只输出纯 LaTeX 代码**：严禁输出任何 Markdown 代码块标记（不要 ```latex 或 ```）。
    2. **禁止闲聊**：严禁输出任何解释、道歉或前言后语。
    3. **表格语法**：在表格中，每行末尾必须使用双反斜杠 `\\\\` 进行换行。
    4. **特殊字符**：正文中的特殊字符（如 &, $, %, #, _）必须使用反斜杠转义（如 \\&, \\$, \\%, \\#, \\_）。但在数学公式或表格对齐中，应保留其功能。
    5. **编译兼容性**：确保输出可以被 XeLaTeX 完美编译，不要使用不常用的宏包。
    """
    
    def __init__(self, backend: AIBackend = None):
        """
        初始化生成器
        
        Args:
            backend: AI 后端实例，None 则使用模拟后端
        """
        self.backend = backend or MockBackend()
    
    def generate_report_content(self,
                                experiment_guide: str = None,
                                data_sheet_images: List[str] = None,
                                additional_requirements: str = None) -> str:
        """
        生成完整的报告内容（分步生成机制）
        
        Args:
            experiment_guide: 实验指导书内容（文本）
            data_sheet_images: 数据记录表图片路径列表
            additional_requirements: 额外要求
            
        Returns:
            合成的完整 LaTeX 报告内容
        """
        print("开始分步生成报告...")
        
        # 1. 生成基础部分 (目的、器材、原理、步骤)
        print("Step 1: 生成基础部分...")
        part1_prompt = self._build_part1_prompt(experiment_guide, additional_requirements)
        part1_raw = self.backend.generate(part1_prompt)
        part1_content = self.backend.clean_content(part1_raw)
        print("Step 1 完成")
        
        # 2. 生成数据处理部分 (结果与数据处理) - 需要传图
        print("Step 2: 生成数据处理部分...")
        part2_prompt = self._build_part2_prompt(part1_content, additional_requirements)
        part2_raw = self.backend.generate(part2_prompt, data_sheet_images)
        part2_content = self.backend.clean_content(part2_raw)
        print("Step 2 完成")
        
        # 3. 生成分析与总结 (思考题、总结)
        print("Step 3: 生成分析与总结...")
        # 将前两部分作为上下文，确保连贯性
        context = f"{part1_content}\n{part2_content}"
        part3_prompt = self._build_part3_prompt(context, additional_requirements)
        part3_raw = self.backend.generate(part3_prompt)
        part3_content = self.backend.clean_content(part3_raw)
        print("Step 3 完成")
        
        # 合成最终内容
        full_content = f"{part1_content}\n\n{part2_content}\n\n{part3_content}"
        
        return full_content

    def _build_part1_prompt(self, guide, requirements):
        return f"""{self.SYSTEM_PROMPT}

请生成报告的第一部分：
1. \\section{{实验目的}}
2. \\section{{实验器材}}
3. \\section{{实验原理}}
4. \\section{{实验步骤}}

## 实验指导书内容：
{guide if guide else "无"}

## 额外要求：
{requirements if requirements else "无"}

请只返回这 4 个 section 的 LaTeX 内容。
"""

    def _build_part2_prompt(self, previous_context, requirements):
        # 截取前文的一部分作为上下文（避免太长）
        context_preview = previous_context[-15000:] if len(previous_context) > 15000 else previous_context
        
        return f"""{self.SYSTEM_PROMPT}

已生成部分内容：
{context_preview}

现在请生成报告的第二部分：
5. \\section{{实验结果与数据处理}}

此部分非常重要，请根据附带的 **数据记录表图片** 仔细识别数据。
- 必须创建 LaTeX 表格 (table 环境) 填入所有数据。
- 表格必须完整，不要在中间截断。如果数据量大，可以分多个表格。
- 严禁输出 Markdown 代码块 (```)。
- 只输出纯 LaTeX 代码。

## 额外要求：
{requirements if requirements else "无"}

请只返回 \\section{{实验结果与数据处理}} 及其内容的 LaTeX 代码。
"""

    def _build_part3_prompt(self, previous_context, requirements):
        # 同样提供上下文
        context_preview = previous_context[-15000:] if len(previous_context) > 15000 else previous_context

        return f"""{self.SYSTEM_PROMPT}

已生成报告的前面部分：
{context_preview}

现在请生成报告的最后部分：
6. \\section{{思考题}} (如果指导书中有，请回答；如果没有，生成 2 个相关的扩展思考题并回答)
7. \\section{{总结}} (总结实验结果、误差分析、心得体会)

## 额外要求：
{requirements if requirements else "无"}

请只返回这两部分的 LaTeX 代码。
"""

    def modify_report_content(self, 
                             current_content: str,
                             modification_request: str) -> str:
        """
        根据用户要求修改报告内容
        """
        prompt = f"""请根据以下要求修改实验报告：

## 当前报告内容：
```latex
{current_content[:15000]}
```

## 修改要求：
{modification_request}

请返回修改后的完整 LaTeX 内容。
"""
        return self.backend.generate(prompt)


def create_generator(backend_type: str = "mock", **kwargs) -> ReportGenerator:
    """
    创建报告生成器
    
    Args:
        backend_type: 后端类型 ("openai", "ollama", "mock")
        **kwargs: 后端参数
        
    Returns:
        ReportGenerator 实例
    """
    if backend_type == "openai":
        backend = OpenAIBackend(
            api_key=kwargs.get("api_key", ""),
            api_url=kwargs.get("api_url", "https://api.openai.com/v1/chat/completions"),
            model=kwargs.get("model", "gpt-4")
        )
    elif backend_type == "ollama":
        backend = OllamaBackend(
            base_url=kwargs.get("base_url", "http://localhost:11434"),
            model=kwargs.get("model", "llama3")
        )
    else:
        backend = MockBackend()
    
    return ReportGenerator(backend)
