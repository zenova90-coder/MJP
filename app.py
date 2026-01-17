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
# 0. 가격표 및 스타일
# -----------------------------------------------------------
PRICES = {
    "chat_step0": 10, "var_confirm": 25, "method_confirm": 30,
    "search": 30, "draft": 100, "ref": 30, "side_chat": 5
}

st.set_page_config(page_title="MJP Research Lab", layout="wide")
st.markdown("""<style>
    div.stButton > button:first-child { background-color: #2c3e50; color: white; border-radius: 6px; border: none; font-weight: 600;}
    div.stButton > button:first-child:hover { background-color: #1a252f; }
    .energy-box { padding: 12px 20px; background-color: #f8f9fa; border-left: 5px solid #2c3e50; border-radius: 4px; display: flex; align-items: center; gap: 15px; margin-bottom: 25px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .energy-val { font-size: 22px; font-weight: bold; color: #2c3e50; font-family: monospace; }
    .confirm-box { padding: 15px; border: 2px solid #e74c3c; background-color: #fdedec; border-radius: 8px; margin-top: 10px; margin-bottom: 10px; text-align: center; }
</style>""", unsafe_allow_html=True)

# -----------------------------------------------------------
# 1. DB & 로그 (구글 시트 연동)
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
    # [민주님 요청] 관리자 아이디/비번 고정
    admin_data = {"zenova90": "0931285asd*"}
    if not sh: return admin_data
    try:
        ws = sh.worksheet("Users")
        records = ws.get_all_values()
        for row in records[1:]:
            if len(row) >= 3: admin_data[row[1]] = row[2]
        return admin_data
    except: return admin_data

def register_user_to_sheet(new_id, new_pw):
    sh = get_google_sheet_connection()
    if not sh: return False, "DB 연동 오류 (Secrets 설정을 확인하세요)"
    users = fetch_users_from_sheet()
    if new_id in users: return False, "❌ 이미 존재하는 ID입니다."
    try:
        ws = sh.worksheet("Users")
        ws.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), new_id, new_pw])
        return True, "✅ 가입 성공! 로그인 하세요."
    except Exception as e: return False, f"오류: {e}"

def log_to_sheet(username, action, content):
    sh = get_google_sheet_connection()
    if not sh: return
    try:
        ws = sh.worksheet("Logs")
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws.append_row([datetime.datetime.now().strftime("%Y-%m-%d"), ts, username, action, content])
    except: pass

def fetch_logs_by_date(username, date_str):
    sh = get_google_sheet_connection()
    if not sh: return []
    try:
        ws = sh.worksheet("Logs")
        rows = ws.get_all_values()
        return [{"time": r[1], "action": r[3], "content": r[4]} for r in rows[1:] if r[0]==date_str and r[2]==username]
    except: return []

# -----------------------------------------------------------
# 2. 유틸리티 & AI
# -----------------------------------------------------------
def create_word_report(username, date, logs):
    doc = Document()
    doc.add_heading(f'{username} 연구일지 ({date})', 0)
    for l in logs:
        doc.add_heading(f"[{l['time']}] {l['action']}", level=2)
        doc.add_paragraph(l['content'])
    buf = BytesIO(); doc.save(buf); buf.seek(0)
    return buf

def check_and_deduct(cost):
    if st.session_state['user_energy'] >= cost:
        st.session_state['user_energy'] -= cost
        return True
    st.error(f"에너지가 부족합니다. (필요: {cost})"); return False

openai.api_key = st.secrets.get("OPENAI_API_KEY", "")
genai.configure(api_key=st.secrets.get("GEMINI_API_KEY", ""))

def chat_with_context(prompt, ctx, stage):
    try:
        res = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"system","content":f"심리연구조교 '다온'. 단계:{stage}\n{ctx}"},{"role":"user","content":prompt}])
        return res.choices[0].message.content
    except: return "AI 오류"

def get_4_options(prompt):
    try:
        res = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user","content":f"{prompt}. 4가지만 명사형으로 간결하게 답해줘."}])
        lines = [l.strip().lstrip("-1234. ").strip() for l in res.choices[0].message.content.split('\n') if l.strip()]
        return lines[:4]
    except: return ["제안 실패"]

# -----------------------------------------------------------
# 3. 앱 로직
# -----------------------------------------------------------
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'user_energy' not in st.session_state: st.session_state['user_energy'] = 500
if 'research_context' not in st.session_state:
    st.session_state['research_context'] = {'topic':'', 'variables_options':[], 'variables':'', 'method_options':[], 'method':'', 'references':''}
if 'paper_sections' not in st.session_state:
    st.session_state['paper_sections'] = {"서론":"", "이론적 배경":"", "연구 방법":"", "결과":"", "논의":""}
if 'confirm_state' not in st.session_state: st.session_state['confirm_state'] = {"type": None, "data": None}

def main_app():
    user = st.session_state['username']
    with st.sidebar:
        st.header(f"👤 {user}님")
        d = st.date_input("기록 선택")
        if st.button("불러오기"):
            st.session_state['fetched_logs'] = fetch_logs_by_date(user, d.strftime("%Y-%m-%d"))
            st.session_state['fetched_date'] = d.strftime("%Y-%m-%d")
        if st.session_state.get('fetched_logs'):
            st.download_button("📄 워드 다운로드", create_word_report(user, st.session_state['fetched_date'], st.session_state['fetched_logs']), f"Log_{st.session_state['fetched_date']}.docx")
        
        st.markdown("---")
        if st.button("💾 오늘의 기록 저장"):
            log_to_sheet(user, "수동저장", str(st.session_state['research_context']))
            st.success("저장 완료!"); time.sleep(0.5); st.rerun()

        # [민주님 요청] 관리자 버튼
        if user == "zenova90":
            st.markdown("---")
            st.error("🔒 관리자")
            st.link_button("📂 구글 시트 열기", "https://docs.google.com/spreadsheets")
        
        if st.button("로그아웃"): st.session_state['logged_in'] = False; st.rerun()

    st.title("🎓 MJP Research Lab")
    st.markdown(f"<div class='energy-box'><span>⚡ Energy:</span><span class='energy-val'>{st.session_state['user_energy']}</span></div>", unsafe_allow_html=True)
    tabs = st.tabs(["💡 토론", "1. 변인", "2. 방법", "3. 검색", "4. 작성", "5. 참고", "📜 로그"])

    # [1. 변인 탭]
    with tabs[1]:
        cL, cR = st.columns([6, 4])
        with cL:
            st.subheader("Variables")
            topic = st.text_input("연구 주제", value=st.session_state['research_context']['topic'])
            if st.button("🤖 4가지 안 제안 (무료)"):
                with st.spinner("생성 중..."):
                    st.session_state['research_context']['variables_options'] = get_4_options(f"주제 '{topic}' 변인 구조 4가지")
                    st.session_state['research_context']['topic'] = topic; st.rerun()
            if st.session_state['research_context']['variables_options']:
                choice = st.radio("선택:", st.session_state['research_context']['variables_options'])
                if st.button("적용하기"): st.session_state['confirm_state'] = {"type": "var", "data": choice}; st.rerun()
            if st.session_state['confirm_state']['type'] == "var":
                st.markdown(f"<div class='confirm_box'><h4>💰 {PRICES['var_confirm']}E 차감</h4></div>", unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                if c1.button("✅ 확정"):
                    if check_and_deduct(PRICES['var_confirm']):
                        st.session_state['research_context']['variables'] = st.session_state['confirm_state']['data']
                        log_to_sheet(user, "변인확정", st.session_state['confirm_state']['data'])
                        st.session_state['confirm_state'] = {"type": None, "data": None}; st.rerun()
                if c2.button("❌ 취소"): st.session_state['confirm_state'] = {"type": None, "data": None}; st.rerun()
            st.text_area("최종 변인", value=st.session_state['research_context']['variables'])
        with cR: # AI 조교 채팅 (생략된 탭들도 동일 로직)
            st.write("조교 대화 생략...")

    # [5. 참고 탭 - 경제적 차감 로직 적용]
    with tabs[5]:
        cost = PRICES['ref']
        if st.button(f"✨ APA 변환 ({cost}E)"):
            if not st.session_state['research_context']['references']:
                st.warning("⚠️ 참고문헌 내용이 없습니다. 먼저 검색을 완료하세요.")
            else:
                if check_and_deduct(cost):
                    res = chat_with_context("APA 스타일로 변환해줘", st.session_state['research_context']['references'], "참고문헌")
                    st.markdown(res)

if st.session_state['logged_in']: main_app()
else:
    st.title("🔐 MJP Research Lab")
    t1, t2 = st.tabs(["로그인", "회원가입"])
    with t1:
        with st.form("login"):
            uid = st.text_input("아이디"); upw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("로그인"):
                users = fetch_users_from_sheet()
                if uid in users and users[uid] == upw:
                    st.session_state['logged_in'] = True; st.session_state['username'] = uid; st.rerun()
                else: st.error("로그인 실패")
    with t2:
        with st.form("signup"):
            nid = st.text_input("새 아이디"); npw = st.text_input("새 비밀번호", type="password")
            if st.form_submit_button("가입하기"):
                s, m = register_user_to_sheet(nid, npw)
                if s: st.success(m)
                else: st.error(m)
