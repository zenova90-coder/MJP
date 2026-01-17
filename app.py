import streamlit as st
import openai
import google.generativeai as genai
import datetime
import time
import json
import os
import hashlib

# -----------------------------------------------------------
# 1. 스타일 & 기본 설정
# -----------------------------------------------------------
st.set_page_config(page_title="MJP Lab: Management", layout="wide")

st.markdown("""
<style>
    div.stButton > button:first-child {
        background-color: #2c3e50;
        color: white;
        border-radius: 6px;
        font-weight: 600;
        border: none;
    }
    div.stButton > button:first-child:hover { background-color: #1a252f; }
    
    .energy-box {
        padding: 10px 20px;
        background-color: #f8f9fa;
        border-left: 5px solid #2c3e50;
        border-radius: 4px;
        display: flex; align-items: center; gap: 15px; margin-bottom: 25px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .energy-val { font-size: 20px; font-weight: bold; color: #2c3e50; }
    
    .log-entry {
        background-color: #fff; border: 1px solid #eee; 
        border-radius: 8px; padding: 15px; margin-bottom: 10px;
        border-left: 4px solid #3498db;
    }
    .success-modal {
        padding: 20px; background-color: #e8f6f3; 
        border: 1px solid #d4efdf; border-radius: 10px; 
        text-align: center; margin-bottom: 20px;
    }
    .prayer-text { font-style: italic; color: #145a32; font-size: 16px; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------
# 2. [핵심] 데이터베이스 관리 시스템 (JSON)
# -----------------------------------------------------------
USER_FILE = "users_db.json"

def init_user_db():
    """최초 실행 시 기본 관리자와 민주님 계정 생성"""
    if not os.path.exists(USER_FILE):
        default_users = {
            "admin": "1234",
            "minju": "0000"
        }
        with open(USER_FILE, "w", encoding="utf-8") as f:
            json.dump(default_users, f)

def load_users():
    """회원 명부 불러오기"""
    if not os.path.exists(USER_FILE): init_user_db()
    with open(USER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_new_user(new_id, new_pw):
    """[중복 체크] 후 회원 저장"""
    users = load_users()
    
    # 1. 중복 검사 (핵심 기능)
    if new_id in users:
        return False, "❌ 이미 존재하는 아이디입니다! 다른 아이디를 사용하세요."
    
    # 2. 저장
    users[new_id] = new_pw
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f)
    return True, f"✅ '{new_id}'님 등록 완료! 이제 로그인할 수 있습니다."

# 로그 시스템 (V8 기능 유지)
def get_log_filename(username): return f"logs_{username}.json"

def save_log(username, action, content):
    path = get_log_filename(username)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    new_entry = {"time": timestamp, "action": action, "content": content}
    logs = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try: logs = json.load(f)
            except: logs = []
    logs.insert(0, new_entry)
    with open(path, "w", encoding="utf-8") as f: json.dump(logs, f, ensure_ascii=False, indent=4)

def load_logs(username):
    path = get_log_filename(username)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    return []

# -----------------------------------------------------------
# 3. 세션 초기화
# -----------------------------------------------------------
# DB 초기화 실행
init_user_db()

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'username' not in st.session_state: st.session_state['username'] = ""
if 'user_energy' not in st.session_state: st.session_state['user_energy'] = 0

if 'research_context' not in st.session_state:
    st.session_state['research_context'] = {'topic': '', 'variables_options': [], 'variables': '', 'method_options': [], 'method': '', 'references': ''}
if 'paper_sections' not in st.session_state:
    st.session_state['paper_sections'] = {"서론": "", "이론적 배경": "", "연구 방법": "", "결과": "", "논의": ""}
if "chat_history_step0" not in st.session_state: st.session_state.chat_history_step0 = []
if "messages_helper" not in st.session_state: st.session_state.messages_helper = []

openai.api_key = st.secrets["OPENAI_API_KEY"]
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# -----------------------------------------------------------
# 4. 로그인 페이지 (DB 연동)
# -----------------------------------------------------------
def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 MJP Research Lab")
        st.caption("회원 전용 연구 시스템")
        
        with st.form("login"):
            uid = st.text_input("아이디")
            upw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("로그인"):
                users = load_users() # 파일에서 불러옴
                if uid in users and users[uid] == upw:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = uid
                    st.session_state['user_energy'] = 1000 # (실제론 파일에 에너지도 저장해야 완벽하지만 일단 유지)
                    st.rerun()
                else:
                    st.error("아이디 혹은 비밀번호가 틀렸습니다.")

# -----------------------------------------------------------
# 5. 메인 앱 (관리자 기능 추가)
# -----------------------------------------------------------
def main_app():
    user = st.session_state['username']
    
    def check_and_deduct(cost):
        if st.session_state['user_energy'] >= cost:
            st.session_state['user_energy'] -= cost
            return True
        st.error(f"Need Energy: {cost}"); return False

    # --- 사이드바 ---
    with st.sidebar:
        st.header(f"👤 {user}님")
        if st.button("로그아웃"):
            st.session_state['logged_in'] = False
            st.rerun()
        
        st.markdown("---")
        
        # [NEW] 관리자 전용 회원가입 메뉴
        # 민주님(admin이나 minju)만 볼 수 있게 설정 가능하지만, 지금은 기능 확인 위해 모두에게 노출
        # (원하시면 if user == 'admin': 조건을 넣으면 됩니다)
        with st.expander("⚙️ 회원 관리 (Admin)"):
            st.write("**신규 회원 등록**")
            new_id = st.text_input("새 아이디")
            new_pw = st.text_input("새 비밀번호", type="password")
            
            if st.button("회원 추가하기"):
                if new_id and new_pw:
                    # 여기서 중복 체크 함수 호출!
                    success, msg = save_new_user(new_id, new_pw)
                    if success: st.success(msg)
                    else: st.error(msg)
                else:
                    st.warning("아이디와 비번을 모두 입력하세요.")

        st.markdown("---")
        with st.expander("⚡ 에너지 충전소"):
            st.write("기업은행 010-2989-0076 (양민주)")
            code = st.text_input("쿠폰 코드")
            if st.button("충전"):
                if code == "TEST-1000":
                    st.session_state['user_energy'] += 1000
                    save_log(user, "에너지 충전", "1000E 충전")
                    st.markdown(f"""
                    <div class="success-modal">
                        <h3>✨ Energy Charged</h3>
                        <div class="prayer-text">"{user}님의 연구가 빛나는 결과가 되기를 기도합니다."</div>
                    </div>
                    """, unsafe_allow_html=True)

    # --- 메인 헤더 ---
    st.title("🎓 MJP Research Lab")
    st.markdown(f"""
    <div class="energy-box">
        <span>⚡ <b>Available Energy:</b></span>
        <span class="energy-val">{st.session_state['user_energy']}</span>
    </div>
    """, unsafe_allow_html=True)

    tabs = st.tabs(["💡 0. 토론", "1. 변인", "2. 방법", "3. 검색", "4. 작성", "5. 참고문헌", "📜 기록"])

    # (기능 구현부 - V8과 동일)
    def simple_chat(prompt, context=""):
        res = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user","content":f"Ctx:{context}\nQ:{prompt}"}])
        return res.choices[0].message.content

    with tabs[0]:
        st.header("💡 Brainstorming")
        for m in st.session_state.chat_history_step0:
             with st.chat_message(m["role"]): st.markdown(m["content"])
        if p := st.chat_input("토론...", key="t0"):
            if check_and_deduct(20):
                st.session_state.chat_history_step0.append({"role":"user","content":p})
                save_log(user, "토론 질문", p)
                with st.chat_message("user"): st.markdown(p)
                with st.chat_message("assistant"):
                    ans = simple_chat(p, "아이디어 토론")
                    st.markdown(ans)
                    st.session_state.chat_history_step0.append({"role":"assistant","content":ans})
                    save_log(user, "AI 답변", ans)

    with tabs[1]:
        st.subheader("🧠 Variables")
        v = st.text_area("변인", value=st.session_state['research_context']['variables'])
        if st.button("저장", key="sv"): 
            st.session_state['research_context']['variables']=v; save_log(user,"변인확정",v); st.success("Saved")

    with tabs[2]: st.subheader("📐 Method"); st.write("방법론 화면")
    with tabs[3]: st.subheader("🔍 Search"); st.write("검색 화면")
    with tabs[4]: st.subheader("✍️ Draft"); st.write("작성 화면")
    with tabs[5]: st.subheader("📚 Ref"); st.write("참고문헌 화면")

    with tabs[6]:
        st.header("📜 Activity Logs")
        logs = load_logs(user)
        for log in logs:
            st.markdown(f"<div class='log-entry'><b>{log['time']}</b> [{log['action']}]<br>{log['content']}</div>", unsafe_allow_html=True)

# -----------------------------------------------------------
# 6. 실행
# -----------------------------------------------------------
if st.session_state['logged_in']: main_app()
else: login_page()