import streamlit as st
import openai
import google.generativeai as genai

# -----------------------------------------------------------
# 기본 설정
# -----------------------------------------------------------
st.set_page_config(page_title="MJP 논문 비서v2", layout="wide")

# -----------------------------------------------------------
# 로그인 시스템
# -----------------------------------------------------------
with st.sidebar:
    st.header("🔐 연구실 입장")
    code = st.text_input("비밀번호를 입력하세요", type="password")
    
    if code in st.secrets["ACCESS_CODES"]:
        st.success("로그인 성공!")
    else:
        st.warning("비밀번호를 입력해주세요.")
        st.stop()

# -----------------------------------------------------------
# API 키 연결
# -----------------------------------------------------------
openai.api_key = st.secrets["OPENAI_API_KEY"]
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# -----------------------------------------------------------
# AI 기능 (검색 & 작성)
# -----------------------------------------------------------
def search_paper(query):
    # Gemini: 논문 검색
    model = genai.GenerativeModel('gemini-1.5-flas')
    response = model.generate_content(f"다음 주제에 대한 학술적 이론과 최신 선행 연구를 찾아서 요약해줘: {query}")
    return response.text

def write_paper(part, context, memo):
    # GPT: 논문 작성 (APA 스타일)
    prompt = f"""
    [작성할 챕터]: {part}
    [참고할 선행 연구]: {context}
    [사용자 메모]: {memo}
    
    위 내용을 바탕으로 심리학 논문의 '{part}' 부분을 작성해.
    문체는 APA 양식을 준수하고, 매우 학술적이고 건조하게 써줘.
    """
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "너는 심리학 논문 전문 에디터야."},
                  {"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# -----------------------------------------------------------
# 화면 구성
# -----------------------------------------------------------
st.title("🎓 MJP: 심리학 논문 작성 파트너")

col1, col2 = st.columns(2)

# 왼쪽: 자료 찾기
with col1:
    st.header("🔍 1. 자료 찾기 (Gemini)")
    topic = st.text_input("연구 주제 입력 (예: 직무 스트레스)")
    if st.button("논문 검색"):
        with st.spinner("자료 찾는 중..."):
            result = search_paper(topic)
            st.text_area("검색 결과", result, height=500)
            st.session_state['data'] = result

# 오른쪽: 논문 쓰기
with col2:
    st.header("✍️ 2. 본문 쓰기 (GPT)")
    section = st.selectbox("작성할 챕터", ["서론", "이론적 배경", "연구 방법", "결과", "논의"])
    memo = st.text_area("통계 수치나 아이디어 입력")
    
    if st.button("AI 초안 작성"):
        ref = st.session_state.get('data', '없음')
        with st.spinner("논문 쓰는 중..."):
            draft = write_paper(section, ref, memo)
            st.text_area("작성 결과", draft, height=500)
        