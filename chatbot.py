import streamlit as st


# Main title and caption
st.title("💬 챗봇")
st.caption("🚀 교통사고 데이터 & LLM 모델을 사용한 챗봇")

# 필수 입력란
if "input_submitted" not in st.session_state:
    st.session_state.input_submitted = False

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "사용자가 입력한 내용입니다."}]

if "side_messages" not in st.session_state:
    st.session_state.side_messages = []

# 단순 내용 입력
prompt = st.chat_input("여기에 질문을 입력하세요")

# 메시지가 입력되면 필수 입력란을 숨김
if prompt:
    st.session_state.input_submitted = True
    # 메인 출력
    st.session_state.messages.append({"role": "user", "content": prompt})
    # 사이드바 출력
    st.session_state.side_messages.append({"role": "user", "text": prompt})
    
    # 여기에 실제 GPT-3.5-turbo를 호출하는 코드가 필요합니다.
    # 예시:
    # response = client.chat.completions.create(model="gpt-3.5-turbo", messages=st.session_state.messages)
    # msg = response.choices[0].message.content

    msg = "예시 응답입니다.."  # 예시 응답
    st.session_state.messages.append({"role": "assistant", "content": msg})

#기본 값
if not st.session_state.input_submitted:
    st.markdown("---")
    st.subheader("필수 입력란")
    st.write("성별: [필수 입력란에 입력된 성별]")
    st.write("출발 위치: [필수 입력란에 입력된 출발 위치]")
    st.write("도착 위치: [필수 입력란에 입력된 도착 위치]")
    st.write("차종(스크롤바로 진행): [필수 입력란에 입력된 차종]")
    st.markdown("---")
    st.write("예시 질문 1")
    st.write("예시 질문 2")
    st.markdown("---")

# 과거 이동 기록 텍스트 출력
with st.sidebar:
    st.write("과거 이동 기록")
    if "messages" in st.session_state:
        user_messages = [msg for msg in st.session_state.side_messages if msg["role"] == "user" and msg["text"]]
        for i, msg in enumerate(user_messages):
            col1, col2 = st.sidebar.columns([3, 1])
            with col1:
                st.write(msg["text"])
            with col2:
                if st.button("입력", key=f"input_{i}"):
                    st.session_state.input_submitted = True
                    st.session_state.messages.append({"role": "user", "content": msg["text"]})
    
                    # 여기에 실제 GPT-3.5-turbo를 호출하는 코드가 필요합니다.
                    # 예시:
                    # response = client.chat.completions.create(model="gpt-3.5-turbo", messages=st.session_state.messages)
                    # response_msg = response.choices[0].message.content
    
                    response_msg =  "[입력] 예시 응답입니다.."  # 예시 응답
                    st.session_state.messages.append({"role": "assistant", "content": response_msg})
                    st.experimental_rerun()
      
# 지도 및 챗봇 영역 표시
if st.session_state.input_submitted:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("챗봇")
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])
    
    with col2:
        st.header("지도")
        # 지도 관련 코드 추가 (예: folium, pydeck 등 사용 가능)
