"""
Sidebar component for the J.A.R.V.I.S. UI.
"""

import streamlit as st
import time

from jarvis_ui.utils import state, device
from jarvis_ui.api import client
from jarvis_ui.config import VERSION, COPYRIGHT

def render_sidebar():
    """
    Render the sidebar UI components.
    """
    # Add sidebar toggle button for mobile devices
    if device.is_mobile_device() and device.is_small_screen():
        add_sidebar_toggle()
    
    # Get device-specific classes
    classes = device.optimize_for_device()
    
    with st.sidebar:
        # Apply mobile-specific classes if needed
        if classes["sidebar_class"]:
            st.markdown(f'<div class="{classes["sidebar_class"]}">', unsafe_allow_html=True)
        
        st.title("🤖 J.A.R.V.I.S.")
        
        # Username input - simplified on mobile
        if device.is_mobile_device() and device.is_small_screen():
            username = st.text_input("👤 您的名字:", value=st.session_state.username,
                                   placeholder="输入名字...", 
                                   help="您的名字将用于标识对话")
        else:
            username = st.text_input("👤 您的名字:", value=st.session_state.username,
                                   placeholder="请输入您的名字...")
        
        if username and username != st.session_state.username:
            st.session_state.username = username
            state.reset_chat()
            st.rerun()
        
        st.divider()
        
        # Image upload section - different for mobile and desktop
        render_image_upload_section()
        
        st.divider()
        
        # Session management - adjusted for mobile
        render_session_management()
        
        st.divider()
        
        # Settings
        render_settings()
        
        # Only show about section on non-small screens to save space
        if not (device.is_mobile_device() and device.is_small_screen()):
            st.divider()
            render_about_section()
        
        # Version info - simplified on mobile
        if device.is_mobile_device() and device.is_small_screen():
            st.caption(f"V{VERSION}")
        else:
            st.caption(f"Version {VERSION} • {COPYRIGHT}")
        
        # Add mobile-specific footer
        if device.is_mobile_device() and device.is_small_screen():
            st.markdown("""
            <div class="mobile-sidebar-footer">
                <p style="font-size: 0.8rem; color: #666; text-align: center;">
                    v{VERSION}<br>
                    {COPYRIGHT}
                </p>
            </div>
            """.format(VERSION=VERSION, COPYRIGHT=COPYRIGHT), unsafe_allow_html=True)
        
        # Close mobile-specific div if needed
        if classes["sidebar_class"]:
            st.markdown('</div>', unsafe_allow_html=True)

def add_sidebar_toggle():
    """
    Add a toggle button to show/hide the sidebar on mobile.
    """
    # Add JavaScript for sidebar toggle functionality with improved touch support
    st.markdown("""
    <script>
    // Function to toggle sidebar on mobile
    function setupSidebarToggle() {
        // Create toggle button if it doesn't exist
        if (!document.querySelector('.mobile-sidebar-toggle')) {
            const toggleBtn = document.createElement('button');
            toggleBtn.className = 'mobile-sidebar-toggle';
            toggleBtn.innerHTML = '☰';
            toggleBtn.setAttribute('aria-label', '切换侧边栏');
            document.body.appendChild(toggleBtn);
            
            // Create backdrop for sidebar
            const backdrop = document.createElement('div');
            backdrop.className = 'sidebar-backdrop';
            document.body.appendChild(backdrop);
            
            // Initially collapse sidebar on mobile
            document.body.classList.add('mobile-sidebar-collapsed');
            
            // Touch event handlers
            let touchStartX = 0;
            let touchEndX = 0;
            
            // Handle touch start
            document.addEventListener('touchstart', function(e) {
                touchStartX = e.changedTouches[0].screenX;
            }, false);
            
            // Handle touch end
            document.addEventListener('touchend', function(e) {
                touchEndX = e.changedTouches[0].screenX;
                handleSwipe();
            }, false);
            
            // Handle swipe
            function handleSwipe() {
                const swipeThreshold = 50;
                const swipeDistance = touchEndX - touchStartX;
                
                if (Math.abs(swipeDistance) > swipeThreshold) {
                    if (swipeDistance > 0 && document.body.classList.contains('mobile-sidebar-collapsed')) {
                        // Swipe right to open
                        document.body.classList.remove('mobile-sidebar-collapsed');
                        document.body.classList.add('mobile-sidebar-expanded');
                    } else if (swipeDistance < 0 && document.body.classList.contains('mobile-sidebar-expanded')) {
                        // Swipe left to close
                        document.body.classList.remove('mobile-sidebar-expanded');
                        document.body.classList.add('mobile-sidebar-collapsed');
                    }
                }
            }
            
            // Toggle sidebar on button click
            toggleBtn.addEventListener('click', function() {
                if (document.body.classList.contains('mobile-sidebar-collapsed')) {
                    document.body.classList.remove('mobile-sidebar-collapsed');
                    document.body.classList.add('mobile-sidebar-expanded');
                } else {
                    document.body.classList.remove('mobile-sidebar-expanded');
                    document.body.classList.add('mobile-sidebar-collapsed');
                }
            });
            
            // Close sidebar when backdrop is clicked
            backdrop.addEventListener('click', function() {
                document.body.classList.remove('mobile-sidebar-expanded');
                document.body.classList.add('mobile-sidebar-collapsed');
            });
            
            // Handle orientation change
            window.addEventListener('orientationchange', function() {
                document.body.classList.remove('mobile-sidebar-expanded');
                document.body.classList.add('mobile-sidebar-collapsed');
            });
        }
    }
    
    // Setup on page load
    document.addEventListener('DOMContentLoaded', setupSidebarToggle);
    
    // Also try setting up after Streamlit is loaded
    window.addEventListener('load', function() {
        setTimeout(setupSidebarToggle, 500);
    });
    </script>
    """, unsafe_allow_html=True)

def render_image_upload_section():
    """
    Render the image upload section in the sidebar.
    """
    # Use responsive columns utility if available on small screens
    use_compact_layout = device.is_mobile_device() and device.is_small_screen()
    
    if device.is_mobile_device():
        # More compact header for mobile
        if use_compact_layout:
            st.write("#### 📷 添加图片")
        else:
            st.subheader("📷 添加图片")
            
        st.caption("请选择上传方式:")
        
        # 1. Camera and gallery tabs for mobile devices
        camera_tab, gallery_tab = st.tabs(["拍照", "相册"])
        
        with camera_tab:
            st.caption("📸 使用相机直接拍照上传")
            camera_image = st.camera_input("拍照", key="camera_input", 
                                          help="点击拍照按钮进行拍照")
            
            if camera_image is not None:
                # Set camera image as upload image
                if "image_uploader" not in st.session_state or st.session_state.image_uploader != camera_image:
                    st.session_state.image_uploader = camera_image
                    st.success("✅ 添加成功!")
        
        with gallery_tab:
            st.caption("🖼️ 从相册中选择图片")
            # Original file_uploader
            uploaded_file = st.file_uploader(
                "选择图片",
                type=["jpg", "jpeg", "png"],
                key="image_uploader",
                accept_multiple_files=False,
                help="支持JPG、PNG格式"
            )
            
            # Simplified device tips for mobile
            if use_compact_layout:
                device_info = device.get_device_info()
                if device_info["device_type"] in ['iphone', 'ipad', 'android']:
                    st.info("📱 提示: 如果相册上传失败，请尝试拍照上传")
            else:
                # More detailed tips for larger screens
                device_info = device.get_device_info()
                if device_info["device_type"] in ['iphone', 'ipad'] and device_info["browser_type"] == 'safari':
                    st.info("📱 iOS Safari 提示: 如果从相册无法上传，请尝试使用拍照上传选项")
                elif device_info["browser_type"] == 'chrome':
                    st.info("📱 Chrome 提示: 如果从相册无法上传，请尝试使用拍照上传选项")
    else:
        # PC device file uploader
        uploaded_file = st.file_uploader(
            "📷 上传图片",
            type=["jpg", "jpeg", "png"],
            key="image_uploader",
            accept_multiple_files=False,
            help="支持 JPG、JPEG、PNG 格式的图片"
        )

def render_session_management():
    """
    Render the session management section in the sidebar.
    """
    # Use responsive layout based on device
    use_compact_layout = device.is_mobile_device() and device.is_small_screen()
    
    if use_compact_layout:
        st.write("#### ⚙️ 会话管理")
    else:
        st.subheader("⚙️ 会话管理")
    
    # Use responsive columns
    if hasattr(device, 'responsive_columns'):
        col1, col2 = device.responsive_columns(2, mobile_stacking=False)
    else:
        col1, col2 = st.columns(2)
    
    # New session button
    with col1:
        if st.button("🆕 新会话", use_container_width=True):
            state.reset_chat()
            st.rerun()
    
    # Clear session button
    with col2:
        if st.session_state.session_id and st.button("🗑️ 清除", use_container_width=True):
            with st.spinner("正在清除会话..."):
                result, error = client.clear_session(st.session_state.session_id)
                if error:
                    state.set_error(error)
                else:
                    state.reset_chat()
                    st.success("会话已清除!")
                    time.sleep(1)
                    st.rerun()
    
    # History sessions button - full width button is better for touch on mobile
    if st.button("📜 历史会话", use_container_width=True):
        state.toggle_history_view()
        st.rerun()
    
    # Display current session info
    if st.session_state.session_id:
        if use_compact_layout:
            st.info(f"🔑 ID: {st.session_state.session_id[:8]}...")
        else:
            st.info(f"🔑 会话ID: {st.session_state.session_id[:8]}...")

def render_settings():
    """
    Render the settings section in the sidebar.
    """
    use_compact_layout = device.is_mobile_device() and device.is_small_screen()
    
    if use_compact_layout:
        st.write("#### 🛠️ 设置")
    else:
        st.subheader("🛠️ 设置")
    
    # Theme toggle
    theme = st.selectbox("🎨 界面主题",
                       options=["light", "dark"],
                       format_func=lambda x: "明亮" if x == "light" else "暗黑",
                       index=0 if st.session_state.theme == "light" else 1)
    
    if theme != st.session_state.theme:
        state.set_theme(theme)
        st.rerun()
    
    # Timestamp toggle
    show_timestamps = st.toggle("🕒 显示时间戳",
                              value=st.session_state.show_timestamps)
    
    if show_timestamps != st.session_state.show_timestamps:
        state.toggle_timestamps()
        st.rerun()

def render_about_section():
    """
    Render the about section in the sidebar.
    """
    use_compact_layout = device.is_mobile_device() and device.is_small_screen()
    
    # On mobile, use a more compact design
    if use_compact_layout:
        with st.expander("ℹ️ 关于"):
            st.write("""
            **J.A.R.V.I.S. AI**
            
            - 🧠 智能对话
            - 💭 上下文记忆
            - 🌐 网络搜索
            
            使用 `@web` 命令可以搜索
            """)
    else:
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

def display_device_debug():
    """
    Display device debug information in sidebar (for development).
    """
    with st.sidebar.expander("📱 设备信息", expanded=False):
        device_info = device.get_device_info()
        st.write(f"设备类型: {device_info['device_type']}")
        st.write(f"是否移动设备: {device_info['is_mobile']}")
        st.write(f"浏览器类型: {device_info['browser_type']}")
        if 'screen_width' in device_info:
            st.write(f"屏幕宽度: {device_info['screen_width']}px")
        if 'screen_height' in device_info:
            st.write(f"屏幕高度: {device_info['screen_height']}px")
        if 'screen_size_category' in device_info:
            st.write(f"屏幕尺寸类别: {device_info['screen_size_category']}") 