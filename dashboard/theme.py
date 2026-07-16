"""CSS theme for the LiveSense Streamlit dashboard."""

THEME_CSS = """
<style>
  .stApp {
    background:
      radial-gradient(circle at 14% 8%, rgba(23, 194, 164, 0.10), transparent 30rem),
      #07100f;
    color: #edf7f5;
  }
  [data-testid="stHeader"] { background: transparent; }
  [data-testid="stSidebar"] {
    background: #0a1514;
    border-right: 1px solid rgba(130, 225, 205, 0.12);
  }
  .block-container { max-width: 1240px; padding-top: 2.4rem; }
  .ls-eyebrow {
    color: #73dec7; font-size: .76rem; font-weight: 700;
    letter-spacing: .16em; text-transform: uppercase;
  }
  .ls-title { font-size: clamp(2.4rem, 6vw, 4.7rem); line-height: .98; margin: .5rem 0; }
  .ls-title span { color: #70e0c5; }
  .ls-subtitle { color: #96aaa6; font-size: 1.08rem; margin-bottom: 2rem; }
  .ls-status {
    display: inline-flex; align-items: center; gap: .5rem; padding: .45rem .75rem;
    border: 1px solid rgba(112, 224, 197, .22); border-radius: 999px;
    background: rgba(112, 224, 197, .07); color: #bcece1; font-size: .82rem;
  }
  .ls-dot {
    width: .48rem; height: .48rem; border-radius: 50%;
    background: #70e0c5; box-shadow: 0 0 14px #70e0c5;
  }
  .ls-card {
    min-height: 9rem; padding: 1.1rem 1.15rem; border-radius: 1rem;
    background: rgba(12, 27, 25, .8); border: 1px solid rgba(130, 225, 205, .12);
  }
  .ls-card-label {
    color: #77908a; font-size: .74rem;
    letter-spacing: .11em; text-transform: uppercase;
  }
  .ls-card-value { font-size: 1.32rem; font-weight: 650; margin-top: .55rem; }
  .ls-card-note { color: #77908a; font-size: .82rem; margin-top: .4rem; }
  .stButton > button { border-radius: 999px; }
  video { border-radius: 1.15rem; border: 1px solid rgba(130, 225, 205, .15); }
</style>
"""
