"""
Image handling components for the J.A.R.V.I.S. UI.
"""

import streamlit as st
from io import BytesIO
import base64
from PIL import Image

from jarvis_ui.utils import device

def get_image_to_use():
    """
    Get the current image to use from various possible sources
    (uploader, clipboard, camera).
    
    Returns:
        bytes or None: Image data if available, None otherwise
    """
    # First check if we have a clipboard image
    if "clipboard_image" in st.session_state and st.session_state.clipboard_image:
        return st.session_state.clipboard_image
    
    # Then check if we have a file uploader image
    if "image_uploader" in st.session_state and st.session_state.image_uploader:
        return st.session_state.image_uploader
    
    # Finally check for camera image
    if "camera_input" in st.session_state and st.session_state.camera_input:
        return st.session_state.camera_input
    
    return None

def add_clipboard_handler():
    """
    Add JavaScript to handle clipboard paste events for images.
    This allows users to paste images directly into the chat.
    """
    # Skip on mobile devices as clipboard API may not be well supported
    if device.is_mobile_device():
        return
        
    # Add JavaScript for clipboard image handling
    st.markdown("""
    <script>
    // Function to handle pasted images from clipboard
    document.addEventListener('paste', function(e) {
        // Check if we're pasting an image
        if (e.clipboardData && e.clipboardData.items) {
            const items = e.clipboardData.items;
            
            for (let i = 0; i < items.length; i++) {
                if (items[i].type.indexOf('image') !== -1) {
                    // We found an image
                    const blob = items[i].getAsFile();
                    const reader = new FileReader();
                    
                    reader.onload = function(event) {
                        // Get base64 data
                        const base64Data = event.target.result;
                        
                        // Send to Streamlit
                        window.parent.postMessage({
                            type: 'streamlit:setComponentValue',
                            value: {
                                type: 'clipboard_image',
                                data: base64Data
                            }
                        }, '*');
                        
                        // Show notification
                        const notificationEl = document.createElement('div');
                        notificationEl.style.position = 'fixed';
                        notificationEl.style.bottom = '20px';
                        notificationEl.style.left = '50%';
                        notificationEl.style.transform = 'translateX(-50%)';
                        notificationEl.style.backgroundColor = '#4CAF50';
                        notificationEl.style.color = 'white';
                        notificationEl.style.padding = '10px 20px';
                        notificationEl.style.borderRadius = '5px';
                        notificationEl.style.zIndex = '9999';
                        notificationEl.style.boxShadow = '0 2px 5px rgba(0,0,0,0.2)';
                        notificationEl.innerHTML = '✅ 图片已复制到剪贴板!';
                        
                        document.body.appendChild(notificationEl);
                        
                        // Remove notification after 3 seconds
                        setTimeout(function() {
                            document.body.removeChild(notificationEl);
                        }, 3000);
                    };
                    
                    reader.readAsDataURL(blob);
                    break;
                }
            }
        }
    });
    </script>
    """, unsafe_allow_html=True)

def add_image_removal_handler():
    """
    Add JavaScript handler for removing images uploaded via the uploader.
    """
    st.markdown("""
    <script>
    // Handle image removal via the uploader
    const removeHandler = setInterval(function() {
        const removeButtons = document.querySelectorAll('[data-testid="stFileDeleter"]');
        
        for (const button of removeButtons) {
            if (!button.hasAttribute('data-handled')) {
                button.setAttribute('data-handled', 'true');
                
                button.addEventListener('click', function() {
                    // Notify Streamlit that the image was removed
                    window.parent.postMessage({
                        type: 'streamlit:setComponentValue',
                        value: {
                            type: 'remove_image',
                            data: true
                        }
                    }, '*');
                });
            }
        }
    }, 500);
    </script>
    """, unsafe_allow_html=True)

def optimize_image_uploader():
    """
    Optimize the image uploader for better UX, especially on mobile devices.
    """
    # Only apply these optimizations for mobile
    if not device.is_mobile_device():
        return
        
    # Add optimizations for mobile file uploaders
    st.markdown("""
    <script>
    // Add optimizations for mobile image uploaders
    const optimizeUploaders = setInterval(function() {
        // Find all file uploaders and optimize them
        const uploaders = document.querySelectorAll('[data-testid="stFileUploader"]');
        
        for (const uploader of uploaders) {
            if (!uploader.hasAttribute('data-mobile-optimized')) {
                uploader.setAttribute('data-mobile-optimized', 'true');
                
                // Find the upload button
                const uploadBtn = uploader.querySelector('.uploadMainButton');
                if (uploadBtn) {
                    // Make the button more mobile-friendly
                    uploadBtn.style.padding = '12px';
                    uploadBtn.style.fontSize = '16px';
                    uploadBtn.style.width = '100%';
                    uploadBtn.style.maxWidth = '300px';
                    uploadBtn.style.margin = '10px auto';
                    uploadBtn.style.display = 'block';
                    
                    // Check if we're on iOS
                    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
                    if (isIOS) {
                        // iOS needs special handling
                        uploadBtn.innerText = "从相册选择";
                    }
                }
                
                // Find any file preview containers
                const previewContainers = uploader.querySelectorAll('.uploadedFile');
                previewContainers.forEach(function(container) {
                    // Make file previews more mobile-friendly
                    container.style.maxWidth = '100%';
                    container.style.overflow = 'hidden';
                    
                    // Find the filename and make it smaller
                    const fileInfo = container.querySelector('.uploadedFileName');
                    if (fileInfo) {
                        fileInfo.style.fontSize = '12px';
                        fileInfo.style.overflow = 'hidden';
                        fileInfo.style.textOverflow = 'ellipsis';
                        fileInfo.style.whiteSpace = 'nowrap';
                        fileInfo.style.maxWidth = '200px';
                    }
                });
            }
        }
    }, 500);
    
    // Handle orientation change on mobile
    window.addEventListener('orientationchange', function() {
        // Force redraw of uploaders after orientation change
        setTimeout(function() {
            const uploaders = document.querySelectorAll('[data-testid="stFileUploader"]');
            uploaders.forEach(function(uploader) {
                uploader.removeAttribute('data-mobile-optimized');
            });
        }, 100);
    });
    </script>
    """, unsafe_allow_html=True)

def handle_clipboard_image_callback():
    """
    Handle clipboard image data from JavaScript callback.
    """
    # Check if we have clipboard image data
    if "image_data" in st.session_state:
        image_data = st.session_state.image_data
        
        # Only process if we have actual data
        if image_data and "data" in image_data and image_data["type"] == "clipboard_image":
            # Get the Base64 string
            base64_str = image_data["data"]
            
            # Remove header (like "data:image/png;base64,")
            if "," in base64_str:
                base64_str = base64_str.split(",")[1]
            
            # Decode Base64 to bytes
            image_bytes = base64.b64decode(base64_str)
            
            # Store in session state
            st.session_state.clipboard_image = BytesIO(image_bytes)
            st.session_state.paste_success = True
            
            # Clear the callback data
            st.session_state.image_data = None
        
        # Handle image removal
        elif image_data and image_data["type"] == "remove_image":
            # Clear the image
            if "image_uploader" in st.session_state:
                st.session_state.image_uploader = None
            
            # Clear the callback data
            st.session_state.image_data = None 