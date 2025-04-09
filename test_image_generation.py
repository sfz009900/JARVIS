import os
import asyncio
import logging
from image_generation import GeminiImageGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("test_image_generation")

async def test_image_generation():
    """测试图片生成功能"""
    # 获取API密钥
    api_key = "AIzaSyDXJRkdBaCMCt0NASc6gC73bA2MRTfYlQQ"
    if not api_key:
        logger.error("未提供 Gemini API 密钥，测试将失败")
        return
    
    # 初始化图片生成器
    generator = GeminiImageGenerator(api_key)
    
    # 测试用例
    test_cases = [
        "一个可爱的卡通角色，有着大大的眼睛，圆圆的脸，蓝色的皮肤，头上有两个小触角，总是带着友好的笑容",
        "宇航员穿着白色宇航服，站在月球表面上。月球表面是灰色的，布满了陨石坑。背景是黑色的太空，可以看到地球和星星"
    ]
    
    # 运行测试
    for i, prompt in enumerate(test_cases):
        logger.info(f"运行测试用例 {i+1}: {prompt}")
        
        # 测试 Gemini 2.0 Flash
        logger.info("使用 Gemini 2.0 Flash 生成图片")
        result = await generator.generate_image_from_prompt(prompt, use_imagen=False)
        
        if result["success"]:
            logger.info(f"Gemini 图片生成成功: {result['images'][0]['image_path']}")
        else:
            logger.warning(f"Gemini 图片生成失败: {result.get('error', '未知错误')}")
        logger.info("-" * 50)

if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_image_generation()) 