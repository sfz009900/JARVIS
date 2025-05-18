from flask import Flask, request, jsonify
from wechat_gui import WechatGUI
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
import pythoncom
import sys
import time

app = Flask(__name__)

# 初始化QApplication
qt_app = QApplication(sys.argv)
wechat_gui = WechatGUI()

# 直接设置微信路径并启动
WECHAT_PATH = "F:/software/wechat/WeChat.exe"
wechat_gui.wechat.path = WECHAT_PATH
wechat_gui.path_label.setText(WECHAT_PATH)
wechat_gui.wechat.open_wechat()

@app.route('/send_message', methods=['POST'])
def send_message():
    try:
        # 初始化COM环境
        pythoncom.CoInitialize()
        
        data = request.get_json()
        
        # 验证必需的参数
        if not all(key in data for key in ['target', 'content']):
            return jsonify({
                'success': False,
                'message': 'Missing required parameters. Need "target" and "content"'
            }), 400
            
        target = data['target']
        content = data['content']
        interval = data.get('interval', 1)  # 默认间隔1秒
        
        # 初始化发送状态
        wechat_gui.hotkey_pressed = False
        
        try:
            # 搜索并发送给目标用户
            if content.startswith('file:'):
                # 处理文件发送
                file_path = content[5:]  # 移除 'file:' 前缀
                wechat_gui.wechat.send_file(target, file_path, True)
            elif content.startswith('at:'):
                # 处理@消息
                at_content = content[3:]  # 移除 'at:' 前缀
                wechat_gui.wechat.at(target, at_content, True)
            else:
                # 处理普通文本消息
                wechat_gui.wechat.send_msg(target, content, True)
            
            # 等待指定的间隔时间
            time.sleep(int(interval))
            
            return jsonify({
                'success': True,
                'message': f'Message sent successfully to {target}'
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Failed to send message: {str(e)}'
            }), 500
        finally:
            # 释放COM环境
            pythoncom.CoUninitialize()
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error processing request: {str(e)}'
        }), 400

if __name__ == '__main__':
    # 启动Flask应用
    app.run(host='0.0.0.0', port=5000) 