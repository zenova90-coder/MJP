import streamlit as st
import openai
import google.generativeai as genai
import gspread
import datetime
import os
import time

# --- 0. 스타일 및 가격표 ---
PRICES = { "chat_step0": 10, "var_confirm": 25, "method_confirm": 30, "search": 30, "draft": 100, "ref": 30, "side_chat": 5 }
st.set_page_config(page_title="MJP Research Lab", layout="wide")

# --- 1. 인증 정보 ---
OAI_KEY = st.secrets.get("OPENAI_API_KEY", "")
GMN_KEY = st.secrets.get("GEMINI_API_KEY", "")
ACCESS_CODES = ["2026", "1234"]

# --- 2. DB 및 유틸리티 함수 ---
def get_gs_sh():
    try:
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
    if not sh: return False, "DB 연동 오류"
    if nid in fetch_users(): return False, "이미 존재하는 ID"
    try:
        ws = sh.worksheet("Users")
        ws.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), nid, npw])
        return True, "✅ 가입 성공! 로그인 하세요."
    except: return False, "가입 실패"

def log_to_sheet(u, a, c):
    sh = get_gs_sh()
    if not sh: return
    try:
        ws = sh.worksheet("Logs")
        ws.append_row([datetime.datetime.now().strftime("%Y-%m-%d"), datetime.datetime.now().strftime("%H:%M:%S"), u, a, str(c)])
    except: pass

def chat_ai(prompt, ctx, stage):
    try:
        client = openai.OpenAI(api_key=OAI_KEY)
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"system","content":f"심리연구조교 다온. 단계:{stage}\n{ctx}"},{"role":"user","content":prompt}])
        return res.choices[0].message.content
    except Exception as e: return f"AI 오류: {e}"

# --- 3. 세션 초기화 (사이드바 및 대화창 유지의 핵심) ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_energy' not in st.session_state: st.session_state.user_energy = 500
if 'research_context' not in st.session_state:
    st.session_state.research_context = {'topic':'', 'variables_options':[], 'variables':'', 'method_options':[], 'method':'', 'references':''}
if 'confirm_state' not in st.session_state: st.session_state.confirm_state = {"type": None, "data": None}
for i in range(6):
    if f'chat_{i}' not in st.session_state: st.session_state[f'chat_{i}'] = []

# --- 4. 렌더링 함수 ---
def render_chat(idx, ctx_data, stage):
    st.markdown(f"###### 💬 AI 다온 ({stage})")
    ckey = f'chat_{idx}'
    for m in st.session_state[ckey]:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    if p := st.chat_input(f"질문 (5E)", key=f"input_{idx}"):
        if st.session_state.user_energy >= 5:
            st.session_state.user_energy -= 5
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
        st.markdown("---")
        if st.button("💾 오늘의 기록 저장"):
            log_to_sheet(u, "수동저장", str(st.session_state.research_context))
            st.success("저장 완료!")
        with st.expander("⚡ 에너지 충전소"):
            st.write("기업은행 010-2989-0076 (양민주)")
            code = st.text_input("충전 코드")
            if code in ACCESS_CODES and st.button("충전"):
                st.session_state.user_energy += 1000; st.success("완료!"); st.rerun()
        if st.button("로그아웃"): st.session_state.logged_in = False; st.rerun()

    st.title("🎓 MJP Research Lab")
    st.markdown(f"⚡ 에너지: **{st.session_state.user_energy}**")
    tabs = st.tabs(["💡 토론", "1. 변인", "2. 방법", "3. 검색", "4. 작성", "5. 참고"])

    with tabs[0]: render_chat(0, "초기 아이디어", "토론")
    with tabs[1]:
        L, R = st.columns([6, 4])
        with L:
            st.subheader("Variables")
            topic = st.text_input("연구 주제", value=st.session_state.research_context['topic'])
            if st.button("🤖 4가지 안 제안 (무료)"):
                st.session_state.research_context['variables_options'] = chat_ai(f"주제 '{topic}'에 맞는 변인 4가지를 명사형으로만 알려줘", "", "제안")
                st.session_state.research_context['topic'] = topic; st.rerun()
            st.write(st.session_state.research_context['variables_options'])
            st.text_area("최종 변인", value=st.session_state.research_context['variables'], height=150)
        with R: render_chat(1, st.session_state.research_context['variables'], "변인")

if st.session_state.logged_in: main_app()
else:
    st.title("🔐 MJP Research Lab")
    t1, t2 = st.tabs(["로그인", "회원가입"])
    with t1:
        with st.form("l_f"):
            uid = st.text_input("ID"); upw = st.text_input("PW", type="password")
            if st.form_submit_button("로그인"):
                users = fetch_users()
                if uid in users and users[uid] == upw:
                    st.session_state.logged_in = True; st.session_state.username = uid; st.rerun()
                else: st.error("실패")
    with t2:
        with st.form("s_f"):
            nid = st.text_input("새 ID"); npw = st.text_input("새 PW", type="password")
            if st.form_submit_button("가입하기"):
                s, m = register_user(nid, npw)
                if s: st.success(m)
                else: st.error(m)
