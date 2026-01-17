import streamlit as st
import openai
import google.generativeai as genai
import hashlib
import datetime

# -----------------------------------------------------------
# 1. 스타일 & 기본 설정 (중립적 디자인)
# -----------------------------------------------------------
st.set_page_config(page_title="MJP Pro: Research Lab", layout="wide")

st.markdown("""
<style>
    /* 전체적인 폰트와 버튼 스타일 */
    div.stButton > button:first-child {
        background-color: #4a5568; /* 중립적인 짙은 회색 */
        color: white;
        border-radius: 4px;
        border: none;
        font-weight: 500;
    }
    div.stButton > button:first-child:hover {
        background-color: #2d3748;
    }
    
    /* 에너지(토큰) 박스 디자인 - 중립적이고 깔끔하게 */
    .energy-box {
        padding: 8px 15px;
        background-color: #f7fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        margin-bottom: 20px;
    }
    .energy-icon {
        font-size: 18px;
    }
    .energy-value {
        font-size: 18px;
        font-weight: bold;
        color: #2d3748; /* 돈 색깔이 아닌 차분한 색 */
        font-family: 'Courier New', monospace;
    }
    .energy-label {
        font-size: 14px;
        color: #718096;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------
# 2. 데이터 저장소 & 시스템 초기화
# -----------------------------------------------------------
if 'user_energy' not in st.session_state:
    st.session_state['user_energy'] = 1000  # 기본 제공 에너지

if 'research_context' not in st.session_state:
    st.session_state['research_context'] = {
        'topic': '', 'variables_options': [], 'variables': '',
        'method_options': [], 'method': '', 'references': ''
    }

if 'paper_sections' not in st.session_state:
    st.session_state['paper_sections'] = {
        "서론": "", "이론적 배경": "", "연구 방법": "", "결과": "", "논의": ""
    }

if "chat_history_step0" not in st.session_state:
    st.session_state.chat_history_step0 = []

if "messages_helper" not in st.session_state:
    st.session_state.messages_helper = []

# -----------------------------------------------------------
# 3. [핵심] 쿠폰 생성 알고리즘 (관리자용)
# -----------------------------------------------------------
# 민주님만의 비밀 키 (이게 있어야 코드가 만들어짐)
SECRET_KEY = "MINJU_RESEARCH_LAB_SECRET_KEY_2026"

def generate_coupon_code(amount):
    """오늘 날짜와 금액을 섞어서 유니크한 코드를 생성"""
    today = datetime.datetime.now().strftime("%Y%m%d")
    raw_string = f"{SECRET_KEY}{amount}{today}"
    # 해시 함수로 암호화 (앞 8자리만 사용)
    code = hashlib.sha256(raw_string.encode()).hexdigest()[:8].upper()
    return f"MJP-{amount}-{code}"

def verify_coupon(code):
    """입력된 코드가 진짜인지 검증"""
    try:
        parts = code.split("-")
        if len(parts) != 3: return False, 0
        
        amount = parts[1]
        input_hash = parts[2]
        
        # 오늘 생성된 코드인지 확인 (유효기간 하루)
        # 만약 유효기간을 없애려면 날짜 체크 로직을 빼면 됩니다.
        today = datetime.datetime.now().strftime("%Y%m%d")
        raw_string = f"{SECRET_KEY}{amount}{today}"
        real_hash = hashlib.sha256(raw_string.encode()).hexdigest()[:8].upper()
        
        if input_hash == real_hash:
            return True, int(amount)
        else:
            return False, 0
    except:
        return False, 0

# -----------------------------------------------------------
# 4. 사이드바: 관리자 모드 & 충전소
# -----------------------------------------------------------
with st.sidebar:
    st.header("🔐 연구실 설정")
    
    # 관리자 로그인 (민주님 전용)
    with st.expander("⚙️ 관리자 도구 (Admin)"):
        admin_pw = st.text_input("관리자 암호", type="password")
        if admin_pw == "admin1234": # [변경필요] 민주님만의 암호로 바꾸세요
            st.success("관리자 모드 활성화")
            st.write("---")
            st.write("**💰 충전 코드 생성기**")
            amount_to_gen = st.number_input("충전할 금액", step=1000, value=5000)
            if st.button("코드 생성"):
                new_code = generate_coupon_code(amount_to_gen)
                st.code(new_code, language="text")
                st.info("👆 이 코드를 복사해서 입금한 사용자에게 보내주세요.")
                st.caption(f"(참고: 이 코드는 오늘({datetime.datetime.now().strftime('%m월 %d일')})만 유효합니다)")

    st.markdown("---")
    
    # 사용자용 충전소
    st.subheader("⚡ 에너지 충전소")
    
    with st.expander("충전 방법 안내"):
        st.caption("연구 에너지가 부족한가요?")
        st.write("1. 아래 계좌로 입금해주세요.")
        st.code("기업은행 010-2989-0076 (양민주)")
        st.write("2. 관리자에게 입금 확인 요청을 하세요.")
        st.write("3. 전달받은 코드를 아래에 입력하세요.")
        
        coupon_input = st.text_input("충전 코드 입력")
        if st.button("충전하기"):
            is_valid, amount = verify_coupon(coupon_input)
            if is_valid:
                st.session_state['user_energy'] += amount
                st.balloons()
                st.success(f"{amount} 에너지가 충전되었습니다!")
            else:
                st.error("유효하지 않거나 만료된 코드입니다.")

    st.markdown("---")
    if st.button("시스템 리셋"):
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()

openai.api_key = st.secrets["OPENAI_API_KEY"]
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# -----------------------------------------------------------
# 5. 기능 함수 (에너지 차감 로직)
# -----------------------------------------------------------
def check_and_deduct(cost):
    if st.session_state['user_energy'] >= cost:
        st.session_state['user_energy'] -= cost
        return True
    else:
        st.error(f"에너지가 부족합니다. (필요: {cost}) 사이드바에서 충전해주세요.")
        return False

def consult_variables_options(topic):
    prompt = f"주제 '{topic}' 변인 구조 3가지 제안 (구분자 |||)"
    response = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    return [opt.strip() for opt in response.choices[0].message.content.split("|||") if opt.strip()]

def design_methodology_options(vars_text):
    prompt = f"변인 '{vars_text}' 방법론 3가지 제안 (구분자 |||)"
    response = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    return [opt.strip() for opt in response.choices[0].message.content.split("|||") if opt.strip()]

def search_literature(topic, vars_text):
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"주제: {topic}, 변인: {vars_text}. 선행 연구 검색."
        return model.generate_content(prompt).text
    except: return "검색 오류"

def write_paper_final(section, context_data):
    prompt = f"[APA 스타일] '{section}' 작성. 근거: {context_data}"
    response = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content

def organize_references_apa(raw_text):
    prompt = f"참고문헌 APA 변환 및 정렬:\n{raw_text}"
    response = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content

# -----------------------------------------------------------
# 6. 채팅 인터페이스
# -----------------------------------------------------------
def render_chat_interface(stage_name, user_input_content, ai_suggestions_content="", unique_key="default"):
    st.markdown(f"#### 💬 AI 조교 ({stage_name})")
    st.caption("👈 왼쪽 내용을 다 보고 있습니다.")
    
    with st.container(height=450):
        for message in st.session_state.messages_helper:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    if prompt := st.chat_input("질문하기...", key=unique_key):
        if not check_and_deduct(10): st.stop()
        st.session_state.messages_helper.append({"role": "user", "content": prompt})
        
        full_context = f"단계: {stage_name}\n내용: {user_input_content}\n옵션: {ai_suggestions_content}\n질문: {prompt}"
        
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "친절한 연구 조교입니다."}] + 
                     [{"role": "user", "content": full_context}]
        )
        ai_msg = response.choices[0].message.content
        st.session_state.messages_helper.append({"role": "assistant", "content": ai_msg})
        st.rerun()

# -----------------------------------------------------------
# 7. 메인 화면
# -----------------------------------------------------------
st.title("🎓 MJP Research Lab")

# [디자인 변경] 에너지 표시바 (중립적 디자인)
st.markdown(f"""
<div class="energy-box">
    <span class="energy-icon">⚡</span>
    <span class="energy-label">Available Energy:</span>
    <span class="energy-value">{st.session_state['user_energy']}</span>
</div>
""", unsafe_allow_html=True)

tabs = st.tabs(["💡 0. 토론", "1. 변인", "2. 방법", "3. 검색", "4. 작성", "5. 참고문헌"])

# [Tab 0] 토론
with tabs[0]:
    st.header("💡 Brainstorming")
    for msg in st.session_state.chat_history_step0:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    if prompt := st.chat_input("아이디어 토론하기...", key="chat_tab0"):
        if check_and_deduct(20):
            st.session_state.chat_history_step0.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Analyzing..."):
                    res = openai.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "system", "content": "심리학 연구팀입니다."}] + 
                                 [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_history_step0]
                    )
                    st.markdown(res.choices[0].message.content)
                    st.session_state.chat_history_step0.append({"role": "assistant", "content": res.choices[0].message.content})
                    st.rerun()

# [Tab 1] 변인
with tabs[1]:
    col_main, col_chat = st.columns([6, 4])
    with col_main:
        st.subheader("🧠 1. Variables")
        final_vars = st.text_area("최종 변인", value=st.session_state['research_context']['variables'], height=150)
        if st.button("✅ 저장", key="save_v"):
            st.session_state['research_context']['variables'] = final_vars
            st.success("Saved")
            
        topic = st.text_input("주제", value=st.session_state['research_context']['topic'])
        if st.button("🤖 3가지 제안 (50 Energy)", key="gen_v"):
            if check_and_deduct(50):
                with st.spinner("Generating..."):
                    opts = consult_variables_options(topic)
                    st.session_state['research_context']['variables_options'] = opts
                    st.session_state['research_context']['topic'] = topic
                    st.rerun()

        if st.session_state['research_context']['variables_options']:
            choice = st.radio("선택:", st.session_state['research_context']['variables_options'])
            if st.button("🔼 적용", key="apply_v"):
                st.session_state['research_context']['variables'] = choice
                st.rerun()

    with col_chat:
        render_chat_interface("1단계", st.session_state['research_context']['variables'], 
                            str(st.session_state['research_context']['variables_options']), unique_key="chat_tab1")

# [Tab 2] 방법
with tabs[2]:
    col_main, col_chat = st.columns([6, 4])
    with col_main:
        st.subheader("📐 2. Methodology")
        final_method = st.text_area("최종 방법", value=st.session_state['research_context']['method'], height=150)
        if st.button("✅ 저장", key="save_m"):
            st.session_state['research_context']['method'] = final_method
            st.success("Saved")
            
        if st.button("🤖 3가지 제안 (50 Energy)", key="gen_m"):
            if check_and_deduct(50):
                with st.spinner("Designing..."):
                    opts = design_methodology_options(st.session_state['research_context']['variables'])
                    st.session_state['research_context']['method_options'] = opts
                    st.rerun()
        
        if st.session_state['research_context']['method_options']:
            choice = st.radio("선택:", st.session_state['research_context']['method_options'])
            if st.button("🔼 적용", key="apply_m"):
                st.session_state['research_context']['method'] = choice
                st.rerun()

    with col_chat:
        render_chat_interface("2단계", st.session_state['research_context']['method'], 
                            str(st.session_state['research_context']['method_options']), unique_key="chat_tab2")

# [Tab 3] 검색
with tabs[3]:
    col_main, col_chat = st.columns([6, 4])
    with col_main:
        st.subheader("🔍 3. Literature Search")
        if st.button("🚀 Gemini 검색 (30 Energy)"):
            if check_and_deduct(30):
                with st.spinner("Searching..."):
                    refs = search_literature(st.session_state['research_context']['topic'], st.session_state['research_context']['variables'])
                    st.session_state['research_context']['references'] = refs
                    st.rerun()
        st.text_area("결과", value=st.session_state['research_context']['references'], height=500)

    with col_chat:
        render_chat_interface("3단계", st.session_state['research_context']['references'], unique_key="chat_tab3")

# [Tab 4] 작성
with tabs[4]:
    col_main, col_chat = st.columns([6, 4])
    with col_main:
        st.subheader("✍️ 4. Drafting")
        sec = st.selectbox("챕터", list(st.session_state['paper_sections'].keys()))
        if st.button(f"🤖 {sec} 작성 (100 Energy)"):
            if check_and_deduct(100):
                with st.spinner("Drafting..."):
                    draft = write_paper_final(sec, st.session_state['research_context']['references'])
                    st.session_state['paper_sections'][sec] = draft
                    st.rerun()
        current = st.text_area("편집기", value=st.session_state['paper_sections'][sec], height=600)
        if st.button("💾 저장", key="save_sec"):
            st.session_state['paper_sections'][sec] = current
            st.success("Saved")

    with col_chat:
        render_chat_interface(f"4단계({sec})", st.session_state['paper_sections'][sec], unique_key="chat_tab4")

# [Tab 5] 참고문헌
with tabs[5]:
    col_main, col_chat = st.columns([6, 4])
    with col_main:
        st.subheader("📚 5. References")
        if st.button("✨ 변환 (20 Energy)"):
            if check_and_deduct(20):
                res = organize_references_apa(st.session_state['research_context']['references'])
                st.markdown(res)
    with col_chat:
        render_chat_interface("5단계", "참고문헌 작업", unique_key="chat_tab5")