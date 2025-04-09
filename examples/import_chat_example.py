#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
聊天记录导入示例

这个示例展示了如何使用聊天记录导入功能将外部聊天记录导入到J.A.R.V.I.S.的记忆系统中。
"""

import json
import os
import sys
import asyncio

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chatbot import ChatbotManager

def main():
    # 初始化聊天机器人管理器
    username = "demo_user"
    chatbot = ChatbotManager(username)
    
    # 示例1: 直接导入聊天记录
    print("示例1: 直接导入聊天记录")
    chat_records = [
        {
            "id": 8134,
            "MsgSvrID": "4621335451872129144",
            "type_name": "文本",
            "is_sender": 1,
            "talker": "hack004",
            "room_name": "caicai_77",
            "msg": "opernrouter出了个R1免费的https://openrouter.ai/deepseek/deepseek-r1-zero:free",
            "src": "",
            "extra": {},
            "CreateTime": "2025-03-11 11:07:54"
        },
        {
            "id": 8135,
            "MsgSvrID": "8931651503458285665",
            "type_name": "文本",
            "is_sender": 1,
            "talker": "hack004",
            "room_name": "caicai_77",
            "msg": "cursor出47了",
            "src": "",
            "extra": {},
            "CreateTime": "2025-03-11 11:18:41"
        }
    ]
    
    result = chatbot.import_chat_records(chat_records)
    print(result)
    
    # 示例2: 批量导入聊天记录
    print("\n示例2: 批量导入聊天记录")
    # 创建一个包含100条记录的列表
    large_chat_records = []
    for i in range(100):
        large_chat_records.append({
            "id": 9000 + i,
            "MsgSvrID": f"msg_id_{i}",
            "type_name": "文本",
            "is_sender": i % 2,  # 交替发送者
            "talker": "hack004" if i % 2 == 1 else "caicai_77",
            "room_name": "caicai_77" if i % 2 == 1 else "hack004",
            "msg": f"这是第{i+1}条测试消息",
            "src": "",
            "extra": {},
            "CreateTime": f"2025-03-12 12:{i//60:02d}:{i%60:02d}"
        })
    
    result = chatbot.batch_import_chat_records(large_chat_records, batch_size=20)
    print(result)
    
    # 示例3: 从文件导入聊天记录
    print("\n示例3: 从文件导入聊天记录")
    # 先创建一个示例文件
    file_path = "examples/chat_records_example.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(chat_records, f, ensure_ascii=False, indent=2)
    
    result = chatbot.import_chat_records_from_file(file_path)
    print(result)
    print(f"示例文件已保存到: {os.path.abspath(file_path)}")
    
    # 示例4: 通过聊天命令导入
    print("\n示例4: 通过聊天命令导入")
    print("在聊天界面中，您可以使用以下命令导入聊天记录:")
    print("1. 直接导入: @import_chat [JSON数据]")
    print("2. 批量导入: @batch_import_chat [batch_size] [JSON数据]")
    print("3. 从文件导入: @import_chat_file [文件路径] [batch=true/false] [batch_size=50]")
    
    # 示例5: 查询导入的记忆
    print("\n示例5: 查询导入的记忆")
    query = "我和caicai_77聊了什么?"
    print(f"查询: {query}")
    response = asyncio.run(chatbot.chat(query))
    print(f"回复: {response}")

if __name__ == "__main__":
    main() 