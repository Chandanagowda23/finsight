"""FinSight Customer Assistant — Streamlit UI."""

from __future__ import annotations

import os

import requests
import streamlit as st

API_URL = os.getenv("FINSIGHT_API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="FinSight",
    page_icon="◇",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,600;0,9..40,700;1,9..40,400&family=Instrument+Serif:ital@0;1&display=swap');

:root {
  --ink: #0c1f1a;
  --pine: #1a4d3e;
  --mint: #c8e6d8;
  --sand: #e8efe9;
  --amber: #c45c26;
  --paper: #f3f7f4;
}

html, body, [class*="css"] {
  font-family: "DM Sans", sans-serif;
  color: var(--ink);
}

.stApp {
  background:
    radial-gradient(1200px 600px at 10% -10%, #d4ebe0 0%, transparent 55%),
    radial-gradient(900px 500px at 100% 0%, #f0e2d4 0%, transparent 50%),
    linear-gradient(180deg, #f3f7f4 0%, #e7efe9 100%);
}

.brand {
  font-family: "Instrument Serif", Georgia, serif;
  font-size: 3.2rem;
  line-height: 1;
  color: var(--pine);
  margin: 0;
  letter-spacing: -0.02em;
}

.tagline {
  font-size: 1.05rem;
  color: #3d5a4f;
  margin: 0.4rem 0 1.5rem;
  max-width: 36rem;
}

.meta-chip {
  display: inline-block;
  font-size: 0.75rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--pine);
  border-bottom: 1px solid var(--pine);
  margin-right: 1rem;
  padding-bottom: 2px;
}

div[data-testid="stChatMessage"] {
  background: rgba(255,255,255,0.55);
  border: 1px solid rgba(26,77,62,0.12);
  backdrop-filter: blur(6px);
}

.cite {
  font-size: 0.8rem;
  color: #4a6b5e;
  border-left: 3px solid var(--amber);
  padding-left: 0.75rem;
  margin-top: 0.5rem;
}

.stButton > button {
  background: var(--pine);
  color: #f5faf7;
  border: none;
  border-radius: 2px;
  font-weight: 600;
}
.stButton > button:hover {
  background: var(--amber);
  color: white;
}
</style>
""",
    unsafe_allow_html=True,
)


def login(username: str, password: str) -> dict | None:
    r = requests.post(
        f"{API_URL}/api/v1/auth/login",
        json={"username": username, "password": password},
        timeout=30,
    )
    if r.status_code != 200:
        return None
    return r.json()


def chat(token: str, message: str, session_id: str | None, history: list) -> dict:
    r = requests.post(
        f"{API_URL}/api/v1/customer/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": message, "session_id": session_id, "history": history},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


with st.sidebar:
    st.markdown("### Sign in")
    if "token" not in st.session_state:
        u = st.text_input("Username", value="customer")
        p = st.text_input("Password", type="password", value="demo1234")
        if st.button("Enter FinSight"):
            data = login(u, p)
            if data and data.get("role") == "customer":
                st.session_state.token = data["access_token"]
                st.session_state.user = data
                st.rerun()
            else:
                st.error("Customer login failed.")
    else:
        st.success(f"Signed in as **{st.session_state.user['username']}**")
        st.caption(f"Customer ID: `{st.session_state.user.get('customer_id')}`")
        if st.button("Sign out"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    st.markdown("---")
    st.markdown(
        "**Try asking**\n\n"
        "- What is the monthly fee for Everyday Checking?\n"
        "- What is the current savings APY?\n"
        "- What's my checking balance?\n"
        "- Show my recent transactions\n"
        "- I want to dispute TXN-9003\n"
        "- Am I eligible for a personal loan? income: $72000"
    )

st.markdown('<p class="brand">FinSight</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="tagline">Your bank, answered with evidence. '
    "Product answers cite source clauses. Account actions never run without confirmation.</p>",
    unsafe_allow_html=True,
)
st.markdown(
    '<span class="meta-chip">Customer assistant</span>'
    '<span class="meta-chip">Grounded RAG</span>'
    '<span class="meta-chip">Human-in-the-loop</span>',
    unsafe_allow_html=True,
)

if "token" not in st.session_state:
    st.info("Sign in with the demo customer account to begin.")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = None

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("citations"):
            st.markdown(
                f'<div class="cite">Citations: {", ".join(m["citations"])}</div>',
                unsafe_allow_html=True,
            )

prompt = st.chat_input("Ask about fees, rates, balances, disputes…")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Verifying against knowledge & tools…"):
            try:
                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages[:-1]
                ]
                resp = chat(
                    st.session_state.token,
                    prompt,
                    st.session_state.session_id,
                    history,
                )
                st.session_state.session_id = resp.get("session_id")
                answer = resp.get("answer") or "_No answer_"
                st.markdown(answer)
                cites = resp.get("citations") or []
                if cites:
                    st.markdown(
                        f'<div class="cite">Citations: {", ".join(cites)}</div>',
                        unsafe_allow_html=True,
                    )
                meta = []
                if resp.get("abstained"):
                    meta.append("abstained")
                if resp.get("require_hitl"):
                    meta.append(f"HITL `{resp.get('hitl_id')}`")
                if resp.get("route"):
                    meta.append(f"route: {resp['route']}")
                if meta:
                    st.caption(" · ".join(meta))
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer, "citations": cites}
                )
            except Exception as e:
                st.error(f"Request failed: {e}")
