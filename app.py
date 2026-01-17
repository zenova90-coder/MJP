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

# --- 0. 가격표 및 스타일 ---
PRICES = {
    "chat_step0": 10, "var_confirm": 25, "method_confirm": 30,
    "search": 30, "draft": 100, "ref": 30, "side_chat": 5
}

st.set_page_config(page_title="MJP Research Lab", layout="wide")
st.markdown("""<style>
    div.stButton > button:first-child { background-color: #2c3e50; color: white; border-radius: 6px; border: none; font-weight: 600;}
    .energy-box { padding: 12px 20px; background-color: #f8f9fa; border-left: 5px solid #2c3e50; border-radius: 4px; display: flex; align-items: center; gap: 15px; margin-bottom: 25px; }
    .energy-val { font-size: 22px; font-weight: bold; color: #2c3e50; font-family: monospace; }
    .confirm-box { padding: 15px; border: 2px solid #e74c3c; background-color: #fdedec; border-radius: 8px; margin: 10px 0; text-align: center; }
</style>""", unsafe_allow_html=True)

# --- 1. DB 함수 (구글 시트 연동) ---
def get_gs_sh():
    try:
        if "gcp_service_account" not in st.secrets: return None
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        return gc.open("MJP 연구실 관리대장")
    except: return None

def fetch_users():
    users = {"zenova90": "0931285asd*"}
    sh = get_gs_sh()
    if not sh: return users
    try:
        ws = sh.worksheet("Users")
        for r in ws.get_all_values()[1:]:
            if len(r) >= 3: users[r[1]] = r[2]
        return users
    except: return users

def register_user(nid, npw):
    sh = get_gs_sh()
    if not sh: return False, "DB 연동 오류 (Secrets 확인)"
    users = fetch_users()
    if nid in users: return False, "❌ 이미 존재하는 ID입니다."
    try:
        ws = sh.worksheet("Users")
        ws.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), nid, npw])
        return True, "✅ 가입 성공! 로그인 하세요."
    except Exception as e: return False, f"오류: {e}"

def log_to_sheet(u, a, c):
    sh = get_gs_sh()
    if not sh: return
    try:
        ws = sh.worksheet("Logs")
        now = datetime.datetime.now()
        ws.append_row([now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), u, a, str(c)])
    except: pass

# --- 2. AI 및 유틸리티 ---
openai.api_key = st.secrets.get("OPENAI_API_KEY", "")
genai.configure(api_key=st.secrets.get("GEMINI_API_KEY", ""))

def chat_ai(prompt, ctx, stage):
    try:
        res = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"system","content":f"심리연구조교 다온. 단계:{stage}\n{ctx}"},{"role":"user","content":prompt}])
        return res.choices[0].message.content
    except: return "AI 서비스 일시 중단"

def check_energy(cost):
    if st.session_state.user_energy >= cost:
        st.session_state.user_energy -= cost
        return True
    st.error("에너지가 부족합니다."); return False

# --- 3. 세션 초기화 ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_energy' not in st.session_state: st.session_state.user_energy = 500
if 'research_context' not in st.session_state:
    st.session_state.research_context = {'topic':'', 'variables_options':[], 'variables':'', 'method_options':[], 'method':'', 'references':''}
if 'paper_sections' not in st.session_state:
    st.session_state.paper_sections = {"서론":"", "이론적 배경":"", "연구 방법":"", "결과":"", "논의":""}
if 'confirm_state' not in st.session_state: st.session_state.confirm_state = {"type": None, "data": None}
for i in range(6):
    if f'chat_{i}' not in st.session_state: st.session_state[f'chat_{i}'] = []

# --- 4. 렌더링 함수 (대화창) ---
def render_chat(idx, ctx_data, stage):
    st.markdown(f"###### 💬 AI 다온 ({stage})")
    ckey = f'chat_{idx}'
    for m in st.session_state[ckey]:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    
    if p := st.chat_input(f"질문 (5E)", key=f"input_{idx}"):
        if check_energy(PRICES["side_chat"]):
            st.session_state[ckey].append({"role":"user", "content":p})
            with st.chat_message("user"): st.markdown(p)
            ans = chat_ai(p, ctx_data, stage)
            st.session_state[ckey].append({"role":"assistant", "content":ans})
            log_to_sheet(st.session_state.username, f"채팅({stage})", p)
            st.rerun()

def main_app():
    u = st.session_state.username
    with st.sidebar:
        st.header(f"👤 {u}님")
        if st.button("💾 오늘 기록 저장"):
            log_to_sheet(u, "수동저장", str(st.session_state.research_context))
            st.success("저장 완료!"); time.sleep(0.5); st.rerun()
        if u == "zenova90":
            st.link_button("📂 시트 열기", "https://docs.google.com/spreadsheets")
        if st.button("로그아웃"): st.session_state.logged_in = False; st.rerun()

    st.title("🎓 MJP Research Lab")
    st.markdown(f"<div class='energy-box'>⚡ Energy: <span class='energy-val'>{st.session_state.user_energy}</span></div>", unsafe_allow_html=True)
    tabs = st.tabs(["💡 토론", "1. 변인", "2. 방법", "3. 검색", "4. 작성", "5. 참고"])

    with tabs[0]: # 토론
        render_chat(0, "초기 아이디어", "토론")
    
    with tabs[1]: # 변인
        L, R = st.columns([6, 4])
        with L: st.subheader("Variables"); st.text_area("변인", value=st.session_state.research_context['variables'])
        with R: render_chat(1, st.session_state.research_context['variables'], "변인")

    with tabs[2]: # 방법 (대화창 복구)
        L, R = st.columns([6, 4])
        with L: st.subheader("Methodology"); st.text_area("방법", value=st.session_state.research_context['method'])
        with R: render_chat(2, st.session_state.research_context['method'], "방법론")

    with tabs[3]: # 검색
        L, R = st.columns([6, 4])
        with L: st.subheader("Search"); st.text_area("결과", value=st.session_state.research_context['references'])
        with R: render_chat(3, st.session_state.research_context['references'], "검색")

    with tabs[4]: # 작성 (대화창 복구)
        L, R = st.columns([6, 4])
        with L:
            st.subheader("Drafting")
            sec = st.selectbox("챕터", list(st.session_state.paper_sections.keys()))
            st.text_area("에디터", value=st.session_state.paper_sections[sec], height=400)
        with R: render_chat(4, st.session_state.paper_sections[sec], f"작성-{sec}")

    with tabs[5]: # 참고
        L, R = st.columns([6, 4])
        with L: st.subheader("APA")
        with R: render_chat(5, st.session_state.research_context['references'], "참고")

if st.session_state.logged_in: main_app()
else:
    st.title("🔐 MJP Research Lab")
    t1, t2 = st.tabs(["로그인", "회원가입"])
    with t1:
        with st.form("login"):
            uid = st.text_input("ID"); upw = st.text_input("PW", type="password")
            if st.form_submit_button("로그인"):
                us = fetch_users()
                if uid in us and us[uid] == upw:
                    st.session_state.logged_in = True; st.session_state.username = uid; st.rerun()
                else: st.error("실패")
    with t2:
        with st.form("signup"):
            nid = st.text_input("새 ID"); npw = st.text_input("새 PW", type="password")
            if st.form_submit_button("가입하기"):
                s, m = register_user(nid, npw)
                if s: st.success(m)
                else: st.error(m)
