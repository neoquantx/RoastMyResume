"""The local-first resume review workspace."""

import hashlib
import json
import time
from html import escape
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

from core.jd_scraper import parse_jd_text, scrape_jd_from_url
from core.resume_parser import parse_resume
from core.roaster import (
    generate_interview_prep,
    get_installed_models,
    get_model_ram_warning,
    get_rejection_scores,
    rewrite_section,
    stream_chat_response,
    stream_roast,
)
from core.exporter import generate_docx_export, generate_markdown_export
from core.tts import generate_voice_roast, get_elevenlabs_key
from core.scorer_viz import (
    build_keyword_match_donut,
    build_resume_score_gauge,
    build_section_bar,
    build_section_radar,
)
from ui import brand, hero, section_heading, tags
from ui.diff import render_word_diff


st.set_page_config(
    page_title="RoastMyResume · A better first impression",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)
# Load design system and custom UI tokens
st.markdown(
    f"<style>{(Path(__file__).parent / 'ui' / 'styles.css').read_text()}</style>",
    unsafe_allow_html=True,
)

# Auto-expand sidebar if browser cached a collapsed state
import streamlit.components.v1 as components
components.html(
    """
    <script>
    function ensureSidebarOpen() {
        try {
            const doc = window.parent.document;
            const expandBtn = doc.querySelector('[data-testid="collapsedControl"]') || doc.querySelector('[data-testid="stExpandSidebarButton"] button') || doc.querySelector('[data-testid="stExpandSidebarButton"]');
            if (expandBtn) {
                expandBtn.click();
            }
        } catch (e) {}
    }
    ensureSidebarOpen();
    setTimeout(ensureSidebarOpen, 60);
    setTimeout(ensureSidebarOpen, 250);
    setTimeout(ensureSidebarOpen, 600);
    </script>
    """,
    height=0,
    width=0,
)

PERSONAS = {
    "Brutal friend": (
        "Straight talk. A little tough love. Always useful.",
        "You are a direct, witty career coach. Give brutally honest but constructive feedback, "
        "like a friend who cares. Pair every criticism with a specific, actionable fix.",
    ),
    "Gentle mentor": (
        "Encouraging feedback, without the sugarcoating.",
        "You are a warm, experienced career mentor. Acknowledge strengths before giving "
        "specific, honest and encouraging suggestions for improvement.",
    ),
    "FAANG recruiter": (
        "Technical depth, clear impact, a higher hiring bar.",
        "Review as an experienced technical recruiter for Google, Meta and Amazon. "
        "Focus on quantified impact, technical depth and strong action verbs.",
    ),
    "Startup founder": (
        "Show what you shipped, not just what you know.",
        "Review as an experienced startup founder. Look for ownership, bias to action, "
        "resourcefulness and evidence of shipped work. Be direct and specific.",
    ),
    "Indian market expert": (
        "A local lens on placements and early-career hiring.",
        "Review as an expert in the Indian job market: campus placements, fresher hiring, "
        "product and service companies, CGPA requirements and technical hiring.",
    ),
    "HR professional": (
        "A structured review of clarity and role fit.",
        "Review as an experienced HR professional. Evaluate ATS compatibility, "
        "clear career progression, professional formatting and job alignment.",
    ),
}


def fingerprint(resume, job, model, persona, temperature):
    payload = [resume.get("raw_text", ""), job, model, persona, temperature]
    return hashlib.sha256(json.dumps(payload).encode()).hexdigest()


def generation_failed(content):
    return not content.strip() or content.lstrip().startswith("⚠️") or "⚠️ Ollama error:" in content


def render_scorecard(report):
    scores = report["scores"]
    if scores.get("analysis_error"):
        st.warning("The written review is ready, but the model could not produce a valid scorecard. No estimated scores have been substituted.")
        if st.button("Retry scorecard", disabled=not installed_models):
            with st.spinner("Building your scorecard locally…"):
                report["scores"] = get_rejection_scores(
                    report["resume"]["raw_text"], report["job"], model=report["model"]
                )
            st.rerun()
        return

    sections = scores.get("sections", {})
    match_pct = scores.get("jd_keyword_match_percent", 50)
    if not isinstance(match_pct, (int, float)):
        match_pct = 50

    # Core role-related sections: experience, projects, skills
    core_keys = ["experience", "projects", "skills"]
    core_scores = [sections.get(k, {}).get("score") for k in core_keys if isinstance(sections.get(k, {}).get("score"), (int, float))]
    avg_core = sum(core_scores) / len(core_scores) if core_scores else 40

    # General structure sections: formatting, contact_header, education, summary
    struct_keys = ["formatting", "contact_header", "education", "summary"]
    struct_scores = [sections.get(k, {}).get("score") for k in struct_keys if isinstance(sections.get(k, {}).get("score"), (int, float))]
    avg_struct = sum(struct_scores) / len(struct_scores) if struct_scores else 60

    # Weighted Composite: 45% Core Experience/Skills + 40% Role Keyword Fit + 15% General Formatting
    weighted_score = (0.45 * avg_core) + (0.40 * match_pct) + (0.15 * avg_struct)

    # Domain mismatch safety guard:
    # If keyword match is <= 15% or ATS compatibility is 'poor', the resume cannot pass screening
    ats = str(scores.get("ats_compatibility", "")).lower()
    if match_pct <= 15:
        computed_score = min(int(round(weighted_score)), 25)
        verdict = "Severe role mismatch"
        verdict_sub = "This resume shows qualifications in a completely different domain than the target job."
        verdict_class = "verdict-severe"
    elif match_pct <= 30 or ats == "poor":
        computed_score = min(int(round(weighted_score)), 45)
        verdict = "Comprehensive revision needed"
        verdict_sub = "Significant experience and keyword gaps for this role."
        verdict_class = "verdict-severe"
    elif weighted_score < 60:
        computed_score = int(round(weighted_score))
        verdict = "Needs refinement"
        verdict_sub = "A starting point for improvement, not a prediction of a hiring decision."
        verdict_class = "verdict-warning"
    elif weighted_score < 80:
        computed_score = int(round(weighted_score))
        verdict = "Ready for junior roles"
        verdict_sub = "Solid foundation with good potential for junior or entry-level positions."
        verdict_class = "verdict-ok"
    else:
        computed_score = int(round(weighted_score))
        verdict = "Strong candidate"
        verdict_sub = "Strong alignment with the core requirements of this role."
        verdict_class = "verdict-ok"

    st.markdown(
        f'<div class="verdict"><span class="eyebrow">THE BIG PICTURE</span>'
        f'<h3 class="{verdict_class}">{escape(verdict)}</h3>'
        f'<p>{escape(verdict_sub)}</p></div>',
        unsafe_allow_html=True,
    )
    a, b, c, d = st.columns(4)
    a.metric("Resume Score", f'{computed_score} / 100')
    seconds = scores.get("attention_seconds")
    b.metric("Estimated attention", f"{seconds}s" if seconds is not None else "Unavailable")
    match = scores.get("jd_keyword_match_percent")
    c.metric("Role keyword match", f"{match}%" if match is not None else "Unavailable")
    d.metric("ATS compatibility", str(scores.get("ats_compatibility", "Unavailable")).title())
    st.caption("AI-generated estimates, not measured recruiter behavior. Higher scores are better.")
    st.caption(
        "Score formula: 45% core sections (experience, projects, skills) "
        "+ 40% role keyword match + 15% structure (formatting, contact, education, summary)."
    )

    left, right = st.columns(2, gap="large")
    with left:
        with st.container(border=True):
            st.markdown("#### Overall Resume Score")
            st.plotly_chart(build_resume_score_gauge(computed_score), use_container_width=True, config={"displayModeBar": False})
    with right:
        with st.container(border=True):
            st.markdown("#### Strength by section")
            st.plotly_chart(build_section_radar(scores.get("sections", {})), use_container_width=True, config={"displayModeBar": False})

    st.markdown("#### Where to focus")
    st.plotly_chart(build_section_bar(scores.get("sections", {})), use_container_width=True, config={"displayModeBar": False})
    for name, data in scores.get("sections", {}).items():
        st.markdown(
            '<div class="section-feedback">'
            f'<div><strong>{escape(name.replace("_", " ").title())}</strong>'
            f'<p>{escape(str(data.get("one_liner", "")))}</p></div>'
            f'<span class="section-score">{escape(str(data.get("score", "—")))}<small> / 100</small></span></div>',
            unsafe_allow_html=True,
        )
    st.markdown("#### The keyword check")
    left, right = st.columns([1, 1.3], gap="large")
    with left:
        st.plotly_chart(build_keyword_match_donut(match), use_container_width=True, config={"displayModeBar": False})
    with right:
        st.markdown("**Already in your resume**")
        tags(scores.get("strong_keywords_found", []), "found", "No matching keywords were identified.")
        st.markdown("**Worth a closer look**")
        tags(scores.get("missing_keywords", []), "missing", "No missing keywords were identified.")
        st.caption("Only add skills and experience you actually have. Keywords should support your story, not replace it.")


def render_report(report):
    st.markdown('<div class="report-anchor" id="your-review"></div>', unsafe_allow_html=True)
    # Auto-scroll to review on render
    components.html("""
        <script>
        (function() {
            const anchor = window.parent.document.getElementById('your-review');
            if (anchor) {
                anchor.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        })();
        </script>
    """, height=0, width=0)
    section_heading("YOUR REVIEW", "A clearer picture. A practical next step.")
    st.caption(f'{report["resume"]["file_name"]} · {report["persona"]} · {report["model"]} · Generated in {report["elapsed"]}s')
    review, scorecard, rewrite, interview, chat_tab = st.tabs(["The review", "Scorecard", "Rewrite a section", "Interview prep", "💬 Q&A"])
    with review:
        with st.container(border=True):
            st.markdown(report["roast"])
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button("Download review text", report["roast"], "resume_review.md", mime="text/markdown", key="download_review")
        with col2:
            if get_elevenlabs_key():
                if st.button("🔊 Listen to Roast (ElevenLabs)", key="play_roast", help="Generates audio using your ElevenLabs API key"):
                    with st.spinner("Generating brutal voiceover..."):
                        try:
                            audio_bytes = generate_voice_roast(report["roast"], report["persona"])
                            if audio_bytes:
                                st.audio(audio_bytes, format="audio/mp3", autoplay=True)
                        except RuntimeError as e:
                            st.error(str(e))
            else:
                st.caption("Add ElevenLabs API key to `.env` to enable audio roasting.")

    with scorecard:
        render_scorecard(report)
    with rewrite:
        st.markdown("### Make every line earn its place.")
        
        # New Feature: Master Export
        if report.get("rewrites"):
            st.success(f"You have rewritten {len(report['rewrites'])} section(s).")
            c1, c2 = st.columns(2)
            with c1:
                md_export = generate_markdown_export(report)
                st.download_button("📥 Download Master Draft (.md)", md_export, "resume_draft.md", mime="text/markdown", use_container_width=True)
            with c2:
                docx_export = generate_docx_export(report)
                st.download_button("📥 Download Master Draft (.docx)", docx_export, "resume_draft.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
            st.divider()

        st.caption("Choose a section, refine the source text, and get a more focused version for this role.")
        sections = report["resume"].get("sections", {})
        options = list(sections) or ["experience", "skills", "projects", "summary"]
        section = st.selectbox("Resume section", options, format_func=lambda s: s.replace("_", " ").title(), key=f'section_{report["id"]}')
        original = st.text_area("Original section", value=sections.get(section, ""), height=220, key=f'original_{report["id"]}_{section}', placeholder="Paste the section you want to improve…")
        if st.button("Rewrite section", type="primary", disabled=len(original.strip()) < 10 or not installed_models):
            with st.spinner("Finding a stronger way to say it…"):
                rewritten = rewrite_section(section, original, report["job"], model=report["model"])
            if generation_failed(rewritten):
                st.error("The rewrite could not be completed. Check the local model and try again.")
            else:
                report.setdefault("rewrites", {})[section] = {"source": original, "text": rewritten}
        saved = report.get("rewrites", {}).get(section)
        if saved:
            if saved["source"] != original:
                st.info("You changed the source text. Rewrite again to update the draft below.")

            diff_toggle = st.toggle("Show word-level diff", key=f"diff_toggle_{report['id']}_{section}")

            with st.container(border=True):
                if diff_toggle:
                    st.markdown("#### Word-level diff")
                    st.caption("Green = added · Red strikethrough = removed")
                    st.markdown(
                        render_word_diff(saved["source"], saved["text"]),
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown("#### Suggested rewrite")
                    st.markdown(saved["text"])
            st.caption("Review before using: verify every fact, skill and metric. Remove anything you cannot substantiate.")
    with interview:
        st.markdown("### Be ready for the follow-up.")
        st.caption("Practice likely questions based on your experience and the role you’re targeting.")
        if st.button("Generate interview questions", type="primary", disabled=not installed_models):
            role = parse_jd_text(report["job"]).get("role_title", "the role")
            with st.spinner("Preparing questions around your experience…"):
                content = generate_interview_prep(report["resume"]["raw_text"], role, model=report["model"])
            if generation_failed(content):
                st.error("Interview prep could not be completed. Check the local model and try again.")
            else:
                report["interview"] = content
        if report.get("interview"):
            with st.container(border=True):
                st.markdown(report["interview"])
            st.download_button("Download interview prep", report["interview"], "interview_prep.md", mime="text/markdown")
        else:
            st.markdown('<div class="quiet-empty"><span class="empty-symbol">?</span><h4>A little preparation goes a long way.</h4><p>Your questions and talking points will appear here.</p></div>', unsafe_allow_html=True)
    with chat_tab:
        st.markdown("### Ask follow-up questions")
        st.caption("Ask about specific frameworks, career choices, or how to phrase your experience for this role.")
        
        chat_key = f"chat_{report['id']}"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = [
                {"role": "assistant", "content": f"I'm ready. What do you want to ask about your resume or this role? I'll review it keeping the {report['persona']} perspective in mind."}
            ]
        else:
            # Auto-purge any stale error bubbles or long essay from prior session
            st.session_state[chat_key] = [
                m for m in st.session_state[chat_key]
                if "stream_chat_response" not in m.get("content", "")
                and "Career Coach Friend" not in m.get("content", "")
                and "First off, great job on your resume" not in m.get("content", "")
            ]

        if len(st.session_state[chat_key]) > 1:
            if st.button("Reset chat", key=f"reset_chat_{report['id']}", type="secondary"):
                st.session_state[chat_key] = [
                    {"role": "assistant", "content": f"I'm ready. What do you want to ask about your resume or this role? I'll review it keeping the {report['persona']} perspective in mind."}
                ]
                st.rerun()
            
        # Display chat messages from history on app rerun
        for msg in st.session_state[chat_key]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
        # Accept user input
        if prompt := st.chat_input("E.g., Should I add Next.js to my skills?"):
            # Display user message in chat message container
            st.session_state[chat_key].append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
                
            # Display assistant response in chat message container
            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                full_response = ""
                
                # Stream the response
                try:
                    for chunk in stream_chat_response(
                        chat_history=st.session_state[chat_key],
                        resume_text=report["resume"]["raw_text"],
                        jd_text=report["job"],
                        model=report["model"],
                        persona_system=PERSONAS[report["persona"]][1],
                    ):
                        full_response += chunk
                        response_placeholder.markdown(full_response + "▌")
                    response_placeholder.markdown(full_response)
                except Exception as e:
                    full_response = f"⚠️ Chat error: {str(e)}"
                    response_placeholder.markdown(full_response)
                    
            # Add assistant response to chat history
            st.session_state[chat_key].append({"role": "assistant", "content": full_response})


installed_models = get_installed_models()

# Merge installed models with a curated recommended list so the user can
# always see popular options and know which are ready vs. need a pull.
# Only the 3 models we have downloaded (or are downloading right now)
RECOMMENDED_MODELS = ["llama3.2", "gemma2", "mistral"]

# Clean model names: strip redundant ':latest' tag for clean UI display
clean_installed = []
for m in installed_models:
    clean_name = m[:-7] if m.endswith(":latest") else m
    if clean_name not in clean_installed:
        clean_installed.append(clean_name)

# Build list: installed models first, then any from our curated list not yet pulled
model_options = list(clean_installed)
for rec in RECOMMENDED_MODELS:
    if rec not in clean_installed and rec not in model_options:
        model_options.append(rec + "  (downloading...)")

with st.sidebar:
    brand()
    st.markdown('<div class="sidebar-label">YOUR WORKSPACE</div>', unsafe_allow_html=True)
    page = st.radio("Workspace navigation", ["Resume review", "How it works"], label_visibility="collapsed", key="workspace_page")
    st.divider()
    st.markdown('<div class="sidebar-label">MAKE IT YOURS</div>', unsafe_allow_html=True)
    persona = st.selectbox("Your reviewer", list(PERSONAS), key="reviewer")
    st.caption(PERSONAS[persona][0])

    # Normalize existing session state if it previously stored ':latest'
    if "local_model" in st.session_state and st.session_state["local_model"] not in model_options:
        normalized_state = st.session_state["local_model"].replace(":latest", "")
        if normalized_state in model_options:
            st.session_state["local_model"] = normalized_state
        elif model_options:
            st.session_state["local_model"] = model_options[0]

    # Model picker — installed models + recommended ones labelled for pulling
    raw_selection = st.selectbox(
        "Local model",
        model_options,
        key="local_model",
        help="✓ models are ready. Others need `ollama pull <model>` first.",
        disabled=not installed_models,
    )
    # Strip the "← pull to use" hint before passing to Ollama
    model = raw_selection.replace("  (downloading...)", "").replace("  ← pull to use", "").strip()
    needs_pull = "(downloading...)" in raw_selection or "← pull to use" in raw_selection
    if needs_pull:
        st.caption(f"⏳ `{model}` is still downloading. Switch back to `llama3.2` for now.")

    with st.expander("Fine-tune your review"):
        temperature = st.slider("Roast intensity", 0.3, 1.0, 0.85, 0.05, help="Higher values make the feedback more creative and direct.")
        st.caption("Measured at 0.3. Unfiltered at 1.0.")

    st.markdown('<div class="sidebar-spacer"></div>', unsafe_allow_html=True)

    # Compact status row + refresh — no full expander needed since Ollama is set up
    if installed_models:
        st.markdown(
            '<div class="connection"><span class="status-dot"></span>'
            '<div><strong>Local model connected</strong>'
            f'<small>{len(installed_models)} model{"s" if len(installed_models) != 1 else ""} ready</small>'
            '\u003c/div\u003e\u003c/div\u003e',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '\u003cdiv class="connection"\u003e\u003cspan class="status-dot offline"\u003e\u003c/span\u003e'
            '\u003cdiv\u003e\u003cstrong\u003eOllama not running\u003c/strong\u003e'
            '\u003csmall\u003eRun: ollama serve\u003c/small\u003e\u003c/div\u003e\u003c/div\u003e',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="privacy-note"><span class="privacy-icon">↳</span>'
        '<div><strong>Your career. Your data.</strong>'
        '<p>Processed on the machine running this app. No external AI service. No account needed.</p>'
        '</div></div>'
        '<div class="sidebar-footer">OPEN SOURCE. ON YOUR SIDE.</div>',
        unsafe_allow_html=True,
    )

st.markdown('<div class="topbar"><span>THE RESUME WORKSPACE</span><span class="topbar-note"><span class="status-dot"></span>Local-first. Always.</span></div>', unsafe_allow_html=True)

if page == "How it works":
    section_heading("A LITTLE CONTEXT", "Honest feedback. Without the guesswork.")
    st.markdown("A second pair of eyes before you hit apply. RoastMyResume compares your experience with a role, then helps you make a stronger case.")
    for number, title, description in [
        ("01", "Bring your experience", "Upload a text-based PDF or DOCX. Scanned images are not supported, so check the extracted text before you begin."),
        ("02", "Add the role", "Paste the job description or import a public job posting. If a website blocks access, paste the description instead."),
        ("03", "Choose your perspective", "Pick a reviewer and an installed Ollama model in the sidebar. Your choice changes the tone, not the need for honest, useful feedback."),
        ("04", "Review, refine, repeat", "Read your review, explore the scorecard, rewrite a section and prepare for follow-up questions. Downloads stay available as you work."),
    ]:
        st.markdown(f'<div class="how-step"><span>{number}</span><div><h3>{title}</h3><p>{description}</p></div></div>', unsafe_allow_html=True)
    with st.expander("What happens to my resume?", expanded=True):
        st.write("Your document is parsed by the machine running this app and sent to its local Ollama server. It is not sent to a third-party AI provider. Importing a job posting makes a request to that website, but does not send your resume. If you host the app remotely, that host processes the document—not your browser’s device.")
        st.write("Reports are kept in this browser session, not a permanent account. Download anything you want to keep before closing or refreshing the session.")
    with st.expander("How should I interpret the scores?"):
        st.write("Scores and recruiter attention are model estimates, not hiring probabilities or measured behavior. Different models can give different assessments. Use the specific feedback as a guide, verify rewritten facts, and keep your experience authentic.")
else:
    hero()
    left, right = st.columns(2, gap="large")
    resume_data = None
    with left:
        with st.container(border=True):
            section_heading("01 / THE STARTING POINT", "Your experience, on paper.", "Upload the resume you’re ready to make better.", level=3)
            uploaded = st.file_uploader("Upload your resume", type=["pdf", "docx"], label_visibility="collapsed", help="Text-based PDF or DOCX, up to 10 MB. Scanned PDFs are not supported.", key="resume_upload")
            st.caption("PDF or DOCX · Up to 10 MB · Text-based documents")
            if uploaded is not None:
                file_id = hashlib.sha256(uploaded.getvalue()).hexdigest() + uploaded.name
                if uploaded.size > 10 * 1024 * 1024:
                    st.error("This file is larger than 10 MB. Please upload a smaller document.")
                else:
                    if st.session_state.get("resume_file_id") != file_id:
                        try:
                            uploaded.seek(0)
                            with st.spinner("Reading your document…"):
                                parsed = parse_resume(uploaded)
                            if not parsed["raw_text"].strip():
                                raise ValueError("No readable text was found. If this is a scanned PDF, export a text-based PDF or use DOCX.")
                            st.session_state["resume_data"] = parsed
                            st.session_state["resume_file_id"] = file_id
                            st.session_state.pop("upload_error", None)
                        except Exception as error:
                            st.session_state.pop("resume_data", None)
                            st.session_state.pop("resume_file_id", None)
                            st.session_state["upload_error"] = str(error)
                    resume_data = st.session_state.get("resume_data")
                    if st.session_state.get("upload_error"):
                        st.error("We couldn’t read this document. Try a text-based PDF or DOCX.")
                        with st.expander("Document details"):
                            st.text(st.session_state["upload_error"])
                if resume_data:
                    st.success(f'Ready to review · {resume_data["word_count"]} words')
                    if len(resume_data["raw_text"]) > 3000:
                        st.warning(
                            f"This resume is {len(resume_data['raw_text']):,} characters. "
                            "The AI reviews the first ~3,000 characters for scoring and ~4,000 for the written "
                            "feedback. If your resume is 2+ pages, consider trimming it or checking that the "
                            "most important sections appear early."
                        )
                    with st.expander("Check extracted text"):
                        st.text_area("Extracted resume text", resume_data["raw_text"], height=200, disabled=True)
                        tags(list(resume_data.get("sections", {})), "neutral")
            else:
                st.markdown('''
                    <div class="job-description-empty" style="min-height: 220px;">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                            <line x1="16" y1="13" x2="8" y2="13"/>
                            <line x1="16" y1="17" x2="8" y2="17"/>
                            <polyline points="10 9 9 9 8 9"/>
                        </svg>
                        <h4>Upload your resume</h4>
                        <p>Drag & drop a PDF or DOCX, or click to browse. Text-based documents only — scanned PDFs won't work.</p>
                    </div>
                ''', unsafe_allow_html=True)

    with right:
        with st.container(border=True):
            section_heading("02 / THE OPPORTUNITY", "What's the next move?", "Give your feedback a role to focus on.", level=3)
            input_type = st.radio("Job description source", ["Paste description", "Import from URL", "Describe a role"], horizontal=True, label_visibility="collapsed", key="job_source")
            job_text = ""
            if input_type == "Paste description":
                job_text = st.text_area("Job description", height=164, placeholder="Paste the role, responsibilities and requirements here…", label_visibility="collapsed", key="job_description")
                st.caption("A full description makes the feedback more specific.")
            elif input_type == "Import from URL":
                job_url = st.text_input("Public job posting URL", placeholder="https://company.com/careers/role", key="job_url")
                if st.button("Import description", disabled=not job_url.strip(), use_container_width=True):
                    parsed_url = urlparse(job_url.strip())
                    if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
                        st.error("Enter a complete URL starting with https:// or http://.")
                    else:
                        with st.spinner("Reading the job posting…"):
                            imported = scrape_jd_from_url(job_url.strip())
                        if not imported.strip() or imported.startswith("[Error"):
                            st.error("This posting couldn't be imported. The site may restrict access. Choose 'Paste description' instead.")
                            st.session_state.pop("imported_job", None)
                        else:
                            st.session_state["imported_job"] = imported
                            st.session_state["imported_url"] = job_url.strip()
                if st.session_state.get("imported_job") and st.session_state.get("imported_url") == job_url.strip():
                    job_text = st.text_area("Imported description · edit as needed", value=st.session_state["imported_job"], height=140, key="imported_text_" + hashlib.sha256(st.session_state["imported_job"].encode()).hexdigest()[:12])
                st.caption("Some job sites block imports. Pasting the text always works.")
            else:
                job_text = st.text_area("Target role", height=164, placeholder="e.g. A frontend engineering internship at a small product team. React, TypeScript, and accessible interfaces.", key="target_role")
                st.caption("No job posting yet? Describe the role and skills you're aiming for.")

            # Empty state when no job description entered
            if not job_text.strip():
                st.markdown('''
                    <div class="job-description-empty">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
                            <polyline points="14 2 14 8 20 8"/>
                            <line x1="16" y1="13" x2="8" y2="13"/>
                            <line x1="16" y1="17" x2="8" y2="17"/>
                            <line x1="10" y1="9" x2="8" y2="9"/>
                        </svg>
                        <h4>Add a role to get started</h4>
                        <p>Paste a job description, import from a URL, or describe your target role. The review focuses on what you provide.</p>
                    </div>
                ''', unsafe_allow_html=True)

    job_text = job_text.strip()
    ready = bool(resume_data and job_text and installed_models)
    action, action_note = st.columns([1, 1], gap="large")
    with action:
        run_review = st.button("Give me an honest review  →", type="primary", use_container_width=True, disabled=not ready, key="run_review_btn")
    with action_note:
        if not resume_data:
            note = "Start with your resume. We'll take it from there."
        elif not job_text:
            note = "Next, add a job description or describe your target role."
        elif not installed_models:
            note = "Almost there. Connect Ollama in the sidebar to begin."
        else:
            note = "A little tough love. A lot of actionable advice."
        st.markdown(f'<div class="action-note">{note}<small>Runs locally · Timing depends on your model and hardware</small></div>', unsafe_allow_html=True)

    # Keyboard shortcut: Cmd/Ctrl+Enter in a job-description field runs the review.
    # Streamlit does not expose widget `key`s in the DOM, so bind by the accessible
    # label on the job-description textareas instead.
    components.html("""
        <script>
        (function() {
            // Streamlit exposes widget keys in Python, not the DOM, so match the
            // textareas by their accessible label prefix (case-insensitive).
            var LABELS = ['job description', 'target role', 'imported description'];
            var bound = new WeakSet();
            function attach() {
                var doc = window.parent.document;
                doc.querySelectorAll('textarea').forEach(function (ta) {
                    if (bound.has(ta)) return;
                    var label = (ta.getAttribute('aria-label') || '').toLowerCase();
                    var isJobField = LABELS.some(function (l) { return label.indexOf(l) === 0; });
                    if (!isJobField) return;
                    bound.add(ta);
                    ta.addEventListener('keydown', function (e) {
                        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                            e.preventDefault();
                            var btn = doc.querySelector('button[data-testid="stBaseButton-primary"]');
                            if (btn && !btn.disabled) btn.click();
                        }
                    });
                });
            }
            // Streamlit reruns replace these nodes, so rebind on every observed change.
            attach();
            new MutationObserver(attach).observe(window.parent.document.body, {
                childList: true, subtree: true
            });
        })();
        </script>
    """, height=0, width=0)

    if run_review and ready:
        started = time.monotonic()
        
        # New Progress Bar UX
        prog_bar = st.progress(0, text="Initializing local AI model...")
        
        prog_bar.progress(10, text="Phase 1: Reading Resume & Job Description...")
        time.sleep(0.5)
        
        prog_bar.progress(25, text="Phase 2: Writing the brutal roast (Streaming)...")
        output = st.empty()
        content = ""
        try:
            for chunk in stream_roast(resume_data["raw_text"], job_text, model=model, persona_system=PERSONAS[persona][1] + " Use professional Markdown headings without emojis. Do not invent experience or metrics.", temperature=temperature):
                content += chunk
                output.markdown(content)
            if generation_failed(content):
                raise RuntimeError("The local model did not finish the review.")
            
            prog_bar.progress(70, text="Phase 3: Calculating Scorecard & Analytics (This takes about 30s)...")
            scores = get_rejection_scores(resume_data["raw_text"], job_text, model=model)
            
            prog_bar.progress(100, text="Done!")
            time.sleep(0.5)
            prog_bar.empty()
            output.empty() # Clear the streaming text so it doesn't duplicate above the final UI
            
            st.session_state["analysis"] = {
                "id": time.time_ns(), "fingerprint": fingerprint(resume_data, job_text, model, persona, temperature),
                "resume": dict(resume_data), "job": job_text, "model": model,
                "persona": persona, "roast": content, "scores": scores,
                "elapsed": round(time.monotonic() - started, 1),
            }
            # Toast notification on success
            st.toast("Review complete! 🎉", icon="✅")
        except Exception as e:
            prog_bar.empty()
            st.error(f"Generation failed. Check that Ollama is running.\n\n{str(e)}")

    report = st.session_state.get("analysis")
    if report:
        current_fingerprint = fingerprint(resume_data or {}, job_text, model, persona, temperature)
        if current_fingerprint != report["fingerprint"]:
            st.info("Your inputs or settings have changed. The report below is your previous review; run another review to update it.")
        render_report(report)
    else:
        st.markdown('''<div class="expectations"><div class="expectations-intro"><span class="eyebrow">LESS GUESSWORK. MORE DIRECTION.</span><h3>Not just a roast.<br>A way forward.</h3><p>Know what's working, what's holding you back, and what to do next.</p></div><div class="expectations-list"><div><span>01</span><section><h4>The honest read</h4><p>A recruiter's first impression, with specific fixes for every section.</p></section></div><div><span>02</span><section><h4>The details that matter</h4><p>Section scores, role alignment, and keywords you may have missed.</p></section></div><div><span>03</span><section><h4>A stronger next draft</h4><p>Focused rewrites and interview questions to help you move forward.</p></section></div></div></div>''', unsafe_allow_html=True)

st.markdown('<div class="workspace-footer"><span>RoastMyResume<span class="footer-dot">·</span>Built for your next chapter.</span></div>', unsafe_allow_html=True)
