import streamlit as st
import openai
import google.generativeai as genai

# -----------------------------------------------------------
# 1. 기본 설정 & 세션(기억 저장소) 초기화
# -----------------------------------------------------------
st.set_page_config(page_title="MJP: Interactive Research Partner", layout="wide")

# [핵심] 논문의 각 챕터 내용을 따로따로 기억하는 저장소
if 'paper_sections' not in st.session_state:
    st.session_state['paper_sections'] = {
        "서론": "",
        "이론적 배경": "",
        "연구 방법": "",
        "결과": "",
        "논의": ""
    }

# 연구 설계 데이터 저장소
if 'research_context' not in st.session_state:
    st.session_state['research_context'] = {
        'topic': '',
        'variables': '',
        'method': '',
        'references': ''
    }

# 채팅 기록 저장소
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

def consult_variables(topic):
    prompt = f"주제 '{topic}'에 적합한 독립, 종속, 조절/매개 변인 구조를 3개 제안해줘."
    response = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content

def design_methodology(vars_text):
    prompt = f"변인 '{vars_text}'을 측정할 척도와 통계 분석 방법을 구체적으로 제안해줘."
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
    # [수정] 더 구체적이고 논리적인 글쓰기를 위한 지시 강화
    prompt = f"""
    [역할]: 당신은 매우 비판적이고 논리적인 심리학 논문 작성자입니다.
    [작업]: '{section}' 챕터 초안 작성.
    [근거 데이터]: {context_data}
    
    [필수 지침]:
    1. 추상적인 표현(예: '영향을 미쳤다')을 지양하고, 구체적인 기제나 논리를 서술할 것.
    2. 문장 간의 인과관계가 명확해야 함. 비약이 없도록 주의할 것.
    3. APA 스타일을 철저히 준수할 것.
    """
    response = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content

def organize_references_apa(raw_text):
    prompt = f"다음 텍스트에서 참고문헌을 추출하여 APA 7판 양식으로 변환하고 알파벳/가나다 순 정렬해줘:\n{raw_text}"
    response = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    return response.choices[0].message.content

# -----------------------------------------------------------
# 4. 화면 구성 (탭 6개)
# -----------------------------------------------------------
st.title("🎓 MJP: 대화형 논문 작성 시스템 V2")

tabs = st.tabs(["1. 변인", "2. 방법", "3. 검색", "4. 본문 작성(저장)", "5. 참고문헌", "💬 6. AI 피드백"])

# [Tab 1~3] 설정 단계
with tabs[0]:
    topic = st.text_input("연구 주제")
    if st.button("변인 제안"):
        st.markdown(consult_variables(topic))
        st.session_state['research_context']['topic'] = topic
    final_vars = st.text_area("변인 확정", key="v_input")
    if st.button("변인 저장"): st.session_state['research_context']['variables'] = final_vars

with tabs[1]:
    if st.button("방법론 제안"): st.markdown(design_methodology(st.session_state['research_context']['variables']))
    final_method = st.text_area("방법론 확정", key="m_input")
    if st.button("방법 저장"): st.session_state['research_context']['method'] = final_method

with tabs[2]:
    if st.button("Gemini 검색"):
        refs = search_literature(st.session_state['research_context']['topic'], st.session_state['research_context']['variables'])
        st.session_state['research_context']['references'] = refs
        st.text_area("검색 결과", refs)

# -----------------------------------------------------------
# [Tab 4] 본문 작성 (여기가 민주님 요청대로 대폭 수정됨!)
# -----------------------------------------------------------
with tabs[3]:
    st.header("✍️ 4단계: 본문 작성 (챕터별 독립 저장)")
    
    # 1. 작성할 챕터 선택
    target_section = st.selectbox("작성/편집할 챕터를 선택하세요", list(st.session_state['paper_sections'].keys()))
    
    col_a, col_b = st.columns([1, 5])
    
    # 2. AI 초안 생성 버튼
    with col_a:
        if st.button(f"🤖 AI 초안 생성"):
            with st.spinner(f"{target_section} 작성 중..."):
                # 검색된 자료가 없으면 경고
                ref_data = st.session_state['research_context']['references']
                if not ref_data:
                    st.warning("3단계 검색 자료가 없습니다! 그냥 쓰면 내용이 부실할 수 있습니다.")
                
                draft = write_paper_final(target_section, ref_data)
                # 생성된 내용을 해당 챕터 서랍에 넣기
                st.session_state['paper_sections'][target_section] = draft
                st.success("생성 완료!")

    # 3. 에디터 (생성된 글을 수정하거나 볼 수 있는 곳)
    st.markdown(f"### 📝 {target_section} 편집기")
    # 서랍에서 꺼내와서 보여줌
    current_text = st.text_area(
        label="내용을 직접 수정할 수 있습니다.",
        value=st.session_state['paper_sections'][target_section],
        height=500
    )
    
    # 4. 저장 버튼
    if st.button(f"💾 {target_section} 내용 저장"):
        st.session_state['paper_sections'][target_section] = current_text
        st.success(f"{target_section} 내용이 안전하게 저장되었습니다.")

# [Tab 5] 참고문헌
with tabs[4]:
    if st.button("APA 변환"):
        st.markdown(organize_references_apa(st.session_state['research_context']['references']))

# -----------------------------------------------------------
# [Tab 6] AI 실시간 피드백 (대화형)
# -----------------------------------------------------------
with tabs[5]:
    st.header("💬 AI 논문 지도 교수 (피드백 & 수정)")
    st.info("4단계에서 쓴 글이 마음에 안 들면 여기서 고쳐달라고 하세요. (예: '서론의 논리적 비약을 수정해줘')")

    # 채팅 기록 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 사용자 입력
    if prompt := st.chat_input("수정 요청 사항을 입력하세요..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            
            # [중요] AI에게 현재까지 작성된 '모든 챕터의 내용'을 보여줍니다.
            current_paper_status = "\n".join([f"[{k}]: {v[:200]}..." for k, v in st.session_state['paper_sections'].items()])
            
            full_context = f"""
            [현재 연구 진행 상황]
            - 주제: {st.session_state['research_context']['topic']}
            - 변인: {st.session_state['research_context']['variables']}
            - 현재 작성된 논문 요약:
            {current_paper_status}
            """
            
            # 지도교수 모드 발동
            system_instruction = f"""
            당신은 까다로운 심리학과 지도교수입니다.
            학생(사용자)이 논문의 논리적 허점이나 구체성 부족을 지적하면, 
            1. 그 지적이 타당한지 평가하고
            2. 구체적인 예시나 문장을 포함하여 직접 수정안을 제시하세요.
            3. 말투는 정중하지만 학술적으로 엄격하게 하세요.
            
            [배경 지식]: {full_context}
            """
            
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system_instruction}] + 
                         [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
            )
            
            ai_response = response.choices[0].message.content
            message_placeholder.markdown(ai_response)
            st.session_state.messages.append({"role": "assistant", "content": ai_response})