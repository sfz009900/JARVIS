"""
J.A.R.V.I.S. AI Assistant - Main Application Entry Point

This module is the main entry point for the J.A.R.V.I.S. AI Assistant application.
It orchestrates all the components and handles the application flow.
"""

import streamlit as st
import os
import time

from jarvis_ui.config import PAGE_TITLE, PAGE_ICON, DEFAULT_LAYOUT, INITIAL_SIDEBAR_STATE, API_URL
from jarvis_ui.utils import state, device, image_utils
from jarvis_ui.components import sidebar, chat, history, image_handler

def load_css():
    """
    Load CSS styles from the static directory.
    """
    css_path = os.path.join(os.path.dirname(__file__), "static", "styles.css")
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def add_responsive_meta_tags():
    """
    Add responsive meta tags for better mobile display.
    Includes specific optimizations for iOS Safari and other mobile browsers.
    """
    st.markdown("""
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#2196F3">
    <meta name="format-detection" content="telephone=no">
    """, unsafe_allow_html=True)

def add_keyboard_handling():
    """
    Add JavaScript for handling mobile keyboard events.
    """
    st.markdown("""
    <script>
    // Handle keyboard events
    function setupKeyboardHandling() {
        const inputContainer = document.querySelector('.chat-input-container');
        if (!inputContainer) return;
        
        // Handle keyboard show/hide
        window.addEventListener('resize', function() {
            const isKeyboardOpen = window.innerHeight < window.outerHeight;
            inputContainer.classList.toggle('keyboard-open', isKeyboardOpen);
        });
        
        // Handle input focus
        const input = document.querySelector('textarea[data-testid="stChatInput"]');
        if (input) {
            input.addEventListener('focus', function() {
                inputContainer.classList.add('keyboard-open');
                // Scroll to bottom
                window.scrollTo(0, document.body.scrollHeight);
            });
            
            input.addEventListener('blur', function() {
                inputContainer.classList.remove('keyboard-open');
            });
        }
    }
    
    // Setup on page load
    document.addEventListener('DOMContentLoaded', setupKeyboardHandling);
    
    // Also try setting up after Streamlit is loaded
    window.addEventListener('load', function() {
        setTimeout(setupKeyboardHandling, 500);
    });
    </script>
    """, unsafe_allow_html=True)

def add_performance_optimizations():
    """
    Add JavaScript for performance optimizations.
    """
    st.markdown("""
    <script>
    // Performance optimizations
    function setupPerformanceOptimizations() {
        // Lazy load images
        const lazyLoadImages = () => {
            const images = document.querySelectorAll('img[data-src]');
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src;
                        img.removeAttribute('data-src');
                        observer.unobserve(img);
                    }
                });
            });
            
            images.forEach(img => imageObserver.observe(img));
        };
        
        // Debounce scroll events
        const debounce = (func, wait) => {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        };
        
        // Optimize scroll performance
        const optimizeScroll = () => {
            const chatContainer = document.querySelector('.chat-container');
            if (!chatContainer) return;
            
            let ticking = false;
            chatContainer.addEventListener('scroll', () => {
                if (!ticking) {
                    window.requestAnimationFrame(() => {
                        // Perform scroll-related operations here
                        ticking = false;
                    });
                    ticking = true;
                }
            });
        };
        
        // Initialize optimizations
        lazyLoadImages();
        optimizeScroll();
    }
    
    // Setup on page load
    document.addEventListener('DOMContentLoaded', setupPerformanceOptimizations);
    
    // Also try setting up after Streamlit is loaded
    window.addEventListener('load', function() {
        setTimeout(setupPerformanceOptimizations, 500);
    });
    </script>
    """, unsafe_allow_html=True)

def handle_image_callbacks():
    """
    Handle various image-related callbacks from JavaScript.
    """
    # Set up an empty callback receiver
    if "image_data" not in st.session_state:
        st.session_state.image_data = None
    
    # Create a container that can respond to callbacks for images
    callback_container = st.container()
    
    with callback_container:
        # Create a dummy component that can receive callbacks
        if "clipboard_image" not in st.session_state:
            st.session_state.clipboard_image = None
        
        # Process any image data we've received via callback
        if st.session_state.get("image_data"):
            # Check for clipboard image data
            if st.session_state.image_data.get("type") == "clipboard_image":
                # Process in the image handler
                image_handler.handle_clipboard_image_callback()
            
            # Check for image removal
            elif st.session_state.image_data.get("type") == "remove_image":
                # Clear image uploader
                st.session_state.image_uploader = None
                st.session_state.image_data = None

def main():
    """
    Main application entry point.
    """
    # Page configuration
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout=DEFAULT_LAYOUT,
        initial_sidebar_state="collapsed" if device.is_mobile_device() else INITIAL_SIDEBAR_STATE
    )
    
    # Add responsive meta tags
    add_responsive_meta_tags()
    
    # Load CSS
    load_css()
    
    # Initialize session state
    state.init_session_state()
    
    # Detect device type
    device.detect_device_type()
    
    # Get device-specific classes
    classes = device.optimize_for_device()
    
    # Handle image callbacks from JavaScript
    handle_image_callbacks()
    
    # Add JavaScript handlers
    image_handler.add_clipboard_handler()
    image_handler.add_image_removal_handler()
    image_handler.optimize_image_uploader()
    
    # Add keyboard handling for mobile
    if device.is_mobile_device():
        add_keyboard_handling()
        add_performance_optimizations()
    
    # Render sidebar
    sidebar.render_sidebar()
    
    # Check for clipboard image paste events
    image_utils.handle_clipboard_image()
    
    # Main content
    if st.session_state.show_history:
        # Show history view
        history.render_history_view()
    else:
        # Show chat interface
        render_chat_interface()

def render_chat_interface():
    """
    Render the main chat interface.
    """
    # Apply device-specific container classes
    classes = device.optimize_for_device()
    
    # Create main container structure with responsive classes
    st.markdown(f'<div class="main-container {classes["container_class"]}">', unsafe_allow_html=True)
    
    # Chat history container
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    
    # Display chat interface title with responsive sizing
    if device.is_mobile_device() and device.is_small_screen():
        st.markdown(f"""
        <h2 style="text-align: center; margin-bottom: 1rem;">
            欢迎使用 J.A.R.V.I.S.
            <div style="font-size: 0.9rem; color: #666; margin-top: 0.3rem;">
                您的智能AI助手
            </div>
        </h2>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <h1 style="text-align: center; margin-bottom: 2rem;">
            欢迎使用 J.A.R.V.I.S.
            <div style="font-size: 1rem; color: #666; margin-top: 0.5rem;">
                您的智能AI助手
            </div>
        </h1>
        """, unsafe_allow_html=True)
    
    # Display chat history
    chat.display_chat_history()
    
    # Display status and errors
    chat.display_status()
    
    # Close chat container
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Add auto-scroll JavaScript
    add_auto_scroll_js()
    
    # Create input container at bottom
    input_container_class = "input-container"
    if device.is_mobile_device():
        input_container_class += " mobile"
    
    st.markdown(f'<div class="{input_container_class}">', unsafe_allow_html=True)
    
    # User input section
    if st.session_state.username:
        # Get image to use (from any source)
        image_to_use = image_handler.get_image_to_use()
        
        # Display paste success notification
        if st.session_state.get("paste_success", False):
            st.success("✅ 图片已成功粘贴!")
            st.session_state.paste_success = False
        
        # Create input field with responsive design
        placeholder = "正在处理..." if st.session_state.is_processing else "输入您的消息..."
        if device.is_mobile_device() and device.is_small_screen():
            placeholder = "输入消息..." if not st.session_state.is_processing else "处理中..."
        
        user_input = st.chat_input(placeholder, disabled=st.session_state.is_processing)
        
        # Display image preview if available
        if image_to_use:
            chat.display_image_preview(image_to_use)
        
        # Process user input
        if user_input and image_to_use:
            chat.handle_user_input(user_input, image_to_use)
        elif user_input:
            chat.handle_user_input(user_input)
    else:
        # More compact message for mobile
        if device.is_mobile_device() and device.is_small_screen():
            st.info("👈 请输入您的名字以开始")
        else:
            st.info("👈 请在侧边栏输入您的名字以开始对话")
    
    # Close input container
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Close main container
    st.markdown('</div>', unsafe_allow_html=True)

def add_auto_scroll_js():
    """
    Add JavaScript to automatically scroll to the bottom of the chat.
    Optimized for mobile devices, including special handling for iOS Safari keyboard issues.
    """
    st.markdown("""
    <script>
    // Scroll to the latest message when the page loads
    window.addEventListener('load', function() {
        // Fix Streamlit container styles
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
        
        // Fix vertical block wrapper positions
        const verticalBlocks = document.querySelectorAll('.stVerticalBlockBorderWrapper');
        verticalBlocks.forEach(function(block) {
            block.style.position = 'relative';
            block.style.order = '1';
            block.style.zIndex = '1';
        });
        
        // Ensure chat container is above input container
        const chatContainer = document.querySelector('.chat-container');
        if (chatContainer) {
            chatContainer.style.order = '0';
        }
        
        // Mobile-specific adjustments
        const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) || 
                     (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
        
        // 修复聊天输入框发送按钮位置
        function fixChatInputSendButton() {
            const chatInputContainer = document.querySelector('div[data-testid="stChatInput"]');
            if (!chatInputContainer) return;
            
            // 确保按钮可见
            const submitButton = chatInputContainer.querySelector('button');
            if (submitButton) {
                submitButton.style.visibility = 'visible';
                submitButton.style.opacity = '1';
                submitButton.style.display = 'flex';
                submitButton.style.position = 'absolute';
                submitButton.style.right = '5px';
                submitButton.style.top = '50%';
                submitButton.style.transform = 'translateY(-50%)';
                submitButton.style.zIndex = '2000';
            }
            
            // 确保输入框留出按钮空间
            const inputElement = chatInputContainer.querySelector('input');
            if (inputElement) {
                inputElement.style.paddingRight = '40px';
            }
        }
        
        // 在DOM加载完成后执行
        document.addEventListener('DOMContentLoaded', function() {
            // 初始化修复
            setTimeout(fixChatInputSendButton, 500);
            
            // 在窗口大小改变时重新应用修复
            window.addEventListener('resize', fixChatInputSendButton);
            
            // 在方向改变时重新应用修复（移动设备）
            window.addEventListener('orientationchange', function() {
                setTimeout(fixChatInputSendButton, 300);
            });
        });
        
        // Handle visual viewport API for modern browsers (especially needed for iOS)
        if (window.visualViewport) {
            function handleVisualViewportChange() {
                const inputContainer = document.querySelector('.input-container');
                if (!inputContainer) return;
                
                // Calculate if keyboard is likely shown (viewport height significantly reduced)
                const viewportHeight = window.visualViewport.height;
                const windowHeight = window.innerHeight;
                const keyboardLikelyShown = windowHeight - viewportHeight > 150;
                
                if (keyboardLikelyShown) {
                    // Keyboard is shown - adjust input container position
                    inputContainer.style.position = 'absolute';
                    inputContainer.style.bottom = '0';
                    
                    // On iOS, position relative to visualViewport
                    if (isIOS) {
                        const offsetFromBottom = windowHeight - viewportHeight - window.visualViewport.offsetTop;
                        inputContainer.style.bottom = offsetFromBottom + 'px';
                    }
                    
                    // Make sure the input is visible
                    setTimeout(function() {
                        // Find active input element
                        const activeElement = document.activeElement;
                        if (activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA')) {
                            activeElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        }
                    }, 300);
                } else {
                    // Keyboard is hidden - reset input container 
                    inputContainer.style.position = 'fixed';
                    inputContainer.style.bottom = isIOS ? 'env(safe-area-inset-bottom, 0)' : '0';
                    
                    // Scroll to bottom of chat once keyboard is closed
                    const messages = document.querySelectorAll('.stChatMessage');
                    if (messages && messages.length > 0) {
                        setTimeout(function() {
                            const lastMessage = messages[messages.length - 1];
                            lastMessage.scrollIntoView({ behavior: 'smooth', block: 'end' });
                        }, 100);
                    }
                }
            }
            
            // Initial setup
            handleVisualViewportChange();
            
            // Listen for viewport changes
            window.visualViewport.addEventListener('resize', handleVisualViewportChange);
            window.visualViewport.addEventListener('scroll', handleVisualViewportChange);
        } else {
            // Fallback for browsers without visualViewport API
            // Ensure input container is at the bottom
            const inputContainer = document.querySelector('.input-container');
            if (inputContainer) {
                inputContainer.style.order = '2';
                inputContainer.style.position = 'fixed';
                inputContainer.style.bottom = '0';
                inputContainer.style.left = '0';
                inputContainer.style.right = '0';
                inputContainer.style.zIndex = '1000';
                
                // Add extra padding for mobile devices to avoid keyboard issues
                if (isMobile) {
                    inputContainer.style.paddingBottom = isIOS ? 'calc(10px + env(safe-area-inset-bottom, 10px))' : '10px';
                    document.body.style.paddingBottom = '70px';
                }
            }
        }
        
        // Scroll to the latest message
        const messages = document.querySelectorAll('.stChatMessage');
        if (messages && messages.length > 0) {
            const lastMessage = messages[messages.length - 1];
            lastMessage.scrollIntoView({ behavior: 'auto', block: 'end' });
        }
    });
    
    // Monitor DOM changes to scroll to new messages
    const observer = new MutationObserver(function() {
        // Check for new chat messages
        const messages = document.querySelectorAll('.stChatMessage');
        if (messages && messages.length > 0) {
            const lastMessage = messages[messages.length - 1];
            lastMessage.scrollIntoView({ behavior: 'smooth', block: 'end' });
        }
    });
    
    // Start observing DOM changes
    setTimeout(function() {
        const chatContainer = document.querySelector('.chat-container');
        if (chatContainer) {
            observer.observe(chatContainer, { 
                childList: true, 
                subtree: true 
            });
        }
    }, 1000);
    
    // Fix for iOS Safari issues with viewport height
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    if (isIOS) {
        // Fix for iOS Safari 100vh issue
        function fixIOSViewport() {
            const vh = window.innerHeight * 0.01;
            document.documentElement.style.setProperty('--vh', `${vh}px`);
            
            // Adjust the main container height
            const mainContainer = document.querySelector('.main-container');
            if (mainContainer) {
                mainContainer.style.minHeight = `calc(100 * var(--vh) - 80px)`;
            }
            
            // 特别针对iOS键盘弹出时处理聊天输入框和发送按钮
            const chatInput = document.querySelector('div[data-testid="stChatInput"]');
            if (chatInput) {
                // 确保按钮在iOS上的可见性和可点击性
                const submitButton = chatInput.querySelector('button');
                if (submitButton) {
                    submitButton.style.visibility = 'visible';
                    submitButton.style.opacity = '1';
                    submitButton.style.display = 'block';
                    submitButton.style.position = 'absolute';
                    submitButton.style.right = '10px';
                    submitButton.style.zIndex = '3000'; // 极高的z-index确保在iOS上可见
                    submitButton.style.width = '40px';
                    submitButton.style.height = '40px';
                }
                
                // 确保输入框留出足够空间给按钮
                const textarea = chatInput.querySelector('textarea');
                if (textarea) {
                    textarea.style.paddingRight = '80px !important';
                }
            }
            
            // iOS键盘遮挡问题特殊处理
            fixChatInputSendButton();
        }
        
        // Set initial values
        fixIOSViewport();
        
        // Update on resize and orientation change
        window.addEventListener('resize', fixIOSViewport);
        window.addEventListener('orientationchange', fixIOSViewport);
        
        // 特别处理iOS键盘弹出时的按钮位置
        document.addEventListener('focusin', function(e) {
            if ((e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) {
                // 延迟执行以确保键盘完全弹出
                setTimeout(function() {
                    // 滚动输入字段到视图
                    e.target.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    
                    // 调整容器位置
                    const inputContainer = document.querySelector('.input-container');
                    if (inputContainer && isIOS) {
                        inputContainer.style.position = 'absolute';
                    }
                    
                    // 执行发送按钮修复
                    fixChatInputSendButton();
                    
                    // 确保发送按钮可见
                    const chatInputContainer = document.querySelector('div[data-testid="stChatInput"]');
                    if (chatInputContainer) {
                        const submitButton = chatInputContainer.querySelector('button');
                        if (submitButton) {
                            submitButton.style.visibility = 'visible';
                            submitButton.style.display = 'block';
                            submitButton.style.opacity = '1';
                            submitButton.style.zIndex = '3000';
                        }
                    }
                }, 300);
            }
        });
        
        document.addEventListener('focusout', function(e) {
            if ((e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') && isIOS) {
                // 键盘隐藏后重置
                setTimeout(function() {
                    const inputContainer = document.querySelector('.input-container');
                    if (inputContainer) {
                        inputContainer.style.position = 'fixed';
                    }
                    
                    // 滚动到最新消息
                    const messages = document.querySelectorAll('.stChatMessage');
                    if (messages && messages.length > 0) {
                        const lastMessage = messages[messages.length - 1];
                        lastMessage.scrollIntoView({ behavior: 'smooth', block: 'end' });
                    }
                    
                    // 再次执行按钮修复确保所有元素正确显示
                    fixChatInputSendButton();
                }, 300);
            }
        });
    }
    </script>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main() 