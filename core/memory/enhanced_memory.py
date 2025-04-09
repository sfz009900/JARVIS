import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass
from uuid import uuid4
import threading
from sklearn.neighbors import NearestNeighbors

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from chromadb.api import Collection
import chromadb
from langchain_chroma import Chroma

logger = logging.getLogger(__name__)

@dataclass
class MemoryTrace:
    """记忆痕迹，模拟人类记忆的基本单位"""
    id: str
    content: str
    timestamp: datetime
    importance: float  # 重要性分数
    emotional_intensity: float  # 情感强度
    context_tags: List[str]  # 上下文标签
    recall_count: int  # 被回忆的次数
    last_recall: datetime  # 最后一次回忆的时间
    memory_type: str  # 记忆类型：episodic（情节）, semantic（语义）, procedural（程序）
    associations: List[str]  # 关联的其他记忆ID
    metadata: Dict[str, Any]  # 额外元数据

class EnhancedMemorySystem:
    """增强型记忆系统，模拟人类记忆机制"""
    
    def __init__(
        self,
        persist_directory: str,
        collection_name: str,
        llm,  # 语言模型用于理解和生成记忆
        embedding_function,
        initial_memory_strength: float = 0.8,
        forgetting_rate: float = 0.1,
        consolidation_threshold: float = 0.5,
        merge_threshold: float = 0.95  # 添加合并阈值参数
    ):
        self.persist_directory = persist_directory
        self.llm = llm
        self.embedding_function = embedding_function
        
        # 记忆参数
        self.initial_memory_strength = initial_memory_strength
        self.forgetting_rate = forgetting_rate
        self.consolidation_threshold = consolidation_threshold
        self.merge_threshold = merge_threshold  # 设置合并阈值
        
        # 初始化Chroma客户端
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # 创建不同类型的记忆集合
        self.collections = {
            "working": self.client.get_or_create_collection(
                name=f"{collection_name}_working",
                embedding_function=embedding_function,
                metadata={
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": 400,  # 默认100，建议增加
                    "hnsw:search_ef": 200,        # 默认40，建议显著增加
                    "hnsw:M": 64                  # 默认16，建议加倍
                }
            ),
            "short_term": self.client.get_or_create_collection(
                name=f"{collection_name}_short_term",
                embedding_function=embedding_function,
                metadata={
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": 400,  # 默认100，建议增加
                    "hnsw:search_ef": 200,        # 默认40，建议显著增加
                    "hnsw:M": 64                  # 默认16，建议加倍
                }
            ),
            "long_term": self.client.get_or_create_collection(
                name=f"{collection_name}_long_term",
                embedding_function=embedding_function,
                metadata={
                    "hnsw:space": "cosine",
                    "hnsw:construction_ef": 400,  # 默认100，建议增加
                    "hnsw:search_ef": 200,        # 默认40，建议显著增加
                    "hnsw:M": 64                  # 默认16，建议加倍
                }
            )
        }
        
        # 记忆关联图
        self.memory_graph = {}
        
        # 加载现有记忆关联
        self._load_memory_graph()
        
        # 添加线程锁
        self.lock = threading.Lock()
        
        # 添加关键词缓存
        self.keywords_cache = {}
        self.keywords_cache_size = 1000  # 缓存大小限制
    
    def _load_memory_graph(self):
        """加载记忆关联图"""
        graph_path = os.path.join(self.persist_directory, "memory_graph.json")
        if os.path.exists(graph_path):
            with open(graph_path, 'r', encoding='utf-8') as f:
                self.memory_graph = json.load(f)
    
    def _save_memory_graph(self):
        """保存记忆关联图"""
        graph_path = os.path.join(self.persist_directory, "memory_graph.json")
        with open(graph_path, 'w', encoding='utf-8') as f:
            json.dump(self.memory_graph, f, ensure_ascii=False, indent=2)
    
    def _analyze_emotion_and_importance(self, content: str) -> Tuple[float, float]:
        """分析内容的情感强度和重要性"""
        try:
            # 使用LLM分析内容的情感强度和重要性
            prompt = f"""请分析以下内容的情感强度和重要性，必须严格按照以下格式返回两个0-1之间的数值：

内容：{content}

请严格按照以下格式返回（不要添加任何其他内容）：
情感强度：0.5
重要性：0.5

注意：
1. 数值必须在0到1之间
2. 必须严格按照上述格式
3. 不要添加任何解释或其他内容"""
            
            logger.debug(f"发送情感分析提示: {prompt}")
            response = self.llm.invoke(prompt).content
            logger.debug(f"收到情感分析响应: {response}")
            
            try:
                # 清理和标准化响应
                lines = [line.strip() for line in response.split('\n') if line.strip()]
                
                # 查找包含所需值的行
                emotional_intensity = 0.5  # 默认值
                importance = 0.5  # 默认值
                
                for line in lines:
                    try:
                        if '情感强度：' in line:
                            value = line.split('：')[1].strip()
                            emotional_intensity = float(value)
                        elif '重要性：' in line:
                            value = line.split('：')[1].strip()
                            importance = float(value)
                    except (IndexError, ValueError) as e:
                        logger.warning(f"解析单行响应时出错: {line} - {e}")
                        continue
                
                # 确保值在0-1范围内
                emotional_intensity = max(0.0, min(1.0, emotional_intensity))
                importance = max(0.0, min(1.0, importance))
                
                logger.debug(f"成功解析 - 情感强度: {emotional_intensity}, 重要性: {importance}")
                return emotional_intensity, importance
                
            except Exception as e:
                logger.warning(f"解析情感分析响应时出错: {e}, 响应内容: {response}")
                return 0.5, 0.5
                
        except Exception as e:
            logger.warning(f"情感分析过程出错: {e}")
            return 0.5, 0.5
    
    def _extract_context_tags(self, content: str) -> List[str]:
        """提取内容的上下文标签"""
        prompt = f"""从以下内容中提取关键的上下文标签（最多5个）：
        
        内容：{content}
        
        请直接返回标签列表，每行一个标签。"""
        
        response = self.llm.invoke(prompt).content
        return [tag.strip() for tag in response.split('\n') if tag.strip()]
    
    def add_memory(self, message: BaseMessage, memory_type: str = "episodic") -> str:
        """添加新的记忆（线程安全版本）"""
        with self.lock:  # 添加线程锁
            logger.info(f"00000000000000000")
            # 分析内容
            emotional_intensity, importance = self._analyze_emotion_and_importance(message.content)
            context_tags = self._extract_context_tags(message.content)
            logger.info(f"11111111111111")
            current_time = datetime.now()
            # 创建记忆痕迹
            trace = MemoryTrace(
                id=str(uuid4()),
                content=message.content,
                timestamp=current_time,
                importance=importance,
                emotional_intensity=emotional_intensity,
                context_tags=context_tags,
                recall_count=0,
                last_recall=current_time,
                memory_type=memory_type,
                associations=[],
                metadata={
                    "message_type": message.type,
                    "additional_kwargs": message.additional_kwargs
                }
            )
            
            # 确定记忆存储位置
            if importance > 0.8 or emotional_intensity > 0.8:
                collection = self.collections["long_term"]
            else:
                collection = self.collections["short_term"]
            
            # 存储记忆
            collection.add(
                ids=[trace.id],
                documents=[trace.content],
                metadatas=[{
                    "timestamp": trace.timestamp.isoformat(),  # 保持原有的ISO格式时间戳
                    "timestamp_float": trace.timestamp.timestamp(),  # 添加浮点数时间戳
                    "importance": trace.importance,
                    "emotional_intensity": trace.emotional_intensity,
                    "context_tags": json.dumps(trace.context_tags),
                    "recall_count": trace.recall_count,
                    "last_recall": trace.last_recall.isoformat(),
                    "memory_type": trace.memory_type,
                    "message_type": trace.metadata["message_type"],
                    "additional_kwargs": json.dumps(trace.metadata["additional_kwargs"])
                }]
            )
            logger.info(f"222222222222222222")
            # 更新记忆关联
            self._update_memory_associations(trace)
            logger.info(f"3333333333333")
            return trace.id
    
    def _update_memory_associations(self, trace: MemoryTrace):
        """更新记忆关联"""
        try:
            # 提取内容中的关键词，用于精确匹配
            keywords = self._extract_keywords(trace.content)
            logger.debug(f"从记忆内容中提取的关键词: {keywords}")
            
            # 存储找到的相似记忆ID
            similar_memories = set()
            similarity_scores = {}  # 存储相似度分数
            
            # 设置相似度阈值，低于此值的关联将被忽略
            similarity_threshold = 0.6
            
            # 按优先级顺序处理集合（先处理长期记忆，因为它们更重要）
            collection_priority = ["long_term", "short_term", "working"]
            
            for collection_name in collection_priority:
                if collection_name not in self.collections:
                    continue
                    
                collection = self.collections[collection_name]
                
                try:
                    # 1. 如果有关键词，先使用关键词进行精确匹配
                    if keywords and len(keywords) > 0:
                        # 单个关键词使用简单包含查询
                        if len(keywords) == 1:
                            where_document = {"$contains": keywords[0]}
                            keyword_results = collection.query(
                                query_texts=[trace.content],
                                n_results=10,  # 增加结果数量以找到更多潜在关联
                                where_document=where_document
                            )
                            
                            # 处理关键词查询结果
                            if keyword_results and keyword_results.get("ids") and keyword_results["ids"][0]:
                                for i, memory_id in enumerate(keyword_results["ids"][0]):
                                    if memory_id != trace.id and memory_id not in similar_memories:
                                        # 如果有距离信息，记录相似度分数
                                        if "distances" in keyword_results and keyword_results["distances"][0]:
                                            similarity = 1.0 - min(1.0, keyword_results["distances"][0][i])
                                            similarity_scores[memory_id] = similarity
                                            
                                            # 只添加超过阈值的记忆
                                            if similarity >= similarity_threshold:
                                                similar_memories.add(memory_id)
                                        else:
                                            # 没有距离信息时，假定关键词匹配的相似度较高
                                            similar_memories.add(memory_id)
                                            similarity_scores[memory_id] = 0.8
                        
                        # 多个关键词使用AND和OR组合
                        elif len(keywords) > 1:
                            # 先尝试AND组合（要求同时包含所有关键词）
                            and_where_document = {
                                "$and": [{"$contains": keyword} for keyword in keywords]
                            }
                            
                            and_results = collection.query(
                                query_texts=[trace.content],
                                n_results=10,
                                where_document=and_where_document
                            )
                            
                            # 处理AND查询结果
                            if and_results and and_results.get("ids") and and_results["ids"][0]:
                                for i, memory_id in enumerate(and_results["ids"][0]):
                                    if memory_id != trace.id and memory_id not in similar_memories:
                                        # 如果有距离信息，记录相似度分数
                                        if "distances" in and_results and and_results["distances"][0]:
                                            similarity = 1.0 - min(1.0, and_results["distances"][0][i])
                                            similarity_scores[memory_id] = similarity
                                            
                                            # 只添加超过阈值的记忆
                                            if similarity >= similarity_threshold:
                                                similar_memories.add(memory_id)
                                        else:
                                            # 没有距离信息时，假定AND匹配的相似度很高
                                            similar_memories.add(memory_id)
                                            similarity_scores[memory_id] = 0.9
                            
                            # 如果AND查询结果不足，再使用OR查询补充
                            if len(similar_memories) < 5:  # 设置一个合理的关联数量上限
                                or_where_document = {
                                    "$or": [{"$contains": keyword} for keyword in keywords]
                                }
                                
                                or_results = collection.query(
                                    query_texts=[trace.content],
                                    n_results=10,
                                    where_document=or_where_document
                                )
                                
                                # 处理OR查询结果
                                if or_results and or_results.get("ids") and or_results["ids"][0]:
                                    for i, memory_id in enumerate(or_results["ids"][0]):
                                        if memory_id != trace.id and memory_id not in similar_memories:
                                            # 如果有距离信息，记录相似度分数
                                            if "distances" in or_results and or_results["distances"][0]:
                                                similarity = 1.0 - min(1.0, or_results["distances"][0][i])
                                                similarity_scores[memory_id] = similarity
                                                
                                                # 只添加超过阈值的记忆
                                                if similarity >= similarity_threshold:
                                                    similar_memories.add(memory_id)
                                            else:
                                                # 没有距离信息时，假定OR匹配的相似度中等
                                                similar_memories.add(memory_id)
                                                similarity_scores[memory_id] = 0.7
                    
                    # 2. 如果关键词搜索结果不足，使用语义搜索补充
                    if len(similar_memories) < 5:  # 设置一个合理的关联数量上限
                        semantic_results = collection.query(
                            query_texts=[trace.content],
                            n_results=10
                        )
                        
                        # 处理语义搜索结果
                        if semantic_results and semantic_results.get("ids") and semantic_results["ids"][0]:
                            for i, memory_id in enumerate(semantic_results["ids"][0]):
                                if memory_id != trace.id and memory_id not in similar_memories:
                                    # 如果有距离信息，记录相似度分数
                                    if "distances" in semantic_results and semantic_results["distances"][0]:
                                        similarity = 1.0 - min(1.0, semantic_results["distances"][0][i])
                                        similarity_scores[memory_id] = similarity
                                        
                                        # 只添加超过阈值的记忆
                                        if similarity >= similarity_threshold:
                                            similar_memories.add(memory_id)
                                    else:
                                        # 没有距离信息时，使用默认相似度
                                        similar_memories.add(memory_id)
                                        similarity_scores[memory_id] = 0.65
                
                except Exception as e:
                    logger.warning(f"在集合 {collection_name} 中查找相似记忆时出错: {e}")
                    continue
                
                # 如果已经找到足够的相似记忆，不再继续搜索其他集合
                if len(similar_memories) >= 10:  # 设置一个上限，避免关联过多
                    break
            
            # 建立双向关联，优先考虑相似度高的记忆
            # 按相似度排序
            sorted_similar_memories = sorted(
                similar_memories, 
                key=lambda x: similarity_scores.get(x, 0), 
                reverse=True
            )
            
            # 限制关联数量，只保留相似度最高的几个
            max_associations = 5  # 设置最大关联数量
            sorted_similar_memories = sorted_similar_memories[:max_associations]
            
            # 建立双向关联
            for similar_id in sorted_similar_memories:
                if similar_id != trace.id:
                    if trace.id not in self.memory_graph:
                        self.memory_graph[trace.id] = []
                    if similar_id not in self.memory_graph:
                        self.memory_graph[similar_id] = []
                    
                    if similar_id not in self.memory_graph[trace.id]:
                        self.memory_graph[trace.id].append(similar_id)
                    if trace.id not in self.memory_graph[similar_id]:
                        self.memory_graph[similar_id].append(trace.id)
            
            # 保存更新后的记忆关联图
            self._save_memory_graph()
            
            logger.debug(f"为记忆 {trace.id} 建立了 {len(sorted_similar_memories)} 个关联")
            
        except Exception as e:
            logger.error(f"更新记忆关联时出错: {e}")
            # 出错时仍然尝试保存已有的关联
            try:
                self._save_memory_graph()
            except Exception as save_error:
                logger.error(f"保存记忆关联图时出错: {save_error}")
    
    def _find_similar_memories(self, content: str, limit: int = 5) -> List[str]:
        """查找相似记忆（简单版本，仅用于向后兼容）
        
        注意：推荐使用更高级的_update_memory_associations方法来建立记忆关联
        """
        similar_ids = []
        for collection in self.collections.values():
            results = collection.query(
                query_texts=[content],
                n_results=limit
            )
            if results["ids"]:
                similar_ids.extend(results["ids"][0])
        return similar_ids
    
    def recall_memory(self, query: str, limit: int = 5) -> List[BaseMessage]:
        """回忆相关记忆，使用渐进式时间窗口搜索和记忆关联"""
        try:
            # 提取查询中的关键词
            keywords = self._extract_keywords(query)
            logger.info(f"从查询中提取的关键词: {keywords}")
            
            # 使用集合来存储已见过的内容,用于去重
            seen_contents = set()
            memories = []
            seen_ids = set()  # 用于跟踪已处理的记忆ID
            
            def _add_unique_memories(new_memories: List[BaseMessage]) -> None:
                """添加非重复的记忆"""
                for memory in new_memories:
                    if not hasattr(memory, 'content'):
                        continue
                        
                    content = memory.content.strip()
                    # 跳过空内容
                    if not content:
                        continue
                        
                    # 跳过与查询完全相同的内容
                    if content == query.strip():
                        continue
                        
                    # 跳过重复内容
                    if content in seen_contents:
                        continue
                        
                    seen_contents.add(content)
                    memories.append(memory)
                    
                    # 如果已经收集够了足够的记忆,就停止
                    if len(memories) >= limit:
                        return
            
            # 首先在工作记忆中查找
            working_memories = self._search_collection(self.collections["working"], query, limit, keywords)
            _add_unique_memories(working_memories)
            
            if len(memories) < limit:
                # 然后在短期记忆中查找
                short_term_memories = self._search_collection(
                    self.collections["short_term"],
                    query,
                    limit - len(memories),
                    keywords
                )
                _add_unique_memories(short_term_memories)
            
            if len(memories) < limit:
                # 最后在长期记忆中使用渐进式时间窗口搜索
                remaining_limit = limit - len(memories)
                long_term_memories = self._search_collection(
                    self.collections["long_term"],
                    query,
                    remaining_limit,
                    keywords
                )
                _add_unique_memories(long_term_memories)
            
            # 如果还没有找到足够的记忆，使用记忆关联图查找相关记忆
            if len(memories) < limit:
                # 收集所有已找到的记忆ID
                found_memory_ids = []
                for memory in memories:
                    if hasattr(memory, 'additional_kwargs') and 'session_id' in memory.additional_kwargs:
                        found_memory_ids.append(memory.additional_kwargs['session_id'])
                
                # 使用记忆关联图查找相关记忆
                associated_memories = set()
                for memory_id in found_memory_ids:
                    if memory_id in self.memory_graph:
                        associated_memories.update(self.memory_graph[memory_id])
                
                # 过滤掉已见过的记忆ID
                associated_memories = associated_memories - seen_ids
                
                # 如果有关联记忆，尝试获取它们
                if associated_memories:
                    remaining_limit = limit - len(memories)
                    associated_memories_list = list(associated_memories)[:remaining_limit]
                    
                    # 在所有集合中查找关联记忆
                    for collection in self.collections.values():
                        if not associated_memories_list:
                            break
                            
                        try:
                            results = collection.get(ids=associated_memories_list)
                            if results and results.get('documents') and results.get('metadatas'):
                                for i, (doc, metadata) in enumerate(zip(results['documents'], results['metadatas'])):
                                    if not doc or not metadata:
                                        continue
                                        
                                    # 创建消息对象
                                    msg_type = metadata.get("message_type")
                                    if not msg_type:
                                        continue
                                        
                                    additional_kwargs = {}
                                    try:
                                        additional_kwargs = json.loads(metadata.get("additional_kwargs", "{}"))
                                    except json.JSONDecodeError:
                                        logger.warning(f"解析additional_kwargs时出错，使用空字典")
                                    
                                    msg = None
                                    if msg_type == "human":
                                        msg = HumanMessage(content=doc)
                                    elif msg_type == "ai":
                                        msg = AIMessage(content=doc)
                                    elif msg_type == "system":
                                        msg = SystemMessage(content=doc)
                                    
                                    if msg:
                                        msg.additional_kwargs = additional_kwargs
                                        _add_unique_memories([msg])
                                        
                        except Exception as e:
                            logger.warning(f"获取关联记忆时出错: {e}")
                            continue
            
            # 更新记忆强度
            def strengthen_memories(memories_list):
                """在单个线程中处理所有记忆的强化"""
                with self.lock:  # 添加线程锁
                    if not memories_list:
                        return
                        
                    try:
                        # 使用批量处理方法
                        self._strengthen_memories_batch(memories_list)
                    except Exception as e:
                        logger.warning(f"批量强化记忆时出错: {e}")
                        
                        # 回退到单个处理
                        for memory in memories_list:
                            try:
                                self._strengthen_memory(memory)
                            except Exception as e:
                                logger.warning(f"强化单个记忆时出错: {e}")

            # 创建单个线程处理所有记忆
            update_thread = threading.Thread(
                target=strengthen_memories,
                args=(memories,),
                daemon=True
            )
            update_thread.start()
            
            return memories
        except Exception as e:
            logger.error(f"回忆记忆时出错: {e}")
            return []
    
    def _search_collection(self, collection: Collection, query: str, limit: int, keywords: List[str] = None) -> List[BaseMessage]:
        """在指定集合中搜索记忆
        
        Args:
            collection: 要搜索的集合
            query: 搜索查询
            limit: 返回结果的最大数量
            keywords: 从查询中提取的关键词列表，用于精确匹配
            
        Returns:
            List[BaseMessage]: 匹配的记忆消息列表
        """
        try:
            messages = []
            remaining_limit = limit
            
            # 如果有关键词，先使用关键词进行精确匹配
            if keywords and len(keywords) > 0:
                # 首先尝试使用collection.get进行直接匹配，这样不使用向量可能会更加精准
                try:
                    # 单个关键词直接使用
                    if len(keywords) == 1:
                        where_document = {"$contains": keywords[0]}
                        logger.debug(f"使用get和单个关键词直接查询: {keywords[0]}")
                        
                        # 使用get进行直接查询
                        get_results = collection.get(
                            limit=limit,
                            where_document=where_document
                        )
                        
                        # 处理get查询结果
                        get_messages = self._process_get_results(get_results, messages)
                        messages.extend(get_messages)
                        
                    elif len(keywords) > 1:
                        # 多个关键词先使用AND组合
                        and_where_document = {
                            "$and": [{"$contains": keyword} for keyword in keywords]
                        }
                        logger.debug(f"使用get和AND组合多关键词查询: {keywords}")
                        
                        # 使用get进行AND组合查询
                        and_get_results = collection.get(
                            limit=limit,
                            where_document=and_where_document
                        )
                        
                        # 处理AND查询结果
                        and_messages = self._process_get_results(and_get_results, messages)
                        messages.extend(and_messages)
                        
                        # 如果AND查询结果不足，再使用OR查询补充
                        remaining_limit = limit - len(messages)
                        if remaining_limit > 0:
                            logger.debug(f"AND查询找到 {len(and_messages)} 条记忆，使用OR查询补充")
                            
                            # 使用OR组合
                            or_where_document = {
                                "$or": [{"$contains": keyword} for keyword in keywords]
                            }
                            logger.debug(f"使用get和OR组合多关键词查询: {keywords}")
                            
                            # 使用get进行OR组合查询
                            or_get_results = collection.get(
                                limit=remaining_limit,
                                where_document=or_where_document
                            )
                            
                            # 处理OR查询结果
                            or_messages = self._process_get_results(or_get_results, messages)
                            messages.extend(or_messages)
                except Exception as e:
                    logger.warning(f"使用get进行关键词查询时出错: {e}")
                
                # 如果get查询结果不足，再使用原来的query方法进行向量搜索
                remaining_limit = limit - len(messages)
                if remaining_limit > 0:
                    logger.debug(f"get查询找到 {len(messages)} 条记忆，使用query方法补充")
                    
                    # 根据关键词数量构建不同的查询条件
                    if len(keywords) == 1:
                        # 单个关键词直接使用 $contains
                        where_document = {"$contains": keywords[0]}
                        logger.debug(f"使用单个关键词查询: {keywords[0]}")
                        
                        # 使用单个关键词进行查询
                        keyword_results = collection.query(
                            query_texts=[query],
                            n_results=remaining_limit,
                            where_document=where_document
                        )
                        
                        # 处理关键词查询结果
                        keyword_messages = self._process_query_results(keyword_results, messages)
                        messages.extend(keyword_messages)
                        
                    elif len(keywords) > 1:
                        # 多个关键词先使用 $and 组合（要求同时包含所有关键词）
                        and_where_document = {
                            "$and": [{"$contains": keyword} for keyword in keywords]
                        }
                        logger.debug(f"使用AND组合多关键词查询: {keywords}")
                        
                        # 使用AND组合关键词进行查询
                        and_keyword_results = collection.query(
                            query_texts=[query],
                            n_results=remaining_limit,
                            where_document=and_where_document
                        )
                        
                        # 处理AND查询结果
                        and_messages = self._process_query_results(and_keyword_results, messages)
                        messages.extend(and_messages)
                        
                        # 如果AND查询结果不足，再使用OR查询补充
                        remaining_limit = limit - len(messages)
                        if remaining_limit > 0:
                            logger.debug(f"AND查询找到 {len(and_messages)} 条记忆，使用OR查询补充")
                            
                            # 使用 $or 组合（只需包含任一关键词）
                            or_where_document = {
                                "$or": [{"$contains": keyword} for keyword in keywords]
                            }
                            logger.debug(f"使用OR组合多关键词查询: {keywords}")
                            
                            # 创建已存在内容的集合，用于去重
                            existing_contents = {msg.content for msg in messages if hasattr(msg, 'content')}
                            
                            # 使用OR组合关键词进行查询
                            or_keyword_results = collection.query(
                                query_texts=[query],
                                n_results=remaining_limit,
                                where_document=or_where_document
                            )
                            
                            # 处理OR查询结果，并确保不重复
                            or_messages = self._process_query_results(or_keyword_results, messages)
                            messages.extend(or_messages)
            
            # 计算还需要多少条记录
            remaining_limit = limit - len(messages)
            
            # 如果关键词搜索结果不足，使用语义搜索补充
            if remaining_limit > 0:
                logger.debug(f"关键词搜索找到 {len(messages)} 条记忆，还需要 {remaining_limit} 条")
                
                # 使用语义搜索查询剩余的记录
                semantic_results = collection.query(
                    query_texts=[query],
                    n_results=remaining_limit
                )
                
                # 处理语义搜索结果
                semantic_messages = self._process_query_results(semantic_results, messages)
                messages.extend(semantic_messages)
            
            return messages
        except Exception as e:
            logger.error(f"搜索集合时出错: {e}")
            return []
    
    def _process_get_results(self, results: Dict, existing_messages: List[BaseMessage]) -> List[BaseMessage]:
        """处理get查询结果，转换为消息列表
        
        Args:
            results: get查询结果
            existing_messages: 已存在的消息列表，用于去重
            
        Returns:
            List[BaseMessage]: 处理后的消息列表
        """
        messages = []
        
        # 创建已存在内容的集合，用于去重
        existing_contents = {msg.content for msg in existing_messages if hasattr(msg, 'content')}
        
        if results and isinstance(results, dict):
            ids = results.get("ids", [])
            documents = results.get("documents", [])
            metadatas = results.get("metadatas", [])
            
            if ids and documents and metadatas:
                for i, (doc, metadata) in enumerate(zip(documents, metadatas)):
                    try:
                        if not doc or not metadata:
                            continue
                        
                        # 跳过已经添加的内容
                        if doc in existing_contents:
                            continue
                        
                        existing_contents.add(doc)
                            
                        msg_type = metadata.get("message_type")
                        if not msg_type:
                            continue
                            
                        additional_kwargs = {}
                        try:
                            additional_kwargs = json.loads(metadata.get("additional_kwargs", "{}"))
                        except json.JSONDecodeError:
                            logger.warning(f"解析additional_kwargs时出错，使用空字典")
                        
                        msg = None
                        if msg_type == "human":
                            msg = HumanMessage(content=doc)
                        elif msg_type == "ai":
                            msg = AIMessage(content=doc)
                        elif msg_type == "system":
                            msg = SystemMessage(content=doc)
                        
                        if msg:
                            msg.additional_kwargs = additional_kwargs
                            messages.append(msg)
                    except Exception as e:
                        logger.warning(f"处理单条记忆时出错: {e}")
                        continue
        
        return messages
    
    def _process_query_results(self, results: Dict, existing_messages: List[BaseMessage]) -> List[BaseMessage]:
        """处理查询结果，转换为消息列表
        
        Args:
            results: 查询结果
            existing_messages: 已存在的消息列表，用于去重
            
        Returns:
            List[BaseMessage]: 处理后的消息列表
        """
        messages = []
        
        # 创建已存在内容的集合，用于去重
        existing_contents = {msg.content for msg in existing_messages if hasattr(msg, 'content')}
        
        if results and isinstance(results, dict):
            ids = results.get("ids", [])
            documents = results.get("documents", [])
            metadatas = results.get("metadatas", [])
            
            if ids and documents and metadatas and len(ids) > 0 and len(documents) > 0 and len(metadatas) > 0:
                for doc, metadata in zip(documents[0], metadatas[0]):
                    try:
                        if not doc or not metadata:
                            continue
                        
                        # 跳过已经添加的内容
                        if doc in existing_contents:
                            continue
                        
                        existing_contents.add(doc)
                            
                        msg_type = metadata.get("message_type")
                        if not msg_type:
                            continue
                            
                        additional_kwargs = {}
                        try:
                            additional_kwargs = json.loads(metadata.get("additional_kwargs", "{}"))
                        except json.JSONDecodeError:
                            logger.warning(f"解析additional_kwargs时出错，使用空字典")
                        
                        msg = None
                        if msg_type == "human":
                            msg = HumanMessage(content=doc)
                        elif msg_type == "ai":
                            msg = AIMessage(content=doc)
                        elif msg_type == "system":
                            msg = SystemMessage(content=doc)
                        
                        if msg:
                            msg.additional_kwargs = additional_kwargs
                            messages.append(msg)
                    except Exception as e:
                        logger.warning(f"处理单条记忆时出错: {e}")
                        continue
        
        return messages
    
    def _extract_keywords(self, query: str) -> List[str]:
        """从查询中提取关键词
        
        Args:
            query: 搜索查询
            
        Returns:
            List[str]: 关键词列表
        """
        try:
            # 检查缓存中是否已存在该查询的关键词
            if query in self.keywords_cache:
                logger.debug(f"从缓存中获取关键词: {self.keywords_cache[query]}")
                return self.keywords_cache[query]
            
            # 使用LLM提取关键词
            prompt = f"""从以下查询中提取重要的关键词（最多3个）：
            规则:
            1:比如像"我提到过重庆防疫站吗?",就只提取"重庆"和"防疫站",不要提取""提到.
            2:要保持原文语言比如"我和oldcai提到过白嫖cursor吗?",不能提取成"['white', 'cursor', 'oldcai']",正确是"['白嫖', 'cursor', 'oldcai']".
            查询：{query}
            
            请直接返回关键词列表，每行一个关键词，不要包含任何其他内容。
            关键词应该是查询中最重要、最具有识别性的词语。"""
            
            response = self.llm.invoke(prompt).content
            keywords = [kw.strip() for kw in response.split('\n') if kw.strip()]
            
            # 如果LLM提取失败，使用简单的分词
            if not keywords:
                # 移除常见的疑问词和虚词
                stop_words = {'谁', '什么', '哪里', '哪个', '为什么', '怎么', '是', '的', '了', '和', '与', '在'}
                words = [w for w in query if w not in stop_words]
                keywords = [w for w in words if len(w) >= 2]  # 只保留长度大于等于2的词
            
            # 将结果存入缓存
            self.keywords_cache[query] = keywords
            
            # 如果缓存大小超过限制，删除最早添加的项
            if len(self.keywords_cache) > self.keywords_cache_size:
                # 删除第一个键值对（最早添加的）
                oldest_key = next(iter(self.keywords_cache))
                del self.keywords_cache[oldest_key]
            
            return keywords
            
        except Exception as e:
            logger.warning(f"提取关键词时出错: {e}")
            return []
    
    def _strengthen_memory(self, message: BaseMessage):
        """增强记忆强度"""
        try:
            if not hasattr(message, 'content') or not message.content:
                logger.warning("记忆内容为空，跳过强化")
                return
                
            logger.info(f"开始强化记忆: {message.content[:100]}...")
            
            # 检查记忆对象是否已包含集合信息
            if hasattr(message, 'additional_kwargs'):
                collection_name = message.additional_kwargs.get('collection_name')
                memory_id = message.additional_kwargs.get('session_id')
                
                # 如果已知集合和ID，直接更新
                if collection_name and memory_id and collection_name in self.collections:
                    collection = self.collections[collection_name]
                    
                    try:
                        # 获取当前元数据
                        results = collection.get(ids=[memory_id])
                        
                        if results and results.get('metadatas') and results['metadatas'][0]:
                            metadata = results['metadatas'][0]
                            
                            # 更新元数据
                            current_time = datetime.now().isoformat()
                            current_time_float = datetime.now().timestamp()
                            
                            recall_count = metadata.get("recall_count", 0) + 1
                            
                            updated_metadata = metadata.copy()
                            updated_metadata["recall_count"] = recall_count
                            updated_metadata["last_recall"] = current_time
                            updated_metadata["timestamp_float"] = current_time_float
                            
                            # 更新集合中的记忆
                            collection.update(
                                ids=[memory_id],
                                metadatas=[updated_metadata]
                            )
                            
                            # 检查是否需要巩固到长期记忆
                            if (updated_metadata.get("importance", 0) * updated_metadata["recall_count"]) > self.consolidation_threshold:
                                self._consolidate_memory(memory_id, message, updated_metadata)
                                
                            return
                    except Exception as e:
                        logger.warning(f"使用已知ID更新记忆时出错: {e}")
            
            # 如果没有集合信息或更新失败，回退到原来的方法
            # 更新记忆的召回次数和最后召回时间
            for collection_name, collection in self.collections.items():
                try:
                    logger.debug(f"在集合 {collection_name} 中查找记忆")
                    results = collection.query(
                        query_texts=[message.content],
                        n_results=1
                    )
                    
                    # 详细记录查询结果
                    logger.debug(f"查询结果: {json.dumps(results, ensure_ascii=False)}")
                    
                    if results["ids"] and results["ids"][0] and results["metadatas"] and results["metadatas"][0]:
                        memory_id = results["ids"][0][0]
                        metadata = results["metadatas"][0][0]
                        
                        # 更新元数据
                        current_time = datetime.now().isoformat()
                        current_time_float = datetime.now().timestamp()
                        
                        recall_count = metadata.get("recall_count", 0) + 1
                        
                        updated_metadata = metadata.copy()
                        updated_metadata["recall_count"] = recall_count
                        updated_metadata["last_recall"] = current_time
                        updated_metadata["timestamp_float"] = current_time_float
                        
                        # 更新集合中的记忆
                        collection.update(
                            ids=[memory_id],
                            metadatas=[updated_metadata]
                        )
                        
                        # 在记忆对象中添加集合信息，以便将来使用
                        if hasattr(message, 'additional_kwargs'):
                            message.additional_kwargs['collection_name'] = collection_name
                            message.additional_kwargs['session_id'] = memory_id
                        
                        # 检查是否需要巩固到长期记忆
                        if (updated_metadata.get("importance", 0) * updated_metadata["recall_count"]) > self.consolidation_threshold:
                            logger.debug(f"记忆强度超过阈值，准备转移到长期记忆")
                            try:
                                self._consolidate_memory(memory_id, message, updated_metadata)
                            except Exception as e:
                                logger.warning(f"巩固记忆时出错: {e}")
                        
                        # 找到并更新了记忆，不需要继续查找
                        break
                except Exception as e:
                    logger.warning(f"在集合 {collection_name} 中查找或更新记忆时出错: {e}")
        except Exception as e:
            logger.error(f"强化记忆时出错: {e}")

    def _strengthen_memories_batch(self, memories: List[BaseMessage]):
        """批量增强多个记忆的强度"""
        if not memories:
            return
        
        logger.info(f"开始批量强化 {len(memories)} 条记忆...")
        
        # 按集合分组记忆
        memories_by_collection = {}
        memories_without_collection = []
        
        # 首先尝试从记忆对象中获取集合信息
        for memory in memories:
            if hasattr(memory, 'additional_kwargs') and 'collection_name' in memory.additional_kwargs and 'session_id' in memory.additional_kwargs:
                collection_name = memory.additional_kwargs['collection_name']
                if collection_name in self.collections:
                    memories_by_collection.setdefault(collection_name, []).append(memory)
                else:
                    memories_without_collection.append(memory)
            else:
                memories_without_collection.append(memory)
        
        # 调试日志：记录分组情况
        #logger.info(f"记忆分组情况: 有集合信息的记忆: {sum(len(mems) for mems in memories_by_collection.values())}, 无集合信息的记忆: {len(memories_without_collection)}")
        
        # 处理有集合信息的记忆
        for collection_name, collection_memories in memories_by_collection.items():
            collection = self.collections[collection_name]
            #logger.info(f"处理集合 {collection_name} 中的 {len(collection_memories)} 条记忆")
            self._strengthen_memories_in_collection(collection, collection_name, collection_memories)
        
        # 处理没有集合信息的记忆
        if memories_without_collection:
            # 为这些记忆创建一个内容到记忆的映射
            content_to_memory = {}
            query_texts = []
            
            for memory in memories_without_collection:
                if hasattr(memory, 'content') and memory.content:
                    content_to_memory[memory.content] = memory
                    query_texts.append(memory.content)
            
            #logger.info(f"开始在所有集合中查询 {len(query_texts)} 条无集合信息的记忆")
            
            # 在所有集合中查询这些记忆
            for collection_name, collection in self.collections.items():
                if not query_texts:
                    break
                
                try:
                   # logger.info(f"在集合 {collection_name} 中查询 {len(query_texts)} 条记忆")
                    # 批量查询
                    results = collection.query(
                        query_texts=query_texts,
                        n_results=1
                    )
                    
                    # 处理查询结果
                    found_memories = []
                    found_indices = []
                    
                    for i, query_text in enumerate(query_texts):
                        if i < len(results.get('ids', [])) and results['ids'][i] and results['ids'][i][0]:
                            # 找到匹配的记忆
                            found_memories.append(content_to_memory[query_text])
                            found_indices.append(i)
                    
                    #logger.info(f"在集合 {collection_name} 中找到 {len(found_memories)} 条匹配记忆")
                    
                    # 从查询列表中移除已找到的记忆
                    for i in sorted(found_indices, reverse=True):
                        query_texts.pop(i)
                    
                    # 处理找到的记忆
                    if found_memories:
                        self._strengthen_memories_in_collection(collection, collection_name, found_memories)
                except Exception as e:
                    logger.warning(f"在集合 {collection_name} 中批量查询记忆时出错: {e}")
        
        logger.info(f"结束批量强化 {len(memories)} 条记忆...")
    
    def _strengthen_memories_in_collection(self, collection, collection_name, memories):
        """在指定集合中强化一批记忆"""
        try:
            # 分为两组：已知ID的记忆和未知ID的记忆
            known_id_memories = []
            unknown_id_memories = []
            
            # 使用集合来跟踪已处理的ID，避免重复
            processed_ids = set()
            
            # 首先检查哪些记忆已经在长期记忆中
            long_term_ids = set(self.collections["long_term"].get()["ids"])
            
            for memory in memories:
                if (hasattr(memory, 'additional_kwargs') and 
                    'session_id' in memory.additional_kwargs and 
                    memory.additional_kwargs['session_id']):
                    memory_id = memory.additional_kwargs['session_id']
                    
                    # 记录记忆的当前集合信息
                    current_collection = memory.additional_kwargs.get('collection_name', 'unknown')
                    #logger.info(f"处理记忆ID: {memory_id}, 当前集合: {current_collection}, 目标集合: {collection_name}")
                    
                    # 记录记忆内容
                    # if hasattr(memory, 'content'):
                    #     logger.info(f"记忆ID: {memory_id} 的内容: {memory.content}")
                    
                    # 检查记忆是否已经在长期记忆中
                    if memory_id in long_term_ids:
                        #logger.info(f"记忆ID: {memory_id} 已经在长期记忆中，跳过强化处理")
                        # 确保记忆对象的集合信息正确
                        if hasattr(memory, 'additional_kwargs'):
                            memory.additional_kwargs['collection_name'] = "long_term"
                        continue
                    
                    # 只添加未处理过的ID
                    if memory_id not in processed_ids:
                        known_id_memories.append(memory)
                        processed_ids.add(memory_id)
                elif hasattr(memory, 'content') and memory.content:
                    unknown_id_memories.append(memory)
                    #logger.info(f"处理未知ID记忆, 内容: {memory.content}")
            
            #logger.info(f"集合 {collection_name} 中: 已知ID记忆数: {len(known_id_memories)}, 未知ID记忆数: {len(unknown_id_memories)}")
            
            # 处理已知ID的记忆
            if known_id_memories:
                memory_ids = [memory.additional_kwargs['session_id'] for memory in known_id_memories]
                
                # 获取当前元数据
                results = collection.get(ids=memory_ids)
                
                if results and results.get('metadatas'):
                    # 更新元数据
                    current_time = datetime.now().isoformat()
                    current_time_float = datetime.now().timestamp()
                    
                    updated_metadatas = []
                    memories_to_consolidate = []
                    unique_memory_ids = []  # 用于跟踪唯一的ID
                    
                    for i, (memory, metadata) in enumerate(zip(known_id_memories, results['metadatas'])):
                        if metadata:
                            memory_id = memory_ids[i]
                            recall_count = metadata.get("recall_count", 0) + 1
                            
                            updated_metadata = metadata.copy()
                            updated_metadata["recall_count"] = recall_count
                            updated_metadata["last_recall"] = current_time
                            updated_metadata["timestamp_float"] = current_time_float
                            
                            updated_metadatas.append(updated_metadata)
                            unique_memory_ids.append(memory_id)
                            
                            # 检查是否需要巩固到长期记忆
                            importance = updated_metadata.get("importance", 0)
                            consolidation_score = importance * updated_metadata["recall_count"]
                            
                            #logger.info(f"记忆ID: {memory_id}, 重要性: {importance:.2f}, 回忆次数: {recall_count}, 巩固分数: {consolidation_score:.2f}, 巩固阈值: {self.consolidation_threshold}")
                            
                            if consolidation_score > self.consolidation_threshold:
                                memories_to_consolidate.append((memory_id, memory, updated_metadata))
                                #logger.info(f"记忆ID: {memory_id} 将被转移到长期记忆, 巩固分数: {consolidation_score:.2f} > 阈值: {self.consolidation_threshold}")
                    
                    # 批量更新元数据，使用唯一的ID列表
                    if updated_metadatas:
                        collection.update(
                            ids=unique_memory_ids,
                            metadatas=updated_metadatas
                        )
                        #logger.info(f"已更新 {len(updated_metadatas)} 条记忆的元数据")
                    
                    # 处理需要巩固的记忆
                    for memory_id, memory, metadata in memories_to_consolidate:
                        try:
                            self._consolidate_memory(memory_id, memory, metadata)
                        except Exception as e:
                            logger.warning(f"巩固记忆时出错: {e}")
            
            # 处理未知ID的记忆
            if unknown_id_memories:
                # 创建内容到记忆的映射，确保内容唯一性
                content_to_memory = {}
                for memory in unknown_id_memories:
                    if memory.content not in content_to_memory:
                        content_to_memory[memory.content] = memory
                
                #logger.info(f"处理 {len(content_to_memory)} 条唯一内容的未知ID记忆")
                
                # 批量查询
                results = collection.query(
                    query_texts=list(content_to_memory.keys()),
                    n_results=1
                )
                
                # 更新每个找到的记忆
                current_time = datetime.now().isoformat()
                current_time_float = datetime.now().timestamp()
                
                memory_ids = []
                updated_metadatas = []
                memories_to_consolidate = []
                processed_query_ids = set()  # 用于跟踪已处理的查询结果ID
                
                for i, query_text in enumerate(content_to_memory.keys()):
                    if (i < len(results.get('ids', [])) and 
                        results['ids'][i] and 
                        results['ids'][i][0] and 
                        i < len(results.get('metadatas', []))):
                        
                        memory_id = results['ids'][i][0]
                        
                        # 检查记忆是否已经在长期记忆中
                        if memory_id in long_term_ids:
                            #logger.info(f"记忆ID: {memory_id} 已经在长期记忆中，跳过强化处理")
                            memory = content_to_memory[query_text]
                            if hasattr(memory, 'additional_kwargs'):
                                memory.additional_kwargs['collection_name'] = "long_term"
                                memory.additional_kwargs['session_id'] = memory_id
                            continue
                        
                        # 跳过已处理的ID
                        if memory_id in processed_query_ids or memory_id in processed_ids:
                            continue
                            
                        processed_query_ids.add(memory_id)
                        metadata = results['metadatas'][i][0]
                        memory = content_to_memory[query_text]
                        
                        # 更新元数据
                        recall_count = metadata.get("recall_count", 0) + 1
                        
                        updated_metadata = metadata.copy()
                        updated_metadata["recall_count"] = recall_count
                        updated_metadata["last_recall"] = current_time
                        updated_metadata["timestamp_float"] = current_time_float
                        
                        memory_ids.append(memory_id)
                        updated_metadatas.append(updated_metadata)
                        
                        # 在记忆对象中添加集合信息，以便将来使用
                        if hasattr(memory, 'additional_kwargs'):
                            memory.additional_kwargs['collection_name'] = collection_name
                            memory.additional_kwargs['session_id'] = memory_id
                        
                        # 检查是否需要巩固到长期记忆
                        importance = updated_metadata.get("importance", 0)
                        consolidation_score = importance * updated_metadata["recall_count"]
                        
                        #logger.info(f"记忆ID: {memory_id}, 重要性: {importance:.2f}, 回忆次数: {recall_count}, 巩固分数: {consolidation_score:.2f}, 巩固阈值: {self.consolidation_threshold}")
                        
                        if consolidation_score > self.consolidation_threshold:
                            memories_to_consolidate.append((memory_id, memory, updated_metadata))
                            #logger.info(f"记忆ID: {memory_id} 将被转移到长期记忆, 巩固分数: {consolidation_score:.2f} > 阈值: {self.consolidation_threshold}")
                
                # 批量更新元数据
                if memory_ids and updated_metadatas:
                    collection.update(
                        ids=memory_ids,
                        metadatas=updated_metadatas
                    )
                    #logger.info(f"已更新 {len(updated_metadatas)} 条未知ID记忆的元数据")
                
                # 处理需要巩固的记忆
                for memory_id, memory, metadata in memories_to_consolidate:
                    try:
                        self._consolidate_memory(memory_id, memory, metadata)
                    except Exception as e:
                        logger.warning(f"巩固记忆时出错: {e}")
                    
        except Exception as e:
            logger.warning(f"在集合 {collection_name} 中强化记忆时出错: {e}")
    
    def _consolidate_memory(self, memory_id: str, message: BaseMessage, metadata: Dict):
        """将记忆巩固到长期记忆"""
        # 获取记忆来源集合
        source_collection = "unknown"
        if hasattr(message, 'additional_kwargs') and 'collection_name' in message.additional_kwargs:
            source_collection = message.additional_kwargs['collection_name']
        
        # 如果记忆不在长期记忆中，则转移
        if memory_id not in self.collections["long_term"].get()["ids"]:
            #logger.info(f"开始将记忆 {memory_id} 从集合 {source_collection} 转移到长期记忆")
            
            # 重要：先从源集合中获取最新内容，避免竞态条件
            source_content = message.content
            source_metadata = metadata
            
            if source_collection in self.collections:
                try:
                    source_result = self.collections[source_collection].get(ids=[memory_id])
                    if source_result and source_result.get("documents") and source_result["documents"][0]:
                        source_content = source_result["documents"][0]
                        #logger.info(f"从源集合 {source_collection} 获取的最新内容: {source_content}")
                        
                        # 如果源集合中有元数据，也更新元数据
                        if source_result.get("metadatas") and source_result["metadatas"][0]:
                            source_metadata = source_result["metadatas"][0]
                            # 保留原始回忆次数和最后回忆时间
                            source_metadata["recall_count"] = metadata.get("recall_count", 0)
                            source_metadata["last_recall"] = metadata.get("last_recall", datetime.now().isoformat())
                            source_metadata["timestamp_float"] = metadata.get("timestamp_float", datetime.now().timestamp())
                            #logger.info(f"从源集合更新元数据: 重要性={source_metadata.get('importance', 0):.2f}, 回忆次数={source_metadata.get('recall_count', 0)}")
                except Exception as e:
                    logger.warning(f"从源集合 {source_collection} 获取记忆内容时出错: {e}")
            
            # 记录将要添加到长期记忆的内容
            #logger.info(f"将添加到长期记忆的内容: {source_content}")
            #logger.info(f"记忆元数据: 重要性={source_metadata.get('importance', 0):.2f}, 回忆次数={source_metadata.get('recall_count', 0)}, 情感强度={source_metadata.get('emotional_intensity', 0):.2f}")
            
            # 添加到长期记忆
            self.collections["long_term"].add(
                ids=[memory_id],
                documents=[source_content],
                metadatas=[source_metadata]
            )
            
            # 验证添加是否成功，并记录长期记忆中的实际内容
            try:
                long_term_result = self.collections["long_term"].get(ids=[memory_id])
                if long_term_result and long_term_result.get("documents") and long_term_result["documents"][0]:
                    #logger.info(f"记忆 {memory_id} 已成功添加到长期记忆")
                    #logger.info(f"长期记忆中的实际内容: {long_term_result['documents'][0]}")
                    
                    # 更新message对象的内容，确保一致性
                    message.content = long_term_result["documents"][0]
                else:
                    logger.warning(f"记忆 {memory_id} 添加到长期记忆后无法获取其内容")
            except Exception as e:
                logger.warning(f"验证长期记忆内容时出错: {e}")
            
            # 更新记忆对象的集合信息
            if hasattr(message, 'additional_kwargs'):
                old_collection = message.additional_kwargs.get('collection_name', 'unknown')
                message.additional_kwargs['collection_name'] = "long_term"
                #logger.info(f"已更新记忆对象 {memory_id} 的集合信息: {old_collection} -> long_term")
            
            # 从其他集合中删除
            for name, collection in self.collections.items():
                if name != "long_term":
                    # 先检查并记录该集合中的记忆内容
                    try:
                        collection_result = collection.get(ids=[memory_id])
                        # if collection_result and collection_result.get("documents") and collection_result["documents"][0]:
                        #     logger.info(f"集合 {name} 中的记忆 {memory_id} 内容: {collection_result['documents'][0]}")
                    except Exception as e:
                        logger.warning(f"获取集合 {name} 中记忆 {memory_id} 内容时出错: {e}")
                    
                    # 删除记忆
                    collection.delete(ids=[memory_id])
                    #logger.info(f"记忆 {memory_id} 已从集合 {name} 中删除")
        else:
            # 记录长期记忆中已存在的内容
            try:
                long_term_result = self.collections["long_term"].get(ids=[memory_id])
                if long_term_result and long_term_result.get("documents") and long_term_result["documents"][0]:
                    #logger.info(f"记忆 {memory_id} 已经存在于长期记忆中，当前内容: {long_term_result['documents'][0]}")
                    #logger.info(f"尝试添加的新内容: {message.content}")
                    
                    # 更新message对象的内容，确保一致性
                    message.content = long_term_result["documents"][0]
                else:
                    logger.warning(f"记忆 {memory_id} 在长期记忆中存在但无法获取其内容")
            except Exception as e:
                logger.warning(f"获取长期记忆中已存在记忆内容时出错: {e}")
            
            #logger.info(f"记忆 {memory_id} 已经存在于长期记忆中，跳过转移")
    
    def forget_old_memories(self, threshold_days: int = 30):
        """遗忘旧的、不重要的记忆，同时考虑记忆关联"""
        try:
            threshold_date = datetime.now() - timedelta(days=threshold_days)
            threshold_timestamp = threshold_date.timestamp()  # Convert to timestamp for consistent comparison
            logger.debug(f"开始清理旧记忆，阈值日期: {threshold_date.isoformat()}, 时间戳: {threshold_timestamp}")
            
            for collection in self.collections.values():
                try:
                    # 首先获取所有记忆
                    results = collection.query(
                        query_texts=[""],
                        n_results=1000  # 设置一个较大的值以获取更多记忆
                    )
                    
                    if not results["ids"] or not results["ids"][0]:
                        continue
                        
                    # 手动筛选需要删除的记忆
                    ids_to_delete = []
                    memory_scores = {}  # 用于存储每个记忆的"遗忘分数"
                    
                    for i, metadata in enumerate(results["metadatas"][0]):
                        try:
                            memory_id = results["ids"][0][i]
                            
                            # 优先使用timestamp_float字段进行比较
                            if "timestamp_float" in metadata:
                                memory_timestamp_float = float(metadata.get("timestamp_float"))
                            else:
                                # 如果没有timestamp_float字段，则尝试解析ISO格式的timestamp
                                try:
                                    memory_timestamp = datetime.fromisoformat(metadata.get("timestamp", ""))
                                    memory_timestamp_float = memory_timestamp.timestamp()
                                except (ValueError, TypeError):
                                    logger.warning(f"无法解析记忆时间戳: {metadata.get('timestamp')}")
                                    continue
                            
                            importance = float(metadata.get("importance", 1.0))
                            recall_count = int(metadata.get("recall_count", 0))
                            
                            # 计算基础遗忘分数
                            time_factor = 1.0 - min(1.0, (datetime.now().timestamp() - memory_timestamp_float) / (threshold_days * 24 * 3600))
                            importance_factor = importance
                            recall_factor = min(1.0, recall_count / 5)  # 最多考虑5次召回
                            
                            # 考虑记忆关联
                            association_factor = 1.0
                            if memory_id in self.memory_graph:
                                # 计算关联记忆的数量和重要性
                                associated_memories = self.memory_graph[memory_id]
                                if associated_memories:
                                    # 获取关联记忆的元数据
                                    associated_results = collection.get(ids=list(associated_memories))
                                    if associated_results and associated_results.get('metadatas'):
                                        # 计算关联记忆的平均重要性
                                        associated_importance = sum(
                                            float(meta.get("importance", 0))
                                            for meta in associated_results['metadatas']
                                            if meta
                                        ) / len(associated_memories)
                                        association_factor = max(0.5, min(1.0, associated_importance))
                            
                            # 计算最终的遗忘分数
                            forget_score = (
                                (1 - time_factor) * 0.4 +  # 时间因素权重
                                (1 - importance_factor) * 0.3 +  # 重要性因素权重
                                (1 - recall_factor) * 0.2 +  # 召回因素权重
                                (1 - association_factor) * 0.1  # 关联因素权重
                            )
                            
                            memory_scores[memory_id] = forget_score
                            
                            # 如果遗忘分数超过阈值，考虑删除
                            if forget_score > 0.7:  # 设置遗忘阈值
                                ids_to_delete.append(memory_id)
                                
                        except (ValueError, TypeError) as e:
                            logger.warning(f"处理记忆元数据时出错: {e}")
                            continue
                    
                    # 删除符合条件的记忆
                    if ids_to_delete:
                        logger.info(f"准备删除 {len(ids_to_delete)} 条旧记忆")
                        collection.delete(ids=ids_to_delete)
                        logger.debug(f"成功删除记忆，IDs: {ids_to_delete}")
                        
                        # 更新记忆关联图
                        for memory_id in ids_to_delete:
                            if memory_id in self.memory_graph:
                                # 获取关联的记忆
                                associated_memories = self.memory_graph[memory_id]
                                # 从关联记忆中删除当前记忆
                                for associated_id in associated_memories:
                                    if associated_id in self.memory_graph:
                                        self.memory_graph[associated_id] = [
                                            mid for mid in self.memory_graph[associated_id]
                                            if mid != memory_id
                                        ]
                                # 删除当前记忆的关联
                                del self.memory_graph[memory_id]
                        
                        # 保存更新后的记忆关联图
                        self._save_memory_graph()
                    
                except Exception as e:
                    logger.warning(f"处理集合中的记忆时出错: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"遗忘旧记忆时出错: {e}", exc_info=True)
            raise
    
    def merge_similar_memories(self, short_term_only: bool = False):
        """合并所有集合中的相似记忆，通过批处理方式高效处理大量记忆
        
        Args:
            short_term_only (bool): 如果为True，只处理working、short_term和semantic集合；
                                  如果为False，处理所有集合（包括long_term）
        """
        try:
            # 跟踪已处理的记忆ID
            processed_ids = set()
            batch_size = 100  # 批处理大小
            
            logger.info("开始记忆合并过程...")
            
            # 根据参数选择要处理的集合
            collections_to_process = {}
            for name, collection in self.collections.items():
                if short_term_only:
                    if name in ["working", "short_term"]:  # semantic不在默认collections中
                        collections_to_process[name] = collection
                else:
                    collections_to_process[name] = collection
            
            logger.info(f"将处理 {len(collections_to_process)} 个集合: {', '.join(collections_to_process.keys())}")
            
            # 遍历选定的记忆集合并合并相似记忆
            for collection_name, collection in collections_to_process.items():
                logger.info(f"开始处理 {collection_name} 集合中的相似记忆")
                
                # 一次性获取所有记忆并批量处理
                logger.info(f"正在从 {collection_name} 集合获取记忆...")
                all_results = collection.query(
                    query_texts=[""],
                    n_results=10000,  # 增加获取数量上限
                    include=["documents", "metadatas", "distances"]
                )
                
                if not all_results["ids"] or not all_results["ids"][0]:
                    logger.info(f"{collection_name} 集合没有找到记忆，跳过处理")
                    continue
                
                all_ids = all_results["ids"][0]
                all_docs = all_results["documents"][0]
                all_metas = all_results["metadatas"][0]
                
                logger.info(f"从 {collection_name} 集合获取到 {len(all_ids)} 条记忆")
                
                # 优化：预计算所有记忆的嵌入向量，避免重复计算
                logger.info(f"开始预计算 {len(all_docs)} 个记忆的嵌入向量...")
                embeddings = {}
                
                # 批量计算嵌入以提高性能
                try:
                    total_batches = (len(all_docs) + batch_size - 1) // batch_size
                    for i in range(0, len(all_docs), batch_size):
                        batch_ids = all_ids[i:i+batch_size]
                        batch_docs = all_docs[i:i+batch_size]
                        
                        current_batch = i // batch_size + 1
                        logger.info(f"计算嵌入向量批次 {current_batch}/{total_batches} ({i}-{min(i+batch_size, len(all_docs))}/{len(all_docs)})")
                        
                        # 处理可能的空文档
                        valid_indices = []
                        valid_docs = []
                        for j, doc in enumerate(batch_docs):
                            if doc and isinstance(doc, str):
                                valid_indices.append(j)
                                valid_docs.append(doc)
                        
                        if not valid_docs:
                            logger.info(f"批次 {current_batch} 中没有有效文档，跳过")
                            continue
                            
                        logger.info(f"批次 {current_batch}: 计算 {len(valid_docs)} 个有效文档的嵌入向量")
                        batch_embeddings = self.embedding_function(valid_docs)
                        
                        # 将嵌入向量存储在字典中
                        for j, embedding in enumerate(batch_embeddings):
                            doc_id = batch_ids[valid_indices[j]]
                            embeddings[doc_id] = embedding
                    
                    logger.info(f"嵌入向量计算完成，共计算 {len(embeddings)} 个向量")
                except Exception as e:
                    logger.error(f"预计算嵌入向量时发生错误: {str(e)}", exc_info=True)
                    logger.info("将继续执行，但可能会降级为只处理已计算的嵌入")
                
                # 按重要性排序处理记忆，确保重要记忆被优先考虑
                logger.info("按重要性对记忆进行排序...")
                sorted_indices = sorted(
                    range(len(all_ids)), 
                    key=lambda i: float(all_metas[i].get("importance", 0)), 
                    reverse=True
                )
                
                logger.info("排序完成，开始识别相似记忆群组")
                
                # 使用并查集结构跟踪合并群组
                memory_groups = {}  # {group_id: [memory_ids]}
                memory_to_group = {}  # {memory_id: group_id}
                
                # 第一阶段：识别相似记忆群组
                logger.info("第一阶段：识别相似记忆群组")
                total_memories = len(sorted_indices)
                
                # 优化：使用近似最近邻搜索而不是暴力比较所有记忆
                # 创建一个内存中的向量索引来加速相似度搜索
                
                # 准备向量数据
                valid_indices = []
                valid_embeddings = []
                valid_ids = []
                
                # 收集有效的嵌入向量
                for idx_pos in sorted_indices:
                    memory_id = all_ids[idx_pos]
                    if memory_id in embeddings:
                        valid_indices.append(idx_pos)
                        valid_embeddings.append(embeddings[memory_id])
                        valid_ids.append(memory_id)
                
                if not valid_embeddings:
                    logger.warning("没有找到有效的嵌入向量，跳过相似度计算")
                    continue
                
                # 将嵌入向量转换为numpy数组
                embedding_array = np.array(valid_embeddings)
                
                # 创建最近邻索引
                logger.info(f"创建最近邻索引，处理 {len(valid_embeddings)} 个向量...")
                n_neighbors = min(50, len(valid_embeddings))  # 限制邻居数量
                nn = NearestNeighbors(
                    n_neighbors=n_neighbors,
                    metric='cosine',
                    algorithm='auto',
                    n_jobs=-1  # 使用所有可用CPU
                )
                nn.fit(embedding_array)
                
                # 批量查询最近邻
                logger.info("批量查询最近邻...")
                distances, indices = nn.kneighbors(embedding_array)
                
                # 将距离转换为相似度
                similarities = 1 - distances
                
                # 处理每个记忆
                for i, idx_pos in enumerate(valid_indices):
                    if i % 100 == 0 or i == len(valid_indices) - 1:
                        logger.info(f"处理记忆进度: {i+1}/{len(valid_indices)} ({(i+1)/len(valid_indices)*100:.1f}%)")
                    
                    memory_id = valid_ids[i]
                    
                    if memory_id in processed_ids:
                        continue
                    
                    # 创建新的记忆群组
                    group_id = memory_id
                    memory_groups[group_id] = [memory_id]
                    memory_to_group[memory_id] = group_id
                    processed_ids.add(memory_id)
                    
                    # 首先检查记忆关联图中的关联记忆
                    associated_memories = set()
                    if memory_id in self.memory_graph:
                        associated_memories.update(self.memory_graph[memory_id])
                    
                    # 优先处理关联记忆
                    for associated_id in associated_memories:
                        if associated_id in processed_ids or associated_id == memory_id:
                            continue
                            
                        # 检查关联记忆是否在当前集合中
                        if associated_id in valid_ids:
                            associated_idx = valid_ids.index(associated_id)
                            # 使用预计算的相似度
                            similarity = similarities[i][indices[i] == associated_idx]
                            if len(similarity) > 0 and similarity[0] > self.merge_threshold:
                                # 高相似度，应归入同一群组
                                memory_groups[group_id].append(associated_id)
                                memory_to_group[associated_id] = group_id
                                processed_ids.add(associated_id)
                    
                    # 处理最近邻结果
                    similar_count = 0
                    for j, neighbor_idx in enumerate(indices[i]):
                        if j == 0:  # 跳过自身
                            continue
                            
                        similarity = similarities[i][j]
                        if similarity <= self.merge_threshold:
                            # 如果相似度低于阈值，跳过后续邻居（因为它们按相似度排序）
                            break
                            
                        neighbor_id = valid_ids[neighbor_idx]
                        
                        if neighbor_id in processed_ids or neighbor_id == memory_id:
                            continue
                        
                        # 高相似度，应归入同一群组
                        memory_groups[group_id].append(neighbor_id)
                        memory_to_group[neighbor_id] = group_id
                        processed_ids.add(neighbor_id)
                        similar_count += 1
                    
                    if similar_count > 0:
                        logger.debug(f"记忆 {memory_id} 找到 {similar_count} 个相似记忆")
                
                # 统计需要合并的群组
                merge_groups = {gid: mids for gid, mids in memory_groups.items() if len(mids) > 1}
                logger.info(f"第一阶段完成，共识别出 {len(memory_groups)} 个记忆群组，其中 {len(merge_groups)} 个需要合并")
                
                # 第二阶段：合并各个群组的记忆
                logger.info(f"第二阶段：合并 {collection_name} 集合中的相似记忆群组")
                merged_count = 0
                total_groups = len(merge_groups)
                
                for group_idx, (group_id, memory_ids) in enumerate(merge_groups.items()):
                    if group_idx % 10 == 0 or group_idx == total_groups - 1:
                        logger.info(f"合并群组进度: {group_idx+1}/{total_groups} ({(group_idx+1)/total_groups*100:.1f}%)")
                    
                    # 收集群组中所有记忆的文档和元数据
                    group_docs = []
                    group_metas = []
                    
                    for mem_id in memory_ids:
                        idx = all_ids.index(mem_id)
                        group_docs.append(all_docs[idx])
                        group_metas.append(all_metas[idx])
                    
                    # 合并记忆
                    logger.debug(f"开始合并群组 {group_idx+1}，包含 {len(memory_ids)} 个记忆")
                    new_memory_id = self._merge_memories(memory_ids, group_docs, group_metas)
                    if new_memory_id:
                        logger.info(f"成功合并群组 {group_idx+1}：将 {len(memory_ids)} 个相似记忆合并为新记忆 {new_memory_id}")
                        merged_count += 1
                    else:
                        logger.warning(f"合并群组 {group_idx+1} 失败，包含 {len(memory_ids)} 个记忆")
                
                logger.info(f"完成 {collection_name} 集合的记忆合并，共处理 {len(processed_ids)} 个记忆，成功合并 {merged_count} 个群组")
                
            logger.info("记忆合并过程完成")
            
        except Exception as e:
            logger.error(f"合并记忆时发生错误: {str(e)}", exc_info=True)
    
    def _vector_similarity(self, vec1, vec2):
        """计算两个向量的余弦相似度
        
        Args:
            vec1: 第一个向量
            vec2: 第二个向量
            
        Returns:
            float: 相似度分数 (0-1)
        """
        try:
            # 确保向量为列表或一维数组
            if hasattr(vec1, 'tolist'):
                vec1 = vec1.tolist()
            if hasattr(vec2, 'tolist'):
                vec2 = vec2.tolist()
            
            # 计算余弦相似度
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            magnitude1 = sum(a * a for a in vec1) ** 0.5
            magnitude2 = sum(b * b for b in vec2) ** 0.5
            
            if magnitude1 * magnitude2 == 0:
                return 0.0
                
            similarity = dot_product / (magnitude1 * magnitude2)
            
            # 确保结果在0-1范围内
            return max(0.0, min(1.0, similarity))
            
        except Exception as e:
            logger.error(f"计算向量相似度时出错: {str(e)}")
            if isinstance(vec1, (list, tuple)) and isinstance(vec2, (list, tuple)):
                logger.debug(f"向量1长度: {len(vec1)}, 向量2长度: {len(vec2)}")
            return 0.0
            
    def _merge_memories(self, ids: List[str], documents: List[str], metadatas: List[Dict]):
        """合并多个相似的记忆"""
        if len(ids) <= 1:
            return
            
        try:
            # 根据记忆的重要性和情感强度排序
            sorted_indices = sorted(
                range(len(metadatas)), 
                key=lambda i: (
                    float(metadatas[i].get("importance", 0)) * 0.7 + 
                    float(metadatas[i].get("emotional_intensity", 0)) * 0.3
                ), 
                reverse=True
            )
            
            # 按重要性排序记忆，优先保留重要记忆的信息
            sorted_docs = [documents[i] for i in sorted_indices]
            
            # 使用LLM生成合并后的内容，并提供更详细的指导
            prompt = f"""请从以下相似记忆中提取关键信息并合并。这些记忆按重要性排序，前面的记忆更重要：

{chr(10).join([f"记忆 {i+1}: {doc}" for i, doc in enumerate(sorted_docs)])}

请合并这些记忆，遵循以下规则：
1. 保留所有事实性内容和关键细节
2. 消除冗余和重复信息
3. 保持时间顺序和因果关系
4. 保留记忆中的情感内容和个人观点
5. 结果应该简洁但不遗漏重要内容

合并后的记忆："""
            
            merged_content = self.llm.invoke(prompt).content
            
            # 计算合并后的元数据
            # 原始权重：按重要性和情感强度加权
            weights = [
                float(meta.get("importance", 0)) * 0.7 + 
                float(meta.get("emotional_intensity", 0)) * 0.3
                for meta in metadatas
            ]
            sum_weights = sum(weights) or 1.0
            normalized_weights = [w / sum_weights for w in weights]
            
            # 获取最新的时间戳（ISO格式和浮点数格式）
            latest_timestamp_iso = ""
            latest_timestamp_float = 0.0
            
            for meta in metadatas:
                # 处理ISO格式时间戳
                timestamp_iso = meta.get("timestamp", "")
                if timestamp_iso:
                    if not latest_timestamp_iso or timestamp_iso > latest_timestamp_iso:
                        latest_timestamp_iso = timestamp_iso
                
                # 处理浮点数时间戳
                if "timestamp_float" in meta:
                    try:
                        timestamp_float = float(meta.get("timestamp_float", 0.0))
                        if timestamp_float > latest_timestamp_float:
                            latest_timestamp_float = timestamp_float
                    except (ValueError, TypeError):
                        pass
            
            # 如果没有有效的ISO格式时间戳，但有浮点数时间戳，则生成ISO格式
            if not latest_timestamp_iso and latest_timestamp_float > 0:
                latest_timestamp_iso = datetime.fromtimestamp(latest_timestamp_float).isoformat()
            
            # 如果没有有效的浮点数时间戳，但有ISO格式时间戳，则生成浮点数
            if latest_timestamp_float == 0.0 and latest_timestamp_iso:
                try:
                    latest_timestamp_float = datetime.fromisoformat(latest_timestamp_iso).timestamp()
                except (ValueError, TypeError):
                    # 如果无法解析ISO格式，则使用当前时间
                    current_time = datetime.now()
                    latest_timestamp_iso = current_time.isoformat()
                    latest_timestamp_float = current_time.timestamp()
            
            # 如果两种格式都没有，则使用当前时间
            if not latest_timestamp_iso or latest_timestamp_float == 0.0:
                current_time = datetime.now()
                latest_timestamp_iso = current_time.isoformat()
                latest_timestamp_float = current_time.timestamp()
            
            # 同样处理最后召回时间
            latest_recall_iso = ""
            latest_recall_float = 0.0
            
            for meta in metadatas:
                recall_iso = meta.get("last_recall", "")
                if recall_iso:
                    if not latest_recall_iso or recall_iso > latest_recall_iso:
                        latest_recall_iso = recall_iso
            
            # 如果没有有效的最后召回时间，则使用当前时间
            if not latest_recall_iso:
                latest_recall_iso = datetime.now().isoformat()
            
            # 计算合并后的元数据，使用加权平均而不是简单的最大值
            merged_metadata = {
                # 时间戳使用最近的（同时保存ISO格式和浮点数格式）
                "timestamp": latest_timestamp_iso,
                "timestamp_float": latest_timestamp_float,
                # 重要性使用加权平均
                "importance": float(sum(
                    float(meta.get("importance", 0)) * w 
                    for meta, w in zip(metadatas, normalized_weights)
                )),
                # 情感强度使用加权平均
                "emotional_intensity": float(sum(
                    float(meta.get("emotional_intensity", 0)) * w 
                    for meta, w in zip(metadatas, normalized_weights)
                )),
                # 合并上下文标签
                "context_tags": json.dumps(list(set(
                    tag for meta in metadatas 
                    for tag in json.loads(meta.get("context_tags", "[]"))
                ))),
                # 召回次数求和
                "recall_count": int(sum(int(meta.get("recall_count", 0)) for meta in metadatas)),
                # 最后召回时间使用最近的
                "last_recall": latest_recall_iso,
                # 记忆类型使用最重要记忆的类型
                "memory_type": metadatas[sorted_indices[0]].get("memory_type", "episodic"),
                "message_type": metadatas[sorted_indices[0]].get("message_type", ""),
                # 保存合并源信息
                "merged_from": json.dumps(ids),
                "additional_kwargs": metadatas[sorted_indices[0]].get("additional_kwargs", "{}")
            }
            
            logger.debug(f"合并后的元数据: {json.dumps(merged_metadata, ensure_ascii=False)}")
            
            # 创建新的合并记忆
            new_id = str(uuid4())
            # 确定合并后的记忆应该放在哪个集合
            # 默认使用最重要记忆所在的集合
            collection_name = None
            original_collections = {}
            
            # 遍历所有集合，找出每个ID所在的集合
            for coll_name, coll in self.collections.items():
                results = coll.get(ids=ids, include=["metadatas"])
                if results and results.get("ids"):
                    for i, mem_id in enumerate(results["ids"]):
                        if mem_id:
                            original_collections[mem_id] = coll_name
            
            # 如果找到了最重要记忆所在的集合，使用它
            if sorted_indices and metadatas and len(sorted_indices) > 0:
                most_important_id = ids[sorted_indices[0]]
                collection_name = original_collections.get(most_important_id, "long_term")
            else:
                # 尝试使用出现频率最高的集合
                collection_counts = {}
                for coll_name in original_collections.values():
                    collection_counts[coll_name] = collection_counts.get(coll_name, 0) + 1
                
                if collection_counts:
                    collection_name = max(collection_counts.items(), key=lambda x: x[1])[0]
                else:
                    collection_name = "long_term"  # 默认使用长期记忆
            
            logger.info(f"合并记忆将保存到集合: {collection_name}")
            collection = self.collections[collection_name]
            collection.add(
                ids=[new_id],
                documents=[merged_content],
                metadatas=[merged_metadata]
            )
            
            # 删除原始记忆
            for coll_name, coll in self.collections.items():
                # 验证每个ID是否存在于该集合中，避免不必要的删除操作
                existing_ids = []
                results = coll.get(ids=ids)
                if results and results.get("ids"):
                    existing_ids = [id_ for id_ in results["ids"] if id_]
                
                if existing_ids:
                    logger.debug(f"从集合 {coll_name} 中删除 {len(existing_ids)} 个原始记忆")
                    coll.delete(ids=existing_ids)
            
            # 更新记忆关联
            self._update_merged_memory_associations(ids, new_id)
            
            return new_id
            
        except Exception as e:
            logger.error(f"合并记忆时出错: {e}", exc_info=True)
            # 出错时不应影响整个流程，返回None表示合并失败
            return None
    
    def _update_merged_memory_associations(self, old_ids: List[str], new_id: str):
        """更新合并后的记忆关联
        
        Args:
            old_ids: 被合并的旧记忆ID列表
            new_id: 新的合并记忆ID
        """
        if not old_ids or not new_id:
            logger.warning("更新记忆关联时缺少必要参数")
            return
        
        # 确保memory_graph已初始化
        if not hasattr(self, 'memory_graph') or self.memory_graph is None:
            self.memory_graph = {}
        
        # 收集所有关联的记忆
        associated_memories = set()
        for old_id in old_ids:
            if old_id and old_id in self.memory_graph:
                # 确保关联列表是有效的
                if isinstance(self.memory_graph[old_id], list):
                    associated_memories.update(self.memory_graph[old_id])
                else:
                    logger.warning(f"记忆ID {old_id} 的关联不是列表类型: {type(self.memory_graph[old_id])}")
                    self.memory_graph[old_id] = []
                
                # 安全删除
                try:
                    del self.memory_graph[old_id]
                except KeyError:
                    logger.warning(f"尝试删除不存在的记忆ID: {old_id}")
        
        # 删除对旧记忆的引用
        for memory_id in list(self.memory_graph.keys()):  # 使用列表复制键以避免在迭代时修改字典
            if memory_id:
                # 确保关联列表是有效的
                if not isinstance(self.memory_graph[memory_id], list):
                    logger.warning(f"记忆ID {memory_id} 的关联不是列表类型: {type(self.memory_graph[memory_id])}")
                    self.memory_graph[memory_id] = []
                
                # 过滤掉旧ID
                self.memory_graph[memory_id] = [
                    mid for mid in self.memory_graph[memory_id]
                    if mid and mid not in old_ids
                ]
        
        # 建立新的关联
        if associated_memories:
            # 过滤掉无效的ID
            valid_associated_memories = [mem_id for mem_id in associated_memories if mem_id and mem_id != new_id]
            
            # 为新ID创建关联列表
            self.memory_graph[new_id] = valid_associated_memories
            
            # 为关联的记忆添加新ID的引用
            for memory_id in valid_associated_memories:
                if memory_id not in self.memory_graph:
                    self.memory_graph[memory_id] = []
                
                if new_id not in self.memory_graph[memory_id]:
                    self.memory_graph[memory_id].append(new_id)
        else:
            # 即使没有关联，也要确保新ID在图中有一个空条目
            self.memory_graph[new_id] = []
        
        # 保存更新后的记忆关联图
        try:
            self._save_memory_graph()
        except Exception as e:
            logger.error(f"保存记忆关联图时出错: {e}")

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算两段文本的相似度
        
        使用余弦相似度计算两段文本的相似度
        
        Args:
            text1: 第一段文本
            text2: 第二段文本
            
        Returns:
            float: 相似度分数，范围在0-1之间
        """
        try:
            # 使用嵌入函数获取文本的向量表示
            embedding1 = self.embedding_function([text1])[0]
            embedding2 = self.embedding_function([text2])[0]
            
            # 计算余弦相似度
            dot_product = sum(a * b for a, b in zip(embedding1, embedding2))
            magnitude1 = sum(a * a for a in embedding1) ** 0.5
            magnitude2 = sum(b * b for b in embedding2) ** 0.5
            
            if magnitude1 * magnitude2 == 0:
                return 0.0
                
            similarity = dot_product / (magnitude1 * magnitude2)
            
            # 确保结果在0-1范围内
            return max(0.0, min(1.0, similarity))
            
        except Exception as e:
            logger.error(f"计算文本相似度时出错: {e}")
            return 0.0

    def manual_memory_maintenance(self):
        """手动执行记忆维护：合并相似记忆和清理旧记忆"""
        try:
            logger.info("开始手动记忆维护...")
            
            # 使用更合理的合并阈值
            original_threshold = self.merge_threshold
            # 不要过度降低阈值，0.8 是一个较为安全的值
            temporary_threshold = self.merge_threshold
            self.merge_threshold = temporary_threshold
            
            logger.info(f"使用临时合并阈值: {temporary_threshold}")
            
            # 合并相似记忆
            logger.info("合并相似记忆...")
            self.merge_similar_memories()
            
            # 恢复原始阈值
            self.merge_threshold = original_threshold
            
            # 清理旧记忆
            # logger.info("清理旧记忆...")
            # self.forget_old_memories(threshold_days=30)
            
            logger.info("记忆维护完成")
            
        except Exception as e:
            logger.error(f"手动记忆维护时出错: {e}", exc_info=True)
            # 确保即使出错也恢复原始阈值
            self.merge_threshold = original_threshold
            raise

    def batch_add_memories(self, memories: List[BaseMessage], memory_type: str = "episodic", skip_emotion_analysis: bool = False):
        """批量添加记忆，避免对每条记录进行LLM调用
        
        Args:
            memories: 要添加的记忆消息列表
            memory_type: 记忆类型，默认为"episodic"
            skip_emotion_analysis: 是否跳过情感分析，为True时使用消息中已有的情感和重要性值或默认值
            
        Returns:
            添加的记忆ID列表
        """
        if not memories:
            return []
            
        memory_ids = []
        with self.lock:  # 使用线程锁确保安全
            # 批量准备记忆数据
            batch_ids = []
            batch_documents = []
            batch_metadatas = []
            
            # 处理每条记忆
            for message in memories:
                try:
                    if not hasattr(message, 'content') or not message.content:
                        logger.warning("记忆内容为空，跳过")
                        continue
                    
                    # 生成唯一ID
                    memory_id = str(uuid4())
                    memory_ids.append(memory_id)
                    
                    # 获取情感和重要性数据
                    if skip_emotion_analysis:
                        # 从消息的额外参数中获取，如果没有则使用默认值
                        additional_kwargs = message.additional_kwargs or {}
                        emotional_intensity = additional_kwargs.get("emotional_intensity", 0.5)
                        importance = additional_kwargs.get("importance", 0.5)
                        # 确保值在0-1范围内
                        emotional_intensity = max(0.0, min(1.0, float(emotional_intensity)))
                        importance = max(0.0, min(1.0, float(importance)))
                    else:
                        # 使用LLM分析情感和重要性
                        emotional_intensity, importance = self._analyze_emotion_and_importance(message.content)
                    
                    # 简化的上下文标签（批量导入时不使用LLM提取标签）
                    context_tags = []
                    
                    current_time = datetime.now()
                    
                    # 准备元数据
                    metadata = {
                        "timestamp": current_time.isoformat(),
                        "timestamp_float": current_time.timestamp(),
                        "importance": importance,
                        "emotional_intensity": emotional_intensity,
                        "context_tags": json.dumps(context_tags),
                        "recall_count": 0,
                        "last_recall": current_time.isoformat(),
                        "memory_type": memory_type,
                        "message_type": message.__class__.__name__.lower().replace('message', ''),
                        "additional_kwargs": json.dumps(message.additional_kwargs or {})
                    }
                    
                    # 添加到批处理列表
                    batch_ids.append(memory_id)
                    batch_documents.append(message.content)
                    batch_metadatas.append(metadata)
                except Exception as e:
                    logger.warning(f"处理单条记忆时出错: {str(e)}")
                    continue
            
            if not batch_ids:
                logger.warning("没有有效的记忆需要添加")
                return []
            
            # 确定存储位置（短期或长期）
            long_term_indices = []
            short_term_indices = []
            
            for i, metadata in enumerate(batch_metadatas):
                 long_term_indices.append(i) #直接插入长期记忆
            
            # 批量添加到长期记忆
            if long_term_indices:
                self.collections["long_term"].add(
                    ids=[batch_ids[i] for i in long_term_indices],
                    documents=[batch_documents[i] for i in long_term_indices],
                    metadatas=[batch_metadatas[i] for i in long_term_indices]
                )
                logger.info(f"已将 {len(long_term_indices)} 条记忆添加到长期记忆")
            
            # 批量添加到短期记忆
            if short_term_indices:
                self.collections["short_term"].add(
                    ids=[batch_ids[i] for i in short_term_indices],
                    documents=[batch_documents[i] for i in short_term_indices],
                    metadatas=[batch_metadatas[i] for i in short_term_indices]
                )
                logger.info(f"已将 {len(short_term_indices)} 条记忆添加到短期记忆")
            
            logger.info(f"批量添加记忆完成，共 {len(batch_ids)} 条")
            return memory_ids