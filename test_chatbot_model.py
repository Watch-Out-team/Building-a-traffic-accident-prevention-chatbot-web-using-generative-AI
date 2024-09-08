import streamlit as st
import requests
import folium
import networkx as nx
import osmnx as ox
import pandas as pd
from streamlit_folium import st_folium
from langchain_community.utilities import SQLDatabase
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from prompt_templates import get_prompt_template


# AWS DB 정보 입력
host = "ls-ce7479bc8962da8ea081f7fff30be78b7b65c590.cp4sigaewkcs.ap-northeast-2.rds.amazonaws.com"
port = 3306
username = "dbmasteruser"
password = "F?Lotn9|Yzfff1amN|B#l_s~mLz(^9*O"
database = "dbmaster"

# MySQL URI 형식
db_uri = f'mysql+mysqlconnector://{username}:{password}@{host}/{database}'
db = SQLDatabase.from_uri(db_uri)  # LangChain을 활용하여 DB 연결

# # IBM Watson API 키와 URL 설정
api_key = "SOUcCBrKx0NmGvbCs114_4yxvAuaFOlAEkCyJDRK28q3" # 서정정
model_id = "meta-llama/llama-2-70b-chat"
url = "https://us-south.ml.cloud.ibm.com/ml/v1/text/generation?version=2023-05-29"
project_id = "b08703d7-0a18-454a-9cc2-2aa5f1e929f8"  # 적절한 project_id를 입력하세요




# 지도 클릭 시 출발 위치와 도착 위치의 위도 및 경도를 저장하기 위한 상태 변수
if "start_location" not in st.session_state:
    st.session_state.start_location = None
if "destination_location" not in st.session_state:
    st.session_state.destination_location = None
gender_output = None
car_types_output = None


def create_map(location_type):
    m = folium.Map(location=[40.608757, -74.038086], zoom_start=10)
    m.add_child(folium.LatLngPopup())
    map_data = st_folium(m, width=700, height=500, key=f"{location_type}_map")

    if map_data and map_data.get("last_clicked"):
        lat, lon = map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]
        if location_type == "start":
            st.session_state.start_location = (lat, lon)
        elif location_type == "destination":
            st.session_state.destination_location = (lat, lon)
        st.success(f"선택된 {location_type} 위치: 위도 {lat}, 경도 {lon}")



def get_ibm_access_token(api_key):
    try:
        iam_url = "https://iam.cloud.ibm.com/identity/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {"apikey": api_key, "grant_type": "urn:ibm:params:oauth:grant-type:apikey"}
        response = requests.post(iam_url, headers=headers, data=data)
        response.raise_for_status()
        return response.json().get("access_token", None)
    except Exception as e:
        st.error(f"IBM API 토큰 가져오기 오류: {str(e)}")
        return None

def generate_ibm_response(prompt, access_token):
    try:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        body = {
            "input": prompt,
            "parameters": {
                "decoding_method": "greedy",
                "max_new_tokens": 40,  # 응답 길이 증가
                "stop_sequences": [";"], # 체크해야할 부분 
                "repetition_penalty": 1
            },
            "model_id": model_id,
            "project_id": project_id,
            "moderations": {
                "hap": {
                    "input": {
                        "enabled": True,
                        "threshold": 0.5,
                        "mask": {
                            "remove_entity_value": True
                        }
                    },
                    "output": {
                        "enabled": True,
                        "threshold": 0.5,
                        "mask": {
                            "remove_entity_value": True
                        }
                    }
                }
            }
        }
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        return response.json()["results"][0]["generated_text"]
    except Exception as e:
        st.error(f"IBM API 호출 오류: {str(e)}")
        st.code(f"Error occurred at generate_ibm_response: {str(e)}")
        return None


def generate_ibm_response_chatbot(prompt, access_token, columns, selected_gender, selected_car_types, lat_min, lat_max, lon_min, lon_max):
    gender_str = ', '.join([f"'{gender}'" for gender in selected_gender])
    car_types_str = ', '.join([f"'{car}'" for car in selected_car_types])

    try:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        body = {
            "input": get_prompt_template(prompt, columns, selected_gender, selected_car_types, lat_min, lat_max, lon_min, lon_max),
            "parameters": {
                "decoding_method": "greedy",
                "max_new_tokens": 550,  # 응답 길이 증가
                "stop_sequences": [".."], # 체크해야할 부분 
                "repetition_penalty": 1
            },
            "model_id": model_id,
            "project_id": project_id,
            "moderations": {
                "hap": {
                    "input": {
                        "enabled": True,
                        "threshold": 0.5,
                        "mask": {
                            "remove_entity_value": True
                        }
                    },
                    "output": {
                        "enabled": True,
                        "threshold": 0.5,
                        "mask": {
                            "remove_entity_value": True
                        }
                    }
                }
            }
        }
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        return response.json()["results"][0]["generated_text"]
    except Exception as e:
        st.error(f"IBM API 호출 오류: {str(e)}")
        st.code(f"Error occurred at generate_ibm_response: {str(e)}")
        return None



# SQL query를 입력으로 변환하는 함수
def get_db_connection():
    try:
        db = SQLDatabase.from_uri(db_uri)
        return db
    except Exception as e:
        st.error(f"데이터베이스 연결 오류: {str(e)}")
        st.code(f"Error occurred at get_db_connection: {str(e)}")
        return None


def handle_user_query(prompt):
    global gender_output
    global car_types_output
    try:
        db = get_db_connection()
        if db:
            # 위도와 경도 변수 설정
            lat_min = min(st.session_state.start_location[0], st.session_state.destination_location[0])
            lat_max = max(st.session_state.start_location[0], st.session_state.destination_location[0])
            lon_min = min(st.session_state.start_location[1], st.session_state.destination_location[1])
            lon_max = max(st.session_state.start_location[1], st.session_state.destination_location[1])
            
            # 성별 선택 처리
            if gender_output == 'M':
                selected_gender = ['M', 'unknown', 'U']
            elif gender_output == 'F':
                selected_gender = ['F', 'unknown', 'U']
            else:
                selected_gender = ['unknown', 'U']  # 기본값
            
            selected_car_types = car_types_output if car_types_output else ['Sedan']  # 기본값 설정
            # 테스트
            # 데이터베이스 스키마 정보 가져오기
            schema = db.get_table_info(["data"])  # 실제 테이블 스키마 정보를 가져오는 부분

            columns = ['COLLISION_ID', 'CRASH_DATE', 'CRASH_TIME', 'Weather', 'BOROUGH', 'LOCATION', 'NUMBER_OF_PERSONS_INJURED', 'NUMBER_OF_PERSONS_KILLED', 'NUMBER_OF_PEDESTRIANS_INJURED', 'NUMBER_OF_PEDESTRIANS_KILLED', 'NUMBER_OF_CYCLIST_INJURED', 'NUMBER_OF_CYCLIST_KILLED', 'NUMBER_OF_MOTORIST_INJURED', 'NUMBER_OF_MOTORIST_KILLED', 'CONTRIBUTING_FACTOR_VEHICLE_1', 'CONTRIBUTING_FACTOR_VEHICLE_2', 'VEHICLE_TYPE_CODE_1', 'VEHICLE_TYPE_CODE_2', 'VEHICLE_TYPE', 'TRAVEL_DIRECTION', 'VEHICLE_OCCUPANTS', 'DRIVER_SEX', 'DRIVER_LICENSE_STATUS', 'PRE_CRASH', 'POINT_OF_IMPACT', 'VEHICLE_DAMAGE', 'VEHICLE_DAMAGE_1', 'VEHICLE_DAMAGE_2', 'VEHICLE_DAMAGE_3', 'CONTRIBUTING_FACTOR_1', 'CONTRIBUTING_FACTOR_2', 'LICENSE_SCORE', 'RISK_LEVEL', 'nearest_street', 'VEHICLE_YEAR_CATEGORY']
            access_token = get_ibm_access_token(api_key)
            if access_token:
                #테스트
                msg = generate_ibm_response_chatbot(prompt, access_token, columns, selected_gender, selected_car_types, lat_min, lat_max, lon_min, lon_max)
               
                return msg

        else:
            return "데이터베이스 연결에 실패했습니다."
    except Exception as e:
        st.error(f"오류: {str(e)}")
        st.code(f"Error occurred at handle_user_query: {str(e)}")
        return "죄송합니다, 요청을 처리할 수 없습니다."
        


# Streamlit 앱 구성 업데이트
st.title("💬 Watch Out")
st.caption("🚀 교통사고 데이터 & LLM 모델을 사용한 챗봇")

if "input_submitted" not in st.session_state:
    st.session_state.input_submitted = False
# 테스트 완료시 지우기
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "안녕하세요! 무엇을 도와드릴까요?"}]

if "side_messages" not in st.session_state:
    st.session_state.side_messages = []
    


if not st.session_state.input_submitted:
    st.markdown("---")
    
    with st.form(key="form"):
        col1, col2 = st.columns(2)
        
        with col1:
            gender = st.selectbox(
                label="성별",
                options=["남성", "여성"]
            )
            gender_output = "M" if gender == "남성" else "F"
        
        with col2:
            car_type_mapping = {
                "세단": "Sedan",
                "왜건": "Wagon",
                "승용차": "PASSENGER VEHICLE",
                "택시": "Taxi",
                "트럭": "Truck",
                "기타": "OTHER"
            }
            car_type = st.selectbox(
                label="차종",
                options=["세단", "왜건", "승용차", "택시", "트럭", "기타"]
            )
            car_types_output = car_type_mapping[car_type]
            
        st.markdown("출발 위치 선택")
        create_map("start")
        if st.session_state.start_location:
            st.write(f"선택된 출발 위치: {st.session_state.start_location}")
        
        st.markdown("도착 위치 선택")
        create_map("destination")
        if st.session_state.destination_location:
            st.write(f"선택된 도착 위치: {st.session_state.destination_location}")
        
        submit = st.form_submit_button(label="Submit")

    if submit:
        st.session_state.input_submitted = True # 챗봇 화면 불러오는 기능
        st.write(f"성별: {gender_output}")
        st.write(f"선택된 차종: {car_types_output}")
        st.write(f"출발 위치: {st.session_state.start_location}")
        st.write(f"도착 위치: {st.session_state.destination_location}")
    
        # 데이터베이스 연결
        try:
            db = get_db_connection()
            if db:
                # 위도와 경도 변수 설정
                lat_min = min(st.session_state.start_location[0], st.session_state.destination_location[0])
                lat_max = max(st.session_state.start_location[0], st.session_state.destination_location[0])
                lon_min = min(st.session_state.start_location[1], st.session_state.destination_location[1])
                lon_max = max(st.session_state.start_location[1], st.session_state.destination_location[1])
                # 성별 선택 처리
                if gender_output == 'M':
                    selected_gender = ['M', 'unknown', 'U']
                elif gender_output == 'F':
                    selected_gender = ['F', 'unknown', 'U']
                else:
                    selected_gender = ['unknown', 'U']  # 기본값
    
                selected_car_types = car_types_output if car_types_output else ['Sedan']  # 기본값 설정

                # SQL 쿼리 작성
                query = f"""
                SELECT VEHICLE_DAMAGE, COUNT(*) as count
                FROM data
                WHERE DRIVER_SEX IN ({', '.join([f"'{gender}'" for gender in selected_gender])})
                AND VEHICLE_TYPE IN  ('{selected_car_types}')
                AND CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(LOCATION, ',', 1), '(', -1) AS DECIMAL(10,8)) BETWEEN {lat_min} AND {lat_max}
                AND CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(LOCATION, ',', -1), ')', 1) AS DECIMAL(11,8)) BETWEEN {lon_min} AND {lon_max}
                GROUP BY VEHICLE_DAMAGE
                ORDER BY count DESC
                LIMIT 3
                """
                # 쿼리 실행
                result = db.run(query)
                result = list(result)
                
                # 결과를 하나의 문자열로 결합
                result_str = ''.join(result)
                
                # 불필요한 문자 제거 및 튜플로 변환
                result_str = result_str.replace('[', '').replace(']', '').replace('(', '').replace(')', '')
                # 문자열을 튜플의 리스트로 변환하는 함수
                def convert_to_tuple_list(input_str):
                    # 문자열을 기준으로 나누고 리스트로 변환
                    items = input_str.split(', ')
                    # 튜플 리스트로 변환
                    tuple_list = [(items[i].strip(), int(items[i + 1].strip())) for i in range(0, len(items), 2)]
                    return tuple_list
                
                # 결과 출력
                result = convert_to_tuple_list(result_str)

                # 결과 처리
                if result:
                    st.write("VEHICLE_DAMAGE의 상위 3개 고유값:")
                    for item in result:
                        # item이 튜플인지 확인하고 unpack하기
                        if isinstance(item, tuple) and len(item) == 2:
                            damage, count = item
                            st.write(f"{damage}: {count}")


                    # 가장 많이 발생한 데이터 출력
                    if isinstance(result[0], tuple) and len(result[0]) == 2:
                        most_common_damage, most_common_damage_count = result[0]
                        output_message = f"VEHICLE_DAMAGE에서 가장 많이 발생한 데이터: {most_common_damage}\n\n"
                        output_message += f"가장 많이 발생한 데이터의 개수: {most_common_damage_count}\n\n"
                    else:
                        output_message = "가장 많이 발생한 데이터 정보를 가져오는 데 오류가 발생했습니다."
                else:
                    output_message = "해당 조건에 맞는 데이터가 없습니다."

                # 챗봇 메시지에 결과 추가
                st.session_state.messages.append({"role": "assistant", "content": output_message})
                st.rerun() # 개인적인 입장으로 이 방법은 선호하지 않습니다.
            else:
                st.error("데이터베이스 연결에 실패했습니다.")
        except Exception as e:
            st.error(f"데이터 처리 중 오류 발생: {str(e)}")

# if "start_map_opened" in st.session_state or "destination_map_opened" in st.session_state:
#     with st.expander("지도 보기"):
#         if st.session_state.get("start_map_opened", False):
#             create_map("start")
#         if st.session_state.get("destination_map_opened", False):
#             create_map("destination")
#     st.markdown("---")
#     st.write("예시 질문 1")
#     st.write("예시 질문 2")
#     st.markdown("---")

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

                    access_token = get_ibm_access_token(api_key)
                    if access_token:
                        msg = generate_ibm_response(msg["text"], access_token)
                        st.session_state.messages.append({"role": "assistant", "content": msg})

if st.session_state.input_submitted:
    prompt = st.chat_input("여기에 질문을 입력하세요")
    
    if prompt:
        st.session_state.input_submitted = True
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.side_messages.append({"role": "user", "text": prompt})
    
        msg = handle_user_query(prompt)
    
        if msg:
            st.session_state.messages.append({"role": "assistant", "content": msg})
        else:
            st.session_state.messages.append({"role": "assistant", "content": "죄송합니다, 요청을 처리할 수 없습니다."})
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("챗봇")
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])
    
    with col2:
        st.header("map")
        # 지도 관련 코드 추가 (예: folium, pydeck 등 사용 가능)
        # 위에서 입력 받은 위도, 경도 불러오기 
        start_address = st.session_state.start_location
        end_address = st.session_state.destination_location
        # 상태 저장을 위한 session_state 초기화
        # if "route_graph_map" not in st.session_state:
        #   st.session_state["route_graph_map"] = None
        if start_address and end_address:
            try:
                start_lat = start_address[0]
                start_lon = start_address[1]
                end_lat = end_address[0]
                end_lon = end_address[1]
                
                # OSM에서 출발지와 도착지가 포함된 그래프 가져오기
                G = ox.graph_from_place('NYC, NY, US', network_type='drive')
                
                # 출발지, 도착지 노드 표시
                start_node = ox.nearest_nodes(G, start_lon, start_lat)
                end_node = ox.nearest_nodes(G, end_lon, end_lat)
                
                # 두 노드가 같은 구성 요소에 있는지 확인
                if not nx.has_path(G, start_node, end_node):
                    st.error("출발지와 도착지 사이에 경로가 없습니다.")
                    st.stop()
                
                # 최단 경로 계산
                route = nx.shortest_path(G, start_node, end_node, weight='length')
               
                # Folium 지도 생성 및 초기 중심 설정
                map_center = [(start_lat + end_lat) / 2, (start_lon + end_lon) / 2]
                route_map = folium.Map(location=map_center, zoom_start=13)
               
                # 최단 경로 시각화 (Folium)
                route_map = ox.plot_route_folium(G, route, route_map=route_map, popup_attribute='length')
               
                # 출발지에 마커 추가
                folium.Marker(
                    [start_lat, start_lon],
                    icon=folium.Icon(color='green', icon='play', prefix='fa'),
                    popup='<b>출발지</b>',
                    tooltip='<i>출발지 위치</i>'
                ).add_to(route_map)

                # 도착지에 마커 추가
                folium.Marker(
                    [end_lat, end_lon],
                    icon=folium.Icon(color='red', icon='stop', prefix='fa'),
                    popup='<b>도착지</b>',
                    tooltip='<i>도착지 위치</i>'
                ).add_to(route_map)

                ## 이동 경로 상에서 실제 교통사고 발생 구간 시각화 ##
              
                # 최단 경로 위의 모든 위도, 경도 쌍 가져오기
                route_coords = [(G.nodes[node]['y'], G.nodes[node]['x']) for node in route]

                # 출발지와 도착지의 위도, 경도 쌍도 추가하기
               
                # route_coords는 출발지와 도착지의 위도, 경도 쌍을 포함하지 않음
                route_coords.insert(0, (start_lat, start_lon))
                route_coords.append((end_lat, end_lon))

                # 'LOCATION' column만 불러오는 SQL 쿼리 작성
                query = "SELECT LOCATION FROM data LIMIT 100"

                # 쿼리 실행
                result = db.run(query)
                result = list(result)
                result_str = ''.join(result)

                # 불필요한 문자 제거
                result_str = result_str.replace('[', '').replace(']', '').replace('(', '').replace(')', '').replace("',","))").replace("'", '(')
                result_list = result_str.split('),', )
                result_list = [item.strip() for item in result_list]

                # 데이터 프레임으로 변환
                df = pd.DataFrame(result_list, columns=['LOCATION'])

                # df['LOCATION'] type을 str -> tuple로 변환
                df['LOCATION'] = df['LOCATION'].apply(lambda x: tuple(map(float, x.strip('()').split(','))))

                # data의 "LOCATION" column 값이 route_coords 안에 있는 값과 일치하면 해당 되는 행 출력
                # 일치하는 행이 없을 수도 있음 (예외 처리 코드 필요)
                df_filtered = df[df['LOCATION'].isin(route_coords)]

                # 일치하는 행이 있을 경우, 해당 행의 'LOCATION' column 값만 뽑아서 list로 저장
                if not df_filtered.empty:
                    location_values = df_filtered['LOCATION'].tolist()
                    # 이동 경로와 과거 교통사고 이력 위치가 겹치는 곳에 원 표시
                    for location in location_values:
                      lat, lon = location
                      # 원 표시
                      folium.Circle(
                          [lat,lon],
                          radius=50,
                          color='#eb9e34',
                          fill_color='red',
                          popup='traffic accident',
                          tooltip='traffic accident'
                      ).add_to(route_graph_map)

                else:
                    st.write("경로 상에 발생한 교통사고가 없습니다.")

                # Folium 지도 Streamlit에 저장
                st.session_state["route_graph_map"] = route_map
        
            except nx.NetworkXNoPath as e:
                st.error(f"경로 오류: {e}")
            except GeocoderTimedOut as e:
                st.error(f"지오코딩 요청이 시간 초과되었습니다: {e}")
            except GeocoderServiceError as e:
                st.error(f"지오코딩 서비스 오류가 발생했습니다: {e}")

        geolocator = Nominatim(user_agent='chiricuto', timeout=10)
        # 위도, 경도를 주소로 변환
        start_address_geo = geolocator.reverse(start_address)
        end_address_geo = geolocator.reverse(end_address)
        
        # CSS로 버튼 숨기는 코드 : HTML 변환해서 작성하기
        st.markdown(
            """
            <style>
            div.stButton > button {
                display: none;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        
        with st.form(key="created_form"):
            st.markdown(f"**Departure**: {start_address_geo}")
            st.markdown(f"**Destination**: {end_address_geo}")
            st_folium(st.session_state["route_graph_map"], width=800, height=600)
        
            submit = st.form_submit_button(label=" ")
