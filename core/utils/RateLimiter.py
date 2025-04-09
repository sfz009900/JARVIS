import time
import logging

logger = logging.getLogger("chatbot")

class RateLimiter:
    """请求速率限制器"""
    
    def __init__(self, requests_per_minute: int, tokens_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.request_timestamps = []
        self.token_usage = []
    
    def check_rate_limit(self, tokens: int = 1) -> bool:
        """检查是否超过速率限制"""
        current_time = time.time()
        
        # 清理一分钟前的记录
        self.request_timestamps = [t for t in self.request_timestamps if current_time - t < 60]
        self.token_usage = [(t, count) for t, count in self.token_usage if current_time - t < 60]
        
        # 检查请求数限制
        if len(self.request_timestamps) >= self.requests_per_minute:
            logger.warning(f"请求速率超过限制: {self.requests_per_minute}/分钟")
            return False
        
        # 检查token使用限制
        total_tokens = sum(count for _, count in self.token_usage)
        if total_tokens + tokens > self.tokens_per_minute:
            logger.warning(f"Token使用超过限制: {self.tokens_per_minute}/分钟")
            return False
        
        # 记录本次请求
        self.request_timestamps.append(current_time)
        self.token_usage.append((current_time, tokens))
        
        return True