import streamlit as st
import requests
import json
import os
import re
from datetime import datetime
import time
import base64
from typing import Optional, Dict, Any, List
from PIL import Image
import io

# 配置
API_URL = "http://localhost:8000"

# 创建自定义Streamlit组件处理剪贴板粘贴
class ClipboardReceiver:
    def __init__(self):
        self.image_data = None
        
    def handle_clipboard(self, image_data):
        """处理从剪贴板接收的图片数据"""
        self.image_data = image_data
        return True

# 处理剪贴板图片上传
def handle_clipboard_image():
    if "clipboard_receiver" not in st.session_state:
        st.session_state.clipboard_receiver = ClipboardReceiver()
    
    # 检查是否有新的粘贴事件
    if "clipboard_event" in st.session_state and st.session_state.clipboard_event:
        # 从前端接收的图片数据处理逻辑
        image_data = st.session_state.clipboard_event.get("image_data")
        if image_data:
            # 将Base64图片数据转换为BytesIO对象
            import base64
            from io import BytesIO
            
            try:
                # 解析Data URL格式
                header, encoded = image_data.split(",", 1)
                image_bytes = base64.b64decode(encoded)
                
                # 创建BytesIO对象
                image_buffer = BytesIO(image_bytes)
                image_buffer.name = "clipboard_image.png"  # 设置文件名
                
                # 存储到会话状态
                st.session_state.clipboard_image = image_buffer
                # 清除事件以避免重复处理
                st.session_state.clipboard_event = None
                
                # 设置粘贴成功标志
                st.session_state.paste_success = True
                
                return True
            except Exception as e:
                st.error(f"处理剪贴板图片出错: {str(e)}")
                st.session_state.clipboard_event = None
    
    return False

# 页面配置
st.set_page_config(
    page_title="J.A.R.V.I.S. AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS
def load_css():
    st.markdown("""
    <style>
    /* 全局样式 */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    /* 主题颜色 */
    :root {
        --primary-color: #2196F3;
        --secondary-color: #1565C0;
        --background-light: #FFFFFF;
        --background-dark: #1A1A1A;
        --text-light: #333333;
        --text-dark: #FFFFFF;
        --accent-color: #00BFA5;
    }
    
    /* 暗色模式 */
    [data-theme="dark"] {
        --background-color: var(--background-dark);
        --text-color: var(--text-dark);
    }
    
    /* 亮色模式 */
    [data-theme="light"] {
        --background-color: var(--background-light);
        --text-color: var(--text-light);
    }
    
    /* 修复Streamlit容器样式 */
    .main {
        overflow: visible !important;
        height: auto !important;
        padding-bottom: 80px !important;
    }
    
    .stApp {
        overflow: visible !important;
        height: 100vh !important;
    }
    
    /* 移动端优化样式 */
    @media (max-width: 768px) {
        /* 侧边栏宽度调整 */
        .css-1d391kg {
            width: 100% !important;
        }
        
        /* 优化相机输入控件 */
        button.streamlit-button.camera-input {
            width: 100% !important;
            padding: 12px !important;
            font-size: 16px !important;
            margin: 10px 0 !important;
        }
        
        /* 优化文件上传器 */
        section[data-testid="stFileUploader"] {
            display: block !important;
            visibility: visible !important;
            height: auto !important;
            width: 100% !important;
            position: relative !important;
            opacity: 1 !important;
            pointer-events: auto !important;
        }
        
        /* 文件上传器提示文本优化 */
        .uploadMainButton {
            font-size: 16px !important;
            padding: 12px !important;
            width: 100% !important;
            margin: 10px 0 !important;
        }
        
        /* 优化选项卡样式 */
        .stTabs [data-baseweb="tab-list"] {
            gap: 2px;
        }
        
        .stTabs [data-baseweb="tab"] {
            padding: 10px 5px;
            font-size: 14px;
        }
    }
    
    /* 隐藏文件上传器的拖放区域 - 仅对非移动设备 */
    .desktop-only section[data-testid="stFileUploader"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        width: 0 !important;
        position: absolute !important;
        top: -9999px !important;
        left: -9999px !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }
    
    /* 显示移动设备上的文件上传器 */
    .mobile-visible section[data-testid="stFileUploader"] {
        display: block !important;
        visibility: visible !important;
        height: auto !important;
        width: 100% !important;
        position: relative !important;
        opacity: 1 !important;
        pointer-events: auto !important;
    }
    
    /* 隐藏文件上传器的所有子元素 - 仅对非移动设备 */
    .desktop-only section[data-testid="stFileUploader"] * {
        display: none !important;
        visibility: hidden !important;
    }
    
    /* 修复垂直块边框包装器的位置 */
    .stVerticalBlockBorderWrapper {
        position: relative !important;
        order: 1 !important;
        z-index: 1 !important;
    }
    
    /* 相机输入控件样式优化 */
    [data-testid="stCameraInput"] {
        width: 100% !important;
    }
    
    [data-testid="stCameraInput"] > button {
        width: 100% !important;
        background-color: var(--primary-color) !important;
        color: white !important;
        border-radius: 8px !important;
        padding: 10px !important;
        font-weight: 500 !important;
        transition: all 0.3s ease !important;
    }
    
    [data-testid="stCameraInput"] > button:hover {
        background-color: var(--secondary-color) !important;
        transform: translateY(-2px) !important;
    }
    
    /* 添加固定底部输入区域的CSS */
    .main-container {
        display: flex;
        flex-direction: column;
        min-height: 100vh;
        height: auto;
        position: relative;
    }
    
    .chat-container {
        flex: 1;
        overflow-y: auto;
        padding-bottom: 100px; /* 为底部输入区域留出空间 */
        margin-bottom: 60px;
        order: 0;
    }
    
    .input-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: white;
        padding: 10px 20px;
        border-top: 1px solid #eee;
        z-index: 100;
        margin-left: 260px; /* 为侧边栏留出空间 */
        order: 2;
    }
    
    /* 暗色模式适配 */
    [data-theme="dark"] .input-container {
        background: #1A1A1A;
        border-top: 1px solid #333;
    }
    
    @media (max-width: 992px) {
        .input-container {
            margin-left: 0;
        }
    }
    
    /* 图片预览区域样式 */
    .image-preview-area {
        background-color: rgba(0,0,0,0.03);
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 10px;
    }
    
    [data-theme="dark"] .image-preview-area {
        background-color: rgba(255,255,255,0.05);
    }
    
    /* 图片附件指示器样式优化 */
    .image-attachment-indicator {
        display: inline-flex;
        align-items: center;
        background-color: rgba(33,150,243,0.1);
        color: #2196F3;
        padding: 0.3rem 0.6rem;
        border-radius: 1rem;
        font-size: 0.8rem;
        margin-bottom: 0.5rem;
        font-weight: 500;
    }
    
    /* 聊天消息样式 */
    .chat-message {
        padding: 1.5rem;
        border-radius: 1rem;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: flex-start;
        border: none;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        animation: slideIn 0.3s ease-out;
        max-width: 85%;
        position: relative;
        overflow: hidden;
    }
    
    .chat-message.user {
        background: linear-gradient(135deg, #6B8DD6 0%, #8E37D7 100%);
        color: white;
        margin-left: auto;
        border-bottom-right-radius: 0.2rem;
    }
    
    .chat-message.assistant {
        background: linear-gradient(135deg, #40C9FF 0%, #E81CFF 100%);
        color: white;
        margin-right: auto;
        border-bottom-left-radius: 0.2rem;
    }
    
    .chat-message .avatar {
        width: 45px;
        height: 45px;
        border-radius: 50%;
        object-fit: cover;
        margin-right: 1rem;
        border: 2px solid white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: transform 0.3s ease;
    }
    
    .chat-message .avatar:hover {
        transform: scale(1.1);
    }
    
    .chat-message .message {
        flex: 1;
        overflow-x: auto;
        font-size: 1rem;
        line-height: 1.5;
    }
    
    /* 输入框样式 */
    .stTextInput>div>div>input {
        padding: 1rem;
        border-radius: 1rem;
        border: 2px solid rgba(0,0,0,0.1);
        transition: all 0.3s ease;
        font-size: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    .stTextInput>div>div>input:focus {
        border-color: var(--primary-color);
        box-shadow: 0 0 0 2px rgba(33,150,243,0.2);
    }
    
    /* 按钮样式 */
    .stButton>button {
        border-radius: 1rem;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
        border: none;
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
        color: white;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    /* 自定义上传按钮 */
    .custom-upload-btn {
        position: fixed;
        bottom: 20px;
        right: 20px;
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background-color: #2196F3;
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        z-index: 1000;
        font-size: 18px;
        border: none;
        transition: all 0.3s ease;
    }
    
    .custom-upload-btn:hover {
        background-color: #1565C0;
        transform: scale(1.05);
        box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    }
    
    /* 调整聊天输入框样式，为按钮留出空间 */
    .stChatInput {
        padding-right: 50px !important;
    }
    
    /* 状态指示器 */
    .status-indicator {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 6px;
    }
    
    .status-indicator.online {
        background-color: #4CAF50;
        box-shadow: 0 0 8px rgba(76,175,80,0.5);
        animation: pulse 2s infinite;
    }
    
    .status-indicator.offline {
        background-color: #F44336;
        box-shadow: 0 0 8px rgba(244,67,54,0.5);
    }
    
    /* 工具提示 */
    [data-tooltip] {
        position: relative;
        cursor: pointer;
    }
    
    [data-tooltip]:before {
        content: attr(data-tooltip);
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%);
        padding: 0.5rem 1rem;
        background: rgba(0,0,0,0.8);
        color: white;
        border-radius: 0.5rem;
        font-size: 0.875rem;
        white-space: nowrap;
        opacity: 0;
        visibility: hidden;
        transition: all 0.3s ease;
    }
    
    [data-tooltip]:hover:before {
        opacity: 1;
        visibility: visible;
    }
    
    /* 加载动画 */
    @keyframes typing {
        0% { content: ""; }
        25% { content: "."; }
        50% { content: ".."; }
        75% { content: "..."; }
        100% { content: ""; }
    }
    
    .typing-indicator:after {
        content: "";
        animation: typing 1.5s infinite;
    }
    
    /* 动画效果 */
    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    
    /* 滚动条美化 */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(0,0,0,0.05);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: var(--primary-color);
        border-radius: 10px;
        transition: all 0.3s ease;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: var(--secondary-color);
    }
    
    /* 代码块样式优化 */
    pre {
        border-radius: 0.8rem !important;
        padding: 1.2rem !important;
        background-color: #1E1E1E !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        margin: 1rem 0 !important;
    }
    
    code {
        font-family: 'JetBrains Mono', 'Consolas', monospace !important;
        font-size: 0.9rem !important;
        line-height: 1.4 !important;
    }
    
    /* 侧边栏样式 */
    .css-1d391kg {
        background: linear-gradient(180deg, var(--background-color) 0%, rgba(33,150,243,0.05) 100%);
        border-right: 1px solid rgba(0,0,0,0.1);
    }
    
    /* 响应式设计 */
    @media (max-width: 768px) {
        .chat-message {
            max-width: 95%;
            padding: 1rem;
        }
        
        .chat-message .avatar {
            width: 35px;
            height: 35px;
        }
    }
    
    /* 聊天输入框容器样式 */
    .chat-input-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: var(--background-color);
        padding: 1rem;
        border-top: 1px solid rgba(49, 51, 63, 0.2);
        z-index: 1000;
        margin-left: 15rem;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }
    
    .input-wrapper {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        max-width: 800px;
        margin: 0 auto;
        position: relative;
        width: 100%;
    }
    
    .input-wrapper .stChatInput {
        flex: 1;
        margin: 0 !important;
        visibility: visible !important;
        display: block !important;
        padding-right: 3rem !important;
    }
    
    .upload-btn {
        position: absolute;
        right: 10px;
        top: 50%;
        transform: translateY(-50%);
        background: transparent;
        border: none;
        cursor: pointer;
        font-size: 1.5rem;
        padding: 0.5rem;
        transition: all 0.2s;
        z-index: 1001;
        color: #666;
    }
    
    .upload-btn:hover {
        color: var(--primary-color);
        transform: translateY(-50%) scale(1.1);
    }
    
    /* 图片预览区域样式 */
    .image-preview-container {
        background-color: rgba(0,0,0,0.03);
        border-radius: 8px;
        padding: 0.5rem;
        margin-bottom: 0.5rem;
        max-width: 800px;
        margin: 0 auto;
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
    }
    
    [data-theme="dark"] .image-preview-container {
        background-color: rgba(255,255,255,0.05);
    }
    
    .image-preview {
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    
    .image-info {
        flex: 1;
        font-size: 0.875rem;
        color: #666;
    }
    
    .remove-image-btn {
        background: transparent;
        border: none;
        color: #f44336;
        cursor: pointer;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.875rem;
        transition: all 0.2s;
    }
    
    .remove-image-btn:hover {
        background-color: rgba(244, 67, 54, 0.1);
    }
    
    /* 确保聊天输入框在移动设备上也可见 */
    @media (max-width: 768px) {
        .chat-input-container {
            margin-left: 0;
        }
    }
    
    /* 修复Streamlit容器样式 */
    .main {
        padding-bottom: 80px !important;
    }
    
    .stApp {
        height: 100vh !important;
    }
    
    /* 确保输入框可见性 */
    div[data-testid="stChatInput"] {
        visibility: visible !important;
        display: block !important;
        opacity: 1 !important;
    }
    
    textarea[data-testid="stChatInput"] {
        visibility: visible !important;
        display: block !important;
        opacity: 1 !important;
        padding-right: 3rem !important;
    }
    
    /* 暗色模式适配 */
    @media (prefers-color-scheme: dark) {
        .chat-input-container {
            background: var(--background-color);
            border-top-color: rgba(250, 250, 250, 0.2);
        }
    }
    </style>
    """, unsafe_allow_html=True)

# 初始化会话状态
def init_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "session_id" not in st.session_state:
        st.session_state.session_id = None
    if "username" not in st.session_state:
        st.session_state.username = ""
    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False
    if "error" not in st.session_state:
        st.session_state.error = None
    if "theme" not in st.session_state:
        st.session_state.theme = "light"
    if "show_timestamps" not in st.session_state:
        st.session_state.show_timestamps = True
    if "history_sessions" not in st.session_state:
        st.session_state.history_sessions = []
    if "show_history" not in st.session_state:
        st.session_state.show_history = False
    if "clipboard_image" not in st.session_state:
        st.session_state.clipboard_image = None
    if "clipboard_event" not in st.session_state:
        st.session_state.clipboard_event = None
    if "paste_success" not in st.session_state:
        st.session_state.paste_success = False
    if "processed_image_ids" not in st.session_state:
        st.session_state.processed_image_ids = []
    if "is_mobile" not in st.session_state:
        st.session_state.is_mobile = False
    if "device_type" not in st.session_state:
        st.session_state.device_type = "desktop"
    if "browser_type" not in st.session_state:
        st.session_state.browser_type = "other"

# 检测设备类型
def detect_device_type():
    # 添加 JavaScript 代码来检测设备类型并存储到 session_state
    st.markdown("""
    <script>
    // 检测移动设备
    function detectMobileDevice() {
        const userAgent = navigator.userAgent || navigator.vendor || window.opera;
        
        // 检查常见的移动设备关键字
        const isMobile = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini|mobile|tablet/i.test(userAgent);
        
        // 获取详细的设备类型
        let deviceType = 'desktop';
        if (isMobile) {
            if (/iphone|ipod/i.test(userAgent)) {
                deviceType = 'iphone';
            } else if (/ipad/i.test(userAgent)) {
                deviceType = 'ipad';
            } else if (/android/i.test(userAgent)) {
                deviceType = 'android';
            } else {
                deviceType = 'other_mobile';
            }
        }
        
        // 检测浏览器类型
        let browserType = 'other';
        if (/chrome/i.test(userAgent)) {
            browserType = 'chrome';
        } else if (/firefox/i.test(userAgent)) {
            browserType = 'firefox';
        } else if (/safari/i.test(userAgent) && !/chrome/i.test(userAgent)) {
            browserType = 'safari';
        }
        
        // 将设备信息发送到 Streamlit
        window.parent.postMessage({
            type: 'streamlit:setComponentValue',
            value: {
                is_mobile: isMobile,
                device_type: deviceType,
                browser_type: browserType
            }
        }, '*');
    }
    
    // 页面加载时执行检测
    document.addEventListener('DOMContentLoaded', detectMobileDevice);
    </script>
    """, unsafe_allow_html=True)

def get_avatar_url(role: str) -> str:
    """获取头像URL"""
    if role == "user":
        return "https://api.dicebear.com/7.x/avataaars/svg?seed=user"
    else:
        return "https://api.dicebear.com/7.x/bottts/svg?seed=jarvis"

def format_message(content: str, timestamp: Optional[datetime] = None) -> str:
    """格式化消息内容"""
    formatted = content
    if timestamp and st.session_state.show_timestamps:
        time_str = timestamp.strftime("%H:%M:%S")
        formatted += f"\n\n<small><i>发送时间: {time_str}</i></small>"
    return formatted

# 显示聊天历史
def display_chat_history():
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            avatar_url = get_avatar_url(message["role"])
            timestamp = datetime.now() if idx == len(st.session_state.messages) - 1 else None
            
            col1, col2 = st.columns([1, 11])
            with col1:
                st.image(avatar_url, width=45)
            with col2:
                st.markdown(format_message(message["content"], timestamp), unsafe_allow_html=True)

# 获取历史会话列表
def get_history_sessions():
    """从API获取历史会话列表"""
    result, error = make_api_request("sessions", method="get")
    if error:
        st.error(f"获取历史会话失败: {error}")
        return []
    
    # 按最后活跃时间排序
    sessions = sorted(
        result.get("active_sessions", []),
        key=lambda x: x.get("last_active", 0),
        reverse=True
    )
    
    return sessions

# 加载历史会话
def load_session(session_id):
    """加载指定ID的历史会话"""
    result, error = make_api_request(f"session/{session_id}", method="get")
    if error:
        st.error(f"加载会话失败: {error}")
        return False
    
    # 更新会话状态
    st.session_state.session_id = session_id
    st.session_state.messages = result.get("messages", [])
    return True

# 显示历史会话列表
def display_history_sessions():
    """显示历史会话列表并允许用户选择恢复"""
    if not st.session_state.username:
        st.warning("请先输入您的名字")
        return
    
    # 获取历史会话
    sessions = get_history_sessions()
    
    if not sessions:
        st.info("没有可用的历史会话")
        return
    
    # 过滤当前用户的会话
    user_sessions = [s for s in sessions if s.get("username") == st.session_state.username]
    
    if not user_sessions:
        st.info(f"没有找到 {st.session_state.username} 的历史会话")
        return
    
    st.subheader("您的历史会话")
    
    # 显示会话列表
    for session in user_sessions:
        session_id = session.get("session_id", "")
        created_time = datetime.fromtimestamp(session.get("created_at", 0)).strftime("%Y-%m-%d %H:%M:%S")
        last_active = datetime.fromtimestamp(session.get("last_active", 0)).strftime("%Y-%m-%d %H:%M:%S")
        message_count = session.get("message_count", 0)
        
        # 创建会话卡片
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.markdown(f"""
                **会话ID**: {session_id[:8]}...  
                **创建时间**: {created_time}  
                **最后活跃**: {last_active}  
                **消息数量**: {message_count}
                """)
            
            with col2:
                if st.button("恢复", key=f"restore_{session_id}"):
                    if load_session(session_id):
                        st.session_state.show_history = False
                        st.success(f"已恢复会话 {session_id[:8]}...")
                        st.rerun()
            
            with col3:
                if st.button("删除", key=f"delete_{session_id}"):
                    result, error = make_api_request(f"clear_session/{session_id}")
                    if error:
                        st.error(f"删除会话失败: {error}")
                    else:
                        st.success(f"已删除会话 {session_id[:8]}...")
                        time.sleep(1)
                        st.rerun()
        
        st.divider()

# 侧边栏功能
def render_sidebar():
    with st.sidebar:
        st.title("🤖 J.A.R.V.I.S.")
        
        # 用户名输入
        username = st.text_input("👤 您的名字:", value=st.session_state.username,
                               placeholder="请输入您的名字...")
        
        if username and username != st.session_state.username:
            st.session_state.username = username
            st.session_state.session_id = None
            st.session_state.messages = []
            st.rerun()
        
        st.divider()
        
        # 根据设备类型显示不同的上传控件
        if st.session_state.is_mobile:
            st.subheader("📷 添加图片")
            st.caption("请选择上传方式:")
            
            # 1. 相机拍照上传（较为稳定的方式）
            camera_tab, gallery_tab = st.tabs(["拍照上传", "从相册选择"])
            
            with camera_tab:
                st.caption("📸 使用相机直接拍照上传")
                camera_image = st.camera_input("拍照", key="camera_input", 
                                               help="点击拍照按钮进行拍照，拍照后点击使用此照片")
                
                if camera_image is not None:
                    # 将相机拍摄的照片设置为上传图片
                    if "image_uploader" not in st.session_state or st.session_state.image_uploader != camera_image:
                        st.session_state.image_uploader = camera_image
                        st.success("✅ 已成功添加拍照图片!")
            
            with gallery_tab:
                st.caption("🖼️ 从相册中选择图片上传")
                st.info("⚠️ 注意：在某些移动浏览器上此功能可能不稳定")
                # 原有的 file_uploader
                uploaded_file = st.file_uploader(
                    "选择图片",
                    type=["jpg", "jpeg", "png"],
                    key="image_uploader",
                    accept_multiple_files=False,
                    help="支持 JPG、JPEG、PNG 格式的图片"
                )
                
                # 添加技术问题提示
                if st.session_state.device_type in ['iphone', 'ipad'] and st.session_state.browser_type == 'safari':
                    st.info("📱 iOS Safari 提示: 如果从相册无法上传，请尝试使用拍照上传选项")
                elif st.session_state.browser_type == 'chrome':
                    st.info("📱 Chrome 提示: 如果从相册无法上传，请尝试使用拍照上传选项")
        else:
            # PC 设备使用原来的文件上传器
            uploaded_file = st.file_uploader(
                "📷 上传图片",
                type=["jpg", "jpeg", "png"],
                key="image_uploader",
                accept_multiple_files=False,
                help="支持 JPG、JPEG、PNG 格式的图片"
            )
        
        st.divider()
        
        # 会话管理
        st.subheader("⚙️ 会话管理")
        
        col1, col2 = st.columns(2)
        
        # 新会话按钮
        with col1:
            if st.button("🆕 新会话", use_container_width=True):
                st.session_state.session_id = None
                st.session_state.messages = []
                st.session_state.error = None
                st.session_state.show_history = False
                st.rerun()
        
        # 清除会话按钮
        with col2:
            if st.session_state.session_id and st.button("🗑️ 清除", use_container_width=True):
                with st.spinner("正在清除会话..."):
                    result, error = make_api_request(f"clear_session/{st.session_state.session_id}")
                    if error:
                        st.error(error)
                    else:
                        st.session_state.session_id = None
                        st.session_state.messages = []
                        st.session_state.error = None
                        st.success("会话已清除!")
                        time.sleep(1)
                        st.rerun()
        
        # 历史会话按钮
        if st.button("📜 历史会话", use_container_width=True):
            st.session_state.show_history = not st.session_state.show_history
            st.rerun()
        
        # 显示当前会话信息
        if st.session_state.session_id:
            st.info(f"🔑 会话ID: {st.session_state.session_id[:8]}...")
        
        st.divider()
        
        # 设置
        st.subheader("🛠️ 设置")
        
        # 主题切换
        theme = st.selectbox("🎨 界面主题",
                           options=["light", "dark"],
                           format_func=lambda x: "明亮模式" if x == "light" else "暗黑模式",
                           index=0 if st.session_state.theme == "light" else 1)
        
        if theme != st.session_state.theme:
            st.session_state.theme = theme
            st.rerun()
        
        # 时间戳显示
        show_timestamps = st.toggle("🕒 显示时间戳",
                                  value=st.session_state.show_timestamps)
        
        if show_timestamps != st.session_state.show_timestamps:
            st.session_state.show_timestamps = show_timestamps
            st.rerun()
        
        st.divider()
        
        # 关于信息
        with st.expander("ℹ️ 关于"):
            st.write("""
            ### J.A.R.V.I.S. AI Assistant
            
            一个强大的AI助手，具有以下特点:
            
            - 🧠 智能对话
            - 💭 上下文记忆
            - 🎯 精准理解
            - 🌐 网络搜索
            - 💻 代码分析
            - 📝 文本生成
            
            使用 `@web` 命令可以进行网络搜索
            """)
        
        # 版本信息
        st.caption("Version 2.0.0 • © 2025 J.A.R.V.I.S.")

# 显示状态和错误
def display_status():
    try:
        response = requests.get(f"{API_URL}/health", timeout=2)
        if response.status_code == 200:
            st.sidebar.markdown("""
            <div style="display: flex; align-items: center; margin-top: 1rem;">
                <span class="status-indicator online"></span>
                <span style="color: #4CAF50; font-weight: 500;">系统在线运行中</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.sidebar.markdown("""
            <div style="display: flex; align-items: center; margin-top: 1rem;">
                <span class="status-indicator offline"></span>
                <span style="color: #F44336; font-weight: 500;">系统服务异常</span>
            </div>
            """, unsafe_allow_html=True)
    except:
        st.sidebar.markdown("""
        <div style="display: flex; align-items: center; margin-top: 1rem;">
            <span class="status-indicator offline"></span>
            <span style="color: #F44336; font-weight: 500;">无法连接到服务</span>
        </div>
        """, unsafe_allow_html=True)
    
    if st.session_state.error:
        st.error(st.session_state.error)
    
    # 添加设备信息调试区（仅开发模式显示）
    with st.sidebar.expander("📱 设备信息", expanded=False):
        st.write(f"设备类型: {st.session_state.device_type}")
        st.write(f"是否移动设备: {st.session_state.is_mobile}")
        st.write(f"浏览器类型: {st.session_state.browser_type}")

# API请求处理
def make_api_request(endpoint, data=None, method="post"):
    """统一处理API请求"""
    try:
        url = f"{API_URL}/{endpoint}"
        
        if method.lower() == "post":
            response = requests.post(url, json=data, timeout=900)
        else:
            response = requests.get(url, timeout=900)
        
        if response.status_code == 200:
            return response.json(), None
        else:
            error_detail = response.json().get('detail', '未知错误')
            return None, f"API请求失败 ({response.status_code}): {error_detail}"
    
    except requests.exceptions.Timeout:
        return None, "API请求超时，请检查服务器状态"
    except requests.exceptions.ConnectionError:
        return None, "无法连接到API服务器，请确认服务器是否运行"
    except Exception as e:
        return None, f"发生错误: {str(e)}"

# 处理用户输入
def handle_user_input(user_input, uploaded_image=None):
    if not user_input and not uploaded_image:
        return
    
    # 防止重复处理或空输入
    if st.session_state.is_processing:
        return
    
    st.session_state.is_processing = True
    
    # 添加用户消息到聊天历史
    user_message = user_input
    
    # 处理图片（如果有）
    image_data = None
    if uploaded_image is not None:
        # 获取文件名作为唯一标识符
        file_identifier = None
        try:
            # 获取文件名（如果有）
            file_name = getattr(uploaded_image, 'name', None)
            if file_name:
                file_identifier = file_name
            else:
                # 如果无法获取文件名，使用时间戳生成临时文件名
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_identifier = f"image_{timestamp}.jpg"
        except Exception as e:
            st.error(f"获取文件名时出错: {str(e)}")
            # 使用时间戳生成临时文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_identifier = f"image_{timestamp}.jpg"
        
        # 检查是否已处理过该图片
        if file_identifier not in st.session_state.processed_image_ids:
            # 将图片转换为base64编码
            if isinstance(uploaded_image, io.BytesIO):
                image_bytes = uploaded_image.getvalue()
            else:
                # 保存当前位置
                current_pos = uploaded_image.tell()
                # 读取内容
                uploaded_image.seek(0)
                image_bytes = uploaded_image.read()
                # 恢复位置
                uploaded_image.seek(current_pos)
                
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # 检测图像类型（如果没有指定）
            image_type = getattr(uploaded_image, 'type', None)
            if not image_type:
                # 尝试从文件头判断图像类型
                if image_bytes.startswith(b'\xff\xd8'):
                    image_type = "image/jpeg"
                elif image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
                    image_type = "image/png"
                elif image_bytes.startswith(b'GIF87a') or image_bytes.startswith(b'GIF89a'):
                    image_type = "image/gif"
                else:
                    # 默认使用 jpeg
                    image_type = "image/jpeg"
            
            image_data = {
                "content": image_b64,
                "mime_type": image_type
            }
            
            # 在消息中显示图片预览
            img_html = f'<img src="data:{image_type};base64,{image_b64}" alt="上传的图片" style="max-width:200px; max-height:200px; margin:10px 0; border-radius:8px; object-fit:contain;">'
            user_message = f"{user_input}\n\n{img_html}" if user_input else f"[图片]\n\n{img_html}"
            
            # 记录已处理的图片标识符
            st.session_state.processed_image_ids.append(file_identifier)
            
            # 限制列表大小，保持最新的30个记录
            if len(st.session_state.processed_image_ids) > 30:
                st.session_state.processed_image_ids = st.session_state.processed_image_ids[-30:]
    
    st.session_state.messages.append({"role": "user", "content": user_message})
    
    with st.chat_message("user"):
        avatar_url = get_avatar_url("user")
        col1, col2 = st.columns([1, 11])
        with col1:
            st.image(avatar_url, width=45)
        with col2:
            st.markdown(format_message(user_message, datetime.now()), unsafe_allow_html=True)
    
    # 显示AI正在思考
    with st.chat_message("assistant"):
        avatar_url = get_avatar_url("assistant")
        col1, col2 = st.columns([1, 11])
        with col1:
            st.image(avatar_url, width=45)
        with col2:
            message_placeholder = st.empty()
            message_placeholder.markdown("""
            <div class="typing-indicator">
                J.A.R.V.I.S. 正在思考中
            </div>
            """, unsafe_allow_html=True)
        
        # 准备请求数据
        data = {
            "username": st.session_state.username,
            "message": user_input,
            "session_id": st.session_state.session_id
        }
        
        # 添加图片数据（如果有）
        if image_data:
            data["image"] = image_data
            # 确保消息字段非空，即使没有用户输入，也发送一个默认消息
            if not user_input:
                data["message"] = "请分析这张图片"
        
        # 发送请求到API
        result, error = make_api_request("chat", data)
        
        if error:
            error_message = f"❌ {error}"
            message_placeholder.markdown(format_message(error_message, datetime.now()), unsafe_allow_html=True)
            st.session_state.messages.append({"role": "assistant", "content": error_message})
            st.session_state.error = error
        else:
            ai_response = result["response"]
            st.session_state.session_id = result["session_id"]
            
            # 处理可能包含的图片并显示AI响应
            processed_response = display_image_from_response(ai_response)
            message_placeholder.markdown(format_message(processed_response, datetime.now()), unsafe_allow_html=True)
            
            # 添加AI响应到聊天历史 - 存储处理后的响应（包含图片HTML）而不是原始响应
            st.session_state.messages.append({"role": "assistant", "content": processed_response})
            st.session_state.error = None
            
            # 清除剪贴板图片（如果存在）
            if "clipboard_image" in st.session_state:
                del st.session_state.clipboard_image
            
            # 清除相机图片（如果存在）
            if "camera_input" in st.session_state:
                del st.session_state.camera_input
    
    st.session_state.is_processing = False

# 显示图片
def display_image_from_response(response_text: str) -> str:
    """从响应文本中提取图片路径并显示图片
    
    Args:
        response_text: AI响应文本
        
    Returns:
        处理后的响应文本（移除图片标记）
    """
    # 检查响应是否包含图片标记
    image_pattern = r'\[已生成图片，保存在: (.+?)\]'
    image_match = re.search(image_pattern, response_text)
    
    if not image_match:
        return response_text
    
    # 提取图片路径
    image_path = image_match.group(1)
    
    # 从路径中提取文件名
    image_filename = os.path.basename(image_path)
    
    try:
        # 构建图片URL
        image_url = f"{API_URL}/image/{image_filename}"
        
        # 获取图片数据
        response = requests.get(image_url)
        if response.status_code == 200:
            # 将图片转换为base64编码，直接嵌入HTML
            image_data = base64.b64encode(response.content).decode('utf-8')
            image_type = response.headers.get('Content-Type', 'image/png')
            
            # 创建图片HTML标签，使用data URI方案
            image_html = f'<img src="data:{image_type};base64,{image_data}" alt="生成的图片" style="max-width:100%; max-height:400px; margin:10px 0; border-radius:8px; object-fit:contain; display:block;">'
            
            # 移除图片标记
            clean_response = re.sub(image_pattern, '', response_text).strip()
            
            # 添加图片HTML到响应
            return f"{clean_response}\n\n{image_html}"
        else:
            st.warning(f"无法加载图片: {image_url}")
            return response_text
    except Exception as e:
        st.warning(f"处理图片时出错: {str(e)}")
        return response_text

# 主界面
def main():
    # 加载CSS
    load_css()
    
    # 初始化会话状态
    init_session_state()
    
    # 检测设备类型
    detect_device_type()
    
    # 渲染侧边栏
    render_sidebar()
    
    # 主界面
    if st.session_state.show_history:
        # 显示历史会话列表
        st.markdown(f"""
        <h1 style="text-align: center; margin-bottom: 2rem;">
            历史会话
            <div style="font-size: 1rem; color: #666; margin-top: 0.5rem;">
                选择一个会话进行恢复
            </div>
        </h1>
        """, unsafe_allow_html=True)
        
        display_history_sessions()
    else:
        # 创建主容器结构
        st.markdown('<div class="main-container">', unsafe_allow_html=True)
        
        # 聊天历史容器
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        
        # 显示聊天界面标题
        st.markdown(f"""
        <h1 style="text-align: center; margin-bottom: 2rem;">
            欢迎使用 J.A.R.V.I.S.
            <div style="font-size: 1rem; color: #666; margin-top: 0.5rem;">
                您的智能AI助手
            </div>
        </h1>
        """, unsafe_allow_html=True)
        
        # 显示聊天历史
        display_chat_history()
        
        # 显示状态和错误
        display_status()
        
        # 关闭聊天容器
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 添加自动滚动到底部的JavaScript
        st.markdown("""
        <script>
        // 页面加载完成后滚动到底部以查看最新消息
        window.addEventListener('load', function() {
            // 修复Streamlit的滚动问题
            const mainElement = document.querySelector('.main');
            if (mainElement) {
                mainElement.style.overflow = 'visible';
                mainElement.style.height = 'auto';
            }
            
            const appElement = document.querySelector('.stApp');
            if (appElement) {
                appElement.style.overflow = 'visible';
                appElement.style.height = 'auto';
            }
            
            // 修复文件上传器样式
            const fileUploaders = document.querySelectorAll('section[data-testid="stFileUploader"]');
            fileUploaders.forEach(function(uploader) {
                uploader.style.display = 'none';
                uploader.style.visibility = 'hidden';
            });
            
            // 修复垂直块边框包装器的位置
            const verticalBlocks = document.querySelectorAll('.stVerticalBlockBorderWrapper');
            verticalBlocks.forEach(function(block) {
                block.style.position = 'relative';
                block.style.order = '1';
                block.style.zIndex = '1';
            });
            
            // 确保聊天容器在输入框上方
            const chatContainer = document.querySelector('.chat-container');
            if (chatContainer) {
                chatContainer.style.order = '0';
            }
            
            // 确保输入容器在底部
            const inputContainer = document.querySelector('.input-container');
            if (inputContainer) {
                inputContainer.style.order = '2';
                inputContainer.style.position = 'fixed';
                inputContainer.style.bottom = '0';
                inputContainer.style.left = '0';
                inputContainer.style.right = '0';
                inputContainer.style.zIndex = '100';
            }
            
            // 滚动到最新消息
            const messages = document.querySelectorAll('.stChatMessage');
            if (messages && messages.length > 0) {
                const lastMessage = messages[messages.length - 1];
                lastMessage.scrollIntoView({ behavior: 'auto', block: 'end' });
            }
        });
        
        // 监听DOM变化，当有新消息时自动滚动到底部
        const observer = new MutationObserver(function(mutations) {
            // 检查是否有新的聊天消息添加
            const messages = document.querySelectorAll('.stChatMessage');
            if (messages && messages.length > 0) {
                const lastMessage = messages[messages.length - 1];
                lastMessage.scrollIntoView({ behavior: 'smooth', block: 'end' });
            }
        });
        
        // 开始观察DOM变化
        setTimeout(function() {
            const chatContainer = document.querySelector('.chat-container');
            if (chatContainer) {
                observer.observe(chatContainer, { 
                    childList: true, 
                    subtree: true 
                });
            }
        }, 1000);
        </script>
        """, unsafe_allow_html=True)
        
        # 创建一个容器来放置输入区域，确保它在页面底部
        st.markdown('<div class="input-container">', unsafe_allow_html=True)
        
        # 检查是否有通过clipboard粘贴的图片
        clipboard_image = st.session_state.get("clipboard_image", None)
        
        # 用户输入
        if st.session_state.username:
            # 处理剪贴板图片
            paste_successful = handle_clipboard_image()
            
            # 如果有粘贴成功的标志，显示通知
            if st.session_state.get("paste_success", False):
                st.success("✅ 图片已成功粘贴!")
                st.session_state.paste_success = False
            
            # 创建输入框
            placeholder = "正在处理上一条消息..." if st.session_state.is_processing else "输入您的消息，使用 @web 进行网络搜索..."
            user_input = st.chat_input(placeholder, disabled=st.session_state.is_processing)
            
            # 获取上传的文件
            uploaded_file = st.session_state.get("image_uploader", None)
            
            # 获取相机拍摄的图片
            camera_image = st.session_state.get("camera_input", None)
            
            # 选择要使用的图片（优先使用最新上传的图片）
            image_to_use = None
            if uploaded_file:
                image_to_use = uploaded_file
            elif camera_image:
                image_to_use = camera_image
            
            # 获取剪贴板图片
            clipboard_image = st.session_state.get("clipboard_image", None)
            if not image_to_use and clipboard_image:
                image_to_use = clipboard_image
            
            # 显示图片预览和指示器（如果有）
            if image_to_use:
                # 创建一个容器来显示预览
                with st.container():
                    st.markdown("""
                    <div class="image-preview-container">
                        <div class="image-preview">
                            <div class="image-attachment-indicator">
                                <i class="fas fa-image"></i> 已附加图片
                            </div>
                    """, unsafe_allow_html=True)
                    
                    try:
                        if isinstance(image_to_use, io.BytesIO):
                            image_to_use.seek(0)
                            try:
                                img = Image.open(image_to_use)
                                width, height = img.size
                                img_format = img.format
                                img_size = len(image_to_use.getvalue()) / 1024  # KB
                                image_to_use.seek(0)
                                st.image(image_to_use, width=100)
                                st.markdown(f'<div class="image-info">{width}x{height} ({img_format}, {img_size:.1f}KB)</div>', unsafe_allow_html=True)
                            except Exception:
                                image_to_use.seek(0)
                                st.image(image_to_use, width=100)
                        else:
                            st.image(image_to_use, width=100)
                    except Exception as e:
                        st.error(f"无法预览图片: {str(e)}")
                    
                    st.markdown("""
                        </div>
                        <button class="remove-image-btn" onclick="removeImage()">删除图片</button>
                    </div>
                    """, unsafe_allow_html=True)
            
            # 处理用户输入和图片
            if user_input and image_to_use:
                handle_user_input(user_input, image_to_use)
            elif user_input and not image_to_use:
                handle_user_input(user_input)
        else:
            st.info("👈 请在侧边栏输入您的名字以开始对话")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # 关闭输入容器
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 关闭主容器
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 添加额外的JavaScript来确保正确的布局和滚动
    st.markdown("""
    <script>
    // 确保在页面完全加载后执行
    window.addEventListener('load', function() {
        // 强制修复stVerticalBlockBorderWrapper的位置
        setTimeout(function() {
            // 获取所有的垂直块边框包装器
            const verticalBlocks = document.querySelectorAll('.stVerticalBlockBorderWrapper');
            
            // 获取聊天容器和输入容器
            const chatContainer = document.querySelector('.chat-container');
            const inputContainer = document.querySelector('.input-container');
            
            if (verticalBlocks.length > 0 && chatContainer && inputContainer) {
                // 将垂直块移动到聊天容器中
                for (let i = 0; i < verticalBlocks.length; i++) {
                    const block = verticalBlocks[i];
                    
                    // 检查是否包含聊天输入
                    if (block.querySelector('.stChatInput')) {
                        // 这是输入块，应该放在输入容器中
                        inputContainer.appendChild(block);
                    } else {
                        // 这是聊天消息块，应该放在聊天容器中
                        chatContainer.appendChild(block);
                    }
                }
                
                // 滚动到最新消息
                const messages = document.querySelectorAll('.stChatMessage');
                if (messages && messages.length > 0) {
                    const lastMessage = messages[messages.length - 1];
                    lastMessage.scrollIntoView({ behavior: 'auto', block: 'end' });
                }
            }
        }, 500);
    });
    </script>
    """, unsafe_allow_html=True)

    # 添加JavaScript代码来优化用户体验
    st.markdown("""
    <script>
    // 处理图片删除
    function removeImage() {
        // 通知Streamlit删除图片
        window.parent.postMessage({
            type: "streamlit:setComponentValue",
            value: {
                clipboard_image: null,
                image_uploader: null,
                camera_input: null
            }
        }, "*");
        
        // 重新加载页面以更新状态
        window.location.reload();
    }
    
    document.addEventListener('DOMContentLoaded', function() {
        // 移动Streamlit的chat input到我们的容器中
        const chatInput = document.querySelector('.stChatInput');
        const inputWrapper = document.querySelector('.input-wrapper');
        if (chatInput && inputWrapper) {
            inputWrapper.insertBefore(chatInput, inputWrapper.firstChild);
        }
        
        // 创建隐藏的文件输入
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = 'image/jpeg, image/png, image/jpg';
        fileInput.style.display = 'none';
        fileInput.id = 'hiddenFileInput';
        fileInput.capture = 'environment'; // 添加capture属性以支持移动设备相机
        document.body.appendChild(fileInput);
        
        // 监听上传按钮点击
        document.addEventListener('click', function(e) {
            if (e.target.closest('#uploadBtn')) {
                e.preventDefault();
                const fileInput = document.getElementById('hiddenFileInput');
                if (fileInput) {
                    fileInput.click();
                }
            }
        });

        // 监听文件选择
        document.addEventListener('change', function(e) {
            if (e.target.id === 'hiddenFileInput' && e.target.files && e.target.files[0]) {
                const streamlitUploader = document.querySelector('section[data-testid="stFileUploader"] input[type="file"]');
                if (streamlitUploader) {
                    try {
                        // 使用更兼容的方式处理文件
                        const file = e.target.files[0];
                        
                        // 检查是否支持DataTransfer API
                        if (typeof DataTransfer !== 'undefined') {
                            const dataTransfer = new DataTransfer();
                            dataTransfer.items.add(file);
                            streamlitUploader.files = dataTransfer.files;
                        } else {
                            // 备用方案 - 直接设置files属性（可能不适用于所有浏览器）
                            try {
                                streamlitUploader.files = e.target.files;
                            } catch (err) {
                                console.error("无法直接设置files属性:", err);
                                // 最后的备用方案 - 触发点击事件
                                streamlitUploader.click();
                                return;
                            }
                        }
                        
                        // 触发change事件
                        const event = new Event('change', { bubbles: true });
                        streamlitUploader.dispatchEvent(event);
                        
                        showToast('图片已上传');
                    } catch (err) {
                        console.error("文件上传处理错误:", err);
                        showToast('上传失败，请重试', 'error');
                    }
                }
            }
        });
        
        // 监听粘贴事件
        document.addEventListener('paste', function(e) {
            const chatInput = document.querySelector('.stChatInput input');
            if (!chatInput || !chatInput.matches(':focus')) {
                return; // 只在输入框聚焦时处理粘贴
            }
            
            if (e.clipboardData && e.clipboardData.items) {
                const items = e.clipboardData.items;
                let imageFile = null;
                let hasText = false;
                
                for (let i = 0; i < items.length; i++) {
                    if (items[i].type.indexOf('image') !== -1) {
                        imageFile = items[i].getAsFile();
                    } else if (items[i].type.indexOf('text') !== -1) {
                        hasText = true;
                    }
                }
                
                if (imageFile && !hasText) {
                    e.preventDefault(); // 只有在没有文本的情况下阻止默认粘贴
                    const reader = new FileReader();
                    reader.onload = function(event) {
                        window.parent.postMessage({
                            type: "streamlit:setComponentValue",
                            value: {
                                clipboard_event: {
                                    image_data: event.target.result
                                }
                            }
                        }, "*");
                        
                        showToast('图片已粘贴');
                    };
                    reader.readAsDataURL(imageFile);
                }
            }
        });
        
        // 显示提示消息
        function showToast(message, type = 'success') {
            const toast = document.createElement('div');
            toast.className = 'upload-toast ' + (type === 'error' ? 'upload-toast-error' : '');
            toast.textContent = message;
            document.body.appendChild(toast);
            
            setTimeout(() => {
                toast.remove();
            }, 2000);
        }
        
        // 特别为移动设备优化的事件处理
        if (/android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini|mobile|tablet/i.test(navigator.userAgent)) {
            // 尝试修复移动设备上的文件上传问题
            const fileUploaders = document.querySelectorAll('section[data-testid="stFileUploader"]');
            
            fileUploaders.forEach(uploader => {
                // 确保文件上传器在移动设备上可见
                uploader.classList.add('mobile-visible');
                uploader.classList.remove('desktop-only');
                
                // 尝试修复上传按钮的样式
                const uploadButtons = uploader.querySelectorAll('button, .uploadMainButton');
                uploadButtons.forEach(button => {
                    button.style.width = '100%';
                    button.style.padding = '12px';
                    button.style.fontSize = '16px';
                    button.style.margin = '10px 0';
                });
                
                // 尝试直接挂载事件监听器
                const inputElements = uploader.querySelectorAll('input[type="file"]');
                inputElements.forEach(input => {
                    // 添加capture属性以优化相机访问
                    input.setAttribute('capture', 'environment');
                    
                    // 移除可能与移动设备不兼容的属性
                    if (input.hasAttribute('webkitdirectory')) {
                        input.removeAttribute('webkitdirectory');
                    }
                    
                    // 直接处理change事件
                    input.addEventListener('change', function(e) {
                        if (e.target.files && e.target.files.length > 0) {
                            console.log("文件已选择:", e.target.files[0].name);
                            showToast('文件已选择: ' + e.target.files[0].name);
                        }
                    });
                });
            });
        } else {
            // 在桌面设备上添加desktop-only类
            const fileUploaders = document.querySelectorAll('section[data-testid="stFileUploader"]');
            fileUploaders.forEach(uploader => {
                uploader.classList.add('desktop-only');
                uploader.classList.remove('mobile-visible');
            });
        }
    });
    </script>
    
    <style>
    .upload-toast {
        position: fixed;
        bottom: 20px;
        right: 20px;
        background-color: #4CAF50;
        color: white;
        padding: 10px 20px;
        border-radius: 4px;
        font-size: 14px;
        z-index: 9999;
        animation: fadeInOut 2s ease-in-out;
    }
    
    .upload-toast-error {
        background-color: #F44336;
    }
    
    @keyframes fadeInOut {
        0% { opacity: 0; transform: translateY(20px); }
        10% { opacity: 1; transform: translateY(0); }
        90% { opacity: 1; transform: translateY(0); }
        100% { opacity: 0; transform: translateY(-20px); }
    }
    </style>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main() 