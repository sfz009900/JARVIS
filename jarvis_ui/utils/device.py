"""
Device detection utilities for the J.A.R.V.I.S. UI.
"""

import streamlit as st

def detect_device_type():
    """
    Detect device type (mobile/desktop) and browser information via JavaScript.
    Stores the results in the session state.
    """
    # Add JavaScript code to detect device type and store in session_state
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
        
        // 获取屏幕尺寸
        const screenWidth = window.innerWidth;
        const screenHeight = window.innerHeight;
        
        // 确定屏幕尺寸类别
        let screenSizeCategory = 'large';
        if (screenWidth < 576) {
            screenSizeCategory = 'xs'; // Extra small
        } else if (screenWidth < 768) {
            screenSizeCategory = 'sm'; // Small
        } else if (screenWidth < 992) {
            screenSizeCategory = 'md'; // Medium
        } else if (screenWidth < 1200) {
            screenSizeCategory = 'lg'; // Large
        } else {
            screenSizeCategory = 'xl'; // Extra large
        }
        
        // 将设备信息发送到 Streamlit
        window.parent.postMessage({
            type: 'streamlit:setComponentValue',
            value: {
                is_mobile: isMobile,
                device_type: deviceType,
                browser_type: browserType,
                screen_width: screenWidth,
                screen_height: screenHeight,
                screen_size_category: screenSizeCategory
            }
        }, '*');
    }
    
    // 页面加载时执行检测
    document.addEventListener('DOMContentLoaded', detectMobileDevice);
    
    // 窗口大小改变时重新检测
    window.addEventListener('resize', detectMobileDevice);
    </script>
    """, unsafe_allow_html=True)

def is_mobile_device():
    """
    Check if the current device is a mobile device.
    
    Returns:
        bool: True if the current device is a mobile device, False otherwise
    """
    return st.session_state.get("is_mobile", False)

def get_device_info():
    """
    Get detailed device information.
    
    Returns:
        dict: A dictionary containing device information
    """
    return {
        "is_mobile": st.session_state.get("is_mobile", False),
        "device_type": st.session_state.get("device_type", "desktop"),
        "browser_type": st.session_state.get("browser_type", "other"),
        "screen_width": st.session_state.get("screen_width", 1200),
        "screen_height": st.session_state.get("screen_height", 800),
        "screen_size_category": st.session_state.get("screen_size_category", "lg")
    }

def is_small_screen():
    """
    Check if the current device has a small screen (xs or sm category).
    
    Returns:
        bool: True if screen is small, False otherwise
    """
    category = st.session_state.get("screen_size_category", "lg")
    return category in ["xs", "sm"]

def is_extra_small_screen():
    """
    Check if the current device has an extra small screen (xs category).
    
    Returns:
        bool: True if screen is extra small, False otherwise
    """
    return st.session_state.get("screen_size_category", "lg") == "xs"

def optimize_for_device():
    """
    Apply device-specific optimizations to the UI.
    Returns classes to be applied to containers for responsive design.
    
    Returns:
        dict: A dictionary containing device-specific CSS classes
    """
    classes = {
        "container_class": "",
        "sidebar_class": "",
        "column_class": ""
    }
    
    if is_mobile_device():
        classes["container_class"] = "mobile-container"
        classes["sidebar_class"] = "mobile-sidebar"
        classes["column_class"] = "mobile-column"
        
        if is_extra_small_screen():
            classes["container_class"] += " xs-screen"
            classes["sidebar_class"] += " xs-screen"
            classes["column_class"] += " xs-screen"
    
    return classes

def responsive_columns(ratios=None, num=2, mobile_stacking=True):
    """
    Create responsive columns that work well on both desktop and mobile.
    
    Args:
        ratios (list, optional): List of width ratios for columns. Defaults to None (equal widths).
        num (int, optional): Number of columns if ratios not provided. Defaults to 2.
        mobile_stacking (bool, optional): Whether to stack columns on mobile. Defaults to True.
    
    Returns:
        list: List of column objects
    """
    if is_mobile_device() and mobile_stacking and is_small_screen():
        # On mobile with small screens, create full-width columns that stack vertically
        return [st.container() for _ in range(num if ratios is None else len(ratios))]
    else:
        # On desktop or large mobile screens, use standard columns
        if ratios is None:
            return st.columns(num)
        else:
            return st.columns(ratios) 