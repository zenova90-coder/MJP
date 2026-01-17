import streamlit as st
import openai
import google.generativeai as genai

# -----------------------------------------------------------
# 기본 설정
# -----------------------------------------------------------
st.set_page_config(page_title="MJP 논문 비서 (2026 Ver.)", layout="wide")

# -----------------------------------------------------------
# 로그인 & 설정
# -----------------------------------------------------------
with st.sidebar:
    st.header("🔐 연구실 입장")
    code = st.text_input("비밀번호", type="password")
    if code not in st.secrets["ACCESS_CODES"]:
        st.warning("비밀번호를 입력하세요.")
        st.stop()
    st.success("로그인 성공!")
    
    # 모델 확인용 (나중에 또 문제 생기면 눌러보세요)
    if st.button("모델 리스트 확인"):
        try:
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            st.write(models)
        except:
            st.error("키 확인 필요")

# API 키 연결
openai.api_key = st.secrets["OPENAI_API_KEY"]
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# -----------------------------------------------------------
# 1. Gemini: 자료 검색 (최신 2.5 버전 적용)
# -----------------------------------------------------------
def search_with_gemini(query):
    try:
        # [수정됨] 민주님 목록에 있는 최신 모델 사용!
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        response = model.generate_content(f"""
        당신은 심리학 연구원입니다. 다음 주제에 대한 
        '핵심 이론'과 '최신 선행 연구(2020~2026)'를 찾아서 요약해주세요.
        
        주제: {query}
        """)
        return response.text
    except Exception as e:
        return f"Gemini 오류: {e}\n(목록에 있는 다른 모델로 교체가 필요할 수 있습니다.)"

# -----------------------------------------------------------
# 2. GPT: 논문 작성
# -----------------------------------------------------------
def write_with_gpt(part, context, memo):
    try:
        prompt = f"""
        [역할]: 심리학 논문 전문 에디터
        [챕터]: {part}
        [참고 자료]: {context}
        [사용자 메모]: {memo}
        
        위 내용을 바탕으로 논문의 '{part}' 부분을 작성하세요.
        APA 양식을 준수하여 학술적으로 서술하세요.
        """
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"GPT 오류: {e}"

# -----------------------------------------------------------
# UI 구성
# -----------------------------------------------------------
st.title("🎓 MJP: 2026 최신 심리학 논문 시스템")
st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.header("🔍 1. 자료 찾기 (Gemini 2.5)")
    topic = st.text_input("연구 주제 입력 (예: 도파민 중독)")
    if st.button("자료 검색 시작"):
        with st.spinner("Gemini 2.5가 최신 자료를 찾는 중..."):
            result = search_with_gemini(topic)
            st.text_area("검색 결과", result, height=600)
            st.session_state['data'] = result

with col2:
    st.header("✍️ 2. 본문 쓰기 (GPT)")
    part = st.selectbox("챕터 선택", ["서론", "이론적 배경", "연구 방법", "결과", "논의"])
    memo = st.text_area("추가 아이디어")
    
    if st.button("초안 작성"):
        ref = st.session_state.get('data', '없음')
        with st.spinner("GPT가 논문을 작성 중..."):
            draft = write_with_gpt(part, ref, memo)
            st.text_area("작성 결과", draft, height=600)