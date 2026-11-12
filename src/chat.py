"""Sağ alttaki "Asistana sor" penceresi (yalnızca Yönetici Özeti'nde).

- Asistan sayfadaki filtrelere bağlı değildir; kapsamı soru belirler. Soruda dönem yoksa sayfadaki
  dönem kullanılır; il, kategori ve segment filtreleri asistanı etkilemez.
- Hazır sorular konuya göre gruplanır ve dil modeli olmadan, paneldeki hesaplarla yanıtlanır.
- Serbest sorular (OpenRouter anahtarı tanımlıysa) üç adımda yanıtlanır: çözümleme, hesaplama, yanıt.
  Anahtar Streamlit secrets'a eklenmemişse serbest soru kutusu gösterilmez.
"""

import streamlit as st

from src import assistant, llm
from src.filters import Filters, period_name

MAX_QUESTIONS = 10        # oturum başına serbest soru sınırı (maliyet ve kötüye kullanım için)
MAX_QUESTION_CHARS = 300  # uzun ve kural dışı istemleri modele göndermeden durdurur
OUT_OF_SCOPE = "Bu asistan yalnızca BookWise panelindeki veriler hakkındaki soruları yanıtlar. Örneğin: \"Ankara'da 2. çeyrekte ciro ne kadardı?\""


def _answer_free(question: str, page_f: Filters, log: list) -> str:
    plan = assistant.parse_plan(llm.plan(question, assistant.planner_prompt(), log))
    if plan.get("konu") == "kapsam_disi":
        return OUT_OF_SCOPE
    context, _ = assistant.answer_context(question, plan, page_f)
    return llm.ask(question, context, log)


def render_assistant(page_f: Filters) -> None:
    log = st.session_state.setdefault("assistant_log", [])
    used = st.session_state.setdefault("chat_used", 0)
    has_model = bool(llm.api_key())
    with st.container(key="chat_fab"):
        with st.popover("Asistana sor", icon=":material/chat:"):
            st.markdown(f'<div class="chat-ctx">Kapsamı soru belirler. Soruda dönem yoksa sayfadaki dönem '
                        f'(<b>{period_name(page_f)}</b>) kullanılır; diğer sayfa filtreleri asistanı etkilemez.</div>',
                        unsafe_allow_html=True)
            history = st.container()  # yeni mesajlar aynı çalıştırmada görünsün diye önce yer ayrılır
            topic = st.segmented_control("Konu", assistant.TOPICS, default="Genel", key="assistant_topic",
                                         label_visibility="collapsed") or "Genel"
            for q in assistant.PRESETS[topic]:
                if st.button(q, key=f"asst_q_{topic}_{q}", width="stretch"):
                    log += [("user", q), ("assistant", assistant.preset_answer(topic, q, page_f))]
            text, sent = "", False
            if has_model:
                with st.form(key="assistant_form", clear_on_submit=True, border=False):
                    text = st.text_input("Soru", placeholder="Ör. Ankara'da 2. çeyrekte ciro ne kadardı?",
                                         label_visibility="collapsed", key="assistant_text",
                                         disabled=used >= MAX_QUESTIONS)
                    sent = st.form_submit_button("Sor", type="primary")
            q = text.strip()
            if sent and q and len(q) > MAX_QUESTION_CHARS:
                log += [("user", q[:80] + "…"), ("assistant", f"Lütfen sorunuzu {MAX_QUESTION_CHARS} karakteri geçmeyecek şekilde kısaltın.")]
            elif sent and q:
                try:
                    with st.spinner("Yanıt hazırlanıyor..."):
                        reply = _answer_free(q, page_f, log)
                    st.session_state["chat_used"] = used + 1
                except Exception:
                    reply = "Şu anda dil modeline ulaşılamıyor. Hazır sorulardan birini seçebilir ya da biraz sonra tekrar deneyebilirsiniz."
                log += [("user", q), ("assistant", reply)]
            if has_model:
                st.caption(f"Kalan soru hakkı: {MAX_QUESTIONS - st.session_state['chat_used']} / {MAX_QUESTIONS}. "
                           "Sayılar paneldeki hesaplardan gelir; dil modeli yalnızca soruyu çözümler ve yanıtı yazar.")
            else:
                st.caption("Hazır sorular paneldeki hesaplarla yanıtlanır.")
            with history:
                for role, msg in log[-12:]:
                    with st.chat_message(role, avatar=":material/person:" if role == "user" else ":material/insights:"):
                        st.markdown(msg)
