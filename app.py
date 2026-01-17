import streamlit as st
import openai
import google.generativeai as genai

# -----------------------------------------------------------
# 1. 스타일 & 기본 설정
# -----------------------------------------------------------
st.set_page_config(page_title="MJP Pro: 연구 파트너", layout="wide")

# [디자인] 버튼 색상 강제 변경 (CSS)
# 일반 버튼은 파란색 계열, 마우스 올리면 진해지게 설정
st.markdown("""
<style>
    div.stButton > button:first-child {
        background-color: #0068c9;
        color: white;
        border-radius: 8px;
        border: none;
        font-weight: bold;
    }
    div.stButton > button:first-child:hover {
        background-color: #004b91;
        color: white;
    }
    /* 탭 글씨 크기 키우기 */
    button[data-baseweb="tab"] {
        font-size: 16px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------
# 2. 데이터 저장소(세션) 초기화
# -----------------------------------------------------------
if 'paper_sections' not in st.session_state:
    st.session_state['paper_sections'] = {
        "서론": "", "이론적 배경": "", "연구 방법": "", "결과": "", "논의": ""
    }

if 'research_context' not in st.session_state:
    st.session_state['research_context'] = {
        'topic': '',
        'variables_options': [], 
        'variables': '', # 확정된 변인
        'method_options': [], # [NEW] 방법론 옵션들
        'method': '',    # 확정된 방법론
        'references': ''
    }

# 각 단계별 채팅 기록을 따로 저장할까 하다가, 연속성을 위해 통합 저장
if "messages" not in st.session_state:
    st.session_state.messages = []

# -----------------------------------------------------------
# 3. 로그인 & 설정
# -----------------------------------------------------------
with st.sidebar:
    st.header("🔐 연구실 입장")
    code = st.text_input("비밀번호", type="password")
    if code not in st.secrets["ACCESS_CODES"]:
        st.warning("연구원 권한이 필요합니다.")
        st.stop()
    st.success("System Online")
    
    if st.button("🗑️ 대화 내용 초기화", type="primary"):
        st.session_state.messages = []
        st.rerun()

openai.api_key = st.secrets["OPENAI_API_KEY"]
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# -----------------------------------------------------------
# 4. AI 기능 정의 (옵션 생성기 강화)
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
    # [NEW] 방법론도 3가지 옵션으로 제안받기
    prompt = f"""
    변인 구조: '{vars_text}'
    이 변인을 연구하기 위한 '척도(측정도구)'와 '통계 분석 방법' 조합을 3가지 제안해주세요.
    각 옵션은 '|||'로 구분해서 출력하세요.
    예: 1안: (척도 A, B + 회귀분석) ||| 2안: (척도 A, B + 구조방정식) ||| 3안: ...
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
# 5. 공통 컴포넌트: 챗봇 인터페이스 (모든 탭에 들어갈 녀석)
# -----------------------------------------------------------
def render_chat_interface(stage_name, context_text):
    st.markdown(f"#### 💬 AI 피드백 ({stage_name})")
    st.caption("왼쪽 내용을 보며 질문하거나 수정을 요청하세요.")
    
    # 채팅창 높이 고정
    with st.container(height=450):
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    if prompt := st.chat_input(f"{stage_name}에 대해 질문하기..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # AI에게 보낼 맥락 구성
        full_context = f"""
        [현재 작업 단계]: {stage_name}
        [사용자가 보고 있는 내용]: 
        {context_text[:1000]}... (생략)
        
        [사용자 질문]: {prompt}
        """
        
        # 챗봇 응답
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "당신은 논문 지도교수입니다. 사용자의 작업물을 검토하고 조언하세요."}] + 
                     [{"role": "user", "content": full_context}]
        )
        ai_msg = response.choices[0].message.content
        st.session_state.messages.append({"role": "assistant", "content": ai_msg})
        st.rerun()

# -----------------------------------------------------------
# 6. 메인 화면 구성
# -----------------------------------------------------------
st.title("🎓 MJP Pro: 연구 파트너")

tabs = st.tabs(["1. 변인 설정", "2. 방법론 설계", "3. 자료 검색", "4. 본문 작성", "5. 참고문헌"])

# ===========================================================
# [Tab 1] 변인 설정 (입력 우선 + 선택 옵션)
# ===========================================================
with tabs[0]:
    col_main, col_chat = st.columns([6, 4])
    
    with col_main:
        st.subheader("🧠 1단계: 변인 확정")
        
        # [1] 사용자가 직접 입력하는 곳 (가장 위!)
        st.caption("아래 칸에 연구할 변인을 직접 적거나, 밑에서 AI 제안을 골라 채워넣으세요.")
        final_vars = st.text_area("📌 최종 변인 입력란", 
                                value=st.session_state['research_context']['variables'], 
                                height=150,
                                key="input_vars")
        
        # 저장 버튼 (눈에 띄게)
        if st.button("✅ 변인 내용 저장하기", type="primary"):
            st.session_state['research_context']['variables'] = final_vars
            st.success("변인이 저장되었습니다! (오른쪽 채팅창에서 점검해보세요)")

        st.markdown("---")
        
        # [2] AI 제안 영역 (아래쪽)
        st.info("💡 아이디어가 필요하신가요? 아래에서 AI의 제안을 받아보세요.")
        topic = st.text_input("연구 주제 키워드 (예: 직무 스트레스)")
        
        if st.button("🤖 변인 구조 3가지 제안받기"):
            with st.spinner("AI가 아이디어를 짜내는 중..."):
                options = consult_variables_options(topic)
                st.session_state['research_context']['variables_options'] = options
                st.session_state['research_context']['topic'] = topic
        
        # 옵션이 있으면 보여줌
        if st.session_state['research_context']['variables_options']:
            choice = st.radio("마음에 드는 안을 선택하세요:", st.session_state['research_context']['variables_options'])
            
            if st.button("🔼 위 입력란에 적용하기"):
                # 선택한 내용을 위쪽 text_area에 반영 (세션 상태 업데이트)
                st.session_state['research_context']['variables'] = choice
                st.rerun() # 화면 새로고침해서 반영

    with col_chat:
        # 현재 입력된 변인을 맥락으로 채팅
        render_chat_interface("1단계(변인)", st.session_state['research_context']['variables'])


# ===========================================================
# [Tab 2] 방법론 설계 (입력 우선 + 선택 옵션 도입!)
# ===========================================================
with tabs[1]:
    col_main, col_chat = st.columns([6, 4])
    
    with col_main:
        st.subheader("📐 2단계: 연구 방법 확정")
        
        # [1] 사용자 입력란 (최우선)
        st.caption("사용할 척도와 분석 방법을 직접 적거나, AI 추천을 받으세요.")
        final_method = st.text_area("📌 최종 방법론 입력란", 
                                  value=st.session_state['research_context']['method'], 
                                  height=150,
                                  key="input_method")
        
        if st.button("✅ 방법론 내용 저장하기", type="primary", key="save_method"):
            st.session_state['research_context']['method'] = final_method
            st.success("방법론이 저장되었습니다!")

        st.markdown("---")
        
        # [2] AI 제안 영역
        st.info("💡 적절한 척도와 통계법을 추천해 드립니다.")
        
        # 1단계에서 정한 변인을 가져와서 보여줌
        current_vars = st.session_state['research_context']['variables']
        st.write(f"현재 설정된 변인: **{current_vars if current_vars else '(변인 미설정)'}**")
        
        if st.button("🤖 방법론 3가지 제안받기"):
            if not current_vars:
                st.error("1단계에서 변인을 먼저 정해주세요!")
            else:
                with st.spinner("통계 방법론 설계 중..."):
                    opts = design_methodology_options(current_vars)
                    st.session_state['research_context']['method_options'] = opts
        
        if st.session_state['research_context']['method_options']:
            method_choice = st.radio("가장 적절한 방법을 선택하세요:", st.session_state['research_context']['method_options'])
            
            if st.button("🔼 위 입력란에 적용하기", key="apply_method"):
                st.session_state['research_context']['method'] = method_choice
                st.rerun()

    with col_chat:
        render_chat_interface("2단계(방법론)", st.session_state['research_context']['method'])


# ===========================================================
# [Tab 3] 자료 검색 (Split View 적용)
# ===========================================================
with tabs[2]:
    col_main, col_chat = st.columns([6, 4])
    
    with col_main:
        st.subheader("🔍 3단계: 선행 연구 수집")
        
        if st.button("🚀 Gemini 검색 시작", type="primary"):
            # 주제와 변인 정보를 합쳐서 검색
            t = st.session_state['research_context']['topic']
            v = st.session_state['research_context']['variables']
            if not t or not v:
                st.warning("1단계에서 주제와 변인을 먼저 설정해야 정확한 검색이 됩니다.")
            else:
                with st.spinner("논문을 읽고 있습니다..."):
                    refs = search_literature(t, v)
                    st.session_state['research_context']['references'] = refs
        
        # 검색 결과 표시
        refs_content = st.session_state['research_context']['references']
        st.text_area("검색 결과 (Raw Data)", value=refs_content, height=500)

    with col_chat:
        render_chat_interface("3단계(검색)", st.session_state['research_context']['references'])


# ===========================================================
# [Tab 4] 본문 작성 (Split View 유지)
# ===========================================================
with tabs[3]:
    col_main, col_chat = st.columns([6, 4])
    
    with col_main:
        st.subheader("✍️ 4단계: 본문 작성")
        target_section = st.selectbox("작성할 챕터", list(st.session_state['paper_sections'].keys()))
        
        if st.button(f"🤖 {target_section} 초안 생성", type="primary"):
            with st.spinner("작성 중..."):
                draft = write_paper_final(target_section, st.session_state['research_context']['references'])
                st.session_state['paper_sections'][target_section] = draft
                st.rerun()
        
        # 에디터
        current_text = st.text_area(
            f"📝 {target_section} 편집기",
            value=st.session_state['paper_sections'][target_section],
            height=600
        )
        
        if st.button("💾 내용 저장"):
            st.session_state['paper_sections'][target_section] = current_text
            st.success("저장되었습니다.")

    with col_chat:
        # 현재 에디터에 있는 글을 맥락으로 전달
        render_chat_interface(f"4단계({target_section})", st.session_state['paper_sections'][target_section])


# ===========================================================
# [Tab 5] 참고문헌 (Split View 적용)
# ===========================================================
with tabs[4]:
    col_main, col_chat = st.columns([6, 4])
    
    with col_main:
        st.subheader("📚 5단계: APA 참고문헌 정리")
        if st.button("✨ APA 스타일로 변환 및 정렬", type="primary"):
            if not st.session_state['research_context']['references']:
                st.error("3단계 검색 결과가 없습니다.")
            else:
                with st.spinner("정렬 중..."):
                    apa_list = organize_references_apa(st.session_state['research_context']['references'])
                    st.markdown(apa_list)
                    st.code(apa_list) # 복사용

    with col_chat:
        render_chat_interface("5단계(참고문헌)", "APA 스타일 변환 작업 중...")