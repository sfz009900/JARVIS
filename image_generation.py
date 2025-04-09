import os
import logging
import time
import requests
import base64
from typing import Dict, Any, Optional
from pathlib import Path
from io import BytesIO
from PIL import Image
import asyncio
import configparser
import random
from core.llmhandle.callopenrouter import _call_openrouter_qwq
from core.llmhandle.callopenrouter import _call_openrouter_other

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("image_generation")

def _get_google_api_key():
    """
    从配置文件中获取Google API密钥
    
    Returns:
        str: 当前使用的API密钥
    """
    # 尝试不同的路径构建方式
    possible_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'keyconfig', 'google.ini'),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'keyconfig', 'google.ini'),
        os.path.join(os.path.dirname(__file__), 'keyconfig', 'google.ini'),
        os.path.abspath(os.path.join('keyconfig', 'google.ini'))
    ]
    
    config = configparser.ConfigParser()
    
    for config_path in possible_paths:
        logger.debug(f"尝试读取Google API配置文件: {config_path}")
        if os.path.exists(config_path):
            try:
                config.read(config_path)
                current_key = config.get('google_api', 'current_key')
                logger.info(f"成功从 {config_path} 读取Google API密钥")
                return current_key
            except Exception as e:
                logger.warning(f"从 {config_path} 读取Google API密钥失败: {str(e)}")
                continue
    
    # 如果所有路径都失败
    logger.error("无法从任何可能的路径读取Google API密钥")
    raise Exception("无法获取API密钥: 配置文件不存在或格式不正确")

def _rotate_google_api_key():
    """
    轮换Google API密钥
    
    Returns:
        str: 新的API密钥
    """
    # 尝试不同的路径构建方式
    possible_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'keyconfig', 'google.ini'),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'keyconfig', 'google.ini'),
        os.path.join(os.path.dirname(__file__), 'keyconfig', 'google.ini'),
        os.path.abspath(os.path.join('keyconfig', 'google.ini'))
    ]
    
    config = configparser.ConfigParser()
    
    for config_path in possible_paths:
        logger.debug(f"尝试读取Google API配置文件进行轮换: {config_path}")
        if os.path.exists(config_path):
            try:
                config.read(config_path)
                current_key = config.get('google_api', 'current_key')
                all_keys = config.get('google_api', 'keys').split(',')
                
                # 从所有密钥中选择一个不同于当前密钥的新密钥
                available_keys = [key for key in all_keys if key != current_key]
                if not available_keys:
                    logger.warning("没有可用的备用密钥")
                    return current_key
                    
                new_key = random.choice(available_keys)
                
                # 更新配置文件
                config.set('google_api', 'current_key', new_key)
                with open(config_path, 'w') as f:
                    config.write(f)
                    
                logger.info(f"已轮换Google API密钥")
                return new_key
            except Exception as e:
                logger.warning(f"从 {config_path} 轮换Google API密钥失败: {str(e)}")
                continue
    
    # 如果所有路径都失败
    logger.error("无法从任何可能的路径轮换Google API密钥")
    raise Exception("无法轮换API密钥: 配置文件不存在或格式不正确")

class GeminiImageGenerator:
    """Google Gemini API 图片生成器"""
    
    def __init__(self):
        """初始化 Gemini 图片生成器"""
        # 创建图片保存目录
        self.images_dir = Path("generated_images")
        self.images_dir.mkdir(exist_ok=True)
        
        # API 端点
        self.gemini_api_endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"
        
        logger.info("成功初始化 Gemini 图片生成器")
    
    async def extract_image_prompt(self, user_input: str, ai_response: str = None, llm = None) -> str:
        """从文本中提取图片生成提示词
        
        Args:
            user_input: 用户输入的文本
            ai_response: AI响应的文本
            llm: 语言模型实例，用于提取提示词
            
        Returns:
            提取出的图片生成提示词（英文）
        """
        try:
            if not user_input:
                logger.error("未提供用户输入")
                return ""
                
            logger.info(f"从文本中提取图片生成提示词: {user_input}")
            
            user_input = ai_response
            
            # 使用 _call_openrouter_qwq 提取英文图片提示词
            messages = [
                {
                    "role": "user",
                    "content": f"你是一个专业的图像提示词提取助手。你的任务是把***用户文本***中的内容用丰富的语言转换成适合图像生成的英文提示词,只返回英文提示词，不要包含任何解释或额外文本。\n\n***用户文本***: {user_input}"
                }
            ]
            
            extracted_prompt = _call_openrouter_other(None, messages).strip()
            
            if not extracted_prompt:
                return ""
            
            logger.info(f"成功提取出图片生成提示词: {extracted_prompt}")
            return extracted_prompt
                
        except Exception as e:
            logger.error(f"提取图片提示词时出错: {e}")
            # 出错时尝试翻译原始文本
            try:
                return ""
            except:
                return user_input or ""
    
    async def generate_image_with_gemini(self, prompt: str) -> Dict[str, Any]:
        """使用 Gemini 2.0 Flash 从提示词生成图片
        
        Args:
            prompt: 图片生成提示词
            
        Returns:
            包含生成结果的字典
        """
        try:
            logger.info(f"使用 Gemini 2.0 Flash 生成图片: {prompt}")
            
            # 请求头
            headers = {
                "Content-Type": "application/json"
            }
            
            # 添加重试逻辑
            max_retries = 3
            retry_count = 0
            last_error = None
            
            while retry_count < max_retries:
                try:
                    # 获取API密钥
                    api_key = _get_google_api_key()
                    
                    # 构建带有 API 密钥的 URL
                    api_url = f"{self.gemini_api_endpoint}?key={api_key}"
                    
                    # 请求数据
                    data = {
                        "contents": [{
                            "parts": [{
                                "text": prompt
                            }]
                        }],
                        "generationConfig": {
                            "response_modalities": ["Text", "Image"]
                        },
                        "safetySettings": [
                            {
                                "category": "HARM_CATEGORY_HARASSMENT",
                                "threshold": "BLOCK_NONE"
                            },
                            {
                                "category": "HARM_CATEGORY_HATE_SPEECH",
                                "threshold": "BLOCK_NONE"
                            },
                            {
                                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                                "threshold": "BLOCK_NONE"
                            },
                            {
                                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                                "threshold": "BLOCK_NONE"
                            }
                        ]
                    }
                    
                    # 发送API请求
                    response = requests.post(api_url, headers=headers, json=data, timeout=60)
                    
                    if response.status_code == 200:
                        # 请求成功，处理结果
                        result = response.json()
                        
                        # 检查是否因安全原因被阻止
                        if result.get("candidates", []) and result["candidates"][0].get("finishReason") == "IMAGE_SAFETY":
                            logger.warning(f"图片生成因安全原因被阻止: {prompt}")
                            # 不直接返回，而是进行重试
                            last_error = "图片生成因安全原因被阻止，尝试重新生成"
                            logger.info(f"第 {retry_count + 1} 次尝试失败: {last_error}")
                            
                            retry_count += 1
                            
                            if retry_count < max_retries:
                                # 指数退避策略
                                wait_time = 2 ** retry_count
                                logger.info(f"等待 {wait_time} 秒后重试...")
                                await asyncio.sleep(wait_time)
                            continue  # 跳到下一次循环进行重试
                        
                        images_saved = []
                        timestamp = int(time.time())
                        
                        for i, part in enumerate(result.get("candidates", [])[0].get("content", {}).get("parts", [])):
                            if "text" in part:
                                logger.info(f"生成的文本: {part['text']}")
                            elif "inlineData" in part:
                                # 保存图片
                                image_filename = f"gemini_{timestamp}_{i}.png"
                                image_path = self.images_dir / image_filename
                                
                                # 解码并保存图片
                                image_data = base64.b64decode(part["inlineData"]["data"])
                                image = Image.open(BytesIO(image_data))
                                image.save(image_path)
                                
                                logger.info(f"图片已保存到: {image_path}")
                                images_saved.append({
                                    "image_path": str(image_path),
                                    "image_url": f"/image/{image_filename}"
                                })
                                
                                # 显示图片
                                # image.show()
                        
                        if not images_saved:
                            logger.warning("响应中未找到图片数据")
                            return {
                                "success": False,
                                "prompt": prompt,
                                "error": "响应中未找到图片数据"
                            }
                        
                        return {
                            "success": True,
                            "images": images_saved,
                            "prompt": prompt
                        }
                    else:
                        # 请求失败，记录错误并准备重试
                        last_error = f"API请求失败: {response.status_code} - {response.text}"
                        logger.warning(f"第 {retry_count + 1} 次请求失败: {last_error}")
                        
                        # 轮换API密钥
                        _rotate_google_api_key()
                        
                        retry_count += 1
                        
                        if retry_count < max_retries:
                            # 指数退避策略
                            wait_time = 2 ** retry_count
                            logger.info(f"等待 {wait_time} 秒后重试...")
                            await asyncio.sleep(wait_time)
                        
                except Exception as e:
                    last_error = f"请求过程中出错: {str(e)}"
                    logger.warning(f"第 {retry_count + 1} 次请求出错: {last_error}")
                    
                    # 轮换API密钥
                    _rotate_google_api_key()
                    
                    retry_count += 1
                    
                    if retry_count < max_retries:
                        # 指数退避策略
                        wait_time = 2 ** retry_count
                        logger.info(f"等待 {wait_time} 秒后重试...")
                        await asyncio.sleep(wait_time)
            
            # 所有重试都失败
            logger.error(f"在 {max_retries} 次尝试后仍然失败: {last_error}")
            return {
                "success": False,
                "prompt": prompt,
                "error": last_error or "多次请求后仍然失败"
            }
                
        except Exception as e:
            logger.error(f"生成图片时出错: {e}")
            return {
                "success": False,
                "prompt": prompt,
                "error": f"生成图片时出错: {str(e)}"
            }

    async def generate_image_from_prompt(self, prompt: str, use_imagen: bool = False) -> Dict[str, Any]:
        """从提示词生成图片
        
        Args:
            prompt: 图片生成提示词
            use_imagen: 是否使用 Imagen API 而不是 Gemini API
            
        Returns:
            包含生成结果的字典
        """
        try:
            logger.info(f"从提示词生成图片: {prompt}")
            
            # 调用 Gemini API 生成图片
            result = await self.generate_image_with_gemini(prompt)
            
            if not result["success"]:
                logger.warning(f"使用 Gemini API 生成图片失败: {result.get('error', '未知错误')}")
                return result
            
            # 提取第一张图片的信息
            if "images" in result and result["images"]:
                first_image = result["images"][0]
                return {
                    "success": True,
                    "image_path": first_image["image_path"],
                    "image_url": first_image["image_url"],
                    "prompt": prompt
                }
            else:
                return {
                    "success": False,
                    "error": "生成的图片列表为空",
                    "prompt": prompt
                }
                
        except Exception as e:
            logger.error(f"生成图片时出错: {e}")
            return {
                "success": False,
                "error": f"生成图片时出错: {str(e)}",
                "prompt": prompt
            }
