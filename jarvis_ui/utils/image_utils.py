"""
Image processing utilities for the J.A.R.V.I.S. UI.
"""

import base64
import io
from datetime import datetime
from PIL import Image
import streamlit as st
import re
import requests
import os

from jarvis_ui.utils import device

def handle_clipboard_image():
    """
    Process clipboard paste events for images.
    
    Returns:
        bool: True if an image was successfully processed, False otherwise
    """
    # Check for image data coming from the component callback
    if "image_data" in st.session_state and st.session_state.image_data:
        image_data = st.session_state.image_data
        
        # Process clipboard image data
        if image_data.get("type") == "clipboard_image" and image_data.get("data"):
            try:
                # Get the base64 data
                base64_data = image_data["data"]
                
                # Remove the header if present
                if "," in base64_data:
                    base64_data = base64_data.split(",")[1]
                
                # Decode the base64 data
                image_bytes = base64.b64decode(base64_data)
                
                # Create a BytesIO object
                image_io = io.BytesIO(image_bytes)
                
                # Store in session state
                st.session_state.clipboard_image = image_io
                
                # Set success flag for notification
                st.session_state.paste_success = True
                
                # Clear the callback data
                st.session_state.image_data = None
                
                return True
            except Exception as e:
                st.error(f"图片处理错误: {str(e)}")
                st.session_state.image_data = None
                return False
    
    return False

def image_to_base64(image_data):
    """
    Convert image data to base64 string.
    
    Args:
        image_data: The image data to convert
        
    Returns:
        str: Base64 encoded string
    """
    try:
        # Handle different types of image data
        if isinstance(image_data, io.BytesIO):
            # Reset the position to the beginning of the file
            image_data.seek(0)
            image_bytes = image_data.read()
        elif isinstance(image_data, bytes):
            image_bytes = image_data
        else:
            # Attempt to read as file-like object
            image_data.seek(0)
            image_bytes = image_data.read()
            
        # Encode to base64
        base64_str = base64.b64encode(image_bytes).decode('utf-8')
        return base64_str
    except Exception as e:
        st.error(f"图片编码错误: {str(e)}")
        return None

def detect_image_type(image_data):
    """
    Detect the type (format) of an image.
    
    Args:
        image_data: The image data
        
    Returns:
        str: Image format (e.g., 'JPEG', 'PNG')
    """
    try:
        # Reset position if it's a file-like object
        if hasattr(image_data, 'seek'):
            image_data.seek(0)
        
        # Open with PIL to detect format
        image = Image.open(image_data)
        return image.format
    except Exception:
        # Default to PNG if detection fails
        return "PNG"

def extract_image_from_response(response_text, api_url):
    """
    Extract image URLs from AI response text and convert to markdown.
    
    Args:
        response_text (str): The response text from the AI
        api_url (str): The base API URL
        
    Returns:
        str: The response with image URLs converted to markdown
    """
    # Pattern to match image URLs
    pattern = r'!\[([^\]]*)\]\((https?://[^)]+)\)'
    
    def replace_with_hosted_image(match):
        # Get the alt text and URL
        alt_text = match.group(1)
        url = match.group(2)
        
        try:
            # Download the image
            response = requests.get(url, stream=True, timeout=10)
            response.raise_for_status()
            
            # Create a BytesIO object from the content
            img_data = io.BytesIO(response.content)
            
            # Open the image with PIL
            image = Image.open(img_data)
            
            # Resize for mobile if needed
            if device.is_mobile_device() and device.is_small_screen():
                # Get screen width
                screen_width = st.session_state.get("screen_width", 375)  # Default to iPhone SE width
                
                # Calculate new size based on screen width
                max_width = min(screen_width - 40, 800)  # Leave some margins
                
                # Get current width and height
                width, height = image.size
                
                # Only resize if larger than max_width
                if width > max_width:
                    ratio = height / width
                    new_width = max_width
                    new_height = int(new_width * ratio)
                    image = image.resize((new_width, new_height))
            
            # Save to BytesIO
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format=image.format)
            img_byte_arr.seek(0)
            
            # Convert to markdown image tag
            return f"![{alt_text}](data:image/{image.format.lower()};base64,{base64.b64encode(img_byte_arr.read()).decode()})"
        except Exception as e:
            # If there's an error, return the original match
            return match.group(0)
    
    # Replace all image URLs with data URLs
    processed_text = re.sub(pattern, replace_with_hosted_image, response_text)
    return processed_text

def prepare_image_for_api(uploaded_image):
    """
    Prepare an uploaded image for API submission.
    
    Args:
        uploaded_image: The uploaded image
        
    Returns:
        bytes: Processed image bytes
    """
    try:
        if uploaded_image is None:
            return None
        
        # Reset stream position
        if hasattr(uploaded_image, 'seek'):
            uploaded_image.seek(0)
        
        # Open with PIL for processing
        image = Image.open(uploaded_image)
        
        # Optimize the image for API upload
        max_size = (1024, 1024)  # Set reasonable max size
        
        # Resize if needed while maintaining aspect ratio
        if image.width > max_size[0] or image.height > max_size[1]:
            image.thumbnail(max_size, Image.LANCZOS)
        
        # Convert to RGB if needed
        if image.mode == 'RGBA':
            # Create a white background
            background = Image.new('RGB', image.size, (255, 255, 255))
            # Paste the image using alpha as mask
            background.paste(image, mask=image.split()[3])
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Save to BytesIO
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG', quality=85)
        img_byte_arr.seek(0)
        
        return img_byte_arr.getvalue()
    except Exception as e:
        st.error(f"图片处理错误: {str(e)}")
        return None 