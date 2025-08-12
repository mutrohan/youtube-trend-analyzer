import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from collections import Counter
import re
import random
import itertools

# -------------------------------
# AYARLAR
# -------------------------------
API_KEY = "BURAYA_YOUTUBE_API_KEYINIZI_YAZIN"  #
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

# Basit stopword listeleri (Türkçe + İngilizce, gerektiğinde genişlet)
STOPWORDS_TR = {
    "ve","ile","bir","bu","da","de","için","ben","sen","o","gibi","çok","en","ama",
    "ise","olarak","kadar","mi","mı","mu","mü","var","yok","şu","burada","hemen"
}
STOPWORDS_EN = {
    "the","and","for","with","this","that","from","your","you","are","how","what",
    "will","can","have","has","but","not","our","they","their","about","more","get"
}
STOPWORDS = STOPWORDS_TR.union(STOPWORDS_EN)

# Initialize YouTube client lazily (so app can start even if key empty)
def get_youtube_client():
    if not API_KEY or API_KEY.strip() == "":
        st.error("Lütfen üstteki API_KEY değişkenine YouTube API anahtarınızı ekleyin.")
        return None
    try:
        return build(API_SERVICE_NAME, API_VERSION, developerKey=API_KEY)
    except Exception as e:
        st.error(f"YouTube client başlatılamadı: {e}")
        return None

# -------------------------------
# YARDIMCI FONKSİYONLAR
# -------------------------------
def tokenize(text):
    # Küçük harfe çevir, alfasayısal kelimeleri al
    tokens = re.findall(r"[a-zA-ZığüşöçİĞÜŞÖÇ0-9]+", text.lower())
    # stopword ve kısa kelimeleri çıkar
    tokens = [t for t in tokens if t not in STOPWORDS and len(t) > 2]
    return tokens

def top_ngrams(texts, n=1, topk=20):
    # texts: iterable of strings
    tokens = []
    for t in texts:
        tokens.extend(tokenize(t))
    if not tokens:
        return []
    if n == 1:
        c = Counter(tokens)
        return [w for w,_ in c.most_common(topk)]
    else:
        # bigrams
        grams = zip(*[tokens[i:] for i in range(n)])
        grams = [" ".join(g) for g in grams]
        c = Counter(grams)
        return [w for w,_ in c.most_common(topk)]

def build_title(topic, keywords):
    # keywords: list of top unigrams/bigrams
    # Try to create clickable title: include main keyword + benefit/hook
    main = keywords[0] if keywords else topic
    second = keywords[1] if len(keywords) > 1 else ""
    hooks = [
        "Adım Adım Rehber", "Hızlı Öğrenme", "Başlangıçtan İleriye",
        "2025 Güncel Taktikler", "Bilinmesi Gerekenler", "Uzman İpuçları"
    ]
    hook = random.choice(hooks)
    title = f"{main.title()} { ('- ' + second.title()) if second else '' } — {hook}"
    # Ensure not too long
    return title[:100]

def build_description(topic, keywords):
    # Compose a multi-sentence description with keywords and CTA
    kw_sample = ", ".join(keywords[:6])
    desc = (
        f"Bu videoda **{topic}** hakkında en güncel ve pratik bilgileri paylaşıyorum. "
        f"Videoda ele alınan konular: {kw_sample}. "
        "Adım adım örneklerle öğrenip, hızlıca uygulamaya geçebileceksiniz.\n\n"
        "📌 Bölümler:\n"
        "- Giriş ve temel kavramlar\n"
        "- Uygulamalı örnekler\n"
        "- İleri ipuçları ve sık yapılan hatalar\n\n"
        "👉 Kanalıma abone olmayı ve videoyu beğenmeyi unutmayın! "
        "#eğitim #öğrenme"
    )
    return desc

def build_tags(topic, unigrams, bigrams, desired_count=40):
    tags = []
    # start with topic tokens
    topic_tokens = tokenize(topic)
    tags.extend(topic_tokens)
    # add top unigrams
    for u in unigrams:
        if u not in tags:
            tags.append(u)
    # add bigrams split and whole
    for b in bigrams:
        if b not in tags:
            tags.append(b)
        for part in b.split():
            if part not in tags:
                tags.append(part)
    # add common suffixes / translations
    extras = [
        "tutorial","howto","guide","öğren","eğitim","rehber","kolay","hızlı",
        "2025","temel","ileri","taktikler","ipuçları","tips"
    ]
    for e in extras:
        if e not in tags:
            tags.append(e)
    # ensure unique and lowercase, trim to desired_count
    final = []
    for t in tags:
        t_clean = t.lower()
        if t_clean not in final:
            final.append(t_clean)
        if len(final) >= desired_count:
            break
    # If still short, pad with numbered variants
    i = 1
    while len(final) < desired_count:
        candidate = f"{topic.replace(' ', '_')}_{i}"
        final.append(candidate[:50])
        i += 1
    return final[:desired_count]

# -------------------------------
# STREAMLIT ARAYÜZÜ
# -------------------------------
st.set_page_config(page_title="YouTube Trend + Akıllı Öneri", page_icon="📺", layout="wide")
st.title("YouTube Trend Analizi ve Akıllı Başlık/Açıklama/40 Etiket Önerici")

tab1, tab2 = st.tabs(["📈 Trend Analizi", "💡 Akıllı Öneri (API Keysiz AI)"])

# ---------- TAB 1: TREND ANALİZİ ----------
with tab1:
    st.header("Trend Analizi")
    query = st.text_input("Arama terimi:", value="python tutorial")
    country_code = st.selectbox("Ülke seç (regionCode):", ["TR","US","GB","DE","FR","IN","JP","BR","CA","ES"], index=0)
    max_results = st.slider("Max sonuç sayısı", 5, 50, 10)

    if st.button("Ara ve Göster", key="search_trends"):
        yt = get_youtube_client()
        if yt:
            try:
                req = yt.search().list(
                    q=query,
                    part="snippet",
                    type="video",
                    order="viewCount",
                    regionCode=country_code,
                    maxResults=max_results
                )
                res = req.execute()
                videos = []
                for item in res.get("items", []):
                    videos.append({
                        "Başlık": item["snippet"]["title"],
                        "Kanal": item["snippet"]["channelTitle"],
                        "Yayın Tarihi": item["snippet"]["publishedAt"],
                        "Açıklama (Önizleme)": item["snippet"]["description"][:200],
                        "Video Linki": f"https://www.youtube.com/watch?v={item['id']['videoId']}"
                    })
                df = pd.DataFrame(videos)
                st.dataframe(df)
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("📥 CSV indir", csv, "youtube_trends.csv", "text/csv")
            except Exception as e:
                st.error(f"Trend verisi alınırken hata: {e}")

# ---------- TAB 2: AKILLI ÖNERİ ----------
with tab2:
    st.header("Akıllı Başlık, Açıklama ve 40 Etiket Önerisi")
    topic = st.text_input("Video konusu (kısa):", value="Python ile Yapay Zeka")
    country2 = st.selectbox("Analiz Ülkesi (trendleri buradan çek):", ["TR","US","GB","DE","FR","IN","JP","BR","CA","ES"], index=0, key="country2")
    results_count = st.slider("Trendden kaç video analiz edilsin?", 5, 50, 15, key="rescount")

    if st.button("Öneri Oluştur", key="gen_suggestion"):
        yt = get_youtube_client()
        if not yt:
            st.stop()

        if not topic.strip():
            st.warning("Lütfen bir video konusu girin.")
            st.stop()

        with st.spinner("Trend videoları çekiliyor ve analiz ediliyor..."):
            try:
                req = yt.search().list(
                    q=topic,
                    part="snippet",
                    type="video",
                    order="viewCount",
                    regionCode=country2,
                    maxResults=results_count
                )
                res = req.execute()
            except Exception as e:
                st.error(f"YouTube araması başarısız: {e}")
                st.stop()

            titles = []
            descriptions = []
            for item in res.get("items", []):
                snip = item.get("snippet", {})
                titles.append(snip.get("title", ""))
                descriptions.append(snip.get("description", ""))

            # unigram ve bigram top kelimeler
            top_unigrams = top_ngrams(titles + descriptions, n=1, topk=30)
            top_bigrams = top_ngrams(titles + descriptions, n=2, topk=30)

            # Build suggestions
            suggested_title = build_title(topic, top_bigrams + top_unigrams)
            suggested_description = build_description(topic, top_unigrams)
            suggested_tags = build_tags(topic, top_unigrams, top_bigrams, desired_count=40)

            # Göster
            st.subheader("📌 Önerilen Başlık")
            st.write(suggested_title)

            st.subheader("📝 Önerilen Açıklama")
            st.markdown(suggested_description)

            st.subheader(f"🏷️ Önerilen 40 Etiket (adet: {len(suggested_tags)})")
            st.write(", ".join(suggested_tags))

            # Ayrıca gösterilen trend anahtar kelimeler (kısa özet)
            st.markdown("**Analiz sonucu öne çıkan anahtar kelimeler (top 15):**")
            st.write(", ".join(top_unigrams[:15]))
