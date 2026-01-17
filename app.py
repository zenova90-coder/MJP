import streamlit as st
import openai
import google.generativeai as genai

# -----------------------------------------------------------
# 1. 스타일 & 기본 설정
# -----------------------------------------------------------
st.set_page_config(page_title="MJP Pro: 연구 토론 파트너", layout="wide")

st.markdown("""
<style>
    div.stButton > button:first-child {
        background-color: #0068c9;
        color: white;
        border-radius: 6px;
        font-weight: bold;
    }
    div.stButton > button:first-child:hover {
        background-color: #004b91;
    }
    /* 토큰 표시 디자인 */
    .token-box {
        padding: 10px;
        background-color: #f0f2f6;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 20px;
        border: 2px solid #0068c9;
    }
    .token-text {
        font-size: 20px;
        font-weight: bold;
        color: #0068c9;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------
# 2. 데이터 저장소 & 토큰 시스템 초기화
# -----------------------------------------------------------
# [NEW] 토큰 시스템
if 'user_tokens' not in st.session_state:
    st.session_state['user_tokens'] = 1000  # 신규 가입 축하금

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
# 3. 사이드바: 로그인 & 결제 시스템 (충전소)
# -----------------------------------------------------------
with st.sidebar:
    st.header("🔐 연구실 입장")
    code = st.text_input("비밀번호", type="password")
    if code not in st.secrets["ACCESS_CODES"]:
        st.warning("연구원 권한이 필요합니다.")
        st.stop()
    st.success("로그인 완료")

    st.markdown("---")
    
    # 💰 [NEW] 토큰 충전소
    st.header("🔋 토큰 충전소")
    
    # 현재 잔액 표시 (사이드바)
    st.metric(label="현재 보유 토큰", value=f"{st.session_state['user_tokens']} T")
    
    with st.expander("💳 토큰 충전하기 (결제)"):
        st.write("토큰이 부족한가요? 아래 계좌로 입금 후 관리자에게 연락주세요.")
        st.code("카카오뱅크 3333-XX-XXXXXX (예금주: 민주)") # [수정필요] 본인 계좌로 변경
        st.markdown("[📲 카카오페이로 송금하기](https://qr.kakaopay.com/...)") # [수정필요] 링크 넣기
        st.info("입금 후 받은 쿠폰 코드를 아래에 입력하세요.")
        
        # 쿠폰 입력 시스템
        coupon = st.text_input("쿠폰 코드 입력")
        if st.button("충전 적용"):
            if coupon == "MJP-LOVE-2026":
                st.session_state['user_tokens'] += 5000
                st.balloons()
                st.success("5,000 토큰이 충전되었습니다!")
            elif coupon == "ADMIN-POWER":
                st.session_state['user_tokens'] += 10000
                st.success("10,000 토큰 충전 완료!")
            else:
                st.error("유효하지 않은 쿠폰입니다.")
                
    st.markdown("---")
    if st.button("🗑️ 초기화", type="primary"):
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()

openai.api_key = st.secrets["OPENAI_API_KEY"]
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# -----------------------------------------------------------
# 4. 기능 함수 (토큰 차감 로직 추가)
# -----------------------------------------------------------
# 토큰 차감 도우미 함수
def check_and_deduct_tokens(cost):
    if st.session_state['user_tokens'] >= cost:
        st.session_state['user_tokens'] -= cost
        return True
    else:
        st.error(f"토큰이 부족합니다! (필요: {cost}, 보유: {st.session_state['user_tokens']}) 사이드바에서 충전하세요.")
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
# 5. [수정됨] 에러 없는 채팅 인터페이스 (Key 추가!)
# -----------------------------------------------------------
def render_chat_interface(stage_name, user_input_content, ai_suggestions_content="", unique_key="default"):
    st.markdown(f"#### 💬 AI 조교 ({stage_name})")
    st.caption("👈 왼쪽 내용을 다 보고 있습니다.")
    
    with st.container(height=450):
        # 현재 단계에 맞는 대화만 보여주면 좋겠지만, 일단 전체 공유 (간소화)
        for message in st.session_state.messages_helper:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # [핵심 수정] key=unique_key를 추가하여 중복 에러 해결!
    if prompt := st.chat_input("질문하기...", key=unique_key):
        
        # 채팅도 토큰 소모 (싸게 10토큰)
        if not check_and_deduct_tokens(10):
            st.stop()
            
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
# 6. 메인 화면 구성 (토큰 잔액 대시보드 추가)
# -----------------------------------------------------------
st.title("🎓 MJP: 연구 토론 & 설계 시스템 (Biz)")

# [NEW] 중앙 토큰 대시보드
st.markdown(f"""
<div class="token-box">
    <span>💎 현재 보유 토큰: </span>
    <span class="token-text">{st.session_state['user_tokens']} T</span>
    <span style="font-size: 14px; color: gray;"> (AI 사용 시 차감됩니다)</span>
</div>
""", unsafe_allow_html=True)


tabs = st.tabs(["💡 0. 토론", "1. 변인", "2. 방법", "3. 검색", "4. 작성", "5. 참고문헌"])

# [Tab 0] 토론
with tabs[0]:
    st.header("💡 0단계: 연구 아이디어 토론")
    for msg in st.session_state.chat_history_step0:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    # [핵심 수정] key 추가
    if prompt := st.chat_input("아이디어 토론하기...", key="chat_tab0"):
        if check_and_deduct_tokens(20): # 토론은 20토큰
            st.session_state.chat_history_step0.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("생각 중..."):
                    res = openai.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "system", "content": "심리학 연구팀입니다."}] + 
                                 [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_history_step0]
                    )
                    st.markdown(res.choices[0].message.content)
                    st.session_state.chat_history_step0.append({"role": "assistant", "content": res.choices[0].message.content})
                    st.rerun() # 잔액 갱신 위해

# [Tab 1] 변인
with tabs[1]:
    col_main, col_chat = st.columns([6, 4])
    with col_main:
        st.subheader("🧠 1단계: 변인 확정")
        final_vars = st.text_area("최종 변인", value=st.session_state['research_context']['variables'], height=150)
        if st.button("✅ 저장", type="primary", key="save_v"):
            st.session_state['research_context']['variables'] = final_vars
            st.success("저장됨")
            
        topic = st.text_input("주제", value=st.session_state['research_context']['topic'])
        if st.button("🤖 3가지 제안 (50토큰)", key="gen_v"):
            if check_and_deduct_tokens(50):
                with st.spinner("생성 중..."):
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
        # [핵심 수정] key="chat_tab1" 전달
        render_chat_interface("1단계", st.session_state['research_context']['variables'], 
                            str(st.session_state['research_context']['variables_options']), unique_key="chat_tab1")

# [Tab 2] 방법
with tabs[2]:
    col_main, col_chat = st.columns([6, 4])
    with col_main:
        st.subheader("📐 2단계: 방법 확정")
        final_method = st.text_area("최종 방법", value=st.session_state['research_context']['method'], height=150)
        if st.button("✅ 저장", type="primary", key="save_m"):
            st.session_state['research_context']['method'] = final_method
            st.success("저장됨")
            
        if st.button("🤖 3가지 제안 (50토큰)", key="gen_m"):
            if check_and_deduct_tokens(50):
                with st.spinner("설계 중..."):
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
        st.subheader("🔍 3단계: 검색")
        if st.button("🚀 Gemini 검색 (30토큰)", type="primary"):
            if check_and_deduct_tokens(30):
                with st.spinner("검색 중..."):
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
        st.subheader("✍️ 4단계: 작성")
        sec = st.selectbox("챕터", list(st.session_state['paper_sections'].keys()))
        if st.button(f"🤖 {sec} 작성 (100토큰)", type="primary"):
            if check_and_deduct_tokens(100):
                with st.spinner("작성 중..."):
                    draft = write_paper_final(sec, st.session_state['research_context']['references'])
                    st.session_state['paper_sections'][sec] = draft
                    st.rerun()
        current = st.text_area("편집기", value=st.session_state['paper_sections'][sec], height=600)
        if st.button("💾 저장", key="save_sec"):
            st.session_state['paper_sections'][sec] = current
            st.success("저장됨")

    with col_chat:
        render_chat_interface(f"4단계({sec})", st.session_state['paper_sections'][sec], unique_key="chat_tab4")

# [Tab 5] 참고문헌
with tabs[5]:
    col_main, col_chat = st.columns([6, 4])
    with col_main:
        if st.button("✨ 변환 (20토큰)", type="primary"):
            if check_and_deduct_tokens(20):
                res = organize_references_apa(st.session_state['research_context']['references'])
                st.markdown(res)
    with col_chat:
        render_chat_interface("5단계", "참고문헌 작업", unique_key="chat_tab5")