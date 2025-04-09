import random
import logging

logger = logging.getLogger(__name__)

def _format_response(chatbot, response: str) -> str:
        """格式化响应文本"""
        # 添加问候语
        if not chatbot.last_user_input and not chatbot.last_ai_response:
            greeting = chatbot._get_greeting()
            response = f"{greeting}\n\n{response}"
        
        return response
    
def _format_proactive_response(chatbot, response: str, proactive_question: str) -> str:
        """
        格式化带有主动学习问题的响应
        
        Args:
            response: 原始响应
            proactive_question: 主动学习问题
            
        Returns:
            格式化后的响应
        """
        # 确保问题格式正确（以问号结尾）
        if not (proactive_question.endswith("?") or proactive_question.endswith("？")):
            if "?" in proactive_question or "？" in proactive_question:
                proactive_question = proactive_question.split("?")[0] + "?"
            else:
                proactive_question += "?"
                
        # 添加自然的过渡词
        transitions = [
            "对了，我想问一下，",
            "另外，我有个问题，",
            "顺便问一下，",
            "我很好奇，",
            "如果您不介意我问，"
        ]
        
        # 随机选择一个过渡词
        transition = random.choice(transitions)
        
        # 根据原始回复的长度决定格式
        if len(response) > 200:
            # 较长回复，使用换行分隔
            formatted = f"{response}\n\n{transition}{proactive_question}"
        else:
            # 较短回复，直接接在后面
            formatted = f"{response} {transition}{proactive_question}"
            
        return formatted
    
def _format_web_search_response(chatbot, search_content: str, user_input: str) -> str:
        """专门为网络搜索结果设计的格式化方法，让AI根据用户输入和搜索结果生成回答
        
        Args:
            search_content (str): 网络搜索的原始内容
            user_input (str): 用户的原始输入
            
        Returns:
            str: 格式化后的响应
        """
        try:
            # 获取相关记忆来确定是否需要问候语
            memories = chatbot.memory_system.recall_memory(
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
            greeting = f"{chatbot._get_greeting()}。"
            
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
            response = chatbot.llm.invoke(prompt).content.strip()
            logger.debug(f"收到网络搜索回答响应")
            
            # 根据个性设置添加幽默元素
            try:
                humor_level = float(chatbot.personality.get("humor_level", 0.3))
                if humor_level > 0.5 and random.random() < humor_level:
                    witty_remarks = [
                        "我很享受我们的对话。",
                        "为您服务是我的荣幸。",
                        "这就是我的日常工作。",
                        "要把这个也加入我的成就列表吗？"
                    ]
                    response += f"\n\n{random.choice(witty_remarks)}"
            except Exception as e:
                logger.warning(f"添加幽默元素时出错: {e}")
            
            return f"{greeting}{response}"
        except Exception as e:
            logger.warning(f"生成网络搜索回答时出错: {e}")
            # 如果生成回答失败，返回原始搜索结果
            return f"{greeting}抱歉，我在处理搜索结果时遇到了问题。以下是原始搜索结果：\n\n{search_content}"        