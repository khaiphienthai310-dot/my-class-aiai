import streamlit as st
import requests
import pandas as pd
import uuid
import json

# --- 页面设置 ---
st.set_page_config(page_title="智能助教", page_icon="🎓")

# --- 从 Streamlit Secrets 获取密钥 (为了安全) ---
# 如果在本地运行，可以直接把字符串填在这里，但部署到云端建议用 Secrets
try:
    COZE_API_TOKEN = st.secrets["COZE_API_TOKEN"]
    BOT_ID = st.secrets["BOT_ID"]
except:
    st.error("请在 Streamlit 后台配置 Secrets: COZE_API_TOKEN 和 BOT_ID")
    st.stop()

COZE_API_URL = "https://api.coze.cn/open_api/v2/chat"

# --- 初始化 Session ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_id" not in st.session_state:
    # 生成一个随机的学生ID，刷新页面会重置。
    # 如果想固定，可以让学生在侧边栏输入学号
    st.session_state.user_id = f"stu_{uuid.uuid4().hex[:8]}"

# --- 侧边栏：功能区 ---
with st.sidebar:
    st.title("🛠️ 功能菜单")
    st.write(f"当前用户ID: `{st.session_state.user_id}`")
    
    # 清空对话
    if st.button("🗑️ 清空对话"):
        st.session_state.messages = []
        st.rerun()
        
    st.divider()
    st.write("💾 **数据导出**")
    if len(st.session_state.messages) > 0:
        # 将对话记录转为 DataFrame
        chat_data = []
        for msg in st.session_state.messages:
            chat_data.append({
                "时间": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"), # 简易时间
                "角色": "学生" if msg["role"] == "user" else "AI助教",
                "内容": msg["content"]
            })
        df = pd.DataFrame(chat_data)
        csv = df.to_csv(index=False).encode('utf-8-sig') # utf-8-sig 防止Excel乱码
        
        st.download_button(
            label="📥 下载对话记录 (Excel/CSV)",
            data=csv,
            file_name=f'对话记录_{st.session_state.user_id}.csv',
            mime='text/csv',
        )
    else:
        st.write("暂无对话可导出")

# --- 主界面 ---
st.title("🎓 智能学习助手")
st.caption("无需登录，直接提问。刷新页面会重置对话。")

# 1. 展示历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 2. 处理用户输入
if prompt := st.chat_input("请输入你的问题..."):
    # 展示用户输入
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 调用 Coze API
    headers = {
        "Authorization": f"Bearer {COZE_API_TOKEN}",
        "Content-Type": "application/json",
        "Connection": "keep-alive",
        "Accept": "*/*"
    }
    
    payload = {
        "conversation_id": st.session_state.user_id,
        "bot_id": BOT_ID,
        "user": st.session_state.user_id,
        "query": prompt,
        "stream": False # 简单起见，这里没用流式输出，AI思考完会一次性显示
    }

    with st.spinner("AI 正在思考中..."):
        try:
            response = requests.post(COZE_API_URL, headers=headers, json=payload)
            if response.status_code == 200:
                res_data = response.json()
                
                # 解析 Coze 返回的复杂结构
                if res_data.get('msg') == 'success':
                    ai_reply = ""
                    # Coze 会返回多条消息（包括你的思考过程等），我们只取最终回答(type=answer)
                    for message in res_data.get('messages', []):
                        if message.get('type') == 'answer':
                            ai_reply = message.get('content')
                            break
                    
                    if not ai_reply:
                        # 兜底：如果没找到 answer 类型，取最后一条的内容
                        ai_reply = res_data.get('messages', [])[-1].get('content', "没有收到有效回复")
                    
                    with st.chat_message("assistant"):
                        st.markdown(ai_reply)
                    st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                else:
                    st.error(f"Coze API 报错: {res_data.get('msg')}")
            else:
                st.error(f"网络请求失败: {response.status_code} - {response.text}")
        except Exception as e:
            st.error(f"发生错误: {e}")
