"""FinSight Staff Console — co-pilot, compliance, fraud triage, HITL queue."""

from __future__ import annotations

import os

import requests
import streamlit as st

API_URL = os.getenv("FINSIGHT_API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="FinSight Staff",
    page_icon="▣",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@500;600&display=swap');

:root {
  --navy: #102a43;
  --slate: #243b53;
  --fog: #d9e2ec;
  --signal: #0e7c7b;
  --warn: #ba5b0d;
  --bg: #f0f4f8;
}

html, body, [class*="css"] { font-family: "IBM Plex Sans", sans-serif; color: var(--navy); }

.stApp {
  background:
    linear-gradient(135deg, rgba(16,42,67,0.04) 0%, transparent 40%),
    repeating-linear-gradient(
      0deg,
      transparent,
      transparent 23px,
      rgba(16,42,67,0.03) 24px
    ),
    var(--bg);
}

.brand {
  font-family: "IBM Plex Serif", Georgia, serif;
  font-size: 2.4rem;
  color: var(--navy);
  margin: 0;
}

.panel-label {
  font-size: 0.7rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--signal);
  font-weight: 600;
}

.stButton > button {
  background: var(--navy);
  color: #f0f4f8;
  border-radius: 2px;
  border: none;
  font-weight: 600;
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


def staff_chat(token: str, message: str, mode: str, session_id: str | None) -> dict:
    r = requests.post(
        f"{API_URL}/api/v1/staff/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": message, "mode": mode, "session_id": session_id},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def fetch_hitl(token: str) -> list:
    r = requests.get(
        f"{API_URL}/api/v1/staff/hitl",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def resolve(token: str, item_id: str, approve: bool, notes: str) -> dict:
    r = requests.post(
        f"{API_URL}/api/v1/staff/hitl/{item_id}/resolve",
        headers={"Authorization": f"Bearer {token}"},
        json={"approve": approve, "notes": notes},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


with st.sidebar:
    st.markdown("### Staff access")
    if "token" not in st.session_state:
        u = st.text_input("Username", value="staff")
        p = st.text_input("Password", type="password", value="staff1234")
        if st.button("Open console"):
            data = login(u, p)
            if data and data.get("role") == "staff":
                st.session_state.token = data["access_token"]
                st.session_state.user = data
                st.rerun()
            else:
                st.error("Staff login failed.")
    else:
        st.success(f"**{st.session_state.user['username']}** · `{st.session_state.user.get('staff_id')}`")
        if st.button("Sign out"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

st.markdown('<p class="brand">FinSight Staff</p>', unsafe_allow_html=True)
st.caption("Compliance lookup · Fraud triage · Service co-pilot · Human approval queue")

if "token" not in st.session_state:
    st.info("Sign in with the demo staff account.")
    st.stop()

tab_chat, tab_hitl = st.tabs(["Co-Pilot Workspace", "HITL Queue"])

with tab_chat:
    mode = st.selectbox(
        "Mode",
        options=["auto", "compliance", "fraud", "copilot"],
        format_func=lambda x: {
            "auto": "Auto-route",
            "compliance": "Compliance Lookup",
            "fraud": "Fraud / Risk Triage",
            "copilot": "Service Co-Pilot",
        }[x],
    )
    if "staff_messages" not in st.session_state:
        st.session_state.staff_messages = []
    if "staff_session" not in st.session_state:
        st.session_state.staff_session = None

    for m in st.session_state.staff_messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    prompt = st.chat_input("Ask internal policy, triage alerts, or draft a customer reply…")
    if prompt:
        st.session_state.staff_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Running staff agent…"):
                try:
                    resp = staff_chat(
                        st.session_state.token,
                        prompt,
                        mode,
                        st.session_state.staff_session,
                    )
                    st.session_state.staff_session = resp.get("session_id")
                    answer = resp.get("answer") or "_No answer_"
                    st.markdown(answer)
                    if resp.get("citations"):
                        st.caption("Citations: " + ", ".join(resp["citations"]))
                    st.session_state.staff_messages.append(
                        {"role": "assistant", "content": answer}
                    )
                except Exception as e:
                    st.error(str(e))

with tab_hitl:
    st.markdown('<p class="panel-label">Pending human approvals</p>', unsafe_allow_html=True)
    if st.button("Refresh queue"):
        st.session_state.hitl = fetch_hitl(st.session_state.token)
    if "hitl" not in st.session_state:
        st.session_state.hitl = fetch_hitl(st.session_state.token)

    items = st.session_state.hitl or []
    if not items:
        st.write("Queue is clear.")
    for item in items:
        with st.expander(f"{item['kind']} · {item['summary']}", expanded=False):
            st.json(item.get("payload"))
            notes = st.text_input("Review notes", key=f"notes_{item['id']}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Approve", key=f"ok_{item['id']}"):
                    resolve(st.session_state.token, item["id"], True, notes)
                    st.session_state.hitl = fetch_hitl(st.session_state.token)
                    st.rerun()
            with c2:
                if st.button("Reject", key=f"no_{item['id']}"):
                    resolve(st.session_state.token, item["id"], False, notes)
                    st.session_state.hitl = fetch_hitl(st.session_state.token)
                    st.rerun()
