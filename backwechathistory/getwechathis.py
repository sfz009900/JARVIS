import requests
import json
import configparser
import os

def get_msg_count(wxids):
    url = "http://127.0.0.1:5000/api/rs/msg_count"
    timeout = 600
    
    # Ensure wxids is a list
    if isinstance(wxids, str):
        wxids = [wxids]
    
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
        'Origin': 'http://127.0.0.1:5000',
        'Referer': 'http://127.0.0.1:5000/s/index.html'
    }
    
    try:
        response = requests.post(url, json={"wxids": wxids}, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"Error getting message count: {str(e)}")
        return None

def get_messages(wxid, start, limit):
    url = "http://127.0.0.1:5000/api/rs/msg_list"
    timeout = 600
    
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
        'Origin': 'http://127.0.0.1:5000',
        'Referer': 'http://127.0.0.1:5000/s/index.html'
    }
    
    try:
        response = requests.post(url, json={"start": start, "limit": limit, "wxid": wxid}, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"Error getting messages: {str(e)}")
        return None

def get_latest_database():
    url = "http://127.0.0.1:5000/api/ls/realtimemsg"
    timeout = 600  # 10 minutes in seconds
    
    try:
        response = requests.post(url, json={}, timeout=timeout)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        result = response.json()
        if result.get("code") == 0:
            print("OK")
            
            # Read config.ini
            config = configparser.ConfigParser()
            config.read('config.ini', encoding='utf-8')
            
            # Get all wxids from sections
            wxids = []
            for section in config.sections():
                if config.has_option(section, 'wxid'):
                    wxid = config.get(section, 'wxid')
                    # wxids.append(wxid)
            
                    # Get message counts for all wxids
                    msg_count_result = get_msg_count(wxid)
                    
                    if msg_count_result and msg_count_result.get("code") == 0:
                        body = msg_count_result.get("body", {})
                        
                        # Compare message counts with lastnum
                        for section in config.sections():
                            if config.has_option(section, 'wxid') and config.has_option(section, 'lastnum'):
                                wxid = config.get(section, 'wxid')
                                lastnum = config.getint(section, 'lastnum')
                                current_count = body.get(wxid, 0)
                                
                                if current_count > lastnum:
                                    print(f"OK1: 获取消息数 - Section: {section}, wxid: {wxid}, "
                                        f"Current count: {current_count}, Last num: {lastnum}")
                                    
                                    # 准备导出消息
                                    start = lastnum
                                    limit = current_count - lastnum
                                    messages = get_messages(wxid, start, limit)
                                    
                                    if messages and messages.get("code") == 0:
                                        msg_list = messages.get("body", {}).get("msg_list", [])
                                        
                                        # Replace talker names with section name
                                        for msg in msg_list:
                                            if msg.get("talker") == wxid:
                                                msg["talker"] = section
                                                msg["room_name"] = section
                                            if msg.get("talker") == "hack004":
                                                msg["room_name"] = section
                                        
                                        # Create data directory if it doesn't exist
                                        os.makedirs("data", exist_ok=True)
                                        
                                        # Get output file path from config
                                        if config.has_option(section, 'file'):
                                            output_file = os.path.join("data", config.get(section, 'file'))
                                            
                                            # Delete old file if it exists
                                            if os.path.exists(output_file):
                                                os.remove(output_file)
                                            
                                            # Save new messages
                                            with open(output_file, 'w', encoding='utf-8') as f:
                                                json.dump(msg_list, f, ensure_ascii=False, indent=4)
                                            
                                            # Update lastnum in config
                                            config.set(section, 'lastnum', str(current_count))
                                            with open('config.ini', 'w', encoding='utf-8') as f:
                                                config.write(f)
                                            
                                            print(f"Messages saved to {output_file}")
                                        else:
                                            print(f"No output file specified for section {section}")
                                    else:
                                        print("Failed to get messages")
            
            print(f"Database path: {result.get('body')}")
            return result.get('body')
        else:
            print(f"Error: {result.get('msg')}")
            return None
            
    except requests.Timeout:
        print("Request timed out after 10 minutes")
        return None
    except requests.RequestException as e:
        print(f"Request failed: {str(e)}")
        return None
    except json.JSONDecodeError:
        print("Failed to parse response as JSON")
        return None
    except configparser.Error as e:
        print(f"Failed to parse config.ini: {str(e)}")
        return None

if __name__ == "__main__":
    get_latest_database()
