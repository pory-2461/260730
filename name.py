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
    page_title="전국 출산율 및 인구 변화 분석 지도",
    layout="wide"
)

st.title("전국 시군구 1세 이하 인구 비율 분석")
st.caption("공공데이터 기반 1세 이하 인구 비율(%) 단계구분도 및 10년 시도별 변화 추이")

# -----------------------------------------------------------------------------
# 2. 데이터 캐싱 및 로드 (스트림릿 속도 향상을 위한 cache_data 사용)
# -----------------------------------------------------------------------------
@st.cache_data
def load_population_data():
    """인구 CSV 파일(Gzip 압축)을 불러와 시군구별 지도 데이터 및 시도별 10년 추이 데이터를 생성합니다."""
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    
    # '코드' 열은 10자리 문자열로 지정하여 앞자리 '0'이 손실되지 않도록 읽기
    df = pd.read_csv(pop_url, dtype={'코드': str})
    
    # 0세 및 1세 인구 합산 ('계_0세', '계_1세')
    df['infant_pop'] = df['계_0세'] + df['계_1세']
    
    # '계_'로 시작하는 모든 나이별 열을 찾아서 전체 인구 계산
    age_cols = [c for c in df.columns if c.startswith('계_')]
    df['total_pop'] = df[age_cols].sum(axis=1)
    
    # ---------------------------------------------------------
    # A. 최신 연도 기준 시군구별 지도 데이터 집계
    # ---------------------------------------------------------
    latest_year = df['연도'].max()
    df_latest = df[df['연도'] == latest_year].copy()
    
    # 시군구 코드 5자리 추출 (10자리 행정동 코드의 앞 5자리)
    df_latest['sigungu_code'] = df_latest['코드'].str.slice(0, 5)
    
    # 시군구(5자리 코드) 단위로 데이터 그룹화 및 합산
    sigungu_grouped = df_latest.groupby('sigungu_code').agg({
        '시도': 'first',
        '시군구': 'first',
        'infant_pop': 'sum',
        'total_pop': 'sum'
    }).reset_index()
    
    # 1세 이하 인구 비율(%) 계산
    sigungu_grouped['rate'] = (sigungu_grouped['infant_pop'] / sigungu_grouped['total_pop'] * 100).round(2)
    
    # ---------------------------------------------------------
    # B. 연도별 x 광역시·도별 10년 추이 데이터 집계
    # ---------------------------------------------------------
    sido_yearly = df.groupby(['연도', '시도']).agg({
        'infant_pop': 'sum',
        'total_pop': 'sum'
    }).reset_index()
    sido_yearly['rate'] = (sido_yearly['infant_pop'] / sido_yearly['total_pop'] * 100).round(2)
    
    # 전국 전체 평균 추이 계산 및 추가
    national_yearly = df.groupby('연도').agg({
        'infant_pop': 'sum',
        'total_pop': 'sum'
    }).reset_index()
    national_yearly['시도'] = '전국 평균'
    national_yearly['rate'] = (national_yearly['infant_pop'] / national_yearly['total_pop'] * 100).round(2)
    
    # 시도 데이터와 전국 평균 데이터 병합
    sido_trend_df = pd.concat([sido_yearly, national_yearly], ignore_index=True)
    
    return sigungu_grouped, sido_trend_df, latest_year

@st.cache_data
def load_geojson():
    """시군구 GeoJSON 경계 데이터를 웹에서 로드합니다."""
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
    response = requests.get(geojson_url)
    return response.json()

# 데이터 불러오기 수행
with st.spinner("데이터를 불러오는 중입니다..."):
    df_sigungu, df_sido_trend, max_year = load_population_data()
    geojson_data = load_geojson()

# -----------------------------------------------------------------------------
# 3. 지도 시각화 (1.0% 기준 0.3%p 단위 구간)
# -----------------------------------------------------------------------------
st.subheader(f"🗺️ {max_year}년 시군구별 1세 이하 인구 비율 지도")

# 1.0% 기준 0.3%p 단위 구간 설정 (8개 다채로운 색상 구간)
bins = [-float('inf'), 0.4, 0.7, 1.0, 1.3, 1.6, 1.9, 2.2, float('inf')]
labels = [
    '0.4% 미만',
    '0.4% ~ 0.7% 미만',
    '0.7% ~ 1.0% 미만',
    '1.0% ~ 1.3% 미만',
    '1.3% ~ 1.6% 미만',
    '1.6% ~ 1.9% 미만',
    '1.9% ~ 2.2% 미만',
    '2.2% 이상'
]

df_sigungu['rate_group'] = pd.cut(
    df_sigungu['rate'], 
    bins=bins, 
    labels=labels, 
    right=False
)

# 스펙트럼 색상 매핑
color_discrete_map = {
    '0.4% 미만': '#d73027',       # 붉은색
    '0.4% ~ 0.7% 미만': '#f46d43', # 주황색
    '0.7% ~ 1.0% 미만': '#fdae61', # 연주황
    '1.0% ~ 1.3% 미만': '#fee08b', # 연노랑 (기준점 1.0%)
    '1.3% ~ 1.6% 미만': '#d9ef8b', # 연연두
    '1.6% ~ 1.9% 미만': '#a6d96a', # 연두
    '1.9% ~ 2.2% 미만': '#66bd63', # 녹색
    '2.2% 이상': '#1a9850'        # 진한 녹색
}

fig_map = px.choropleth(
    df_sigungu,
    geojson=geojson_data,
    locations='sigungu_code',
    featureidkey='properties.코드',
    color='rate_group',
    color_discrete_map=color_discrete_map,
    category_orders={'rate_group': labels},
    hover_name='시군구',
    hover_data={
        'sigungu_code': False,
        'rate_group': False,
        '시도': True,
        'rate': ':.2f'
    },
    labels={
        '시도': '시도명',
        'rate': '1세 이하 인구 비율(%)',
        'rate_group': '비율 구간'
    }
)

fig_map.update_geos(fitbounds="locations", visible=False)
fig_map.update_layout(
    margin={"r": 0, "t": 10, "l": 0, "b": 0},
    legend_title_text="비율 구간 (1.0% 기준 0.3%p 단위)",
    height=600
)

st.plotly_chart(fig_map, use_container_width=True)

# -----------------------------------------------------------------------------
# 4. 출산율(1세 이하 인구 비율) 상위/하위 10개 시군구 표
# -----------------------------------------------------------------------------
st.subheader("📊 시군구별 비율 상위 & 하위 TOP 10")

col1, col2 = st.columns(2)

df_sorted = df_sigungu.sort_values(by='rate', ascending=False)
df_display = df_sorted[['시도', '시군구', 'rate']].rename(columns={
    '시도': '시도',
    '시군구': '시군구',
    'rate': '1세 이하 비율(%)'
})

with col1:
    st.markdown("##### 🟢 비율이 가장 높은 지역 TOP 10")
    st.dataframe(df_display.head(10).reset_index(drop=True), use_container_width=True)

with col2:
    st.markdown("##### 🔴 비율이 가장 낮은 지역 TOP 10")
    st.dataframe(df_display.tail(10).iloc[::-1].reset_index(drop=True), use_container_width=True)

# -----------------------------------------------------------------------------
# 5. [신규 기능] 최근 10년간 광역시·도별 출산율 변화 추이 그래프
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("📈 광역시·도별 1세 이하 인구 비율 10년 변화 추이")
st.caption("2015년부터 최신 연도까지 각 시/도의 연도별 비율 변화 흐름을 비교합니다.")

# 광역시·도 목록 추출
all_sidos = sorted(list(df_sido_trend[df_sido_trend['시도'] != '전국 평균']['시도'].unique()))
default_selected = ['전국 평균', '서울특별시', '경기도', '세종특별자치시']

# 사용자 선택을 위한 다중 선택 박스 (Multiselect)
selected_sidos = st.multiselect(
    "비교할 광역시·도를 선택하세요:",
    options=['전국 평균'] + all_sidos,
    default=default_selected
)

if selected_sidos:
    # 선택된 시도만 필터링
    filtered_trend = df_sido_trend[df_sido_trend['시도'].isin(selected_sidos)]
    
    # plotly 선 그래프 생성
    fig_line = px.line(
        filtered_trend,
        x='연도',
        y='rate',
        color='시도',
        markers=True,  # 각 연도 데이터 지점에 점 표시
        hover_data={'rate': ':.2f'},
        labels={
            '연도': '연도',
            'rate': '1세 이하 인구 비율(%)',
            '시도': '광역시·도'
        }
    )
    
    # 그래프 스타일 조정
    fig_line.update_layout(
        xaxis=dict(dtick=1),  # X축 연도를 1년 단위 정수로 표시
        yaxis_title="1세 이하 인구 비율(%)",
        legend_title_text="지역명",
        height=500,
        hovermode="x unified"  # 마우스 올렸을 때 동일 연도의 모든 지역 값을 동시에 비교
    )
    
    st.plotly_chart(fig_line, use_container_width=True)
else:
    st.info("하나 이상의 광역시·도를 선택해 주세요.")
