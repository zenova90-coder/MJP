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
# 1. 스타일 & 기본 설정
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
# 2. 구글 시트 DB 연결 (핵심: 영구 저장소)
# -----------------------------------------------------------
@st.cache_resource
def get_google_sheet_connection():
    """구글 시트 연결 객체 리턴 (캐싱으로 속도 향상)"""
    try:
        if "gcp_service_account" not in st.secrets: return None
        gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        sh = gc.open("MJP 연구실 관리대장") # 시트 이름 정확해야 함
        return sh
    except Exception as e:
        print(f"Sheet Connect Error: {e}")
        return None

def fetch_users_from_sheet():
    """구글 시트 'Users' 탭에서 회원 명부 가져오기"""
    sh = get_google_sheet_connection()
    if not sh: return {"zenova90": "0931285asd*"} # 연결 실패 시 기본 관리자만
    try:
        ws = sh.worksheet("Users")
        # A열(ID), B열(PW) 읽기 (헤더 제외하고 읽기 위해 2행부터)
        records = ws.get_all_values()
        user_dict = {}
        for row in records[1:]: # 첫줄 헤더 건너뜀
            if len(row) >= 2:
                user_dict[row[1]] = row[2] # B열: ID, C열: PW (구조에 따라 조정 필요, 여기선 A:날짜, B:ID, C:PW 가정)
        
        # 관리자 강제 추가 (혹시 시트에 없더라도 작동하게)
        user_dict["zenova90"] = "0931285asd*"
        return user_dict
    except:
        return {"zenova90": "0931285asd*"}

def register_user_to_sheet(new_id, new_pw):
    """구글 시트 'Users' 탭에 신규 회원 추가"""
    sh = get_google_sheet_connection()
    if not sh: return False, "구글 시트 연동 오류 (관리자 문의)"
    
    # 중복 체크
    current_users = fetch_users_from_sheet()
    if new_id in current_users:
        return False, "❌ 이미 존재하는 아이디입니다."
    
    try:
        ws = sh.worksheet("Users")
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws.append_row([ts, new_id, new_pw]) # 날짜, ID, PW 순서
        return True, "✅ 회원가입 완료! 로그인해주세요."
    except Exception as e:
        return False, f"가입 실패: {e}"

def log_to_sheet(username, action, content):
    """구글 시트 'Logs' 탭에 활동 기록 (영구 저장)"""
    sh = get_google_sheet_connection()
    if not sh: return
    try:
        ws = sh.worksheet("Logs")
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 날짜(YYYY-MM-DD), 시간, ID, 액션, 내용
        date_only = datetime.datetime.now().strftime("%Y-%m-%d")
        ws.append_row([date_only, ts, username, action, content])
    except: pass

def fetch_logs_by_date(username, target_date_str):
    """특정 날짜의 로그를 구글 시트에서 가져오기"""
    sh = get_google_sheet_connection()
    if not sh: return []
    try:
        ws = sh.worksheet("Logs")
        rows = ws.get_all_values()
        # 헤더: Date, Time, User, Action, Content
        filtered_logs = []
        for row in rows[1:]:
            if len(row) >= 5:
                log_date = row[0] # A열: 날짜
                log_user = row[2] # C열: 유저
                if log_date == target_date_str and log_user == username:
                    filtered_logs.append({
                        "time": row[1],
                        "action": row[3],
                        "content": row[4]
                    })
        # 시간 역순 정렬 (최신이 위로)
        return sorted(filtered_logs, key=lambda x: x['time'], reverse=True)
    except: return []

# -----------------------------------------------------------
# 3. 워드 파일 생성 함수
# -----------------------------------------------------------
def create_word_report(username, date_str, logs):
    doc = Document()
    doc.add_heading(f'{username}님의 연구 일지', 0)
    doc.add_paragraph(f'날짜: {date_str}')
    
    if not logs:
        doc.add_paragraph("기록된 활동이 없습니다.")
    else:
        for log in logs:
            doc.add_heading(f"[{log['time']}] {log['action']}", level=2)
            doc.add_paragraph(log['content'])
            doc.add_paragraph("-" * 30)
            
    # 메모리에 저장
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# -----------------------------------------------------------
# 4. AI 및 설정 초기화
# -----------------------------------------------------------
openai.api_key = st.secrets.get("OPENAI_API_KEY", "")
genai.configure(api_key=st.secrets.get("GEMINI_API_KEY", ""))

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'username' not in st.session_state: st.session_state['username'] = ""
if 'user_energy' not in st.session_state: st.session_state['user_energy'] = 500

# 컨텍스트 복구
if 'research_context' not in st.session_state: st.session_state['research_context'] = {}
keys = ['topic', 'variables_options', 'variables', 'method_options', 'method', 'references']
for k in keys:
    if k not in st.session_state['research_context']:
        if 'options' in k: st.session_state['research_context'][k] = []
        else: st.session_state['research_context'][k] = ""
if 'paper_sections' not in st.session_state:
    st.session_state['paper_sections'] = {"서론": "", "이론적 배경": "", "연구 방법": "", "결과": "", "논의": ""}
# 채팅 기록
chat_keys = ["chat_0", "chat_1", "chat_2", "chat_3", "chat_4", "chat_5"]
for k in chat_keys:
    if k not in st.session_state: st.session_state[k] = []

# -----------------------------------------------------------
# 5. AI 함수
# -----------------------------------------------------------
def chat_with_context(prompt, context_data, stage_name):
    try:
        system_msg = f"당신은 심리학 연구 조교 '다온'입니다.\n단계: {stage_name}\n[화면 내용]\n{context_data}"
        res = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"system","content":system_msg},{"role":"user","content":prompt}])
        return res.choices[0].message.content
    except Exception as e: return f"오류: {e}"

def get_ai_options(prompt):
    try:
        res = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user","content":prompt}])
        return [opt.strip() for opt in res.choices[0].message.content.split("|||") if opt.strip()]
    except: return ["오류 발생"]

def search_literature(topic, vars_text):
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        return model.generate_content(f"주제: {topic}, 변인: {vars_text}. 선행연구 3개 검색 요약.").text
    except: return "검색 오류"

def check_and_deduct(cost):
    if st.session_state['user_energy'] >= cost:
        st.session_state['user_energy'] -= cost
        return True
    st.error(f"에너지가 부족합니다 (필요: {cost})"); return False

# -----------------------------------------------------------
# 6. 메인 화면 (로그인 & 앱)
# -----------------------------------------------------------
def login_page():
    st.title("🔐 MJP Research Lab")
    
    tab1, tab2 = st.tabs(["로그인", "회원가입"])
    
    with tab1:
        with st.form("login_form"):
            uid = st.text_input("아이디")
            upw = st.text_input("비밀번호", type="password")
            if st.form_submit_button("로그인"):
                # 구글 시트에서 최신 유저 정보 가져오기
                users = fetch_users_from_sheet()
                if uid in users and users[uid] == upw:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = uid
                    # 로그인 기록
                    log_to_sheet(uid, "로그인", "접속 성공")
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 잘못되었습니다.")
    
    with tab2:
        st.write("새로운 연구원 등록")
        with st.form("signup_form"):
            new_id = st.text_input("사용할 아이디")
            new_pw = st.text_input("사용할 비밀번호", type="password")
            if st.form_submit_button("가입하기"):
                if new_id and new_pw:
                    suc, msg = register_user_to_sheet(new_id, new_pw)
                    if suc: st.success(msg)
                    else: st.error(msg)
                else:
                    st.warning("아이디와 비밀번호를 입력해주세요.")

def render_right_chat(key_suffix, context_data, stage_name):
    st.markdown(f"###### 💬 AI 조교 ({stage_name})")
    chat_key = f"chat_{key_suffix}"
    for msg in st.session_state[chat_key]:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    if prompt := st.chat_input("질문...", key=f"in_{key_suffix}"):
        if check_and_deduct(10):
            st.session_state[chat_key].append({"role":"user", "content":prompt})
            log_to_sheet(st.session_state['username'], f"질문({stage_name})", prompt)
            with st.chat_message("user"): st.markdown(prompt)
            with st.spinner("..."):
                ans = chat_with_context(prompt, context_data, stage_name)
                st.session_state[chat_key].append({"role":"assistant", "content":ans})
                log_to_sheet(st.session_state['username'], f"답변({stage_name})", ans)
                st.rerun()

def main_app():
    user = st.session_state['username']
    
    # [좌측 사이드바: 캘린더 & 관리자]
    with st.sidebar:
        st.header(f"👤 {user}님")
        
        # 1. 캘린더 (기록 열람)
        st.markdown("---")
        st.subheader("📅 연구 기록 열람")
        search_date = st.date_input("날짜 선택")
        
        if st.button("기록 불러오기"):
            date_str = search_date.strftime("%Y-%m-%d")
            logs = fetch_logs_by_date(user, date_str)
            if logs:
                st.success(f"{len(logs)}건의 기록을 찾았습니다.")
                st.session_state['fetched_logs'] = logs # 결과 저장
                st.session_state['fetched_date'] = date_str
            else:
                st.info("해당 날짜의 기록이 없습니다.")
        
        # 워드 다운로드 (불러온 기록이 있을 때만)
        if 'fetched_logs' in st.session_state and st.session_state['fetched_logs']:
            docx = create_word_report(user, st.session_state['fetched_date'], st.session_state['fetched_logs'])
            st.download_button(
                label="📄 워드파일 다운로드",
                data=docx,
                file_name=f"Research_Log_{st.session_state['fetched_date']}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

        # 2. 관리자 메뉴 (zenova90 전용)
        if user == "zenova90":
            st.markdown("---")
            st.error("🔒 관리자 메뉴")
            # 실제 시트 주소가 있으면 넣으세요. 없다면 구글 드라이브 메인으로 보냅니다.
            st.link_button("📂 구글 스프레드시트 열기", "https://docs.google.com/spreadsheets")
        
        # 3. 충전소 & 로그아웃
        st.markdown("---")
        with st.expander("⚡ 충전소"):
            code = st.text_input("쿠폰")
            if st.button("충전"):
                if code == "TEST-1000":
                    st.session_state['user_energy'] += 1000
                    log_to_sheet(user, "충전", "1000E")
                    st.success("충전 완료")
        
        if st.button("로그아웃"): 
            st.session_state['logged_in'] = False
            st.rerun()

    # [메인 화면]
    st.title("🎓 MJP Research Lab")
    st.markdown(f"<div class='energy-box'><span>⚡ Energy:</span><span class='energy-val'>{st.session_state['user_energy']}</span></div>", unsafe_allow_html=True)

    tabs = st.tabs(["💡 토론", "1. 변인", "2. 방법", "3. 검색", "4. 작성", "5. 참고", "📜 오늘 기록"])

    with tabs[0]:
        st.header("Brainstorming")
        render_right_chat("0", "초기 아이디어 구상 단계", "0단계")

    with tabs[1]:
        col_L, col_R = st.columns([6, 4])
        with col_L:
            st.subheader("Variables")
            v = st.text_area("변인", value=st.session_state['research_context']['variables'])
            if st.button("저장", key="s_v"): 
                st.session_state['research_context']['variables']=v; log_to_sheet(user,"변인확정",v); st.success("Saved")
            
            topic = st.text_input("주제", value=st.session_state['research_context']['topic'])
            if st.button("AI 제안 (50E)", key="ai_v"):
                if check_and_deduct(50):
                    opts = get_ai_options(f"주제 '{topic}' 변인 3개 추천")
                    st.session_state['research_context']['variables_options'] = opts
                    st.rerun()
            if st.session_state['research_context']['variables_options']:
                c = st.radio("선택", st.session_state['research_context']['variables_options'])
                if st.button("적용", key="a_v"): st.session_state['research_context']['variables']=c; st.rerun()
        with col_R:
            render_right_chat("1", f"주제:{topic}\n변인:{v}", "1단계")

    with tabs[2]:
        col_L, col_R = st.columns([6, 4])
        with col_L:
            st.subheader("Methodology")
            m = st.text_area("방법", value=st.session_state['research_context']['method'])
            if st.button("저장", key="s_m"): 
                st.session_state['research_context']['method']=m; log_to_sheet(user,"방법확정",m); st.success("Saved")
            if st.button("AI 제안 (50E)", key="ai_m"):
                if check_and_deduct(50):
                    opts = get_ai_options(f"변인 '{st.session_state['research_context']['variables']}' 방법론 3개 추천")
                    st.session_state['research_context']['method_options'] = opts
                    st.rerun()
            if st.session_state['research_context']['method_options']:
                c = st.radio("선택", st.session_state['research_context']['method_options'])
                if st.button("적용", key="a_m"): st.session_state['research_context']['method']=c; st.rerun()
        with col_R:
            render_right_chat("2", f"방법:{m}", "2단계")

    with tabs[3]:
        col_L, col_R = st.columns([6, 4])
        with col_L:
            st.subheader("Search")
            if st.button("검색 (30E)", key="s_g"):
                if check_and_deduct(30):
                    res = search_literature(st.session_state['research_context']['topic'], st.session_state['research_context']['variables'])
                    st.session_state['research_context']['references'] = res
                    log_to_sheet(user, "검색", res)
                    st.rerun()
            st.text_area("결과", value=st.session_state['research_context']['references'])
        with col_R: render_right_chat("3", st.session_state['research_context']['references'], "3단계")

    with tabs[4]:
        col_L, col_R = st.columns([6, 4])
        with col_L:
            st.subheader("Drafting")
            sec = st.selectbox("챕터", list(st.session_state['paper_sections'].keys()))
            if st.button("AI 작성 (100E)", key="ai_w"):
                if check_and_deduct(100):
                    draft = chat_with_context(f"'{sec}' 작성해줘", str(st.session_state['research_context']), "작성")
                    st.session_state['paper_sections'][sec] = draft
                    log_to_sheet(user, f"작성({sec})", draft)
                    st.rerun()
            cur = st.text_area("에디터", value=st.session_state['paper_sections'][sec])
            if st.button("저장", key="s_d"): st.session_state['paper_sections'][sec]=cur; log_to_sheet(user,f"수정({sec})", cur); st.success("Saved")
        with col_R: render_right_chat("4", f"챕터:{sec}\n{st.session_state['paper_sections'][sec]}", "4단계")

    with tabs[5]:
        col_L, col_R = st.columns([6, 4])
        with col_L:
            st.subheader("References")
            if st.button("APA 변환 (20E)", key="apa"):
                if check_and_deduct(20):
                    res = chat_with_context("APA 변환해줘", st.session_state['research_context']['references'], "참고문헌")
                    st.markdown(res)
        with col_R: render_right_chat("5", st.session_state['research_context']['references'], "5단계")

    with tabs[6]:
        st.header("오늘의 활동 로그")
        # 오늘 날짜 로그만 간단히 보여주기
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        if 'fetched_date' in st.session_state and st.session_state['fetched_date'] == today:
             logs = st.session_state['fetched_logs']
        else:
             logs = fetch_logs_by_date(user, today)
        
        for log in logs:
            st.markdown(f"<div class='log-entry'><b>{log['time']}</b> [{log['action']}]<br>{log['content'][:60]}...</div>", unsafe_allow_html=True)

if st.session_state['logged_in']: main_app()
else: login_page()
