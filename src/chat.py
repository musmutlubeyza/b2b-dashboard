"""Sağ alttaki 'Panele sor' sohbeti.

- Hazır sorular, sayfanın hesapladığı yanıtlarla anında cevaplanır (model gerekmez).
- Serbest sorular OpenRouter'daki dil modeline gider. Modele yalnızca bu sayfanın bağlamı verilir:
  etkin filtreler, KPI'lar, öne çıkanlar, önerilen aksiyonlar ve hazır yanıtlar.
- Anahtar tanımlı değilse serbest soru kutusu gösterilmez; sohbet hazır sorularla çalışır.
  Anahtar Streamlit secrets'a eklendiğinde kod değişmeden serbest sorular açılır.
"""

import streamlit as st

from src import llm

MAX_QUESTIONS = 10   # oturum başına serbest soru sınırı (maliyet ve kötüye kullanım için)
MAX_QUESTION_CHARS = 300  # uzun ve kural dışı istemleri modele göndermeden durdurur
PAGE_NAMES = {"summary": "Yönetici Özeti", "sales": "Satış ve Müşteri", "marketing": "Pazarlama ve Segmentler",
              "supply": "Ürün ve Tedarik", "forecast": "Tahmin", "notes": "Veri Notları"}


def start_page_facts() -> None:
    """Her çalıştırmanın başında sayfa bilgileri listesini sıfırlar (KPI ve aksiyon kartları buraya yazar)."""
    st.session_state["_page_facts"] = []


def add_fact(text: str) -> None:
    st.session_state.setdefault("_page_facts", []).append(text)


def _context(page_name: str, filters: str, highlights: list[str], answers: dict[str, str]) -> str:
    facts = st.session_state.get("_page_facts", [])
    parts = [f"Sayfa: {PAGE_NAMES.get(page_name, page_name)}", f"Etkin filtreler: {filters}",
             "Göstergeler ve önerilen aksiyonlar:\n" + "\n".join(f"- {x}" for x in facts),
             "Öne çıkanlar:\n" + "\n".join(f"- {h}" for h in highlights),
             "Hesaplanmış yanıtlar:\n" + "\n".join(f"- {q}: {a}" for q, a in answers.items())]
    return "\n\n".join(parts)


def render_chat(page_key: str, context: str, highlights: list[str], answers: dict[str, str]) -> None:
    log = st.session_state.setdefault(f"chat_log_{page_key}", [])
    used = st.session_state.setdefault("chat_used", 0)
    has_model = bool(llm.api_key())
    with st.container(key="chat_fab"):
        with st.popover("Panele sor", icon=":material/chat:"):
            st.markdown(f'<div class="chat-ctx"><b>Etkin filtreler:</b> {context}</div>', unsafe_allow_html=True)
            with st.chat_message("assistant", avatar=":material/insights:"):
                st.markdown("**Bu sayfada öne çıkanlar**\n\n" + "\n".join(f"- {h}" for h in highlights))
            history = st.container()  # yeni mesajlar aynı çalıştırmada burada görünsün diye önce yer ayırıyoruz
            for q, a in answers.items():
                if st.button(q, key=f"chat_q_{page_key}_{q}", width="stretch"):
                    log += [("user", q), ("assistant", a)]
            sent, text = False, ""
            if has_model:  # dil modeli anahtarı tanımlıysa serbest soru kutusu açılır
                with st.form(key=f"chat_form_{page_key}", clear_on_submit=True, border=False):
                    text = st.text_input("Soru", placeholder="Bir soru yazın", label_visibility="collapsed",
                                         key=f"chat_text_{page_key}", disabled=used >= MAX_QUESTIONS)
                    sent = st.form_submit_button("Sor", type="primary")
            if sent and text.strip() and len(text.strip()) > MAX_QUESTION_CHARS:
                log += [("user", text.strip()[:80] + "…"),
                        ("assistant", f"Lütfen sorunuzu {MAX_QUESTION_CHARS} karakteri geçmeyecek şekilde kısaltın.")]
            elif sent and text.strip():
                q = text.strip()
                try:
                    with st.spinner("Yanıt hazırlanıyor..."):
                        reply = llm.ask(q, _context(page_key, context, highlights, answers), log)
                    st.session_state["chat_used"] = used + 1
                except Exception:
                    reply = "Şu anda dil modeline ulaşılamıyor. Hazır sorulardan birini seçebilir ya da biraz sonra tekrar deneyebilirsiniz."
                log += [("user", q), ("assistant", reply)]
            if has_model:
                st.caption(f"Kalan soru hakkı: {MAX_QUESTIONS - st.session_state['chat_used']} / {MAX_QUESTIONS}. "
                           "Yanıtlar yalnızca bu sayfadaki verilere dayanır.")
            else:
                st.caption("Sorular bu sayfanın güncel verileri ve seçili filtrelerle yanıtlanır.")
            with history:
                for role, msg in log:
                    with st.chat_message(role, avatar=":material/person:" if role == "user" else ":material/insights:"):
                        st.markdown(msg)
