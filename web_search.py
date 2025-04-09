import requests
import logging
import re  # 添加正则表达式模块
import html  # 添加HTML处理模块
import json  # 添加JSON处理模块
from datetime import datetime
from typing import List, Dict, Any, Optional

# 配置日志
logger = logging.getLogger(__name__)

class WebSearchManager:
    """处理网络搜索请求的类，模拟钢铁侠电影中J.A.R.V.I.S.的网络搜索能力"""
    
    def __init__(self, api_key="db2322fc-1cf6-40a4-b8bb-487af2de2a19"):
        """初始化WebSearchManager
        
        Args:
            api_key (str): Exa.ai API密钥
        """
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json"
        }
        self.search_history = []  # 存储搜索历史
        self.max_history = 20     # 最大历史记录数
    
    async def search(self, query: str) -> dict:
        """执行网络搜索
        
        Args:
            query (str): 搜索查询
            
        Returns:
            dict: 包含搜索结果和状态的字典
        """
        try:
            # 记录搜索开始时间
            start_time = datetime.now()
            
            # 执行Exa.ai搜索
            url = "https://api.exa.ai/search"
            
            # 准备请求数据
            data = {
                "query": query,
                "contents": {
                    "text": True,
                    "summary": True,
                }
            }
            
            logger.info(f"执行网络搜索: {query}")
            response = requests.post(url, headers=self.headers, json=data)
            
            if response.status_code == 200:
                # 解析JSON响应
                search_results = response.json()
                
                # 记录搜索结束时间和耗时
                end_time = datetime.now()
                search_duration = (end_time - start_time).total_seconds()
                
                # 处理新的API响应格式
                if "data" in search_results:
                    return self._process_new_api_format(search_results, query, search_duration)
                # 处理旧的API响应格式
                elif "results" in search_results:
                    return self._process_old_api_format(search_results, query, search_duration)
                else:
                    return {
                        "success": False,
                        "error": "未知的API响应格式"
                    }
            else:
                error_msg = f"搜索请求失败，状态码：{response.status_code}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }
        except Exception as e:
            logger.error(f"执行网络搜索时出错: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _process_new_api_format(self, search_results: Dict[str, Any], query: str, duration: float) -> Dict[str, Any]:
        """处理新的API响应格式
        
        Args:
            search_results: API返回的原始结果
            query: 原始查询
            duration: 搜索耗时
            
        Returns:
            处理后的搜索结果
        """
        try:
            data = search_results.get("data", {})
            results = data.get("results", [])
            
            if not results:
                return {
                    "success": False,
                    "error": "无法找到相关的搜索结果"
                }
            
            # 提取文章内容和元数据
            articles = []
            urls = []
            titles = []
            published_dates = []
            
            for result in results:
                # 提取基本信息
                title = result.get("title", "")
                url = result.get("url", "")
                published_date = result.get("publishedDate", "")
                author = result.get("author", "")
                
                # 提取并清理文本内容
                content = result.get("text", "")
                if content:
                    # 移除HTML标签
                    content = re.sub(r'<[^>]+>', ' ', content)
                    # 解码HTML实体
                    content = html.unescape(content)
                    # 处理多余的空白
                    content = re.sub(r'\s+', ' ', content).strip()
                    
                    # 构建格式化的文章
                    article = {
                        "title": title,
                        "url": url,
                        "published_date": published_date,
                        "author": author,
                        "content": content[:500] + ("..." if len(content) > 500 else "")  # 限制内容长度
                    }
                    
                    articles.append(article)
                    urls.append(url)
                    titles.append(title)
                    if published_date:
                        published_dates.append(published_date)
            
            # 构建结构化的响应
            structured_content = self._format_articles(articles)
            
            # 添加到搜索历史
            self._add_to_search_history(query, urls, titles)
            
            # 构建元数据
            metadata = {
                "query": query,
                "duration": f"{duration:.2f}秒",
                "result_count": len(articles),
                "request_id": data.get("requestId", ""),
                "cost": data.get("costDollars", {}).get("total", 0),
                "autoprompt": data.get("autopromptString", ""),
                "search_type": data.get("resolvedSearchType", "")
            }
            
            return {
                "success": True,
                "content": structured_content,
                "urls": urls,
                "titles": titles,
                "published_dates": published_dates,
                "query": query,
                "metadata": metadata,
                "raw_articles": articles  # 包含原始文章数据，以便进一步处理
            }
        except Exception as e:
            logger.error(f"处理新API格式时出错: {e}")
            return {
                "success": False,
                "error": f"处理搜索结果时出错: {str(e)}"
            }
    
    def _process_old_api_format(self, search_results: Dict[str, Any], query: str, duration: float) -> Dict[str, Any]:
        """处理旧的API响应格式
        
        Args:
            search_results: API返回的原始结果
            query: 原始查询
            duration: 搜索耗时
            
        Returns:
            处理后的搜索结果
        """
        try:
            if "results" in search_results and len(search_results["results"]) > 0:
                # 获取前3个结果的文本内容
                results = search_results["results"][:10]
                web_contents = []
                urls = []
                titles = []
                
                for result in results:
                    content = result.get("summary", "")
                    # 移除HTML标签
                    content = re.sub(r'<[^>]+>', ' ', content)
                    # 解码HTML实体
                    content = html.unescape(content)
                    # 处理多余的空白
                    content = re.sub(r'\s+', ' ', content).strip()
                    
                    if content:
                        web_contents.append(content)
                        urls.append(result.get("url", ""))
                        titles.append(result.get("title", ""))
                
                # 合并所有内容
                combined_content = " ".join(web_contents)
                
                # 添加到搜索历史
                self._add_to_search_history(query, urls, titles)
                
                return {
                    "success": True,
                    "content": combined_content,
                    "urls": urls,
                    "titles": titles,
                    "query": query,
                    "metadata": {
                        "duration": f"{duration:.2f}秒",
                        "result_count": len(web_contents)
                    }
                }
            else:
                return {
                    "success": False,
                    "error": "无法找到相关的搜索结果"
                }
        except Exception as e:
            logger.error(f"处理旧API格式时出错: {e}")
            return {
                "success": False,
                "error": f"处理搜索结果时出错: {str(e)}"
            }
    
    def _format_articles(self, articles: List[Dict[str, Any]]) -> str:
        """格式化文章列表为可读文本
        
        Args:
            articles: 文章列表
            
        Returns:
            格式化后的文本
        """
        if not articles:
            return "未找到相关信息。"
        
        formatted_text = "以下是我找到的信息：\n\n"
        
        for i, article in enumerate(articles, 1):
            formatted_text += f"【来源 {i}】{article['title']}\n"
            if article.get('published_date'):
                try:
                    # 尝试格式化日期
                    date_obj = datetime.fromisoformat(article['published_date'].replace('Z', '+00:00'))
                    formatted_date = date_obj.strftime("%Y年%m月%d日")
                    formatted_text += f"发布日期：{formatted_date}\n"
                except:
                    formatted_text += f"发布日期：{article['published_date']}\n"
            
            if article.get('author'):
                formatted_text += f"作者：{article['author']}\n"
            
            formatted_text += f"链接：{article['url']}\n"
            formatted_text += f"内容摘要：{article['content']}\n\n"
        
        return formatted_text
    
    def _add_to_search_history(self, query: str, urls: List[str], titles: List[str]) -> None:
        """添加搜索记录到历史
        
        Args:
            query: 搜索查询
            urls: 结果URL列表
            titles: 结果标题列表
        """
        search_record = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "urls": urls,
            "titles": titles
        }
        
        self.search_history.append(search_record)
        
        # 保持历史记录在限制范围内
        if len(self.search_history) > self.max_history:
            self.search_history.pop(0)
    
    def get_search_history(self) -> List[Dict[str, Any]]:
        """获取搜索历史
        
        Returns:
            搜索历史记录列表
        """
        return self.search_history
    
    def clear_search_history(self) -> None:
        """清除搜索历史"""
        self.search_history = []

# 创建一个简单的函数接口，方便直接调用
async def perform_web_search(query: str, api_key=None, search_manager=None) -> dict:
    """执行网络搜索的便捷函数
    
    Args:
        query (str): 搜索查询
        api_key (str, optional): Exa.ai API密钥，如果不提供则使用默认值
        search_manager (WebSearchManager, optional): 搜索管理器实例，如果不提供则创建新的
        
    Returns:
        dict: 包含搜索结果和状态的字典
    """
    # 使用提供的search_manager或创建新的
    if search_manager is None:
        search_manager = WebSearchManager(api_key) if api_key else WebSearchManager()
    elif api_key:  # 如果提供了search_manager和api_key，更新api_key
        search_manager.api_key = api_key
        search_manager.headers = {
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json"
        }
        
    return await search_manager.search(query) 