import streamlit as st
import openai
import google.generativeai as genai

# -----------------------------------------------------------
# 기본 설정
# -----------------------------------------------------------
st.set_page_config(page_title="MJP 논문 비서 (Hybrid)", layout="wide")

# -----------------------------------------------------------
# 로그인 & API 설정
# -----------------------------------------------------------
with st.sidebar:
    st.header("🔐 연구실 입장")
    code = st.text_input("비밀번호", type="password")
    if code not in st.secrets["ACCESS_CODES"]:
        st.warning("비밀번호를 입력하세요.")
        st.stop()
    st.success("로그인 성공!")

# API 키 연결
openai.api_key = st.secrets["OPENAI_API_KEY"]
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# -----------------------------------------------------------
# 1. Gemini: 자료 검색 기능
# -----------------------------------------------------------
def search_with_gemini(query):
    try:
        # 최신 모델 사용 (라이브러리 업데이트 필수)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(f"""
        당신은 전문 연구원입니다. 다음 주제에 대해 논문에 사용할 수 있는
        '학술적 이론'과 '최신 선행 연구'를 찾아서 상세히 요약해주세요.
        
        주제: {query}
        """)
        return response.text
    except Exception as e:
        return f"Gemini 검색 중 오류가 발생했습니다: {e}"

# -----------------------------------------------------------
# 2. GPT: 논문 작성 기능
# -----------------------------------------------------------
def write_with_gpt(part, context, memo):
    try:
        prompt = f"""
        [역할]: 심리학 논문 전문 에디터
        [작성 챕터]: {part}
        [참고 자료(Gemini 검색 결과)]: {context}
        [사용자 아이디어]: {memo}
        
        위 내용을 통합하여 심리학 논문의 '{part}' 파트를 작성하세요.
        문체는 APA 스타일을 엄격히 준수하고, 학술적이고 건조하게 서술하세요.
        """
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"GPT 작성 중 오류가 발생했습니다: {e}"

# -----------------------------------------------------------
# 화면 구성 (UI)
# -----------------------------------------------------------
st.title("🤖 MJP: Gemini x GPT 협업 시스템")
st.markdown("---")

col1, col2 = st.columns(2)

# 왼쪽: Gemini 영역
with col1:
    st.header("🔍 1. Gemini (자료 조사)")
    topic = st.text_input("연구 주제를 입력하세요")
    if st.button("자료 검색 시작"):
        with st.spinner("Gemini가 논문을 읽고 있습니다..."):
            result = search_with_gemini(topic)
            st.text_area("검색 결과", result, height=600)
            st.session_state['search_data'] = result  # 기억하기

# 오른쪽: GPT 영역
with col2:
    st.header("✍️ 2. GPT (논문 작성)")
    part = st.selectbox("작성할 챕터", ["서론", "이론적 배경", "연구 방법", "결과", "논의"])
    memo = st.text_area("추가 아이디어/통계 수치")
    
    if st.button("초안 작성 시작"):
        # Gemini가 찾은 자료 가져오기
        context_data = st.session_state.get('search_data', '검색된 자료 없음')
        
        with st.spinner("GPT가 글을 쓰고 있습니다..."):
            draft = write_with_gpt(part, context_data, memo)
            st.text_area("작성 결과", draft, height=600)