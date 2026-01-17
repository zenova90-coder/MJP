import streamlit as st
import openai
import google.generativeai as genai
import datetime
import json
import os
import time

# -----------------------------------------------------------
# 1. 스타일 및 설정 (디자인 복구)
# -----------------------------------------------------------
st.set_page_config(page_title="MJP Research Lab", layout="wide")

st.markdown("""
<style>
    div.stButton > button:first-child { background-color: #2c3e50; color: white; border-radius: 6px; border: none; font-weight: 600;}
    div.stButton > button:first-child:hover { background-color: #1a252f; }
    .energy-box { padding: 12px 20px; background-color: #f8f9fa; border-left: 5px solid #2c3e50; border-radius: 4px; display: flex; align-items: center; gap: 15px; margin-bottom: 25px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .energy-val { font-size: 22px; font-weight: bold; color: #2c3e50; font-family: monospace; }
    .log-entry { background-color: #fff; border: 1px solid #eee; border-radius: 8px; padding: 15px; margin-bottom: 10px; border-left: 4px solid #3498db; }
    .success-modal { padding: 20px; background-color: #e8f6f3; border: 1px solid #d4efdf; border-radius: 10px; text-align: center; margin-bottom: 20px; }
    .prayer-text { font-style: italic; color: #145a32; font-size: 16px; margin-top: 10px; font-family: serif; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------
# 2. 시스템 함수 (구글 시트, DB, 로그)
# -----------------------------------------------------------
def sync_to_google_sheet(sheet_name, data_list):
    try:
        import gspread
        if "gcp_service_account" not in st.secrets: return 
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        try:
            sh = gc.open("MJP 연구실 관리대장")
            worksheet = sh.worksheet(sheet_name)
            worksheet.append_row(data_list)
        except: return 
    except: pass 

USER_FILE = "users_db.json"

def init_user_db():
    if not os.path.exists(USER_FILE):
        default_users = {"admin": "1234", "minju": "0000"}
        with open(USER_FILE, "w", encoding="utf-8") as f: json.dump(default_users, f)

def load_users():
    if not os.path.exists(USER_FILE): init_user_db()
    try:
        with open(USER_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {"admin": "1234"} 

def save_new_user(new_id, new_pw):
    users = load_users()
    if new_id in users: return False, "❌ 이미 존재하는 아이디입니다."
    users[new_id] = new_pw
    with open(USER_FILE, "w", encoding="utf-8") as f: json.dump(users, f)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sync_to_google_sheet("Users", [ts, new_id, "신규 등록"])
    return True, f"✅ '{new_id}'님 등록 완료!"

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
# 3. AI 기능 함수 (복구됨!)
# -----------------------------------------------------------
openai.api_key = st.secrets.get("OPENAI_API_KEY", "")
genai.configure(api_key=st.secrets.get("GEMINI_API_KEY", ""))

def simple_chat(prompt, ctx=""):
    try:
        if not openai.api_key: return "⚠️ API 키 설정 필요"
        res = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user","content":f"{ctx}\n{prompt}"}])
        return res.choices[0].message.content
    except Exception as e: return f"Error: {e}"

def get_ai_options(prompt):
    try:
        res = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user","content":prompt}])
        return [opt.strip() for opt in res.choices[0].message.content.split("|||") if opt.strip()]
    except: return ["AI 제안 실패", "다시 시도하세요"]

def search_literature(topic, vars_text):
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"주제: {topic}, 변인: {vars_text}. 관련 선행연구 3개 검색 요약."
        return model.generate_content(prompt).text
    except: return "검색 오류 (API Key 확인 필요)"

# -----------------------------------------------------------
# 4. 세션 초기화 (안전장치)
# -----------------------------------------------------------
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'username' not in st.session_state: st.session_state['username'] = ""
if 'user_energy' not in st.session_state: st.session_state['user_energy'] = 0

# 연구 데이터 구조체 복구
if 'research_context' not in st.session_state: st.session_state['research_context'] = {}
keys = ['topic', 'variables_options', 'variables', 'method_options', 'method', 'references']
for k in keys:
    if k not in st.session_state['research_context']:
        if 'options' in k: st.session_state['research_context'][k] = []
        else: st.session_state['research_context'][k] = ""

if 'paper_sections' not in st.session_state:
    st.session_state['paper_sections'] = {"서론": "", "이론적 배경": "", "연구 방법": "", "결과": "", "논의": ""}
if "chat_history_step0" not in st.session_state: st.session_state.chat_history_step0 = []

# -----------------------------------------------------------
# 5. 메인 앱 로직
# -----------------------------------------------------------
def check_and_deduct(cost):
    if st.session_state['user_energy'] >= cost:
        st.session_state['user_energy'] -= cost
        return True
    st.error(f"에너지가 부족합니다 (필요: {cost})"); return False

def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔐 MJP Lab")
        st.caption("연구원 전용 접속 시스템")
        with st.form("login_form"):
            uid = st.text_input("아이디")
            upw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("로그인"):
                users = load_users()
                if uid in users and users[uid] == upw:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = uid
                    if st.session_state['user_energy'] == 0: st.session_state['user_energy'] = 1000
                    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sync_to_google_sheet("Logs", [ts, uid, "로그인 성공", "-"])
                    st.rerun()
                else: st.error("로그인 정보 불일치")

def main_app():
    user = st.session_state['username']
    
    # [사이드바]
    with st.sidebar:
        st.header(f"👤 {user}님")
        if st.button("로그아웃"): st.session_state['logged_in'] = False; st.rerun()
        st.markdown("---")
        with st.expander("⚡ 에너지 충전소"):
            st.write("기업은행 010-2989-0076 (양민주)")
            code = st.text_input("쿠폰 번호")
            if st.button("충전"):
                if code == "TEST-1000":
                    st.session_state['user_energy'] += 1000
                    save_log(user, "충전", "1000E")
                    st.markdown(f"""
                    <div class="success-modal">
                        <h3>✨ Energy Charged</h3>
                        <div class="prayer-text">"{user}님의 연구가 빛나는 결과가 되기를 기도합니다."</div>
                    </div>""", unsafe_allow_html=True)
                else: st.error("유효하지 않은 코드")
        
        with st.expander("⚙️ 회원 관리 (Admin)"):
            new_id = st.text_input("신규 ID")
            new_pw = st.text_input("신규 PW", type="password")
            if st.button("회원 추가"):
                suc, msg = save_new_user(new_id, new_pw)
                if suc: st.success(msg)
                else: st.error(msg)

    # [메인 헤더]
    st.title("🎓 MJP Research Lab")
    st.markdown(f"""
    <div class="energy-box">
        <span>⚡ <b>Available Energy:</b></span>
        <span class="energy-val">{st.session_state['user_energy']}</span>
    </div>""", unsafe_allow_html=True)

    tabs = st.tabs(["💡 0. 토론", "1. 변인", "2. 방법", "3. 검색", "4. 작성", "5. 참고", "📜 기록"])

    # [Tab 0: 토론]
    with tabs[0]:
        st.header("💡 Brainstorming")
        for m in st.session_state.chat_history_step0:
             with st.chat_message(m["role"]): st.markdown(m["content"])
        if p := st.chat_input("아이디어 토론...", key="chat0"):
            if check_and_deduct(20):
                st.session_state.chat_history_step0.append({"role":"user","content":p})
                save_log(user, "토론 질문", p)
                with st.chat_message("user"): st.markdown(p)
                with st.chat_message("assistant"):
                    with st.spinner("생각 중..."):
                        ans = simple_chat(p, "연구 주제 토론 단계")
                        st.markdown(ans)
                        st.session_state.chat_history_step0.append({"role":"assistant","content":ans})
                        save_log(user, "AI 답변", ans)

    # [Tab 1: 변인] (AI 제안 기능 복구)
    with tabs[1]:
        st.subheader("🧠 Variables")
        v = st.text_area("최종 변인", value=st.session_state['research_context']['variables'])
        if st.button("✅ 저장", key="sv_v"): 
            st.session_state['research_context']['variables']=v; save_log(user,"변인확정",v); st.success("저장됨")
        
        topic = st.text_input("연구 주제 (제안용)", value=st.session_state['research_context']['topic'])
        if st.button("🤖 3가지 구조 제안 (50E)", key="ai_v"):
            if check_and_deduct(50):
                with st.spinner("생성 중..."):
                    opts = get_ai_options(f"주제 '{topic}'에 적합한 변인 구조 3가지 제안 (구분자 |||)")
                    st.session_state['research_context']['variables_options'] = opts
                    st.session_state['research_context']['topic'] = topic
                    st.rerun()
        
        if st.session_state['research_context']['variables_options']:
            choice = st.radio("선택:", st.session_state['research_context']['variables_options'])
            if st.button("🔼 적용하기", key="app_v"):
                st.session_state['research_context']['variables'] = choice
                st.rerun()

    # [Tab 2: 방법] (AI 제안 기능 복구)
    with tabs[2]:
        st.subheader("📐 Methodology")
        m_val = st.text_area("최종 방법", value=st.session_state['research_context']['method'])
        if st.button("✅ 저장", key="sv_m"): 
            st.session_state['research_context']['method']=m_val; save_log(user,"방법론확정",m_val); st.success("저장됨")
        
        if st.button("🤖 방법론 제안 (50E)", key="ai_m"):
            if check_and_deduct(50):
                with st.spinner("설계 중..."):
                    opts = get_ai_options(f"변인 '{st.session_state['research_context']['variables']}'에 적합한 연구방법 3가지 (구분자 |||)")
                    st.session_state['research_context']['method_options'] = opts
                    st.rerun()
        
        if st.session_state['research_context']['method_options']:
            choice_m = st.radio("선택:", st.session_state['research_context']['method_options'])
            if st.button("🔼 적용하기", key="app_m"):
                st.session_state['research_context']['method'] = choice_m
                st.rerun()

    # [Tab 3: 검색] (Gemini 복구)
    with tabs[3]:
        st.subheader("🔍 Literature Search")
        if st.button("🚀 Gemini 검색 (30E)", key="sch_g"):
            if check_and_deduct(30):
                with st.spinner("검색 중..."):
                    res = search_literature(st.session_state['research_context']['topic'], st.session_state['research_context']['variables'])
                    st.session_state['research_context']['references'] = res
                    save_log(user, "선행연구검색", res)
                    st.rerun()
        st.text_area("검색 결과", value=st.session_state['research_context']['references'], height=400)

    # [Tab 4: 작성] (논문 초안 복구)
    with tabs[4]:
        st.subheader("✍️ Drafting")
        sec = st.selectbox("챕터", list(st.session_state['paper_sections'].keys()))
        if st.button(f"🤖 {sec} 초안 작성 (100E)", key="wrt_ai"):
            if check_and_deduct(100):
                with st.spinner("작성 중..."):
                    draft = simple_chat(f"참고문헌과 변인을 바탕으로 '{sec}' 챕터를 학술적으로 작성해줘.", str(st.session_state['research_context']))
                    st.session_state['paper_sections'][sec] = draft
                    save_log(user, f"논문작성({sec})", draft)
                    st.rerun()
        
        current = st.text_area("에디터", value=st.session_state['paper_sections'][sec], height=500)
        if st.button("💾 내용 저장", key="sv_sec"):
            st.session_state['paper_sections'][sec] = current
            save_log(user, f"논문수정({sec})", current)
            st.success("저장됨")

    # [Tab 5: 참고문헌] (APA 복구)
    with tabs[5]:
        st.subheader("📚 References")
        if st.button("✨ APA 스타일 변환 (20E)", key="apa_btn"):
            if check_and_deduct(20):
                res = simple_chat("다음 참고문헌을 APA 스타일로 정리해줘:\n" + st.session_state['research_context']['references'])
                st.markdown(res)

    # [Tab 6: 기록] (로그 뷰어)
    with tabs[6]:
        st.header(f"📜 {user}'s History")
        logs = load_logs(user)
        for log in logs:
            st.markdown(f"<div class='log-entry'><b>{log['time']}</b> [{log['action']}]<br>{log['content'][:100]}...</div>", unsafe_allow_html=True)

if st.session_state['logged_in']: main_app()
else: login_page()
