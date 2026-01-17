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

# --- 0. 가격 설정 및 스타일 ---
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

# --- 1. 구글 시트 DB (연동 실패 시에도 앱 실행 보장) ---
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

def log_to_sheet(u, a, c):
    sh = get_gs_sh()
    if not sh: return
    try:
        ws = sh.worksheet("Logs")
        now = datetime.datetime.now()
        ws.append_row([now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"), u, a, str(c)])
    except: pass

def fetch_history(u, d):
    sh = get_gs_sh()
    if not sh: return []
    try:
        ws = sh.worksheet("Logs")
        return [{"time":r[1], "action":r[3], "content":r[4]} for r in ws.get_all_values()[1:] if r[0]==d and r[2]==u]
    except: return []

# --- 2. AI 및 유틸리티 ---
openai.api_key = st.secrets.get("OPENAI_API_KEY", "")
genai.configure(api_key=st.secrets.get("GEMINI_API_KEY", ""))

def chat_ai(prompt, ctx, stage):
    try:
        res = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"system","content":f"심리연구조교 다온. 단계:{stage}\n{ctx}"},{"role":"user","content":prompt}])
        return res.choices[0].message.content
    except: return "AI 서비스 일시 중단"

def get_4_opts(p):
    try:
        res = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user","content":f"{p}. 4가지만 명사형으로 짧게 답해."}])
        return [l.strip().lstrip("-1234. ").strip() for l in res.choices[0].message.content.split('\n') if l.strip()][:4]
    except: return ["제안 실패"]

def check_energy(cost):
    if st.session_state.user_energy >= cost:
        st.session_state.user_energy -= cost
        return True
    st.error("에너지가 부족합니다."); return False

# --- 3. 세션 및 상태 초기화 (사라진 대화창 복구의 핵심) ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_energy' not in st.session_state: st.session_state.user_energy = 500
if 'research_context' not in st.session_state:
    st.session_state.research_context = {'topic':'', 'variables_options':[], 'variables':'', 'method_options':[], 'method':'', 'references':''}
if 'paper_sections' not in st.session_state:
    st.session_state.paper_sections = {"서론":"", "이론적 배경":"", "연구 방법":"", "결과":"", "논의":""}
if 'confirm_state' not in st.session_state: st.session_state.confirm_state = {"type": None, "data": None}
# 각 탭별 채팅 기록 초기화
for i in range(6):
    if f'chat_{i}' not in st.session_state: st.session_state[f'chat_{i}'] = []

# --- 4. 렌더링 함수 ---
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
        d = st.date_input("연구 기록")
        if st.button("기록 불러오기"):
            st.session_state.h_logs = fetch_history(u, d.strftime("%Y-%m-%d"))
            st.session_state.h_date = d.strftime("%Y-%m-%d")
        
        if st.button("💾 오늘 기록 저장"):
            log_to_sheet(u, "수동저장", str(st.session_state.research_context))
            st.success("저장 완료!"); time.sleep(0.5); st.rerun()
            
        if u == "zenova90":
            st.error("🔒 관리자")
            st.link_button("📂 시트 열기", "https://docs.google.com/spreadsheets")
        if st.button("로그아웃"): st.session_state.logged_in = False; st.rerun()

    st.title("🎓 MJP Research Lab")
    st.markdown(f"<div class='energy-box'>⚡ Energy: <span class='energy-val'>{st.session_state.user_energy}</span></div>", unsafe_allow_html=True)
    tabs = st.tabs(["💡 토론", "1. 변인", "2. 방법", "3. 검색", "4. 작성", "5. 참고"])

    # 탭별 화면 구성
    with tabs[0]: # 토론
        render_chat(0, "초기 아이디어 단계", "토론")
        
    with tabs[1]: # 변인
        L, R = st.columns([6, 4])
        with L:
            st.subheader("Variables")
            topic = st.text_input("주제", value=st.session_state.research_context['topic'])
            if st.button("🤖 4가지 안 제안 (무료)"):
                st.session_state.research_context['variables_options'] = get_4_opts(f"주제 '{topic}' 변인 구조")
                st.session_state.research_context['topic'] = topic; st.rerun()
            if st.session_state.research_context['variables_options']:
                choice = st.radio("안 선택:", st.session_state.research_context['variables_options'])
                if st.button("적용하기"): st.session_state.confirm_state = {"type":"var", "data":choice}; st.rerun()
            if st.session_state.confirm_state['type'] == "var":
                st.markdown(f"<div class='confirm-box'>💰 {PRICES['var_confirm']}E 차감</div>", unsafe_allow_html=True)
                if st.button("✅ 확정 결제"):
                    if check_energy(PRICES['var_confirm']):
                        st.session_state.research_context['variables'] = st.session_state.confirm_state['data']
                        log_to_sheet(u, "변인확정", st.session_state.confirm_state['data'])
                        st.session_state.confirm_state = {"type":None, "data":None}; st.rerun()
            st.text_area("최종 변인", value=st.session_state.research_context['variables'])
        with R: render_chat(1, f"주제:{topic}\n변인:{st.session_state.research_context['variables']}", "변인")

    with tabs[3]: # 검색 (Gemini)
        L, R = st.columns([6, 4])
        with L:
            st.subheader("Search")
            if st.button(f"🚀 검색 ({PRICES['search']}E)"):
                if check_energy(PRICES['search']):
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    res = model.generate_content(f"주제:{st.session_state.research_context['topic']} 선행연구 요약").text
                    st.session_state.research_context['references'] = res
                    log_to_sheet(u, "검색", res); st.rerun()
            st.text_area("결과", value=st.session_state.research_context['references'], height=300)
        with R: render_chat(3, st.session_state.research_context['references'], "검색")

    with tabs[5]: # 참고 (APA)
        L, R = st.columns([6, 4])
        with L:
            st.subheader("APA")
            if st.button(f"✨ APA 변환 ({PRICES['ref']}E)"):
                if not st.session_state.research_context['references']: st.warning("내용 없음")
                else:
                    if check_energy(PRICES['ref']):
                        res = chat_ai("APA 변환해줘", st.session_state.research_context['references'], "참고")
                        st.markdown(res)
        with R: render_chat(5, st.session_state.research_context['references'], "참고")

if st.session_state.logged_in: main_app()
else:
    st.title("🔐 MJP Research Lab")
    uid = st.text_input("ID"); upw = st.text_input("PW", type="password")
    if st.button("로그인"):
        us = fetch_users()
        if uid in us and us[uid] == upw:
            st.session_state.logged_in = True; st.session_state.username = uid; st.rerun()
        else: st.error("실패")
    if st.button("자율 회원가입"):
        if uid and upw:
            s, m = (True, "✅ 성공") if "success" else (False, "❌") # 간소화
            st.info("회원가입은 관리자에게 문의하거나 시트 연동 후 사용하세요.")
