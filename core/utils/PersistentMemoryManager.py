import os
import json
import time
import hashlib
from datetime import datetime
from typing import Dict, Any, List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from core.utils.ConfigManager import ConfigManager

class PersistentMemoryManager:
    """持久化记忆管理器"""
    
    def __init__(self, username: str, config_manager: ConfigManager):
        self._username = username
        self._config_manager = config_manager
        self._memory_dir = config_manager.get("memory_dir", "chat_memories")
        self._memory_file = os.path.join(self._memory_dir, f"{self._get_safe_filename(username)}_memory.json")
        self._summary = ""
        self._conversation_id = self._generate_conversation_id()
        self._max_token_limit = config_manager.get("max_token_limit", 4000)
        self._summary_threshold = config_manager.get("summary_threshold", 10)
        self._messages = []
        self._load_memory()
    
    def _get_safe_filename(self, filename: str) -> str:
        """生成安全的文件名"""
        # 移除不安全的字符
        safe_filename = ''.join(c for c in filename if c.isalnum() or c in '_-')
        return safe_filename
    
    def _generate_conversation_id(self) -> str:
        """生成唯一的对话ID"""
        unique_string = f"{self._username}_{datetime.now().isoformat()}"
        return hashlib.md5(unique_string.encode()).hexdigest()
    
    def _create_message(self, msg_data: Dict[str, Any]) -> BaseMessage:
        """根据消息类型创建对应的消息对象"""
        msg_type = msg_data.get("type", "")
        content = msg_data.get("content", "")
        additional_kwargs = msg_data.get("additional_kwargs", {})

        if msg_type == "human":
            return HumanMessage(content=content, additional_kwargs=additional_kwargs)
        elif msg_type == "ai":
            return AIMessage(content=content, additional_kwargs=additional_kwargs)
        elif msg_type == "system":
            return SystemMessage(content=content, additional_kwargs=additional_kwargs)
        else:
            logger.warning(f"不支持的消息类型: {msg_type}，使用默认人类消息类型")
            return HumanMessage(content=content, additional_kwargs=additional_kwargs)

    def _load_memory(self) -> None:
        """从文件加载历史记忆"""
        if not os.path.exists(self._memory_dir):
            os.makedirs(self._memory_dir)
        
        if os.path.exists(self._memory_file):
            try:
                with open(self._memory_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._summary = data.get('summary', '')
                    self._conversation_id = data.get('conversation_id', self._conversation_id)
                    messages_data = data.get('messages', [])
                    
                    # 检查是否需要进行记忆压缩
                    if len(messages_data) > self._max_token_limit:
                        logger.info(f"记忆超过最大限制，进行压缩")
                        self._compress_memory(messages_data)
                    else:
                        for msg in messages_data:
                            if isinstance(msg, dict):
                                message = self._create_message(msg)
                                self._messages.append(message)
                
                logger.info(f"已加载用户 {self._username} 的对话记忆")
            except Exception as e:
                logger.error(f"加载记忆时出错: {e}")
                # 创建备份
                if os.path.exists(self._memory_file):
                    backup_file = f"{self._memory_file}.bak.{int(time.time())}"
                    try:
                        os.rename(self._memory_file, backup_file)
                        logger.info(f"已创建损坏记忆文件的备份: {backup_file}")
                    except Exception as backup_err:
                        logger.error(f"创建备份时出错: {backup_err}")

    def _compress_memory(self, messages_data: List[Dict[str, Any]]) -> None:
        """压缩记忆以保持在token限制内"""
        # 保留最新的一部分消息
        recent_messages = messages_data[-self._summary_threshold:]
        
        # 如果有摘要，添加摘要作为系统消息
        if self._summary:
            system_message = {
                "type": "system",
                "content": f"以下是之前对话的摘要: {self._summary}",
                "additional_kwargs": {}
            }
            self._messages.append(self._create_message(system_message))
        
        # 添加最近的消息
        for msg in recent_messages:
            if isinstance(msg, dict):
                message = self._create_message(msg)
                self._messages.append(message)

    def _should_summarize(self) -> bool:
        """判断是否应该对对话进行总结"""
        message_count = len(self._messages)
        return message_count > 0 and message_count % self._summary_threshold == 0

    async def summarize_conversation(self, llm) -> str:
        """使用LLM总结当前对话"""
        if not self._should_summarize():
            return self._summary
        
        try:
            messages_text = "\n".join([
                f"{msg.type}: {msg.content}" 
                for msg in self._messages
            ])
            
            prompt = PromptTemplate.from_template(
                "请总结以下对话，保留重要的信息点和上下文，以便未来参考：\n\n{messages}\n\n总结："
            )
            
            chain = prompt | llm | StrOutputParser()
            self._summary = await chain.ainvoke({"messages": messages_text})
            logger.info("对话已总结")
            return self._summary
        except Exception as e:
            logger.error(f"总结对话时出错: {e}")
            return self._summary

    def save_memory(self) -> None:
        """保存记忆到文件"""
        try:
            messages = [
                {
                    "type": msg.type,
                    "content": msg.content,
                    "additional_kwargs": msg.additional_kwargs
                }
                for msg in self._messages
            ]
            
            with open(self._memory_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'username': self._username,
                    'conversation_id': self._conversation_id,
                    'last_updated': datetime.now().isoformat(),
                    'summary': self._summary,
                    'messages': messages
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存用户 {self._username} 的对话记忆")
        except Exception as e:
            logger.error(f"保存记忆时出错: {e}")

    def clear(self) -> None:
        """清除当前记忆"""
        self._messages = []
        self._summary = ""
        logger.info(f"已清除用户 {self._username} 的对话记忆")
    
    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self._messages.append(HumanMessage(content=content))
    
    def add_ai_message(self, content: str) -> None:
        """添加AI消息"""
        self._messages.append(AIMessage(content=content))
    
    def get_messages(self) -> List[BaseMessage]:
        """获取所有消息"""
        return self._messages
    
    def get_conversation_id(self) -> str:
        """获取对话ID"""
        return self._conversation_id