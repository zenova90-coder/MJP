import streamlit as st
import openai
import google.generativeai as genai

# -----------------------------------------------------------
# 기본 설정
# -----------------------------------------------------------
st.set_page_config(page_title="MJP 논문 비서 (Final)", layout="wide")

# -----------------------------------------------------------
# 로그인 & 설정
# -----------------------------------------------------------
with st.sidebar:
    st.header("🔐 연구실 입장")
    code = st.text_input("비밀번호", type="password")
    if code not in st.secrets["ACCESS_CODES"]:
        st.warning("비밀번호를 입력하세요.")
        st.stop()
    st.success(f"로그인 성공! (v{genai.__version__})")
    
    # [진단] 사용 가능한 모델 확인하기
    if st.button("내 모델 확인하기"):
        try:
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            st.write("사용 가능 모델:", models)
        except Exception as e:
            st.error(f"키 확인 필요: {e}")

# API 키 연결
openai.api_key = st.secrets["OPENAI_API_KEY"]
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# -----------------------------------------------------------
# 1. Smart Gemini: 알아서 모델 찾기
# -----------------------------------------------------------
def search_with_gemini(query):
    try:
        # 1순위: 1.5-flash (최신)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(f"학술 검색: {query}")
        return response.text
    except:
        try:
            # 2순위: gemini-pro (표준)
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(f"학술 검색: {query}")
            return response.text
        except Exception as e:
            return f"검색 실패. (원인: {e})\n\n[해결책] 왼쪽 사이드바의 '내 모델 확인하기'를 눌러보세요."

# -----------------------------------------------------------
# 2. GPT: 논문 작성
# -----------------------------------------------------------
def write_with_gpt(part, context, memo):
    try:
        prompt = f"""
        [역할]: 심리학 논문 전문 에디터
        [챕터]: {part}
        [참고 자료]: {context}
        [메모]: {memo}
        
        위 내용을 바탕으로 심리학 논문의 '{part}' 부분을 작성하세요.
        APA 양식을 준수하여 학술적으로 서술하세요.
        """
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"GPT 작성 오류: {e}"

# -----------------------------------------------------------
# UI 구성
# -----------------------------------------------------------
st.title("🎓 MJP: 자동화 논문 시스템 (Auto)")
st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.header("🔍 1. 자료 찾기 (Gemini)")
    topic = st.text_input("연구 주제 입력")
    if st.button("자료 검색 시작"):
        with st.spinner("Gemini가 가능한 모델을 찾아서 검색 중..."):
            result = search_with_gemini(topic)
            st.text_area("검색 결과", result, height=600)
            st.session_state['data'] = result

with col2:
    st.header("✍️ 2. 본문 쓰기 (GPT)")
    part = st.selectbox("챕터 선택", ["서론", "이론적 배경", "방법", "결과", "논의"])
    memo = st.text_area("아이디어 입력")
    
    if st.button("초안 작성"):
        ref = st.session_state.get('data', '없음')
        with st.spinner("GPT가 작성 중..."):
            draft = write_with_gpt(part, ref, memo)
            st.text_area("작성 결과", draft, height=600)