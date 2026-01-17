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
    .energy-box { padding: 12px 20px; background-color: #f8f9fa; border-left: 5px solid #2c3e50; border-radius: 4px; display: flex; align-items: center; gap: 15px; margin-bottom: 25px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .energy-val { font-size: 22px; font-weight: bold; color: #2c3e50; font-family: monospace; }
    .confirm-box { padding: 15px; border: 2px solid #e74c3c; background-color: #fdedec; border-radius: 8px; margin: 10px 0; text-align: center; }
</style>""", unsafe_allow_html=True)

# --- 1. 구글 시트 DB 함수 (안전장치 강화) ---
@st.cache_resource
def get_google_sheet():
    try:
        if "gcp_service_account" not in st.secrets: return None
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        return gc.open("MJP 연구실 관리대장")
    except: return None

def fetch_users():
    admin_data = {"zenova90": "0931285asd*"} # 관리자 계정 고정
    sh = get_google_sheet()
    if not sh: return admin_data
    try:
        ws = sh.worksheet("Users")
        for row in ws.get_all_values()[1:]:
            if len(row) >= 3: admin_data[row[1]] = row[2]
        return admin_data
    except: return admin_data

def register_user(nid, npw):
    sh = get_google_sheet()
    if not sh: return False, "DB 연결 오류 (Secrets 설정 확인)"
    users = fetch_users()
    if nid in users: return False, "❌ 이미 존재하는 ID입니다."
    try:
        ws = sh.worksheet("Users")
        ws.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), nid, npw])
        return True, "✅ 가입 성공! 로그인 하세요."
    except Exception as e: return False, f"오류: {e}"

def log_to_sheet(user, action, content):
    sh = get_google_sheet()
    if not sh: return
    try:
        ws = sh.worksheet("Logs")
        now = datetime.datetime.now()
        ws.append_row([now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), user, action, content])
    except: pass

def fetch_logs(user, date_str):
    sh = get_google_sheet()
    if not sh: return []
    try:
        ws = sh.worksheet("Logs")
        rows = ws.get_all_values()
        return [{"time": r[1], "action": r[3], "content": r[4]} for r in rows[1:] if r[0]==date_str and r[2]==user]
    except: return []

# --- 2. AI 및 유틸리티 ---
openai.api_key = st.secrets.get("OPENAI_API_KEY", "")
genai.configure(api_key=st.secrets.get("GEMINI_API_KEY", ""))

def chat_with_context(prompt, ctx, stage):
    try:
        res = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"system","content":f"심리연구조교 '다온'. 단계:{stage}\n{ctx}"},{"role":"user","content":prompt}])
        return res.choices[0].message.content
    except: return "AI 호출 오류"

def get_4_options(prompt):
    try:
        res = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user","content":f"{prompt}. 4가지만 명사형으로 간결하게 답해줘. 설명 금지."}])
        lines = [l.strip().lstrip("-1234. ").strip() for l in res.choices[0].message.content.split('\n') if l.strip()]
        return lines[:4]
    except: return ["제안 실패"]

def check_and_deduct(cost):
    if st.session_state['user_energy'] >= cost:
        st.session_state['user_energy'] -= cost
        return True
    st.error("에너지가 부족합니다."); return False

# --- 3. 세션 초기화 (NameError 방지) ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_energy' not in st.session_state: st.session_state['user_energy'] = 500
if 'research_context' not in st.session_state:
    st.session_state['research_context'] = {'topic':'', 'variables_options':[], 'variables':'', 'method_options':[], 'method':'', 'references':''}
if 'paper_sections' not in st.session_state:
    st.session_state['paper_sections'] = {"서론":"", "이론적 배경":"", "연구 방법":"", "결과":"", "논의":""}
if 'confirm_state' not in st.session_state: st.session_state['confirm_state'] = {"type": None, "data": None}
for k in ["chat_0", "chat_1", "chat_2", "chat_3", "chat_4", "chat_5"]:
    if k not in st.session_state: st.session_state[k] = []

# --- 4. 화면 구성 함수 ---
def render_right_chat(key_suffix, context_data, stage_name):
    st.markdown(f"###### 💬 AI 조교 ({stage_name})")
    cost = PRICES["side_chat"]
    chat_key = f"chat_{key_suffix}"
    for msg in st.session_state[chat_key]:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    if p := st.chat_input(f"질문 (비용: {cost}E)", key=f"in_{key_suffix}"):
        if check_and_deduct(cost):
            st.session_state[chat_key].append({"role":"user", "content":p})
            log_to_sheet(st.session_state['username'], f"질문({stage_name})", p)
            with st.chat_message("user"): st.markdown(p)
            ans = chat_with_context(p, context_data, stage_name)
            st.session_state[chat_key].append({"role":"assistant", "content":ans})
            log_to_sheet(st.session_state['username'], f"답변({stage_name})", ans)
            st.rerun()

def main_app():
    user = st.session_state['username']
    with st.sidebar:
        st.header(f"👤 {user}님")
        d = st.date_input("연구 기록 날짜")
        if st.button("기록 불러오기"):
            st.session_state['fetched_logs'] = fetch_logs(user, d.strftime("%Y-%m-%d"))
            st.session_state['fetched_date'] = d.strftime("%Y-%m-%d")
        
        st.markdown("---")
        if st.button("💾 오늘의 기록 저장"):
            log_to_sheet(user, "수동저장", str(st.session_state['research_context']))
            st.success("저장 완료!"); time.sleep(0.5); st.rerun()
        
        if user == "zenova90":
            st.markdown("---")
            st.error("🔒 관리자 전용")
            st.link_button("📂 관리자 시트 열기", "https://docs.google.com/spreadsheets")
        
        if st.button("로그아웃"): st.session_state['logged_in'] = False; st.rerun()

    st.title("🎓 MJP Research Lab")
    st.markdown(f"<div class='energy-box'>⚡ Energy: <span class='energy-val'>{st.session_state['user_energy']}</span></div>", unsafe_allow_html=True)
    tabs = st.tabs(["💡 토론", "1. 변인", "2. 방법", "3. 검색", "4. 작성", "5. 참고", "📜 로그"])

    with tabs[1]: # 변인 단계
        cL, cR = st.columns([6, 4])
        with cL:
            st.subheader("Variables")
            topic = st.text_input("연구 주제", value=st.session_state['research_context']['topic'])
            if st.button("🤖 4가지 안 제안 (무료)", key="btn_v_free"):
                with st.spinner("제안 생성 중..."):
                    st.session_state['research_context']['variables_options'] = get_4_options(f"주제 '{topic}' 변인 구조")
                    st.session_state['research_context']['topic'] = topic; st.rerun()
            if st.session_state['research_context']['variables_options']:
                choice = st.radio("안 선택:", st.session_state['research_context']['variables_options'])
                if st.button("적용하기"): st.session_state['confirm_state'] = {"type":"var", "data":choice}; st.rerun()
            if st.session_state['confirm_state']['type'] == "var":
                st.markdown(f"<div class='confirm_box'>💰 {PRICES['var_confirm']}E 차감됩니다.</div>", unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                if c1.button("✅ 최종 확정"):
                    if check_and_deduct(PRICES['var_confirm']):
                        st.session_state['research_context']['variables'] = st.session_state['confirm_state']['data']
                        log_to_sheet(user, "변인확정", st.session_state['confirm_state']['data'])
                        st.session_state['confirm_state'] = {"type":None, "data":None}; st.rerun()
                if c2.button("❌ 취소"): st.session_state['confirm_state'] = {"type":None, "data":None}; st.rerun()
            st.text_area("최종 변인", value=st.session_state['research_context']['variables'], height=150)
        with cR: render_right_chat("1", f"주제:{topic}\n변인:{st.session_state['research_context']['variables']}", "변인")

    with tabs[5]: # 참고문헌 (APA)
        cL, cR = st.columns([6, 4])
        with cL:
            st.subheader("References")
            cost = PRICES['ref']
            if st.button(f"✨ APA 변환 ({cost}E)"):
                if not st.session_state['research_context']['references']:
                    st.warning("⚠️ 참고문헌 데이터가 없습니다. 먼저 검색을 완료하세요.")
                else:
                    if check_and_deduct(cost):
                        res = chat_with_context("APA 스타일로 변환해줘", st.session_state['research_context']['references'], "참고문헌")
                        st.markdown(res)
        with cR: render_right_chat("5", st.session_state['research_context']['references'], "참고")

if st.session_state['logged_in']: main_app()
else:
    st.title("🔐 MJP Research Lab")
    t1, t2 = st.tabs(["로그인", "회원가입"])
    with t1:
        with st.form("login"):
            uid = st.text_input("아이디"); upw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("로그인"):
                users = fetch_users()
                if uid in users and users[uid] == upw:
                    st.session_state['logged_in'] = True; st.session_state['username'] = uid; st.rerun()
                else: st.error("로그인 실패")
    with t2:
        with st.form("signup"):
            nid = st.text_input("희망 아이디"); npw = st.text_input("희망 비밀번호", type="password")
            if st.form_submit_button("가입하기"):
                s, m = register_user(nid, npw)
                if s: st.success(m)
                else: st.error(m)
