# 聊天记录导入功能

J.A.R.V.I.S. 现在支持将外部聊天记录导入到记忆系统中，这使得AI助手能够"记住"您在其他平台上的对话内容。

## 功能特点

- 支持单条和批量导入聊天记录
- 支持从JSON文件导入聊天记录
- 自动区分用户和他人的消息
- 将聊天记录转换为情景记忆(episodic memory)
- 支持通过聊天命令直接导入

## 聊天记录格式

导入的聊天记录应为JSON格式，每条记录包含以下字段：

```json
{
    "id": 8134,                         // 消息ID
    "MsgSvrID": "4621335451872129144",  // 消息服务器ID
    "type_name": "文本",                // 消息类型，目前仅支持"文本"
    "is_sender": 1,                     // 是否为发送者(1)或接收者(0)
    "talker": "hack004",                // 发言者ID
    "room_name": "caicai_77",           // 聊天室/对话对象
    "msg": "这是一条消息",              // 消息内容
    "src": "",                          // 媒体源(如图片路径)
    "extra": {},                        // 额外信息
    "CreateTime": "2025-03-11 11:07:54" // 创建时间
}
```

## 使用方法

### 1. 通过API导入

```python
from chatbot import ChatbotManager

# 初始化聊天机器人
chatbot = ChatbotManager("username")

# 导入单条或少量聊天记录
chat_records = [
    {
        "id": 8134,
        "type_name": "文本",
        "talker": "hack004",
        "room_name": "caicai_77",
        "msg": "这是一条测试消息",
        "CreateTime": "2025-03-11 11:07:54"
    }
]
result = chatbot.import_chat_records(chat_records)

# 批量导入大量聊天记录
large_chat_records = [...] # 大量聊天记录
result = chatbot.batch_import_chat_records(large_chat_records, batch_size=50)

# 从文件导入聊天记录
result = chatbot.import_chat_records_from_file("chat_records.json", use_batch=True, batch_size=50)
```

### 2. 通过聊天命令导入

在与J.A.R.V.I.S.的对话中，您可以使用以下命令导入聊天记录：

1. 直接导入少量记录：
   ```
   @import_chat [JSON数据]
   ```

2. 批量导入大量记录：
   ```
   @batch_import_chat [batch_size] [JSON数据]
   ```

3. 从文件导入：
   ```
   @import_chat_file [文件路径] [batch=true/false] [batch_size=50]
   ```

## 示例

```python
# 导入单条聊天记录
@import_chat {"id": 8134, "type_name": "文本", "talker": "hack004", "room_name": "caicai_77", "msg": "这是一条测试消息", "CreateTime": "2025-03-11 11:07:54"}

# 批量导入聊天记录，每批20条
@batch_import_chat 20 [{"id": 8134, "type_name": "文本", "talker": "hack004", "room_name": "caicai_77", "msg": "消息1"}, {"id": 8135, "type_name": "文本", "talker": "caicai_77", "room_name": "hack004", "msg": "消息2"}]

# 从文件导入，使用批处理，每批50条
@import_chat_file D:/chats/wechat_export.json batch=true batch_size=50
```

## 注意事项

1. 目前仅支持文本类型的消息，其他类型(如图片、视频等)会被跳过
2. 导入大量聊天记录时建议使用批处理模式，以避免内存占用过高
3. 导入完成后会自动触发记忆维护，整合相似记忆
4. 默认情况下，用户ID为"hack004"的消息会被识别为用户自己的消息，如需修改，请调整代码中的判断逻辑 