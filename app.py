# app.py
import streamlit as st
import difflib
import requests
from io import StringIO
import html
import re
from urllib.parse import urlparse
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer, guess_lexer_for_filename
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound
import textwrap # Not strictly needed in final version but was imported before

# --- Page Configuration ---
st.set_page_config(
    page_title="Ultimate Diff Tool",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://docs.streamlit.io',
        'Report a bug': "https://github.com/streamlit/streamlit/issues",
        'About': """
        ## Ultimate File Comparison Tool
        Enhanced diffing with syntax highlighting, multiple inputs, advanced ignores, themes, search, filtering, and patch export.
        Built with Streamlit & Pygments.
        """
    }
)

# --- Initialize Session State ---
default_options = {
    'ignore_whitespace': True, 'ignore_case': False, 'ignore_blank_lines': False,
    'hide_unchanged': False, 'num_context': 3, 'ignore_comments': False,
    'ignore_regex': '', 'theme': 'Light'
}
# Initialize if keys don't exist
for key, value in default_options.items():
    if f'option_{key}' not in st.session_state:
        st.session_state[f'option_{key}'] = value

if 'input_text_a' not in st.session_state: st.session_state.input_text_a = ""
if 'input_text_b' not in st.session_state: st.session_state.input_text_b = ""
if 'input_url_a' not in st.session_state: st.session_state.input_url_a = ""
if 'input_url_b' not in st.session_state: st.session_state.input_url_b = ""
# Use different keys for upload widget state vs processed data
if 'widget_uploaded_file_a' not in st.session_state: st.session_state.widget_uploaded_file_a = None
if 'widget_uploaded_file_b' not in st.session_state: st.session_state.widget_uploaded_file_b = None
if 'processed_file_a_name' not in st.session_state: st.session_state.processed_file_a_name = "Source A"
if 'processed_file_b_name' not in st.session_state: st.session_state.processed_file_b_name = "Source B"
if 'processed_lines_a' not in st.session_state: st.session_state.processed_lines_a = None
if 'processed_lines_b' not in st.session_state: st.session_state.processed_lines_b = None
if 'diff_results' not in st.session_state: st.session_state.diff_results = None
if 'filter_changes' not in st.session_state: st.session_state.filter_changes = []
if 'search_term' not in st.session_state: st.session_state.search_term = ""
if 'input_method' not in st.session_state: st.session_state.input_method = "File Upload"


# --- Theme Handling ---
is_dark_theme = st.session_state.option_theme == 'Dark'
pygments_style = "monokai" if is_dark_theme else "default"

# --- Generate Combined CSS ---
# Base styles (without <style> tags)
base_css_rules = """
    /* General Layout */
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    div[data-testid="stHorizontalBlock"] > div[data-testid="stVerticalBlock"] { padding: 0 8px; }
    div[data-testid="stExpander"] div[role="button"] p { font-weight: bold; }

    /* Diff View Specific */
    .diff-view-container {
        border: 1px solid var(--diff-border-color);
        border-radius: 8px;
        padding: 0; /* Padding removed, handled by line content */
        height: 650px;
        overflow: auto;
        font-family: Consolas, 'Courier New', monospace;
        font-size: 0.88em;
        line-height: 1.5;
        background-color: var(--diff-equal-bg); /* Base background */
    }
    .diff-line-wrapper {
        display: flex;
        align-items: stretch; /* Make num and content same height */
        border-bottom: 1px dotted var(--line-border-color);
        margin: 0;
        padding: 0;
    }
    .diff-line-wrapper:hover { background-color: var(--hover-bg); }
    .line-num {
        flex: 0 0 45px; /* Fixed width */
        text-align: right;
        padding: 1px 10px 1px 0;
        color: var(--line-num-color);
        background-color: var(--line-num-bg);
        user-select: none;
        position: sticky; /* Keep line numbers visible */
        left: 0;
        z-index: 10;
        border-right: 1px solid var(--line-border-color);
    }
    .line-content {
        flex: 1 1 auto; /* Take remaining space */
        padding: 1px 0 1px 8px; /* Add padding inside content */
        white-space: pre; /* Preserve whitespace, prevent wrapping */
        overflow-x: auto; /* Allow horizontal scroll for long lines */
    }
    /* Placeholder styling */
    .diff-placeholder > .line-num { background-color: var(--diff-placeholder-bg); }
    .diff-placeholder > .line-content { background-color: var(--diff-placeholder-bg); color: var(--diff-placeholder-color); font-style: italic; }
    .diff-placeholder .highlight { background: none; } /* Remove pygments bg on placeholders */
    /* Add/Sub styling */
    .diff-add > .line-num { background-color: var(--diff-add-num-bg); border-color: var(--diff-add-num-border); }
    .diff-add > .line-content { background-color: var(--diff-add-bg); }
    .diff-sub > .line-num { background-color: var(--diff-sub-num-bg); border-color: var(--diff-sub-num-border); }
    .diff-sub > .line-content { background-color: var(--diff-sub-bg); text-decoration: line-through; }
    /* Context styling */
    .diff-context > .line-content { color: var(--context-color); font-style: italic; }
    /* Mark styling */
    mark { padding: 0 2px; border-radius: 3px; font-weight: bold; background-color: var(--mark-bg); color: var(--mark-color); }
    /* Separator styling */
    .diff-sep { text-align: center; font-style: italic; padding: 5px 0; margin: 0; user-select: none; border-top: 1px dashed var(--diff-border-color); border-bottom: 1px dashed var(--diff-border-color); color: var(--sep-color); background-color: var(--sep-bg); }

    /* Pygments Overrides within Diff */
    .diff-view-container .highlight pre { margin: 0 !important; padding: 0 !important; border: none !important; background: none !important; white-space: pre !important; line-height: inherit !important; font-size: inherit !important; }
    .diff-view-container .highlight { background: none !important; } /* Remove overall highlight bg */

    /* Minimap styles */
    .minimap-container {
        border: 1px solid var(--diff-border-color);
        padding: 5px;
        height: 650px;
        overflow-y: hidden;
        display: flex;
        flex-direction: column;
        background-color: var(--minimap-bg-color);
    }
    .minimap-line {
        flex-grow: 1; min-height: 2px; max-height: 5px; opacity: 0.7;
    }
    .minimap-equal { background-color: var(--minimap-equal-color); }
    .minimap-add { background-color: var(--minimap-add-color); }
    .minimap-sub { background-color: var(--minimap-sub-color); }
    .minimap-mod { background-color: var(--minimap-mod-color); }

    /* Action Bar */
    .action-bar {
        display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
        margin-bottom: 1rem; padding: 0.5rem; background-color: var(--secondary-background-color); border-radius: 8px;
    }
    .action-bar > div { margin-bottom: 0 !important; } /* Prevent extra margin on buttons/widgets */
"""

# Theme specific variables and overrides
light_theme_rules = """
    :root {
        --diff-border-color: #ccc;
        --line-num-bg: #f0f0f0;
        --line-num-color: #888;
        --line-border-color: #eee;
        --diff-equal-bg: #fff;
        --diff-add-bg: #e6ffed;
        --diff-add-num-bg: #d6f5e0;
        --diff-add-num-border: #b6eac4;
        --diff-sub-bg: #ffeef0;
        --diff-sub-num-bg: #ffe0e4;
        --diff-sub-num-border: #fdcdd2;
        --diff-placeholder-bg: #fafafa;
        --diff-placeholder-color: #aaa;
        --hover-bg: #f1f1f1;
        --mark-bg: #fffbdd;
        --mark-color: #555;
        --sep-color: #888;
        --sep-bg: #fafafa;
        --context-color: #666;
        --secondary-background-color: #f0f2f6;
        /* Minimap */
        --minimap-bg-color: #f8f9fa;
        --minimap-equal-color: #d4d4d4;
        --minimap-add-color: #94e4a1;
        --minimap-sub-color: #f1a7a7;
        --minimap-mod-color: #f5d58a;
    }
"""

dark_theme_rules = """
    :root {
        --diff-border-color: #555;
        --line-num-bg: #333;
        --line-num-color: #aaa;
        --line-border-color: #444;
        --diff-equal-bg: #2b2b2b;
        --diff-add-bg: #354a38;
        --diff-add-num-bg: #2a3b2d;
        --diff-add-num-border: #3a513e;
        --diff-sub-bg: #533134;
        --diff-sub-num-bg: #42282a;
        --diff-sub-num-border: #5c3b3e;
        --diff-placeholder-bg: #383838;
        --diff-placeholder-color: #777;
        --hover-bg: #404040;
        --mark-bg: #7a7a4f;
        --mark-color: #fff;
        --sep-color: #888;
        --sep-bg: #3a3a3a;
        --context-color: #999;
        --secondary-background-color: #3a3a3a;
         /* Minimap */
        --minimap-bg-color: #333;
        --minimap-equal-color: #555;
        --minimap-add-color: #4b8758;
        --minimap-sub-color: #9e5c5c;
        --minimap-mod-color: #9c7f49;
    }
    /* Specific overrides for dark theme */
    .diff-view-container { color: #e0e0e0; }
"""

# Pygments CSS
try:
    # Use lineos=True generates line number spans, but we handle numbers ourselves.
    # Use cssclass="highlight" to scope pygments styles.
    formatter = HtmlFormatter(style=pygments_style, cssclass="highlight", nowrap=True)
    pygments_css = formatter.get_style_defs() # Get styles for the specified class
except Exception as e:
    st.warning(f"Could not generate Pygments styles for theme '{pygments_style}': {e}")
    pygments_css = "" # Fallback to no specific Pygments styles

# --- Combine and Inject CSS ---
final_css = f"""
<style>
    /* Base Rules */
    {base_css_rules}

    /* Theme Rules */
    {dark_theme_rules if is_dark_theme else light_theme_rules}

    /* Pygments Rules (scoped to .highlight) */
    {pygments_css}
</style>
"""
st.markdown(final_css, unsafe_allow_html=True)


# --- Helper Functions --- (Mostly unchanged from previous version)

@st.cache_data(show_spinner="Fetching URL...", ttl=600) # Cache URL fetches for 10 min
def fetch_url_content(url):
    """Fetches content from a URL."""
    if not url or not urlparse(url).scheme in ['http', 'https']:
        return None, "Invalid URL"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        content = None
        encoding = response.encoding or 'utf-8' # Guess encoding or default
        try:
            content = response.content.decode(encoding)
        except (UnicodeDecodeError, LookupError): # LookupError for invalid encoding name
             try:
                 content = response.content.decode('latin-1')
                 st.toast(f"URL content wasn't {encoding}. Decoded using latin-1.", icon="⚠️")
             except Exception as e:
                 return None, f"Failed to decode content: {e}"
        file_name = url.split('/')[-1] or "URL Content"
        return (file_name, content.splitlines()), None # Return tuple (name, lines)
    except requests.exceptions.Timeout:
         return None, f"Timeout fetching {url}"
    except requests.exceptions.RequestException as e:
        return None, f"Error fetching URL: {e}"
    except Exception as e:
        return None, f"Unexpected error fetching URL: {e}"

def read_file_content_from_upload(uploaded_file):
    """Reads content from uploaded file object."""
    if uploaded_file is None:
        return None, None
    try:
        bytes_data = uploaded_file.getvalue()
        try:
            content = bytes_data.decode("utf-8")
        except UnicodeDecodeError:
            content = bytes_data.decode("latin-1")
            st.toast(f"File '{uploaded_file.name}' wasn't UTF-8. Decoded using latin-1.", icon="⚠️")
        return uploaded_file.name, content.splitlines()
    except Exception as e:
        st.error(f"Error reading file '{uploaded_file.name}': {e}")
        return uploaded_file.name, None

@st.cache_data(show_spinner=False)
def get_lexer(_filename, _text_content):
    """Guesses or gets a Pygments lexer. Caching this can speed up reruns."""
    try:
        if _filename and _filename not in ["Pasted Text A", "Pasted Text B", "URL Content A", "URL Content B"]:
             # Try guessing by filename first
            try:
                return guess_lexer_for_filename(_filename, _text_content)
            except ClassNotFound:
                pass # Fall through to guessing by content if filename fails
        # Guess by content if filename is generic or guess failed
        return guess_lexer(_text_content)
    except ClassNotFound:
         # If guessing fails entirely, default to text
        return get_lexer_by_name("text")
    except Exception: # Catch other potential errors
        return get_lexer_by_name("text")

@st.cache_data(show_spinner=False)
def highlight_syntax(_code, _language_lexer):
    """Applies Pygments syntax highlighting. Caching helps."""
    if not _code: return "" # Handle empty lines
    try:
        # Use the global formatter instance defined based on theme
        return highlight(_code, _language_lexer, formatter)
    except Exception:
        return html.escape(_code)

# --- Preprocessing Function ---
def preprocess_lines(lines, options):
    processed = []
    original_indices = []
    patterns = []
    if options.get('ignore_regex'):
        try:
            patterns = [re.compile(p.strip()) for p in options['ignore_regex'].splitlines() if p.strip()]
        except re.error as e:
            st.warning(f"Invalid Regex: {e}. Ignoring.", icon="⚠️")
    comment_patterns = []
    if options.get('ignore_comments'):
        comment_patterns = [
            re.compile(r"^\s*#.*"), re.compile(r"^\s*//.*"), re.compile(r"^\s*/\*.*\*/\s*$"),
        ]
    for i, line in enumerate(lines):
        ignore_this_line = False
        if any(pattern.search(line) for pattern in patterns): continue
        if options.get('ignore_comments') and any(pattern.match(line) for pattern in comment_patterns): continue
        if options.get('ignore_blank_lines') and not line.strip(): continue

        processed_line = line
        if options.get('ignore_whitespace'): processed_line = processed_line.strip()
        if options.get('ignore_case'): processed_line = processed_line.lower()

        processed.append(processed_line)
        original_indices.append(i)
    return processed, original_indices

# --- Core Diff Generation --- (Includes Minimap Data)
@st.cache_data(show_spinner="Generating Diff Views...", persist=True) # Persist cache across sessions if desired
def generate_ultimate_diff_views(_lines_a_orig, _lines_b_orig, _options_dict, _file_a_name, _file_b_name):
    if _lines_a_orig is None or _lines_b_orig is None:
        return [], [], [], {"added": 0, "deleted": 0, "modified": 0, "unchanged": 0}, []

    lexer_a = get_lexer(_file_a_name, "\n".join(_lines_a_orig[:50]))
    lexer_b = get_lexer(_file_b_name, "\n".join(_lines_b_orig[:50]))
    lexer = lexer_a # Use lexer A for both sides for consistency

    processed_a, orig_indices_a = preprocess_lines(_lines_a_orig, _options_dict)
    processed_b, orig_indices_b = preprocess_lines(_lines_b_orig, _options_dict)

    if not processed_a and not processed_b and (_lines_a_orig or _lines_b_orig):
        # Handle case where all lines were filtered out
        return [], [], [], {"added": 0, "deleted": 0, "modified": 0, "unchanged": 0}, []

    s = difflib.SequenceMatcher(None, processed_a, processed_b, autojunk=False)
    opcodes = s.get_opcodes()

    view_a_lines, view_b_lines, view_diff_lines = [], [], []
    minimap_lines = []
    diff_stats = {"added": 0, "deleted": 0, "modified": 0, "unchanged": 0}
    map_proc_to_orig_a = {proc_idx: orig_idx for proc_idx, orig_idx in enumerate(orig_indices_a)}
    map_proc_to_orig_b = {proc_idx: orig_idx for proc_idx, orig_idx in enumerate(orig_indices_b)}
    last_proc_a_idx, last_proc_b_idx = 0, 0

    def format_html_line_tuple(line_num, content_html, line_class):
        return (line_num, content_html if content_html.strip() else ' ', line_class)

    placeholder_content = ''
    separator_tuple = (None, '<div class="diff-sep">...</div>', 'diff-sep') # Shorter separator text

    # --- Process Opcodes --- (Logic largely similar to previous, ensure correct indexing)
    for tag, i1_proc, i2_proc, j1_proc, j2_proc in opcodes:
        # Need robust way to get original lines corresponding to processed block
        orig_lines_a = []
        orig_line_nums_a = []
        for proc_idx in range(i1_proc, i2_proc):
             orig_idx = map_proc_to_orig_a.get(proc_idx)
             if orig_idx is not None:
                 orig_lines_a.append(_lines_a_orig[orig_idx])
                 orig_line_nums_a.append(orig_idx + 1)

        orig_lines_b = []
        orig_line_nums_b = []
        for proc_idx in range(j1_proc, j2_proc):
             orig_idx = map_proc_to_orig_b.get(proc_idx)
             if orig_idx is not None:
                 orig_lines_b.append(_lines_b_orig[orig_idx])
                 orig_line_nums_b.append(orig_idx + 1)

        num_proc_lines = i2_proc - i1_proc # Length of block in terms of processed lines

        # --- Context Handling ---
        if _options_dict.get('hide_unchanged') and tag == 'equal':
            num_context = _options_dict.get('num_context', 3)
            if num_proc_lines > num_context * 2:
                 # Context Before
                 for k in range(num_context):
                     la = format_html_line_tuple(orig_line_nums_a[k], highlight_syntax(orig_lines_a[k], lexer), "diff-context")
                     lb = format_html_line_tuple(orig_line_nums_b[k], highlight_syntax(orig_lines_b[k], lexer), "diff-context")
                     view_a_lines.append(la); view_b_lines.append(lb)
                     view_diff_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder"))
                     minimap_lines.append("equal")
                 view_a_lines.append(separator_tuple); view_b_lines.append(separator_tuple); view_diff_lines.append(separator_tuple)
                 # Context After
                 for k in range(num_context):
                     idx = num_proc_lines - num_context + k
                     la = format_html_line_tuple(orig_line_nums_a[idx], highlight_syntax(orig_lines_a[idx], lexer), "diff-context")
                     lb = format_html_line_tuple(orig_line_nums_b[idx], highlight_syntax(orig_lines_b[idx], lexer), "diff-context")
                     view_a_lines.append(la); view_b_lines.append(lb)
                     view_diff_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder"))
                     minimap_lines.append("equal")
            else: # Show all lines in small equal block
                 for k in range(len(orig_lines_a)):
                     la = format_html_line_tuple(orig_line_nums_a[k], highlight_syntax(orig_lines_a[k], lexer), "diff-equal")
                     lb = format_html_line_tuple(orig_line_nums_b[k], highlight_syntax(orig_lines_b[k], lexer), "diff-equal")
                     view_a_lines.append(la); view_b_lines.append(lb)
                     view_diff_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder"))
                     minimap_lines.append("equal")
                 diff_stats["unchanged"] += len(orig_lines_a)
        else: # Process difference or show all
             # Add context from preceding equal block if needed (simplified logic)
             if _options_dict.get('hide_unchanged') and tag != 'equal' and i1_proc > last_proc_a_idx:
                prev_equal_proc_len = i1_proc - last_proc_a_idx
                num_context = _options_dict.get('num_context', 3)
                if prev_equal_proc_len > num_context: # Check if lines were skipped
                    if not view_a_lines or view_a_lines[-1][2] != 'diff-sep':
                         view_a_lines.append(separator_tuple); view_b_lines.append(separator_tuple); view_diff_lines.append(separator_tuple)
                    # Add first N lines of the *current* difference block's preceding context
                    # This requires looking back at the original data based on proc indices
                    for k in range(num_context):
                         proc_idx_a = i1_proc - num_context + k
                         proc_idx_b = j1_proc - num_context + k
                         orig_idx_a = map_proc_to_orig_a.get(proc_idx_a)
                         orig_idx_b = map_proc_to_orig_b.get(proc_idx_b)
                         if orig_idx_a is not None and orig_idx_b is not None:
                             la = format_html_line_tuple(orig_idx_a + 1, highlight_syntax(_lines_a_orig[orig_idx_a], lexer), "diff-context")
                             lb = format_html_line_tuple(orig_idx_b + 1, highlight_syntax(_lines_b_orig[orig_idx_b], lexer), "diff-context")
                             view_a_lines.append(la); view_b_lines.append(lb)
                             view_diff_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder"))
                             minimap_lines.append("equal")

             # Add actual lines for this opcode tag
             if tag == 'equal':
                 for k in range(len(orig_lines_a)):
                     la = format_html_line_tuple(orig_line_nums_a[k], highlight_syntax(orig_lines_a[k], lexer), "diff-equal")
                     lb = format_html_line_tuple(orig_line_nums_b[k], highlight_syntax(orig_lines_b[k], lexer), "diff-equal")
                     view_a_lines.append(la); view_b_lines.append(lb)
                     view_diff_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder"))
                     minimap_lines.append("equal")
                 diff_stats["unchanged"] += len(orig_lines_a)
             elif tag == 'delete':
                 for k in range(len(orig_lines_a)):
                     line_tuple = format_html_line_tuple(orig_line_nums_a[k], highlight_syntax(orig_lines_a[k], lexer), "diff-sub")
                     view_a_lines.append(line_tuple)
                     view_b_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder"))
                     view_diff_lines.append(line_tuple)
                     minimap_lines.append("sub")
                 diff_stats["deleted"] += len(orig_lines_a)
             elif tag == 'insert':
                 for k in range(len(orig_lines_b)):
                     line_tuple = format_html_line_tuple(orig_line_nums_b[k], highlight_syntax(orig_lines_b[k], lexer), "diff-add")
                     view_a_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder"))
                     view_b_lines.append(line_tuple)
                     view_diff_lines.append(line_tuple)
                     minimap_lines.append("add")
                 diff_stats["added"] += len(orig_lines_b)
             elif tag == 'replace':
                 n_a, n_b = len(orig_lines_a), len(orig_lines_b)
                 diff_stats["modified"] += max(n_a, n_b)
                 for k in range(max(n_a, n_b)):
                     if k < n_a:
                         tuple_a = format_html_line_tuple(orig_line_nums_a[k], highlight_syntax(orig_lines_a[k], lexer), "diff-sub")
                         view_a_lines.append(tuple_a); view_diff_lines.append(tuple_a)
                     else:
                         view_a_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder"))
                     if k < n_b:
                         tuple_b = format_html_line_tuple(orig_line_nums_b[k], highlight_syntax(orig_lines_b[k], lexer), "diff-add")
                         view_b_lines.append(tuple_b)
                         if k >= n_a: view_diff_lines.append(tuple_b) # Add to diff only if no corresponding A line
                     else:
                         view_b_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder"))
                         if k >= n_a: view_diff_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder")) # Placeholder in diff if both ran out
                     minimap_lines.append("mod")

        last_proc_a_idx = i2_proc
        last_proc_b_idx = j2_proc

    # Final filtering of diff view
    final_diff_lines = [line for line in view_diff_lines if 'placeholder' not in line[2] or 'sep' in line[2]]
    if not final_diff_lines or all('sep' in line[2] for line in final_diff_lines):
         final_diff_lines = [format_html_line_tuple(None, "<i style='color: var(--context-color);'>Files are identical with current options.</i>", "diff-equal")]

    return view_a_lines, final_diff_lines, view_b_lines, diff_stats, minimap_lines

# --- Report Generation Functions --- (Unchanged from previous version)
def generate_html_report(view_a_tuples, view_diff_tuples, view_b_tuples, stats, options, file_a_name, file_b_name):
    # This function renders tuples to HTML for the report download
    def render_view_to_html(view_tuples):
        lines_html = []
        for line_num, content_html, line_class in view_tuples:
            num_display = line_num if line_num is not None else " "
            if line_class == 'diff-sep':
                 lines_html.append(content_html) # Separator is already a full div
            else:
                 # Use simplified structure for report, avoid complex CSS if needed
                 lines_html.append(f'<div class="diff-line-wrapper {line_class}"><span class="line-num">{num_display}</span><span class="line-content">{content_html}</span></div>')
        return "".join(lines_html)

    html_a = f'<div class="diff-view-container">{render_view_to_html(view_a_tuples)}</div>'
    html_diff = f'<div class="diff-view-container">{render_view_to_html(view_diff_tuples)}</div>'
    html_b = f'<div class="diff-view-container">{render_view_to_html(view_b_tuples)}</div>'

    report_css = light_theme_css if options.get('theme', 'Light') == 'Light' else dark_theme_css
    # Include Pygments CSS directly in the report's style block
    report_pygments_css = HtmlFormatter(style=pygments_style, cssclass="highlight").get_style_defs()

    options_html = "<ul class='options-list'>"
    opts_ss = {key.split('_')[-1]: st.session_state[key] for key in st.session_state if key.startswith('option_')} # Get options from session state
    if opts_ss.get('ignore_whitespace'): options_html += "<li>Ignore Leading/Trailing Whitespace</li>"
    # ... (include all other options similarly) ...
    if opts_ss.get('hide_unchanged'): options_html += f"<li>Hide Unchanged Lines (Context: {opts_ss.get('num_context', 3)})</li>"
    if opts_ss.get('ignore_regex'): options_html += f"<li>Ignore Lines Matching Regex:<pre style='margin-top: 5px; padding: 5px; border: 1px solid var(--diff-border-color); border-radius: 4px; white-space: pre-wrap;'>{html.escape(opts_ss['ignore_regex'])}</pre></li>"
    options_html += "</ul>"
    if not any(opts_ss.get(k) for k in ['ignore_whitespace', 'ignore_case', 'ignore_blank_lines', 'ignore_comments', 'hide_unchanged', 'ignore_regex']):
        options_html = "<p>Default comparison options used.</p>"

    report = f"""
    <!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
    <title>Comparison: {html.escape(file_a_name)} vs {html.escape(file_b_name)}</title>
    <style>
        /* Base Rules */ {base_css_rules}
        /* Theme Rules */ {dark_theme_rules if is_dark_theme else light_theme_rules}
        /* Pygments Rules */ {report_pygments_css}
        /* Report specific adjustments */
        body {{ font-family: sans-serif; margin: 20px; background-color: var(--diff-equal-bg); color: var(--line-num-color); }}
        h1, h2 {{ border-bottom: 1px solid var(--line-border-color); padding-bottom: 5px; }}
        .diff-container {{ display: flex; gap: 15px; margin-bottom: 20px; }}
        .diff-column {{ flex: 1; min-width: 0; }}
        .summary-container {{ display: flex; gap: 20px; margin-bottom: 20px; }}
        .summary-item {{ background-color: var(--secondary-background-color); border: 1px solid var(--diff-border-color) ; border-radius: 8px; padding: 15px; text-align: center; flex: 1; }}
        .summary-item strong {{ display: block; font-size: 1.5em; margin-bottom: 5px;}}
        .options-list {{ list-style: none; padding-left: 0; }} .options-list li::before {{ content: "✓ "; color: green; }}
        .options-list pre {{ white-space: pre-wrap; word-break: break-all; }}
        /* Ensure report diff view has correct height/scroll */
        .diff-view-container {{ height: auto; max-height: 70vh; }}
    </style></head><body>
        <h1>Comparison Report</h1>
        <p><strong>Source A:</strong> {html.escape(file_a_name)}</p>
        <p><strong>Source B:</strong> {html.escape(file_b_name)}</p>
        <h2>Summary</h2><div class="summary-container">
            <div class="summary-item"><strong>{stats['added']}</strong> Added</div>
            <div class="summary-item"><strong>{stats['deleted']}</strong> Deleted</div>
            <div class="summary-item"><strong>{stats['modified']}</strong> Modified</div>
            <div class="summary-item"><strong>{stats['unchanged']}</strong> Unchanged</div>
        </div>
        <h2>Options Used</h2>{options_html}
        <h2>Difference Views</h2><div class="diff-container">
            <div class="diff-column"><h3>Source A</h3>{html_a}</div>
            <div class="diff-column"><h3>Differences</h3>{html_diff}</div>
            <div class="diff-column"><h3>Source B</h3>{html_b}</div>
        </div></body></html>
    """
    return report

def generate_patch_file(lines_a, lines_b, file_a_name, file_b_name):
    """Generates a unified diff patch file content."""
    if lines_a is None or lines_b is None: return ""
    lines_a_nl = [line + '\n' for line in lines_a]
    lines_b_nl = [line + '\n' for line in lines_b]
    patch_lines = list(difflib.unified_diff(
        lines_a_nl, lines_b_nl, fromfile=file_a_name, tofile=file_b_name, lineterm='\n'
    ))
    return "".join(patch_lines)

# --- Filtering and Rendering Function ---
def filter_and_render_view(view_tuples, filters, search_term):
    """Filters view tuples and renders the final HTML string."""
    if not view_tuples: return "<div class='diff-view-container'></div>" # Handle empty input

    filtered_tuples = []
    search_lower = search_term.lower() if search_term else None
    filter_map = { "Added": "diff-add", "Deleted": "diff-sub", "Modified": "diff-", "Unchanged": "diff-equal" } # Modified matches add/sub
    active_classes = set()
    show_all = not filters
    if filters:
        for f in filters:
             cls = filter_map.get(f)
             if cls == "diff-": active_classes.update(["diff-add", "diff-sub"]) # Special case for modified
             elif cls: active_classes.add(cls)

    for line_num, content_html, line_class in view_tuples:
        is_sep = line_class == 'diff-sep'
        is_context = line_class == 'diff-context'
        is_placeholder = line_class == 'diff-placeholder'
        show_line = False

        if show_all or is_sep or is_context: # Always show separators and context lines if showing diffs
            show_line = True
        elif any(cls in line_class for cls in active_classes):
            show_line = True

        if show_line and search_lower and not is_sep:
             # Basic search: check if search term is in the content_html (case-insensitive)
            # More robust search would strip HTML tags first
            temp_div = f"<div>{content_html}</div>" # Wrap to handle fragments
            # A simple approximation:
            import re
            text_content = re.sub('<[^>]*>', '', content_html) # Strip tags crudely
            if search_lower not in text_content.lower():
                show_line = False

        if show_line:
            filtered_tuples.append((line_num, content_html, line_class))

    # Render to final HTML
    lines_html = []
    for line_num, content_html, line_class in filtered_tuples:
        num_display = line_num if line_num is not None else " "
        if line_class == 'diff-sep':
            lines_html.append(content_html)
        else:
            # Note: content_html ALREADY contains the <pre> block from Pygments
            lines_html.append(f'<div class="diff-line-wrapper {line_class}"><span class="line-num">{num_display}</span><div class="line-content">{content_html}</div></div>')

    if not filtered_tuples or all(t[2]=='diff-sep' for t in filtered_tuples):
        return "<div class='diff-view-container'><i style='display: block; padding: 10px; color: var(--context-color);'>No differences match filters/search.</i></div>"

    return f'<div class="diff-view-container">{"".join(lines_html)}</div>'


# --- UI Layout ---

# --- Sidebar ---
with st.sidebar:
    st.title("🚀 Ultimate Diff")

    with st.expander("📚 Input Source", expanded=True):
        st.session_state.input_method = st.radio(
            "Select Input Method:",
            ("File Upload", "Text Input", "URL Fetch"),
            key="input_method_radio",
            index=["File Upload", "Text Input", "URL Fetch"].index(st.session_state.input_method) # Preserve selection
        )
        input_method = st.session_state.input_method # Get current value

        # Conditional Inputs
        if input_method == "File Upload":
            # Use different keys for widget to avoid conflict with processed data
            uploaded_a = st.file_uploader("Upload Source A", type=["txt", "csv", "py", "js", "html", "css", "md", "json", "yaml", "log", "ini", "java", "c", "cpp", "h"], key="widget_upload_a")
            uploaded_b = st.file_uploader("Upload Source B", type=["txt", "csv", "py", "js", "html", "css", "md", "json", "yaml", "log", "ini", "java", "c", "cpp", "h"], key="widget_upload_b")
            # Process uploads immediately if they change
            if uploaded_a and uploaded_a != st.session_state.get('processed_upload_a_ref'):
                st.session_state.processed_file_a_name, st.session_state.processed_lines_a = read_file_content_from_upload(uploaded_a)
                st.session_state.processed_upload_a_ref = uploaded_a # Store ref to check for change
                st.session_state.diff_results = None # Reset results on new input
            elif not uploaded_a and st.session_state.get('processed_upload_a_ref'):
                st.session_state.processed_lines_a = None
                st.session_state.processed_upload_a_ref = None
                st.session_state.diff_results = None

            if uploaded_b and uploaded_b != st.session_state.get('processed_upload_b_ref'):
                st.session_state.processed_file_b_name, st.session_state.processed_lines_b = read_file_content_from_upload(uploaded_b)
                st.session_state.processed_upload_b_ref = uploaded_b
                st.session_state.diff_results = None
            elif not uploaded_b and st.session_state.get('processed_upload_b_ref'):
                st.session_state.processed_lines_b = None
                st.session_state.processed_upload_b_ref = None
                st.session_state.diff_results = None


        elif input_method == "Text Input":
            text_a = st.text_area("Paste Text A", height=150, key="input_text_a", value=st.session_state.input_text_a)
            text_b = st.text_area("Paste Text B", height=150, key="input_text_b", value=st.session_state.input_text_b)
            if text_a != st.session_state.input_text_a or text_b != st.session_state.input_text_b:
                 st.session_state.processed_lines_a = text_a.splitlines() if text_a else None
                 st.session_state.processed_lines_b = text_b.splitlines() if text_b else None
                 st.session_state.processed_file_a_name, st.session_state.processed_file_b_name = "Pasted Text A", "Pasted Text B"
                 st.session_state.diff_results = None # Reset results

        elif input_method == "URL Fetch":
            url_a = st.text_input("Fetch URL A", key="input_url_a", value=st.session_state.input_url_a, placeholder="https://example.com/file.txt")
            url_b = st.text_input("Fetch URL B", key="input_url_b", value=st.session_state.input_url_b, placeholder="https://example.com/other_file.txt")
            # Use a button to trigger fetch to avoid fetching on every keystroke
            if st.button("Fetch URLs"):
                 result_a, error_a = fetch_url_content(url_a)
                 result_b, error_b = fetch_url_content(url_b)
                 if error_a: st.error(f"URL A Error: {error_a}")
                 if error_b: st.error(f"URL B Error: {error_b}")

                 st.session_state.processed_file_a_name = result_a[0] if result_a else "URL A Error"
                 st.session_state.processed_lines_a = result_a[1] if result_a else None
                 st.session_state.processed_file_b_name = result_b[0] if result_b else "URL B Error"
                 st.session_state.processed_lines_b = result_b[1] if result_b else None
                 st.session_state.diff_results = None # Reset results

    # --- Options Expanders ---
    with st.expander("⚙️ Comparison Options"):
        st.checkbox("Ignore Leading/Trailing Whitespace", key="option_ignore_whitespace")
        st.checkbox("Ignore Case", key="option_ignore_case")
        st.checkbox("Ignore Blank Lines", key="option_ignore_blank_lines")
        st.checkbox("Ignore Comments (#, //, /* */)", key="option_ignore_comments")
        st.text_area("Ignore Lines Matching Regex (one per line)", height=100, key="option_ignore_regex", placeholder="e.g., ^Timestamp:.*")

    with st.expander("👁️ View Options"):
        st.checkbox("Hide Unchanged Lines", key="option_hide_unchanged")
        st.number_input(
            "Context Lines", min_value=0, step=1, key="option_num_context",
            disabled=not st.session_state.option_hide_unchanged,
            help="Lines around differences when 'Hide Unchanged' is active."
        )
        # Theme selection triggers immediate rerun via widget state change
        st.radio("Theme", ('Light', 'Dark'), key="option_theme", horizontal=True)

# --- Main Area ---
st.title("🚀 Ultimate Diff Tool")
st.caption("Compare files, text, or URLs with syntax highlighting, advanced options, and more.")

# --- Action Bar ---
with st.container():
    st.markdown('<div class="action-bar">', unsafe_allow_html=True)
    can_compare = st.session_state.processed_lines_a is not None and st.session_state.processed_lines_b is not None
    report_ready = st.session_state.diff_results is not None

    # Pass necessary data directly to download button generation
    patch_data = generate_patch_file(
        st.session_state.processed_lines_a, st.session_state.processed_lines_b,
        st.session_state.processed_file_a_name, st.session_state.processed_file_b_name
    ) if can_compare else ""

    st.download_button(
        label="📄 Patch (.diff)", data=patch_data,
        file_name=f"compare_{st.session_state.processed_file_a_name}_vs_{st.session_state.processed_file_b_name}.diff",
        mime="text/plain", key="download_patch", help="Download differences in unified diff format.",
        disabled=not can_compare
    )

    # Prepare report data only if needed and possible
    report_html_data = ""
    if report_ready:
        view_a, view_diff, view_b, stats, _ = st.session_state.diff_results
        current_options = {key.split('_')[-1]: st.session_state[key] for key in st.session_state if key.startswith('option_')}
        report_html_data = generate_html_report(
            view_a, view_diff, view_b, stats, current_options,
            st.session_state.processed_file_a_name, st.session_state.processed_file_b_name
        )

    st.download_button(
        label="📊 HTML Report", data=report_html_data,
        file_name=f"report_{st.session_state.processed_file_a_name}_vs_{st.session_state.processed_file_b_name}.html",
        mime="text/html", key="download_report", help="Download a standalone HTML report.",
        disabled=not report_ready
    )
    st.markdown("</div>", unsafe_allow_html=True) # End action bar

st.markdown("---")

# --- Comparison Logic & Display ---
if can_compare:
    # --- Generate Diff if needed ---
    # Compare current options hash vs stored hash to see if recompute needed
    current_options = {key.split('_')[-1]: st.session_state[key] for key in st.session_state if key.startswith('option_')}
    options_changed = current_options != st.session_state.get('last_run_options')

    if st.session_state.diff_results is None or options_changed:
        if len(st.session_state.processed_lines_a) > 15000 or len(st.session_state.processed_lines_b) > 15000:
            st.warning("Inputs >15,000 lines. Diff generation might be slow or unstable.", icon="⏳")
        try:
            diff_results = generate_ultimate_diff_views(
                st.session_state.processed_lines_a, st.session_state.processed_lines_b,
                current_options, st.session_state.processed_file_a_name, st.session_state.processed_file_b_name
            )
            st.session_state.diff_results = diff_results
            st.session_state.last_run_options = current_options.copy() # Store options hash
        except Exception as e:
            st.error(f"Error during diff generation: {e}")
            st.exception(e)
            st.session_state.diff_results = None

    # --- Display Results if available ---
    if st.session_state.diff_results:
        view_a_tuples, view_diff_tuples, view_b_tuples, diff_stats, minimap_data = st.session_state.diff_results

        # --- Display Summary Stats ---
        st.subheader("📊 Comparison Summary")
        stat_cols = st.columns(4)
        stat_cols[0].metric("Lines Added", f"{diff_stats['added']}", delta=diff_stats['added'] if diff_stats['added'] > 0 else None)
        stat_cols[1].metric("Lines Deleted", f"{diff_stats['deleted']}", delta=-diff_stats['deleted'] if diff_stats['deleted'] > 0 else None, delta_color="inverse")
        stat_cols[2].metric("Lines Modified", f"{diff_stats['modified']}")
        stat_cols[3].metric("Lines Unchanged", f"{diff_stats['unchanged']}")
        st.markdown("---")

        # --- Filtering and Search Bar ---
        st.subheader("🔍 Filter & Search Results")
        filter_col, search_col = st.columns([2, 3])
        with filter_col:
             st.multiselect("Filter by Change Type", ["Added", "Deleted", "Modified", "Unchanged"],
                           key="filter_changes", placeholder="Filter by Change Type...", label_visibility="collapsed")
        with search_col:
             st.text_input("Search in Results", key="search_term", placeholder="Search text...", label_visibility="collapsed")

        # --- Render Filtered Views ---
        st.subheader("↔️ Side-by-Side Comparison")
        html_a_filtered = filter_and_render_view(view_a_tuples, st.session_state.filter_changes, st.session_state.search_term)
        html_diff_filtered = filter_and_render_view(view_diff_tuples, st.session_state.filter_changes, st.session_state.search_term)
        html_b_filtered = filter_and_render_view(view_b_tuples, st.session_state.filter_changes, st.session_state.search_term)

        # --- Minimap ---
        minimap_html_lines = [f'<div class="minimap-line minimap-{line_type}"></div>' for line_type in minimap_data]
        minimap_html = f'<div class="minimap-container">{"".join(minimap_html_lines)}</div>'

        # --- Display Columns ---
        col1, col2, col3, col_map = st.columns([10, 10, 10, 1]) # Give minimap less space
        with col1:
            st.caption(f"Source A: {html.escape(st.session_state.processed_file_a_name)}")
            st.markdown(html_a_filtered, unsafe_allow_html=True)
        with col2:
            st.caption("Differences View")
            st.markdown(html_diff_filtered, unsafe_allow_html=True)
        with col3:
            st.caption(f"Source B: {html.escape(st.session_state.processed_file_b_name)}")
            st.markdown(html_b_filtered, unsafe_allow_html=True)
        with col_map:
             st.caption("Map")
             st.markdown(minimap_html, unsafe_allow_html=True)

    elif st.session_state.diff_results == []: # Handle empty results after processing
        st.info("Inputs resulted in no differences after applying ignore options.", icon="✅")

else: # Inputs not ready
    st.info("Select an input method and provide content for **Source A** and **Source B** to begin.", icon="⏳")

# --- Footer ---
st.markdown("---")
st.markdown("Ultimate Diff Tool | Powered by `Streamlit`, `difflib`, and `Pygments`")