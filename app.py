import streamlit as st
import openai
import google.generativeai as genai

# -----------------------------------------------------------
# 1. 기본 설정 & 세션 초기화
# -----------------------------------------------------------
st.set_page_config(page_title="MJP 연구 설계 파트너", layout="wide")

# 데이터를 페이지끼리 공유하기 위한 저장소 초기화
if 'research_context' not in st.session_state:
    st.session_state['research_context'] = {
        'topic': '',
        'variables': '',
        'method': '',
        'references': ''
    }

# -----------------------------------------------------------
# 2. 사이드바: 로그인 & 설정
# -----------------------------------------------------------
with st.sidebar:
    st.header("🔐 연구실 입장")
    code = st.text_input("비밀번호", type="password")
    if code not in st.secrets["ACCESS_CODES"]:
        st.warning("연구원 접속 권한이 필요합니다.")
        st.stop()
    st.success("시스템 가동 중 (Research Mode)")
    
    # 모델 확인 (비상용)
    with st.expander("🛠️ 시스템 상태"):
        if st.button("Gemini 모델 점검"):
            try:
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                st.write(models)
            except:
                st.error("키 연결 확인 필요")

# API 키 연결
openai.api_key = st.secrets["OPENAI_API_KEY"]
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# -----------------------------------------------------------
# 3. AI 두뇌 정의 (각 단계별 전문가)
# -----------------------------------------------------------

# [Brain 1] 변인 설정 컨설턴트 (GPT)
def consult_variables(topic):
    prompt = f"""
    당신은 심리학 연구 방법론 전문가입니다.
    사용자가 입력한 관심 주제: '{topic}'
    
    이 주제를 연구하기 위한 적절한 '변인 구조'를 3가지 옵션으로 제안해주세요.
    각 옵션은 다음을 포함해야 합니다:
    1. 독립변인 (IV)
    2. 종속변인 (DV)
    3. 매개변인 또는 조절변인 (Mediator/Moderator)
    4. 연구 가설 예시 1개
    
    출력 형식은 깔끔하게 정리해서 보여주세요.
    """
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# [Brain 2] 연구 방법론 설계자 (GPT)
def design_methodology(vars_text):
    prompt = f"""
    당신은 통계 분석 및 척도 전문가입니다.
    확정된 변인 구조:
    {vars_text}
    
    위 변인들을 측정하고 분석하기 위한 구체적인 방법을 제안하세요:
    1. 각 변인을 측정할 수 있는 신뢰도 높은 척도(Scale) 추천 (구체적인 척도명 기재)
    2. 데이터 수집 대상 및 절차
    3. 분석 방법 (예: 중다회귀분석, 구조방정식 등)
    """
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# [Brain 3] 선행 연구 탐색기 (Gemini 2.5)
def search_literature(topic, vars_text):
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
        주제: {topic}
        변인: {vars_text}
        
        위 연구를 뒷받침할 수 있는 '최신 선행 연구(2020-2026)'와 '핵심 이론'을 찾아주세요.
        특히 제안된 변인 간의 관계를 지지하는 연구들을 중심으로 요약해주세요.
        """
        response = model.generate_content(prompt)
        return response.text
    except:
        # 2.5가 안되면 pro로 자동 전환
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        return response.text

# [Brain 4] 논문 작성기 (GPT)
def write_paper_final(section, context_data):
    prompt = f"""
    [역할]: APA 스타일 심리학 논문 작성
    [작성 챕터]: {section}
    
    [활용할 연구 데이터]:
    - 주제: {st.session_state['research_context']['topic']}
    - 변인 설정: {st.session_state['research_context']['variables']}
    - 연구 방법: {st.session_state['research_context']['method']}
    - 선행 연구: {context_data}
    
    위 정보를 모두 종합하여, 논문의 '{section}' 파트를 학술적으로 서술하세요.
    """
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# -----------------------------------------------------------
# 4. 화면 구성 (탭 방식 도입)
# -----------------------------------------------------------
st.title("🎓 MJP: 심리학 연구 설계 및 작성 시스템")
st.info("💡 연구 설계(변인) -> 방법론 -> 자료 조사 -> 논문 작성 순서로 진행하세요.")

# 탭 만들기
tab1, tab2, tab3, tab4 = st.tabs(["1. 변인 설정", "2. 연구 방법", "3. 선행 연구", "4. 논문 작성"])

# --- [Tab 1] 변인 설정 ---
with tab1:
    st.header("🧠 1단계: 무엇을 연구할까요?")
    topic_input = st.text_input("관심 있는 키워드나 주제를 입력하세요 (예: 직무 스트레스와 이직 의도)")
    
    if st.button("변인 구조 제안받기"):
        with st.spinner("GPT가 연구 모형을 구상 중입니다..."):
            result = consult_variables(topic_input)
            st.success("추천 연구 모형입니다. 마음에 드는 것을 선택해 아래에 적어주세요.")
            st.markdown(result)
            st.session_state['research_context']['topic'] = topic_input

    st.subheader("📌 확정된 변인 (여기에 정리해서 적어주세요)")
    final_vars = st.text_area("예: IV-직무스트레스, DV-이직의도, MV-회복탄력성", height=100)
    if st.button("변인 확정 저장"):
        st.session_state['research_context']['variables'] = final_vars
        st.success("변인 설정이 저장되었습니다! 다음 탭으로 이동하세요.")

# --- [Tab 2] 연구 방법 ---
with tab2:
    st.header("📐 2단계: 어떻게 측정할까요?")
    st.write(f"현재 설정된 변인: **{st.session_state['research_context']['variables']}**")
    
    if st.button("방법론 및 척도 추천받기"):
        if not st.session_state['research_context']['variables']:
            st.error("1단계에서 변인을 먼저 확정해주세요!")
        else:
            with st.spinner("적절한 척도와 분석 방법을 찾는 중..."):
                method_result = design_methodology(st.session_state['research_context']['variables'])
                st.markdown(method_result)
    
    st.subheader("📌 확정된 연구 방법")
    final_method = st.text_area("사용할 척도와 분석 방법을 요약해 주세요", height=100)
    if st.button("방법론 확정 저장"):
        st.session_state['research_context']['method'] = final_method
        st.success("방법론이 저장되었습니다! 다음 탭으로 이동하세요.")

# --- [Tab 3] 선행 연구 ---
with tab3:
    st.header("🔍 3단계: 근거 자료 찾기 (Gemini)")
    
    if st.button("관련 선행 연구 검색"):
        topic = st.session_state['research_context']['topic']
        vars_text = st.session_state['research_context']['variables']
        
        if not topic or not vars_text:
            st.error("앞 단계의 설정이 완료되지 않았습니다.")
        else:
            with st.spinner("Gemini 2.5가 논문을 검색 중입니다..."):
                refs = search_literature(topic, vars_text)
                st.text_area("검색 결과", refs, height=500)
                st.session_state['research_context']['references'] = refs

# --- [Tab 4] 논문 작성 ---
with tab4:
    st.header("✍️ 4단계: 논문 쓰기 (종합)")
    
    section = st.selectbox("작성할 챕터", ["서론 (연구의 필요성)", "이론적 배경", "연구 방법", "결과 (예상)", "논의"])
    
    if st.button("AI 초안 작성 시작"):
        # 저장된 모든 맥락을 가져옴
        context = st.session_state['research_context']['references']
        
        if not context:
            st.warning("3단계에서 선행 연구 검색을 먼저 해주세요. (근거 없는 글쓰기는 위험합니다)")
        else:
            with st.spinner(f"설계된 내용(변인, 방법)을 바탕으로 '{section}' 작성 중..."):
                draft = write_paper_final(section, context)
                st.markdown(draft)