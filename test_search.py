import asyncio
import json
from web_search import WebSearchManager
import unittest
from unittest.mock import patch, MagicMock

class TestWebSearch(unittest.TestCase):
    
    @patch('requests.post')
    async def test_search_with_mock_data(self, mock_post):
        # 创建模拟响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        # 使用提供的JSON示例
        mock_json = {
            "requestId": "5d9808ad10f66ea6d300193c272d41c9",
            "autopromptString": "遵义的天气是:",
            "autoDate": "2025-03-09T11:54:44.780Z",
            "resolvedSearchType": "keyword",
            "results": [
                {
                    "id": "https://www.weather.com.cn/weather/101260201.shtml",
                    "title": "预报- 遵义 - 中国天气网",
                    "url": "https://www.weather.com.cn/weather/101260201.shtml",
                    "publishedDate": "2025-03-02T08:00:00.000Z",
                    "author": "",
                    "text": "今天 \n \n \n 7天 \n \n \n 8-15天 \n \n \n 40天 \n \n \n 雷达图 \n \n \n \n \n \n 2日（今天） \n 多云转阴 \n \n 22 / 10℃ \n \n \n \n \n \n \n &lt;3级 \n \n \n \n 3日（明天） \n 阴转阵雨 \n \n 17 / 5℃"
                }
            ]
        }
        
        mock_response.json.return_value = mock_json
        mock_post.return_value = mock_response
        
        # 执行搜索
        search_manager = WebSearchManager()
        result = await search_manager.search("遵义今天天气")
        
        # 验证结果
        self.assertTrue(result["success"])
        self.assertIn("多云转阴", result["content"])
        self.assertEqual(result["url"], "https://www.weather.com.cn/weather/101260201.shtml")
        
        print("测试成功！搜索结果:")
        print(f"URL: {result['url']}")
        print(f"内容预览: {result['content'][:100]}...")

async def main():
    # 运行测试
    test = TestWebSearch()
    await test.test_search_with_mock_data()

if __name__ == "__main__":
    asyncio.run(main()) 