import streamlit as st
import openai
import google.generativeai as genai

# -----------------------------------------------------------
# 1. 스타일 & 기본 설정
# -----------------------------------------------------------
st.set_page_config(page_title="MJP Pro: 연구 토론 파트너", layout="wide")

# 스타일: 버튼 색상 및 탭 폰트 강화
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
    /* 텍스트 영역 상단 여백 조정 */
    .stTextArea { margin-top: -10px; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------
# 2. 데이터 저장소(세션) 초기화
# -----------------------------------------------------------
# 연구의 각 단계별 내용을 저장
if 'research_context' not in st.session_state:
    st.session_state['research_context'] = {
        'topic': '',
        'variables_options': [], 
        'variables': '', # 1단계 확정 변인
        'method_options': [], 
        'method': '',    # 2단계 확정 방법
        'references': '' # 3단계 검색 결과
    }

# 논문 챕터별 내용 저장
if 'paper_sections' not in st.session_state:
    st.session_state['paper_sections'] = {
        "서론": "", "이론적 배경": "", "연구 방법": "", "결과": "", "논의": ""
    }

# [NEW] 0단계 토론방 전용 채팅 기록
if "chat_history_step0" not in st.session_state:
    st.session_state.chat_history_step0 = []

# 각 단계별 도우미 채팅 기록 (통합)
if "messages_helper" not in st.session_state:
    st.session_state.messages_helper = []

# -----------------------------------------------------------
# 3. 로그인 & API 설정
# -----------------------------------------------------------
with st.sidebar:
    st.header("🔐 연구실 입장")
    code = st.text_input("비밀번호", type="password")
    if code not in st.secrets["ACCESS_CODES"]:
        st.warning("연구원 권한이 필요합니다.")
        st.stop()
    st.success("System Online")
    
    if st.button("🗑️ 모든 대화/설정 초기화", type="primary"):
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()

openai.api_key = st.secrets["OPENAI_API_KEY"]
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# -----------------------------------------------------------
# 4. AI 두뇌 (기능 함수)
# -----------------------------------------------------------

def consult_variables_options(topic):
    prompt = f"""
    주제 '{topic}'에 적합한 변인 구조(독립/종속/매개 등)를 3가지 제안해주세요.
    각 옵션은 '|||'로 구분해서 출력하세요. 설명은 핵심만 간결하게.
    예: 1안: ... ||| 2안: ... ||| 3안: ...
    """
    response = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    return [opt.strip() for opt in response.choices[0].message.content.split("|||") if opt.strip()]

def design_methodology_options(vars_text):
    prompt = f"""
    변인 구조: '{vars_text}'
    이 변인을 연구하기 위한 '척도(측정도구)'와 '통계 분석 방법' 조합을 3가지 제안해주세요.
    각 옵션은 '|||'로 구분해서 출력하세요.
    """
    response = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    return [opt.strip() for opt in response.choices[0].message.content.split("|||") if opt.strip()]

def search_literature(topic, vars_text):
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"주제: {topic}, 변인: {vars_text}. 관련 최신 선행 연구(2020-2026)와 핵심 이론 요약."
        return model.generate_content(prompt).text
    except:
        return "검색 오류. 잠시 후 다시 시도하세요."

def write_paper_final(section, context_data):
    prompt = f"""
    [역할]: 논리적이고 비판적인 심리학 연구자.
    [작업]: '{section}' 챕터 작성.
    [근거]: {context_data}
    [지침]: 구체적인 수치나 논리를 포함하여 APA 스타일로 작성.
    """
    response = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content

def organize_references_apa(raw_text):
    prompt = f"참고문헌 추출 -> APA 7판 변환 -> 알파벳/가나다 순 정렬:\n{raw_text}"
    response = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content

# -----------------------------------------------------------
# 5. 공통 컴포넌트: 맥락 인식 챗봇 (오른쪽 화면)
# -----------------------------------------------------------
def render_chat_interface(stage_name, user_input_content, ai_suggestions_content=""):
    st.markdown(f"#### 💬 AI 조교 ({stage_name})")
    st.caption("👈 왼쪽 내용을 다 보고 있습니다. 편하게 질문하세요.")
    
    with st.container(height=500):
        for message in st.session_state.messages_helper:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    if prompt := st.chat_input("예: 1안은 너무 복잡하지 않아?"):
        st.session_state.messages_helper.append({"role": "user", "content": prompt})
        
        # [핵심] 왼쪽의 모든 정보를 긁어서 AI에게 줍니다.
        full_context = f"""
        [현재 작업 단계]: {stage_name}
        
        [사용자가 작성/확정한 내용]: 
        {user_input_content}
        
        [AI가 제안했던 옵션들(있다면)]:
        {ai_suggestions_content}
        
        [사용자 질문]: {prompt}
        """
        
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "당신은 사용자의 연구 파트너입니다. 왼쪽의 화면 내용을 바탕으로 조언하세요."}] + 
                     [{"role": "user", "content": full_context}]
        )
        ai_msg = response.choices[0].message.content
        st.session_state.messages_helper.append({"role": "assistant", "content": ai_msg})
        st.rerun()

# -----------------------------------------------------------
# 6. 메인 화면 구성
# -----------------------------------------------------------
st.title("🎓 MJP: 연구 토론 & 설계 시스템")

# 탭 구성 (0단계 추가됨!)
tabs = st.tabs(["💡 0. 토론(Brainstorming)", "1. 변인 설정", "2. 방법론 설계", "3. 자료 검색", "4. 본문 작성", "5. 참고문헌"])

# ===========================================================
# [Tab 0] 연구 토론방 (Brainstorming) - NEW!
# ===========================================================
with tabs[0]:
    st.header("💡 0단계: 연구 아이디어 토론방")
    st.info("여기는 막연한 생각을 구체화하는 곳입니다. \"나 요즘 이런 게 궁금한데...\"라고 말을 걸어보세요.")
    
    # 토론방 전용 채팅 인터페이스
    for message in st.session_state.chat_history_step0:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("예: 우울증 약을 먹는데 '시간관'이랑 무슨 관계가 있을까? 설문 연구 가능할까?"):
        st.session_state.chat_history_step0.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Gemini와 GPT가 머리를 맞대고 고민 중입니다..."):
                # 토론을 위한 시스템 프롬프트
                system_prompt = """
                당신은 '심리학 연구 팀'입니다. (Gemini의 지식 + GPT의 논리)
                사용자의 개인적인 경험이나 막연한 궁금증을 들으면, 다음 단계로 토론을 진행하세요:
                
                1. [공감 및 학술적 연결]: 사용자의 경험이 심리학적으로 어떤 개념(변인)과 연결되는지 설명.
                2. [선행 연구 힌트]: "실제로 ~한 연구 결과가 있습니다" 형태로 근거 제시.
                3. [연구 가능성 평가]: 이것을 설문지 연구로 진행할 때의 장점과 주의점.
                4. [질문 유도]: 사용자가 더 깊게 생각할 수 있도록 역질문을 던지세요.
                """
                
                response = openai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": system_prompt}] + 
                             [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat_history_step0]
                )
                ai_msg = response.choices[0].message.content
                st.markdown(ai_msg)
                st.session_state.chat_history_step0.append({"role": "assistant", "content": ai_msg})


# ===========================================================
# [Tab 1] 변인 설정 (버그 수정 + 연동 강화)
# ===========================================================
with tabs[1]:
    col_main, col_chat = st.columns([6, 4])
    
    with col_main:
        st.subheader("🧠 1단계: 변인 확정")
        
        # 입력란 (세션 상태와 바로 연동)
        final_vars = st.text_area("📌 최종 변인 (0단계 토론 내용을 참고해 작성하세요)", 
                                value=st.session_state['research_context']['variables'], 
                                height=150)
        
        if st.button("✅ 변인 내용 저장하기", type="primary"):
            st.session_state['research_context']['variables'] = final_vars
            st.success("저장되었습니다! (오른쪽 채팅창에서 피드백을 받아보세요)")

        st.markdown("---")
        st.info("💡 변인 구조가 잡히지 않았다면 AI 제안을 받아보세요.")
        
        topic = st.text_input("연구 주제 키워드", value=st.session_state['research_context']['topic'])
        
        if st.button("🤖 변인 구조 3가지 제안받기"):
            with st.spinner("구조 생성 중..."):
                opts = consult_variables_options(topic)
                st.session_state['research_context']['variables_options'] = opts
                st.session_state['research_context']['topic'] = topic
        
        # 옵션 표시 및 적용 기능
        if st.session_state['research_context']['variables_options']:
            choice = st.radio("옵션 선택:", st.session_state['research_context']['variables_options'])
            
            # [Fix] 적용하기 버튼 작동하게 수정
            if st.button("🔼 위 입력란에 적용하기"):
                st.session_state['research_context']['variables'] = choice
                st.rerun() # 즉시 새로고침하여 text_area 업데이트

    with col_chat:
        # [Upgrade] 제안된 옵션들도 같이 보여줌
        ai_opts = "\n".join(st.session_state['research_context']['variables_options'])
        render_chat_interface("1단계(변인)", st.session_state['research_context']['variables'], ai_opts)


# ===========================================================
# [Tab 2] 방법론 설계 (버그 수정 + 연동 강화)
# ===========================================================
with tabs[2]:
    col_main, col_chat = st.columns([6, 4])
    
    with col_main:
        st.subheader("📐 2단계: 연구 방법 확정")
        
        final_method = st.text_area("📌 최종 방법론 입력란", 
                                  value=st.session_state['research_context']['method'], 
                                  height=150)
        
        if st.button("✅ 방법론 내용 저장하기", type="primary"):
            st.session_state['research_context']['method'] = final_method
            st.success("저장되었습니다!")

        st.markdown("---")
        
        current_vars = st.session_state['research_context']['variables']
        st.write(f"현재 설정된 변인: **{current_vars if current_vars else '(변인 미설정)'}**")
        
        if st.button("🤖 방법론 3가지 제안받기"):
            if not current_vars:
                st.error("1단계 변인을 먼저 설정하세요.")
            else:
                with st.spinner("설계 중..."):
                    opts = design_methodology_options(current_vars)
                    st.session_state['research_context']['method_options'] = opts
        
        if st.session_state['research_context']['method_options']:
            method_choice = st.radio("방법론 선택:", st.session_state['research_context']['method_options'])
            
            # [Fix] 적용하기 버튼 수리
            if st.button("🔼 위 입력란에 적용하기", key="btn_apply_method"):
                st.session_state['research_context']['method'] = method_choice
                st.rerun()

    with col_chat:
        ai_opts = "\n".join(st.session_state['research_context']['method_options'])
        render_chat_interface("2단계(방법론)", st.session_state['research_context']['method'], ai_opts)


# ===========================================================
# [Tab 3] 자료 검색 (기존 기능 유지)
# ===========================================================
with tabs[3]:
    col_main, col_chat = st.columns([6, 4])
    
    with col_main:
        st.subheader("🔍 3단계: 선행 연구 수집")
        if st.button("🚀 Gemini 검색 시작", type="primary"):
            t = st.session_state['research_context']['topic']
            v = st.session_state['research_context']['variables']
            if not t or not v:
                st.warning("주제와 변인을 먼저 설정해주세요.")
            else:
                with st.spinner("논문 검색 중..."):
                    refs = search_literature(t, v)
                    st.session_state['research_context']['references'] = refs
        
        st.text_area("검색 결과", value=st.session_state['research_context']['references'], height=500)

    with col_chat:
        render_chat_interface("3단계(검색)", st.session_state['research_context']['references'])


# ===========================================================
# [Tab 4] 본문 작성 (기존 기능 유지)
# ===========================================================
with tabs[4]:
    col_main, col_chat = st.columns([6, 4])
    
    with col_main:
        st.subheader("✍️ 4단계: 본문 작성")
        target_section = st.selectbox("작성 챕터", list(st.session_state['paper_sections'].keys()))
        
        if st.button(f"🤖 {target_section} 초안 생성", type="primary"):
            with st.spinner("작성 중..."):
                draft = write_paper_final(target_section, st.session_state['research_context']['references'])
                st.session_state['paper_sections'][target_section] = draft
                st.rerun()
        
        current_text = st.text_area(
            f"📝 {target_section} 편집기",
            value=st.session_state['paper_sections'][target_section],
            height=600
        )
        if st.button("💾 내용 저장"):
            st.session_state['paper_sections'][target_section] = current_text
            st.success("저장됨")

    with col_chat:
        render_chat_interface(f"4단계({target_section})", st.session_state['paper_sections'][target_section])


# ===========================================================
# [Tab 5] 참고문헌 (기존 기능 유지)
# ===========================================================
with tabs[5]:
    col_main, col_chat = st.columns([6, 4])
    
    with col_main:
        st.subheader("📚 5단계: APA 참고문헌")
        if st.button("✨ 변환 및 정렬", type="primary"):
            if not st.session_state['research_context']['references']:
                st.error("검색 결과가 없습니다.")
            else:
                with st.spinner("정렬 중..."):
                    apa = organize_references_apa(st.session_state['research_context']['references'])
                    st.markdown(apa)
                    st.code(apa)

    with col_chat:
        render_chat_interface("5단계(참고문헌)", "APA 변환 작업")