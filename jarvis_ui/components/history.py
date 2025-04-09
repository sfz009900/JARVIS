"""
Chat history management components for the J.A.R.V.I.S. UI.
"""

import streamlit as st
from datetime import datetime
import time

from jarvis_ui.api import client
from jarvis_ui.utils import state, device

def display_history_sessions():
    """
    Display the list of history sessions and allow users to select a session to restore.
    """
    if not st.session_state.username:
        st.warning("请先输入您的名字")
        return
    
    # Get history sessions
    sessions, error = client.get_sessions()
    
    if error:
        st.error(f"获取历史会话失败: {error}")
        return
    
    if not sessions:
        st.info("没有可用的历史会话")
        return
    
    # Filter current user's sessions
    user_sessions = [s for s in sessions if s.get("username") == st.session_state.username]
    
    if not user_sessions:
        st.info(f"没有找到 {st.session_state.username} 的历史会话")
        return
    
    # Use responsive header based on device
    if device.is_mobile_device() and device.is_small_screen():
        st.write("#### 历史会话")
    else:
        st.subheader("您的历史会话")
    
    # Display session list
    for session in user_sessions:
        session_id = session.get("session_id", "")
        
        # Format dates based on device
        if device.is_mobile_device() and device.is_extra_small_screen():
            # Very compact format for extra small screens
            created_time = datetime.fromtimestamp(session.get("created_at", 0)).strftime("%m-%d %H:%M")
            last_active = datetime.fromtimestamp(session.get("last_active", 0)).strftime("%m-%d %H:%M")
        elif device.is_mobile_device() and device.is_small_screen():
            # Compact format for small screens
            created_time = datetime.fromtimestamp(session.get("created_at", 0)).strftime("%Y-%m-%d %H:%M")
            last_active = datetime.fromtimestamp(session.get("last_active", 0)).strftime("%Y-%m-%d %H:%M")
        else:
            # Full format for desktop
            created_time = datetime.fromtimestamp(session.get("created_at", 0)).strftime("%Y-%m-%d %H:%M:%S")
            last_active = datetime.fromtimestamp(session.get("last_active", 0)).strftime("%Y-%m-%d %H:%M:%S")
            
        message_count = session.get("message_count", 0)
        
        # Create session card with responsive layout
        with st.container():
            if device.is_mobile_device() and device.is_small_screen():
                # Simplified layout for mobile
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"""
                    **ID:** {session_id[:8]}...  
                    **消息:** {message_count}条  
                    **创建:** {created_time}
                    """)
                
                with col2:
                    st.button("加载", key=f"load_{session_id}", 
                              on_click=load_session, args=(session_id,),
                              use_container_width=True)
            else:
                # Desktop layout with more details
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.markdown(f"""
                    **会话ID:** {session_id[:8]}...  
                    **创建时间:** {created_time}  
                    **最后活动:** {last_active}  
                    **消息数量:** {message_count}条
                    """)
                
                with col2:
                    st.button("🔄 加载会话", key=f"load_{session_id}", 
                              on_click=load_session, args=(session_id,))
                
                with col3:
                    if st.button("🗑️ 删除会话", key=f"delete_{session_id}"):
                        with st.spinner("正在删除会话..."):
                            result, error = client.clear_session(session_id)
                            if error:
                                st.error(f"删除失败: {error}")
                            else:
                                st.success("会话已删除!")
                                time.sleep(1)
                                st.rerun()
                
            st.divider()

def load_session(session_id):
    """
    Load a session by its ID.
    
    Args:
        session_id (str): Session ID to load
    """
    # Get session messages
    messages, error = client.get_session_messages(session_id)
    
    if error:
        state.set_error(f"加载会话失败: {error}")
    else:
        # Reset current state and update with loaded session
        state.reset_chat(keep_username=True)
        state.update_session_id(session_id)
        
        # Add loaded messages to state
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            timestamp = datetime.fromtimestamp(msg.get("timestamp", 0))
            image_data = msg.get("image_data")
            
            state.add_message(role, content, timestamp, image_data)
        
        # Exit history view
        state.toggle_history_view()
        
        # Show success message
        st.session_state.load_success = True

def render_history_view():
    """
    Render the history view UI.
    """
    # Get device-specific classes
    classes = device.optimize_for_device()
    
    # Container with responsive class
    st.markdown(f'<div class="history-container {classes["container_class"]}">', unsafe_allow_html=True)
    
    # Header section with back button
    col1, col2 = st.columns([1, 9])
    
    with col1:
        # Larger touch target on mobile
        if device.is_mobile_device():
            if st.button("← 返回", key="back_button", use_container_width=True):
                state.toggle_history_view()
                st.rerun()
        else:
            if st.button("← 返回聊天", key="back_button"):
                state.toggle_history_view()
                st.rerun()
    
    with col2:
        if device.is_mobile_device() and device.is_small_screen():
            st.write("### 会话历史")
        else:
            st.header("会话历史")
    
    st.divider()
    
    # Display session history
    display_history_sessions()
    
    # Close container
    st.markdown('</div>', unsafe_allow_html=True) 