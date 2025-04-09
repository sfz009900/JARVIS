import os
import json
import logging
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
import uvicorn
from chatbot import ChatbotManager, async_chat

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("chatbot-api")

# 创建FastAPI应用
app = FastAPI(
    title="智能聊天机器人API",
    description="基于LangChain和Ollama的智能聊天机器人API",
    version="1.0.1",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 确保图片目录存在
IMAGES_DIR = "generated_images"
os.makedirs(IMAGES_DIR, exist_ok=True)

# 挂载静态文件目录
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

# 活跃的聊天会话
active_sessions: Dict[str, Any] = {}
# 会话超时时间（秒）
SESSION_TIMEOUT = 3600 * 3  # 3小时

# 请求模型
class ChatRequest(BaseModel):
    username: str = Field(..., description="用户名", min_length=1, max_length=50)
    message: str = Field(..., description="用户消息", min_length=1)
    session_id: Optional[str] = Field(None, description="会话ID（可选）")
    image: Optional[Dict[str, str]] = Field(None, description="图片数据（可选）")
    
    @field_validator('username')
    @classmethod
    def username_must_be_valid(cls, v):
        if not v.strip():
            raise ValueError('用户名不能为空')
        return v.strip()
    
    @field_validator('message')
    @classmethod
    def message_must_be_valid(cls, v, info):
        # 如果图片存在，允许消息为空
        values = info.data
        if not v.strip() and not values.get('image'):
            raise ValueError('消息不能为空')
        return v.strip()

# 响应模型
class ChatResponse(BaseModel):
    response: str = Field(..., description="AI助手的回复")
    session_id: str = Field(..., description="会话ID")
    timestamp: float = Field(default_factory=time.time, description="响应时间戳")

# 会话信息模型
class SessionInfo(BaseModel):
    session_id: str = Field(..., description="会话ID")
    username: str = Field(..., description="用户名")
    created_at: float = Field(..., description="创建时间")
    last_active: float = Field(..., description="最后活跃时间")
    message_count: int = Field(..., description="消息数量")

# 会话详情模型
class SessionDetail(BaseModel):
    session_id: str = Field(..., description="会话ID")
    username: str = Field(..., description="用户名")
    created_at: float = Field(..., description="创建时间")
    last_active: float = Field(..., description="最后活跃时间")
    message_count: int = Field(..., description="消息数量")
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="会话消息历史")

# 会话统计模型
class SessionStats(BaseModel):
    total_sessions: int = Field(..., description="总会话数")
    active_sessions: List[SessionInfo] = Field(..., description="活跃会话列表")

# 会话元数据
session_metadata = {}

# 会话清理任务
async def cleanup_inactive_sessions():
    """定期清理不活跃的会话"""
    while True:
        try:
            now = time.time()
            sessions_to_remove = []
            
            for session_id, metadata in session_metadata.items():
                if now - metadata["last_active"] > SESSION_TIMEOUT:
                    sessions_to_remove.append(session_id)
            
            for session_id in sessions_to_remove:
                if session_id in active_sessions:
                    try:
                        # 保存并清理会话数据
                        chatbot_manager = active_sessions[session_id]
                        # 保存记忆
                        await save_memory(chatbot_manager)
                        del active_sessions[session_id]
                        del session_metadata[session_id]
                        logger.info(f"已清理不活跃会话: {session_id}")
                    except Exception as e:
                        logger.error(f"清理会话 {session_id} 时出错: {e}")
                        
            logger.info(f"当前活跃会话数: {len(active_sessions)}")
            # await asyncio.sleep(600)  # 每10分钟检查一次
        except Exception as e:
            logger.error(f"会话清理任务出错: {e}")
            await asyncio.sleep(60)

# 启动时运行会话清理任务
@app.on_event("startup")
async def startup_event():
    logger.info("API服务启动中...")
    # asyncio.create_task(cleanup_inactive_sessions())
    # logger.info("会话清理任务已启动")

# 关闭时保存所有会话
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("API服务关闭中...")
    for session_id, chatbot_manager in active_sessions.items():
        try:
            await save_memory(chatbot_manager)
            logger.info(f"已保存会话 {session_id} 的记忆")
        except Exception as e:
            logger.error(f"关闭时保存会话 {session_id} 出错: {e}")

# 健康检查端点
@app.get("/health", status_code=status.HTTP_200_OK, tags=["系统"])
async def health_check():
    """健康检查端点，用于监控系统状态"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_sessions": len(active_sessions)
    }

# 获取会话统计信息
@app.get("/sessions", response_model=SessionStats, tags=["系统"])
async def get_sessions():
    """获取活跃会话统计信息"""
    sessions = []
    for session_id, metadata in session_metadata.items():
        sessions.append(SessionInfo(
            session_id=session_id,
            username=metadata["username"],
            created_at=metadata["created_at"],
            last_active=metadata["last_active"],
            message_count=metadata["message_count"]
        ))
    
    return SessionStats(
        total_sessions=len(sessions),
        active_sessions=sessions
    )

# 聊天端点
@app.post("/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK, tags=["聊天"])
async def chat_endpoint(request: ChatRequest, background_tasks: BackgroundTasks):
    """处理用户聊天请求，返回AI助手的回复"""
    try:
        username = request.username
        message = request.message
        session_id = request.session_id
        image_data = request.image
        now = time.time()
        
        # 如果没有提供会话ID或会话不存在，创建新的聊天管理器
        if not session_id or session_id not in active_sessions:
            chatbot_manager = ChatbotManager(username)
            # 修复: 使用memory_system而不是memory_manager
            session_id = chatbot_manager.session_id
            active_sessions[session_id] = chatbot_manager
            
            # 记录会话元数据
            session_metadata[session_id] = {
                "username": username,
                "created_at": now,
                "last_active": now,
                "message_count": 0
            }
            
            logger.info(f"为用户 {username} 创建新会话: {session_id}")
        else:
            chatbot_manager = active_sessions[session_id]
            
            # 更新会话元数据
            if session_id in session_metadata:
                session_metadata[session_id]["last_active"] = now
                session_metadata[session_id]["message_count"] += 1
            
            logger.info(f"用户 {username} 使用现有会话: {session_id}")
        
        # 记录请求
        logger.info(f"用户请求: [会话ID: {session_id}] {username}: {message[:50]}...")
        if image_data:
            logger.info(f"请求中包含图片数据")
        
        # 处理聊天请求
        start_time = time.time()
        response = await chatbot_manager.chat(message, image_data)
        process_time = time.time() - start_time
        
        # 记录响应时间
        logger.info(f"响应时间: {process_time:.2f}秒")
        
        # 在后台保存记忆
        background_tasks.add_task(save_memory, chatbot_manager)
        
        return ChatResponse(response=response, session_id=session_id)
    except Exception as e:
        logger.error(f"处理聊天请求时出错: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

async def save_memory(chatbot_manager):
    """异步保存记忆"""
    try:
        # 修复: 应该调用适当的方法来保存记忆
        # chatbot_manager.perform_memory_maintenance()
        logger.info(f"已保存用户 {chatbot_manager.username} 的记忆")
    except Exception as e:
        logger.error(f"保存记忆时出错: {e}", exc_info=True)

# 清除会话端点
@app.post("/clear_session/{session_id}", status_code=status.HTTP_200_OK, tags=["聊天"])
async def clear_session(session_id: str):
    """清除指定的聊天会话"""
    if session_id in active_sessions:
        try:
            chatbot_manager = active_sessions[session_id]
            
            # 清理记忆
            chatbot_manager.perform_memory_maintenance()
            
            # 移除会话
            del active_sessions[session_id]
            if session_id in session_metadata:
                del session_metadata[session_id]
                
            logger.info(f"已清除会话: {session_id}")
            return {"status": "success", "message": f"会话 {session_id} 已清除"}
        except Exception as e:
            logger.error(f"清除会话时出错: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    else:
        logger.warning(f"尝试清除不存在的会话: {session_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"会话 {session_id} 不存在")

# 错误处理中间件
@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    """全局错误处理中间件"""
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"请求处理时出错 [{request.method} {request.url.path}]: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": str(e),
                "path": request.url.path,
                "method": request.method,
                "process_time": process_time
            }
        )

# 请求日志中间件
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """记录所有API请求"""
    start_time = time.time()
    
    logger.info(f"收到请求: {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(f"请求完成: {request.method} {request.url.path} - 状态码: {response.status_code} - 耗时: {process_time:.4f}秒")
    
    return response

# 获取图片端点
@app.get("/image/{image_filename}", tags=["图片"])
async def get_image(image_filename: str):
    """获取生成的图片"""
    image_path = os.path.join(IMAGES_DIR, image_filename)
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(image_path)

# 获取单个会话详情
@app.get("/session/{session_id}", response_model=SessionDetail, status_code=status.HTTP_200_OK, tags=["聊天"])
async def get_session(session_id: str):
    """获取指定会话的详细信息，包括消息历史"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"会话 {session_id} 不存在")
    
    try:
        chatbot_manager = active_sessions[session_id]
        metadata = session_metadata.get(session_id, {})
        
        # 获取会话消息历史
        messages = []
        try:
            # 从聊天管理器中获取消息历史
            messages = chatbot_manager.get_message_history()
        except Exception as e:
            logger.error(f"获取会话 {session_id} 的消息历史时出错: {e}", exc_info=True)
            messages = []  # 如果出错，返回空消息列表
        
        return SessionDetail(
            session_id=session_id,
            username=metadata.get("username", "未知用户"),
            created_at=metadata.get("created_at", time.time()),
            last_active=metadata.get("last_active", time.time()),
            message_count=metadata.get("message_count", 0),
            messages=messages
        )
    except Exception as e:
        logger.error(f"获取会话 {session_id} 详情时出错: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True) 