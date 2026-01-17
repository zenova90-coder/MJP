import streamlit as st
import openai
import google.generativeai as genai
import datetime
import json
import os
import time

# -----------------------------------------------------------
# 1. [안전장치] 구글 시트 연동 (라이브러리 없어도 작동 보장)
# -----------------------------------------------------------
def sync_to_google_sheet(sheet_name, data_list):
    try:
        import gspread
        # 비밀키 확인
        if "gcp_service_account" not in st.secrets:
            return # 조용히 넘어감
        
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        sh = gc.open("MJP 연구실 관리대장")
        worksheet = sh.worksheet(sheet_name)
        worksheet.append_row(data_list)
    except Exception:
        pass # 에러 나도 무시하고 앱은 계속 실행

# -----------------------------------------------------------
# 2. 데이터 관리
# -----------------------------------------------------------
USER_FILE = "users_db.json"

def init_user_db():
    if not os.path.exists(USER_FILE):
        default_users = {"admin": "1234", "minju": "0000"}
        with open(USER_FILE, "w", encoding="utf-8") as f: json.dump(default_users, f)

def load_users():
    if not os.path.exists(USER_FILE): init_user_db()
    try:
        with open(USER_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except:
        return {"admin": "1234"} # 파일 깨짐 방지

def save_new_user(new_id, new_pw):
    users = load_users()
    if new_id in users: return False, "❌ 이미 존재하는 아이디입니다."
    users[new_id] = new_pw
    with open(USER_FILE, "w", encoding="utf-8") as f: json.dump(users, f)
    
    # 구글 시트 전송
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sync_to_google_sheet("Users", [ts, new_id, "신규 등록"])
    return True, f"✅ 등록 완료!"

def get_log_filename(username): return f"logs_{username}.json"

def save_log(username, action, content):
    path = get_log_filename(username)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entry = {"time": ts, "action": action, "content": content}
    
    logs = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try: logs = json.load(f)
            except: logs = []
    logs.insert(0, new_entry)
    with open(path, "w", encoding="utf-8") as f: json.dump(logs, f, ensure_ascii=False, indent=4)
    sync_to_google_sheet("Logs", [ts, username, action, content])

def load_logs(username):
    path = get_log_filename(username)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return []
    return []

# -----------------------------------------------------------
# 3. 설정 및 초기화 (KeyError 방지)
# -----------------------------------------------------------
st.set_page_config(page_title="MJP Lab", layout="wide")

# [핵심 수정] 초기화 로직 강화 (KeyError 원천 차단)
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'username' not in st.session_state: st.session_state['username'] = ""
if 'user_energy' not in st.session_state: st.session_state['user_energy'] = 0

# 연구 데이터 구조가 깨져있으면 복구
if 'research_context' not in st.session_state:
    st.session_state['research_context'] = {}

# 세부 항목 하나하나 체크해서 없으면 만듦
defaults = {
    'topic': '', 'variables_options': [], 'variables': '', 
    'method_options': [], 'method': '', 'references': ''
}
for k, v in defaults.items():
    if k not in st.session_state['research_context']:
        st.session_state['research_context'][k] = v

if 'paper_sections' not in st.session_state:
    st.session_state['paper_sections'] = {"서론": "", "이론적 배경": "", "연구 방법": "", "결과": "", "논의": ""}
if "chat_history_step0" not in st.session_state: st.session_state.chat_history_step0 = []
if "messages_helper" not in st.session_state: st.session_state.messages_helper = []

openai.api_key = st.secrets.get("OPENAI_API_KEY", "")
genai.configure(api_key=st.secrets.get("GEMINI_API_KEY", ""))

# -----------------------------------------------------------
# 4. 앱 로직
# -----------------------------------------------------------
def check_and_deduct(cost):
    if st.session_state['user_energy'] >= cost:
        st.session_state['user_energy'] -= cost
        return True
    st.error(f"Need Energy: {cost}"); return False

def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 MJP Lab")
        with st.form("login"):
            uid = st.text_input("ID")
            upw = st.text_input("PW", type="password")
            if st.form_submit_button("로그인"):
                users = load_users()
                if uid in users and users[uid] == upw:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = uid
                    if st.session_state['user_energy'] == 0: st.session_state['user_energy'] = 1000
                    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sync_to_google_sheet("Logs", [ts, uid, "로그인 성공", "-"])
                    st.rerun()
                else:
                    st.error("로그인 실패")

def main_app():
    user = st.session_state['username']
    
    with st.sidebar:
        st.header(f"👤 {user}")
        if st.button("로그아웃"): 
            st.session_state['logged_in'] = False
            st.rerun()
        st.markdown("---")
        with st.expander("⚡ 충전소"):
            code = st.text_input("쿠폰")
            if st.button("충전"):
                if code == "TEST-1000":
                    st.session_state['user_energy'] += 1000
                    save_log(user, "충전", "1000E")
                    st.success("충전 완료")
                else: st.error("코드 오류")

    st.title("🎓 MJP Research Lab")
    st.write(f"⚡ Available Energy: **{st.session_state['user_energy']}**")

    tabs = st.tabs(["💡 토론", "1. 변인", "2. 방법", "3. 검색", "4. 작성", "5. 참고", "📜 기록"])

    def simple_chat(prompt, ctx=""):
        try:
            res = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user","content":f"{ctx}\n{prompt}"}])
            return res.choices[0].message.content
        except: return "AI 오류 발생"

    with tabs[0]:
        st.header("Brainstorming")
        for m in st.session_state.chat_history_step0:
             with st.chat_message(m["role"]): st.markdown(m["content"])
        # [DuplicateId 방지] key를 명확하게 지정
        if p := st.chat_input("...", key="chat_tab_0"):
            if check_and_deduct(20):
                st.session_state.chat_history_step0.append({"role":"user","content":p})
                save_log(user, "토론 질문", p)
                st.rerun()

    with tabs[1]:
        st.subheader("Variables")
        v = st.text_area("변인", value=st.session_state['research_context']['variables'])
        if st.button("저장", key="btn_save_v"): 
            st.session_state['research_context']['variables']=v; save_log(user,"변인확정",v); st.success("Saved")

    with tabs[2]: st.write("Methodology Area")
    with tabs[3]: st.write("Search Area")
    with tabs[4]: st.write("Drafting Area")
    with tabs[5]: st.write("References Area")
    
    with tabs[6]:
        st.header("Logs")
        logs = load_logs(user)
        for log in logs:
            st.text(f"[{log['time']}] {log['action']}: {log['content'][:50]}...")

if st.session_state['logged_in']: main_app()
else: login_page()
