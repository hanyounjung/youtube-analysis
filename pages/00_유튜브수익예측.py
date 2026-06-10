import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import isodate
from urllib.parse import urlparse
from datetime import datetime

st.set_page_config(page_title="유튜브 수익 예측기", layout="wide")

API_KEY = st.secrets["YOUTUBE_API_KEY"]

st.title("📺 유튜브 채널 분석 웹앱")
st.write("유튜브 채널 URL 또는 채널 ID를 입력하면 최근 영상 데이터를 분석하고 예상 수익을 계산합니다.")

# -----------------------------
# 기본 함수
# -----------------------------
def format_number(num):
    try:
        num = int(num)
        if num >= 100000000:
            return f"{num / 100000000:.1f}억"
        elif num >= 10000:
            return f"{num / 10000:.1f}만"
        else:
            return f"{num:,}"
    except:
        return "0"


def parse_duration(duration):
    try:
        d = isodate.parse_duration(duration)
        return round(d.total_seconds() / 60, 1)
    except:
        return 0


def get_channel_id(user_input):
    user_input = user_input.strip()

    if user_input.startswith("UC"):
        return user_input

    if "youtube.com" in user_input:
        path = urlparse(user_input).path.strip("/")

        if path.startswith("@"):
            handle = path
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                "part": "snippet",
                "q": handle,
                "type": "channel",
                "key": API_KEY,
                "maxResults": 1,
            }
            data = requests.get(url, params=params).json()
            items = data.get("items", [])
            if items:
                return items[0]["snippet"]["channelId"]

        if "channel/" in path:
            return path.split("channel/")[-1].split("/")[0]

    return None


def get_channel_info(channel_id):
    url = "https://www.googleapis.com/youtube/v3/channels"
    params = {
        "part": "snippet,statistics,contentDetails",
        "id": channel_id,
        "key": API_KEY,
    }
    data = requests.get(url, params=params).json()
    items = data.get("items", [])

    if not items:
        return None

    item = items[0]
    return {
        "title": item["snippet"].get("title", ""),
        "description": item["snippet"].get("description", ""),
        "thumbnail": item["snippet"]["thumbnails"]["default"]["url"],
        "subscriber_count": int(item["statistics"].get("subscriberCount", 0)),
        "view_count": int(item["statistics"].get("viewCount", 0)),
        "video_count": int(item["statistics"].get("videoCount", 0)),
        "uploads_playlist_id": item["contentDetails"]["relatedPlaylists"]["uploads"],
        "channel_url": f"https://www.youtube.com/channel/{channel_id}",
    }


def get_recent_video_ids(playlist_id, max_videos):
    video_ids = []
    next_page_token = None

    while len(video_ids) < max_videos:
        url = "https://www.googleapis.com/youtube/v3/playlistItems"
        params = {
            "part": "contentDetails",
            "playlistId": playlist_id,
            "maxResults": min(50, max_videos - len(video_ids)),
            "key": API_KEY,
        }

        if next_page_token:
            params["pageToken"] = next_page_token

        data = requests.get(url, params=params).json()

        for item in data.get("items", []):
            video_ids.append(item["contentDetails"]["videoId"])

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    return video_ids


def get_video_details(video_ids):
    rows = []

    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(batch),
            "key": API_KEY,
        }

        data = requests.get(url, params=params).json()

        for item in data.get("items", []):
            stats = item.get("statistics", {})
            snippet = item.get("snippet", {})
            content = item.get("contentDetails", {})

            rows.append({
                "제목": snippet.get("title", ""),
                "게시일": snippet.get("publishedAt", "")[:10],
                "조회수": int(stats.get("viewCount", 0)),
                "좋아요수": int(stats.get("likeCount", 0)),
                "댓글수": int(stats.get("commentCount", 0)),
                "영상길이(분)": parse_duration(content.get("duration", "PT0M")),
                "영상URL": f"https://www.youtube.com/watch?v={item['id']}",
            })

    return pd.DataFrame(rows)


# -----------------------------
# 사이드바
# -----------------------------
st.sidebar.header("⚙️ 분석 설정")

channel_input = st.sidebar.text_input(
    "유튜브 채널 URL / 채널 ID / 핸들",
    value="https://www.youtube.com/@tikitakaboo"
)

max_videos = st.sidebar.slider(
    "분석할 최근 영상 수",
    min_value=5,
    max_value=100,
    value=50,
    step=5
)

st.sidebar.markdown("---")
st.sidebar.subheader("💰 수익 예측 설정")

rpm = st.sidebar.slider(
    "예상 RPM(조회수 1,000회당 수익, 원)",
    min_value=300,
    max_value=5000,
    value=1500,
    step=100
)

analyze_btn = st.sidebar.button("채널 분석 시작")

# -----------------------------
# 메인 실행
# -----------------------------
if analyze_btn:
    channel_id = get_channel_id(channel_input)

    if not channel_id:
        st.error("채널 ID를 찾을 수 없습니다. 채널 URL 또는 @핸들을 다시 확인하세요.")
        st.stop()

    with st.spinner("채널 정보를 불러오는 중입니다..."):
        channel_info = get_channel_info(channel_id)

    if not channel_info:
        st.error("채널 정보를 가져오지 못했습니다. API 키 또는 채널 주소를 확인하세요.")
        st.stop()

    st.subheader("📌 채널 기본 정보")

    col_img, col_info = st.columns([1, 3])

    with col_img:
        st.image(channel_info["thumbnail"], width=160)

    with col_info:
        st.markdown(f"## {channel_info['title']}")
        st.write(channel_info["description"][:150] + "...")
        st.link_button("채널 바로가기", channel_info["channel_url"])

    col1, col2, col3 = st.columns(3)
    col1.metric("구독자 수", format_number(channel_info["subscriber_count"]))
    col2.metric("총 조회수", format_number(channel_info["view_count"]))
    col3.metric("전체 영상 수", format_number(channel_info["video_count"]))

    with st.spinner("최근 영상 데이터를 분석하는 중입니다..."):
        video_ids = get_recent_video_ids(channel_info["uploads_playlist_id"], max_videos)
        videos_df = get_video_details(video_ids)

    if videos_df.empty:
        st.warning("분석할 영상 데이터를 가져오지 못했습니다.")
        st.stop()

    st.success(f"최근 영상 {len(videos_df)}개를 분석했습니다.")

    # -----------------------------
    # 핵심 지표
    # -----------------------------
    st.subheader("📊 최근 영상 핵심 지표")

    avg_views = videos_df["조회수"].mean()
    avg_likes = videos_df["좋아요수"].mean()
    avg_comments = videos_df["댓글수"].mean()
    avg_duration = videos_df["영상길이(분)"].mean()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("평균 조회수", format_number(avg_views))
    col2.metric("평균 좋아요 수", format_number(avg_likes))
    col3.metric("평균 댓글 수", format_number(avg_comments))
    col4.metric("평균 영상 길이", f"{avg_duration:.1f}분")

    # -----------------------------
    # 수익 예측
    # -----------------------------
    st.subheader("💰 최근 영상 예상 수익 예측")

    total_recent_views = videos_df["조회수"].sum()
    estimated_revenue = total_recent_views / 1000 * rpm
    avg_revenue_per_video = estimated_revenue / len(videos_df)

    col1, col2, col3 = st.columns(3)
    col1.metric("분석 영상 총 조회수", f"{total_recent_views:,.0f}회")
    col2.metric("적용 RPM", f"{rpm:,.0f}원")
    col3.metric("예상 수익", f"{estimated_revenue:,.0f}원")

    col4, col5 = st.columns(2)
    col4.metric("영상 1개당 평균 예상 수익", f"{avg_revenue_per_video:,.0f}원")
    col5.metric("최근 영상 수", f"{len(videos_df)}개")

    st.info(
        "※ 실제 유튜브 수익이 아니라 조회수와 사용자가 입력한 RPM을 바탕으로 계산한 단순 추정값입니다. "
        "실제 수익은 광고 단가, 시청 국가, 영상 길이, 광고 노출률, 쇼츠 여부 등에 따라 크게 달라질 수 있습니다."
    )

    # -----------------------------
    # 그래프
    # -----------------------------
    st.subheader("🔥 조회수 TOP 10 영상")

    top_views = videos_df.sort_values("조회수", ascending=False).head(10)

    fig_top = px.bar(
        top_views,
        x="조회수",
        y="제목",
        orientation="h",
        title="조회수 TOP 10 영상"
    )
    fig_top.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_top, use_container_width=True)

    st.subheader("👍 좋아요 수 TOP 10 영상")

    top_likes = videos_df.sort_values("좋아요수", ascending=False).head(10)

    fig_likes = px.bar(
        top_likes,
        x="좋아요수",
        y="제목",
        orientation="h",
        title="좋아요 수 TOP 10 영상"
    )
    fig_likes.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_likes, use_container_width=True)

    st.subheader("💬 댓글 수 TOP 10 영상")

    top_comments = videos_df.sort_values("댓글수", ascending=False).head(10)

    fig_comments = px.bar(
        top_comments,
        x="댓글수",
        y="제목",
        orientation="h",
        title="댓글 수 TOP 10 영상"
    )
    fig_comments.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_comments, use_container_width=True)

    st.subheader("📈 게시일별 조회수 변화")

    videos_df["게시일"] = pd.to_datetime(videos_df["게시일"])
    df_date = videos_df.sort_values("게시일")

    fig_date = px.line(
        df_date,
        x="게시일",
        y="조회수",
        markers=True,
        title="최근 영상 게시일별 조회수"
    )
    st.plotly_chart(fig_date, use_container_width=True)

    # -----------------------------
    # 수익 예측 그래프
    # -----------------------------
    st.subheader("💵 영상별 예상 수익 TOP 10")

    videos_df["예상수익"] = videos_df["조회수"] / 1000 * rpm
    top_revenue = videos_df.sort_values("예상수익", ascending=False).head(10)

    fig_revenue = px.bar(
        top_revenue,
        x="예상수익",
        y="제목",
        orientation="h",
        title="영상별 예상 수익 TOP 10"
    )
    fig_revenue.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig_revenue, use_container_width=True)

    # -----------------------------
    # 데이터 표
    # -----------------------------
    st.subheader("📋 영상 데이터")

    show_df = videos_df.copy()
    show_df["게시일"] = show_df["게시일"].dt.strftime("%Y-%m-%d")
    show_df["예상수익"] = show_df["예상수익"].round(0).astype(int)

    st.dataframe(show_df, use_container_width=True)

    csv = show_df.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "📥 분석 결과 CSV 다운로드",
        data=csv,
        file_name="youtube_channel_analysis.csv",
        mime="text/csv"
    )

else:
    st.info("왼쪽 사이드바에서 채널 주소를 입력하고 [채널 분석 시작] 버튼을 누르세요.")
