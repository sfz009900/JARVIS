import requests
import json
import time
import base64
from typing import List, Dict
import logging
import os
import configparser
import random

logger = logging.getLogger(__name__)    

def _get_google_api_key():
    """
    从配置文件中获取Google API密钥
    
    Returns:
        str: 当前使用的API密钥
    """
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'keyconfig', 'google.ini')
    config = configparser.ConfigParser()
    
    try:
        config.read(config_path)
        current_key = config.get('google_api', 'current_key')
        return current_key
    except Exception as e:
        logger.error(f"读取Google API密钥失败: {str(e)}")
        raise Exception(f"无法获取API密钥: {str(e)}")

def _rotate_google_api_key():
    """
    轮换Google API密钥
    
    Returns:
        str: 新的API密钥
    """
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'keyconfig', 'google.ini')
    config = configparser.ConfigParser()
    
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
        logger.error(f"轮换Google API密钥失败: {str(e)}")
        raise Exception(f"无法轮换API密钥: {str(e)}")

def _get_openrouter_api_key():
    """
    从配置文件中获取OpenRouter API密钥
    
    Returns:
        str: 当前使用的API密钥
    """
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'keyconfig', 'openrouter.ini')
    config = configparser.ConfigParser()
    
    try:
        config.read(config_path)
        current_key = config.get('openrouter_api', 'current_key')
        return current_key
    except Exception as e:
        logger.error(f"读取OpenRouter API密钥失败: {str(e)}")
        raise Exception(f"无法获取API密钥: {str(e)}")

def _rotate_openrouter_api_key():
    """
    轮换OpenRouter API密钥
    
    Returns:
        str: 新的API密钥
    """
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'keyconfig', 'openrouter.ini')
    config = configparser.ConfigParser()
    
    try:
        config.read(config_path)
        current_key = config.get('openrouter_api', 'current_key')
        all_keys = config.get('openrouter_api', 'keys').split(',')
        
        # 从所有密钥中选择一个不同于当前密钥的新密钥
        available_keys = [key for key in all_keys if key != current_key]
        if not available_keys:
            logger.warning("没有可用的备用OpenRouter密钥")
            return current_key
            
        new_key = random.choice(available_keys)
        
        # 更新配置文件
        config.set('openrouter_api', 'current_key', new_key)
        with open(config_path, 'w') as f:
            config.write(f)
            
        logger.info(f"已轮换OpenRouter API密钥")
        return new_key
    except Exception as e:
        logger.error(f"轮换OpenRouter API密钥失败: {str(e)}")
        raise Exception(f"无法轮换API密钥: {str(e)}")

def _call_openrouter_main(chatbot, messages: List[Dict[str, str]]) -> str:
    """
    调用Gemini API进行对话
    
    Args:
        messages: 消息列表，每个消息包含role和content       
    Returns:
        str: AI的响应内容
        
    Raises:
        Exception: 当API调用失败时抛出异常
    """
    # 从messages中提取最后一条用户消息作为prompt
    prompt = ""
    for msg in messages:
        if msg["role"] == "user":
            prompt = msg["content"]
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # 获取当前API密钥
            api_key = _get_google_api_key()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro-exp-03-25:generateContent?key={api_key}"
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            data = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }]
            }
            
            logger.debug(f"Sending request to Gemini API with prompt: {prompt}")
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            logger.debug(f"Gemini API raw response: {json.dumps(result, ensure_ascii=False)}")
            
            # Extract the response text
            try:
                content = ""
                parts = result['candidates'][0]['content']['parts']
                for part in parts:
                    if 'text' in part:
                        content += part['text']
                
                if not content:
                    raise ValueError("API返回的响应内容为空")
                logger.debug(f"Successfully extracted content: {content[:100]}...")
                return content
            except (KeyError, IndexError) as e:
                raise ValueError(f"无法从API响应中提取内容: {str(e)}")
                
        except (requests.exceptions.RequestException, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Gemini API调用失败 (尝试 {retry_count+1}/{max_retries}): {str(e)}")
            
            # 轮换API密钥
            _rotate_google_api_key()
            retry_count += 1
            
            if retry_count >= max_retries:
                logger.error(f"Gemini API调用在 {max_retries} 次尝试后仍然失败")
                if isinstance(e, requests.exceptions.RequestException):
                    raise Exception(f"API请求失败: {str(e)}")
                elif isinstance(e, json.JSONDecodeError):
                    raise Exception(f"解析响应失败: {str(e)}")
                else:
                    raise Exception(f"API调用失败: {str(e)}")
            
            # 短暂延迟后重试
            time.sleep(2)

def _call_openrouter(chatbot, messages: List[Dict[str, str]]) -> str:
    """
    调用Gemini API进行对话
    
    Args:
        messages: 消息列表，每个消息包含role和content       
    Returns:
        str: AI的响应内容
        
    Raises:
        Exception: 当API调用失败时抛出异常
    """
    # 从messages中提取最后一条用户消息作为prompt
    prompt = ""
    for msg in messages:
        if msg["role"] == "user":
            prompt = msg["content"]
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # 获取当前API密钥
            api_key = _get_google_api_key()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-pro-exp-02-05:generateContent?key={api_key}"
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            data = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }]
            }
            
            logger.debug(f"Sending request to Gemini API with prompt: {prompt}")
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            logger.debug(f"Gemini API raw response: {json.dumps(result, ensure_ascii=False)}")
            
            # Extract the response text
            try:
                content = ""
                parts = result['candidates'][0]['content']['parts']
                for part in parts:
                    if 'text' in part:
                        content += part['text']
                
                if not content:
                    raise ValueError("API返回的响应内容为空")
                logger.debug(f"Successfully extracted content: {content[:100]}...")
                return content
            except (KeyError, IndexError) as e:
                raise ValueError(f"无法从API响应中提取内容: {str(e)}")
                
        except (requests.exceptions.RequestException, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Gemini API调用失败 (尝试 {retry_count+1}/{max_retries}): {str(e)}")
            
            # 轮换API密钥
            _rotate_google_api_key()
            retry_count += 1
            
            if retry_count >= max_retries:
                logger.error(f"Gemini API调用在 {max_retries} 次尝试后仍然失败")
                if isinstance(e, requests.exceptions.RequestException):
                    raise Exception(f"API请求失败: {str(e)}")
                elif isinstance(e, json.JSONDecodeError):
                    raise Exception(f"解析响应失败: {str(e)}")
                else:
                    raise Exception(f"API调用失败: {str(e)}")
            
            # 短暂延迟后重试
            time.sleep(2)
            
def _call_openrouter_qwq(chatbot, messages: List[Dict[str, str]]) -> str:
        """
        调用OpenRouter API进行对话
        
        Args:
            messages: 消息列表，每个消息包含role和content
            
        Returns:
            str: AI的响应内容
            
        Raises:
            Exception: 当API调用失败时抛出异常
        """
        max_retries = 3
        retry_count = 0
        retry_delay = 3  # 延迟3秒
        
        while retry_count < max_retries:
            try:
                # 获取当前API密钥
                api_key = _get_openrouter_api_key()
                
                # 记录请求详情
                logger.debug(f"Sending request to OpenRouter API with messages: {json.dumps(messages, ensure_ascii=False)}")
                
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com",
                        "X-Title": "J.A.R.V.I.S AI Assistant"
                    },
                    json={
                        "model": "qwen/qwen-2.5-72b-instruct:free",
                        "messages": messages
                    },
                    timeout=900  # 设置900秒超时
                )
                
                # 记录原始响应
                logger.debug(f"OpenRouter API raw response: {response.text}")
                
                # 检查请求是否成功
                response.raise_for_status()
                
                # 解析JSON响应
                result = response.json()
                logger.debug(f"OpenRouter API parsed response: {json.dumps(result, ensure_ascii=False)}")
                
                # 提取响应内容
                if 'choices' in result and len(result['choices']) > 0:
                    content = result['choices'][0]['message']['content']
                    if not content:
                        raise ValueError("API返回的响应内容为空")
                    logger.debug(f"Successfully extracted content: {content[:100]}...")
                    return content
                else:
                    raise ValueError("API响应中没有找到内容")
                    
            except (ValueError, requests.exceptions.RequestException, json.JSONDecodeError) as e:
                logger.warning(f"OpenRouter API调用失败 (尝试 {retry_count+1}/{max_retries}): {str(e)}")
                
                # 轮换API密钥
                _rotate_openrouter_api_key()
                retry_count += 1
                
                if retry_count >= max_retries:
                    logger.error(f"OpenRouter API调用在 {max_retries} 次尝试后仍然失败")
                    if isinstance(e, requests.exceptions.Timeout):
                        raise Exception("API请求超时，请稍后重试")
                    elif isinstance(e, requests.exceptions.RequestException):
                        raise Exception(f"API请求失败: {str(e)}")
                    elif isinstance(e, json.JSONDecodeError):
                        raise Exception(f"解析响应失败: {str(e)}")
                    else:
                        raise Exception(f"API调用失败: {str(e)}")
                
                # 短暂延迟后重试
                time.sleep(retry_delay)

def _call_openrouter_other(chatbot, messages: List[Dict[str, str]]) -> str:
        """
        调用OpenRouter API进行对话
        
        Args:
            messages: 消息列表，每个消息包含role和content
            
        Returns:
            str: AI的响应内容
            
        Raises:
            Exception: 当API调用失败时抛出异常
        """
        max_retries = 3
        retry_count = 0
        retry_delay = 3  # 延迟3秒
        
        while retry_count < max_retries:
            try:
                # 获取当前API密钥
                api_key = _get_openrouter_api_key()
                
                # 记录请求详情
                logger.debug(f"Sending request to OpenRouter API with messages: {json.dumps(messages, ensure_ascii=False)}")
                
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com",
                        "X-Title": "J.A.R.V.I.S AI Assistant"
                    },
                    json={
                        "model": "openrouter/quasar-alpha",
                        "messages": messages
                    },
                    timeout=180  # 设置900秒超时
                )
                
                # 记录原始响应
                logger.debug(f"OpenRouter API raw response: {response.text}")
                
                # 检查请求是否成功
                response.raise_for_status()
                
                # 解析JSON响应
                result = response.json()
                logger.debug(f"OpenRouter API parsed response: {json.dumps(result, ensure_ascii=False)}")
                
                # 提取响应内容
                if 'choices' in result and len(result['choices']) > 0:
                    content = result['choices'][0]['message']['content']
                    if not content:
                        raise ValueError("API返回的响应内容为空")
                    logger.debug(f"Successfully extracted content: {content[:100]}...")
                    return content
                else:
                    raise ValueError("API响应中没有找到内容")
                    
            except (ValueError, requests.exceptions.RequestException, json.JSONDecodeError) as e:
                logger.warning(f"OpenRouter API调用失败 (尝试 {retry_count+1}/{max_retries}): {str(e)}")
                
                # 轮换API密钥
                _rotate_openrouter_api_key()
                retry_count += 1
                
                if retry_count >= max_retries:
                    logger.error(f"OpenRouter API调用在 {max_retries} 次尝试后仍然失败")
                    if isinstance(e, requests.exceptions.Timeout):
                        raise Exception("API请求超时，请稍后重试")
                    elif isinstance(e, requests.exceptions.RequestException):
                        raise Exception(f"API请求失败: {str(e)}")
                    elif isinstance(e, json.JSONDecodeError):
                        raise Exception(f"解析响应失败: {str(e)}")
                    else:
                        raise Exception(f"API调用失败: {str(e)}")
                
                # 短暂延迟后重试
                time.sleep(retry_delay)
                
def _call_openrouter_search(chatbot, messages: List[Dict[str, str]], use_search_grounding: bool = True) -> str:
    """
    调用Gemini API进行对话，可选择启用Google Search grounding功能
    
    Args:
        messages: 消息列表，每个消息包含role和content
        use_search_grounding: 是否启用Google Search grounding功能
    Returns:
        str: 包含AI响应内容和搜索建议的组合字符串
        
    Raises:
        Exception: 当API调用失败时抛出异常
    """
    # 从messages中提取最后一条用户消息作为prompt
    prompt = ""
    for msg in messages:
        if msg["role"] == "user":
            prompt = msg["content"]
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # 获取当前API密钥
            api_key = _get_google_api_key()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro-exp-03-25:generateContent?key={api_key}"
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            # 基本请求数据
            data = {
                "contents": [{
                    "parts": [{"text": "请使用中文回复," + prompt}]
                }]
            }
            
            # 如果启用了Google Search grounding，添加相应配置
            if use_search_grounding:
                data["tools"] = [{
                    "googleSearch": {}
                }]
                # 根据API文档，正确的字段名是config.generationConfig.responseMimeType
                data["generationConfig"] = {
                    "responseMimeType": "text/plain"
                }
            
            logger.debug(f"Sending request to Gemini API with prompt: {prompt}")
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            logger.debug(f"Gemini API raw response: {json.dumps(result, ensure_ascii=False)}")
            
            try:
                # 提取响应内容
                content = ""
                parts = result['candidates'][0]['content']['parts']
                for part in parts:
                    if 'text' in part:
                        content += part['text']
                
                if not content:
                    raise ValueError("API返回的响应内容为空")
                
                logger.debug(f"Successfully extracted content: {content[:100]}...")
                
                return content
                
            except (KeyError, IndexError) as e:
                raise ValueError(f"无法从API响应中提取内容: {str(e)}")
                
        except (requests.exceptions.RequestException, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Gemini API调用失败 (尝试 {retry_count+1}/{max_retries}): {str(e)}")
            
            # 轮换API密钥
            _rotate_google_api_key()
            retry_count += 1
            
            if retry_count >= max_retries:
                logger.error(f"Gemini API调用在 {max_retries} 次尝试后仍然失败")
                if isinstance(e, requests.exceptions.RequestException):
                    raise Exception(f"API请求失败: {str(e)}")
                elif isinstance(e, json.JSONDecodeError):
                    raise Exception(f"解析响应失败: {str(e)}")
                else:
                    raise Exception(f"API调用失败: {str(e)}")
            
            # 短暂延迟后重试
            time.sleep(2)

def _encode_image(image_path: str) -> str:
    """
    将图像文件编码为base64字符串
    
    Args:
        image_path: 图像文件路径
    Returns:
        str: base64编码的图像字符串
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def _call_gemini_vision(image_path: str = None, image_base64: str = None, prompt: str = "请详细分析这张图片中的任何细节并用中文告诉我你看到了什么") -> str:
    """
    调用Gemini API进行图像分析
    
    Args:
        image_path: 图像文件路径（与image_base64二选一）
        image_base64: base64编码的图像数据（与image_path二选一）
        prompt: 提示文本，告诉AI如何分析图像
    Returns:
        str: AI的分析结果
        
    Raises:
        Exception: 当API调用失败时抛出异常
    """
    if not image_path and not image_base64:
        raise ValueError("必须提供image_path或image_base64参数")
        
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # 获取API密钥
            api_key = _get_google_api_key()
            # 使用gemini-2.0-flash模型替代gemini-pro-vision
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            # 获取base64编码的图像
            base64_image = image_base64 if image_base64 else _encode_image(image_path)
            
            # 构建请求数据
            data = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": base64_image
                            }
                        }
                    ]
                }]
            }
            
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            
            try:
                # 提取响应内容
                content = ""
                parts = result['candidates'][0]['content']['parts']
                for part in parts:
                    if 'text' in part:
                        content += part['text']
                
                if not content:
                    raise ValueError("API返回的响应内容为空")
                
                logger.debug(f"Successfully extracted content: {content[:100]}...")
                
                return content
                
            except (KeyError, IndexError) as e:
                raise ValueError(f"无法从API响应中提取内容: {str(e)}")
                
        except (requests.exceptions.RequestException, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Gemini API调用失败 (尝试 {retry_count+1}/{max_retries}): {str(e)}")
            
            # 轮换API密钥
            _rotate_google_api_key()
            retry_count += 1
            
            if retry_count >= max_retries:
                logger.error(f"Gemini API调用在 {max_retries} 次尝试后仍然失败")
                if isinstance(e, requests.exceptions.RequestException):
                    raise Exception(f"API请求失败: {str(e)}")
                elif isinstance(e, json.JSONDecodeError):
                    raise Exception(f"解析响应失败: {str(e)}")
                else:
                    raise Exception(f"API调用失败: {str(e)}")
            
            # 短暂延迟后重试
            time.sleep(2)

def _call_grok3(chatbot, messages: List[Dict[str, str]]) -> str:
    """
    调用本地运行的Grok3 API进行对话
    
    Args:
        messages: 消息列表，每个消息包含role和content
        
    Returns:
        str: AI的响应内容
        
    Raises:
        Exception: 当API调用失败时抛出异常
    """
    max_retries = 3
    retry_count = 0
    retry_delay = 2  # 延迟2秒
    
    # 从messages中提取最后一条用户消息作为question
    question = ""
    for msg in messages:
        if msg["role"] == "user":
            question = msg["content"]
    
    while retry_count < max_retries:
        try:
            # 记录请求详情
            logger.debug(f"Sending request to local Grok3 API with question: {question}")
            
            response = requests.post(
                url="http://localhost:1718/ask",
                headers={
                    "Content-Type": "application/json"
                },
                json={
                    "question": question
                },
                timeout=120  # 设置120秒超时
            )
            
            # 记录原始响应
            logger.debug(f"Grok3 API raw response: {response.text}")
            
            # 检查请求是否成功
            response.raise_for_status()
            
            # 解析JSON响应
            result = response.json()
            logger.debug(f"Grok3 API parsed response: {json.dumps(result, ensure_ascii=False)}")
            
            # 提取响应内容
            if 'status' in result and result['status'] == 'success' and 'responses' in result:
                responses = result['responses'][1]
                if not responses or len(responses) == 0:
                    raise ValueError("API返回的响应列表为空")
                
                # 处理响应，移除UI相关文本并提取JSON内容
                if isinstance(responses, str) and responses.startswith("json"):
                    # 移除UI文本，提取JSON部分
                    json_start = responses.find('{')
                    if json_start != -1:
                        json_str = responses[json_start:]
                        try:
                            # 只解析JSON以验证它是有效的，但返回原始字符串
                            json.loads(json_str)  # 只是验证有效性
                            content = json_str  # 返回未格式化的JSON字符串
                        except json.JSONDecodeError:
                            # 如果JSON解析失败，返回原始文本
                            content = responses
                    else:
                        content = responses
                # 处理响应列表的情况
                elif isinstance(responses, list):
                    content = "\n".join(responses)
                else:
                    content = str(responses)
                
                if not content:
                    raise ValueError("API返回的响应内容为空")
                
                logger.debug(f"Successfully extracted content: {content[:100]}...")
                return content
            else:
                status = result.get('status', 'unknown')
                raise ValueError(f"API响应状态不是success，而是: {status}")
                
        except (ValueError, requests.exceptions.RequestException, json.JSONDecodeError) as e:
            logger.warning(f"Grok3 API调用失败 (尝试 {retry_count+1}/{max_retries}): {str(e)}")
            
            retry_count += 1
            
            if retry_count >= max_retries:
                logger.error(f"Grok3 API调用在 {max_retries} 次尝试后仍然失败")
                if isinstance(e, requests.exceptions.Timeout):
                    raise Exception("API请求超时，请稍后重试")
                elif isinstance(e, requests.exceptions.ConnectionError):
                    raise Exception("无法连接到本地Grok3服务，请确保服务正在运行")
                elif isinstance(e, requests.exceptions.RequestException):
                    raise Exception(f"API请求失败: {str(e)}")
                elif isinstance(e, json.JSONDecodeError):
                    raise Exception(f"解析响应失败: {str(e)}")
                else:
                    raise Exception(f"API调用失败: {str(e)}")
            
            # 短暂延迟后重试
            time.sleep(retry_delay)