# app.py
import re
import html
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from collections import Counter
from konlpy.tag import Okt


st.set_page_config(
    page_title="유튜브 댓글 반응 분석 웹앱",
    page_icon="📊",
    layout="wide"
)

st.title("📊 유튜브 댓글 반응 분석 웹앱")
st.caption("유튜브 영상 링크를 입력하면 댓글을 수집하고, 시간대별 반응·좋아요·핵심 단어를 분석합니다.")


API_KEY = st.secrets.get("YOUTUBE_API_KEY", "")

STOPWORDS = {
    "영상", "댓글", "진짜", "정말", "너무", "그냥", "이거", "저거", "ㅋㅋ", "ㅎㅎ",
    "ㅠㅠ", "합니다", "있는", "없는", "하면", "해서", "그리고", "근데", "오늘",
    "사람", "생각", "우리", "제가", "이런", "저런", "그런", "보기",
    "입니다", "네요", "어요", "아요", "ㅋㅋㅋ", "ㅎㅎㅎ", "유튜브"
}


def extract_video_id(url: str):
    patterns = [
        r"v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"shorts/([a-zA-Z0-9_-]{11})",
        r"embed/([a-zA-Z0-9_-]{11})"
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    if re.fullmatch(r"[a-zA-Z0-9_-]{11}", url.strip()):
        return url.strip()

    return None


def clean_text(text):
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"http\S+|www\S+", " ", text)
    text = re.sub(r"[^가-힣a-zA-Z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@st.cache_data(show_spinner=False)
def collect_comments(video_id, max_comments):
    comments = []
    next_page_token = None

    while len(comments) < max_comments:
        url = "https://www.googleapis.com/youtube/v3/commentThreads"
        params = {
            "part": "snippet",
            "videoId": video_id,
            "key": API_KEY,
            "maxResults": 100,
            "textFormat": "html",
            "order": "time"
        }

        if next_page_token:
            params["pageToken"] = next_page_token

        response = requests.get(url, params=params, timeout=15)

        if response.status_code != 200:
            raise Exception(response.json())

        data = response.json()

        for item in data.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]

            comments.append({
                "작성자": snippet.get("authorDisplayName", ""),
                "댓글": clean_text(snippet.get("textDisplay", "")),
                "좋아요수": snippet.get("likeCount", 0),
                "작성일": snippet.get("publishedAt", ""),
                "수정일": snippet.get("updatedAt", "")
            })

            if len(comments) >= max_comments:
                break

        next_page_token = data.get("nextPageToken")

        if not next_page_token:
            break

    df = pd.DataFrame(comments)

    if not df.empty:
        df["작성일"] = pd.to_datetime(df["작성일"])
        df["날짜"] = df["작성일"].dt.date
        df["시간"] = df["작성일"].dt.hour
        df["요일"] = df["작성일"].dt.day_name()
        df["댓글길이"] = df["댓글"].str.len()

    return df


def extract_words(texts, min_len=2):
    okt = Okt()
    words = []

    for text in texts:
        nouns = okt.nouns(text)
        for word in nouns:
            if len(word) >= min_len and word not in STOPWORDS:
                words.append(word)

    return words


st.sidebar.header("⚙️ 분석 설정")

video_url = st.sidebar.text_input(
    "유튜브 영상 링크",
    placeholder="https://www.youtube.com/watch?v=..."
)

max_comments = st.sidebar.slider(
    "수집할 댓글 수",
    min_value=10,
    max_value=5000,
    value=500,
    step=10
)

top_n = st.sidebar.slider(
    "상위 단어 개수",
    min_value=10,
    max_value=50,
    value=20,
    step=5
)

min_word_len = st.sidebar.slider(
    "단어 최소 글자 수",
    min_value=1,
    max_value=4,
    value=2
)

analyze_btn = st.sidebar.button("댓글 수집 및 분석 시작", type="primary")


if analyze_btn:
    if not API_KEY:
        st.error("YouTube API 키가 없습니다. Streamlit Secrets에 YOUTUBE_API_KEY를 등록하세요.")
        st.stop()

    video_id = extract_video_id(video_url)

    if not video_id:
        st.error("올바른 유튜브 영상 링크를 입력하세요.")
        st.stop()

    with st.spinner("댓글을 수집하는 중입니다..."):
        try:
            df = collect_comments(video_id, max_comments)
        except Exception as e:
            st.error("댓글 수집 중 오류가 발생했습니다.")
            st.code(str(e))
            st.stop()

    if df.empty:
        st.warning("수집된 댓글이 없습니다. 댓글이 비활성화된 영상일 수 있습니다.")
        st.stop()

    st.success(f"총 {len(df):,}개의 댓글을 수집했습니다.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 댓글 수", f"{len(df):,}개")
    c2.metric("총 좋아요 수", f"{int(df['좋아요수'].sum()):,}개")
    c3.metric("댓글당 평균 좋아요", round(df["좋아요수"].mean(), 2))
    c4.metric("평균 댓글 길이", f"{round(df['댓글길이'].mean(), 1)}자")

    st.divider()

    st.subheader("⏰ 시간대별 댓글 추이")
    hourly = df.groupby("시간").size().reset_index(name="댓글수")

    fig_hour = px.line(
        hourly,
        x="시간",
        y="댓글수",
        markers=True,
        title="시간대별 댓글 수"
    )
    fig_hour.update_layout(xaxis=dict(dtick=1))
    st.plotly_chart(fig_hour, use_container_width=True)

    st.subheader("📅 날짜별 댓글 추이")
    daily = df.groupby("날짜").size().reset_index(name="댓글수")

    fig_daily = px.bar(
        daily,
        x="날짜",
        y="댓글수",
        title="날짜별 댓글 수"
    )
    st.plotly_chart(fig_daily, use_container_width=True)

    st.subheader("👍 좋아요 수 분석")

    col1, col2 = st.columns(2)

    with col1:
        fig_like_hist = px.histogram(
            df,
            x="좋아요수",
            nbins=30,
            title="댓글 좋아요 수 분포"
        )
        st.plotly_chart(fig_like_hist, use_container_width=True)

    with col2:
        top_liked = df.sort_values("좋아요수", ascending=False).head(10)

        fig_top_liked = px.bar(
            top_liked,
            x="좋아요수",
            y="댓글",
            orientation="h",
            title="좋아요가 많은 댓글 TOP 10"
        )
        fig_top_liked.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_top_liked, use_container_width=True)

    st.dataframe(
        top_liked[["작성자", "댓글", "좋아요수", "작성일"]],
        use_container_width=True
    )

    st.subheader("🔤 자주 등장하는 단어 분석")

    with st.spinner("단어를 분석하는 중입니다..."):
        words = extract_words(df["댓글"].dropna().tolist(), min_word_len)

    if not words:
        st.warning("분석할 단어가 충분하지 않습니다.")
    else:
        word_counts = Counter(words)
        word_df = pd.DataFrame(
            word_counts.most_common(top_n),
            columns=["단어", "빈도"]
        )

        col1, col2 = st.columns(2)

        with col1:
            fig_words = px.bar(
                word_df,
                x="빈도",
                y="단어",
                orientation="h",
                title=f"상위 {top_n}개 핵심 단어"
            )
            fig_words.update_layout(yaxis=dict(autorange="reversed"))
            st.plotly_chart(fig_words, use_container_width=True)

        with col2:
            st.write("☁️ 워드클라우드")

            wc = WordCloud(
                font_path="/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                width=800,
                height=500,
                background_color="white"
            ).generate_from_frequencies(word_counts)

            fig, ax = plt.subplots(figsize=(10, 6))
            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")
            st.pyplot(fig)

        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 댓글 데이터 CSV 다운로드",
            data=csv,
            file_name=f"youtube_comments_{video_id}.csv",
            mime="text/csv"
        )

        word_csv = word_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 단어 빈도 CSV 다운로드",
            data=word_csv,
            file_name=f"youtube_word_frequency_{video_id}.csv",
            mime="text/csv"
        )

    st.subheader("💬 수집된 댓글 원본")
    st.dataframe(
        df[["작성자", "댓글", "좋아요수", "작성일"]],
        use_container_width=True,
        height=400
    )

else:
    st.info("왼쪽 사이드바에 유튜브 영상 링크를 입력하고 분석을 시작하세요.")

    st.markdown("""
    ### 이 웹앱에서 가능한 분석

    - 유튜브 영상 링크만으로 댓글 수집
    - 수집할 댓글 수 선택: 10개 ~ 5000개
    - 시간대별 댓글 추이 분석
    - 날짜별 댓글 추이 분석
    - 댓글 좋아요 수 분포 분석
    - 좋아요가 많은 댓글 TOP 10 확인
    - 자주 등장하는 단어 차트 시각화
    - 워드클라우드 생성
    - 댓글 데이터 CSV 다운로드
    """)
