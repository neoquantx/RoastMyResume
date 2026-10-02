"""Small presentation helpers; user/model content is escaped before HTML output."""

from html import escape
import streamlit as st


def brand():
    st.markdown('''<div class="brand"><span class="brand-mark">r<span>·</span></span><div><strong>RoastMyResume</strong><small>A BETTER FIRST IMPRESSION</small></div></div>''', unsafe_allow_html=True)


def section_heading(kicker, title, description="", level=2):
    level = level if level in (2, 3) else 2
    description_html = f"<p>{escape(description)}</p>" if description else ""
    st.markdown(f'<div class="section-heading"><span class="eyebrow">{escape(kicker)}</span><h{level}>{escape(title)}</h{level}>{description_html}</div>', unsafe_allow_html=True)


def tags(values, variant="neutral", empty=""):
    if not values:
        if empty:
            st.caption(empty)
        return
    variant = variant if variant in {"neutral", "found", "missing"} else "neutral"
    st.markdown('<div class="tag-list">' + "".join(f'<span class="tag tag-{variant}">{escape(str(value))}</span>' for value in values) + '</div>', unsafe_allow_html=True)


def hero():
    st.markdown('''<div class="hero"><div class="hero-copy"><span class="hero-kicker"><span class="tiny-line"></span>HONEST FEEDBACK. BETTER OPPORTUNITIES.</span><h1>Good experience.<br><span>Better on paper.</span></h1><p>You’ve done the work. Let’s make sure your resume shows it.<br class="desktop-break"> Get a candid review, clear fixes, and a stronger next draft.</p><div class="hero-footnote"><span class="small-check">✓</span>Private by design<span class="footnote-dot">·</span>Powered by open-source AI</div></div><div class="resume-preview" aria-label="Illustration of turning a vague resume bullet into a specific achievement"><div class="preview-toolbar"><span class="preview-file">YOUR NEXT DRAFT</span><span class="preview-status">A little sharper</span></div><div class="preview-document"><div class="document-heading"><span class="document-avatar">R.</span><div><span class="skeleton-line long"></span><span class="skeleton-line short"></span></div><span class="document-check">✓</span></div><span class="document-label">EXPERIENCE</span><div class="before-line">Responsible for working on projects.</div><div class="annotation"><span class="annotation-arrow">↳</span><div><strong>Show the impact. Not just the task.</strong><p>What did you build? Who did it help?<br>What changed because of your work?</p></div></div><div class="document-bottom"><span class="skeleton-line"></span><span class="skeleton-line short"></span></div></div><div class="preview-caption"><span class="small-check">✓</span>Same experience. A stronger story.</div></div></div>''', unsafe_allow_html=True)
