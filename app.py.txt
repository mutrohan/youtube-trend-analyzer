import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from datetime import datetime, timedelta

st.title("YouTube Trend Analyzer")

api_key = st.text_input("YouTube API Key", type="password")
query = st.text_input("Aramak istediğiniz konu")
min_views = st.number_input("Minimum görüntülenme sayısı", value=500000, step=10000)
days = st.slider("Son kaç gün içinde?", 1, 60, 30)

def iso8601_days_ago(days):
    dt = datetime.utcnow() - timedelta(days=days)
    return dt.isoformat("T") + "Z"

def get_videos(api_key, query, min_views, days):
    youtube = build("youtube", "v3", developerKey=api_key)
    published_after = iso8601_days_ago(days)

    # Video arama
    search_response = youtube.search().list(
        q=query,
        part="id,snippet",
        type="video",
        order="viewCount",
        publishedAfter=published_after,
        maxResults=50
    ).execute()

    videos = []
    video_ids = [item["id"]["videoId"] for item in search_response.get("items", [])]

    # Video detaylarını al
    if not video_ids:
        return []

    videos_response = youtube.videos().list(
        part="snippet,statistics",
        id=",".join(video_ids),
        maxResults=50
    ).execute()

    for item in videos_response.get("items", []):
        stats = item.get("statistics", {})
        view_count = int(stats.get("viewCount", 0))
        if view_count >= min_views:
            videos.append({
                "Video Başlığı": item["snippet"].get("title", ""),
                "Kanal": item["snippet"].get("channelTitle", ""),
                "Yayın Tarihi": item["snippet"].get("publishedAt", ""),
                "Görüntülenme": view_count,
                "Beğeni": int(stats.get("likeCount", 0)),
                "Açıklama": item["snippet"].get("description", ""),
                "Etiketler": ", ".join(item["snippet"].get("tags", [])),
                "Video URL": f"https://www.youtube.com/watch?v={item['id']}"
            })

    return videos

if st.button("Analizi Başlat"):
    if not api_key or not query:
        st.error("Lütfen API anahtarını ve konuyu gir.")
    else:
        with st.spinner("Veriler çekiliyor..."):
            results = get_videos(api_key, query, min_views, days)
            if not results:
                st.warning("Veri bulunamadı veya kriterlere uyan video yok.")
            else:
                df = pd.DataFrame(results)
                st.dataframe(df)
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("📥 CSV olarak indir", csv, "youtube_trend.csv", "text/csv")
