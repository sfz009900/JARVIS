"""
Chat component for the J.A.R.V.I.S. UI.
"""

import streamlit as st
from datetime import datetime
from typing import Optional
import io
from PIL import Image
import base64

from jarvis_ui.config import USER_AVATAR_URL, ASSISTANT_AVATAR_URL
from jarvis_ui.utils import state, image_utils, device
from jarvis_ui.api import client

def get_avatar_url(role: str) -> str:
    """
    Get the avatar URL for a chat role.
    
    Args:
        role (str): The role ("user" or "assistant")
        
    Returns:
        str: The avatar URL
    """
    if role == "user":
        return USER_AVATAR_URL
    else:
        return ASSISTANT_AVATAR_URL

def format_message(content: str, timestamp: Optional[datetime] = None) -> str:
    """
    Format a message with optional timestamp.
    
    Args:
        content (str): Message content
        timestamp (Optional[datetime]): Message timestamp
        
    Returns:
        str: Formatted message
    """
    formatted = content
    
    # On mobile devices with small screens, use a more compact timestamp format
    if timestamp and st.session_state.show_timestamps:
        if device.is_mobile_device() and device.is_small_screen():
            time_str = timestamp.strftime("%H:%M")
            formatted += f"\n\n<small>{time_str}</small>"
        else:
            time_str = timestamp.strftime("%H:%M:%S")
            formatted += f"\n\n<small><i>发送时间: {time_str}</i></small>"
    
    return formatted

def display_chat_history():
    """
    Display the current chat conversation history.
    """
    # Get device-specific classes
    classes = device.optimize_for_device()
    
    # Check if we should use compact layout
    use_compact_layout = device.is_mobile_device() and device.is_small_screen()
    
    if not st.session_state.messages:
        # Display welcome message
        display_welcome_message(use_compact_layout)
        return
    
    # Display messages
    for i, message in enumerate(st.session_state.messages):
        # Apply device-specific message styling
        message_class = f"chat-message {message['role']}"
        if device.is_mobile_device():
            message_class += " mobile"
        if device.is_extra_small_screen():
            message_class += " xs-screen"
            
        # Format message content based on device
        content = format_message(
            message["content"], 
            message.get("timestamp")
        )
        
        # Get avatar with appropriate size for device
        avatar_url = get_avatar_url(message["role"])
        
        with st.chat_message(message["role"], avatar=avatar_url):
            st.markdown(content, unsafe_allow_html=True)
            
            # Add image if present
            if message.get("image_data"):
                display_message_image(message["image_data"], is_mobile=device.is_mobile_device())

def display_welcome_message(use_compact_layout=False):
    """
    Display a welcome message when no messages exist.
    
    Args:
        use_compact_layout (bool): Whether to use a compact layout for mobile
    """
    if use_compact_layout:
        st.markdown("""
        👋 **欢迎使用 J.A.R.V.I.S.!**
        
        您可以:
        - 问任何问题
        - 使用 @web 搜索
        - 发送图片分析
        
        我会尽力帮助您!
        """)
    else:
        st.markdown("""
        ## 👋 欢迎使用 J.A.R.V.I.S.!
        
        您可以向我提问任何问题，我会尽力帮助您。以下是一些功能:
        
        - **随时问我任何问题** - 我会尽力提供最好的回答
        - **使用 @web 命令** - 在问题中添加 @web 可以让我进行网络搜索
        - **发送图片** - 您可以发送图片，我会分析并回答相关问题
        
        请在下方输入您的第一个问题以开始对话!
        """)

def display_status():
    """
    Display the API connection status and any error messages.
    """
    if client.check_api_status():
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
    
    if st.session_state.error:
        st.error(st.session_state.error)

def handle_user_input(user_input: str, uploaded_image=None):
    """
    Process user input and send to the API.
    
    Args:
        user_input (str): The text input from the user
        uploaded_image: An optional image file uploaded by the user
    """
    if not user_input and not uploaded_image:
        return
    
    # Prevent processing while a request is in progress
    if st.session_state.is_processing:
        return
    
    state.set_processing_state(True)
    
    # Add user message to chat history
    user_message = user_input
    
    # Process image if present
    image_data = None
    if uploaded_image is not None:
        # Get a unique identifier for the file
        file_identifier = None
        try:
            # Get filename if available
            file_name = getattr(uploaded_image, 'name', None)
            if file_name:
                file_identifier = file_name
            else:
                # Generate temporary filename with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_identifier = f"image_{timestamp}.jpg"
        except Exception as e:
            st.error(f"获取文件名时出错: {str(e)}")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_identifier = f"image_{timestamp}.jpg"
        
        # Check if already processed
        if file_identifier not in st.session_state.processed_image_ids:
            # Convert image for API
            image_bytes = image_utils.prepare_image_for_api(uploaded_image)
            
            if image_bytes:
                # Convert to base64
                image_b64 = base64.b64encode(image_bytes).decode('utf-8')
                
                # Detect image type
                image_type = image_utils.detect_image_type(io.BytesIO(image_bytes))
                
                # Create image data dictionary
                image_data = {
                    "content": image_b64,
                    "mime_type": f"image/{image_type.lower()}"
                }
                
                # Display image preview in message
                img_html = f'<img src="data:image/{image_type.lower()};base64,{image_b64}" alt="上传的图片" style="max-width:200px; max-height:200px; margin:10px 0; border-radius:8px; object-fit:contain;">'
                user_message = f"{user_input}\n\n{img_html}" if user_input else f"[图片]\n\n{img_html}"
                
                # Record processed image
                st.session_state.processed_image_ids.append(file_identifier)
                
                # Limit list size to most recent 30
                if len(st.session_state.processed_image_ids) > 30:
                    st.session_state.processed_image_ids = st.session_state.processed_image_ids[-30:]
    
    # Add user message to state
    state.add_message("user", user_message)
    
    # Display user message
    with st.chat_message("user"):
        avatar_url = get_avatar_url("user")
        col1, col2 = st.columns([1, 11])
        with col1:
            st.image(avatar_url, width=45)
        with col2:
            st.markdown(format_message(user_message, datetime.now()), unsafe_allow_html=True)
    
    # Show AI thinking indicator
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
        
        # Send to API
        result, error = client.send_chat_message(
            username=st.session_state.username,
            message=user_input,
            session_id=st.session_state.session_id,
            image=image_data
        )
        
        if error:
            error_message = f"❌ {error}"
            message_placeholder.markdown(format_message(error_message, datetime.now()), unsafe_allow_html=True)
            state.add_message("assistant", error_message)
            state.set_error(error)
        else:
            ai_response = result["response"]
            state.update_session_id(result["session_id"])
            
            # Process any images in the response
            processed_response = image_utils.extract_image_from_response(ai_response, client.API_URL)
            message_placeholder.markdown(format_message(processed_response, datetime.now()), unsafe_allow_html=True)
            
            # Add to chat history
            state.add_message("assistant", processed_response)
            state.set_error(None)
            
            # Clean up
            if "clipboard_image" in st.session_state:
                del st.session_state.clipboard_image
            
            if "camera_input" in st.session_state:
                del st.session_state.camera_input
                
            # Clean up image_uploader as well (fix for image disappearing but not being sent)
            if "image_uploader" in st.session_state:
                del st.session_state.image_uploader
    
    state.set_processing_state(False)
    
def display_message_image(image_data, is_mobile=False):
    """
    Display an image within a message.
    
    Args:
        image_data (bytes): The image data
        is_mobile (bool): Whether this is displayed on a mobile device
    """
    # Convert bytes to image
    image = Image.open(io.BytesIO(image_data))
    
    # On mobile devices, limit the image width
    if is_mobile:
        # Get container width based on screen size category
        if device.is_extra_small_screen():
            container_width = 240  # Very small screens
        elif device.is_small_screen():
            container_width = 300  # Small screens
        else:
            container_width = 400  # Medium screens
            
        # Calculate aspect ratio
        width, height = image.size
        aspect_ratio = width / height
        
        # Resize image to fit container width
        if width > container_width:
            new_width = container_width
            new_height = int(new_width / aspect_ratio)
            image = image.resize((new_width, new_height))
            
    # Display the image
    st.image(image, use_column_width=True)

def display_image_preview(image_to_use):
    """
    Display a preview of the image to be sent.
    
    Args:
        image_to_use: The image to display
    """
    if image_to_use:
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