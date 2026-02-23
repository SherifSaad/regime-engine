import streamlit as st

st.set_page_config(
    page_title="Regime Intelligence",
    page_icon="📈",
    layout="wide",
)

pages = [
    st.Page("pages/Dashboard.py", title="Dashboard", icon="📊"),
    st.Page("pages/Audit.py", title="Audit", icon="🧾"),
    st.Page("pages/Pricing.py", title="Pricing", icon="💳"),
    st.Page("pages/Login.py", title="Login", icon="🔐"),
]

nav = st.navigation(pages)
nav.run()
