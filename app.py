import streamlit as st
import openai
import google.generativeai as genai
import gspread
import datetime
import json
import os
import time
from docx import Document
from io import BytesIO

# -----------------------------------------------------------
# 0. 에너지 가격표 및 스타일 설정
# -----------------------------------------------------------
PRICES = {
    "chat_step0": 10,      # 토론 코멘트
    "var_confirm": 25,     # 변인 확정
    "method_confirm": 30,  # 방법론 확정
    "search": 30,          # 선행연구 검색
    "draft": 100,          # 논문 초안 작성
    "ref": 30,             # APA 변환
    "side_chat": 5         # AI 조교 질문
}

st.set_page_config(page_title="MJP Research Lab", layout="wide")

st.markdown("""
<style>
    div.stButton > button:first-child { background-color: #2c3e50; color: white; border-radius: 6px; border: none; font-weight: 600;}
    div.stButton > button:first-child:hover { background-color: #1a252f; }
    .energy-box { padding: 12px 20px; background-color: #f8f9fa; border-left: 5px solid #2c3e50; border-radius: 4px; display: flex; align-items: center; gap: 15px; margin-bottom: 25px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .energy-val { font-size: 22px; font-weight: bold; color: #2c3e50; font-family: monospace; }
    .confirm-box { padding: 15px; border: 2px solid #e74c3c; background-color: #fdedec; border-radius: 8px; margin-top: 10px; margin-bottom: 10px; text-align: center; }
    .log-entry { background-color: #fff; border: 1px solid #eee; border-radius: 8px; padding: 12px; margin-bottom: 8px; border-left: 4px solid #3498db; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------
# 1. 구글 시트 데이터베이스 연동
# -----------------------------------------------------------
@st.cache_resource
def get_google_sheet_connection():
    try:
        if "gcp_service_account" not in st.secrets: return None
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        return gc.open("MJP 연구실 관리대장")
    except: return None

def fetch_users_from_sheet():
    sh = get_google_sheet_connection()
    user_dict = {"zenova90": "0931285asd*"} # 관리자 기본값
    if not sh: return user_dict
    try:
        ws = sh.worksheet("Users")
        records = ws.get_all_values()
        for row in records[1:]:
            if len(row) >= 3: user_dict[row[1]] = row[2]
        return user_dict
    except: return user_dict

def register_user_to_sheet(new_id, new_pw):
    sh = get_google_sheet_connection()
    if not sh: return False, "DB 연결 오류 (Secrets 설정 확인)"
    current = fetch_users_from_sheet()
    if new_id in current: return False, "❌ 이미 존재하는 아이디입니다."
    try:
        ws = sh.worksheet("Users")
        ws.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), new_id, new_pw])
        return True, "✅ 가입 완료! 로그인 해주세요."
    except: return False, "가입 처리 중 오류 발생"

def log_to_sheet(username, action, content):
    sh = get_google_sheet_connection()
    if not sh: return
    try:
        ws = sh.worksheet("Logs")
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        ws.append_row([date_str, time_str, username, action, content])
    except: pass

def fetch_logs_by_date(username, date_str):
    sh = get_google_sheet_connection()
    if not sh: return []
    try:
        ws = sh.worksheet("Logs")
        rows = ws.get_all_values()
        filtered = [{"time": r[1], "action": r[3], "content": r[4]} for r in rows[1:] if r[0] == date_str and r[2] == username]
        return sorted(filtered, key=lambda x: x['time'], reverse=True)
    except: return []

# -----------------------------------------------------------
# 2. 문서화 및 유틸리티
# -----------------------------------------------------------
def create_word_report(username, date_str, logs):
    doc = Document()
    doc.add_heading(f'{username} 연구 보고서 ({date_str})', 0)
    for log in logs:
        doc.add_heading(f"[{log['time']}] {log['action']}", level=2)
        doc.add_paragraph(log['content'])
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

def check_and_deduct(cost):
    if st.session_state['user_energy'] >= cost:
        st.session_state['user_energy'] -= cost
        return True
    st.error(f"⚠️ 에너지가 부족합니다. (필요: {cost})"); return False

# -----------------------------------------------------------
# 3. AI 조교 '다온' 핵심 로직
# -----------------------------------------------------------
openai.api_key = st.secrets.get("OPENAI_API_KEY", "")
genai.configure(api_key=st.secrets.get("GEMINI_API_KEY", ""))

def chat_with_daon(prompt, context_data, stage_name):
    try:
        sys_msg = f"당신은 심리학 연구 조교 '다온'입니다. 현재 단계: {stage_name}. 화면 내용: {context_data}. 전문적이고 친절하게 답하세요."
        res = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"system","content":sys_msg},{"role":"user","content":prompt}])
        return res.choices[0].message.content
    except: return "AI 조교와 연결할 수 없습니다."

def get_ai_suggestions(prompt):
    try:
        sys_msg = "4개의 대안을 제안하세요. 각 안은 '|||' 구분자로 나누고 설명 없이 제목 위주로 작성하세요."
        res = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"system","content":sys_msg},{"role":"user","content":prompt}])
        return [opt.strip() for opt in res.choices[0].message.content.split("|||") if opt.strip()][:4]
    except: return ["제안 실패"]

# -----------------------------------------------------------
# 4. 세션 및 상태 관리
# -----------------------------------------------------------
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_energy' not in st.session_state: st.session_state.user_energy = 500
if 'confirm_state' not in st.session_state: st.session_state.confirm_state = {"type": None, "data": None}

for key in ['topic', 'v_opts', 'v_final', 'm_opts', 'm_final', 'refs']:
    if key not in st.session_state: st.session_state[key] = [] if 'opts' in key else ""
if 'paper' not in st.session_state: st.session_state.paper = {"서론": "", "이론적 배경": "", "연구 방법": "", "결과": "", "논의": ""}
for i in range(6):
    if f"chat_{i}" not in st.session_state: st.session_state[f"chat_{i}"] = []

# -----------------------------------------------------------
# 5. UI 렌더링 함수
# -----------------------------------------------------------
def render_side_chat(idx, context, name):
    st.markdown(f"###### 💬 AI 조교 다온 ({name})")
    for m in st.session_state[f"chat_{idx}"]:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    if p := st.chat_input(f"질문 ({PRICES['side_chat']}E)", key=f"input_{idx}"):
        if check_and_deduct(PRICES['side_chat']):
            st.session_state[f"chat_{idx}"].append({"role":"user","content":p})
            with st.chat_message("user"): st.markdown(p)
            ans = chat_with_daon(p, context, name)
            st.session_state[f"chat_{idx}"].append({"role":"assistant","content":ans})
            log_to_sheet(st.session_state.username, f"조교질문({name})", p)
            st.rerun()

def main_app():
    user = st.session_state.username
    with st.sidebar:
        st.header(f"👤 {user}")
        st.markdown("---")
        st.subheader("📅 연구 기록")
        d = st.date_input("날짜 선택")
        if st.button("기록 불러오기"):
            st.session_state.history = fetch_logs_by_date(user, d.strftime("%Y-%m-%d"))
            st.session_state.h_date = d.strftime("%Y-%m-%d")
        if 'history' in st.session_state and st.session_state.history:
            buf = create_word_report(user, st.session_state.h_date, st.session_state.history)
            st.download_button("📄 워드 다운로드", buf, f"MJP_{st.session_state.h_date}.docx")
        
        if st.button("💾 오늘의 기록 저장"):
            log_to_sheet(user, "수동저장", f"주제: {st.session_state.topic}\n변인: {st.session_state.v_final}")
            st.success("저장 완료!"); time.sleep(1); st.rerun()
            
        if user == "zenova90": #
            st.markdown("---")
            st.link_button("📂 관리자 시트 열기", "https://docs.google.com/spreadsheets/d/1XshK969D36k74uR7N_uG8Pst0S-k7oK4fD1E-6Y_iCg/")
            
        if st.button("로그아웃"): st.session_state.logged_in = False; st.rerun()

    st.title("🎓 MJP Research Lab")
    st.markdown(f"<div class='energy-box'>⚡ Available Energy: <span class='energy-val'>{st.session_state.user_energy}</span></div>", unsafe_allow_html=True)
    
    tabs = st.tabs(["💡 토론", "1. 변인", "2. 방법", "3. 검색", "4. 작성", "5. APA", "📜 로그"])

    with tabs[0]: # 토론
        render_side_chat(0, "주제 구상 중", "브레인스토밍")

    with tabs[1]: # 변인
        L, R = st.columns([6, 4])
        with L:
            st.session_state.topic = st.text_input("연구 주제", value=st.session_state.topic)
            if st.button("🤖 4가지 안 제안 (무료)"):
                st.session_state.v_opts = get_ai_suggestions(f"주제 '{st.session_state.topic}' 변인 구조 제안")
            if st.session_state.v_opts:
                pick = st.radio("안 선택", st.session_state.v_opts)
                if st.button("적용하기"): st.session_state.confirm_state = {"type": "v", "data": pick}
            
            if st.session_state.confirm_state["type"] == "v":
                st.markdown(f"<div class='confirm-box'>💰 {PRICES['var_confirm']}E 차감됩니다.</div>", unsafe_allow_html=True)
                if st.button("✅ 결제 및 적용"):
                    if check_and_deduct(PRICES['var_confirm']):
                        st.session_state.v_final = st.session_state.confirm_state["data"]
                        st.session_state.confirm_state = {"type": None, "data": None}
                        log_to_sheet(user, "변인확정", st.session_state.v_final); st.rerun()
            st.text_area("확정된 변인", value=st.session_state.v_final)
        with R: render_side_chat(1, f"주제:{st.session_state.topic}\n변인:{st.session_state.v_final}", "변인설계")

    with tabs[2]: # 방법론
        L, R = st.columns([6, 4])
        with L:
            if st.button("🤖 방법론 제안 (무료)"):
                st.session_state.m_opts = get_ai_suggestions(f"변인 '{st.session_state.v_final}' 적합한 연구방법")
            if st.session_state.m_opts:
                pick = st.radio("방법론 선택", st.session_state.m_opts)
                if st.button("방법론 적용"): st.session_state.confirm_state = {"type": "m", "data": pick}
            
            if st.session_state.confirm_state["type"] == "m":
                st.markdown(f"<div class='confirm-box'>💰 {PRICES['method_confirm']}E 차감됩니다.</div>", unsafe_allow_html=True)
                if st.button("✅ 결제/적용"):
                    if check_and_deduct(PRICES['method_confirm']):
                        st.session_state.m_final = st.session_state.confirm_state["data"]
                        st.session_state.confirm_state = {"type": None, "data": None}
                        log_to_sheet(user, "방법확정", st.session_state.m_final); st.rerun()
            st.text_area("확정된 방법", value=st.session_state.m_final)
        with R: render_side_chat(2, f"방법:{st.session_state.m_final}", "방법론설계")

    with tabs[3]: # 검색
        L, R = st.columns([6, 4])
        with L:
            if st.button(f"🚀 Gemini 검색 ({PRICES['search']}E)"):
                if check_and_deduct(PRICES['search']):
                    st.session_state.refs = search_literature(st.session_state.topic, st.session_state.v_final)
                    log_to_sheet(user, "선행연구검색", st.session_state.refs); st.rerun()
            st.text_area("검색 결과", value=st.session_state.refs, height=400)
        with R: render_right_chat(3, st.session_state.refs, "연구검색")

    with tabs[4]: # 작성
        L, R = st.columns([6, 4])
        with L:
            sec = st.selectbox("챕터 선택", list(st.session_state.paper.keys()))
            if st.button(f"✍️ AI 작성 ({PRICES['draft']}E)"):
                if check_and_deduct(PRICES['draft']):
                    with st.spinner("작성 중..."):
                        txt = chat_with_daon(f"'{sec}' 챕터 학술적 작성", str(st.session_state.refs), "논문작성")
                        st.session_state.paper[sec] = txt
                        log_to_sheet(user, f"작성({sec})", txt); st.rerun()
            st.session_state.paper[sec] = st.text_area("에디터", value=st.session_state.paper[sec], height=400)
        with R: render_right_chat(4, st.session_state.paper[sec], "논문집필")

    with tabs[5]: # APA
        L, R = st.columns([6, 4])
        with L:
            if st.button(f"✨ APA 스타일 변환 ({PRICES['ref']}E)"):
                if not st.session_state.refs.strip(): st.warning("⚠️ 변환할 내용이 없습니다.")
                elif check_and_deduct(PRICES['ref']):
                    apa = chat_with_daon("APA 스타일로 변환해줘", st.session_state.refs, "참고문헌")
                    st.markdown(apa); log_to_sheet(user, "APA변환", apa)
        with R: render_right_chat(5, st.session_state.refs, "문헌정리")

    with tabs[6]:
        logs = fetch_logs_by_date(user, datetime.datetime.now().strftime("%Y-%m-%d"))
        for l in logs: st.markdown(f"<div class='log-entry'><b>{l['time']}</b> [{l['action']}] {l['content'][:100]}...</div>", unsafe_allow_html=True)

# 로그인/회원가입 페이지
if not st.session_state.logged_in:
    st.title("🔐 MJP Research Lab")
    t1, t2 = st.tabs(["로그인", "회원가입"])
    with t1:
        with st.form("L"):
            u, p = st.text_input("ID"), st.text_input("PW", type="password")
            if st.form_submit_button("접속"):
                db = fetch_users_from_sheet()
                if u in db and db[u] == p:
                    st.session_state.logged_in, st.session_state.username = True, u
                    log_to_sheet(u, "로그인", "성공"); st.rerun()
                else: st.error("정보 불일치")
    with t2:
        with st.form("S"):
            nu, np = st.text_input("새 ID"), st.text_input("새 PW", type="password")
            if st.form_submit_button("가입"):
                s, m = register_user_to_sheet(nu, np)
                if s: st.success(m)
                else: st.error(m)
else: main_app()
