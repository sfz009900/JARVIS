import multiprocessing
from flask import Flask, request, jsonify
from wechat_gui import main as gui_main
import threading

app = Flask(__name__)

# 全局消息队列
message_queue = None
gui_process = None

def send_message(queue, target, content, interval=1):
    """
    发送消息到GUI进程
    
    Args:
        queue: 消息队列
        target: 目标用户/群
        content: 消息内容
        interval: 发送间隔(秒)
    """
    message = {
        'target': target,
        'content': content,
        'interval': interval
    }
    queue.put(message)

def start_gui_process():
    """启动GUI进程的函数"""
    global message_queue, gui_process
    
    # 创建消息队列
    message_queue = multiprocessing.Queue()
    
    # 启动GUI进程
    gui_process = multiprocessing.Process(target=gui_main, args=(message_queue,))
    gui_process.start()

@app.route('/send_message', methods=['POST'])
def api_send_message():
    """
    发送消息的API接口
    
    请求体格式:
    {
        "target": "接收者名称",
        "content": "消息内容",
        "interval": 1  // 可选，默认为1秒
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No JSON data provided'
            }), 400
        
        target = data.get('target')
        content = data.get('content')
        interval = data.get('interval', 1)
        
        if not target or not content:
            return jsonify({
                'success': False,
                'message': 'Missing required fields: target and content'
            }), 400
            
        # 发送消息到队列
        send_message(message_queue, target, content, interval)
        
        return jsonify({
            'success': True,
            'message': 'Message queued for sending'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error processing request: {str(e)}'
        }), 500

@app.route('/send_file', methods=['POST'])
def api_send_file():
    """
    发送文件的API接口
    
    请求体格式:
    {
        "target": "接收者名称",
        "file_path": "文件路径",
        "interval": 1  // 可选，默认为1秒
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No JSON data provided'
            }), 400
        
        target = data.get('target')
        file_path = data.get('file_path')
        interval = data.get('interval', 1)
        
        if not target or not file_path:
            return jsonify({
                'success': False,
                'message': 'Missing required fields: target and file_path'
            }), 400
            
        # 发送文件消息到队列
        content = f"file:{file_path}"
        send_message(message_queue, target, content, interval)
        
        return jsonify({
            'success': True,
            'message': 'File message queued for sending'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error processing request: {str(e)}'
        }), 500

@app.route('/send_at', methods=['POST'])
def api_send_at():
    """
    发送@消息的API接口
    
    请求体格式:
    {
        "target": "接收者名称",
        "content": "@消息内容",
        "interval": 1  // 可选，默认为1秒
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No JSON data provided'
            }), 400
        
        target = data.get('target')
        content = data.get('content')
        interval = data.get('interval', 1)
        
        if not target or not content:
            return jsonify({
                'success': False,
                'message': 'Missing required fields: target and content'
            }), 400
            
        # 发送@消息到队列
        content = f"at:{content}"
        send_message(message_queue, target, content, interval)
        
        return jsonify({
            'success': True,
            'message': 'At message queued for sending'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error processing request: {str(e)}'
        }), 500

def main():
    # 启动GUI进程
    start_gui_process()
    
    # 启动Flask应用
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    main() 