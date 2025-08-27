"""
Keyword Surfer - Streamlit App

Installation (recommended):
  pip install -r requirements.txt

Minimal dependencies (if installing manually):
  streamlit
  requests

Run:
  streamlit run app.py
"""

import json
import textwrap
from typing import List
import os
import re
import random

import requests
import streamlit as st

# -----------------------------
# Backend Functions
# -----------------------------

SUGGEST_URL = "https://suggestqueries.google.com/complete/search"

# Mandatory Contact Us section to include in every blog
CONTACT_US_MD = textwrap.dedent(
    """
    ## Contact Us
    💡 Want to reduce your electricity bill to ZERO starting next month?
    Book your Free Home Visit Today and instantly claim ₹78,000 Government Subsidy — all paperwork to installation is handled by Mierae Solar. Start saving up to ₹5,000 on your electricity bill every month, effortlessly!

    Mierae Solar Energy Private Limited
    HD-065, Eldeco Centre, Malviya Nagar, Delhi – 17
    📞 Contact Number: 9070607050
    🌐 Visit our Website: www.mierae.com
    📧 Email: solar@mierae.com
    🌐 Follow Us on Social Media:
    * Facebook: [Mierae Solar Facebook Page](https://www.facebook.com/p/Mierae-61566760449520/)
    * LinkedIn: [Mierae Solar LinkedIn](https://www.linkedin.com/company/102557528/)
    """
)

# Promotional snippet for Mierae website to be injected when needed
PROMO_SNIPPET_MD = textwrap.dedent(
    """
    > Looking for hassle-free solar installation, subsidy support, or a free home visit? Visit **[Mierae.com](https://www.mierae.com)** to Book Your Free Home Visit today. Start saving on your electricity bill now!
    
    - Solar installation by trusted experts: **www.mierae.com**
    - Claim your government subsidy with complete assistance: **www.mierae.com**
    - Book a free home visit in minutes: **[Book Now](https://www.mierae.com)**
    """
)


def get_google_suggestions(keyword: str, lang: str = "en", country: str = "US", limit: int = 10) -> List[str]:
    """
    Fetch autocomplete suggestions from Google's unofficial endpoint.

    Tries multiple clients (firefox, chrome, toolbar) and parses their
    different response shapes. Returns up to `limit` suggestions.
    """
    if not keyword:
        return []

    clients = ["firefox", "chrome", "toolbar"]
    bases = [
        "https://suggestqueries.google.com/complete/search",
        "https://www.google.com/complete/search",
    ]
    base_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.google.com/",
        "Accept-Language": f"{lang}-{country},{lang};q=0.9",
    }

    def parse_payload(data) -> List[str]:
        # Firefox and some chrome variants: [query, [s1, s2, ...], ...]
        if isinstance(data, list):
            if len(data) > 1 and isinstance(data[1], list):
                items = data[1]
                if items and isinstance(items[0], str):
                    return [s for s in items if isinstance(s, str)]
                # Some variants: list of lists [["foo",..],["bar",..]]
                if items and isinstance(items[0], list):
                    out = []
                    for it in items:
                        if isinstance(it, list) and it and isinstance(it[0], str):
                            out.append(it[0])
                    return out
        # Some responses may be dict-like
        if isinstance(data, dict):
            if "suggestions" in data and isinstance(data["suggestions"], list):
                out = []
                for it in data["suggestions"]:
                    if isinstance(it, dict):
                        v = it.get("value") or it.get("term") or it.get("q")
                        if isinstance(v, str):
                            out.append(v)
                return out
        return []

    attempts_log = []
    for base in bases:
        for client in clients:
            params = {
                "client": client,
                "q": keyword,
                "hl": lang,
                "gl": country,
                "ie": "utf8",
                "oe": "utf8",
            }
            try:
                r = requests.get(base, params=params, headers=base_headers, timeout=10)
                r.raise_for_status()
                data = r.json()
                suggestions = parse_payload(data)
                if suggestions:
                    st.session_state["suggest_debug"] = {
                        "ok": True,
                        "endpoint": r.url,
                        "count": len(suggestions),
                    }
                    return suggestions[:limit]
                else:
                    attempts_log.append({"url": r.url, "status": r.status_code, "note": "no suggestions parsed"})
            except Exception as e:
                # try next combination
                attempts_log.append({"url": f"{base}?client={client}", "error": str(e)[:200]})
                continue

    st.session_state["suggest_debug"] = {"ok": False, "attempts": attempts_log}
    return []


# -----------------------------
# Frontend (Streamlit)
# -----------------------------

st.set_page_config(page_title="Keyword Surfer", page_icon="🔎", layout="centered")

st.title("🔎 Keyword Surfer")
st.caption("Get Google Autocomplete Suggestions")

# Reload button
col_reload, _ = st.columns([1, 9])
with col_reload:
    if st.button("↻ Reload", type="secondary"):
        # Clear transient outputs and rerun
        for k in ["blog_output", "blog_used_keywords", "blog_main_keyword", "blog_other_keywords"]:
            st.session_state.pop(k, None)
        try:
            st.rerun()
        except Exception:
            st.experimental_rerun()

with st.sidebar:
    st.subheader("Settings")
    lang = st.text_input("Language (hl)", value="en")
    country = st.text_input("Country (gl)", value="US")
    show_debug = st.checkbox("Show debug", value=False)
    st.markdown("---")
    st.subheader("Generation Status")
    model_status = st.empty()

keyword = st.text_input("Base Keyword", placeholder="e.g. best coffee beans")
get_btn = st.button("Get Keywords", type="primary")

suggestions: List[str] = []

if get_btn:
    if not keyword.strip():
        st.warning("Please enter a keyword.")
    else:
        with st.spinner("Fetching Google suggestions..."):
            suggestions = get_google_suggestions(keyword.strip(), lang=lang.strip() or "en", country=country.strip() or "US", limit=10)
            # Persist latest query and suggestions so they stay visible across reruns
            st.session_state["last_keyword"] = keyword.strip()
            st.session_state["last_suggestions"] = suggestions

# Determine what to display based on latest successful fetch
display_keyword = keyword.strip() or st.session_state.get("last_keyword", "")
display_suggestions: List[str] = []
if suggestions:
    display_suggestions = suggestions
else:
    display_suggestions = st.session_state.get("last_suggestions", [])

if display_keyword:
    st.markdown("---")
    st.subheader("Results")

    st.markdown(f"**Base Keyword:** {display_keyword}")
    
    st.markdown("**Suggestions**")
    if display_suggestions:
        for s in display_suggestions:
            st.write(f"- {s}")
    else:
        st.write("- No suggestions found.")

    # -------------------------------------------------
    # Blog Generation: uses extracted keywords above (or base keyword)
    # -------------------------------------------------
    if True:
        st.markdown("---")
        st.subheader("Generate Blog")

        # Choose which keywords to use (default: all suggestions + base)
        default_selection = display_suggestions
        selected_keywords = st.multiselect(
            "Select keywords to include",
            options=display_suggestions,
            default=default_selection,
        )

        include_base = st.checkbox("Include base keyword", value=True)
        effective_keywords = ([display_keyword] if include_base and display_keyword else []) + selected_keywords

        # Load instruction file
        def _read_instructions() -> str:
            candidates = [
                "instruction blogs generate .md",  # file present in workspace with space
                "instruction blogs generate.md",   # fallback without extra space
            ]
            for name in candidates:
                try:
                    with open(name, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception:
                    continue
            return ""

        instructions_text = _read_instructions()

        # OpenRouter round-robin with Gemini fallback
        # API keys loaded from Streamlit secrets or environment (no UI inputs)
        def _get_secret(name: str) -> str:
            try:
                return st.secrets[name]
            except Exception:
                return os.environ.get(name, "")

        openrouter_key = _get_secret("OPENROUTER_API_KEY")
        gemini_key = _get_secret("GEMINI_API_KEY")

        # Show quick notice if keys are missing (useful for local dev)
        with st.sidebar:
            if not openrouter_key and not gemini_key:
                st.warning("No API keys found. Add them to .streamlit/secrets.toml or environment vars.")
            elif not openrouter_key:
                st.info("OpenRouter key missing. Will try Gemini only.")
            elif not gemini_key:
                st.info("Gemini key missing. Will use OpenRouter only.")
        OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
        MODELS = [
            "meta-llama/llama-3.3-70b-instruct:free",
            "mistralai/mistral-small-3.2-24b-instruct:free",
            "google/gemma-3-27b-it:free",
            "cognitivecomputations/dolphin3.0-mistral-24b:free",
            "deepseek/deepseek-r1-distill-qwen-14b:free",
            "moonshotai/kimi-k2:free",
            "deepseek/deepseek-chat-v3-0324:free",
            "deepseek/deepseek-r1-0528:free",
            "z-ai/glm-4.5-air:free",
            "tngtech/deepseek-r1t2-chimera:free",
            "google/gemini-2.0-flash-exp:free",
            "qwen/qwen3-235b-a22b:free",
            "openai/gpt-oss-20b:free",
            "microsoft/mai-ds-r1:free",
            "deepseek/deepseek-r1-0528-qwen3-8b:free",
            "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
            "mistralai/mistral-nemo:free",
            "qwen/qwen3-30b-a3b:free",
            "mistralai/mistral-7b-instruct:free",
            "tencent/hunyuan-a13b-instruct:free",
            "featherless/qwerky-72b:free",
            "moonshotai/kimi-vl-a3b-thinking:free",
            "mistralai/devstral-small-2505:free",
            "rekaai/reka-flash-3:free",
        ]

        def _openrouter_chat(model: str, prompt: str) -> str:
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": instructions_text or "You are an expert SEO blog writer."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
            }
            r = requests.post(f"{OPENROUTER_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=120)
            r.raise_for_status()
            data = r.json()
            return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        def _gemini_generate(prompt: str) -> str:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            payload = {
                "contents": [
                    {
                        "parts": [{"text": (instructions_text + "\n\n" + prompt).strip()}],
                    }
                ]
            }
            r = requests.post(url, json=payload, timeout=120)
            r.raise_for_status()
            data = r.json()
            # Try common response paths
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception:
                return json.dumps(data)[:5000]

        def _build_prompt(kw: List[str]) -> str:
            bullets = "\n".join([f"- {k}" for k in kw])
            return textwrap.dedent(f"""
            Generate a professional, persuasive, SEO-optimized blog article of 1000+ words.
            Use ALL of these keywords naturally throughout the article:
            {bullets}

            Follow the required structure: title, permalink, meta description, table of contents, headings (H2/H3), CTA, contact info, and external links. Format clean Markdown ready to publish.
            Aggressively promote Mierae's website (www.mierae.com) throughout the article with multiple inline links and CTAs for solar installation, booking a free home visit, and claiming subsidy. Mention the domain at least 3 times with meaningful anchor text and clear calls to action.
            IMPORTANT: Include the following Contact Us section verbatim at the end of the blog:
            ---
            {CONTACT_US_MD}
            ---
            """)

        def _inject_promo(text: str) -> str:
            """Ensure www.mierae.com is promoted at least 3 times by inserting promo blocks.
            - Insert after the first H1 if found; else prepend.
            - Also add a closing CTA before Contact Us.
            """
            body = text
            # Do not let Contact Us absorb the promo; split if present
            parts = re.split(r"(^##\s+Contact Us.*$)", body, flags=re.IGNORECASE | re.MULTILINE)
            prefix = body
            contact_header = ""
            suffix = ""
            if len(parts) >= 3:
                prefix = parts[0]
                contact_header = parts[1]
                suffix = body.split(parts[1], 1)[1]

            # Count mentions in the whole content (case-insensitive)
            count = len(re.findall(r"mierae\.com", body, flags=re.IGNORECASE))
            updated_prefix = prefix
            updated_suffix = suffix

            if count < 3:
                # Insert promo after first H1 if exists; else prepend
                m = re.search(r"^#\s+.*$", updated_prefix, flags=re.MULTILINE)
                if m:
                    insert_at = m.end()
                    updated_prefix = updated_prefix[:insert_at] + "\n\n" + PROMO_SNIPPET_MD + "\n" + updated_prefix[insert_at:]
                else:
                    updated_prefix = PROMO_SNIPPET_MD + "\n\n" + updated_prefix

                # Add one more CTA before Contact Us or at the end if no contact header yet
                closing_cta = "\n\n> Ready to start? Visit **www.mierae.com** and Book Your Free Home Visit today.\n"
                if contact_header:
                    updated_prefix = updated_prefix.rstrip() + closing_cta
                else:
                    updated_suffix = updated_suffix.rstrip() + closing_cta

            # Reassemble
            if contact_header:
                return updated_prefix + contact_header + updated_suffix
            return updated_prefix

        blog_output = st.session_state.get("blog_output", "")
        if st.button("Generate Blog", type="primary", disabled=(not effective_keywords) or not (openrouter_key or gemini_key)):
            with st.spinner("Generating blog (trying multiple models)..."):
                prompt = _build_prompt(effective_keywords)
                content = ""
                last_error = None
                # Try OpenRouter models in randomized order each run
                if openrouter_key:
                    randomized_models = random.sample(MODELS, k=len(MODELS))
                    for m in randomized_models:
                        try:
                            model_status.info(f"Using model: {m}")
                            content = _openrouter_chat(m, prompt)
                            if content and len(content.split()) >= 200:  # sanity check for non-empty
                                model_status.success(f"Completed with: {m}")
                                break
                        except Exception as e:
                            last_error = e
                            continue
                # Fallback to Gemini
                if (not content or len(content.strip()) == 0) and gemini_key:
                    try:
                        model_status.info("Using model: google/gemini-1.5-flash")
                        content = _gemini_generate(prompt)
                        if content and len(content.strip()) > 0:
                            model_status.success("Completed with: google/gemini-1.5-flash")
                    except Exception as e:
                        last_error = e

                if not content:
                    st.error(f"Blog generation failed. Last error: {last_error}")
                else:
                    # Promote mierae.com aggressively (ensure >=3 mentions with CTA insertions)
                    content = _inject_promo(content)

                    # Ensure Contact Us section is present; append if missing
                    if "contact us" not in content.lower() or ("9070607050" not in content and "solar@mierae.com" not in content.lower()):
                        content = content.rstrip() + "\n\n" + CONTACT_US_MD

                    st.session_state["blog_output"] = content
                    # Persist which keywords were used
                    used = list(dict.fromkeys(effective_keywords))  # preserve order, dedupe
                    main_kw = display_keyword if (include_base and display_keyword) else (used[0] if used else "")
                    others = [k for k in used if k != main_kw]
                    st.session_state["blog_used_keywords"] = used
                    st.session_state["blog_main_keyword"] = main_kw
                    st.session_state["blog_other_keywords"] = others
                    blog_output = content

        if blog_output:
            st.markdown("---")
            st.subheader("Generated Blog")
            # Show which keywords were used
            main_kw = st.session_state.get("blog_main_keyword")
            other_kws = st.session_state.get("blog_other_keywords", [])
            if main_kw or other_kws:
                st.markdown("**Keywords used in blog:**")
                if main_kw:
                    st.write(f"- Main keyword: `{main_kw}`")
                if other_kws:
                    st.write("- Other keywords:")
                    for k in other_kws:
                        st.write(f"  - `{k}`")

            # Highlight keywords in the blog content
            def _highlight_keywords(text: str, kws: List[str]) -> str:
                if not text or not kws:
                    return text
                # Sort by length to avoid shorter keywords overriding longer ones
                ordered = sorted(set(kws), key=lambda x: len(x), reverse=True)
                for kw in ordered:
                    if not kw:
                        continue
                    pattern = re.escape(kw)
                    # Case-insensitive replacement using a function to preserve original case
                    def repl(m):
                        return f"<mark>{m.group(0)}</mark>"
                    text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
                return text

            used_kws = st.session_state.get("blog_used_keywords", [])
            highlighted = _highlight_keywords(blog_output, used_kws)
            st.markdown(highlighted, unsafe_allow_html=True)

            # Copy button for blog content
            import html as _html
            escaped_blog = _html.escape(blog_output)
            copy_blog_component = f"""
            <textarea id=\"blog_copy_area\" style=\"position:absolute;left:-9999px\">{escaped_blog}</textarea>
            <button id=\"blog_copy_btn\" style=\"padding:0.5rem 0.75rem;border-radius:6px;border:1px solid #ddd;background:#f6f6f6;cursor:pointer;\">Copy Blog</button>
            <span id=\"blog_copy_status\" style=\"margin-left:8px;color:#666;\"></span>
            <script>
              const bbtn = document.getElementById('blog_copy_btn');
              const barea = document.getElementById('blog_copy_area');
              const bstatus = document.getElementById('blog_copy_status');
              bbtn.onclick = async () => {{
                barea.select();
                barea.setSelectionRange(0, 9999999);
                try {{
                  await navigator.clipboard.writeText(barea.value);
                  bstatus.textContent = 'Copied!';
                  setTimeout(() => bstatus.textContent = '', 1500);
                }} catch (e) {{
                  try {{
                    document.execCommand('copy');
                    bstatus.textContent = 'Copied!';
                    setTimeout(() => bstatus.textContent = '', 1500);
                  }} catch (err) {{
                    bstatus.textContent = 'Copy failed';
                  }}
                }}
              }}
            </script>
            """
            st.components.v1.html(copy_blog_component, height=50)

    # Build combined copy text
    lines = [
        "Base Keyword:",
        display_keyword,
        "",
        "Suggestions:",
    ]
    lines.extend([f"- {s}" for s in display_suggestions] or ["- (none)"])

    copy_payload = "\n".join(lines)

    st.markdown("\n")

    # Copy button via small HTML component to access clipboard
    import html
    escaped = html.escape(copy_payload)
    copy_component = f"""
    <textarea id=\"kw_copy_area\" style=\"position:absolute;left:-9999px\">{escaped}</textarea>
    <button id=\"kw_copy_btn\" style=\"padding:0.5rem 0.75rem;border-radius:6px;border:1px solid #ddd;background:#f6f6f6;cursor:pointer;\">Copy All Keywords</button>
    <span id=\"kw_copy_status\" style=\"margin-left:8px;color:#666;\"></span>
    <script>
      const btn = document.getElementById('kw_copy_btn');
      const area = document.getElementById('kw_copy_area');
      const status = document.getElementById('kw_copy_status');
      btn.onclick = async () => {{
        area.select();
        area.setSelectionRange(0, 99999);
        try {{
          await navigator.clipboard.writeText(area.value);
          status.textContent = 'Copied!';
          setTimeout(() => status.textContent = '', 1500);
        }} catch (e) {{
          try {{
            document.execCommand('copy');
            status.textContent = 'Copied!';
            setTimeout(() => status.textContent = '', 1500);
          }} catch (err) {{
            status.textContent = 'Copy failed';
          }}
        }}
      }}
    </script>
    """
    st.components.v1.html(copy_component, height=50)

st.markdown("---")
with st.expander("Notes & Tips"):
    st.write(
        textwrap.dedent(
            """
            - This app uses an unofficial Google suggestions endpoint; results may vary by region and time.
            - For consistent, reliable data at scale, consider official APIs or trusted third-party providers.
            """
        )
    )

# Optional diagnostics
if 'show_debug' in locals() and show_debug:
    st.subheader("Diagnostics")
    st.write("**Suggestion fetch attempts/outcome:**")
    st.json(st.session_state.get("suggest_debug", {}))
