from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from core.utils.ConfigManager import ConfigManager
from core.utils.PersistentMemoryManager import PersistentMemoryManager
from langchain.memory import ConversationBufferMemory
from typing import Dict, Any

class CustomConversationBufferMemory(ConversationBufferMemory):
    """自定义对话缓冲记忆类"""
    
    def __init__(self, memory_manager: PersistentMemoryManager, **kwargs):
        super().__init__(**kwargs)
        self.__dict__["_memory_manager"] = memory_manager
        for message in self._memory_manager.get_messages():
            self.chat_memory.add_message(message)
    
    @property
    def memory_manager(self):
        """获取记忆管理器"""
        return self.__dict__["_memory_manager"]
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """保存对话上下文"""
        super().save_context(inputs, outputs)
        if "input" in inputs:
            self.memory_manager.add_user_message(inputs["input"])
        if "output" in outputs:
            self.memory_manager.add_ai_message(outputs["output"])
    
    def clear(self) -> None:
        """清除记忆"""
        super().clear()
        self.memory_manager.clear()