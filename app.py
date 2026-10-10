import streamlit as st
from openai import OpenAI
import re
import datetime
import html
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ==============================================================================
# 1. PASSWORT-SCHUTZ
# ==============================================================================
# Das Passwort wird sicher in den Streamlit-Secrets hinterlegt
APP_PASSWORD = st.secrets["APP_PASSWORD"]

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 KI-Strategie-Berater (Login)")
    pwd = st.text_input("Bitte Passwort eingeben:", type="password")
    if st.button("Login"):
        if pwd == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Falsches Passwort!")
    st.stop() # Stoppt das Skript hier, wenn nicht eingeloggt

# ==============================================================================
# 2. SETUP & EINSTELLUNGEN
# ==============================================================================
client = OpenAI(
    api_key=st.secrets["OPENROUTER_KEY"],
    base_url="https://openrouter.ai/api/v1"
)
MODERATOR_MODELL = "openai/gpt-4o-mini"
ANZAHL_RUNDEN = 3

QUELLEN_PFLICHT = (
    "STRIKTES VERBOT: Erfinde NIEMALS historische Fallstudien, Zahlen oder Studien (Null Halluzination!). "
    "Wenn du eine Kennzahl oder Studie nennst, MUSST du die Quelle in Klammern angeben. "
    "Wenn du keine Quelle hast, argumentiere streng logisch. "
    "ANTI-PLAGIATS-REGEL: Wiederhole NIEMALS Argumente, Zahlen oder Formulierungen deiner Vorredner. "
    "Finde immer einen komplett neuen, eigenen Blickwinkel. Keine Zustimmung zu Vorrednern."
)

agenten = [
    {
        "name": "Der Visionär (Llama 3.3 70B)",
        "model": "meta-llama/llama-3.3-70b-instruct",
        "prompt": f"Du bist der radikale Technologie-Visionär. Fokus: Disruption, Skalierbarkeit. {QUELLEN_PFLICHT}"
    },
    {
        "name": "Der Skeptiker (DeepSeek V3)",
        "model": "deepseek/deepseek-chat",
        "prompt": f"Du bist der analytische Red Teamer. Fokus: Systeminstabilität, Risiken. {QUELLEN_PFLICHT}"
    },
    {
        "name": "Der Pragmatiker (Mistral Small)",
        "model": "mistralai/mistral-small-24b-instruct-2501",
        "prompt": f"Du bist der Regulierer. Fokus: DSGVO, Schnittstellenkomplexität. {QUELLEN_PFLICHT}"
    },
    {
        "name": "Der Stratege (Qwen 2.5 72B)",
        "model": "qwen/qwen-2.5-72b-instruct",
        "prompt": f"Du bist der Makro-Stratege. Fokus: Neue unkonventionelle Geschäftsmodelle. {QUELLEN_PFLICHT}"
    }
]

# ==============================================================================
# 3. HILFSFUNKTIONEN
# ==============================================================================
def get_ki_antwort(model, system_prompt, transkript, aufgabenstellung):
    nachrichten = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"PROTOKOLL DER BISHERIGEN DEBATTE:\n{transkript}\n\nDEINE AUFGABE FÜR DIESE RUNDE:\n{aufgabenstellung}"}
    ]
    try:
        response = client.chat.completions.create(
            model=model, messages=nachrichten, temperature=0.7, max_tokens=450
        )
        rohtext = response.choices[0].message.content or ""
        sauber = re.sub(r'<think>.*?</think>', '', rohtext, flags=re.DOTALL).strip()
        return sauber if sauber else "[Keine Antwort]"
    except Exception as e:
        return f"[Fehler bei {model}: {e}]"

def erstelle_pdf_buffer(thema, protokoll, fazit):
    buffer = io.BytesIO() # PDF wird direkt im Arbeitsspeicher generiert (Cloud-sicher)
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    
    titel_stil = ParagraphStyle('Titel', parent=styles['Heading1'], fontSize=16, spaceAfter=6)
    meta_stil = ParagraphStyle('Meta', parent=styles['Normal'], fontSize=8.5, textColor=colors.HexColor('#64748B'), spaceAfter=10)
    runden_stil = ParagraphStyle('Runde', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#1D4ED8'), spaceBefore=8, spaceAfter=4)
    sprecher_stil = ParagraphStyle('Sprecher', parent=styles['Normal'], fontSize=9.5, fontName='Helvetica-Bold', spaceBefore=4, spaceAfter=2)
    text_stil = ParagraphStyle('Text', parent=styles['Normal'], fontSize=8.5, spaceAfter=5)
    
    story = [Paragraph("Strategie-Debatte & Schiedsrichter-Urteil", titel_stil)]
    zeit = datetime.datetime.now().strftime("%d.%m.%Y um %H:%M Uhr")
    story.append(Paragraph(f"<b>Thema:</b> {html.escape(str(thema))}<br/><b>Datum:</b> {zeit}", meta_stil))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E1'), spaceAfter=8))
    
    for eintrag in protokoll:
        if eintrag["typ"] == "runde":
            story.append(Paragraph(f"{eintrag['titel']}", runden_stil))
        elif eintrag["typ"] == "beitrag":
            story.append(Paragraph(f"💬 {html.escape(str(eintrag['sprecher']))}", sprecher_stil))
            story.append(Paragraph(html.escape(str(eintrag['text'])).replace("\n", "<br/>"), text_stil))
            
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1D4ED8'), spaceAfter=8))
    story.append(Paragraph(f"⚖️ Urteil ({MODERATOR_MODELL})", runden_stil))
    story.append(Paragraph(html.escape(str(fazit)).replace("\n", "<br/>"), text_stil))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# ==============================================================================
# 4. DAS WEB-INTERFACE
# ==============================================================================
st.title("🧠 Experten-Denkfabrik")
st.markdown("Beschreibe eine strategische Fragestellung. 4 KIs diskutieren hart und faktenbasiert.")

thema = st.text_area("Dein Thema / Fragestellung:", 
                     "Soll ein mittelständisches Industrieunternehmen (300 Mitarbeiter) alle Prozesse radikal auf KI umstellen?")

if st.button("🚀 Debatte starten"):
    st.divider()
    transkript = f"KERNAUFGABE / THEMA:\n{thema}\n"
    protokoll_daten = []
    
    # 1. Die Debatte (Live-Ausgabe im Browser)
    with st.spinner("Die KIs diskutieren... Bitte warten (kann ca. 1-2 Minuten dauern)."):
        for runde in range(1, ANZAHL_RUNDEN + 1):
            r_titel = f"Runde {runde}: " + ["Fakten-Plädoyer", "Gezieltes Kreuzverhör", "Verteidigung & Ultimatum"][runde-1]
            st.subheader(r_titel)
            protokoll_daten.append({"typ": "runde", "titel": r_titel, "nummer": runde})
            transkript += f"\n--- {r_titel.upper()} ---\n"
            
            for i, agent in enumerate(agenten):
                if runde == 1:
                    instruktion = "AUFGABE FÜR RUNDE 1: Stelle deine Kern-These in exakt 2 Sätzen vor. Untermauere sie zwingend mit einer Kennzahl (belege diese in Klammern mit einer realen Quelle!). Argumentiere streng logisch. Schreibe keinen weiteren Text."
                elif runde == 2:
                    ziel = agenten[(i + 1) % 4]["name"]
                    instruktion = f"AUFGABE FÜR RUNDE 2: DEIN EXKLUSIVES ANGRIFFSZIEL IST '{ziel}'. Zitiere in Anführungszeichen EINEN Kernsatz von '{ziel}' aus Runde 1. Erkläre dann anhand harter Fakten, warum dieser Ansatz in der Praxis fatal ist. Sprich nicht über Quellen oder den Textaufbau. Attackiere nur den INHALT. Verteidige dich nicht selbst. Max 4 Sätze."
                else:
                    instruktion = "AUFGABE FÜR RUNDE 3: Du wurdest angegriffen. Verteidige deine Position hart! Verwende komplett neue Formulierungen. Kopiere KEINE Argumente. Greife niemanden neu an. Schließe mit einem ultimativen Ratschlag an die Geschäftsführung. Max 4 Sätze."
                
                antwort = get_ki_antwort(agent["model"], agent["prompt"], transkript, f"Du bist '{agent['name']}'. {instruktion}")
                
                # Chat-Nachricht auf der Webseite anzeigen
                with st.chat_message("assistant"):
                    st.markdown(f"**{agent['name']}**\n\n{antwort}")
                
                transkript += f"[{agent['name']}]:\n{antwort}\n\n"
                protokoll_daten.append({"typ": "beitrag", "sprecher": agent["name"], "text": antwort})

        # 2. Schiedsrichter
        st.subheader("⚖️ Schiedsrichter-Urteil")
        mod_prompt = "Werte die Debatte aus: 1. Wer hat die stärkste Evidenz geliefert? 2. Wer hat im Kreuzverhör am besten argumentiert? 3. Liefere eine finale Entscheidungsmatrix (Go/No-Go) für die Geschäftsführung."
        
        fazit = get_ki_antwort(MODERATOR_MODELL, mod_prompt, transkript, "Fälle jetzt das strukturierte Urteil als Senior-Consultant.")
        with st.chat_message("assistant", avatar="⚖️"):
            st.markdown(fazit)

    # 3. PDF Download Button erzeugen
    pdf_buffer = erstelle_pdf_buffer(thema, protokoll_daten, fazit)
    
    st.divider()
    st.success("Debatte abgeschlossen!")
    st.download_button(
        label="📄 PDF-Protokoll herunterladen",
        data=pdf_buffer,
        file_name=f"Debatte_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
        mime="application/pdf"
    )