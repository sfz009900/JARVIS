from typing import Dict, Any, List
import random
import logging
import re
import json
from datetime import datetime
from core.llmhandle.callopenrouter import _call_openrouter, _call_openrouter_qwq
from core.llmhandle.callopenrouter import _call_openrouter_other
import asyncio

logger = logging.getLogger(__name__)

async def _extract_time_context(chatbot, user_input: str) -> Dict[str, Any]:
    """
    从用户输入中提取时间相关的上下文信息
    
    Args:
        user_input: 用户输入
        
    Returns:
        Dict: 包含时间上下文信息的字典
    """
    time_context = {
        "has_time_reference": False,
        "time_expressions": [],
        "is_past_reference": False,
        "is_future_reference": False,
        "is_present_reference": False,
        "time_relation": "unknown"  # 可能的值: "before", "after", "during", "unknown"
    }
    
    try:
        # 检测时间相关短语
        time_phrases = [
            "昨天", "前天", "上周", "上个月", "去年", "刚才", "之前", "过去",
            "明天", "后天", "下周", "下个月", "明年", "将来", "即将", "未来",
            "现在", "当前", "今天", "本周", "这个月", "最近"
        ]
        
        # 检查是否包含时间短语
        found_phrases = []
        for phrase in time_phrases:
            if phrase in user_input:
                found_phrases.append(phrase)
                time_context["has_time_reference"] = True
        
        if found_phrases:
            time_context["time_expressions"] = found_phrases
            
            # 确定时间参考类型
            past_phrases = ["昨天", "前天", "上周", "上个月", "去年", "刚才", "之前", "过去"]
            future_phrases = ["明天", "后天", "下周", "下个月", "明年", "将来", "即将", "未来"]
            present_phrases = ["现在", "当前", "今天", "本周", "这个月", "最近"]
            
            for phrase in found_phrases:
                if phrase in past_phrases:
                    time_context["is_past_reference"] = True
                elif phrase in future_phrases:
                    time_context["is_future_reference"] = True
                elif phrase in present_phrases:
                    time_context["is_present_reference"] = True
            
            # 确定时间关系
            if any(phrase in user_input for phrase in ["之前", "以前", "过去"]):
                time_context["time_relation"] = "before"
            elif any(phrase in user_input for phrase in ["之后", "以后", "将来"]):
                time_context["time_relation"] = "after"
            elif any(phrase in user_input for phrase in ["期间", "当时", "同时"]):
                time_context["time_relation"] = "during"
        
        # 使用更复杂的时间表达式检测
        if not time_context["has_time_reference"]:
            # 使用LLM检测更复杂的时间表达式
            time_prompt = f"""请分析以下用户输入，判断其中是否包含时间相关的表达式或引用。
如果包含，请提取出这些表达式，并确定它们是指代过去、现在还是未来。

用户输入: {user_input}

输出格式:
包含时间表达式: [是/否]
时间表达式: [提取的表达式，逗号分隔]
时间参考: [过去/现在/未来/混合]"""

            # 限制此类调用的频率，不是每次查询都需要
            # 这里可以添加一个随机抽样或基于输入特征的判断
            if len(user_input) > 15 and random.random() < 0.5:  # 只有在输入较长且随机条件满足时才调用
                time_response = chatbot.llm.invoke(time_prompt).content
                
                # 解析响应
                for line in time_response.strip().split('\n'):
                    if line.startswith("包含时间表达式:") and "是" in line:
                        time_context["has_time_reference"] = True
                    elif line.startswith("时间表达式:"):
                        expressions = line.split(':', 1)[1].strip()
                        if expressions and expressions != "无":
                            time_context["time_expressions"] = [expr.strip() for expr in expressions.split(',')]
                    elif line.startswith("时间参考:"):
                        reference = line.split(':', 1)[1].strip()
                        if "过去" in reference:
                            time_context["is_past_reference"] = True
                        if "现在" in reference:
                            time_context["is_present_reference"] = True
                        if "未来" in reference:
                            time_context["is_future_reference"] = True
            
        return time_context
        
    except Exception as e:
        logger.warning(f"提取时间上下文时出错: {e}")
        return time_context
    
    
async def _evaluate_query_effectiveness(chatbot, query: str) -> float:
    """
    评估查询的有效性，返回一个0-1之间的分数。
    使用多个维度评估：记忆重要性、情感强度、时间新鲜度、召回频率和语义相关性。

    Args:
        query: 要评估的查询字符串
        
    Returns:
        float: 查询有效性分数，0-1之间
    """
    try:
        #logger.info(f"开始评估查询: '{query}'")
        
        # 如果查询过短，直接返回较低分数
        if len(query.strip()) < 5:
            #logger.info(f"查询过短 (长度={len(query.strip())}), 返回分数 0.3")
            return 0.3
            
        # 使用查询检索记忆，确保包含distances
        memories = chatbot.memory_system.recall_memory(
            query=query,
            limit=5  # 只检索少量记忆用于评估
        )
        
        #logger.info(f"检索到 {len(memories) if memories else 0} 条记忆")
        
        # 如果没有找到任何记忆，返回较低分数
        if not memories:
            #logger.info("没有找到相关记忆, 返回分数 0.4")
            return 0.4
            
        current_time = datetime.now().timestamp()
        total_score = 0.0
        memory_weights = []
        
        for i, memory in enumerate(memories):
            try:
                # 获取记忆的元数据
                metadata = memory.additional_kwargs if hasattr(memory, 'additional_kwargs') else {}
                
                # 1. 重要性分数 (0-1)
                importance = float(metadata.get("importance", 0.5))
                
                # 2. 情感强度分数 (0-1)
                emotional_intensity = float(metadata.get("emotional_intensity", 0.5))
                
                # 3. 时间新鲜度分数 (0-1)
                timestamp = float(metadata.get("timestamp_float", current_time))
                time_diff = max(0, current_time - timestamp) / (30 * 24 * 3600)  # 转换为月
                recency_score = 1.0 / (1.0 + time_diff)  # 使用衰减函数
                
                # 4. 召回频率分数 (0-1)
                recall_count = int(metadata.get("recall_count", 0))
                recall_score = min(1.0, recall_count / 10.0)  # 最多10次召回
                
                # 5. 位置权重 (考虑检索顺序)
                position_weight = 1.0 - (i / len(memories) * 0.5)  # 第一个结果权重1.0，最后一个0.5
                
                # 计算该记忆的综合分数
                memory_score = (
                    importance * 0.3 +           # 30% 重要性
                    emotional_intensity * 0.2 +   # 20% 情感强度
                    recency_score * 0.2 +        # 20% 时间新鲜度
                    recall_score * 0.1 +         # 10% 召回频率
                    position_weight * 0.2         # 20% 位置权重
                )
                
                # logger.info(f"记忆 {i+1} 评分详情:")
                # logger.info(f"- 重要性: {importance:.3f}")
                # logger.info(f"- 情感强度: {emotional_intensity:.3f}")
                # logger.info(f"- 时间新鲜度: {recency_score:.3f}")
                # logger.info(f"- 召回频率: {recall_score:.3f}")
                # logger.info(f"- 位置权重: {position_weight:.3f}")
                # logger.info(f"- 综合分数: {memory_score:.3f}")
                
                memory_weights.append(memory_score)
                
            except Exception as e:
                logger.warning(f"处理单条记忆时出错: {e}")
                memory_weights.append(0.5)  # 出错时使用中等权重
        
        # 计算最终分数
        if memory_weights:
            # 使用记忆数量和平均质量计算最终分数
            memory_quality = sum(memory_weights) / len(memory_weights)
            quantity_factor = min(1.0, len(memories) / 5.0)
            
            final_score = (memory_quality * 0.7) + (quantity_factor * 0.3)
            
            # logger.info(f"最终评分计算:")
            # logger.info(f"- 记忆质量: {memory_quality:.3f}")
            # logger.info(f"- 数量因子: {quantity_factor:.3f}")
            # logger.info(f"- 最终分数: {final_score:.3f}")
            
            return min(1.0, max(0.0, final_score))
        else:
            #logger.info("没有有效的记忆权重，返回默认分数 0.4")
            return 0.4
        
    except Exception as e:
        logger.warning(f"评估查询有效性时出错: {e}")
        return 0.5  # 出错时返回中等分数
    
    
async def _expand_query_with_synonyms(chatbot, query: str) -> str:
        """
        通过添加同义词和相关概念扩展查询，增加检索广度
        
        Args:
            query: 原始查询
            
        Returns:
            str: 扩展后的查询
        """
        # 如果查询过短，不进行扩展
        if len(query.strip()) < 5:
            return query
            
        try:
            # 创建扩展查询提示
            expansion_prompt = f"""请分析以下查询，并提取其中最重要的1-3个核心关键词或短语。
然后为每个关键词或短语提供2-3个同义词或密切相关的概念。

查询: {query}

输出格式示例:
关键词1: 同义词A, 同义词B
关键词2: 相关概念A, 相关概念B, 相关概念C

只需提供关键词和同义词/相关概念，不要添加任何解释。"""
            
            # 使用LLM生成同义词和相关概念
            expansion_response = chatbot.llm.invoke(expansion_prompt).content
            
            # 解析响应
            expanded_terms = []
            
            # 提取所有同义词和相关概念
            for line in expansion_response.strip().split('\n'):
                if ':' in line:
                    parts = line.split(':', 1)
                    keyword = parts[0].strip()
                    
                    # 跳过"关键词"、"同义词"等标签行
                    if keyword.lower() in ["关键词", "同义词", "相关概念", "核心概念"]:
                        continue
                    
                    # 添加原始关键词
                    if keyword and len(keyword) > 1:
                        expanded_terms.append(keyword)
                    
                    # 添加同义词和相关概念
                    if len(parts) > 1:
                        synonyms = [s.strip() for s in parts[1].split(',')]
                        for synonym in synonyms:
                            if synonym and len(synonym) > 1:
                                expanded_terms.append(synonym)
            
            # 如果没有提取到任何扩展词，返回原始查询
            if not expanded_terms:
                return query
                
            # 去除重复项，并保持顺序
            unique_terms = []
            for term in expanded_terms:
                if term.lower() not in [t.lower() for t in unique_terms]:
                    unique_terms.append(term)
            
            # 构建扩展查询
            # 原始查询 + (同义词1 OR 同义词2 OR ...)
            expanded_query = f"{query} ({' OR '.join(unique_terms)})"
            
            # 记录查询扩展
            logger.debug(f"查询扩展: 原始='{query}' → 扩展='{expanded_query}'")
            
            return expanded_query
            
        except Exception as e:
            logger.warning(f"扩展查询时出错: {e}")
            return query  # 出错时返回原始查询
        
async def _select_best_query(chatbot, original_query: str, candidate_queries: List[str]) -> str:
        """
        从候选查询中选择最佳的一个，使用LLM来选择最适合ChromaDB的查询
        
        Args:
            original_query: 原始查询
            candidate_queries: 候选查询列表
            
        Returns:
            str: 选择的最佳查询，可能包含同义词扩展
        """
        # 如果没有候选查询，返回原始查询
        if not candidate_queries:
            logger.debug(f"没有候选查询，使用原始查询: '{original_query}'")
            return original_query
            
        # 如果只有一个候选查询，直接返回
        if len(candidate_queries) == 1:
            logger.debug(f"只有一个候选查询: '{candidate_queries[0]}'")
            return candidate_queries[0]
            
        # 去除空的候选查询
        valid_candidates = [q for q in candidate_queries if q and len(q.strip()) > 3]
        if not valid_candidates:
            logger.debug(f"没有有效的候选查询，使用原始查询: '{original_query}'")
            return original_query
            
        try:
            # 创建选择最佳查询的提示
            selection_prompt = f"""作为一个向量数据库查询专家，你需要从以下候选查询中选择一个最适合用于ChromaDB的语义搜索查询。

ChromaDB使用文本嵌入进行语义搜索，它会：
1. 将查询文本转换为高维向量
2. 在向量空间中寻找最相似的文档
3. 基于余弦相似度进行匹配

好的查询应该：
1. 包含关键概念和重要语义信息
2. 避免过多的修饰词和无关细节
3. 保持语义完整性
4. 使用清晰、直接的表达
5. 长度适中（既不过短也不过长）

原始查询: {original_query}

候选查询:
{chr(10).join(f"{i+1}. {query}" for i, query in enumerate(valid_candidates))}

请分析每个查询，并选择最适合ChromaDB的一个。
只需返回选中查询的编号（如：1）。不要添加任何解释。"""

            # 使用LLM选择最佳查询
            selection_result = chatbot.llm.invoke(selection_prompt).content.strip()
            
            # 解析LLM的选择结果
            try:
                # 提取数字
                selected_index = int(''.join(filter(str.isdigit, selection_result))) - 1
                if 0 <= selected_index < len(valid_candidates):
                    best_query = valid_candidates[selected_index]
                    logger.debug(f"LLM选择了查询 {selected_index + 1}: '{best_query}'")
                    return best_query
            except (ValueError, IndexError):
                logger.warning(f"无法解析LLM的选择结果: {selection_result}")
            
            # 如果LLM选择失败，回退到评分机制
            scores = {}
            for query in valid_candidates:
                score = await _evaluate_query_effectiveness(chatbot, query)
                scores[query] = score
            
            best_query = max(scores.items(), key=lambda x: x[1])[0]
            logger.debug(f"回退到评分机制，选择查询: '{best_query}'")
            
            return best_query
            
        except Exception as e:
            logger.warning(f"选择最佳查询时出错: {e}")
            # 出错时返回原始查询
            return original_query
        
async def _reformulate_query(chatbot, user_input: str) -> str:
        """
        重构用户查询，使其成为最适合ChromaDB语义搜索的形式。
        先获取相关记忆作为参考，再让LLM优化查询。
        
        Args:
            user_input: 用户输入
            
        Returns:
            str: 重构后的查询
        """
        # 如果用户输入为空或过短，直接返回
        if not user_input or len(user_input.strip()) < 3:
            return user_input
            
        try:
            # # 先用原始查询获取相关记忆
            relevant_memories = chatbot.memory_system.recall_memory(
                query=user_input,
                limit=20  # 获取更多记忆作为参考
            )
            
            # 准备记忆参考数据
            memory_references = []
            if relevant_memories:
                for i, memory in enumerate(relevant_memories, 1):
                    if hasattr(memory, 'content'):
                        # 提取记忆内容和相似度分数
                        content = memory.content
                        memory_references.append(f"{i}. {content}")
            
            # 准备对话历史
            recent_history_turns = min(3, len(chatbot.conversation_history) // 2)
            if chatbot.conversation_history and len(chatbot.conversation_history) >= 2:
                chat_history = "\n".join(chatbot.conversation_history[-recent_history_turns*2:])
            else:
                chat_history = f"User: {chatbot.last_user_input}\nJ.A.R.V.I.S.: {chatbot.last_ai_response}"
            
            # 提取时间上下文
            time_context = await _extract_time_context(chatbot=chatbot, user_input=user_input)
            
            # 准备时间上下文信息
            time_context_str = "没有明确的时间引用"
            if time_context["has_time_reference"]:
                time_info = []
                if time_context["time_expressions"]:
                    time_info.append(f"时间表达式: {', '.join(time_context['time_expressions'])}")
                
                time_references = []
                if time_context["is_past_reference"]:
                    time_references.append("过去")
                if time_context["is_present_reference"]:
                    time_references.append("现在")
                if time_context["is_future_reference"]:
                    time_references.append("未来")
                    
                if time_references:
                    time_info.append(f"时间参考: {', '.join(time_references)}")
                    
                if time_context["time_relation"] != "unknown":
                    relation_map = {
                        "before": "之前", 
                        "after": "之后", 
                        "during": "期间"
                    }
                    time_info.append(f"时间关系: {relation_map.get(time_context['time_relation'], '')}")
                    
                time_context_str = "; ".join(time_info)
            
            # 创建优化的查询重构提示
            reformulation_prompt = f"""作为向量数据库查询优化专家，请将用户查询重构为最适合ChromaDB语义搜索的形式。
[特别重要]  
0:一定要以"[原始查询]"中的人物作为主要重构对象!比如([原始查询]="test004最近在做什么?"),重构后的关键人物应该是"test004",而不是优先考虑使用"[对话上下文]"和"[给你参考的相关记忆]"里的人物.         
1:只输出最感觉的重构查询,不要添加前缀比如"[原始查询重构]:"
[重要]:
1:一定要参考"给你参考的相关记忆"的数据进行重构,例如"你还记得我妹妹的名字吗?",参考数据里有"妹妹,党颖",那么重构后的查询应该是"你妹妹党颖的名字是什么？.
2:比如"你还记得我妹妹的小狗吗?"不能优化成"你妹妹党颖的小狗年糕",应该是"我妹妹党颖的小狗年糕"这样的.
".
1:只需给出重构后的查询，不要添加任何解释或额外信息.
2:确保输出是单行文本，不包含任何格式标记或换行.

[原始查询]: {user_input}

[对话上下文]:
{chat_history}

[给你参考的相关记忆]:
{chr(10).join(memory_references) if memory_references else "没有找到相关记忆"}"""


            # 使用LLM重构查询
            messages = [{"role": "user", "content": reformulation_prompt}]
            response = _call_openrouter_other(chatbot, messages)
            #response = chatbot.llm.invoke(reformulation_prompt).content
            # 清理响应
            reformulated = response.strip()
            
            # 清理可能的格式标记和前缀
            reformulated = re.sub(r'\*\*.*?\*\*', '', reformulated)  # 移除**标记**
            reformulated = re.sub(r'\(.*?\)', '', reformulated)      # 移除(括号内容)
            
            # 清理常见前缀
            for prefix in ["'[原始查询]:","查询:", "查询：", "重构查询:", "重构查询：", "优化查询:", "优化查询："]:
                if reformulated.startswith(prefix):
                    reformulated = reformulated[len(prefix):].strip()
            
            # 如果重构后的查询无效，返回原始查询
            if not reformulated or len(reformulated) < 5:
                logger.debug(f"重构结果无效，使用原始查询: '{user_input}'")
                return user_input
            
            # 如果重构后的查询过长，可能包含了解释性内容
            if len(reformulated) > len(user_input) * 3:
                logger.debug(f"重构查询过长，截断处理")
                reformulated = reformulated[:len(user_input) * 2].strip()
            
            # 记录查询重构
            if reformulated != user_input:
                logger.debug(f"查询重构: 原始='{user_input}' → 重构='{reformulated}'")
            else:
                logger.debug(f"查询保持不变: '{user_input}'")
            
            return reformulated
            
        except Exception as e:
            logger.warning(f"查询重构过程中出错: {e}", exc_info=True)
            return user_input  # 出错时返回原始查询
        


async def test_query_reformulation(chatbot, test_input: str) -> Dict[str, Any]:
        """
        测试查询重构功能，返回详细的处理结果
        
        Args:
            test_input: 测试输入
            
        Returns:
            Dict: 包含原始查询、重构结果和处理细节的字典
        """
        result = {
            "original_query": test_input,
            "reformulated_query": "",
            "candidate_queries": [],
            "time_context": {},
            "debug_info": {}
        }
        
        try:
            # 提取时间上下文
            time_context = await _extract_time_context(chatbot=chatbot, user_input=test_input)
            result["time_context"] = time_context
            
            # 执行查询重构
            reformulated = await _reformulate_query(chatbot, test_input)
            result["reformulated_query"] = reformulated
            
            # 获取评估信息
            original_score = await _evaluate_query_effectiveness(chatbot, test_input)
            reformulated_score = await _evaluate_query_effectiveness(chatbot, reformulated)
            
            result["debug_info"]["original_score"] = original_score
            result["debug_info"]["reformulated_score"] = reformulated_score
            result["debug_info"]["improvement"] = reformulated_score - original_score
            
            # 尝试查询扩展
            expanded_query = await _expand_query_with_synonyms(chatbot, reformulated)
            result["expanded_query"] = expanded_query
            
            if expanded_query != reformulated:
                expanded_score = await _evaluate_query_effectiveness(chatbot, expanded_query)
                result["debug_info"]["expanded_score"] = expanded_score
            
            return result
            
        except Exception as e:
            logger.error(f"测试查询重构时出错: {e}", exc_info=True)
            result["error"] = str(e)
            return result
        
def perform_memory_maintenance(chatbot, short_term_only: bool = False):
        """执行记忆维护操作
        
        Args:
            short_term_only (bool): 如果为True，只处理短期记忆（working和short_term）；
                                  如果为False，处理所有记忆（包括long_term）
        """
        try:
            logger.info(f"执行{'短期' if short_term_only else '完整'}记忆维护...")
            chatbot.memory_system.merge_similar_memories(short_term_only=short_term_only)
            return f"{'短期' if short_term_only else '完整'}记忆维护已完成"
        except Exception as e:
            logger.error(f"执行记忆维护时出错: {e}")
            return f"记忆维护失败: {str(e)}"
        
async def _extract_search_keywords(chatbot, user_input: str) -> str:
        """从用户输入中提取搜索关键词"""
        # 简单关键词提取逻辑
        keywords = user_input.replace("?", "").replace("？", "").strip()
        if len(keywords) > 1:
            # 如果关键词过长，使用LLM提取
            try:
                extraction_prompt = f"""
请从以下查询中提取3-5个最重要的关键词，用于网络搜索。只返回关键词，用空格分隔：

查询: {user_input}

关键词:"""
                extraction_result = chatbot.llm.invoke(extraction_prompt).content
                keywords = extraction_result.strip()
                # 限制长度
                keywords = " ".join(keywords.split()[:5])
            except Exception as e:
                logger.warning(f"使用LLM提取关键词失败: {e}")
                # 如果LLM处理失败，取前100个字符
                keywords = user_input[:100]
        
        return keywords        


async def _generate_coherent_context(chatbot, topic_analysis: Dict, intent_analysis: Dict, 
                                    key_info: Dict, time_context: Dict, 
                                    conversation_history: List[str], relevant_memories: List) -> Dict[str, Any]:
    """
    生成连贯的对话上下文摘要
    
    Args:
        chatbot: 聊天机器人实例
        topic_analysis: 主题分析结果
        intent_analysis: 意图分析结果
        key_info: 关键信息提取结果
        time_context: 时间上下文
        conversation_history: 对话历史
        relevant_memories: 相关记忆
        
    Returns:
        Dict: 包含连贯上下文的字典
    """
    # 准备记忆参考
    memory_references = []
    if relevant_memories:
        for i, memory in enumerate(relevant_memories[:10], 1):  # 限制使用的记忆数量
            if hasattr(memory, 'content'):
                memory_references.append(f"{i}. {memory.content}")
    
    # 准备主题信息
    topic_info = f"主要话题: {topic_analysis.get('main_topic', '未知')}"
    if topic_analysis.get('topic_shift', False):
        topic_info += f"\n话题变化: 从「{topic_analysis.get('previous_topic', '未知')}」变为「{topic_analysis.get('main_topic', '未知')}」"
        topic_info += f"\n变化类型: {topic_analysis.get('topic_shift_type', '未知')}"
    
    # 准备意图信息
    intent_info = f"主要意图: {intent_analysis.get('primary_intent', '未知')} (类别: {intent_analysis.get('intent_category', '未知')})"
    if intent_analysis.get('intent_shift', False):
        intent_info += f"\n意图变化: 从「{intent_analysis.get('previous_intent', '未知')}」变为「{intent_analysis.get('primary_intent', '未知')}」"
    
    # 准备关键信息
    key_entities = ", ".join(key_info.get('key_entities', []))
    key_facts = ", ".join(key_info.get('key_facts', []))
    user_preferences = ", ".join(key_info.get('user_preferences', []))
    
    # 准备时间上下文
    time_info = "没有明确的时间引用"
    if time_context.get("has_time_reference", False):
        time_expressions = ", ".join(time_context.get('time_expressions', []))
        time_info = f"时间表达式: {time_expressions}"
    
    # 构建上下文生成提示
    context_prompt = f"""请基于以下信息生成一个连贯的对话上下文摘要，该摘要将用于帮助AI理解当前对话状态。

主题信息:
{topic_info}

意图信息:
{intent_info}

关键实体: {key_entities}
关键事实: {key_facts}
用户偏好: {user_preferences}

时间上下文:
{time_info}

相关记忆:
{chr(10).join(memory_references) if memory_references else "没有找到相关记忆"}

请生成一个简洁但信息丰富的上下文摘要，确保包含所有重要信息，并以连贯的方式呈现。
摘要应该是第三人称的，不要使用"我"或"你"等第一人称或第二人称代词。
"""
    
    try:
        # 使用LLM生成上下文摘要
        messages = [{"role": "user", "content": context_prompt}]
        response = _call_openrouter_other(chatbot, messages)
        
        # 清理响应
        coherent_context = response.strip()
        
        return {
            "coherent_context": coherent_context,
            "topic_analysis": topic_analysis,
            "intent_analysis": intent_analysis,
            "key_info": key_info,
            "time_context": time_context
        }
    except Exception as e:
        logger.error(f"生成连贯上下文时出错: {str(e)}")
        return {
            "coherent_context": "无法生成上下文摘要",
            "topic_analysis": topic_analysis,
            "intent_analysis": intent_analysis,
            "key_info": key_info,
            "time_context": time_context
        }

async def _analyze_dialogue_combined(chatbot, conversation_history: List[str], user_input: str) -> Dict[str, Any]:
    """
    合并执行对话分析，包括主题、意图、关键信息和时间上下文分析
    
    Args:
        chatbot: 聊天机器人实例
        conversation_history: 对话历史记录
        user_input: 当前用户输入
        
    Returns:
        Dict: 包含所有分析结果的字典
    """
    # 构建合并分析的提示
    if not conversation_history:
        analysis_prompt = f"""请对以下用户输入进行全面分析，包括主题、意图、关键信息和时间上下文。

用户输入: {user_input}

请以JSON格式返回以下信息:
{{
    "topic_analysis": {{
        "main_topic": "主要话题",
        "sub_topics": ["子话题1", "子话题2"],
        "topic_keywords": ["关键词1", "关键词2"]
    }},
    "intent_analysis": {{
        "primary_intent": "主要意图",
        "intent_category": "问询/请求/命令/闲聊/情感表达/其他",
        "confidence": 0.95,
        "secondary_intents": ["次要意图1", "次要意图2"]
    }},
    "key_info": {{
        "key_entities": ["实体1", "实体2"],
        "key_facts": ["事实1", "事实2"],
        "user_preferences": ["偏好1", "偏好2"],
        "questions": ["问题1", "问题2"],
        "action_items": ["行动项1", "行动项2"]
    }},
    "time_context": {{
        "has_time_reference": true/false,
        "time_expressions": ["时间表达式1", "时间表达式2"],
        "is_past_reference": true/false,
        "is_future_reference": true/false,
        "is_present_reference": true/false,
        "time_relation": "before/after/during/unknown"
    }}
}}
"""
    else:
        # 构建包含历史的提示
        history_text = "\n".join(conversation_history[-10:])  # 最多使用最近10条消息
        analysis_prompt = f"""请对以下对话进行全面分析，包括主题、意图、关键信息和时间上下文。

对话历史:
{history_text}

当前用户输入: {user_input}

请以JSON格式返回以下信息:
{{
    "topic_analysis": {{
        "main_topic": "当前主要话题",
        "previous_topic": "之前的主要话题",
        "topic_shift": true/false,
        "topic_shift_type": "渐进式/突然式/无",
        "sub_topics": ["子话题1", "子话题2"],
        "topic_keywords": ["关键词1", "关键词2"]
    }},
    "intent_analysis": {{
        "primary_intent": "主要意图",
        "previous_intent": "之前的主要意图",
        "intent_category": "问询/请求/命令/闲聊/情感表达/其他",
        "intent_shift": true/false,
        "intent_continuity": 0.85,
        "confidence": 0.95,
        "secondary_intents": ["次要意图1", "次要意图2"]
    }},
    "key_info": {{
        "key_entities": ["实体1", "实体2"],
        "key_facts": ["事实1", "事实2"],
        "user_preferences": ["偏好1", "偏好2"],
        "questions": ["问题1", "问题2"],
        "action_items": ["行动项1", "行动项2"],
        "new_information": ["新信息1", "新信息2"],
        "context_dependencies": ["依赖1", "依赖2"]
    }},
    "time_context": {{
        "has_time_reference": true/false,
        "time_expressions": ["时间表达式1", "时间表达式2"],
        "is_past_reference": true/false,
        "is_future_reference": true/false,
        "is_present_reference": true/false,
        "time_relation": "before/after/during/unknown"
    }}
}}
"""
    
    try:
        # 使用LLM进行分析
        messages = [{"role": "user", "content": analysis_prompt}]
        response = _call_openrouter_other(chatbot, messages)
        
        # 解析JSON响应
        json_match = re.search(r'({.*})', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            # 清理可能的格式问题
            json_str = re.sub(r'```json|```', '', json_str).strip()
            combined_analysis = json.loads(json_str)
        else:
            # 如果无法解析JSON，返回基本结构
            logger.warning(f"无法从响应中解析JSON: {response}")
            combined_analysis = {
                "topic_analysis": {
                    "main_topic": "未知",
                    "sub_topics": [],
                    "topic_keywords": []
                },
                "intent_analysis": {
                    "primary_intent": "未知",
                    "intent_category": "问询",
                    "confidence": 0.5,
                    "secondary_intents": []
                },
                "key_info": {
                    "key_entities": [],
                    "key_facts": [],
                    "user_preferences": [],
                    "questions": [],
                    "action_items": []
                },
                "time_context": {
                    "has_time_reference": False,
                    "time_expressions": [],
                    "is_past_reference": False,
                    "is_future_reference": False,
                    "is_present_reference": False,
                    "time_relation": "unknown"
                }
            }
            
        return combined_analysis
    except Exception as e:
        logger.error(f"合并分析对话时出错: {str(e)}")
        return {
            "topic_analysis": {
                "main_topic": "未知",
                "sub_topics": [],
                "topic_keywords": []
            },
            "intent_analysis": {
                "primary_intent": "未知",
                "intent_category": "问询",
                "confidence": 0.5,
                "secondary_intents": []
            },
            "key_info": {
                "key_entities": [],
                "key_facts": [],
                "user_preferences": [],
                "questions": [],
                "action_items": []
            },
            "time_context": {
                "has_time_reference": False,
                "time_expressions": [],
                "is_past_reference": False,
                "is_future_reference": False,
                "is_present_reference": False,
                "time_relation": "unknown"
            }
        }

async def analyze_dialogue_context(chatbot, user_input: str, reformulated_query: str = None) -> Dict[str, Any]:
    """
    综合分析对话上下文，包括主题、意图、关键信息和时间上下文
    
    Args:
        chatbot: 聊天机器人实例
        user_input: 用户输入
        reformulated_query: 已重构的查询(可选)
        
    Returns:
        Dict: 包含完整上下文分析的字典
    """
    try:
        # 获取对话历史
        conversation_history = chatbot.conversation_history
        
        # 执行合并分析
        combined_analysis = await _analyze_dialogue_combined(chatbot, conversation_history, user_input)
        
        # 获取相关记忆
        # 使用传入的重构查询或原始输入
        query_to_use = reformulated_query if reformulated_query else user_input
        relevant_memories = chatbot.memory_system.recall_memory(
            query=query_to_use,
            limit=20  # 获取足够的记忆作为上下文
        )
        
        # 生成连贯的上下文摘要
        context_result = await _generate_coherent_context(
            chatbot, 
            combined_analysis["topic_analysis"], 
            combined_analysis["intent_analysis"], 
            combined_analysis["key_info"], 
            combined_analysis["time_context"], 
            conversation_history, 
            relevant_memories
        )
        
        return context_result
    except Exception as e:
        logger.error(f"分析对话上下文时出错: {str(e)}")
        return {
            "coherent_context": "对话上下文分析失败",
            "error": str(e)
        }        