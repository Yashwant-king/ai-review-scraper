import streamlit as st
import os
import time
import pandas as pd
from dotenv import load_dotenv
from scraper import scrape_reviews, detect_platform, SUPPORTED_PLATFORMS, PLATFORM_ICONS
from preprocess import preprocess_all
from llm import analyze_chunked_review

load_dotenv()

st.set_page_config(
    page_title="AI Review Scraper",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #6366f1, #8b5cf6, #06b6d4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .subtitle { color: #94a3b8; font-size: 1rem; margin-bottom: 1.5rem; }
    
    .stat-card {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        text-align: center;
    }
    .stat-number { font-size: 2rem; font-weight: 700; color: #6366f1; }
    .stat-label { font-size: 0.8rem; color: #94a3b8; margin-top: 2px; }
    
    .review-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-left: 4px solid #6366f1;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
    }
    .sentiment-positive { border-left-color: #22c55e !important; }
    .sentiment-negative { border-left-color: #ef4444 !important; }
    .sentiment-mixed    { border-left-color: #f59e0b !important; }
    .sentiment-neutral  { border-left-color: #94a3b8 !important; }
    
    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-positive { background: #166534; color: #86efac; }
    .badge-negative { background: #7f1d1d; color: #fca5a5; }
    .badge-mixed    { background: #78350f; color: #fcd34d; }
    .badge-neutral  { background: #1e293b; color: #94a3b8; border: 1px solid #334155; }
    
    div[data-testid="stSidebarContent"] { background: #0f172a; }
    .stButton button {
        background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)


# =====================
# SIDEBAR
# =====================
with st.sidebar:
    st.markdown("## 🔍 AI Review Scraper")
    st.markdown("Scrape product reviews and analyze them with AI")
    st.divider()

    # LLM Provider selection
    st.markdown("### 🤖 LLM Provider")
    provider = st.selectbox(
        "Choose AI Provider",
        ["OpenRouter", "Groq", "OpenAI", "Gemini"],
        index=0,
        help="OpenRouter gives access to many models including GPT-4o"
    )

    # model info
    model_info = {
        "OpenRouter": "openai/gpt-4o-mini (via openrouter.ai)",
        "Groq":       "llama-3.3-70b-versatile (fastest, free)",
        "OpenAI":     "gpt-4o-mini",
        "Gemini":     "gemini-1.5-flash"
    }
    default_models = {
        "OpenRouter": "openai/gpt-4o-mini",
        "Groq":       "llama-3.3-70b-versatile",
        "OpenAI":     "gpt-4o-mini",
        "Gemini":     "gemini-1.5-flash"
    }
    st.caption(f"Default model: `{model_info[provider]}`")

    # Custom model override
    custom_model = st.text_input(
        "🧠 Model name (optional override)",
        value="",
        placeholder=default_models[provider],
        help="Leave blank to use the default model. For OpenRouter use format: provider/model-name"
    )
    selected_model = custom_model.strip() if custom_model.strip() else default_models[provider]

    # API key input — loads from .env silently, never shown in UI
    env_keys = {
        "OpenRouter": "OPENROUTER_API_KEY",
        "Groq":       "GROQ_API_KEY",
        "OpenAI":     "OPENAI_API_KEY",
        "Gemini":     "GEMINI_API_KEY",
    }
    env_key = os.getenv(env_keys[provider], "")
    user_key = st.text_input(
        f"🔑 {provider} API Key",
        type="password",
        value="",
        placeholder=f"Enter your {provider} API key..."
    )
    # use user-provided key first, fallback to .env key
    api_key = user_key if user_key else env_key
    if env_key and not user_key:
        st.caption("✅ Key loaded from `.env` file")

    link_map = {
        "OpenRouter": "https://openrouter.ai/keys",
        "Groq":   "https://console.groq.com",
        "OpenAI": "https://platform.openai.com/api-keys",
        "Gemini": "https://aistudio.google.com/app/apikey"
    }
    st.caption(f"Get key → [{link_map[provider]}]({link_map[provider]})")

    st.divider()

    # scraper settings
    st.markdown("### ⚙️ Scraper Settings")
    max_pages = st.slider("Max review pages", 1, 5, 2)

    st.divider()
    st.markdown("#### 📌 Quick Links")
    st.markdown("- [OpenRouter (Free credits)](https://openrouter.ai/keys)")
    st.markdown("- [Get Groq Key (Free)](https://console.groq.com)")
    st.markdown("- [Get OpenAI Key](https://platform.openai.com/api-keys)")
    st.markdown("- [Get Gemini Key (Free)](https://aistudio.google.com/app/apikey)")


# =====================
# MAIN UI
# =====================
st.markdown('<div class="main-title">🔍 AI Review Scraper</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Scrape product reviews from major platforms → Analyze with AI → Export results</div>',
            unsafe_allow_html=True)

# URL input
col1, col2 = st.columns([4, 1])
with col1:
    url = st.text_input(
        "Product URL",
        value="",
        placeholder="Paste a product or review page URL…",
        label_visibility="collapsed"
    )
with col2:
    run_btn = st.button("🚀 Analyze", use_container_width=True)

st.caption(
    "Supported: "
    "🛒 Amazon · "
    "🛍️ Flipkart · "
    "⭐ Trustpilot · "
    "🏷️ eBay · "
    "🖥️ Best Buy · "
    "💼 G2"
)
st.divider()


# =====================
# ANALYSIS
# =====================
if run_btn:
    if not api_key:
        st.error(f"Please enter your {provider} API key in the sidebar")
        st.stop()

    if not url.strip():
        st.error("Please enter a product URL")
        st.stop()

    # detect platform before starting
    platform = detect_platform(url.strip())
    platform_icon = PLATFORM_ICONS.get(platform, "❓")

    if platform == "Unknown":
        st.error(
            "**Unsupported website.**\n\n"
            f"Supported platforms: {', '.join(SUPPORTED_PLATFORMS)}\n\n"
            "Please paste a URL from one of the supported sites."
        )
        st.stop()

    st.info(f"{platform_icon} Detected platform: **{platform}**")

    # step 1: scrape
    with st.status(f"📦 Scraping {platform} reviews...", expanded=True) as status:
        st.write(f"Scraping `{url}` (up to {max_pages} pages)…")
        reviews, debug = scrape_reviews(url, max_pages=max_pages, status_cb=st.write)

        if not reviews:
            status.update(label="❌ Scraping returned 0 reviews", state="error")
            html_info = ""
            if debug.get("html_sizes"):
                avg = sum(debug["html_sizes"]) // len(debug["html_sizes"])
                html_info = f" (received ~{avg:,} bytes of HTML per page)"

            st.error(
                f"**{platform} returned 0 reviews{html_info}.**\n\n"
                "**Why this happens:**\n"
                f"- {platform} requires JavaScript to load reviews — plain HTTP requests can't see them\n"
                "- Your IP may be rate-limited or flagged as a bot\n"
                "- The page structure may have changed since this parser was written\n\n"
                "**What you can try:**\n"
                "- ⭐ **Trustpilot** works best — paste a URL like `https://www.trustpilot.com/review/amazon.com`\n"
                "- Wait a few minutes and retry\n"
                "- Use a VPN or different network\n"
                "- Check the debug output above for the HTML preview to understand what was received"
            )
            st.stop()

        st.write(f"✅ Got {len(reviews)} reviews from {platform}")

        # step 2: preprocess
        st.write("🧹 Cleaning and chunking text...")
        processed = preprocess_all(reviews)
        st.write(f"✅ {len(processed)} reviews ready for analysis")
        status.update(label=f"✅ Scraped {len(reviews)} {platform} reviews!", state="complete")

    # step 3: LLM analysis
    st.markdown(f"### 🤖 Analyzing {platform} reviews with {provider}...")

    progress = st.progress(0)
    results = []

    result_container = st.empty()

    for i, review in enumerate(processed, 1):
        progress.progress(i / len(processed))

        analysis = analyze_chunked_review(
            review["chunks"],
            provider=provider,
            api_key=api_key,
            model=selected_model
        )

        results.append({
            "author": review.get("author", "Unknown"),
            "rating": review.get("rating", "N/A"),
            "date": review.get("date", "N/A"),
            "title": review.get("title", ""),
            "review_text": review.get("review_text", ""),
            "llm_summary": analysis.get("summary", ""),
            "sentiment": analysis.get("sentiment", "Unknown"),
            "provider": provider
        })

        # show live result cards
        with result_container.container():
            s = analysis.get("sentiment", "Unknown").lower()
            css_class = f"sentiment-{s}" if s in ["positive", "negative", "mixed", "neutral"] else ""
            badge_class = f"badge-{s}" if s in ["positive", "negative", "mixed", "neutral"] else "badge-neutral"

            st.markdown(f"""
            <div class="review-card {css_class}">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <b>{review.get('title', 'Review')}</b>
                    <span class="badge {badge_class}">{analysis.get('sentiment', '?')}</span>
                </div>
                <div style="color:#94a3b8; font-size:0.8rem; margin:4px 0;">
                    ⭐ {review.get('rating', 'N/A')} &nbsp;|&nbsp; {review.get('author', '?')} &nbsp;|&nbsp; {review.get('date', '')}
                </div>
                <div style="font-size:0.9rem; color:#cbd5e1;">{analysis.get('summary', '')}</div>
            </div>
            """, unsafe_allow_html=True)

        time.sleep(0.5)

    progress.progress(1.0)
    st.success(f"✅ Analysis complete — {len(results)} reviews processed using {provider} / `{selected_model}`")

    # step 4: stats + output
    df = pd.DataFrame(results)

    st.divider()
    st.markdown("### 📊 Results Summary")

    counts = df["sentiment"].value_counts()
    total = len(df)

    cols = st.columns(len(counts) + 2)
    for idx, (sent, cnt) in enumerate(counts.items()):
        with cols[idx]:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number">{cnt}</div>
                <div class="stat-label">{sent}</div>
            </div>
            """, unsafe_allow_html=True)

    try:
        avg = df[df["rating"] != "N/A"]["rating"].astype(float).mean()
        with cols[-2]:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-number">{avg:.1f}⭐</div>
                <div class="stat-label">Avg Rating</div>
            </div>
            """, unsafe_allow_html=True)
    except Exception:
        pass

    with cols[-1]:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{total}</div>
            <div class="stat-label">Total Reviews</div>
        </div>
        """, unsafe_allow_html=True)

    # full results table
    st.divider()
    st.markdown("### 📋 Full Results")
    st.dataframe(
        df[["author", "rating", "title", "llm_summary", "sentiment"]],
        use_container_width=True,
        hide_index=True
    )

    # download button
    csv_data = df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="⬇️ Download CSV",
        data=csv_data,
        file_name="reviews_analysis.csv",
        mime="text/csv",
        use_container_width=True
    )

else:
    # landing state
    st.markdown("""
    ### How it works
    1. **Paste a product or review page URL** from any supported platform
    2. **Choose your LLM** in the sidebar (OpenRouter is recommended — free credits available)
    3. **Enter your API key** in the sidebar
    4. Click **🚀 Analyze** — the app scrapes reviews and runs AI analysis on each one
    5. **Download results** as CSV
    """)

    st.markdown("### 🌐 Supported Platforms")
    p1, p2, p3 = st.columns(3)
    with p1:
        st.info("🛒 **Amazon**\namazon.com product pages")
        st.info("🏷️ **eBay**\nebay.com product pages")
    with p2:
        st.info("🛍️ **Flipkart**\nflipkart.com product pages")
        st.info("🖥️ **Best Buy**\nbestbuy.com product pages")
    with p3:
        st.info("⭐ **Trustpilot**\ntrustpilot.com/review/...")
        st.info("💼 **G2**\ng2.com/products/.../reviews")

    st.markdown("### 🤖 LLM Providers")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.info("🌐 **OpenRouter** (★ Recommended)\nAccess GPT-4o, Claude, Llama via one key")
    with c2:
        st.info("🤖 **Groq** (Free)\nFastest option, Llama 3.3-70b")
    with c3:
        st.info("🟢 **OpenAI**\nGPT-4o-mini, paid")
    with c4:
        st.info("💎 **Gemini** (Free tier)\nGemini 1.5 Flash")
