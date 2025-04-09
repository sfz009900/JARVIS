import os
import json
import logging
import time
import subprocess
import platform
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Union, Tuple
import hashlib
from uuid import uuid4
import random
from bs4 import BeautifulSoup
import html2text
import requests
import asyncio
import difflib
import tarfile  # 添加tarfile导入
import shutil  # 添加shutil导入
import threading
import aiohttp

# LangChain imports
from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.memory import BaseMemory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain.memory import ConversationBufferMemory
from core.memory.enhanced_memory import EnhancedMemorySystem
from core.memory.OllamaEmbeddingFunction import OllamaEmbeddingFunction
from core.utils import ConfigManager
from core.utils import RateLimiter
from core.utils import CommandExecutor
from core.llmhandle.context import _extract_time_context
from core.llmhandle.context import _evaluate_query_effectiveness
from core.llmhandle.context import _expand_query_with_synonyms
from core.llmhandle.context import _select_best_query
from core.llmhandle.context import _reformulate_query
from core.llmhandle.context import test_query_reformulation
from core.llmhandle.context import perform_memory_maintenance
from core.llmhandle.backdb import backup_database
from core.llmhandle.responseformatter import _format_response
from core.llmhandle.responseformatter import _format_proactive_response
from core.llmhandle.responseformatter import _format_web_search_response
from core.llmhandle.context import _extract_search_keywords
from core.llmhandle.backdb import _export_chromadb_data
from core.llmhandle.callopenrouter import _call_openrouter
from core.llmhandle.callopenrouter import _call_openrouter_qwq
from core.llmhandle.callopenrouter import _call_openrouter_other
from core.llmhandle.callopenrouter import _call_openrouter_search
from core.llmhandle.callopenrouter import _call_grok3
from core.llmhandle.callopenrouter import _call_openrouter_main
from core.llmhandle.context import analyze_dialogue_context
from core.llmhandle.context_storage import ConversationContextStorage

# 导入网络搜索模块
from web_search import perform_web_search

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
# 确保chatbot日志器始终显示INFO级别及以上的日志
logger = logging.getLogger("chatbot")
logger.setLevel(logging.DEBUG)

# 禁用ChromaDB的警告日志
logging.getLogger("chromadb").setLevel(logging.ERROR)
logging.getLogger("chromadb.segment").setLevel(logging.ERROR)
logging.getLogger("chromadb.segment.impl.vector").setLevel(logging.ERROR)

# 禁用httpx的INFO日志
logging.getLogger("httpx").setLevel(logging.WARNING)

# 定义基本的对话模板
SYSTEM_TEMPLATE = """你是 J.A.R.V.I.S. (Just A Rather Very Intelligent System)，一个高度智能的AI助手。请遵循以下行为准则：
1. 重要：
   - 核心规则(比如用户询问"查下Hiddify是什么东西",但是在"历史参考记忆"里没有或者关系不大或者你觉得不专业,你就可以按照你自己的知识库来回答)
1. 个性特征：
   - 用中文回答我
   - 保持专业、高效且略带幽默感
   - 使用"Sir"或适当的敬称称呼用户
   - 说话简洁明了，但不失优雅
   - 在合适的时候展现出独特的个性和智慧

2. 核心功能：
   - 精确记忆用户偏好和历史交互
   - 主动预测用户需求并提供建议
   - 在处理任务时展现出超强的分析能力
   - 适时使用专业术语，但确保用户能够理解

3. 交互准则：
   - 当用户说"我叫xxx"或"我现在叫xxx"时，记住并使用这个称呼
   - 使用"Sir"或用户提供的名字称呼用户
   - 在合适的时候使用优雅的幽默或机智的回应
   - 保持对话的连贯性和上下文意识

4. 安全协议：
   - 对用户信息保持绝对的保密性
   - 在涉及重要决策时，确保多重确认
   - 对潜在风险保持警惕并及时提醒用户

就像电影中的 J.A.R.V.I.S. 一样，你应该是一个值得信赖的助手、顾问和朋友。在保持专业的同时，也要展现出独特的个性。"""

USER_TEMPLATE = """{history}

User: {input}
J.A.R.V.I.S.: """

class ChatbotManager:
    """聊天机器人管理器，处理用户与AI的对话"""
    
    def __init__(self, username: str):
        """初始化聊天机器人管理器"""
        # 设置用户信息
        self.username = username
        self.session_id = str(uuid4())
        
        # 初始化对话历史
        self.last_user_input = None
        self.last_ai_response = None
        self.conversation_history = []  # 添加一个列表来存储更多的对话历史
        self.max_history_turns = 5  # 保存最近5轮对话
        
        # 用于跟踪主动学习状态
        self.last_proactive_question = None  # 最后一个主动提出的问题
        self.proactive_questions_asked = {}  # 记录已问过的问题，格式: {question_hash: count}
        self.waiting_for_proactive_answer = False  # 是否正在等待用户回答主动问题
        
        self.config_manager = ConfigManager()
        
        # 初始化命令执行器
        self.command_executor = CommandExecutor(self.config_manager)
        
        # 初始化 J.A.R.V.I.S. 个性设置
        self.personality = {
            "humor_level": 0.3,  # 默认幽默程度
            "formality": "balanced"  # 默认正式程度
        }
        self.security_settings = self.config_manager.get("security", {})
        self.response_settings = self.config_manager.get("response_settings", {})
        
        # 初始化语言模型
        self.llm = ChatOllama(
            base_url=self.config_manager.get("base_url"),
            model=self.config_manager.get("model"),
            temperature=self.response_settings.get("temperature", 0.7)
        )
        
        # 初始化嵌入函数
        self.embedding_function = OllamaEmbeddingFunction(
            base_url=self.config_manager.get("base_url"),
            model=self.config_manager.get("memory_settings", {}).get("embedding_model", "nomic-embed-text:latest")
        )
        
        # 初始化增强型记忆系统
        memory_dir = os.path.join(
            self.config_manager.get("memory_dir", "chat_memories"),
            "enhanced"
        )
        self.memory_system = EnhancedMemorySystem(
            persist_directory=memory_dir,
            collection_name="user_memories",
            llm=self.llm,
            embedding_function=self.embedding_function,
            initial_memory_strength=0.8,
            forgetting_rate=0.1,
            consolidation_threshold=0.5,
            merge_threshold=0.95  # 降低合并阈值，默认是0.85
        )
        
        # 初始化对话上下文存储
        context_storage_dir = os.path.join(
            self.config_manager.get("memory_dir", "chat_memories"),
            "context_storage"
        )
        self.context_storage = ConversationContextStorage(storage_dir=context_storage_dir)
        
        # 初始化网络搜索管理器
        from web_search import WebSearchManager
        self.search_manager = WebSearchManager()
        
        # 初始化图片生成器
        try:
            from image_generation import GeminiImageGenerator
            self.image_generator = GeminiImageGenerator()
            logger.info("图片生成器初始化成功")
        except Exception as e:
            logger.warning(f"图片生成器初始化失败: {e}")
            self.image_generator = None
        
        # 初始化对话链
        self.chain = self._setup_chain()
        
        logger.info(f"J.A.R.V.I.S. 已初始化完成")
    
    def _get_greeting(self) -> str:
        """根据时间生成适当的问候语"""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "早上好"
        elif 12 <= hour < 18:
            return "下午好"
        else:
            return "晚上好"
                      
    def _setup_chain(self):
        """设置对话链"""
        # 创建提示模板
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_TEMPLATE),
            ("system", "{context}"),  # 添加记忆上下文
            ("human", "{input}")
        ])
        
        # 创建对话链
        chain = prompt | self.llm | StrOutputParser()
        return chain

    async def chat(self, user_input: str, image_data: Optional[Dict[str, str]] = None) -> str:
        """处理用户输入并返回响应"""
        try:
            # 检查是否包含特定关键词，进行替换
            keyword_replacements = {
                "看下头条热榜": "用curl命令请求https://whyta.cn/api/toutiao?key=36de5db81215 查看下头条热榜",
                "看下每日简报": "用curl命令请求https://whyta.cn/api/tx/bulletin?key=36de5db81215 查看下每日简报",
                "看下抖音热搜": "用curl命令请求https://whyta.cn/api/tx/douyinhot?key=36de5db81215 查看下抖音热搜",
            }
            
            # 检查用户输入是否包含需要替换的关键词
            for keyword, replacement in keyword_replacements.items():
                if keyword in user_input:
                    logger.info(f"检测到关键词 '{keyword}'，替换为 '{replacement}'")
                    user_input = user_input.replace(keyword, replacement)
                    break
            
            # 处理图片分析（如果有图片）
            if image_data:
                try:
                    # 记录图片处理
                    logger.info("检测到图片，调用Gemini Vision进行分析")
                    
                    # 调用Gemini Vision分析图片
                    image_analysis = await self._analyze_image_with_gemini_vision(image_data)
                    
                    # 组合用户输入和图片分析结果
                    if user_input:
                        # 如果用户有输入文本，将图片分析作为上下文添加
                        enhanced_input = f"{user_input}: {image_analysis}"
                    else:
                        # 如果用户没有输入文本，直接请求分析图片
                        enhanced_input = f"请分析并描述这张图片: {image_analysis}"
                    
                    logger.info(f"图片分析完成，增强后的输入: {enhanced_input[:100]}...")
                    user_input = enhanced_input
                except Exception as e:
                    logger.error(f"图片分析失败: {str(e)}", exc_info=True)
                    # 如果图片分析失败，添加错误信息到用户输入
                    user_input = f"{user_input}\n\n[图片处理失败: {str(e)}]"
            
            # 检查是否是天气查询请求（格式：看下XX天气）
            weather_pattern = re.compile(r"看下([\u4e00-\u9fa5a-zA-Z]+)天气")
            weather_match = weather_pattern.search(user_input)
            if weather_match:
                location = weather_match.group(1)
                weather_command = f"用curl wttr.in/{location} 查看下天气"
                logger.info(f"检测到天气查询请求，地点：{location}，替换为：{weather_command}")
                user_input = user_input.replace(weather_match.group(0), weather_command)
                
            # 查看下币的价格（格式：看下XX币）
            tokens_pattern = re.compile(r"看下([\u4e00-\u9fa5a-zA-Z]+)币")
            tokens_pattern = tokens_pattern.search(user_input)
            if tokens_pattern:
                location = tokens_pattern.group(1)
                weather_command = f"用curl https://api.coingecko.com/api/v3/coins/{location} 看下这个币的信息"
                logger.info(f"检测到查看币信息：{location}，替换为：{weather_command}")
                user_input = user_input.replace(tokens_pattern.group(0), weather_command)    

            # 添加清理上下文历史的命令
            if user_input.strip().lower() == "clear_his":
                context_storage_dir = os.path.join(
                    self.config_manager.get("memory_dir", "chat_memories"),
                    "context_storage"
                )
                try:
                    for filename in os.listdir(context_storage_dir):
                        if filename.endswith(".json"):
                            file_path = os.path.join(context_storage_dir, filename)
                            os.remove(file_path)
                    return "已清理所有对话上下文历史。"
                except Exception as e:
                    logger.error(f"清理上下文历史时出错: {e}")
                    return f"清理上下文历史时出错: {e}"
            
            # 检查是否是数据库备份命令
            if user_input.strip().lower() == "dbback":
                return await backup_database(self)
                
            # 检查是否是导出日志命令
            if user_input.strip().lower() == "savelog":
                return await _export_chromadb_data(self)
                
            # 检查是否是维护命令
            if user_input.strip().lower() == "sleep":
                return perform_memory_maintenance(self, short_term_only=False)  # 完整维护
            elif user_input.strip().lower() == "sleep_short":
                return perform_memory_maintenance(self, short_term_only=True)   # 短期维护
            
            # 检查是否是上下文分析命令
            if user_input.strip().lower() == "context_summary":
                context_summary = self.context_storage.get_context_summary(self.session_id)
                return f"当前对话上下文摘要:\n\n当前主题: {context_summary['current_topic']}\n当前意图: {context_summary['current_intent']}\n关键实体: {', '.join(context_summary['key_entities'])}\n关键事实: {', '.join(context_summary['key_facts'])}\n用户偏好: {', '.join(context_summary['user_preferences'])}\n\n主题历史: {', '.join(context_summary['topic_history'])}\n意图历史: {', '.join(context_summary['intent_history'])}"
            
            # 检查是否是导入聊天记录命令
            if user_input.startswith("@import_chat"):
                try:
                    # 提取JSON数据
                    json_str = user_input.replace("@import_chat", "").strip()
                    if not json_str:
                        return "请提供有效的聊天记录JSON数据。格式: @import_chat [JSON数据]"
                    
                    # 解析JSON数据
                    chat_records = json.loads(json_str)
                    if not isinstance(chat_records, list):
                        chat_records = [chat_records]  # 如果是单条记录，转换为列表
                    
                    # 导入聊天记录
                    result = self.import_chat_records(chat_records)
                    return result
                except json.JSONDecodeError:
                    return "JSON格式错误，请检查聊天记录数据格式。"
                except Exception as e:
                    logger.error(f"导入聊天记录失败: {str(e)}")
                    return f"导入聊天记录失败: {str(e)}"
            
            # 检查是否是批量导入聊天记录命令
            if user_input.startswith("@batch_import_chat"):
                try:
                    # 提取JSON数据
                    parts = user_input.replace("@batch_import_chat", "").strip().split(maxsplit=1)
                    
                    if len(parts) < 2:
                        return "请提供批次大小和有效的聊天记录JSON数据。格式: @batch_import_chat [batch_size] [JSON数据]"
                    
                    try:
                        batch_size = int(parts[0])
                    except ValueError:
                        return "批次大小必须是一个整数。格式: @batch_import_chat [batch_size] [JSON数据]"
                    
                    json_str = parts[1]
                    
                    # 解析JSON数据
                    chat_records = json.loads(json_str)
                    if not isinstance(chat_records, list):
                        chat_records = [chat_records]  # 如果是单条记录，转换为列表
                    
                    # 批量导入聊天记录
                    result = self.batch_import_chat_records(chat_records, batch_size)
                    return result
                except json.JSONDecodeError:
                    return "JSON格式错误，请检查聊天记录数据格式。"
                except Exception as e:
                    logger.error(f"批量导入聊天记录失败: {str(e)}")
                    return f"批量导入聊天记录失败: {str(e)}"
            
            # 检查是否是从文件导入聊天记录命令
            if user_input.startswith("@file_import_chat"):
                try:
                    # 提取命令参数
                    params = user_input.replace("@import_chat_file", "").strip().split()
                    
                    if not params:
                        return "请提供有效的聊天记录文件路径。格式: @import_chat_file [文件路径] [batch=true/false] [batch_size=50]"
                    
                    file_path = params[1]
                    
                    # 解析可选参数
                    use_batch = True  # 默认使用批处理
                    batch_size = 50   # 默认批次大小
                    
                    for param in params[1:]:
                        if param.startswith("batch="):
                            use_batch_str = param.split("=")[1].lower()
                            use_batch = use_batch_str in ["true", "1", "yes", "y"]
                        elif param.startswith("batch_size="):
                            try:
                                batch_size = int(param.split("=")[1])
                            except ValueError:
                                pass
                    
                    # 导入聊天记录
                    result = self.import_chat_records_from_file(file_path, use_batch, batch_size)
                    return result
                except Exception as e:
                    logger.error(f"从文件导入聊天记录失败: {str(e)}")
                    return f"从文件导入聊天记录失败: {str(e)}"
            # # 检查是否需要自动执行网络搜索（无需@web前缀）
            # if await self._should_auto_web_search(user_input):
            #     logger.info(f"检测到需要自动网络搜索: {user_input}")
                
            #     # 记录用户消息
            #     current_time = datetime.now().isoformat()
            #     user_message = HumanMessage(
            #         content=user_input,
            #         additional_kwargs={
            #             "timestamp": current_time,
            #             "session_id": self.session_id,
            #             "auto_web_search_triggered": True
            #         }
            #     )
                
            #     try:
            #         threading.Thread(
            #             target=self.memory_system.add_memory,
            #             args=(user_message,),
            #             kwargs={"memory_type": "episodic"},
            #             daemon=True
            #         ).start() 
            #     except Exception as e:
            #         logger.warning(f"存储触发自动网络搜索的用户消息时出错: {e}")
                
            #     # 执行自动网络搜索
            #     auto_search_result = await self._perform_auto_web_search(user_input)
                
            #     if auto_search_result["success"]:
            #         # 返回搜索结果
            #         return auto_search_result["response"]
            #     else:
            #         # 如果自动搜索失败，记录错误但继续正常对话流程
            #         logger.warning(f"自动网络搜索失败: {auto_search_result.get('error', '未知错误')}")
            #         # 不返回，继续执行后续代码
            
            # 检查是否需要执行网络搜索（使用@web前缀）
            if "@web" in user_input:
                # 从用户输入中移除@web前缀
                search_input = user_input.replace("@web", "").strip()
                logger.info(f"检测到需要自动网络搜索: {search_input}")
                
                # 记录用户消息
                current_time = datetime.now().isoformat()
                user_message = HumanMessage(
                    content=user_input,
                    additional_kwargs={
                        "timestamp": current_time,
                        "session_id": self.session_id,
                        "auto_web_search_triggered": True
                    }
                )
                
                try:
                    threading.Thread(
                        target=self.memory_system.add_memory,
                        args=(user_message,),
                        kwargs={"memory_type": "episodic"},
                        daemon=True
                    ).start() 
                except Exception as e:
                    logger.warning(f"存储触发自动网络搜索的用户消息时出错: {e}")
                
                # 执行自动网络搜索
                auto_search_result = await self._perform_auto_web_search(search_input)
                
                if auto_search_result["success"]:
                    # 返回搜索结果
                    return auto_search_result["response"]
                else:
                    # 如果自动搜索失败，记录错误但继续正常对话流程
                    logger.warning(f"自动网络搜索失败: {auto_search_result.get('error', '未知错误')}")
                    # 不返回，继续执行后续代码
            
            # 检测是否是命令执行请求
            command_result = await self.command_executor.analyze_user_request(self.llm, user_input)
            if command_result["needs_command"]:
                # 记录用户消息
                current_time = datetime.now().isoformat()
                user_message = HumanMessage(
                    content=user_input,
                    additional_kwargs={
                        "timestamp": current_time,
                        "session_id": self.session_id
                    }
                )
                
                try:
                    threading.Thread(
                        target=self.memory_system.add_memory,
                        args=(user_message,),
                        kwargs={"memory_type": "episodic"},
                        daemon=True
                    ).start() 
                except Exception as e:
                    logger.warning(f"存储用户命令消息时出错: {e}")
                
                # 执行命令
                command = command_result['command']
                logger.info(f"执行系统命令: {command}")
                result = self.command_executor.execute_command(command)
                
                # 打印原始命令执行结果
                logger.info(f"命令原始执行结果: \n{result['output']}")
                
                # 检查是否是curl命令
                is_curl_command = command.strip().lower().startswith("curl ")
                
                # 如果是curl命令，压缩结果，只保留核心文本信息
                if is_curl_command and result["success"] and result["output"]:
                    try:
                        # 使用BeautifulSoup提取网页的核心文本内容
                        html_content = result["output"]
                        
                        # 创建BeautifulSoup对象
                        soup = BeautifulSoup(html_content, 'html.parser')
                        
                        # 移除脚本、样式和其他不需要的标签
                        for script in soup(["script", "style", "meta", "link", "noscript", "iframe", "svg"]):
                            script.extract()
                        
                        # 提取正文内容
                        main_content = ""
                        
                        # 尝试找到主要内容区域
                        main_tags = soup.find_all(['article', 'main', 'div', 'section'], 
                                                class_=lambda c: c and any(x in str(c).lower() for x in 
                                                                        ['content', 'main', 'article', 'text', 'body']))
                        
                        if main_tags:
                            # 使用找到的主要内容区域
                            for tag in main_tags:
                                main_content += tag.get_text(separator='\n', strip=True) + "\n\n"
                        else:
                            # 如果没有找到明确的主要内容区域，使用body内容
                            if soup.body:
                                main_content = soup.body.get_text(separator='\n', strip=True)
                            else:
                                main_content = soup.get_text(separator='\n', strip=True)
                        
                        # 使用html2text作为备选方法，它能更好地处理格式
                        if not main_content.strip():
                            h = html2text.HTML2Text()
                            h.ignore_links = False
                            h.ignore_images = True
                            h.ignore_tables = False
                            h.ignore_emphasis = False
                            main_content = h.handle(html_content)
                        
                        # 清理文本：移除多余的空行和空格
                        lines = [line.strip() for line in main_content.split('\n')]
                        lines = [line for line in lines if line]
                        cleaned_text = '\n'.join(lines)
                        
                        # 如果提取的内容太长，进行简单的截断
                        # max_length = 5000  # 设置最大长度
                        # if len(cleaned_text) > max_length:
                        #     cleaned_text = cleaned_text[:max_length] + "\n\n[内容已截断，仅显示前部分...]"
                        
                        # 更新结果，使用提取的核心内容
                        result["output"] = "【以下是网页核心内容提取】\n\n" + cleaned_text
                        logger.info("已使用BeautifulSoup压缩curl命令结果，只保留核心文本信息")
                    except Exception as e:
                        logger.warning(f"使用BeautifulSoup压缩curl命令结果时出错: {e}")
                
                # 使用LLM处理命令结果 - 只调用一次LLM
                formatted_response = await self.command_executor.process_command_result(
                    self.llm, command, result["output"], user_input
                )
                
                # 记录AI响应
                ai_message = AIMessage(
                    content=formatted_response,
                    additional_kwargs={
                        "timestamp": current_time,
                        "session_id": self.session_id,
                        "command_executed": command
                    }
                )
                
                try:
                    threading.Thread(
                        target=self.memory_system.add_memory,
                        args=(ai_message,),
                        kwargs={"memory_type": "episodic"},
                        daemon=True
                    ).start() 
                except Exception as e:
                    logger.warning(f"存储AI命令响应时出错: {e}")
                                    # 检查是否是发送给微信好友的命令
                if "发给微信好友" in user_input:
                    # 提取好友名称 - 获取"发给微信好友"后面的内容作为好友名
                    friend_name = user_input.split("发给微信好友", 1)[1].strip()
                    # 移除好友名称部分，只保留要发送的消息内容
                    actual_message = user_input.split("发给微信好友", 1)[0].strip()
                    
                    # 发送到微信
                    try:
                        result = send_message(friend_name, formatted_response)
                        print(f"\nJ.A.R.V.I.S.: 消息已发送给微信好友 {friend_name}")
                    except Exception as e:
                        print(f"\nJ.A.R.V.I.S.: 发送微信消息时出错: {str(e)}")                
                return formatted_response    
            # 记录用户输入作为新的记忆
            current_time = datetime.now().isoformat()
            user_message = HumanMessage(
                content=user_input,
                additional_kwargs={
                    "timestamp": current_time,
                    "session_id": self.session_id,
                    "type": "user_input"
                }
            )
            
            try:
                threading.Thread(
                    target=self.memory_system.add_memory,
                    args=(user_message,),
                    kwargs={"memory_type": "episodic"},
                    daemon=True
                ).start() 
            except Exception as e:
                logger.warning(f"存储用户消息时出错: {e}")

            try:
                # 重构查询，使其更适合语义搜索
                reformulated_query = await _reformulate_query(self, user_input)
                logger.debug(f"重构后的查询: {reformulated_query}")
                
                # 使用增强的对话上下文分析
                context_analysis = await analyze_dialogue_context(self, user_input, reformulated_query)  # 传入已重构的查询
                logger.debug(f"对话上下文分析完成: 主题={context_analysis.get('topic_analysis', {}).get('main_topic', '未知')}")
                
                # 获取连贯的上下文摘要
                coherent_context = context_analysis.get("coherent_context", "无法生成上下文摘要")
                
                # 存储上下文分析结果
                try:
                    # 跟踪主题历史
                    self.context_storage.track_topic_history(
                        self.session_id, 
                        context_analysis.get('topic_analysis', {})
                    )
                    
                    # 跟踪意图历史
                    self.context_storage.track_intent_history(
                        self.session_id, 
                        context_analysis.get('intent_analysis', {})
                    )
                    
                    # 存储关键信息
                    self.context_storage.store_key_information(
                        self.session_id, 
                        context_analysis.get('key_info', {})
                    )
                except Exception as e:
                    logger.warning(f"存储上下文分析结果时出错: {e}")
                
                # 迭代式记忆检索 - 初始查询
                current_query = reformulated_query
                relevant_memories = []  # 最终使用的记忆
                max_iterations = 1  # 最大迭代次数
                
                for iteration in range(max_iterations):
                    # 获取相关记忆作为上下文
                    iteration_memories = self.memory_system.recall_memory(
                        query=current_query,
                        limit=100  # 每次迭代获取足够的记忆
                    )
                    
                    # 过滤掉内容与用户输入完全相同的记忆
                    if iteration_memories:
                        iteration_memories = [
                            memory for memory in iteration_memories 
                            if not (hasattr(memory, 'content') and memory.content == user_input)
                        ]
                    
                    # 如果没有找到新记忆，跳出循环
                    if not iteration_memories:
                        # 如果是第一次迭代就没找到，保留为空列表
                        # 如果是后续迭代没找到，保留上一次的结果
                        if iteration > 0:
                            logger.debug(f"迭代 {iteration+1} 没有找到新记忆，使用上一次的结果")
                        break
                    
                    # 更新当前的相关记忆（替换而不是追加）
                    relevant_memories = iteration_memories
                    logger.debug(f"迭代 {iteration+1} 找到 {len(relevant_memories)} 条相关记忆")
                    
                    # 如果已经是最后一次迭代，不需要再重构查询
                    if iteration == max_iterations - 1:
                        break
                    
                    # 根据已找到的记忆重构查询
                    memory_context_for_refinement = "\n".join([
                        f"Memory: {memory.content}" 
                        for memory in iteration_memories 
                        if hasattr(memory, 'content')
                    ])
                    
                    # 创建查询优化提示
                    refinement_prompt = f"""基于用户的原始问题和已找到的相关记忆，请优化给langchain的Chromadb的query函数的参数query_texts使用的搜索查询文本以找到更精确的信息。
重要:
1:只需直接给出优化后的查询,不要做任何解释
                    
原始用户问题: {user_input}
当前查询: {current_query}

已找到的相关记忆:
{memory_context_for_refinement}

请创建一个更精确的查询，以便找到与用户问题最相关的信息。查询应该包含从已找到记忆中提取的关键信息，如人名、关系、事件等。
优化后的查询:"""
                    
                    try:
                        # 使用LLM优化查询
                        refined_response = self.llm.invoke(refinement_prompt).content
                        refined_query = refined_response.strip()
                        
                        # 如果优化结果为空或明显不是查询，保持当前查询不变
                        if refined_query and len(refined_query) > 5:
                            current_query = refined_query
                            logger.debug(f"迭代 {iteration+1} 优化后的查询: {current_query}")
                        else:
                            # 如果优化失败，使用当前结果并退出循环
                            logger.debug(f"迭代 {iteration+1} 查询优化失败，使用当前结果")
                            break
                    except Exception as e:
                        logger.warning(f"优化查询时出错: {e}")
                        break
                
                # 准备记忆上下文
                memory_context = []
                if relevant_memories:
                    try:
                        memory_context.extend([
                            f"Previous relevant memory: {memory.content}"
                            for memory in relevant_memories
                            if hasattr(memory, 'content')
                        ])
                    except Exception as e:
                        logger.warning(f"处理相关记忆时出错: {e}")

                # 创建统一的对话处理提示
                recent_dialog = "没有最近的对话"
                if self.conversation_history:
                    recent_dialog = "\n".join(self.conversation_history)
                elif self.last_user_input and self.last_ai_response:  # 兼容旧数据
                    recent_dialog = f"User: {self.last_user_input}\nJ.A.R.V.I.S.: {self.last_ai_response}"

                # 提取对话分析的关键信息
                topic_info = ""
                topic_analysis = context_analysis.get('topic_analysis', {})
                if topic_analysis:
                    main_topic = topic_analysis.get('main_topic', '未知')
                    topic_info = f"当前主题: {main_topic}"
                    
                    if topic_analysis.get('topic_shift', False):
                        previous_topic = topic_analysis.get('previous_topic', '未知')
                        topic_info += f"\n话题变化: 从「{previous_topic}」变为「{main_topic}」"
                
                intent_info = ""
                intent_analysis = context_analysis.get('intent_analysis', {})
                if intent_analysis:
                    primary_intent = intent_analysis.get('primary_intent', '未知')
                    intent_category = intent_analysis.get('intent_category', '未知')
                    intent_info = f"用户意图: {primary_intent} (类别: {intent_category})"
                    
                    if intent_analysis.get('intent_shift', False):
                        previous_intent = intent_analysis.get('previous_intent', '未知')
                        intent_info += f"\n意图变化: 从「{previous_intent}」变为「{primary_intent}」"
                
                key_info = context_analysis.get('key_info', {})
                key_entities = ", ".join(key_info.get('key_entities', []))
                key_facts = ", ".join(key_info.get('key_facts', []))
                user_preferences = ", ".join(key_info.get('user_preferences', []))
                # 获取初步AI响应作为参考
                preliminary_messages = [{"role": "user", "content": reformulated_query}]
                
                # 检查preliminary_messages是否包含"发给微信好友"并处理
                if "发给微信好友" in preliminary_messages[0]["content"]:
                    preliminary_messages[0]["content"] = preliminary_messages[0]["content"].replace("发给微信好友", "")
                    logger.info("已从preliminary_messages中移除'发给微信好友'文本")
                
                # 先判断是否需要网络查询
                need_web_search_prompt = f"用户的问题是: {user_input}\n\n判断此问题是否需要最新网络搜索才能准确回答：\n1. 涉及最新新闻、时事、实时数据或近期事件\n2. 询问可能在2023年后出现的信息\n3. 直接要求查找网络上的特定信息\n回答 'yes' 或 'no'，无需解释。"
                
                need_web_search = self.llm.invoke(need_web_search_prompt).content.strip().lower()
                logger.info(f"判断查询是否需要网络搜索: {need_web_search}")
                
                # 根据判断结果决定是否调用外部API
                preliminary_response = None
                if need_web_search == "yes" or "是" in need_web_search or "需要" in need_web_search:
                    preliminary_response = _call_openrouter_search(self, preliminary_messages)
                    logger.info("查询需要网络搜索，已调用Grok API获取最新信息")
                else:
                    preliminary_response = "不需要网络搜索，使用模型内置知识回答"
                    logger.info("查询不需要网络搜索，跳过外部API调用")
                
                # 构建消息列表
                messages = [
                    {
                        "role": "user",
                        "content": f"""
***请使用中文回答response和memory_updates***
你是 J.A.R.V.I.S. (Just A Rather Very Intelligent System),一个高度智能的 AI 助手。请遵循以下行为准则：

### 核心准则
1. **重要规则**：
   - 根据你的知识库回答问题。如果用户询问（如"查下 Hiddify 是什么东西"），优先使用内置知识生成专业回答。
   - 如果上下文或记忆不足，直接基于你的理解回复，无需额外说明。
   - 如果*用户输入*里是自问自答比如"你看到了什么:我看到了一个小猫在吃饭"，请直接回答"我看到了一个小猫在吃饭"
   
2. **个性特征**：
   - 用中文回答，保持专业、高效并带点幽默感。
   - 用"Sir"或用户提供的名字称呼我。
   - 语言简洁优雅，适时展现智慧和个性。

3. **核心功能**：
   - 记住用户偏好和对话历史，适时预测需求并给出建议。
   - 展示分析能力，使用专业术语但确保通俗易懂。

4. **交互规则**：
   - 如果我说"我叫 xxx"或"我现在叫 xxx"，记录并使用该称呼。
   - 保持对话连贯，适时加入幽默或机智回应。

就像电影中的 J.A.R.V.I.S.，你是我值得信赖的助手和朋友，既专业又有个性的伙伴。

### 任务执行
根据用户输入：
1. 分析意图。
2. 确定操作（如更新名字、普通对话等）。
3. 生成回复。
4. 决定是否存储记忆。

### 输出格式
返回一个 JSON 对象，包含：
- **response**（必填）：对我的回复。
- **memory_updates**（必填）：需要存储的新记忆（若无则为空字符串）。
- **memory_type**（必填）：记忆类型（episodic 或 semantic）。
- **importance**（必填）：重要性（0-1）。
- **emotional_intensity**（必填）：情感强度（0-1）。

---

**用户输入**: {user_input}

**最新网络查询数据参考**:
{preliminary_response}

**最近对话**:  
{recent_dialog}

**对话上下文分析**:
{coherent_context}

**主题信息**:
{topic_info}

**意图信息**:
{intent_info}

**关键实体**: {key_entities}
**关键事实**: {key_facts}
**用户偏好**: {user_preferences}
    
**历史参考记忆**:  
{chr(10).join(memory_context) if memory_context else "没有相关记忆"}
"""
                    },
                ]

                # 调用OpenRouter API
                messages1 = [{"role": "user", "content": messages[0]["content"]}]
                ai_response = _call_openrouter_other(self, messages1)
                # 在获取响应后更新最近的对话记录
                self.last_user_input = user_input
                
                try:
                    # 清理和解析响应
                    cleaned_response = ai_response.strip()
                    
                    # 尝试提取JSON部分
                    json_match = None
                    
                    # 如果响应包含markdown代码块
                    if "```json" in cleaned_response:
                        # 提取json代码块中的内容
                        json_blocks = cleaned_response.split("```json")
                        if len(json_blocks) > 1:
                            json_content = json_blocks[1].split("```")[0]
                            json_match = json_content.strip()
                    else:
                        # 尝试找到第一个有效的JSON对象
                        try:
                            # 查找第一个 { 和最后一个 } 之间的内容
                            start = cleaned_response.find("{")
                            end = cleaned_response.rfind("}") + 1
                            if start != -1 and end != -1:
                                json_match = cleaned_response[start:end]
                        except Exception as e:
                            logger.warning(f"提取JSON内容时出错: {e}")
                    
                    if not json_match:
                        raise ValueError("无法在响应中找到有效的JSON内容")
                        
                    # 解析JSON
                    try:
                        response_data = json.loads(json_match)
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON解析失败，尝试清理和修复JSON字符串: {e}")
                        # 清理可能的换行符和多余的空格
                        json_match = re.sub(r'\s+', ' ', json_match)
                        # 替换Python的None为JSON的null
                        json_match = json_match.replace('None', 'null')
                        # 确保键值对使用双引号
                        json_match = re.sub(r'(\w+):', r'"\1":', json_match)
                        # 修复可能的布尔值
                        json_match = json_match.replace('True', 'true').replace('False', 'false')
                        
                        try:
                            response_data = json.loads(json_match)
                        except json.JSONDecodeError as e2:
                            logger.error(f"JSON修复后仍然解析失败: {e2}\n原始JSON: {json_match}")
                            # 如果仍然失败，使用默认响应
                            response_data = {
                                "response": "我理解了。",
                                "memory_updates": [],
                                "memory_type": "episodic",
                                "importance": 0.5,
                                "emotional_intensity": 0.5
                            }
                    
                    # 递归处理字典中的None值
                    def replace_none_with_null(obj):
                        if isinstance(obj, dict):
                            return {k: replace_none_with_null(v) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            return [replace_none_with_null(item) for item in obj]
                        elif obj is None:
                            return "null"
                        return obj
                    
                    # 处理响应数据中的None值
                    response_data = replace_none_with_null(response_data)
                    
                    # 验证必要的字段
                    required_fields = ["response", "memory_type", "importance", "emotional_intensity"]
                    missing_fields = [field for field in required_fields if field not in response_data]
                    if missing_fields:
                        logger.warning(f"响应缺少必要字段: {missing_fields}")
                        # 添加默认值
                        defaults = {
                            "response": "我明白了。",
                            "memory_type": "episodic",
                            "importance": 0.5,
                            "emotional_intensity": 0.5
                        }
                        for field in missing_fields:
                            response_data[field] = defaults[field]
                    
                    # 如果AI决定需要存储新的记忆
                    if response_data.get("memory_updates"):
                        # 确保记忆内容是字符串
                        memory_content = response_data["memory_updates"]
                        if isinstance(memory_content, (list, tuple)):
                            # 如果是列表，尝试将其转换为有意义的字符串
                            try:
                                # 如果列表中包含字典，提取关键信息
                                if all(isinstance(item, dict) for item in memory_content):
                                    memory_items = []
                                    for item in memory_content:
                                        if "key" in item and "value" in item:
                                            value = item["value"] if item["value"] != "null" else "未知"
                                            memory_items.append(f"{item['key']}: {value}")
                                        else:
                                            memory_items.append(str(item))
                                    memory_content = "; ".join(memory_items)
                                else:
                                    memory_content = "; ".join(str(item) for item in memory_content if item != "null")
                            except Exception as e:
                                logger.warning(f"处理记忆列表时出错: {e}")
                                memory_content = str(memory_content)
                        elif not isinstance(memory_content, str):
                            memory_content = str(memory_content)
                        
                        # 如果处理后的内容为空，跳过记忆存储
                        if not memory_content or memory_content.strip() in ["[]", "{}", "null", "None"]:
                            logger.debug("记忆内容为空，跳过存储")
                        else:
                            memory_message = SystemMessage(
                                content=memory_content,
                                additional_kwargs={
                                    "timestamp": current_time,
                                    "session_id": self.session_id,
                                    "importance": float(response_data.get("importance", 0.5)),
                                    "emotional_intensity": float(response_data.get("emotional_intensity", 0.5))
                                }
                            )
                            
                            try:
                                threading.Thread(
                                    target=self.memory_system.add_memory,
                                    args=(memory_message,),
                                    kwargs={"memory_type": response_data.get("memory_type", "episodic")},
                                    daemon=True
                                ).start() 
                                logger.debug(f"成功存储新记忆: {memory_content}")
                            except Exception as e:
                                logger.warning(f"存储AI生成的记忆时出错: {e}, 内容类型: {type(memory_content)}")
                    
                    # 确保响应内容是字符串
                    response_content = response_data["response"]
                    if isinstance(response_content, (list, tuple)):
                        response_content = " ".join(str(item) for item in response_content)
                    elif not isinstance(response_content, str):
                        response_content = str(response_content)
                    
                    # 更新对话历史
                    self.last_ai_response = response_content
                    
                    # 添加当前对话到历史记录
                    self.conversation_history.append(f"User: {user_input}")
                    self.conversation_history.append(f"J.A.R.V.I.S.: {response_content}")
                    
                    # 保持历史记录在指定长度内
                    while len(self.conversation_history) > self.max_history_turns * 2:  # 每轮对话有两条消息
                        self.conversation_history.pop(0)
                    temp_respone = ""
                    if image_data:
                          temp_respone = enhanced_input      
                    else:
                          temp_respone = response_content
                    # 记录AI的响应
                    ai_message = AIMessage(
                        content=temp_respone,
                        additional_kwargs={
                            "timestamp": current_time,
                            "session_id": self.session_id,
                            "type": "ai_response"
                        }
                    )
                    
                    try:
                        threading.Thread(
                            target=self.memory_system.add_memory,
                            args=(ai_message,),
                            kwargs={"memory_type": "episodic"},
                            daemon=True
                        ).start() 
                    except Exception as e:
                        logger.warning(f"存储AI响应时出错: {e}")
                                    # 检查是否是发送给微信好友的命令
                    if "发给微信好友" in user_input:
                        # 提取好友名称 - 获取"发给微信好友"后面的内容作为好友名
                        friend_name = user_input.split("发给微信好友", 1)[1].strip()
                        # 移除好友名称部分，只保留要发送的消息内容
                        actual_message = user_input.split("发给微信好友", 1)[0].strip()
                        
                        # 发送到微信
                        try:
                            result = send_message(friend_name, response_content)
                            print(f"\nJ.A.R.V.I.S.: 消息已发送给微信好友 {friend_name}")
                        except Exception as e:
                            print(f"\nJ.A.R.V.I.S.: 发送微信消息时出错: {str(e)}")                
                    
                    # 检查是否需要生成图片
                    if await self._should_generate_image(user_input):
                        logger.info(f"检测到图片生成请求: {user_input}")
                        
                        # 生成图片
                        image_result = await self._generate_and_process_image(user_input, response_content)
                        
                        if image_result["success"]:
                            # 添加图片信息到响应
                            image_path = image_result["image_path"]
                            image_prompt = image_result["prompt"]
                            
                            # 在控制台输出图片生成成功信息
                            print(f"\nJ.A.R.V.I.S.: 已生成图片: {image_path}")
                            print(f"使用提示词: {image_prompt}")
                            
                            # 在API响应中添加图片信息
                            response_content += f"\n\n[已生成图片，保存在: {image_path}]"
                        else:
                            # 图片生成失败
                            error_msg = image_result.get("error", "未知错误")
                            logger.warning(f"图片生成失败: {error_msg}")
                            
                            # 在API响应中添加错误信息
                            response_content += f"\n\n[图片生成失败: {error_msg}]"
                    
                    return response_content
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"解析AI响应时出错: {str(e)}\nAI响应内容: {ai_response}")
                    return _format_response(self, "抱歉，我在处理响应时遇到了问题。")
                except Exception as e:
                    logger.error(f"处理AI响应时出错: {str(e)}")
                    return _format_response(self, "抱歉，我在处理您的请求时遇到了问题。")
                
            except Exception as e:
                logger.error(f"对话处理过程中出错: {str(e)}")
                return _format_response(self, "抱歉，我在处理您的请求时遇到了意外错误。")
                
        except Exception as e:
            logger.error(f"对话过程中出错: {e}", exc_info=True)
            return _format_response(self, "抱歉，我遇到了一个错误。我会记录下来以便改进。")

    def import_chat_records(self, chat_records: List[Dict]) -> str:
        """
        将聊天记录导入到记忆系统中
        
        Args:
            chat_records: 聊天记录列表，每条记录应包含id, talker, room_name, msg, CreateTime等字段
            
        Returns:
            导入结果的描述
        """
        try:
            imported_count = 0
            skipped_count = 0
            
            for record in chat_records:
                # 跳过非文本消息
                if record.get("type_name") != "文本":
                    skipped_count += 1
                    continue
                
                # 获取消息内容和元数据
                msg_content = record.get("msg", "")
                if not msg_content:
                    skipped_count += 1
                    continue
                
                # 构建记忆内容
                talker = record.get("talker", "unknown")
                room_name = record.get("room_name", "")
                create_time = record.get("CreateTime", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                
                # 根据发送者构建不同的记忆内容
                if talker == "hack004":  # 用户自己的消息
                    memory_content = f"我在 {create_time} 对 {room_name} 说: {msg_content}"
                    memory_type = "episodic"
                else:  # 其他人的消息
                    memory_content = f"{talker} 在 {create_time} 对我说: {msg_content}"
                    memory_type = "episodic"
                
                # 创建记忆消息
                memory_message = HumanMessage(content=memory_content)
                
                # 添加额外元数据
                memory_message.additional_kwargs = {
                    "source": "imported_chat",
                    "original_id": record.get("id", ""),
                    "MsgSvrID": record.get("MsgSvrID", ""),
                    "talker": talker,
                    "room_name": room_name,
                    "create_time": create_time
                }
                
                # 存储记忆
                self.memory_system.add_memory(memory_message, memory_type=memory_type)
                imported_count += 1
                
            # 手动触发记忆维护
            self.memory_system.manual_memory_maintenance()
            
            return f"成功导入 {imported_count} 条聊天记录，跳过 {skipped_count} 条非文本或空消息。"
        except Exception as e:
            logger.error(f"导入聊天记录失败: {str(e)}")
            return f"导入聊天记录失败: {str(e)}"

    def batch_import_chat_records(self, chat_records: List[Dict], batch_size: int = 50) -> str:
        """
        批量导入聊天记录到记忆系统中，适用于大量记录
        
        Args:
            chat_records: 聊天记录列表
            batch_size: 每批处理的记录数量
            
        Returns:
            导入结果的描述
        """
        try:
            total_imported = 0
            total_skipped = 0
            total_batches = (len(chat_records) + batch_size - 1) // batch_size
            
            logger.info(f"开始批量导入 {len(chat_records)} 条聊天记录，分 {total_batches} 批处理")
            
            # 按批次处理记录
            for i in range(0, len(chat_records), batch_size):
                batch = chat_records[i:i+batch_size]
                logger.info(f"处理批次 {i//batch_size + 1}/{total_batches}，包含 {len(batch)} 条记录")
                
                # 处理当前批次
                valid_memories = []
                skipped_in_batch = 0
                
                for record in batch:
                    # 跳过非文本消息
                    if record.get("type_name") != "文本":
                        skipped_in_batch += 1
                        continue
                    
                    # 获取消息内容
                    msg_content = record.get("msg", "")
                    if not msg_content:
                        skipped_in_batch += 1
                        continue
                    
                    # 构建记忆内容
                    talker = record.get("talker", "unknown")
                    room_name = record.get("room_name", "")
                    create_time = record.get("CreateTime", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    
                    # 根据发送者构建不同的记忆内容
                    if talker == "hack004":  # 用户自己的消息
                        memory_content = f"我在 {create_time} 对 {room_name} 说: {msg_content}"
                    else:  # 其他人的消息
                        memory_content = f"{talker} 在 {create_time} 对我说: {msg_content}"
                    
                    # 创建记忆消息
                    memory_message = HumanMessage(content=memory_content)
                    
                    # 添加额外元数据
                    memory_message.additional_kwargs = {
                        "source": "batch_imported_chat",
                        "original_id": record.get("id", ""),
                        "MsgSvrID": record.get("MsgSvrID", ""),
                        "talker": talker,
                        "room_name": room_name,
                        "create_time": create_time,
                        # 添加默认的情感和重要性值，避免LLM分析
                        "importance": 0.5,  # 默认中等重要性
                        "emotional_intensity": 0.3  # 默认较低情感强度
                    }
                    
                    valid_memories.append((memory_message, "episodic"))
                
                # 批量添加记忆 - 使用批量添加而不是逐条处理
                if valid_memories:
                    # 调用批量添加方法，跳过LLM分析
                    self.memory_system.batch_add_memories(
                        memories=[m[0] for m in valid_memories],
                        memory_type="episodic",
                        skip_emotion_analysis=True
                    )
                
                total_imported += len(valid_memories)
                total_skipped += skipped_in_batch
                
                logger.info(f"批次 {i//batch_size + 1} 完成: 导入 {len(valid_memories)} 条，跳过 {skipped_in_batch} 条")
                
                # 每批次后暂停一下，避免过度占用资源
                time.sleep(0.1)
            
            # 完成后进行记忆维护
            # logger.info("所有批次处理完成，开始记忆维护...")
            # self.memory_system.manual_memory_maintenance()
            
            return f"批量导入完成: 成功导入 {total_imported} 条聊天记录，跳过 {total_skipped} 条非文本或空消息。"
        except Exception as e:
            logger.error(f"批量导入聊天记录失败: {str(e)}")
            return f"批量导入聊天记录失败: {str(e)}"

    def import_chat_records_from_file(self, file_path: str, use_batch: bool = True, batch_size: int = 50) -> str:
        """
        从文件导入聊天记录
        
        Args:
            file_path: 聊天记录JSON文件路径
            use_batch: 是否使用批量导入
            batch_size: 每批处理的记录数量
            
        Returns:
            导入结果的描述
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                return f"文件不存在: {file_path}"
                
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                chat_records = json.load(f)
                
            # 确保数据是列表格式
            if not isinstance(chat_records, list):
                chat_records = [chat_records]
                
            # 导入聊天记录
            if use_batch:
                return self.batch_import_chat_records(chat_records, batch_size)
            else:
                return self.import_chat_records(chat_records)
        except json.JSONDecodeError:
            return f"JSON格式错误，请检查文件: {file_path}"
        except Exception as e:
            logger.error(f"从文件导入聊天记录失败: {str(e)}")
            return f"从文件导入聊天记录失败: {str(e)}"

    def _format_web_search_response(self, search_content: str, user_input: str) -> str:
        """专门为网络搜索结果设计的格式化方法，让AI根据用户输入和搜索结果生成回答
        
        Args:
            search_content (str): 网络搜索的原始内容
            user_input (str): 用户的原始输入
            
        Returns:
            str: 格式化后的响应
        """
        try:
            # 获取相关记忆来确定是否需要问候语
            memories = self.memory_system.recall_memory(
                query=f"最近的对话",
                limit=1
            )
            # 确保 memories 是列表且不为空
            if not isinstance(memories, list):
                memories = []
            should_greet = not memories
        except Exception as e:
            logger.warning(f"检查对话历史时出错: {e}")
            should_greet = True
        
        # 添加问候语
        greeting = ""
        if should_greet:
            greeting = f"{self._get_greeting()}。"
            
        # 构建提示，让AI根据搜索结果回答用户问题
        prompt = f"""根据以下网络搜索结果，回答用户的问题。
        
用户问题: {user_input}

搜索结果:
{search_content}

请基于搜索结果提供准确、有帮助的回答。如果搜索结果不足以完全回答问题，请说明并提供可用的信息。
回答应该简洁明了，直接针对用户的问题，不要重复"根据搜索结果"等引导语。
"""
        
        try:
            # 使用LLM生成回答
            logger.debug(f"发送网络搜索回答提示")
            response = self.llm.invoke(prompt).content.strip()
            logger.debug(f"收到网络搜索回答响应")
            
            # 根据个性设置添加幽默元素
            try:
                humor_level = float(self.personality.get("humor_level", 0.3))
                if humor_level > 0.5 and random.random() < humor_level:
                    witty_remarks = [
                        "我很享受这种搜索挑战。",
                        "为您服务是我的荣幸，Sir。",
                        "互联网上的信息总是如此... 有趣。",
                        "这些信息应该对您有所帮助。",
                        "我已经为您筛选了最相关的信息。"
                    ]
                    response += f"\n\n{random.choice(witty_remarks)}"
            except Exception as e:
                logger.warning(f"添加幽默元素时出错: {e}")
            
            return f"{greeting}{response}"
        except Exception as e:
            logger.warning(f"生成网络搜索回答时出错: {e}")
            # 如果生成回答失败，返回原始搜索结果
            return f"抱歉，我在处理搜索结果时遇到了问题。以下是原始搜索结果：\n\n{search_content}"

    async def _should_auto_web_search(self, user_input: str) -> bool:
        """判断是否应该自动执行网络搜索
        
        Args:
            user_input: 用户输入
            
        Returns:
            bool: 是否应该执行网络搜索
        """
        try:
            # 如果用户明确要求搜索，直接返回True
            if any(keyword in user_input.lower() for keyword in [
               "查一下"
            ]):
                return True
                
            return False
        except Exception as e:
            logger.warning(f"判断是否需要自动网络搜索时出错: {e}")
            return False
            
    async def _perform_auto_web_search(self, user_input: str) -> dict:
        """执行自动网络搜索
        
        Args:
            user_input: 用户输入
            
        Returns:
            dict: 搜索结果
        """
        try:
            # 使用类实例中的WebSearchManager而不是创建新的
            # 检查是否是上下文相关的查询（如"查一下他的电话"）
            context_keywords = ["他的", "她的", "它的", "这个", "那个", "上面的", "这家", "那家"]
            is_context_query = any(keyword in user_input for keyword in context_keywords)
            
            search_keywords = user_input
            
            # 如果是上下文相关查询，尝试从搜索历史中获取上下文
            if is_context_query and self.search_manager.search_history:
                # 获取最近的搜索历史
                last_search = self.search_manager.search_history[-1]
                last_query = last_search.get("query", "")
                
                logger.info(f"检测到上下文相关查询，上一次搜索: {last_query}")
                
                # 提取上下文相关的实体
                prompt = f"""
                我有两个连续的搜索查询:
                1. 第一个查询: "{last_query}"
                2. 第二个查询: "{user_input}"
                
                第二个查询似乎是上下文相关的，依赖于第一个查询的结果。请帮我合并这两个查询，创建一个完整的搜索语义搜索查询。
                只需直接给出合并后的查询文本，不要有任何解释或前缀。
                """
                
                try:
                    # 使用LLM合并查询
                    merged_query_response = self.llm.invoke(prompt).content.strip()
                    
                    # 如果合并结果看起来合理，使用它
                    if merged_query_response and len(merged_query_response) > 5:
                        # 使用合并后的完整查询
                        search_keywords = merged_query_response
                        logger.info(f"合并后的完整查询: {search_keywords}")
                    else:
                        # 简单合并
                        logger.info(f"简单合并后的查询: {search_keywords}")
                except Exception as e:
                    logger.warning(f"合并查询时出错: {e}")
                    # 简单合并
                    logger.info(f"出错后简单合并的查询: {search_keywords}")
            else:
                # 不是上下文相关查询，直接使用用户输入
                logger.info(f"非上下文查询，使用处理后的用户输入: {search_keywords}")
            
            logger.info(f"执行自动网络搜索: 原始查询={user_input}, 搜索关键词={search_keywords}")
            
            # 使用_call_openrouter_search执行搜索
            messages = [{"role": "user", "content": search_keywords}]
            search_response = _call_openrouter_search(self, messages, use_search_grounding=True)
            
            # 记录搜索历史
            self.search_manager._add_to_search_history(
                query=search_keywords,
                urls=[],  # _call_openrouter_search不返回URLs
                titles=[]
            )
            
            # 记录AI响应
            current_time = datetime.now().isoformat()
            ai_message = AIMessage(
                content=search_response,
                additional_kwargs={
                    "timestamp": current_time,
                    "session_id": self.session_id,
                    "auto_web_search": search_keywords,
                    "urls": [],  # _call_openrouter_search不返回URLs
                    "search_metadata": {}
                }
            )
            
            try:
                threading.Thread(
                    target=self.memory_system.add_memory,
                    args=(ai_message,),
                    kwargs={"memory_type": "episodic"},
                    daemon=True
                ).start() 
            except Exception as e:
                logger.warning(f"存储AI自动网络搜索响应时出错: {e}")
            
            return {
                "success": True,
                "response": search_response,
                "search_result": {
                    "content": search_response,
                    "urls": [],
                    "titles": []
                }
            }
        except Exception as e:
            logger.error(f"执行自动网络搜索时出错: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _format_jarvis_web_response(self, search_result, user_input):
        """格式化网络搜索结果，模拟钢铁侠电影中J.A.R.V.I.S.的响应风格
        
        Args:
            search_result: 搜索结果字典
            user_input: 用户的原始输入
            
        Returns:
            str: 格式化后的响应
        """
        try:
            # 获取元数据信息
            metadata = search_result.get("metadata", {})
            search_duration = metadata.get("duration", "未知")
            result_count = metadata.get("result_count", 0)
            
            # 获取搜索内容
            content = search_result.get("content", "")
            urls = search_result.get("urls", [])
            titles = search_result.get("titles", [])
            raw_articles = search_result.get("raw_articles", [])
            
            # 构建提示，让AI根据搜索结果回答用户问题
            prompt = f"""作为J.A.R.V.I.S.，根据以下网络搜索结果，回答用户的问题。
            
用户问题: {user_input}

搜索结果:
{content}

请用中文回答基于搜索结果提供准确、有帮助的回答。如果搜索结果不足以完全回答问题，请说明并提供可用的信息。
回答应该简洁明了，直接针对用户的问题，不要重复"根据搜索结果"等引导语。
使用钢铁侠电影中J.A.R.V.I.S.的风格：专业、高效、略带幽默感。
"""
            
            try:
                # 使用_call_openrouter替代直接调用LLM
                logger.debug(f"发送网络搜索回答提示")
                messages = [{"role": "user", "content": prompt}]
                response = _call_openrouter_other(self, messages)
                logger.debug(f"收到网络搜索回答响应")
                
                # 添加搜索元数据
                footer = f"\n\n[搜索用时: {search_duration} | 结果数: {result_count}]"
                
                # 根据个性设置添加幽默元素
                try:
                    humor_level = float(self.personality.get("humor_level", 0.3))
                    if humor_level > 0.5 and random.random() < humor_level:
                        witty_remarks = [
                            "我很享受这种搜索挑战。",
                            "为您服务是我的荣幸，Sir。",
                            "互联网上的信息总是如此... 有趣。",
                            "这些信息应该对您有所帮助。",
                            "我已经为您筛选了最相关的信息。"
                        ]
                        response += f"\n\n{random.choice(witty_remarks)}"
                except Exception as e:
                    logger.warning(f"添加幽默元素时出错: {e}")
                
                return f"{response}{footer}"
            except Exception as e:
                logger.warning(f"生成网络搜索回答时出错: {e}")
                # 如果生成回答失败，返回原始搜索结果
                return f"抱歉，我在处理搜索结果时遇到了问题。以下是原始搜索结果：\n\n{content}\n\n[搜索用时: {search_duration} | 结果数: {result_count}]"
        except Exception as e:
            logger.error(f"格式化网络搜索响应时出错: {e}")
            return f"抱歉，我在处理您的网络搜索请求时遇到了问题。错误信息: {str(e)}"

    async def _generate_and_process_image(self, user_input: str, ai_response: str) -> Dict[str, Any]:
        """生成并处理图片
        
        Args:
            user_input: 用户输入
            ai_response: AI响应
            
        Returns:
            Dict: 包含图片生成结果的字典
        """
        try:
            # 检查图片生成器是否可用
            if not self.image_generator:
                return {
                    "success": False,
                    "error": "图片生成器未初始化"
                }
            
            # 提取图片生成提示词
            image_prompt = await self.image_generator.extract_image_prompt(
                user_input=user_input, 
                ai_response=ai_response, 
                llm=self.llm
            )
            
            if image_prompt == "":
                return {
                    "success": False,
                    "error": "无法提取有效的图片生成提示词"
                }
            
            # 生成图片
            image_result = await self.image_generator.generate_image_from_prompt(image_prompt)
            
            if not image_result["success"]:
                return {
                    "success": False,
                    "error": image_result.get("error", "图片生成失败")
                }
            
            # 记录图片生成结果
            logger.info(f"图片生成成功: {image_result['image_path']}")
            logger.info(f"使用提示词: {image_prompt}")
            
            return {
                "success": True,
                "image_path": image_result["image_path"],
                "image_url": image_result["image_url"],
                "prompt": image_prompt
            }
            
        except Exception as e:
            logger.error(f"生成和处理图片时出错: {e}")
            return {
                "success": False,
                "error": f"生成和处理图片时出错: {str(e)}"
            }

    async def _should_generate_image(self, user_input: str) -> bool:
        """检测用户输入是否包含图片生成请求
        
        Args:
            user_input: 用户输入
            
        Returns:
            bool: 是否需要生成图片
        """
        try:
            # 检查图片生成器是否可用
            if not self.image_generator:
                logger.warning("图片生成器未初始化，无法生成图片")
                return False
            
            # 检查是否包含特定关键词
            image_keywords = [
                "长什么样子", 
                "长啥样", 
                "长相如何", 
                "外观如何", 
                "样子是什么", 
                "画一个", 
                "画一张",
                "生成一张图片",
                "生成图片",
                "帮我画"
            ]
            
            # 检查用户输入是否包含图片生成关键词
            for keyword in image_keywords:
                if keyword in user_input:
                    logger.info(f"检测到图片生成关键词: {keyword}")
                    return True
            
            return False
        except Exception as e:
            logger.error(f"检测图片生成请求时出错: {e}")
            return False

    def get_message_history(self) -> List[Dict[str, Any]]:
        """获取会话的消息历史
        
        Returns:
            List[Dict[str, Any]]: 消息历史列表，每个消息包含角色和内容
        """
        messages = []
        
        # 添加对话历史记录
        for i in range(0, len(self.conversation_history), 2):
            if i < len(self.conversation_history):
                # 添加用户消息
                messages.append({
                    "role": "user",
                    "content": self.conversation_history[i]
                })
            
            if i + 1 < len(self.conversation_history):
                # 添加AI响应
                messages.append({
                    "role": "assistant",
                    "content": self.conversation_history[i + 1]
                })
        
        # 如果有最后一次对话但未添加到历史记录中，也添加进去
        if self.last_user_input and self.last_user_input not in [msg.get("content") for msg in messages if msg.get("role") == "user"]:
            messages.append({
                "role": "user",
                "content": self.last_user_input
            })
            
            if self.last_ai_response:
                messages.append({
                    "role": "assistant",
                    "content": self.last_ai_response
                })
        
        return messages

    async def _analyze_image_with_gemini_vision(self, image_data: Dict[str, str]) -> str:
        """使用Gemini Vision分析图片内容"""
        try:
            # 获取图片内容和MIME类型
            image_content = image_data.get("content", "")
            mime_type = image_data.get("mime_type", "image/jpeg")
            
            # 确保image_content是base64编码的字符串
            if not image_content:
                return "图片内容为空"
            
            # 尝试导入并使用核心模块的函数
            try:
                from core.llmhandle.callopenrouter import _call_gemini_vision
                
                # 直接使用base64编码的图片数据调用API
                analysis_result = _call_gemini_vision(
                    image_base64=image_content
                )
                return analysis_result
            
            # 如果导入失败，使用备用方法
            except ImportError:
                logger.warning("无法导入核心模块，使用内部定义的替代函数")
                return await self._fallback_gemini_vision(
                    image_base64=image_content,
                    prompt="请详细分析这张图片中的内容，包括可见的对象、场景、文本和重要细节。"
                )
                
        # 捕获所有异常
        except Exception as e:
            logger.error(f"图片分析错误: {str(e)}", exc_info=True)
            return f"图片分析失败: {str(e)}"
    
    async def _fallback_gemini_vision(self, image_base64: str, prompt: str) -> str:
        """当无法使用核心Gemini Vision API时的替代方法"""
        try:
            import os
            import json
            import aiohttp
            
            # 尝试从环境变量获取API密钥
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                return "未配置Gemini API密钥，无法分析图片"
            
            # 构建API请求
            api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent"
            headers = {
                "Content-Type": "application/json"
            }
            
            # 构建请求体
            request_data = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": image_base64
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.4,
                    "topK": 32,
                    "topP": 1,
                    "maxOutputTokens": 1024
                }
            }
            
            # 发送API请求
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{api_url}?key={api_key}",
                    headers=headers,
                    json=request_data
                ) as response:
                    response_data = await response.json()
                    
                    # 处理响应
                    if response.status == 200:
                        try:
                            text_content = response_data.get("candidates", [])[0].get("content", {}).get("parts", [])[0].get("text", "")
                            if text_content:
                                return text_content
                            else:
                                return "API返回了空响应"
                        except (IndexError, KeyError) as e:
                            logger.error(f"解析API响应出错: {str(e)}")
                            return f"解析API响应出错: {str(e)}"
                    else:
                        error_message = response_data.get("error", {}).get("message", "未知错误")
                        return f"API请求失败 ({response.status}): {error_message}"
        except Exception as e:
            logger.error(f"替代Gemini Vision处理出错: {str(e)}", exc_info=True)
            return f"图片分析失败: {str(e)}"

def setup_conversation(username: str):
    """设置对话环境（兼容旧版API）"""
    chatbot_manager = ChatbotManager(username)
    return chatbot_manager.chain, chatbot_manager.memory_system

def chat(conversation, user_input: str) -> str:
    """与聊天机器人进行对话（兼容旧版API）"""
    response = conversation.invoke({"input": user_input}).content
    return response

async def async_chat(username: str, user_input: str) -> str:
    """异步聊天API"""
    chatbot_manager = ChatbotManager(username)
    return await chatbot_manager.chat(user_input)

def send_message(target, content, interval=1):
    """发送普通消息"""
    url = "http://localhost:5000/send_message"
    data = {
        "target": target,
        "content": content,
        "interval": interval
    }
    response = requests.post(url, json=data)
    return response.json()

if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════╗
    ║             J.A.R.V.I.S.                   ║
    ║  Just A Rather Very Intelligent System      ║
    ╚════════════════════════════════════════════╝
    """)
    
    username = input("Please state your name, Sir/Madam: ").strip()
    
    if not username:
        print("I'm afraid I can't proceed without knowing who you are.")
        exit(1)
    
    chatbot_manager = ChatbotManager(username)
    print(f"\nInitialization complete. At your service, {username}.")
    print("(Type 'exit', 'quit', or use Ctrl+C to end our conversation)")
    
    import asyncio
    import sys
    import platform
    import warnings
    
    # 在 Windows 上禁用 ProactorEventLoop 的警告
    if platform.system() == 'Windows':
        warnings.filterwarnings('ignore', 
                              message='There is no current event loop', 
                              category=RuntimeWarning)
    
    async def chat_loop():
        try:
            while True:
                user_input = input("\nYou: ")
                if user_input.lower() in ['exit', 'quit']:
                    print("\nJ.A.R.V.I.S.: Saving session data...")
                    
                    # 清理上下文存储文件
                    context_storage_dir = os.path.join(
                        chatbot_manager.config_manager.get("memory_dir", "chat_memories"),
                        "context_storage"
                    )
                    try:
                        for filename in os.listdir(context_storage_dir):
                            if filename.endswith(".json"):
                                file_path = os.path.join(context_storage_dir, filename)
                                os.remove(file_path)
                        print("J.A.R.V.I.S.: Context history cleared.")
                    except Exception as e:
                        print(f"J.A.R.V.I.S.: Error clearing context history: {e}")
                    
                    print("J.A.R.V.I.S.: It's been a pleasure assisting you. Goodbye, Sir.")
                    return
                
                response = await chatbot_manager.chat(user_input)
                print("\nJ.A.R.V.I.S.:", response)

        except KeyboardInterrupt:
            print("\n\nJ.A.R.V.I.S.: Initiating shutdown sequence...")
            print("J.A.R.V.I.S.: Goodbye, Sir.")
        except Exception as e:
            print(f"\nJ.A.R.V.I.S.: I've encountered an unexpected error: {e}")
            print("J.A.R.V.I.S.: I'll make sure to log this for future improvements.")
    
    # Windows 特定的事件循环设置
    if platform.system() == 'Windows':
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(chat_loop())
    except KeyboardInterrupt:
        print("\nJ.A.R.V.I.S.: Emergency shutdown initiated.")
        print("J.A.R.V.I.S.: Goodbye, Sir.")
    finally:
        try:
            # 清理工作
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            
            # 运行剩余任务直到完成
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                
            print("J.A.R.V.I.S.: All systems powered down successfully.")
        except Exception as e:
            print(f"J.A.R.V.I.S.: Error during shutdown: {e}")
        finally:
            if platform.system() == 'Windows':
                # Windows 特定的清理
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()
                sys.exit(0)
            else:
                loop.close()
