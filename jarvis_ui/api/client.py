"""
API client module for interacting with the J.A.R.V.I.S. backend.
"""

import requests
from typing import Dict, Any, Tuple, List, Optional
import streamlit as st
from jarvis_ui.config import API_URL

def make_api_request(endpoint: str, data: Optional[Dict[str, Any]] = None, method: str = "post") -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Make a request to the API.
    
    Args:
        endpoint (str): The API endpoint to call
        data (Dict[str, Any], optional): The data to send in the request body
        method (str, optional): The HTTP method to use. Defaults to "post".
        
    Returns:
        Tuple[Optional[Dict[str, Any]], Optional[str]]: A tuple containing the API response and an error message (if any)
    """
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

def check_api_status() -> bool:
    """
    Check if the API is available and running.
    
    Returns:
        bool: True if the API is available, False otherwise
    """
    try:
        response = requests.get(f"{API_URL}/health", timeout=2)
        return response.status_code == 200
    except:
        return False

def send_chat_message(username: str, message: str, session_id: Optional[str] = None, image: Optional[Dict[str, str]] = None) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Send a chat message to the API.
    
    Args:
        username (str): The username of the sender
        message (str): The message content
        session_id (str, optional): The session ID for continuing a conversation
        image (Dict[str, str], optional): Image data to include with the message
        
    Returns:
        Tuple[Optional[Dict[str, Any]], Optional[str]]: A tuple containing the API response and an error message (if any)
    """
    data = {
        "username": username,
        "message": message,
        "session_id": session_id
    }
    
    if image:
        data["image"] = image
        # If no message but image is present, set a default message
        if not message:
            data["message"] = "请分析这张图片"
    
    return make_api_request("chat", data)

def get_sessions() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Get a list of active chat sessions.
    
    Returns:
        Tuple[List[Dict[str, Any]], Optional[str]]: A tuple containing the list of sessions and an error message (if any)
    """
    result, error = make_api_request("sessions", method="get")
    
    if error:
        return [], error
    
    # Sort by last active time (descending)
    sessions = sorted(
        result.get("active_sessions", []),
        key=lambda x: x.get("last_active", 0),
        reverse=True
    )
    
    return sessions, None

def get_session(session_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Get a specific chat session by ID.
    
    Args:
        session_id (str): The ID of the session to retrieve
        
    Returns:
        Tuple[Optional[Dict[str, Any]], Optional[str]]: A tuple containing the session data and an error message (if any)
    """
    return make_api_request(f"session/{session_id}", method="get")

def clear_session(session_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Clear (delete) a chat session.
    
    Args:
        session_id (str): The ID of the session to clear
        
    Returns:
        Tuple[Optional[Dict[str, Any]], Optional[str]]: A tuple containing the API response and an error message (if any)
    """
    return make_api_request(f"clear_session/{session_id}")

def create_web_search_url(query: str) -> str:
    """
    Create a URL for performing a web search via the API.
    
    Args:
        query (str): The search query
        
    Returns:
        str: The web search URL
    """
    return f"{API_URL}/search?query={query}" 