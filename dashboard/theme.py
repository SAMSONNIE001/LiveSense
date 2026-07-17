"""Reference-aligned light dashboard theme for LiveSense."""

THEME_CSS = """
<style>
  :root {
    --green: #07966f;
    --green-dark: #087b5e;
    --green-soft: #e9f7f1;
    --ink: #182421;
    --muted: #70807b;
    --line: #dfe7e3;
    --surface: #ffffff;
    --canvas: #f5f7f6;
    --amber: #e89c25;
    --red: #d94c45;
  }
  html, body, [class*="css"] {
    font-family: Inter, "Segoe UI", Arial, sans-serif;
  }
  html, body, #root, .stApp, [data-testid="stAppViewContainer"] {
    height: 100vh;
    max-height: 100vh;
    overflow: hidden;
  }
  .stApp { background: var(--canvas); color: var(--ink); }
  [data-testid="stMain"] {
    height: 100vh;
    max-height: 100vh;
    overflow: hidden;
  }
  [data-testid="stHeader"] { background: transparent; height: 0; }
  [data-testid="stToolbar"] { display: none; }
  [data-testid="stSidebar"] {
    min-width: 218px;
    max-width: 218px;
    height: 100vh;
    max-height: 100vh;
    overflow: hidden;
    background: #ffffff;
    border-right: 1px solid var(--line);
  }
  [data-testid="stSidebar"] > div:first-child,
  [data-testid="stSidebarContent"],
  [data-testid="stSidebarUserContent"] {
    box-sizing: border-box;
    height: 100%;
    max-height: 100vh;
    overflow: hidden;
  }
  [data-testid="stSidebar"] > div:first-child,
  [data-testid="stSidebarContent"],
  [data-testid="stSidebarUserContent"] { padding: 1rem .8rem; }
  .block-container {
    box-sizing: border-box;
    height: 100vh;
    max-height: 100vh;
    max-width: 1540px;
    overflow: hidden;
    padding: .75rem 1.15rem .55rem;
  }
  .stApp p { color: var(--ink); }
  div[data-testid="stVerticalBlock"] { gap: .55rem; }
  div[data-testid="column"] { min-width: 0; }

  .brand { display: flex; gap: .65rem; align-items: center; margin-bottom: 1.15rem; }
  .brand-mark {
    display: grid; place-items: center; width: 2rem; height: 2rem;
    border-radius: .45rem; background: var(--green); color: white;
    font-size: .68rem; font-weight: 800;
  }
  .brand-title { font-size: .92rem; font-weight: 800; line-height: 1.1; }
  .brand-subtitle { color: var(--muted); font-size: .62rem; margin-top: .2rem; }
  .side-section {
    color: #82908c; font-size: .57rem; font-weight: 800;
    letter-spacing: .08em; margin: 1rem 0 .42rem;
  }
  .nav-item { padding: .58rem .62rem; border-radius: .35rem; font-size: .72rem; font-weight: 650; }
  .nav-active { background: var(--green-soft); color: var(--green-dark); }
  .nav-muted { color: #31403c; }
  [data-testid="stSidebar"] .stButton > button {
    min-height: 1.9rem; width: 100%; border-radius: .32rem;
    border: 1px solid #d9e2de; background: white; color: #263630;
    font-size: .66rem; font-weight: 700; padding: .28rem .45rem;
  }
  [data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: var(--green); color: white; border-color: var(--green);
  }
  [data-testid="stSidebar"] label { font-size: .62rem; color: #64736e; }
  [data-testid="stSidebar"] [data-baseweb="select"] > div {
    min-height: 1.95rem; border-color: #dde5e2; font-size: .67rem;
  }

  .topbar { display: flex; justify-content: flex-end; align-items: center; min-height: 2.15rem; }
  .user-chip { color: #5e6c67; font-size: .66rem; }
  .user-avatar {
    display: inline-block; width: 1.25rem; height: 1.25rem; margin: 0 .35rem;
    vertical-align: middle; border-radius: 50%;
    background: linear-gradient(135deg, #754b2a, #d08c55);
  }
  .status-banner {
    display: grid; grid-template-columns: auto 1fr auto; align-items: center;
    gap: .7rem; padding: .72rem .9rem; margin-bottom: .6rem;
    background: #eefaf4; border: 1px solid #bfe9d5; border-radius: .38rem;
  }
  .status-icon {
    display: grid; place-items: center; width: 2rem; height: 2rem;
    border-radius: 50%; background: #18ad7c; color: white; font-weight: 900;
  }
  .status-title { color: #087d5d; font-size: .87rem; font-weight: 800; }
  .status-copy { color: #49625a; font-size: .62rem; margin-top: .12rem; }
  .quality { min-width: 13rem; padding-left: 1rem; border-left: 1px solid #cfe9de; }
  .quality-row { display: flex; align-items: center; justify-content: space-between; gap: .8rem; }
  .quality-label { font-size: .62rem; font-weight: 800; }
  .quality-value { color: var(--green-dark); font-size: .67rem; font-weight: 800; }
  .quality-copy { color: #75847f; font-size: .55rem; margin-top: .16rem; }
  .alarm-banner {
    display: flex; align-items: center; gap: .75rem; margin-bottom: .55rem;
    padding: .72rem .9rem; border: 2px solid #d83e38; border-radius: .38rem;
    background: #fff0ef; color: #a92723; font-size: .68rem;
    animation: alarm-flash 1s ease-in-out infinite alternate;
  }
  .notice-banner {
    display: flex; align-items: center; gap: .75rem; margin-bottom: .55rem;
    padding: .72rem .9rem; border: 2px solid; border-radius: .38rem;
    font-size: .7rem; line-height: 1.45;
  }
  .notice-danger {
    border-color: #d83e38; background: #fff0ef; color: #9f201c;
  }
  .notice-critical { animation: alarm-flash 1.4s ease-in-out infinite alternate; }
  .notice-warning { border-color: #e5a12f; background: #fff8e9; color: #8b5a08; }
  .notice-icon {
    display: grid; place-items: center; flex: 0 0 auto;
    width: 2rem; height: 2rem; border-radius: 50%;
    background: #e5a12f; color: white; font-size: 1.1rem; font-weight: 900;
  }
  .danger-icon {
    display: grid; place-items: center; flex: 0 0 auto;
    width: 2rem; height: 2rem; border-radius: 50%;
    background: #d83e38; color: white; font-size: 1.1rem; font-weight: 900;
  }
  .alarm-pulse {
    display: grid; place-items: center; flex: 0 0 auto;
    width: 2rem; height: 2rem; border-radius: 50%;
    background: #d83e38; color: white; font-size: 1.1rem; font-weight: 900;
  }
  @keyframes alarm-flash {
    from { box-shadow: 0 0 0 rgba(216, 62, 56, 0); }
    to { box-shadow: 0 0 18px rgba(216, 62, 56, .28); }
  }

  .panel {
    height: 100%; background: var(--surface); border: 1px solid var(--line);
    border-radius: .35rem; box-shadow: 0 1px 3px rgba(30, 55, 47, .035);
    padding: .68rem;
  }
  .panel-head {
    display: flex; justify-content: space-between;
    align-items: center; margin-bottom: .5rem;
  }
  .panel-title { color: #25332e; font-size: .67rem; font-weight: 800; }
  .live-label { color: var(--green); font-size: .56rem; font-weight: 750; }
  .live-dot {
    display: inline-block; width: .35rem; height: .35rem;
    margin-right: .25rem; border-radius: 50%; background: #1eba87;
  }
  video { border-radius: .18rem !important; background: #17201e; }
  [data-testid="stCustomComponentV1"] { border: 0; }
  iframe[title="streamlit_webrtc.component.webrtc_streamer"] {
    position: absolute; width: 1px !important; height: 1px !important;
    opacity: 0; pointer-events: none;
  }

  .metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .55rem; }
  .metric-box { padding: .55rem .58rem; border: 1px solid #edf1ef; border-radius: .25rem; }
  .metric-name { color: #65746f; font-size: .6rem; }
  .metric-number { margin-top: .18rem; font-size: 1.08rem; font-weight: 850; line-height: 1; }
  .metric-denominator { color: #82908c; font-size: .54rem; font-weight: 600; }
  .metric-state { margin: .2rem 0 .3rem; font-size: .53rem; font-weight: 700; }
  .progress-track { height: .22rem; background: #edf1ef; border-radius: 1rem; overflow: hidden; }
  .progress-value { height: 100%; border-radius: 1rem; }
  .recommendation {
    display: grid; grid-template-columns: auto 1fr; gap: .55rem; margin-top: .58rem;
    padding: .58rem; background: #effaf5; border: 1px solid #ccecdc; border-radius: .3rem;
  }
  .recommendation-icon {
    display: grid; place-items: center; width: 1.65rem; height: 1.65rem;
    border-radius: 50%; background: white; color: var(--green); font-size: .55rem; font-weight: 850;
  }
  .recommendation-title { color: var(--green-dark); font-size: .57rem; font-weight: 800; }
  .recommendation-copy { color: #354943; font-size: .57rem; margin-top: .12rem; }
  .activity-pill {
    display: inline-flex; align-items: center; gap: .35rem; margin-top: .55rem;
    padding: .3rem .45rem; border-radius: 1rem; background: #f2f6f4;
    color: #3d514a; font-size: .57rem; font-weight: 750;
  }
  .cue-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: .3rem;
    margin-top: .45rem; color: #65746f; font-size: .54rem;
  }
  .cue-grid span { padding: .32rem .4rem; border-radius: .25rem; background: #f5f8f7; }
  .cue-grid strong { color: #2f433c; }

  .event-empty { padding: .75rem .35rem; color: #6f7e79; font-size: .58rem; line-height: 1.5; }
  .event-item {
    display: grid; grid-template-columns: auto 1fr; gap: .45rem;
    padding: .55rem 0; border-bottom: 1px solid #edf1ef;
  }
  .event-dot {
    width: .55rem; height: .55rem; margin-top: .08rem;
    border-radius: 50%; background: var(--amber);
  }
  .event-critical { background: var(--red); box-shadow: 0 0 8px rgba(217, 76, 69, .5); }
  .event-title { color: #34443f; font-size: .59rem; font-weight: 800; }
  .event-copy { color: #7b8985; font-size: .53rem; line-height: 1.35; margin-top: .1rem; }

  .trend-row { margin-top: .65rem; }
  .trend-card {
    background: white; border: 1px solid var(--line);
    border-radius: .35rem; padding: .65rem .7rem .35rem;
  }
  .trend-meta { display: flex; justify-content: space-between; align-items: center; }
  .trend-title { font-size: .62rem; font-weight: 800; }
  .trend-range { color: #7c8985; font-size: .5rem; }
  .trend-label { color: #7f8d88; font-size: .5rem; margin: .58rem 0 .1rem; }
  .sparkline { width: 100%; height: 4rem; overflow: visible; }
  .spark-grid { stroke: #edf1ef; stroke-width: 1; }
  .activity-card { padding-bottom: .4rem; }
  .activity-plot {
    display: block; width: 100%; height: 10.4rem; margin-top: .35rem;
    overflow: visible;
  }
  .activity-label {
    fill: #53645e; font-family: Inter, "Segoe UI", Arial, sans-serif;
    font-size: 10px; font-weight: 700;
  }
  .activity-state {
    fill: #75847f; font-family: Inter, "Segoe UI", Arial, sans-serif;
    font-size: 9px; font-weight: 700;
  }

  @media (max-width: 900px) {
    [data-testid="stSidebar"] { min-width: 190px; max-width: 190px; }
    .quality { min-width: 9rem; }
    .status-banner { grid-template-columns: auto 1fr; }
    .quality { grid-column: 1 / -1; border-left: 0; padding-left: 0; }
  }

  /* Keep the complete monitoring console inside a typical laptop viewport. */
  @media (max-height: 820px) {
    [data-testid="stSidebar"] > div:first-child,
    [data-testid="stSidebarContent"],
    [data-testid="stSidebarUserContent"] { padding: .55rem .7rem; }
    .block-container { padding: .3rem .8rem .35rem; }
    div[data-testid="stVerticalBlock"] { gap: .28rem; }

    .brand { margin-bottom: .45rem; }
    .brand-mark { width: 1.7rem; height: 1.7rem; }
    .brand-subtitle { margin-top: .08rem; }
    .side-section { margin: .45rem 0 .22rem; }
    .nav-item { padding: .36rem .52rem; }
    [data-testid="stSidebar"] .stButton > button {
      min-height: 1.55rem; padding: .12rem .4rem;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] > div { min-height: 1.65rem; }

    .topbar { min-height: 1.35rem; }
    .status-banner {
      gap: .5rem; padding: .42rem .65rem; margin-bottom: .3rem;
    }
    .status-icon { width: 1.55rem; height: 1.55rem; }
    .alarm-banner, .notice-banner { padding: .4rem .65rem; margin-bottom: .3rem; }
    .alarm-pulse { width: 1.55rem; height: 1.55rem; }
    .notice-icon, .danger-icon { width: 1.55rem; height: 1.55rem; }
    .panel { padding: .42rem; }
    .panel-head { margin-bottom: .26rem; }
    video { max-height: 34vh !important; object-fit: cover; }
    [data-testid="stCustomComponentV1"] iframe { max-height: 35vh; }

    .metric-grid { gap: .3rem; }
    .metric-box { padding: .35rem .42rem; }
    .metric-number { margin-top: .1rem; font-size: .92rem; }
    .metric-state { margin: .1rem 0 .18rem; }
    .recommendation { gap: .4rem; margin-top: .3rem; padding: .35rem; }
    .recommendation-icon { width: 1.35rem; height: 1.35rem; }
    .activity-pill { margin-top: .28rem; padding: .2rem .38rem; }
    .cue-grid { gap: .2rem; margin-top: .25rem; }
    .cue-grid span { padding: .2rem .3rem; }
    .event-empty { padding: .42rem .25rem; }
    .event-item { padding: .32rem 0; }

    .trend-row { margin-top: .3rem; }
    .trend-card { padding: .4rem .5rem .2rem; }
    .trend-label { margin: .28rem 0 .05rem; }
    .sparkline { height: 2.45rem; }
    .activity-plot { height: 7.6rem; margin-top: .18rem; }
  }

  @media (max-height: 680px) {
    [data-testid="stSidebar"] > div:first-child,
    [data-testid="stSidebarContent"],
    [data-testid="stSidebarUserContent"] { padding: .35rem .62rem; }
    .block-container { padding: .18rem .65rem .22rem; }
    .brand { margin-bottom: .25rem; }
    .brand-subtitle { display: none; }
    .side-section { margin: .25rem 0 .12rem; }
    .nav-item { padding: .25rem .45rem; }
    [data-testid="stSidebar"] .stButton > button { min-height: 1.35rem; }
    .topbar { min-height: 1rem; }
    .user-chip { font-size: .58rem; }
    .status-banner { padding: .3rem .5rem; margin-bottom: .2rem; }
    .status-copy, .quality-copy { display: none; }
    video { max-height: 30vh !important; }
    [data-testid="stCustomComponentV1"] iframe { max-height: 31vh; }
    .sparkline { height: 1.8rem; }
    .activity-plot { height: 6.5rem; }
  }
</style>
"""
