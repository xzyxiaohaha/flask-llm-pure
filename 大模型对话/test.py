import requests
import json
import os

# 配置你的 API Key
# 优先从环境变量 DEEPSEEK_API_KEY 读取，如果不存在则使用字符串（不安全，仅用于测试）
# API_KEY = os.getenv("DEEPSEEK_API_KEY", "你的API_Key在这里")
API_KEY = "sk-7a8cfd72d36844f6b1aafb5dbf04944b"
url = "https://api.deepseek.com/chat/completions"


def simple_chat():
    """基础对话模式（一次性返回全部结果）"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    data = {
        "model": "deepseek-chat",  # 使用 deepseek-chat 模型
        "messages": [
            {"role": "system", "content": "你是一个乐于助人的助手。"},
            {"role": "user", "content": "你是什么大模型"}
        ],
        "stream": False  # 关闭流式传输
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # 如果请求失败（状态码非200），将抛出异常
        result = response.json()
        answer = result['choices'][0]['message']['content']
        print("助手回复：")
        print(answer)

    except requests.exceptions.RequestException as e:
        print(f"请求出错: {e}")
    except KeyError:
        print("解析响应数据时出错。")
        print(f"原始响应: {response.text}")


def stream_chat():
    """流式对话模式（逐字实时显示结果）"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": "请你用一段话介绍深空探测的意义。"}
        ],
        "stream": True  # 开启流式传输
    }

    try:
        response = requests.post(url, headers=headers, json=data, stream=True)
        response.raise_for_status()

        print("助手回复（流式）: ")
        for line in response.iter_lines(decode_unicode=True):
            if line and line.startswith('data: '):
                if line == 'data: [DONE]':  # 流结束标志
                    break
                try:
                    chunk = json.loads(line[6:])  # 去掉 'data: ' 前缀后解析JSON
                    content = chunk['choices'][0]['delta'].get('content', '')
                    print(content, end='', flush=True)
                except json.JSONDecodeError:
                    continue
        print()  # 最后换行

    except requests.exceptions.RequestException as e:
        print(f"请求出错: {e}")


if __name__ == "__main__":
    # 请先配置好 API_KEY，然后取消下面一行的注释来选择模式

    simple_chat()  # 运行基础对话模式
    # stream_chat() # 运行流式对话模式