"""
Session state management utilities for the J.A.R.V.I.S. UI.
"""

import streamlit as st
from datetime import datetime

def init_session_state():
    """
    Initialize the session state with default values if not already set.
    """
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

def reset_chat():
    """
    Reset the chat state to start a new conversation.
    """
    st.session_state.session_id = None
    st.session_state.messages = []
    st.session_state.error = None
    
def update_session_id(session_id):
    """
    Update the current session ID.
    
    Args:
        session_id (str): The new session ID
    """
    st.session_state.session_id = session_id
    
def add_message(role, content):
    """
    Add a message to the chat history.
    
    Args:
        role (str): The message role ("user" or "assistant")
        content (str): The message content
    """
    st.session_state.messages.append({
        "role": role, 
        "content": content,
        "timestamp": datetime.now()
    })
    
def get_messages():
    """
    Get all messages in the current session.
    
    Returns:
        list: All messages in the current session
    """
    return st.session_state.messages
    
def set_processing_state(is_processing):
    """
    Set the processing state to control UI behavior during API calls.
    
    Args:
        is_processing (bool): Whether the app is currently processing a request
    """
    st.session_state.is_processing = is_processing
    
def set_error(error_message=None):
    """
    Set an error message to display to the user.
    
    Args:
        error_message (str, optional): The error message to display. If None, clears the error.
    """
    st.session_state.error = error_message
    
def toggle_history_view():
    """
    Toggle the history view state.
    """
    st.session_state.show_history = not st.session_state.show_history
    
def set_theme(theme):
    """
    Set the UI theme.
    
    Args:
        theme (str): The theme name ("light" or "dark")
    """
    st.session_state.theme = theme
    
def toggle_timestamps():
    """
    Toggle the display of timestamps.
    """
    st.session_state.show_timestamps = not st.session_state.show_timestamps 