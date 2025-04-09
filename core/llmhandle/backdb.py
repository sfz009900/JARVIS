import os
import tarfile
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

async def backup_database(chatbot) -> str:
        """
        备份chat_memories目录到dbback目录下的日期和时间戳目录中，使用tar.gz格式打包
        
        Returns:
            str: 备份操作的结果消息
        """
        try:
            # 获取当前日期和时间
            current_date = datetime.now().strftime("%Y-%m-%d")
            current_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 创建备份目录结构
            base_backup_dir = "dbback"
            date_backup_dir = os.path.join(base_backup_dir, current_date)
            
            # 确保备份目录存在
            os.makedirs(date_backup_dir, exist_ok=True)
            
            # 源目录
            source_dir = "chat_memories"
            
            # 如果源目录不存在，返回错误
            if not os.path.exists(source_dir):
                return f"错误：源目录 '{source_dir}' 不存在"
            
            # 创建tar.gz文件名
            backup_filename = f"chat_memories_{current_timestamp}.tar.gz"
            backup_path = os.path.join(date_backup_dir, backup_filename)
            
            # 创建tar.gz文件
            with tarfile.open(backup_path, "w:gz") as tar:
                # 添加整个目录到压缩包
                tar.add(source_dir, arcname=os.path.basename(source_dir))
            
            # 获取压缩包大小
            backup_size = os.path.getsize(backup_path)
            backup_size_mb = backup_size / (1024 * 1024)  # 转换为MB
            
            logger.info(f"数据库备份已完成: {backup_path} (大小: {backup_size_mb:.2f}MB)")
            return f"数据库备份成功完成。\n备份文件: {backup_path}\n大小: {backup_size_mb:.2f}MB"
            
        except Exception as e:
            logger.error(f"数据库备份时出错: {e}", exc_info=True)
            return f"备份过程中出错: {str(e)}"
        
async def _export_chromadb_data(chatbot) -> str:
        """将所有Chromadb数据导出到文件"""
        try:
            output_file = "test.txt"
            
            with open(output_file, "w", encoding="utf-8") as f:
                # 获取所有集合
                collections = chatbot.memory_system.collections
                
                f.write("=== Chromadb 数据导出 ===\n")
                f.write(f"导出时间: {datetime.now().isoformat()}\n")
                f.write(f"用户: {chatbot.username}\n")
                f.write(f"会话ID: {chatbot.session_id}\n\n")
                
                # 遍历所有集合
                for collection_name, collection in collections.items():
                    f.write(f"=== 集合: {collection_name} ===\n")
                    
                    # 获取集合中的所有数据
                    try:
                        data = collection.get()
                        
                        # 写入数据统计信息
                        f.write(f"记录总数: {len(data.get('ids', []))}\n\n")
                        
                        # 写入每条记录的详细信息
                        for i, (id, document, metadata) in enumerate(zip(
                            data.get('ids', []),
                            data.get('documents', []),
                            data.get('metadatas', [])
                        )):
                            f.write(f"--- 记录 {i+1} ---\n")
                            f.write(f"ID: {id}\n")
                            f.write(f"内容: {document}\n")
                            f.write("元数据:\n")
                            for key, value in metadata.items():
                                f.write(f"  {key}: {value}\n")
                            f.write("\n")
                    except Exception as e:
                        f.write(f"获取集合数据时出错: {str(e)}\n\n")
                
                # 导出记忆图谱数据（如果存在）
                try:
                    memory_graph_path = os.path.join(chatbot.memory_system.persist_directory, "memory_graph.json")
                    if os.path.exists(memory_graph_path):
                        with open(memory_graph_path, "r", encoding="utf-8") as graph_file:
                            memory_graph = json.load(graph_file)
                            f.write("=== 记忆图谱 ===\n")
                            f.write(json.dumps(memory_graph, ensure_ascii=False, indent=2))
                            f.write("\n\n")
                except Exception as e:
                    f.write(f"导出记忆图谱时出错: {str(e)}\n\n")
            
            return f"已将所有Chromadb数据保存到当前目录的{output_file}文件中。"
        except Exception as e:
            logger.error(f"导出Chromadb数据时出错: {e}", exc_info=True)
            return f"导出数据时出错: {str(e)}"        