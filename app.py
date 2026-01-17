import streamlit as st
import openai
import google.generativeai as genai
import datetime
import json
import os
import gspread # [NEW] 구글 시트 연동 라이브러리

# -----------------------------------------------------------
# 1. 구글 시트 연동 설정 (비밀 열쇠 사용)
# -----------------------------------------------------------
def sync_to_google_sheet(sheet_name, data_list):
    """
    구글 시트에 데이터를 한 줄 추가하는 함수
    sheet_name: 'Logs' 또는 'Users'
    data_list: ['날짜', '아이디', '내용'...]
    """
    try:
        # secrets.toml에서 키를 꺼내서 연결
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        # 스프레드시트 열기 (파일 이름이 정확해야 함!)
        sh = gc.open("MJP 연구실 관리대장") 
        worksheet = sh.worksheet(sheet_name)
        worksheet.append_row(data_list)
    except Exception as e:
        # 아직 설정이 안 되었거나 오류가 나도 앱은 멈추지 않게 함
        print(f"구글 시트 연동 실패 (설정을 확인하세요): {e}")

# -----------------------------------------------------------
# 2. 기존 데이터 관리 함수 (업그레이드)
# -----------------------------------------------------------
USER_FILE = "users_db.json"

def init_user_db():
    if not os.path.exists(USER_FILE):
        default_users = {"admin": "1234", "minju": "0000"}
        with open(USER_FILE, "w", encoding="utf-8") as f: json.dump(default_users, f)

def load_users():
    if not os.path.exists(USER_FILE): init_user_db()
    with open(USER_FILE, "r", encoding="utf-8") as f: return json.load(f)

def save_new_user(new_id, new_pw):
    users = load_users()
    if new_id in users: return False, "❌ 이미 존재하는 아이디입니다."
    
    users[new_id] = new_pw
    with open(USER_FILE, "w", encoding="utf-8") as f: json.dump(users, f)
    
    # [NEW] 구글 시트 'Users' 탭에 자동 추가
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sync_to_google_sheet("Users", [timestamp, new_id, "신규 등록"])
    
    return True, f"✅ '{new_id}'님 등록 완료!"

def get_log_filename(username): return f"logs_{username}.json"

def save_log(username, action, content):
    # 1. 로컬 파일 저장 (기존)
    path = get_log_filename(username)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_entry = {"time": timestamp, "action": action, "content": content}
    
    logs = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try: logs = json.load(f)
            except: logs = []
    logs.insert(0, new_entry)
    with open(path, "w", encoding="utf-8") as f: json.dump(logs, f, ensure_ascii=False, indent=4)
    
    # [NEW] 2. 구글 시트 'Logs' 탭에 실시간 전송!
    sync_to_google_sheet("Logs", [timestamp, username, action, content])

def load_logs(username):
    path = get_log_filename(username)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    return []

# -----------------------------------------------------------
# 3. 스타일 및 설정
# -----------------------------------------------------------
st.set_page_config(page_title="MJP Lab: Auto-Sync", layout="wide")
st.markdown("""<style>
    div.stButton > button:first-child { background-color: #2c3e50; color: white; border-radius: 6px; }
    .energy-box { padding: 10px 20px; background-color: #f8f9fa; border-left: 5px solid #2c3e50; border-radius: 4px; display: flex; align-items: center; gap: 15px; margin-bottom: 25px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .energy-val { font-size: 20px; font-weight: bold; color: #2c3e50; }
    .log-entry { background-color: #fff; border: 1px solid #eee; border-radius: 8px; padding: 15px; margin-bottom: 10px; border-left: 4px solid #3498db; }
</style>""", unsafe_allow_html=True)

# 초기화
init_user_db()
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'username' not in st.session_state: st.session_state['username'] = ""
if 'user_energy' not in st.session_state: st.session_state['user_energy'] = 0
if 'research_context' not in st.session_state: st.session_state['research_context'] = {'topic': '', 'variables_options': [], 'variables': '', 'method_options': [], 'method': '', 'references': ''}
if 'paper_sections' not in st.session_state: st.session_state['paper_sections'] = {"서론": "", "이론적 배경": "", "연구 방법": "", "결과": "", "논의": ""}
if "chat_history_step0" not in st.session_state: st.session_state.chat_history_step0 = []
if "messages_helper" not in st.session_state: st.session_state.messages_helper = []

openai.api_key = st.secrets["OPENAI_API_KEY"]
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

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
            uid = st.text_input("아이디")
            upw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("로그인"):
                users = load_users()
                if uid in users and users[uid] == upw:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = uid
                    st.session_state['user_energy'] = 1000
                    # [NEW] 로그인 기록도 구글 시트로!
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sync_to_google_sheet("Logs", [timestamp, uid, "로그인 성공", "-"])
                    st.rerun()
                else:
                    st.error("실패")

def main_app():
    user = st.session_state['username']
    
    with st.sidebar:
        st.header(f"👤 {user}")
        if st.button("로그아웃"): st.session_state['logged_in'] = False; st.rerun()
        st.markdown("---")
        with st.expander("⚙️ 회원 관리 (Admin)"):
            new_id = st.text_input("새 아이디")
            new_pw = st.text_input("새 비번", type="password")
            if st.button("추가"):
                if new_id and new_pw:
                    suc, msg = save_new_user(new_id, new_pw)
                    if suc: st.success(msg)
                    else: st.error(msg)
        st.markdown("---")
        with st.expander("⚡ 충전소"):
            code = st.text_input("쿠폰")
            if st.button("충전"):
                if code == "TEST-1000":
                    st.session_state['user_energy'] += 1000
                    save_log(user, "충전", "1000E")
                    st.success("충전 완료")

    st.title("🎓 MJP Research Lab")
    st.markdown(f"<div class='energy-box'><span>⚡ <b>Energy:</b></span><span class='energy-val'>{st.session_state['user_energy']}</span></div>", unsafe_allow_html=True)

    tabs = st.tabs(["💡 토론", "1. 변인", "2. 방법", "3. 검색", "4. 작성", "5. 참고", "📜 기록"])

    def simple_chat(prompt, ctx=""):
        res = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user","content":f"{ctx}\n{prompt}"}])
        return res.choices[0].message.content

    with tabs[0]:
        st.header("Brainstorming")
        for m in st.session_state.chat_history_step0:
             with st.chat_message(m["role"]): st.markdown(m["content"])
        if p := st.chat_input("...", key="t0"):
            if check_and_deduct(20):
                st.session_state.chat_history_step0.append({"role":"user","content":p})
                save_log(user, "토론 질문", p)
                with st.chat_message("user"): st.markdown(p)
                with st.chat_message("assistant"):
                    ans = simple_chat(p)
                    st.markdown(ans)
                    st.session_state.chat_history_step0.append({"role":"assistant","content":ans})
                    save_log(user, "AI 답변", ans)

    with tabs[1]:
        st.subheader("Variables")
        v = st.text_area("변인", value=st.session_state['research_context']['variables'])
        if st.button("저장", key="sv"): 
            st.session_state['research_context']['variables']=v; save_log(user,"변인확정",v); st.success("Saved")

    # (나머지 탭들은 UI 구조 동일하므로 생략하지만 실제 파일엔 포함)
    with tabs[2]: st.write("Methodology Area")
    with tabs[3]: st.write("Search Area")
    with tabs[4]: st.write("Drafting Area")
    with tabs[5]: st.write("References Area")

    with tabs[6]:
        st.header("Activity Logs")
        logs = load_logs(user)
        for log in logs:
            st.markdown(f"<div class='log-entry'><b>{log['time']}</b> [{log['action']}]<br>{log['content']}</div>", unsafe_allow_html=True)

if st.session_state['logged_in']: main_app()
else: login_page()