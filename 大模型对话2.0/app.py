from flask import Flask, render_template, request, jsonify, session
import requests
import json
import openpyxl
from openpyxl import Workbook
import os
from datetime import datetime
import uuid
import pandas as pd

app = Flask(__name__)
app.secret_key = 'xxxxxxxxxxxxx'  # 请修改为随机密钥

# DeepSeek API配置
DEEPSEEK_API_KEY = "xxxxxxxxxxx"  # 请替换为你的API Key
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"


# 初始化Excel文件
def init_excel():
    if not os.path.exists('chat_history.xlsx'):
        wb = Workbook()
        ws = wb.active
        ws.title = "聊天记录"
        # 添加表头
        headers = ["会话ID", "时间戳", "角色", "消息内容", "Tokens使用量"]
        ws.append(headers)
        wb.save('chat_history.xlsx')


# 保存对话到Excel
def save_to_excel(session_id, role, message, tokens_used=None):
    try:
        wb = openpyxl.load_workbook('chat_history.xlsx')
        ws = wb.active

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [session_id, timestamp, role, message, tokens_used or ""]
        ws.append(row)

        wb.save('chat_history.xlsx')
        return True
    except Exception as e:
        print(f"保存到Excel时出错: {e}")
        return False


# 获取所有会话列表
def get_all_sessions():
    try:
        if not os.path.exists('chat_history.xlsx'):
            return []

        df = pd.read_excel('chat_history.xlsx')
        if df.empty:
            return []

        # 获取每个会话的最后一条记录时间
        sessions = df.groupby('会话ID').agg({
            '时间戳': 'max',
            '角色': 'count'
        }).reset_index()

        sessions = sessions.rename(columns={'角色': '消息数量', '时间戳': '最后活动'})
        sessions = sessions.sort_values('最后活动', ascending=False)

        return sessions.to_dict('records')
    except Exception as e:
        print(f"获取会话列表时出错: {e}")
        return []


# 获取指定会话的历史记录
def get_session_history(session_id):
    try:
        if not os.path.exists('chat_history.xlsx'):
            return []

        df = pd.read_excel('chat_history.xlsx')
        if df.empty:
            return []

        session_df = df[df['会话ID'] == session_id]
        session_df = session_df.sort_values('时间戳')

        history = []
        for _, row in session_df.iterrows():
            history.append({
                'role': 'user' if row['角色'] == '用户' else 'assistant',
                'content': row['消息内容']
            })

        return history
    except Exception as e:
        print(f"获取会话历史时出错: {e}")
        return []


@app.route('/')
def index():
    # 为每个会话生成唯一ID
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())

    # 获取所有会话列表
    sessions = get_all_sessions()
    return render_template('index.html', sessions=sessions)


@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({'error': '消息不能为空'}), 400

    # 获取或初始化会话历史
    if 'conversation_history' not in session:
        session['conversation_history'] = []

    conversation_history = session['conversation_history']

    # 添加用户消息到历史
    conversation_history.append({"role": "user", "content": user_message})

    # 保存用户消息到Excel
    save_to_excel(session['session_id'], "用户", user_message)

    try:
        # 准备API请求
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }

        payload = {
            "model": "deepseek-chat",
            "messages": conversation_history,
            "stream": False
        }

        # 调用DeepSeek API
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            assistant_message = result['choices'][0]['message']['content']
            tokens_used = result.get('usage', {}).get('total_tokens')

            # 添加助手回复到历史
            conversation_history.append({"role": "assistant", "content": assistant_message})
            session['conversation_history'] = conversation_history

            # 保存助手回复到Excel
            save_to_excel(session['session_id'], "助手", assistant_message, tokens_used)

            return jsonify({
                'response': assistant_message,
                'tokens_used': tokens_used,
                'history_length': len(conversation_history)
            })
        else:
            error_msg = f"API请求失败: {response.status_code} - {response.text}"
            return jsonify({'error': error_msg}), 500

    except requests.exceptions.Timeout:
        return jsonify({'error': '请求超时，请稍后重试'}), 408
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'网络错误: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'处理请求时出错: {str(e)}'}), 500


@app.route('/sessions', methods=['GET'])
def get_sessions():
    """获取所有会话列表"""
    sessions = get_all_sessions()
    return jsonify({'sessions': sessions})


@app.route('/session/<session_id>', methods=['GET'])
def get_session(session_id):
    """获取特定会话的详细信息"""
    history = get_session_history(session_id)
    return jsonify({
        'session_id': session_id,
        'history': history
    })


@app.route('/switch_session', methods=['POST'])
def switch_session():
    """切换到指定会话"""
    new_session_id = request.json.get('session_id')
    if not new_session_id:
        return jsonify({'error': '会话ID不能为空'}), 400

    # 获取新会话的历史记录
    history = get_session_history(new_session_id)

    # 更新会话
    session['session_id'] = new_session_id
    session['conversation_history'] = history

    return jsonify({
        'success': True,
        'session_id': new_session_id,
        'history': history,
        'message': f'已切换到会话: {new_session_id}'
    })


@app.route('/new_session', methods=['POST'])
def new_session():
    """创建新会话"""
    new_session_id = str(uuid.uuid4())

    # 更新会话
    session['session_id'] = new_session_id
    session['conversation_history'] = []

    return jsonify({
        'success': True,
        'session_id': new_session_id,
        'message': '已创建新会话'
    })


@app.route('/clear', methods=['POST'])
def clear_chat():
    """清空当前会话历史"""
    session.pop('conversation_history', None)
    # 生成新的会话ID
    session['session_id'] = str(uuid.uuid4())
    return jsonify({'success': True, 'message': '对话历史已清空'})


@app.route('/history', methods=['GET'])
def get_history():
    """获取当前会话历史"""
    history = session.get('conversation_history', [])
    return jsonify({'history': history})


if __name__ == '__main__':
    init_excel()

    app.run(debug=True, host='0.0.0.0', port=5000)
