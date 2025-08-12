# app.py
import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from collections import Counter, defaultdict
import re
import random
import math
import datetime

# -------------------------------
# KULLANIM / ÇALIŞTIRMA
# -------------------------------
# 1) Google Cloud Console -> YouTube Data API v3 aktif et -> API key al
# 2) Bu dosyada API_KEY değişkenine anahtarı koy
# 3) Gerekli paketleri yükle:
#    pip install streamlit pandas google-api-python-client
# 4) Çalıştır:
#    streamlit run app.py
#
# UYARI: YouTube Data API kota sınırlarınız olabilir. Çok sık istek atmayın.

# -------------------------------
# AYARLAR
# -------------------------------
API_KEY = "BURAYA_YOUR_YOUTUBE_API_KEY_YAZIN"  # <<-- buraya YouTube API key
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

# Basit stopword set (TR + EN); ihtiyaç varsa genişletin
STOPWORDS_TR = {
    "ve","ile","bir","bu","da","de","için","ben","sen","o","gibi","çok","en","ama",
    "ise","olarak","kadar","mi","mı","mu","mü","var","yok","şu","burada","hemen",
    "ile", "nasıl", "niçin", "neden"
}
STOPWORDS_EN = {
    "the","and","for","with","this","that","from","your","you","are","how","what",
    "will","can","have","has","but","not","our","they","their","about","more","get",
    "a","an","in","on","to","of","is","it"
}
STOPWORDS = STOPWORDS_TR.union(STOPWORDS_EN)

# Power words & hooks to increase CTR
POWER_WORDS = [
    "Hızlı", "Kolay", "Kesin", "Adım Adım", "Uzman", "Güncel",
    "2025", "Sıfırdan", "Başlangıç", "Etkili", "Sırları", "İpuçları",
    "Taktikler", "Hatalar", "En İyi", "Mutlaka"
]
BRACKET_OPTIONS = ["(Kolay)", "(2025)", "[Hızlı Rehber]", "(%100 Çalışır)"]

# Utility: YouTube client
def get_youtube_client():
    if not API_KEY or API_KEY.strip() == "":
        return None
    try:
        return build(API_SERVICE_NAME, API_VERSION, developerKey=API_KEY)
    except Exception as e:
        st.error(f"YouTube client başlatılamadı: {e}")
        return None

# -------------------------------
# TEXT PROCESSING & SEO ALGORITHMASI
# -------------------------------
def clean_text(text):
    if not text:
        return ""
    # remove urls and extra spaces
    text = re.sub(r'http\S+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def tokenize(text):
    text = clean_text(text).lower()
    tokens = re.findall(r"[a-zA-ZığüşöçİĞÜŞÖÇ0-9]+", text)
    tokens = [t for t in tokens if t not in STOPWORDS and len(t) > 2]
    return tokens

def extract_ngrams(tokens, n):
    if len(tokens) < n:
        return []
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens)-n+1)]

def score_keywords(titles, descriptions):
    """
    Basit TF scoring with title-weight boost.
    Returns sorted keywords (unigrams + bigrams) with scores.
    """
    tf = Counter()
    # Title words weighted higher
    for t in titles:
        toks = tokenize(t)
        for tok in toks:
            tf[tok] += 3  # title weight
        # bigrams from title
        for bg in extract_ngrams(toks, 2):
            tf[bg] += 4
    # Description words less weight
    for d in descriptions:
        toks = tokenize(d)
        for tok in toks:
            tf[tok] += 1
        for bg in extract_ngrams(toks, 2):
            tf[bg] += 1.5

    # Normalize / sort
    items = sorted(tf.items(), key=lambda x: x[1], reverse=True)
    return items

def pick_primary_keyword(topic, scored_keywords):
    # Prefer exact topic tokens if present; else top keyword
    topic_tokens = tokenize(topic)
    for k, _ in scored_keywords:
        # full match
        if k in topic_tokens or all(tok in k.split() for tok in topic_tokens if len(tok)>2):
            return k
    return scored_keywords[0][0] if scored_keywords else topic

def make_title(primary, secondary_candidates, topic):
    """
    Title heuristics:
     - include primary keyword prominently
     - include a hook/power word or number + bracket
     - length <= 100
    """
    # try variants
    variants = []
    # Variant: "Primary — Hook"
    hook = random.choice(POWER_WORDS)
    variants.append(f"{primary.title()} — {hook}")
    # Variant: "How to Primary (2025) | Quick Guide"
    variants.append(f"{primary.title()} {random.choice(BRACKET_OPTIONS)} | Hızlı Rehber")
    # Variant: "Top N Primary Tips"
    n = random.choice([5,7,10])
    variants.append(f"{n} {primary.title()} İpucu | {random.choice(['Başlangıç','Hızlı Öğrenme'])}")
    # Variant: "Primary: Secondary — Hook"
    if secondary_candidates:
        sec = secondary_candidates[0].title()
        variants.append(f"{primary.title()}: {sec} — {random.choice(POWER_WORDS)}")
    # Variant: topic-based fallback
    variants.append(f"{topic.title()} — {random.choice(POWER_WORDS)}")
    # Choose best -> prefer medium length and containing primary
    def score_variant(v):
        length_penalty = abs(len(v) - 60) / 60  # prefer around 60 chars
        power_bonus = sum(1 for p in POWER_WORDS if p in v)
        return power_bonus - length_penalty
    variants = sorted(variants, key=score_variant, reverse=True)
    title = variants[0][:100]
    # ensure primary appears
    if primary.lower() not in title.lower():
        title = f"{primary.title()} — {title}"
    return title

def make_description(topic, primary_keyword, top_keywords):
    # First 1-2 lines: hook + primary keyword; these must appear early (first 100 chars)
    hook_templates = [
        f"Bu videoda {primary_keyword} hakkında bilmeniz gereken her şeyi adım adım öğreneceksiniz.",
        f"{primary_keyword} konusunda hızlı ve etkili bir rehber: başlangıçtan ileri seviyeye.",
        f"{primary_keyword} — en güncel yöntemler ve uygulamalı örneklerle."
    ]
    first_lines = random.choice(hook_templates)

    # build sections
    topics_sample = ", ".join(top_keywords[:8])
    body = (
        f"{first_lines}\n\n"
        f"Videoda ele alınan başlıca konular: {topics_sample}.\n\n"
        "📌 Bu videoda:\n"
        "- Temel kavramlar ve neden önemli olduklarını anlattık\n"
        "- Uygulamalı örneklerle nasıl yapılacağını gösterdik\n"
        "- Sık yapılan hatalar ve nasıl kaçınılacağı\n\n"
        "⏱ Bölümler:\n"
        # placeholder chapters; user will edit times before upload
        "00:00 – Giriş\n05:00 – Temel Kavramlar\n12:00 – Uygulamalı Örnekler\n20:00 – İleri İpuçları\n\n"
        "👉 Videoyu beğendiyseniz lütfen beğen butonuna basın ve abone olun. Yorumlarda hangi konuyu daha detaylı görmek istediğinizi yazın.\n\n"
    )
    # Add suggested hashtags at end (will be returned separately too)
    return first_lines + "\n\n" + body

def generate_tags(topic, scored_keywords, desired=40):
    """
    Build 40 tags mixing:
     - exact topic tokens
     - top unigrams
     - bigrams
     - english variations (simple heuristics)
     - suffixes and tag templates
    """
    tags = []
    topic_tokens = tokenize(topic)
    # 1. topic tokens
    for t in topic_tokens:
        if t not in tags: tags.append(t)
    # 2. top keywords (scored_keywords is list of tuples)
    for k, _ in scored_keywords:
        if k not in tags:
            tags.append(k)
    # 3. split bigrams into components
    for t in list(tags):
        for part in t.split():
            if part not in tags:
                tags.append(part)
    # 4. english simple map / suffixes
    suffixes = ["tutorial","howto","guide","tips","beginner","2025","easy","fast","tr"]
    for s in suffixes:
        candidate = f"{topic_tokens[0]} {s}" if topic_tokens else s
        candidate = candidate.strip()
        if candidate not in tags:
            tags.append(candidate)
    # 5. category-ish tags & variants
    cat = ["eğitim","öğrenme","tutorial","ders","nasıl yapılır"]
    for c in cat:
        if c not in tags:
            tags.append(c)
    # 6. ensure uniqueness & lowercase, trim/pad to desired
    final = []
    for t in tags:
        t_clean = t.lower()[:50]  # youtube tag length limit roughly 500 chars total; per tag up to 500? keep 50 safe
        if t_clean not in final:
            final.append(t_clean)
        if len(final) >= desired:
            break
    # pad if needed with numbered variants
    i = 1
    while len(final) < desired:
        cand = f"{topic.replace(' ', '_')}_{i}"
        final.append(cand[:50])
        i += 1
    return final[:desired]

def pick_hashtags(tags):
    # choose up to 3 hashtag candidates from top tags (no spaces)
    hashtags = []
    for t in tags:
        if len(hashtags) >= 3:
            break
        if " " not in t and len(t) > 2 and not any(ch.isdigit() for ch in t[:1]):
            hashtags.append("#" + t)
    # fallback generate from first tag words
    if not hashtags:
        hashtags = ["#" + tags[0].split()[0]]
    return hashtags

def suggest_thumbnail_text(primary, secondary):
    # Short punchy phrase
    opts = [
        f"EN İYİ {primary.upper()}",
        f"{primary.upper()} HIZLI ÖĞREN",
        f"{secondary.upper() if secondary else 'KISA REHBER'}",
        f"{primary.upper()} - ADIM ADIM"
    ]
    return random.choice(opts)

# -------------------------------
# STREAMLIT UI
# -------------------------------
st.set_page_config(page_title="YouTube Upload Helper (SEO+Trend)", page_icon="📺", layout="wide")
st.title("YouTube Upload Helper — Yeni Başlayanlar için Yüklemeye Hazır Öneriler")

tab1, tab2, tab3 = st.tabs(["Trend Analizi", "Video Yükleme Yardımcısı", "Yükleme Kontrol Listesi & İpuçları"])

# ---------- TAB 1: Trend Analizi ----------
with tab1:
    st.header("Trend Analizi — Ülke & Konu Bazlı")
    yt = get_youtube_client()
    if not yt:
        st.warning("YouTube API key eksik veya hatalı. Üstte API_KEY değişkenine anahtarınızı ekleyin.")
    query = st.text_input("Arama terimi (ör: Python makine öğrenmesi):", value="python tutorial")
    country_code = st.selectbox("Ülke (regionCode):", ["TR","US","GB","DE","FR","IN","JP","BR","CA","ES"], index=0)
    max_results = st.slider("Çekilecek video sayısı", 5, 50, 15)

    if st.button("Trendleri Çek ve Göster"):
        if not yt:
            st.stop()
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
                snp = item.get("snippet", {})
                videos.append({
                    "Başlık": snp.get("title"),
                    "Kanal": snp.get("channelTitle"),
                    "Yayın Tarihi": snp.get("publishedAt"),
                    "Açıklama (Önizleme)": (snp.get("description") or "")[:250],
                    "Link": f"https://www.youtube.com/watch?v={item['id']['videoId']}"
                })
            df = pd.DataFrame(videos)
            st.dataframe(df)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("CSV İndir", csv, "youtube_trends.csv", "text/csv")
        except Exception as e:
            st.error(f"YouTube API hatası: {e}")

# ---------- TAB 2: Video Yükleme Yardımcısı ----------
with tab2:
    st.header("Video Yükleme Yardımcısı — Yüklemeye Hazır Çıktılar")
    with st.form("upload_helper_form"):
        topic = st.text_input("Video konusu (kısa ve net):", value="Python ile Yapay Zeka")
        country2 = st.selectbox("Trend Analizini Hangi Ülke Üzerinden Yapalım?", ["TR","US","GB","DE","FR","IN","JP","BR","CA","ES"], index=0)
        results_count = st.slider("Trend'den kaç video analiz edilsin?", 5, 50, 15)
        preferred_length = st.selectbox("Hedef Başlık Uzunluğu:", ["Kısa (≤50)", "Orta (~60)", "Uzun (≤100)"], index=1)
        submit = st.form_submit_button("Analiz Et & Öneri Oluştur")

    if submit:
        yt = get_youtube_client()
        if not yt:
            st.error("YouTube API client başlatılamadı. API_KEY kontrol edin.")
            st.stop()
        if not topic.strip():
            st.warning("Lütfen bir video konusu girin.")
            st.stop()

        with st.spinner("Trend videoları çekiliyor, anahtar kelimeler analiz ediliyor..."):
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
                sn = item.get("snippet", {})
                titles.append(clean_text(sn.get("title", "")))
                descriptions.append(clean_text(sn.get("description", "")))

            # Score keywords
            scored = score_keywords(titles, descriptions)  # list of (kw, score)
            # Extract lists
            scored_keywords = [k for k, s in scored]
            # Separate unigrams and multiword
            unigrams = [k for k in scored_keywords if " " not in k]
            multi = [k for k in scored_keywords if " " in k]

            primary = pick_primary_keyword(topic, scored)
            secondary = multi[0] if multi else (unigrams[1] if len(unigrams)>1 else None)

            # Build title & description & tags
            suggested_title = make_title(primary, [secondary] if secondary else [], topic)
            suggested_description = make_description(topic, primary, scored_keywords)
            suggested_tags = generate_tags(topic, scored, desired=40)
            suggested_hashtags = pick_hashtags(suggested_tags)
            thumbnail_text = suggest_thumbnail_text(primary, secondary)

            # Show results with copy buttons
            st.subheader("🔖 Önerilen Başlık (kopyala & yapıştır hazır)")
            st.code(suggested_title, language="text")
            st.markdown("**Uzunluk:** " + str(len(suggested_title)) + " karakter")

            st.subheader("📝 Önerilen Açıklama (ilk 2 satır önemli; 100-200 karakter içine CTA koyun)")
            st.text_area("Açıklama (düzenleyip kopyalayın)", value=suggested_description, height=260)

            st.subheader(f"🏷️ Önerilen 40 Etiket")
            st.write(", ".join(suggested_tags))

            st.subheader("🔗 Önerilen Hashtagler (açıklama içinde kullan)")
            st.write(" ".join(suggested_hashtags))

            st.subheader("🖼 Thumbnail Önerisi")
            st.write(f"Metin önerisi: **{thumbnail_text}**")
            st.write("Tasarım önerisi: büyük kontrastlı yazı (ör: beyaz/yellow), koyu arka plan, yüz/duygu ifadeleri, küçük metin değil büyük ve okunur")

            # Offer to download JSON with everything
            output = {
                "title": suggested_title,
                "description": suggested_description,
                "tags": suggested_tags,
                "hashtags": suggested_hashtags,
                "thumbnail_text": thumbnail_text,
                "primary_keyword": primary,
                "secondary_keyword": secondary,
                "analysis_date": datetime.datetime.utcnow().isoformat() + "Z",
                "source_country": country2,
                "analyzed_count": results_count
            }
            st.download_button("📥 Önerileri JSON olarak indir", data=pd.Series(output).to_json(), file_name="youtube_suggestion.json", mime="application/json")

            # Show top keywords summary
            st.markdown("**Analiz Özeti — Öne Çıkan Anahtar Kelimeler (Top 20)**")
            st.write(", ".join(scored_keywords[:20]))

# ---------- TAB 3: YÜKLEME KONTROL LİSTESİ & İPUÇLAR ----------
with tab3:
    st.header("Yükleme Kontrol Listesi & Kanal Büyütme İpuçları (Yeni Başlayanlar için)")
    st.markdown("""
    **Yükleme Kontrol Listesi (Upload-ready checklist):**
    1. Başlık: İlk 60 karakter güçlü, içinde anahtar kelime olsun. Parantez / yıl / sayı kullan.
    2. Açıklama: İlk 1-2 satır (100-150 karakter) izleyiciyi çekmeli — anahtar kelime + CTA (abone ol) olmalı.
    3. Etiketler: 40 adet; anahtar kelime + long-tail varyasyonlar + İngilizce varyasyonlar.
    4. Hashtag: 1-3 hashtag açıklamada (YouTube ilk 3'ü üstte gösterir).
    5. Thumbnail: Yüz, büyük metin, kontrast.
    6. Kategori: Doğru kategori seçin (Eğitim, Eğlence vs.)
    7. Dil ve altyazı: Video dili doğru seçin; mümkünse otomatik altyazıyı düzenleyin veya manuel altyazı ekleyin.
    8. Bölümler (chapters): Açıklamada timestamp ekleyin.
    9. Playlist: İlgili bir oynatma listesine ekleyin.
    10. Pinned comment & End screen: İlk yorumda CTAs, videonun sonunda end screen ekleyin.
    11. Küçük resim boyutu: 1280x720, JPG/PNG, max 2MB.
    12. Yayın zamanı: Hedef kitlenizin aktif olduğu saatlerde yayınlayın (hafta içi akşamlar vs).
    """)
    st.markdown("**İleri Seviye Kanal Büyütme İpuçları:**")
    st.markdown("""
    - İlk 10 saniye önemlidir: hemen değeri gösterin.
    - Düzenli içerik takvimi: haftada 1-2 video tavsiye edilir.
    - İzleyici etkileşimi: videonun sonunda açık bir CTA ile yorum/like/subscribe isteyin.
    - Thumbnail A/B testi: farklı tasarımlar deneyin.
    - Analitik takibi: YouTube Studio'dan izlenme süresi (watch time) ve click-through rate (CTR) takip edin.
    - Kısa formatları (Shorts) kullanarak kanal keşfedilebilirliğini artırın.
    """)
