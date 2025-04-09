import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import threading

logger = logging.getLogger(__name__)

class ConversationContextStorage:
    """
    存储和管理对话上下文数据，支持会话间的上下文持久化
    """
    
    def __init__(self, storage_dir: str = "conversation_contexts"):
        """
        初始化上下文存储
        
        Args:
            storage_dir: 存储上下文数据的目录
        """
        self.storage_dir = storage_dir
        self.contexts = {}  # 会话ID -> 上下文数据
        self.lock = threading.RLock()  # 用于线程安全的锁
        
        # 确保存储目录存在
        os.makedirs(storage_dir, exist_ok=True)
        
        # 加载现有上下文数据
        self._load_contexts()
        
        logger.info(f"对话上下文存储初始化完成，存储目录: {storage_dir}")
    
    def _load_contexts(self):
        """加载所有现有的上下文数据"""
        try:
            with self.lock:
                for filename in os.listdir(self.storage_dir):
                    if filename.endswith(".json"):
                        session_id = filename.replace(".json", "")
                        file_path = os.path.join(self.storage_dir, filename)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                context_data = json.load(f)
                                self.contexts[session_id] = context_data
                        except Exception as e:
                            logger.warning(f"加载上下文文件 {filename} 时出错: {e}")
                
                logger.info(f"已加载 {len(self.contexts)} 个会话的上下文数据")
        except Exception as e:
            logger.error(f"加载上下文数据时出错: {e}")
    
    def save_context(self, session_id: str, context_data: Dict[str, Any]):
        """
        保存会话上下文数据
        
        Args:
            session_id: 会话ID
            context_data: 上下文数据
        """
        try:
            with self.lock:
                # 添加时间戳
                context_data["last_updated"] = datetime.now().isoformat()
                
                # 更新内存中的数据
                self.contexts[session_id] = context_data
                
                # 保存到文件
                file_path = os.path.join(self.storage_dir, f"{session_id}.json")
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(context_data, f, ensure_ascii=False, indent=2)
                
                logger.debug(f"已保存会话 {session_id} 的上下文数据")
        except Exception as e:
            logger.error(f"保存会话 {session_id} 的上下文数据时出错: {e}")
    
    def get_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取会话上下文数据
        
        Args:
            session_id: 会话ID
            
        Returns:
            Dict 或 None: 上下文数据，如果不存在则返回None
        """
        with self.lock:
            return self.contexts.get(session_id)
    
    def update_context(self, session_id: str, context_updates: Dict[str, Any]):
        """
        更新会话上下文数据
        
        Args:
            session_id: 会话ID
            context_updates: 要更新的上下文数据
        """
        try:
            with self.lock:
                # 获取现有上下文或创建新的
                current_context = self.contexts.get(session_id, {})
                
                # 更新上下文
                current_context.update(context_updates)
                
                # 保存更新后的上下文
                self.save_context(session_id, current_context)
        except Exception as e:
            logger.error(f"更新会话 {session_id} 的上下文数据时出错: {e}")
    
    def delete_context(self, session_id: str):
        """
        删除会话上下文数据
        
        Args:
            session_id: 会话ID
        """
        try:
            with self.lock:
                # 从内存中删除
                if session_id in self.contexts:
                    del self.contexts[session_id]
                
                # 从文件系统中删除
                file_path = os.path.join(self.storage_dir, f"{session_id}.json")
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
                logger.info(f"已删除会话 {session_id} 的上下文数据")
        except Exception as e:
            logger.error(f"删除会话 {session_id} 的上下文数据时出错: {e}")
    
    def get_all_sessions(self) -> List[str]:
        """
        获取所有会话ID
        
        Returns:
            List[str]: 会话ID列表
        """
        with self.lock:
            return list(self.contexts.keys())
    
    def cleanup_old_sessions(self, days: int = 30):
        """
        清理超过指定天数的旧会话
        
        Args:
            days: 天数阈值，默认30天
        """
        try:
            with self.lock:
                now = datetime.now()
                sessions_to_delete = []
                
                for session_id, context in self.contexts.items():
                    last_updated_str = context.get("last_updated")
                    if not last_updated_str:
                        continue
                        
                    try:
                        last_updated = datetime.fromisoformat(last_updated_str)
                        days_diff = (now - last_updated).days
                        
                        if days_diff > days:
                            sessions_to_delete.append(session_id)
                    except Exception as e:
                        logger.warning(f"解析会话 {session_id} 的更新时间时出错: {e}")
                
                # 删除旧会话
                for session_id in sessions_to_delete:
                    self.delete_context(session_id)
                    
                logger.info(f"已清理 {len(sessions_to_delete)} 个超过 {days} 天的旧会话")
        except Exception as e:
            logger.error(f"清理旧会话时出错: {e}")
    
    def track_topic_history(self, session_id: str, topic_analysis: Dict[str, Any], max_history: int = 10):
        """
        跟踪会话的主题历史
        
        Args:
            session_id: 会话ID
            topic_analysis: 主题分析结果
            max_history: 最大历史记录数
        """
        try:
            with self.lock:
                # 获取现有上下文
                current_context = self.contexts.get(session_id, {})
                
                # 获取主题历史或创建新的
                topic_history = current_context.get("topic_history", [])
                
                # 添加新主题
                if "main_topic" in topic_analysis:
                    new_topic_entry = {
                        "topic": topic_analysis["main_topic"],
                        "timestamp": datetime.now().isoformat(),
                        "sub_topics": topic_analysis.get("sub_topics", []),
                        "keywords": topic_analysis.get("topic_keywords", [])
                    }
                    
                    # 检查是否与上一个主题相同
                    if topic_history and topic_history[-1]["topic"] == new_topic_entry["topic"]:
                        # 更新时间戳和可能的子主题/关键词
                        topic_history[-1] = new_topic_entry
                    else:
                        # 添加新主题
                        topic_history.append(new_topic_entry)
                    
                    # 限制历史记录数量
                    if len(topic_history) > max_history:
                        topic_history = topic_history[-max_history:]
                    
                    # 更新上下文
                    current_context["topic_history"] = topic_history
                    self.save_context(session_id, current_context)
        except Exception as e:
            logger.error(f"跟踪会话 {session_id} 的主题历史时出错: {e}")
    
    def track_intent_history(self, session_id: str, intent_analysis: Dict[str, Any], max_history: int = 10):
        """
        跟踪会话的意图历史
        
        Args:
            session_id: 会话ID
            intent_analysis: 意图分析结果
            max_history: 最大历史记录数
        """
        try:
            with self.lock:
                # 获取现有上下文
                current_context = self.contexts.get(session_id, {})
                
                # 获取意图历史或创建新的
                intent_history = current_context.get("intent_history", [])
                
                # 添加新意图
                if "primary_intent" in intent_analysis:
                    new_intent_entry = {
                        "intent": intent_analysis["primary_intent"],
                        "category": intent_analysis.get("intent_category", "未知"),
                        "timestamp": datetime.now().isoformat(),
                        "secondary_intents": intent_analysis.get("secondary_intents", []),
                        "confidence": intent_analysis.get("confidence", 0.5)
                    }
                    
                    # 检查是否与上一个意图相同
                    if intent_history and intent_history[-1]["intent"] == new_intent_entry["intent"]:
                        # 更新时间戳和可能的其他属性
                        intent_history[-1] = new_intent_entry
                    else:
                        # 添加新意图
                        intent_history.append(new_intent_entry)
                    
                    # 限制历史记录数量
                    if len(intent_history) > max_history:
                        intent_history = intent_history[-max_history:]
                    
                    # 更新上下文
                    current_context["intent_history"] = intent_history
                    self.save_context(session_id, current_context)
        except Exception as e:
            logger.error(f"跟踪会话 {session_id} 的意图历史时出错: {e}")
    
    def store_key_information(self, session_id: str, key_info: Dict[str, Any]):
        """
        存储会话中的关键信息
        
        Args:
            session_id: 会话ID
            key_info: 关键信息
        """
        try:
            with self.lock:
                # 获取现有上下文
                current_context = self.contexts.get(session_id, {})
                
                # 获取已存储的关键信息或创建新的
                stored_info = current_context.get("key_information", {})
                
                # 更新关键实体
                if "key_entities" in key_info and key_info["key_entities"]:
                    entities = stored_info.get("entities", {})
                    for entity in key_info["key_entities"]:
                        entities[entity] = {
                            "last_mentioned": datetime.now().isoformat(),
                            "mention_count": entities.get(entity, {}).get("mention_count", 0) + 1
                        }
                    stored_info["entities"] = entities
                
                # 更新关键事实
                if "key_facts" in key_info and key_info["key_facts"]:
                    facts = stored_info.get("facts", [])
                    for fact in key_info["key_facts"]:
                        if fact not in facts:
                            facts.append(fact)
                    stored_info["facts"] = facts
                
                # 更新用户偏好
                if "user_preferences" in key_info and key_info["user_preferences"]:
                    preferences = stored_info.get("preferences", [])
                    for pref in key_info["user_preferences"]:
                        if pref not in preferences:
                            preferences.append(pref)
                    stored_info["preferences"] = preferences
                
                # 更新上下文
                current_context["key_information"] = stored_info
                self.save_context(session_id, current_context)
        except Exception as e:
            logger.error(f"存储会话 {session_id} 的关键信息时出错: {e}")
    
    def get_context_summary(self, session_id: str) -> Dict[str, Any]:
        """
        获取会话上下文的摘要
        
        Args:
            session_id: 会话ID
            
        Returns:
            Dict: 上下文摘要
        """
        try:
            with self.lock:
                context = self.contexts.get(session_id, {})
                
                # 提取主题历史
                topic_history = context.get("topic_history", [])
                current_topic = topic_history[-1]["topic"] if topic_history else "未知"
                
                # 提取意图历史
                intent_history = context.get("intent_history", [])
                current_intent = intent_history[-1]["intent"] if intent_history else "未知"
                
                # 提取关键信息
                key_info = context.get("key_information", {})
                entities = list(key_info.get("entities", {}).keys())
                facts = key_info.get("facts", [])
                preferences = key_info.get("preferences", [])
                
                return {
                    "current_topic": current_topic,
                    "current_intent": current_intent,
                    "key_entities": entities,
                    "key_facts": facts,
                    "user_preferences": preferences,
                    "topic_history": [item["topic"] for item in topic_history],
                    "intent_history": [item["intent"] for item in intent_history]
                }
        except Exception as e:
            logger.error(f"获取会话 {session_id} 的上下文摘要时出错: {e}")
            return {
                "current_topic": "未知",
                "current_intent": "未知",
                "key_entities": [],
                "key_facts": [],
                "user_preferences": [],
                "topic_history": [],
                "intent_history": []
            } 