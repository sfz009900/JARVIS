import chromadb
from core.memory.OllamaEmbeddingFunction import OllamaEmbeddingFunction
import json

# 初始化嵌入函数
embedding_function = OllamaEmbeddingFunction(
    base_url="http://gpu.credat.com.cn",
    model="nomic-embed-text:latest"
)

# 初始化Chroma客户端
client = chromadb.PersistentClient(path="./chat_memories/enhanced")
# 获取long_term集合
collection = client.get_collection(
    name="user_memories_long_term",
    embedding_function=embedding_function
)

# 测试查询
# query = "我提到过卤牛肉吗?"
# results = collection.query(
#     query_texts=[query],
#     n_results=100,  # 获取前5条结果
#     where_document={"$contains":"卤牛肉"},
#     #     where_document={
#     #     "$or": [
#     #         {"$contains": "卤牛肉"},
#     #         {"$contains": "防疫站"}
#     #     ]
#     # }

# )

# results = collection.get(
#     limit =100,  # 获取前5条结果
#     where_document={"$contains":"腰椎"},
#     #     where_document={
#     #     "$or": [
#     #         {"$contains": "卤牛肉"},
#     #         {"$contains": "防疫站"}
#     #     ]
#     # }

# )

where_document = {"$contains": "本来就欠缺"}
results = collection.get(
    limit =10,
    where_document=where_document
)

# 打印结果
print("\n查询结果:")
if results["documents"] and results["documents"][0]:
    for i, (doc, metadata) in enumerate(zip(results["documents"][0], results["metadatas"][0]), 1):
        print(f"\n结果 {i}:")
        print(f"内容: {doc}")
        # 解析元数据中的context_tags并显示中文
        metadata_copy = metadata.copy()
        if 'context_tags' in metadata_copy:
            tags = json.loads(metadata_copy['context_tags'])
            metadata_copy['context_tags'] = tags  # 这样会自动显示中文
        print(f"元数据: {metadata_copy}")
else:
    print("没有找到匹配的结果") 