import streamlit as st
import openai
import google.generativeai as genai

# -----------------------------------------------------------
# 1. 기본 설정 & 세션 초기화
# -----------------------------------------------------------
st.set_page_config(page_title="MJP 연구 파트너 (Pro Layout)", layout="wide")

# 저장소 초기화
if 'paper_sections' not in st.session_state:
    st.session_state['paper_sections'] = {
        "서론": "", "이론적 배경": "", "연구 방법": "", "결과": "", "논의": ""
    }

if 'research_context' not in st.session_state:
    st.session_state['research_context'] = {
        'topic': '',
        'variables_options': [], # 제안된 변인 옵션들을 저장할 곳
        'variables': '',
        'method': '',
        'references': ''
    }

if "messages" not in st.session_state:
    st.session_state.messages = []

# -----------------------------------------------------------
# 2. 사이드바: 로그인 & 설정
# -----------------------------------------------------------
with st.sidebar:
    st.header("🔐 연구실 입장")
    code = st.text_input("비밀번호", type="password")
    if code not in st.secrets["ACCESS_CODES"]:
        st.warning("접근 권한이 필요합니다.")
        st.stop()
    
    st.success("System Online")
    
    if st.button("🗑️ 대화 내용 지우기"):
        st.session_state.messages = []
        st.rerun()

# API 키 연결
openai.api_key = st.secrets["OPENAI_API_KEY"]
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# -----------------------------------------------------------
# 3. AI 두뇌 (기능 정의)
# -----------------------------------------------------------

def consult_variables_options(topic):
    # [핵심] 클릭 선택을 위해 AI에게 "옵션 3개만 딱 줘"라고 시킴 (구분자 ||| 사용)
    prompt = f"""
    주제 '{topic}'에 적합한 변인 구조(독립/종속/매개 등)를 3가지 제안해주세요.
    각 옵션은 '|||'로 구분해서 출력하세요. 설명은 짧게 핵심만.
    예시:
    1안: IV-A, DV-B, MV-C ||| 2안: IV-X, DV-Y... ||| 3안: ...
    """
    response = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    # 텍스트를 ||| 기준으로 쪼개서 리스트로 만듦
    options = response.choices[0].message.content.split("|||")
    return [opt.strip() for opt in options if opt.strip()]

def design_methodology(vars_text):
    prompt = f"변인 '{vars_text}'을 측정할 척도와 통계 분석 방법을 제안해줘."
    response = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content

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
# 4. 화면 구성 (탭 5개 - 채팅 탭을 4단계로 통합!)
# -----------------------------------------------------------
st.title("🎓 MJP 연구 파트너 (Dual Mode)")

tabs = st.tabs(["1. 변인 선택", "2. 방법 설계", "3. 자료 검색", "4. 작성 & 피드백", "5. 참고문헌"])

# [Tab 1] 변인 (클릭 선택 기능 추가!)
with tabs[0]:
    st.header("🧠 1단계: 변인 아이디어 선택")
    topic = st.text_input("연구 주제")
    
    if st.button("변인 옵션 제안받기"):
        with st.spinner("GPT가 3가지 연구 모형을 구상 중..."):
            options = consult_variables_options(topic)
            st.session_state['research_context']['variables_options'] = options
            st.session_state['research_context']['topic'] = topic
    
    # 옵션이 생성되었으면 선택지(Radio Button)를 보여줌
    if st.session_state['research_context']['variables_options']:
        st.subheader("마음에 드는 연구 모형을 선택하세요:")
        choice = st.radio(
            "아래 옵션 중 하나를 클릭하세요:",
            st.session_state['research_context']['variables_options']
        )
        
        st.info(f"선택된 모형: {choice}")
        
        # 선택하면 자동으로 확정 칸에 채워넣기
        if st.button("이 모형으로 확정 및 저장"):
            st.session_state['research_context']['variables'] = choice
            st.success("변인이 저장되었습니다! 2단계로 넘어가세요.")

# [Tab 2] 방법
with tabs[1]:
    st.header("📐 2단계: 방법론")
    if st.button("방법론 제안"): st.markdown(design_methodology(st.session_state['research_context']['variables']))
    final_method = st.text_area("방법론 확정", key="m_input")
    if st.button("방법 저장"): st.session_state['research_context']['method'] = final_method

# [Tab 3] 검색
with tabs[2]:
    st.header("🔍 3단계: 선행 연구")
    if st.button("Gemini 검색"):
        refs = search_literature(st.session_state['research_context']['topic'], st.session_state['research_context']['variables'])
        st.session_state['research_context']['references'] = refs
        st.text_area("검색 결과", refs)

# -----------------------------------------------------------
# [Tab 4] 여기가 핵심! (에디터 + 챗봇 동시 화면)
# -----------------------------------------------------------
with tabs[3]:
    st.header("✍️ 4단계: 실시간 작성 및 피드백")
    
    # 화면을 6:4 비율로 나눔 (왼쪽: 글쓰기 / 오른쪽: 채팅)
    col_editor, col_chat = st.columns([6, 4])
    
    # --- [왼쪽] 논문 에디터 ---
    with col_editor:
        st.subheader("📝 원고지 (Editor)")
        target_section = st.selectbox("작성할 챕터", list(st.session_state['paper_sections'].keys()))
        
        if st.button("🤖 AI 초안 생성 (왼쪽)"):
            with st.spinner("작성 중..."):
                draft = write_paper_final(target_section, st.session_state['research_context']['references'])
                st.session_state['paper_sections'][target_section] = draft
        
        # 에디터 창
        current_text = st.text_area(
            "내용 편집",
            value=st.session_state['paper_sections'][target_section],
            height=600
        )
        
        if st.button("💾 내용 저장"):
            st.session_state['paper_sections'][target_section] = current_text
            st.success("저장됨")

    # --- [오른쪽] AI 지도교수 (채팅) ---
    with col_chat:
        st.subheader("💬 지도교수 피드백")
        st.info("왼쪽 글을 보고 수정사항을 말하세요.")
        
        # 채팅창 스타일링 (높이 제한)
        with st.container(height=500):
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        # 채팅 입력
        if prompt := st.chat_input("예: 서론의 두 번째 문단 통계가 부족해."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # AI 답변 생성
            # [중요] 현재 에디터에 있는 글을 맥락으로 같이 보냄
            full_context = f"""
            [현재 사용자가 보고 있는 글 ({target_section})]:
            {st.session_state['paper_sections'][target_section]}
            
            [사용자 요청]: {prompt}
            """
            
            # 챗봇 응답 생성
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "당신은 논문 지도교수입니다. 사용자의 요청에 따라 왼쪽의 글을 수정하거나 조언을 해주세요."}] + 
                         [{"role": "user", "content": full_context}]
            )
            
            ai_msg = response.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": ai_msg})
            st.rerun() # 채팅 올라가게 새로고침

# [Tab 5] 참고문헌
with tabs[4]:
    st.header("📚 5단계: 참고문헌")
    if st.button("APA 변환"):
        st.markdown(organize_references_apa(st.session_state['research_context']['references']))