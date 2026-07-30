import streamlit as st
import pandas as pd
import requests

# plotly.express 및 graph_objects 라이브러리 불러오기
import plotly.express as px
import plotly.graph_objects as go

# -----------------------------------------------------------------------------
# 1. 스트림릿 페이지 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="전국 시군구 1세 이하 인구 비율 지도",
    layout="wide"
)

st.title("전국 시군구 1세 이하 인구 비율 지도")
st.caption("공공데이터 기반 최신 연도 시군구별 1세 이하 인구 비율(%) 단계구분도")

# -----------------------------------------------------------------------------
# 2. 데이터 캐싱 및 로드 (스트림릿 속도 향상을 위한 cache_data 사용)
# -----------------------------------------------------------------------------
@st.cache_data
def load_population_data():
    """인구 CSV 파일(Gzip 압축)을 불러오고 최신 연도 기준 시군구별 비율을 계산합니다."""
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    
    # '코드' 열은 10자리 문자열로 지정하여 앞자리 '0'이 손실되지 않도록 정수로 읽지 않습니다.
    df = pd.read_csv(pop_url, dtype={'코드': str})
    
    # 가장 최신 연도 추출
    latest_year = df['연도'].max()
    df_latest = df[df['연도'] == latest_year].copy()
    
    # 시군구 코드 5자리 추출 (10자리 행정동 코드의 앞 5자리)
    df_latest['sigungu_code'] = df_latest['코드'].str.slice(0, 5)
    
    # 0세 및 1세 인구 합산 ('계_0세', '계_1세')
    df_latest['infant_pop'] = df_latest['계_0세'] + df_latest['계_1세']
    
    # '계_'로 시작하는 모든 나이별 열을 찾아서 전체 인구 계산
    age_cols = [c for c in df_latest.columns if c.startswith('계_')]
    df_latest['total_pop'] = df_latest[age_cols].sum(axis=1)
    
    # 시군구(5자리 코드) 단위로 데이터 그룹화 및 합산
    grouped = df_latest.groupby('sigungu_code').agg({
        '시도': 'first',
        '시군구': 'first',
        'infant_pop': 'sum',
        'total_pop': 'sum'
    }).reset_index()
    
    # 1세 이하 인구 비율(%) 계산 (소수점 둘째 자리까지 반올림)
    grouped['rate'] = (grouped['infant_pop'] / grouped['total_pop'] * 100).round(2)
    
    return grouped, latest_year

@st.cache_data
def load_geojson():
    """시군구 GeoJSON 경계 데이터를 웹에서 로드합니다."""
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    response = requests.get(geojson_url)
    return response.json()

# 데이터 불러오기 수행
with st.spinner("데이터를 불러오는 중입니다..."):
    df_sigungu, max_year = load_population_data()
    geojson_data = load_geojson()

st.write(f"**기준 연도:** {max_year}년")

# -----------------------------------------------------------------------------
# 3. 5단계 지정 구간(Custom Bins) 데이터 라벨링
# 지정된 구간: 19% 미만, 19%~23%, 23%~28%, 28%~38%, 38% 이상
# -----------------------------------------------------------------------------
bins = [-float('inf'), 19, 23, 28, 38, float('inf')]
labels = ['19% 미만', '19% ~ 23% 미만', '23% ~ 28% 미만', '28% ~ 38% 미만', '38% 이상']

# 지정된 경계값에 따라 각 시군구를 5개 범주 중 하나로 분류
df_sigungu['rate_group'] = pd.cut(
    df_sigungu['rate'], 
    bins=bins, 
    labels=labels, 
    right=False
)

# -----------------------------------------------------------------------------
# 4. Plotly 단계구분도(Choropleth) 생성
# -----------------------------------------------------------------------------
# 범주 순서와 단계별 색상 지정 (연한 색 -> 진한 색)
color_discrete_map = {
    '19% 미만': '#f7fbff',
    '19% ~ 23% 미만': '#c6dbef',
    '23% ~ 28% 미만': '#6baed6',
    '28% ~ 38% 미만': '#2171b5',
    '38% 이상': '#08306b'
}

fig = px.choropleth(
    df_sigungu,
    geojson=geojson_data,
    locations='sigungu_code',         # 데이터의 시군구 코드 (5자리)
    featureidkey='properties.코드',    # GeoJSON 내 시군구 코드 속성 (5자리)
    color='rate_group',               # 5단계 범주 열 지정
    color_discrete_map=color_discrete_map,
    category_orders={'rate_group': labels}, # 범례 표시 순서 고정
    hover_name='시군구',              # 마우스 오버 시 표시할 메인 라벨
    hover_data={
        'sigungu_code': False,
        'rate_group': False,
        '시도': True,
        'rate': ':.2f'                # 비율 표시 형식 (소수점 2자리)
    },
    labels={
        '시도': '시도명',
        'rate': '1세 이하 인구 비율(%)',
        'rate_group': '비율 구간'
    }
)

# 대한민국 중심 위치로 지도의 시점과 범위를 고정 및 타일 배경 제거
fig.update_geos(
    fitbounds="locations",            # GeoJSON 경계에 맞게 지도 자동 축소/확대
    visible=False                     # 외부 기본 타일 및 해안선/국경선 안 보이게 설정
)

# 지도 레이아웃 마감 설정 (배경 투명 및 여백 최소화)
fig.update_layout(
    margin={"r": 0, "t": 10, "l": 0, "b": 0},
    legend_title_text="비율 구간",
    height=650
)

# 스트림릿에 지도 시각화 출력
st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------------
# 5. 출산율(1세 이하 인구 비율) 상위/하위 10개 시군구 표 출력
# -----------------------------------------------------------------------------
st.subheader("📊 시군구별 비율 상위 & 하위 TOP 10")

col1, col2 = st.columns(2)

# 화면에 표시하기 적합하도록 데이터 정돈
df_sorted = df_sigungu.sort_values(by='rate', ascending=False)
df_display = df_sorted[['시도', '시군구', 'rate']].rename(columns={
    '시도': '시도',
    '시군구': '시군구',
    'rate': '1세 이하 비율(%)'
})

with col1:
    st.markdown("##### 🟢 비율이 가장 높은 지역 TOP 10")
    top_10 = df_display.head(10).reset_index(drop=True)
    st.dataframe(top_10, use_container_width=True)

with col2:
    st.markdown("##### 🔴 비율이 가장 낮은 지역 TOP 10")
    bottom_10 = df_display.tail(10).iloc[::-1].reset_index(drop=True)
    st.dataframe(bottom_10, use_container_width=True)
