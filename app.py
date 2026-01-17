import streamlit as st
import openai
import google.generativeai as genai

# -----------------------------------------------------------
# 1. 기본 설정 & 세션 초기화
# -----------------------------------------------------------
st.set_page_config(page_title="MJP 논문 마스터 (Full Ver.)", layout="wide")

# 데이터를 페이지끼리 공유하기 위한 저장소
if 'research_context' not in st.session_state:
    st.session_state['research_context'] = {
        'topic': '',
        'variables': '',
        'method': '',
        'references': ''  # 검색된 원본 자료들이 저장됨
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
    st.success("Research System Online")

# API 키 연결
openai.api_key = st.secrets["OPENAI_API_KEY"]
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# -----------------------------------------------------------
# 3. AI 두뇌 정의 (각 단계별 전문가)
# -----------------------------------------------------------

# [Brain 1] 변인 설정
def consult_variables(topic):
    prompt = f"""
    당신은 심리학 연구 방법론 전문가입니다. 주제: '{topic}'
    이 주제를 위한 '변인 구조(독립, 종속, 조절/매개)'를 3가지 옵션으로 제안하세요.
    """
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# [Brain 2] 연구 방법
def design_methodology(vars_text):
    prompt = f"""
    변인 구조: {vars_text}
    위 변인을 측정하기 위한 '척도(Scale)'와 '통계 분석 방법'을 구체적으로 제안하세요.
    """
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# [Brain 3] 선행 연구 검색 (Gemini 2.5)
def search_literature(topic, vars_text):
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
        주제: {topic}
        변인: {vars_text}
        위 연구와 관련된 '핵심 선행 연구(2020-2026)' 5개 이상과 '주요 이론'을 찾아주세요.
        각 연구의 저자, 연도, 주요 결과가 명확히 드러나게 요약해주세요.
        """
        response = model.generate_content(prompt)
        return response.text
    except:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        return response.text

# [Brain 4] 논문 작성
def write_paper_final(section, context_data):
    prompt = f"""
    [역할]: APA 스타일 심리학 논문 에디터
    [챕터]: {section}
    [선행 연구 데이터]: {context_data}
    
    위 정보를 바탕으로 논문의 '{section}' 파트를 학술적으로 서술하세요.
    인용 표기(예: Kim, 2023)를 정확히 포함하세요.
    """
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# [Brain 5] 참고문헌 정리기 (NEW!)
def organize_references_apa(raw_text):
    prompt = f"""
    [역할]: APA 참고문헌 서지 정보 전문가
    
    [입력된 원본 자료]:
    {raw_text}
    
    [작업 지시]:
    1. 위 텍스트에 언급된 모든 논문/저서를 추출하세요.
    2. 추출된 항목을 'APA 7판 양식'에 맞게 완벽하게 변환하세요.
    3. 정렬 순서:
       - 1순위: 저자명 알파벳 순 (A -> Z)
       - 2순위: 한글 저자 가나다 순 (ㄱ -> ㅎ)
       - (또는 APA 규정에 따라 통합 정렬)
    4. 출력 형식: 번호(1,2,3) 없이, 깔끔한 리스트 형태로 출력하세요.
    """
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# -----------------------------------------------------------
# 4. 화면 구성 (5단계 탭)
# -----------------------------------------------------------
st.title("🎓 MJP: 논문 완성 올인원 시스템")

# 탭 5개 생성
tabs = st.tabs(["1. 변인 설정", "2. 연구 방법", "3. 선행 연구", "4. 논문 작성", "5. 참고문헌(APA)"])

# [Tab 1] 변인
with tabs[0]:
    st.header("🧠 1단계: 변인 설계")
    topic = st.text_input("연구 주제 입력")
    if st.button("구조 제안"):
        with st.spinner("설계 중..."):
            res = consult_variables(topic)
            st.markdown(res)
            st.session_state['research_context']['topic'] = topic
    
    final_vars = st.text_area("📌 변인 확정 입력", height=100)
    if st.button("변인 저장"):
        st.session_state['research_context']['variables'] = final_vars
        st.success("저장 완료!")

# [Tab 2] 방법
with tabs[1]:
    st.header("📐 2단계: 방법론 설계")
    if st.button("척도 추천"):
        with st.spinner("분석 중..."):
            res = design_methodology(st.session_state['research_context']['variables'])
            st.markdown(res)
    
    final_method = st.text_area("📌 방법론 확정 입력", height=100)
    if st.button("방법 저장"):
        st.session_state['research_context']['method'] = final_method
        st.success("저장 완료!")

# [Tab 3] 선행 연구
with tabs[2]:
    st.header("🔍 3단계: 근거 자료 수집")
    if st.button("Gemini 검색 시작"):
        with st.spinner("논문 검색 중..."):
            refs = search_literature(st.session_state['research_context']['topic'], 
                                   st.session_state['research_context']['variables'])
            st.text_area("검색 결과 (원본)", refs, height=500)
            st.session_state['research_context']['references'] = refs  # 여기에 저장된 게 나중에 참고문헌이 됨

# [Tab 4] 논문 작성
with tabs[3]:
    st.header("✍️ 4단계: 본문 작성")
    section = st.selectbox("챕터", ["서론", "이론적 배경", "방법", "결과", "논의"])
    if st.button("초안 작성"):
        with st.spinner("집필 중..."):
            draft = write_paper_final(section, st.session_state['research_context']['references'])
            st.markdown(draft)

# [Tab 5] 참고문헌 (NEW!)
with tabs[4]:
    st.header("📚 5단계: 참고문헌 자동 정리 (APA)")
    st.info("3단계에서 검색된 자료들을 바탕으로 APA 양식 리스트를 생성합니다.")
    
    # 검색된 자료가 있는지 확인
    raw_refs = st.session_state['research_context']['references']
    
    if not raw_refs:
        st.warning("⚠️ 아직 3단계에서 선행 연구 검색을 하지 않았습니다. 자료가 있어야 정리를 하죠!")
    else:
        st.text_area("수집된 원본 자료", raw_refs, height=150, disabled=True)
        
        if st.button("APA 스타일로 변환 및 정렬"):
            with st.spinner("저자명 A-Z / 가나다 순으로 정렬 중입니다..."):
                apa_list = organize_references_apa(raw_refs)
                st.success("참고문헌 생성이 완료되었습니다!")
                st.markdown("### References")
                st.markdown(apa_list) # 여기가 진짜 결과물
                st.code(apa_list, language='markdown') # 복사하기 좋게 코드 블록으로도 제공