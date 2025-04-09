import platform
import subprocess
import re
import json
from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from core.utils.ConfigManager import ConfigManager
import logging
from core.llmhandle.callopenrouter import _call_openrouter
from core.llmhandle.callopenrouter import _call_openrouter_other
logger = logging.getLogger(__name__)

class CommandExecutor:
    """处理系统命令执行的类"""
    
    def __init__(self, config_manager: 'ConfigManager'):
        self.config_manager = config_manager
        self.os_type = platform.system()  # 'Windows', 'Linux', 'Darwin' (macOS)
        
        # 获取安全设置
        self.security_settings = self.config_manager.get("security", {})
        self.command_execution_enabled = self.security_settings.get("command_execution_enabled", True)
        self.command_timeout = self.security_settings.get("command_timeout", 10)
        
        # 危险命令列表
        self.dangerous_commands = [
            "rm", "del", "format", "mkfs", "fdisk", "shutdown", "reboot", 
            "halt", ">", "2>", "sudo", "su", "passwd", "mkfs", "dd",
            "chmod", "chown", "kill", "pkill", ":(){ :|:& };:", "mv", "rd",
            "rmdir", "deltree", "format", "reg delete"
        ]
    
    async def analyze_user_request(self, llm, user_input: str) -> Dict[str, Any]:
        """分析用户请求，判断是否需要执行命令，并生成适当的命令"""
        if not self.command_execution_enabled:
            return {
                "needs_command": False,
                "command": "",
                "explanation": "命令执行功能已禁用"
            }
        
        # 调用LLM生成命令
        messages = [
            {"role": "user", "content": f"""你是一个Windows系统命令分析专家。你的任务是提供命令,我来交给其他AI模型分析命令结果：
        1. 评估用户请求是否需要执行Windows系统命令
        2. 如需执行，生成适用于Windows的CMD命令
        3. 提供命令的技术说明
        4. 比如原始提问是"分析下我的进程列表看有病毒没",你只需提供显示进程列表的命令"tasklist"就行,不要做过多操作
        重要:
        0: 只能使用CMD命令
        1: 命令一定要放到command字段
        2: 严格按照返回格式返回
        3: 如果不需要执行命令，请返回needs_command:false,command:"",explanation:""

        专业要求：
        - URL处理需保持原始结构，确保查询参数完整性
        - 示例：当用户请求"获取https://example.com/api?param=value的内容"，
        应返回needs_command:false，并说明CMD无直接网页抓取功能

        安全规范：
        - 避免使用需要管理员权限的命令
        - 不执行会改变系统配置或状态的命令
        - 仅限于信息查询和状态监控类命令

        返回格式(JSON)：
        {{
        "needs_command": true/false,  // 命令执行必要性
        "command": "具体命令",        // needs_command为true时的命令内容
        "explanation": "技术说明"     // 命令的技术说明和预期效果
        }}

        用户请求: {user_input}

        请仔细分析用户请求，特别注意：
        1. 如果用户请求包含URL，请准确提取完整URL，不要修改URL结构
        2. 对于网页抓取请求除非URL里包含whyta.cn和wttr.in关键字，否则不生成curl或wget命令，直接说明CMD无此功能
        3. 保留URL中的所有参数和特殊字符

        请判断是否需要执行命令，并生成适当的命令（如果需要）。"""}
        ]
        
        content = _call_openrouter_other(self, messages)
        
        # 尝试提取JSON部分
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        else:
            # 尝试找到可能的JSON对象
            json_match = re.search(r'({.*})', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
        
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # 如果无法解析JSON，尝试手动解析
            needs_command = "true" in content.lower() and "needs_command" in content
            command_match = re.search(r'"command":\s*"(.*?)"', content)
            explanation_match = re.search(r'"explanation":\s*"(.*?)"', content)
            
            result = {
                "needs_command": needs_command,
                "command": command_match.group(1) if command_match else "",
                "explanation": explanation_match.group(1) if explanation_match else "无法解析命令解释"
            }
        
        # 特殊处理curl命令，确保URL正确提取
        # if result.get("needs_command", False) and result.get("command", "").startswith("curl "):
        #     # 从用户输入中尝试提取URL
        #     url_match = re.search(r'https?://[^\s"\']+', user_input)
        #     if url_match:
        #         extracted_url = url_match.group(0)
        #         # 如果URL包含特殊字符，确保它们被正确处理
        #         if any(char in extracted_url for char in "?&="):
        #             # 构建新的curl命令，保留原始URL结构
        #             result["command"] = f"curl {extracted_url}"
        #             result["explanation"] = f"使用curl获取网页内容: {extracted_url}"
        
        # 检查命令安全性
        if result.get("needs_command", False) and result.get("command"):
            command = result["command"]
            
            # 检查是否包含危险命令，但允许curl命令
            is_curl_command = command.strip().startswith("curl ")
            
            if not is_curl_command and any(dangerous_cmd in command.lower() for dangerous_cmd in self.dangerous_commands):
                return {
                    "needs_command": False,
                    "command": "",
                    "explanation": f"生成的命令 '{command}' 可能不安全，已被拒绝执行"
                }
            
            return result
        else:
            return {
                "needs_command": False,
                "command": "",
                "explanation": result.get("explanation", "不需要执行命令")
            }
            
    def execute_command(self, command: str) -> Dict[str, Any]:
        """执行系统命令并返回结果"""
        result = {
            "success": False,
            "output": "",
            "error": "",
            "command": command
        }
        
        # 如果命令执行被禁用，返回错误
        if not self.command_execution_enabled:
            result["error"] = "命令执行功能已被禁用"
            return result
            
        try:
            # 使用subprocess执行命令，使用bytes模式而不是text模式
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False  # 使用bytes模式
            )
            stdout_bytes, stderr_bytes = process.communicate(timeout=self.command_timeout)
            
            # 尝试多种编码解码输出
            encodings_to_try = ['utf-8', 'gbk', 'latin1', 'cp1252']
            stdout = ""
            stderr = ""
            
            # 尝试解码stdout
            for encoding in encodings_to_try:
                try:
                    if stdout_bytes:
                        stdout = stdout_bytes.decode(encoding)
                        break
                except UnicodeDecodeError:
                    continue
            
            # 如果所有编码都失败，使用latin1（它可以解码任何字节序列）
            if not stdout and stdout_bytes:
                stdout = stdout_bytes.decode('latin1', errors='replace')
            
            # 尝试解码stderr
            for encoding in encodings_to_try:
                try:
                    if stderr_bytes:
                        stderr = stderr_bytes.decode(encoding)
                        break
                except UnicodeDecodeError:
                    continue
            
            # 如果所有编码都失败，使用latin1
            if not stderr and stderr_bytes:
                stderr = stderr_bytes.decode('latin1', errors='replace')
            
            if process.returncode == 0:
                result["success"] = True
                result["output"] = stdout
            else:
                result["error"] = stderr
                
        except subprocess.TimeoutExpired:
            result["error"] = f"命令执行超时 (超过 {self.command_timeout} 秒)"
        except Exception as e:
            result["error"] = str(e)
            
        return result
        
    async def process_command_result(self, llm, command: str, output: str, user_input: str) -> str:
        """使用LLM处理命令执行结果"""
        system_prompt = f"""你是一个系统命令结果分析助手。你的任务是：
1. 分析以下命令的执行结果
2. 提取关键信息并以用户友好的方式呈现
3. 如果结果中有技术术语，请解释它们
4. 如果结果很长，请总结最重要的部分
5. 如果命令执行失败，请解释可能的原因并提供解决建议

命令: {command}
用户原始请求: {user_input}

请直接回答，不要提及你在分析命令结果。回答应该像是你直接在回应用户的问题，语气友好、专业且有帮助。
如果合适，可以使用表格或列表格式来组织信息，使其更易于阅读。
"""
        
        user_prompt = f"命令执行结果:\n\n{output}\n\n请分析上述结果并以用户友好的方式呈现关键信息。确保你的回答直接解决了用户的原始请求：'{user_input}'。"
        
        try:
            # 调用OpenRouter处理结果
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            return _call_openrouter_other(self, messages)
            
        except Exception as e:
            logger.error(f"处理命令结果时出错: {str(e)}")
            return f"处理命令结果时出错: {str(e)}\n\n原始结果:\n{output}"