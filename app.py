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

# --- [인증 정보 고정] 민주님이 주신 키를 직접 적용 ---
GOOGLE_KEY = {
    "type": "service_account",
    "project_id": "mjpp-484616",
    "private_key_id": "275d351b5e7f4c548001fc29d51e259fb1157d55",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDQTYgBOlJofwGj\n6UuPgQBTbmb7CJxTWtZZoNY7ooDXDixgek5QDEL5yflTSomNt9vWyfaccBRR5OcR\nW6ATmXCQ4F8hAwxHinhH7JRWA/rX1TgZFyEQkrT1dd9PlqFz22EgQ9E5hll6IS60\nTePbXfJux0rrTlr7s7NRv/oQM2+mQg/Gf54uCShgfoCcEBOQ67igtJ8dPNpdajsr\nV/SRGZq6h3BjskBAMP1IyPL5uPD1Lq1Z7x4RwJ8n6VlcTZKQAR/9f5AvuKyMpAop\nMaYMREbhjsbIMaBAIIp1fi1qjLPA8bCJSBCGfBoB4qwNYggyGw/YHL71Qw3jO6O0\ngVCWWqiLAgMBAAECggEAGP0UEcGjXTHPSpCUJfT9ywR1iivwRPeiu0HWMXU/K41h\nuXkyp9uwtTKLnHhWpA+oac30rbOsXF6vcZ+iRnejz117TASHlpV/9HDnIqJ7lyTX\nA/uIVeqjlsa7MVsKp1FsB2jbUqFRXptYdPzbFtfgW3XBARV3SLa4DliPcR4aiMEw\nppGRqpaH0SmNaeIiLwH7nF+f6h4e3H2My+HU7Lw/CHRIaGnmaTMPLBgtptdDwBLB\nj5prrkU8xECAIiGUlw+4tLMxSi4sq83HbPtjmJtRSq3L7X4zr0Z08LufOZEJ4Sia\nClBOWBEr8LQZTUzdgnVVL0SQBYhSQwQvre6+qDnkEQKBgQDpp9jALnPWVMzKXEG4\nzSQOc6HVE1iQOL+4eYvl93oVmtIyVjZ/MNpig26X3FGkYehFOHJj2dAAzzdu3uHd\nf0y1QJbGXkyaerIRfVoaLz0q57AFNRyROSEUkG5VhJCY/E1BimX8HNNR0Y16RRzI\ngSnQG/e3fgXdPykrHHAVc69JNQKBgQDkOQUHJrdNPI6oIsaaSbu6HqQR8XgnJu6W\ncgVW3lrz4DwmY+RhbElfV0AelQFcngD/RT2UwAST4NOjKMUId6eYYC1MaS1UPHTD\notQTc02CzlUQyabEN7Sgclx+tK2EyFazzR4aIaYL69JchdbWmqSLlYji7a/xsCum\nso8HuLIivwKBgQDbO/YQPIXL8T1GElJIR5MxTCXoe4J5sAWT3df6Kr6OTvoy6Nmx\ndfEyxgeazcp85rC9Yj1Smyij2co1aUOcRLmAx92wuwI9YCp8ZWIRBKskz+BY1gu\nmuADH5GnA/94zCLhAC6444MUHf8VXounRiopblR8Au8VrRG/taslNaqekQKBgQDP\nA+XKqdTFi7O/UeQimdVeK2MaH5WktgzfjMfJF2MbKoCFNkE4GdioUeWImBKnJ2+y\nHeWRI2hDl0GCE34+gwMUFdGhKRqD+V7VAsMqbYGWsIC6/J94ByuiCnpaOJvZATyc\nVegDPhh3Yc7sPD83ZQjy0I5dgcsCCZJe4EMbdu6m0wKBgG+wYQQ6i47vSxuYcZN2\nd8fj8Skcu6EWXoq439qohiejHWE1Ha6ZozLA9XwjcEzazQtMoPa3KCKX+gHPym7a\nGg0dN5OHbNeQw0rvQa2zWDvDm0ayAZTD85Hs75NDtDBrxwlpOkNDoo0wRYMVNR64\nH+UbKmzlu9/8UqSX5nPQ+N81\n-----END PRIVATE KEY-----\n",
    "client_email": "zenova90@mjpp-484616.iam.gserviceaccount.com"
}
OAI_KEY = "sk-BlK4mW6E94FMuMgClvjiHrtmPuAA4HbYSq7fvXrQR4yA76lJrJGV7YB1JUFh40MWUIle0A"
GMN_KEY = "AIzaSyCbnrz_5j2nAgEXWvyNTM-R_36RmFN_kf8"

# --- 0. 가격표 및 스타일 ---
PRICES = { "chat_step0": 10, "var_confirm": 25, "method_confirm": 30, "search": 30, "draft": 100, "ref": 30, "side_chat": 5 }
st.set_page_config(page_title="MJP Research Lab", layout="wide")
st.markdown("""<style>
    div.stButton > button:first-child { background-color: #2c3e50; color: white; border-radius: 6px; border: none; font-weight: 600;}
    .energy-box { padding: 12px 20px; background-color: #f8f9fa; border-left: 5px solid #2c3e50; border-radius: 4px; display: flex; align-items: center; gap: 15px; margin-bottom: 25px; }
    .energy-val { font-size: 22px; font-weight: bold; color: #2c3e50; font-family: monospace; }
    .confirm-box { padding: 15px; border: 2px solid #e74c3c; background-color: #fdedec; border-radius: 8px; margin: 10px 0; text-align: center; }
</style>""", unsafe_allow_html=True)

# --- 1. DB 함수 ---
def get_gs_sh():
    try:
        gc = gspread.service_account_from_dict(GOOGLE_KEY)
        return gc.open("MJP 연구실 관리대장")
    except: return None

def fetch_users():
    u = {"zenova90": "0931285asd*"}
    sh = get_gs_sh()
    if not sh: return u
    try:
        ws = sh.worksheet("Users")
        for r in ws.get_all_values()[1:]:
            if len(r) >= 3: u[r[1]] = r[2]
        return u
    except: return u

def register_user(nid, npw):
    sh = get_gs_sh()
    if not sh: return False, "DB 연동 오류"
    if nid in fetch_users(): return False, "❌ 이미 존재하는 ID"
    try:
        ws = sh.worksheet("Users")
        ws.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), nid, npw])
        return True, "✅ 가입 성공!"
    except: return False, "가입 실패"

def log_to_sheet(u, a, c):
    sh = get_gs_sh()
    if not sh: return
    try:
        ws = sh.worksheet("Logs")
        ws.append_row([datetime.datetime.now().strftime("%Y-%m-%d"), datetime.datetime.now().strftime("%H:%M:%S"), u, a, str(c)])
    except: pass

def fetch_logs(u, d):
    sh = get_gs_sh()
    if not sh: return []
    try:
        ws = sh.worksheet("Logs")
        return [{"time": r[1], "action": r[3], "content": r[4]} for r in ws.get_all_values()[1:] if r[0]==d and r[2]==u]
    except: return []

# --- 2. AI 기능 ---
def chat_ai(prompt, ctx, stage):
    try:
        client = openai.OpenAI(api_key=OAI_KEY)
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"system","content":f"심리연구조교 다온. 단계:{stage}\n{ctx}"},{"role":"user","content":prompt}])
        return res.choices[0].message.content
    except Exception as e: return f"오류: {e}"

def get_4_opts(p):
    try:
        client = openai.OpenAI(api_key=OAI_KEY)
        res = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user","content":f"{p}. 4가지만 명사형으로 간결하게 답해."}])
        return [l.strip().lstrip("-1234. ").strip() for l in res.choices[0].message.content.split('\n') if l.strip()][:4]
    except: return ["생성 실패"]

def check_energy(cost):
    if st.session_state.user_energy >= cost:
        st.session_state.user_energy -= cost
        return True
    st.error("에너지가 부족합니다."); return False

# --- 3. 세션 초기화 ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_energy' not in st.session_state: st.session_state.user_energy = 500
if 'research_context' not in st.session_state: st.session_state.research_context = {'topic':'', 'variables_options':[], 'variables':'', 'method_options':[], 'method':'', 'references':''}
if 'paper_sections' not in st.session_state: st.session_state.paper_sections = {"서론":"", "이론적 배경":"", "연구 방법":"", "결과":"", "논의":""}
if 'confirm_state' not in st.session_state: st.session_state.confirm_state = {"type": None, "data": None}
for i in range(6):
    if f'chat_{i}' not in st.session_state: st.session_state[f'chat_{i}'] = []

# --- 4. 렌더링 함수 (NameError 수정됨) ---
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
        st.markdown("---")
        st.subheader("📅 연구 기록")
        d = st.date_input("날짜 선택")
        if st.button("기록 불러오기"):
            st.session_state['fetched_logs'] = fetch_logs(u, d.strftime("%Y-%m-%d"))
            st.session_state['fetched_date'] = d.strftime("%Y-%m-%d")
        if st.button("💾 오늘의 기록 저장"):
            log_to_sheet(u, "수동저장", str(st.session_state.research_context))
            st.success("저장 완료!"); time.sleep(0.5); st.rerun()
        with st.expander("⚡ 에너지 충전소"):
            st.write("기업은행 010-2989-0076 (양민주)")
            if st.text_input("쿠폰") == "TEST-1000" and st.button("충전"):
                st.session_state.user_energy += 1000; log_to_sheet(u, "충전", "1000E"); st.rerun()
        if u == "zenova90":
            st.link_button("📂 시트 열기", "https://docs.google.com/spreadsheets")
        if st.button("로그아웃"): st.session_state.logged_in = False; st.rerun()

    st.title("🎓 MJP Research Lab")
    st.markdown(f"<div class='energy-box'>⚡ Energy: <span class='energy-val'>{st.session_state.user_energy}</span></div>", unsafe_allow_html=True)
    tabs = st.tabs(["💡 토론", "1. 변인", "2. 방법", "3. 검색", "4. 작성", "5. 참고"])

    with tabs[0]: render_chat(0, "토론 단계", "토론")
    with tabs[1]:
        L, R = st.columns([6, 4])
        with L:
            st.subheader("Variables")
            topic = st.text_input("연구 주제", value=st.session_state.research_context['topic'])
            if st.button("🤖 4가지 안 제안 (무료)"):
                st.session_state.research_context['variables_options'] = get_4_opts(f"주제 '{topic}' 변인 구조")
                st.session_state.research_context['topic'] = topic; st.rerun()
            if st.session_state.research_context['variables_options']:
                c = st.radio("선택:", st.session_state.research_context['variables_options'])
                if st.button("적용하기"): st.session_state.confirm_state = {"type":"var", "data":c}; st.rerun()
            if st.session_state.confirm_state['type'] == "var":
                st.markdown(f"<div class='confirm-box'>💰 {PRICES['var_confirm']}E 차감</div>", unsafe_allow_html=True)
                if st.button("✅ 확정 결제"):
                    if check_energy(PRICES['var_confirm']):
                        st.session_state.research_context['variables'] = st.session_state.confirm_state['data']
                        log_to_sheet(u, "변인확정", st.session_state.confirm_state['data'])
                        st.session_state.confirm_state = {"type":None, "data":None}; st.rerun()
            st.text_area("최종 변인", value=st.session_state.research_context['variables'], height=150)
        with R: render_chat(1, st.session_state.research_context['variables'], "변인")

    with tabs[2]:
        L, R = st.columns([6, 4])
        with L:
            st.subheader("Methodology")
            if st.button("🤖 4가지 방법 제안 (무료)", key="m_free"):
                st.session_state.research_context['method_options'] = get_4_opts(f"변인 '{st.session_state.research_context['variables']}' 연구방법")
                st.rerun()
            if st.session_state.research_context['method_options']:
                c = st.radio("선택:", st.session_state.research_context['method_options'])
                if st.button("적용하기", key="m_app"): st.session_state.confirm_state = {"type":"method", "data":c}; st.rerun()
            if st.session_state.confirm_state['type'] == "method":
                st.markdown(f"<div class='confirm-box'>💰 {PRICES['method_confirm']}E 차감</div>", unsafe_allow_html=True)
                if st.button("✅ 확정 결제", key="m_pay"):
                    if check_energy(PRICES['method_confirm']):
                        st.session_state.research_context['method'] = st.session_state.confirm_state['data']
                        log_to_sheet(u, "방법확정", st.session_state.confirm_state['data'])
                        st.session_state.confirm_state = {"type":None, "data":None}; st.rerun()
            st.text_area("최종 방법", value=st.session_state.research_context['method'], height=150)
        with R: render_chat(2, st.session_state.research_context['method'], "방법")

    with tabs[3]:
        L, R = st.columns([6, 4])
        with L:
            st.subheader("Search")
            if st.button(f"🚀 검색 ({PRICES['search']}E)"):
                if check_energy(PRICES['search']):
                    genai.configure(api_key=GMN_KEY)
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    res = model.generate_content(f"주제:{st.session_state.research_context['topic']} 선행연구 요약").text
                    st.session_state.research_context['references'] = res
                    log_to_sheet(u, "검색", res); st.rerun()
            st.text_area("결과", value=st.session_state.research_context['references'], height=400)
        with R: render_chat(3, st.session_state.research_context['references'], "검색")

    with tabs[4]:
        L, R = st.columns([6, 4])
        with L:
            st.subheader("Drafting")
            sec = st.selectbox("챕터", list(st.session_state.paper_sections.keys()))
            if st.button("🤖 AI 초안 작성"): st.session_state.confirm_state = {"type":"draft", "data":sec}; st.rerun()
            if st.session_state.confirm_state['type'] == "draft":
                st.markdown(f"<div class='confirm-box'>💰 {PRICES['draft']}E 차감</div>", unsafe_allow_html=True)
                if st.button("✅ 작성 시작"):
                    if check_energy(PRICES['draft']):
                        st.session_state.confirm_state = {"type":None, "data":None}
                        draft = chat_ai(f"'{sec}' 작성해줘", str(st.session_state.research_context), "작성")
                        st.session_state.paper_sections[sec] = draft
                        log_to_sheet(u, f"작성({sec})", draft); st.rerun()
            st.text_area("에디터", value=st.session_state.paper_sections[sec], height=400)
        with R: render_chat(4, st.session_state.paper_sections[sec], "작성")

    with tabs[5]:
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
    t1, t2 = st.tabs(["로그인", "회원가입"])
    with t1:
        with st.form("login_f"):
            uid = st.text_input("ID"); upw = st.text_input("PW", type="password")
            if st.form_submit_button("로그인"):
                us = fetch_users()
                if uid in us and us[uid] == upw:
                    st.session_state.logged_in = True; st.session_state.username = uid; st.rerun()
                else: st.error("정보 불일치")
    with t2:
        with st.form("signup_f"):
            nid = st.text_input("새 ID"); npw = st.text_input("새 PW", type="password")
            if st.form_submit_button("가입하기"):
                s, m = register_user(nid, npw)
                if s: st.success(m)
                else: st.error(m)
