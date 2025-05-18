import requests
import json

def send_message(target, content, interval=1):
    """发送普通消息"""
    url = "http://localhost:5000/send_message"
    data = {
        "target": target,
        "content": content,
        "interval": interval
    }
    response = requests.post(url, json=data)
    return response.json()

if __name__ == "__main__":
    # 测试发送普通消息
    result = send_message("测试一号", "你好！这是一条测试消息", 2)
    print("发送普通消息结果:", json.dumps(result, ensure_ascii=False, indent=2))
