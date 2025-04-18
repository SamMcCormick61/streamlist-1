import streamlit as st
import difflib
import requests
from io import StringIO
import html
import re
from urllib.parse import urlparse
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer_for_filename
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound
import textwrap

# --- Page Configuration ---
st.set_page_config(
    page_title="Ultimate Diff Tool",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/streamlit/streamlit', # Example link
        'Report a bug': "https://github.com/streamlit/streamlit/issues", # Example link
        'About': """
        ## Ultimate File Comparison Tool
        Enhanced diffing with syntax highlighting, multiple inputs, advanced ignores, themes, search, filtering, and patch export.
        Built with Streamlit & Pygments.
        """
    }
)

# --- Initialize Session State ---
# Persist inputs and settings across reruns
default_options = {
    'ignore_whitespace': True, 'ignore_case': False, 'ignore_blank_lines': False,
    'hide_unchanged': False, 'num_context': 3, 'ignore_comments': False,
    'ignore_regex': '', 'theme': 'Light'
}
if 'options' not in st.session_state:
    st.session_state.options = default_options.copy()
if 'text_a' not in st.session_state:
    st.session_state.text_a = ""
if 'text_b' not in st.session_state:
    st.session_state.text_b = ""
if 'url_a' not in st.session_state:
    st.session_state.url_a = ""
if 'url_b' not in st.session_state:
    st.session_state.url_b = ""
if 'uploaded_file_a' not in st.session_state:
    st.session_state.uploaded_file_a = None
if 'uploaded_file_b' not in st.session_state:
    st.session_state.uploaded_file_b = None
if 'file_a_name' not in st.session_state:
    st.session_state.file_a_name = "Source A"
if 'file_b_name' not in st.session_state:
    st.session_state.file_b_name = "Source B"
if 'lines_a' not in st.session_state:
    st.session_state.lines_a = None
if 'lines_b' not in st.session_state:
    st.session_state.lines_b = None
if 'diff_results' not in st.session_state:
    st.session_state.diff_results = None # Store results to avoid recomputing on theme change etc.
if 'filter_changes' not in st.session_state:
    st.session_state.filter_changes = []
if 'search_term' not in st.session_state:
    st.session_state.search_term = ""

# --- Theme Handling ---
is_dark_theme = st.session_state.options.get('theme', 'Light') == 'Dark'
pygments_style = "monokai" if is_dark_theme else "default" # Pygments theme

# --- CSS Styling (Dynamic based on Theme) ---
# Base styles + theme-specific overrides
base_css = """
<style>
    /* General Layout */
    .block-container { padding-top: 2rem; padding-bottom: 2rem; } /* More spacing */
    div[data-testid="stHorizontalBlock"] > div[data-testid="stVerticalBlock"] { padding: 0 8px; }
    div[data-testid="stExpander"] div[role="button"] p { font-weight: bold; } /* Bolder expander titles */

    /* Diff View Specific */
    .diff-view-container {
        border: 1px solid; /* Color set by theme */
        border-radius: 8px;
        padding: 5px;
        height: 650px; /* Increased height */
        overflow: auto; /* Scroll both ways */
        font-family: Consolas, 'Courier New', monospace;
        font-size: 0.88em;
        line-height: 1.5;
    }
    .diff-line-wrapper { display: flex; align-items: stretch; border-bottom: 1px dotted; padding: 0; margin: 0; }
    .diff-line-wrapper:hover { /* Hover effect set by theme */ }
    .line-num {
        flex: 0 0 45px; text-align: right; padding: 1px 10px 1px 0;
        user-select: none; position: sticky; left: 0; z-index: 10;
        border-right: 1px solid; /* Color set by theme */
    }
    .line-content { flex: 1 1 auto; padding-left: 8px; white-space: pre; /* No wrap for code */ }
    .diff-placeholder .line-content { font-style: italic; }
    mark { padding: 0 2px; border-radius: 3px; font-weight: bold; } /* Highlight color set by theme */
    .diff-sep { text-align: center; font-style: italic; padding: 5px 0; margin: 5px 0; user-select: none; border-top: 1px dashed; border-bottom: 1px dashed; }

    /* Pygments Overrides within Diff */
    .diff-view-container .highlight pre { margin: 0; padding: 0; border: none; background: none; white-space: pre !important; }
    .diff-view-container .highlight { background: none; }

    /* Minimap styles */
    .minimap-container {
        border: 1px solid; /* Color set by theme */
        padding: 5px;
        height: 650px; /* Match diff view height */
        overflow-y: hidden; /* No scroll needed */
        display: flex;
        flex-direction: column;
        background-color: var(--minimap-bg-color);
    }
    .minimap-line {
        flex-grow: 1; /* Distribute height */
        min-height: 2px; /* Minimum visibility */
        max-height: 5px; /* Prevent excessive height for short files */
        opacity: 0.7;
    }
    .minimap-equal { background-color: var(--minimap-equal-color); }
    .minimap-add { background-color: var(--minimap-add-color); }
    .minimap-sub { background-color: var(--minimap-sub-color); }
    .minimap-mod { background-color: var(--minimap-mod-color); } /* For replace blocks */

    /* Action Bar */
    .action-bar {
        display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
        margin-bottom: 1rem; padding: 0.5rem; background-color: var(--secondary-background-color); border-radius: 8px;
    }
    .action-bar > div { margin-bottom: 0 !important; } /* Prevent extra margin on buttons */
</style>
"""

light_theme_css = """
<style>
    :root {
        --diff-border-color: #ccc;
        --line-num-bg: #f0f0f0;
        --line-num-color: #888;
        --line-border-color: #eee;
        --diff-equal-bg: #fff;
        --diff-add-bg: #e6ffed;
        --diff-add-num-bg: #c6f9d0;
        --diff-sub-bg: #ffeef0;
        --diff-sub-num-bg: #ffdce0;
        --diff-placeholder-bg: #fafafa;
        --diff-placeholder-color: #aaa;
        --hover-bg: #f1f1f1;
        --mark-bg: #fffbdd;
        --sep-color: #888;
        --sep-bg: #fafafa;
        --secondary-background-color: #f0f2f6;
        /* Minimap */
        --minimap-bg-color: #f8f9fa;
        --minimap-equal-color: #d4d4d4;
        --minimap-add-color: #94e4a1;
        --minimap-sub-color: #f1a7a7;
        --minimap-mod-color: #f5d58a;
    }
    .diff-view-container { border-color: var(--diff-border-color); background-color: var(--diff-equal-bg); }
    .line-num { background-color: var(--line-num-bg); color: var(--line-num-color); border-color: var(--line-border-color); }
    .diff-line-wrapper { border-bottom-color: var(--line-border-color); }
    .diff-line-wrapper:hover { background-color: var(--hover-bg); }
    .diff-add > .line-num { background-color: var(--diff-add-num-bg); }
    .diff-add > .line-content { background-color: var(--diff-add-bg); }
    .diff-sub > .line-num { background-color: var(--diff-sub-num-bg); }
    .diff-sub > .line-content { background-color: var(--diff-sub-bg); }
    .diff-placeholder > .line-num { background-color: var(--diff-placeholder-bg); }
    .diff-placeholder > .line-content { background-color: var(--diff-placeholder-bg); color: var(--diff-placeholder-color); }
    mark { background-color: var(--mark-bg); }
    .diff-sep { color: var(--sep-color); background-color: var(--sep-bg); border-color: var(--diff-border-color); }
    .minimap-container { border-color: var(--diff-border-color); }
</style>
""" + base_css + HtmlFormatter(style=pygments_style).get_style_defs('.highlight')

dark_theme_css = """
<style>
    :root {
        --diff-border-color: #555;
        --line-num-bg: #333;
        --line-num-color: #aaa;
        --line-border-color: #444;
        --diff-equal-bg: #2b2b2b;
        --diff-add-bg: #354a38;
        --diff-add-num-bg: #2a3b2d;
        --diff-sub-bg: #533134;
        --diff-sub-num-bg: #42282a;
        --diff-placeholder-bg: #383838;
        --diff-placeholder-color: #777;
        --hover-bg: #404040;
        --mark-bg: #7a7a4f;
        --sep-color: #888;
        --sep-bg: #3a3a3a;
        --secondary-background-color: #3a3a3a;
         /* Minimap */
        --minimap-bg-color: #333;
        --minimap-equal-color: #555;
        --minimap-add-color: #4b8758;
        --minimap-sub-color: #9e5c5c;
        --minimap-mod-color: #9c7f49;
    }
    .diff-view-container { border-color: var(--diff-border-color); background-color: var(--diff-equal-bg); color: #e0e0e0; }
    .line-num { background-color: var(--line-num-bg); color: var(--line-num-color); border-color: var(--line-border-color); }
    .diff-line-wrapper { border-bottom-color: var(--line-border-color); }
    .diff-line-wrapper:hover { background-color: var(--hover-bg); }
    .diff-add > .line-num { background-color: var(--diff-add-num-bg); }
    .diff-add > .line-content { background-color: var(--diff-add-bg); }
    .diff-sub > .line-num { background-color: var(--diff-sub-num-bg); }
    .diff-sub > .line-content { background-color: var(--diff-sub-bg); }
    .diff-placeholder > .line-num { background-color: var(--diff-placeholder-bg); }
    .diff-placeholder > .line-content { background-color: var(--diff-placeholder-bg); color: var(--diff-placeholder-color); }
    mark { background-color: var(--mark-bg); color: #fff; }
    .diff-sep { color: var(--sep-color); background-color: var(--sep-bg); border-color: var(--diff-border-color); }
    .minimap-container { border-color: var(--diff-border-color); }
</style>
""" + base_css + HtmlFormatter(style=pygments_style).get_style_defs('.highlight')

st.markdown(dark_theme_css if is_dark_theme else light_theme_css, unsafe_allow_html=True)

# --- Helper Functions ---

@st.cache_data(show_spinner=False)
def fetch_url_content(url):
    """Fetches content from a URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise errors for bad responses (4xx, 5xx)
        # Decode content, trying common encodings
        content = None
        try:
            content = response.content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                content = response.content.decode('latin-1')
                st.warning(f"URL content wasn't UTF-8. Decoded using latin-1.", icon="⚠️")
            except Exception as e:
                st.error(f"Failed to decode content from {url}: {e}")
                return None
        return content.splitlines()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching URL {url}: {e}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred fetching {url}: {e}")
        return None

def read_file_content_from_upload(uploaded_file):
    """Reads content from uploaded file object."""
    if uploaded_file is None:
        return None, None
    try:
        bytes_data = uploaded_file.getvalue()
        # Try decoding as UTF-8 first
        try:
            content = bytes_data.decode("utf-8")
        except UnicodeDecodeError:
            # Fallback to latin-1 if UTF-8 fails
            content = bytes_data.decode("latin-1")
            st.warning(f"File '{uploaded_file.name}' wasn't UTF-8. Decoded using latin-1.", icon="⚠️")
        return uploaded_file.name, content.splitlines()
    except Exception as e:
        st.error(f"Error reading file '{uploaded_file.name}': {e}")
        return uploaded_file.name, None

def get_lexer(filename, text_content):
    """Guesses or gets a Pygments lexer."""
    try:
        if filename and filename != "Pasted Text" and filename != "URL Content":
            return get_lexer_by_name(guess_lexer_for_filename(filename, text_content).aliases[0])
        else:
            return get_lexer_by_name(guess_lexer(text_content).aliases[0])
    except ClassNotFound:
        return get_lexer_by_name("text") # Default to plain text
    except Exception: # Catch other potential errors
        return get_lexer_by_name("text")

def highlight_syntax(code, language_lexer):
    """Applies Pygments syntax highlighting."""
    try:
        # Use the global pygments_style determined by the theme
        formatter = HtmlFormatter(style=pygments_style, nowrap=True, cssclass="highlight")
        return highlight(code, language_lexer, formatter)
    except Exception as e:
        # st.warning(f"Syntax highlighting failed: {e}", icon="🎨") # Optional warning
        return html.escape(code) # Fallback to escaped code

def preprocess_lines(lines, options):
    """Applies preprocessing options including regex ignores."""
    processed = []
    original_indices = []
    patterns = []
    if options.get('ignore_regex'):
        try:
            patterns = [re.compile(p.strip()) for p in options['ignore_regex'].splitlines() if p.strip()]
        except re.error as e:
            st.warning(f"Invalid Regex Pattern: {e}. Ignoring this pattern.", icon="⚠️")

    comment_patterns = []
    if options.get('ignore_comments'):
        # Basic comment patterns (can be expanded)
        comment_patterns = [
            re.compile(r"^\s*#.*"),       # Python/Shell comments
            re.compile(r"^\s*//.*"),      # C++/Java/JS comments
            re.compile(r"^\s*/\*.*\*/\s*$"), # Single-line C block comments
            # Multi-line C comments are harder without context, skip for simplicity
        ]

    for i, line in enumerate(lines):
        original_line = line
        # Apply regex ignores first
        ignore_this_line = False
        for pattern in patterns:
            if pattern.search(line):
                ignore_this_line = True
                break
        if ignore_this_line:
            continue # Treat as if it doesn't exist for diffing

        # Apply comment ignores
        is_comment = False
        if options.get('ignore_comments'):
            for pattern in comment_patterns:
                if pattern.match(line):
                    is_comment = True
                    break
        if is_comment:
            continue # Treat comments as if they don't exist for diffing

        # Standard preprocessing
        if options.get('ignore_blank_lines') and not line.strip():
            continue
        processed_line = line # Keep original for now unless processing applied
        if options.get('ignore_whitespace'):
            processed_line = processed_line.strip()
        if options.get('ignore_case'):
            processed_line = processed_line.lower()

        processed.append(processed_line)
        original_indices.append(i)

    return processed, original_indices

def highlight_intra_line_diffs_enhanced(line_a, line_b, lexer):
    """Highlights char diffs within syntax-highlighted lines."""
    # 1. Get char diffs using SequenceMatcher on plain text
    s = difflib.SequenceMatcher(None, line_a, line_b)
    a_markers = [False] * len(line_a)
    b_markers = [False] * len(line_b)

    for tag, i1, i2, j1, j2 in s.get_opcodes():
        if tag == 'delete':
            for i in range(i1, i2): a_markers[i] = True
        elif tag == 'insert':
            for j in range(j1, j2): b_markers[j] = True
        elif tag == 'replace':
            for i in range(i1, i2): a_markers[i] = True
            for j in range(j1, j2): b_markers[j] = True

    # 2. Apply syntax highlighting
    hl_a = highlight_syntax(line_a, lexer)
    hl_b = highlight_syntax(line_b, lexer)

    # 3. Inject <mark> tags into the HTML output (tricky part)
    # This is complex to do perfectly without breaking Pygments' spans.
    # A simpler (less accurate) approach: wrap the entire highlighted line if diffs exist.
    # A better approach (attempted here): Iterate through plain text and markers,
    # build new HTML string, inserting marks around corresponding chars in highlighted HTML.
    # NOTE: This simplified version just adds marks around *all* highlighted spans if *any* diff exists.
    # A truly robust solution would need careful HTML parsing.
    has_diff_a = any(a_markers)
    has_diff_b = any(b_markers)

    # Simplification: If a line has char diffs, we wrap the whole line content.
    # This avoids breaking pygments spans but is less granular.
    # A production tool would likely parse the pygments output and insert marks precisely.
    # For now, let's rely on the line-level background color for the main indication.
    # We *could* add marks crudely, but it might look messy with syntax colors.
    # Decision: Omit the <mark> tags for now to prioritize clean syntax highlighting.
    # The line background color (add/sub) already indicates changes.
    # If we wanted marks, we'd need to implement the complex parsing logic.

    return hl_a, hl_b # Return syntax-highlighted HTML

@st.cache_data(show_spinner="Generating Diff Views...")
def generate_ultimate_diff_views(_lines_a_orig, _lines_b_orig, options, file_a_name, file_b_name):
    """Generates three HTML views with line numbers, highlighting, syntax, context, filtering."""

    # --- Lexer Detection ---
    # Use content from the first few lines for guessing if filename is generic
    lexer_a = get_lexer(file_a_name, "\n".join(_lines_a_orig[:50]))
    lexer_b = get_lexer(file_b_name, "\n".join(_lines_b_orig[:50]))
    # Use lexer A for both for consistency in the diff view? Or allow different? Let's use A.
    lexer = lexer_a

    # --- Preprocessing ---
    processed_a, orig_indices_a = preprocess_lines(_lines_a_orig, options)
    processed_b, orig_indices_b = preprocess_lines(_lines_b_orig, options)

    if not processed_a and not processed_b:
        return [], [], [], {"added": 0, "deleted": 0, "modified": 0, "unchanged": 0} # Handle empty after processing

    s = difflib.SequenceMatcher(None, processed_a, processed_b, autojunk=False)
    opcodes = s.get_opcodes()

    view_a_lines = [] # Store tuples: (line_num, html_content, line_class)
    view_b_lines = []
    view_diff_lines = [] # Only stores lines for the diff column
    minimap_lines = [] # Store 'add', 'sub', 'mod', 'equal'
    diff_stats = {"added": 0, "deleted": 0, "modified": 0, "unchanged": 0}

    map_proc_to_orig_a = {proc_idx: orig_idx for proc_idx, orig_idx in enumerate(orig_indices_a)}
    map_proc_to_orig_b = {proc_idx: orig_idx for proc_idx, orig_idx in enumerate(orig_indices_b)}

    last_proc_a_idx, last_proc_b_idx = 0, 0

    def format_html_line_tuple(line_num, content_html, line_class):
        return (line_num, content_html if content_html.strip() else ' ', line_class)

    placeholder_content = '' # Use empty string for content
    separator_tuple = (None, '<div class="diff-sep">... unchanged lines hidden ...</div>', 'diff-sep')

    # --- Process Opcodes ---
    for tag, i1_proc, i2_proc, j1_proc, j2_proc in opcodes:
        # Derive original indices (handle potential gaps from preprocessing)
        i1_orig = map_proc_to_orig_a.get(i1_proc)
        i2_orig_prev = map_proc_to_orig_a.get(i2_proc - 1)
        i2_orig = (i2_orig_prev + 1) if i2_orig_prev is not None else i1_orig

        j1_orig = map_proc_to_orig_b.get(j1_proc)
        j2_orig_prev = map_proc_to_orig_b.get(j2_proc - 1)
        j2_orig = (j2_orig_prev + 1) if j2_orig_prev is not None else j1_orig

        lines_in_block_a_orig = _lines_a_orig[i1_orig:i2_orig] if i1_orig is not None and i2_orig is not None else []
        lines_in_block_b_orig = _lines_b_orig[j1_orig:j2_orig] if j1_orig is not None and j2_orig is not None else []

        num_lines_proc = i2_proc - i1_proc

        # --- Context Handling ---
        if options.get('hide_unchanged') and tag == 'equal':
            if num_lines_proc > options['num_context'] * 2:
                 # Context Before
                 for k in range(options['num_context']):
                     line_num_a = i1_orig + k + 1
                     line_num_b = j1_orig + k + 1
                     content_a = highlight_syntax(lines_in_block_a_orig[k], lexer)
                     content_b = highlight_syntax(lines_in_block_b_orig[k], lexer)
                     la = format_html_line_tuple(line_num_a, content_a, "diff-context")
                     lb = format_html_line_tuple(line_num_b, content_b, "diff-context")
                     view_a_lines.append(la)
                     view_b_lines.append(lb)
                     view_diff_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder"))
                     minimap_lines.append("equal")
                 view_a_lines.append(separator_tuple)
                 view_b_lines.append(separator_tuple)
                 view_diff_lines.append(separator_tuple)
                 # Context After
                 for k in range(options['num_context']):
                     idx_a = num_lines_proc - options['num_context'] + k
                     idx_b = num_lines_proc - options['num_context'] + k
                     line_num_a = i1_orig + idx_a + 1
                     line_num_b = j1_orig + idx_b + 1
                     content_a = highlight_syntax(lines_in_block_a_orig[idx_a], lexer)
                     content_b = highlight_syntax(lines_in_block_b_orig[idx_b], lexer)
                     la = format_html_line_tuple(line_num_a, content_a, "diff-context")
                     lb = format_html_line_tuple(line_num_b, content_b, "diff-context")
                     view_a_lines.append(la)
                     view_b_lines.append(lb)
                     view_diff_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder"))
                     minimap_lines.append("equal")
            else: # Show all lines in small equal block
                 for k in range(num_lines_proc):
                     line_num_a = i1_orig + k + 1
                     line_num_b = j1_orig + k + 1
                     content_a = highlight_syntax(lines_in_block_a_orig[k], lexer)
                     content_b = highlight_syntax(lines_in_block_b_orig[k], lexer)
                     la = format_html_line_tuple(line_num_a, content_a, "diff-equal")
                     lb = format_html_line_tuple(line_num_b, content_b, "diff-equal")
                     view_a_lines.append(la)
                     view_b_lines.append(lb)
                     view_diff_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder"))
                     minimap_lines.append("equal")
                 diff_stats["unchanged"] += num_lines_proc

        # --- Process Difference or All Lines (if not hiding) ---
        else:
            # Add context from preceding equal block if needed
            if options.get('hide_unchanged') and tag != 'equal' and i1_proc > last_proc_a_idx:
                prev_equal_proc_len = i1_proc - last_proc_a_idx
                if prev_equal_proc_len > options['num_context']:
                    # Determine original lines for context (handle gaps)
                    context_start_proc_a = i1_proc - options['num_context']
                    context_start_proc_b = j1_proc - options['num_context']
                    context_start_orig_a = map_proc_to_orig_a.get(context_start_proc_a)
                    context_start_orig_b = map_proc_to_orig_b.get(context_start_proc_b)

                    if context_start_orig_a is not None and context_start_orig_b is not None:
                        if not view_a_lines or view_a_lines[-1][2] != 'diff-sep':
                             view_a_lines.append(separator_tuple)
                             view_b_lines.append(separator_tuple)
                             view_diff_lines.append(separator_tuple)
                        for k in range(options['num_context']):
                             # Need to map processed index k back to original index carefully
                             current_proc_a = context_start_proc_a + k
                             current_proc_b = context_start_proc_b + k
                             current_orig_a = map_proc_to_orig_a.get(current_proc_a)
                             current_orig_b = map_proc_to_orig_b.get(current_proc_b)
                             if current_orig_a is not None and current_orig_b is not None:
                                 line_num_a = current_orig_a + 1
                                 line_num_b = current_orig_b + 1
                                 content_a = highlight_syntax(_lines_a_orig[current_orig_a], lexer)
                                 content_b = highlight_syntax(_lines_b_orig[current_orig_b], lexer)
                                 la = format_html_line_tuple(line_num_a, content_a, "diff-context")
                                 lb = format_html_line_tuple(line_num_b, content_b, "diff-context")
                                 view_a_lines.append(la)
                                 view_b_lines.append(lb)
                                 view_diff_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder"))
                                 minimap_lines.append("equal")

            # Add actual lines for this opcode tag
            if tag == 'equal':
                n_lines = i2_proc - i1_proc
                for k in range(n_lines):
                    line_num_a = i1_orig + k + 1
                    line_num_b = j1_orig + k + 1
                    content_a = highlight_syntax(lines_in_block_a_orig[k], lexer)
                    content_b = highlight_syntax(lines_in_block_b_orig[k], lexer)
                    la = format_html_line_tuple(line_num_a, content_a, "diff-equal")
                    lb = format_html_line_tuple(line_num_b, content_b, "diff-equal")
                    view_a_lines.append(la)
                    view_b_lines.append(lb)
                    view_diff_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder"))
                    minimap_lines.append("equal")
                diff_stats["unchanged"] += n_lines

            elif tag == 'delete':
                n_lines = i2_proc - i1_proc
                for k in range(n_lines):
                    line_num_a = i1_orig + k + 1
                    content_a = highlight_syntax(lines_in_block_a_orig[k], lexer)
                    line_tuple = format_html_line_tuple(line_num_a, content_a, "diff-sub")
                    view_a_lines.append(line_tuple)
                    view_b_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder"))
                    view_diff_lines.append(line_tuple)
                    minimap_lines.append("sub")
                diff_stats["deleted"] += n_lines

            elif tag == 'insert':
                n_lines = j2_proc - j1_proc
                for k in range(n_lines):
                    line_num_b = j1_orig + k + 1
                    content_b = highlight_syntax(lines_in_block_b_orig[k], lexer)
                    line_tuple = format_html_line_tuple(line_num_b, content_b, "diff-add")
                    view_a_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder"))
                    view_b_lines.append(line_tuple)
                    view_diff_lines.append(line_tuple)
                    minimap_lines.append("add")
                diff_stats["added"] += n_lines

            elif tag == 'replace':
                n_lines_a = i2_proc - i1_proc
                n_lines_b = j2_proc - j1_proc
                diff_stats["modified"] += max(n_lines_a, n_lines_b)

                for k in range(max(n_lines_a, n_lines_b)):
                    line_num_a = (i1_orig + k + 1) if k < n_lines_a and i1_orig is not None else None
                    line_num_b = (j1_orig + k + 1) if k < n_lines_b and j1_orig is not None else None
                    line_a_orig_k = lines_in_block_a_orig[k] if k < n_lines_a else ""
                    line_b_orig_k = lines_in_block_b_orig[k] if k < n_lines_b else ""

                    # Use original plain text for intra-line diff calculation if needed in future
                    # For now, just use syntax highlighting
                    content_a_h = highlight_syntax(line_a_orig_k, lexer)
                    content_b_h = highlight_syntax(line_b_orig_k, lexer)

                    if k < n_lines_a:
                        tuple_a = format_html_line_tuple(line_num_a, content_a_h, "diff-sub")
                        view_a_lines.append(tuple_a)
                        view_diff_lines.append(tuple_a)
                    else:
                        view_a_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder"))

                    if k < n_lines_b:
                        tuple_b = format_html_line_tuple(line_num_b, content_b_h, "diff-add")
                        view_b_lines.append(tuple_b)
                        # Add to diff view only if A didn't have a line here
                        if k >= n_lines_a:
                            view_diff_lines.append(tuple_b)
                    else:
                        view_b_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder"))
                        # Add placeholder to diff view only if B also has no line here
                        if k >= n_lines_a:
                             view_diff_lines.append(format_html_line_tuple(None, placeholder_content, "diff-placeholder"))

                    minimap_lines.append("mod") # Mark as modified in minimap

        last_proc_a_idx = i2_proc
        last_proc_b_idx = j2_proc

    # Filter diff view: remove placeholders unless they are separators
    final_diff_lines = [line for line in view_diff_lines if 'placeholder' not in line[2] or 'sep' in line[2]]
    if not final_diff_lines or all('sep' in line[2] for line in final_diff_lines):
         final_diff_lines = [format_html_line_tuple(None, "<i style='color: var(--line-num-color);'>Files are identical with current options.</i>", "diff-equal")]

    return view_a_lines, final_diff_lines, view_b_lines, diff_stats, minimap_lines


def generate_html_report(view_a_tuples, view_diff_tuples, view_b_tuples, stats, options, file_a_name, file_b_name):
    """Generates a standalone HTML report file content including styles."""

    def render_view_to_html(view_tuples):
        lines_html = []
        for line_num, content_html, line_class in view_tuples:
            num_display = line_num if line_num is not None else " "
            if line_class == 'diff-sep':
                 lines_html.append(content_html) # Separator is already a full div
            else:
                 lines_html.append(f'<div class="diff-line-wrapper {line_class}"><span class="line-num">{num_display}</span><span class="line-content">{content_html}</span></div>')
        return "".join(lines_html)

    html_a = f'<div class="diff-view-container">{render_view_to_html(view_a_tuples)}</div>'
    html_diff = f'<div class="diff-view-container">{render_view_to_html(view_diff_tuples)}</div>'
    html_b = f'<div class="diff-view-container">{render_view_to_html(view_b_tuples)}</div>'

    report_css = light_theme_css if options.get('theme', 'Light') == 'Light' else dark_theme_css
    # Adjust CSS for standalone report (remove Streamlit specifics if any)

    options_html = "<ul class='options-list'>" # Class defined in CSS
    opts = options # Use the provided options dict
    if opts.get('ignore_whitespace'): options_html += "<li>Ignore Leading/Trailing Whitespace</li>"
    if opts.get('ignore_case'): options_html += "<li>Ignore Case</li>"
    if opts.get('ignore_blank_lines'): options_html += "<li>Ignore Blank Lines</li>"
    if opts.get('ignore_comments'): options_html += "<li>Ignore Comments</li>"
    if opts.get('hide_unchanged'): options_html += f"<li>Hide Unchanged Lines (Context: {opts.get('num_context', 3)})</li>"
    if opts.get('ignore_regex'): options_html += f"<li>Ignore Lines Matching Regex:<pre style='margin-top: 5px; padding: 5px; border: 1px solid var(--diff-border-color); border-radius: 4px;'>{html.escape(opts['ignore_regex'])}</pre></li>"
    options_html += "</ul>"
    if not any(opts.get(k) for k in ['ignore_whitespace', 'ignore_case', 'ignore_blank_lines', 'ignore_comments', 'hide_unchanged', 'ignore_regex']):
        options_html = "<p>Default comparison options used.</p>"

    # Basic HTML structure from previous version, incorporating the new CSS and options
    report = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Comparison Report: {html.escape(file_a_name)} vs {html.escape(file_b_name)}</title>
        {report_css}
         <style> /* Report specific adjustments */
            body {{ font-family: sans-serif; margin: 20px; background-color: var(--diff-equal-bg); color: var(--line-num-color); }}
            h1, h2 {{ border-bottom: 1px solid var(--line-border-color); padding-bottom: 5px; }}
            .diff-container {{ display: flex; gap: 15px; margin-bottom: 20px; }}
            .diff-column {{ flex: 1; min-width: 0; }}
            .summary-container {{ display: flex; gap: 20px; margin-bottom: 20px; }}
            .summary-item {{ background-color: var(--secondary-background-color); border: 1px solid var(--diff-border-color) ; border-radius: 8px; padding: 15px; text-align: center; flex: 1; }}
            .summary-item strong {{ display: block; font-size: 1.5em; margin-bottom: 5px;}}
            .options-list {{ list-style: none; padding-left: 0; }}
            .options-list li::before {{ content: "✓ "; color: green; }}
            .options-list pre {{ white-space: pre-wrap; word-break: break-all; }}
        </style>
    </head>
    <body>
        <h1>Comparison Report</h1>
        <p><strong>Source A:</strong> {html.escape(file_a_name)}</p>
        <p><strong>Source B:</strong> {html.escape(file_b_name)}</p>

        <h2>Summary</h2>
        <div class="summary-container">
            <div class="summary-item"><strong>{stats['added']}</strong> Lines Added</div>
            <div class="summary-item"><strong>{stats['deleted']}</strong> Lines Deleted</div>
            <div class="summary-item"><strong>{stats['modified']}</strong> Lines Modified</div>
            <div class="summary-item"><strong>{stats['unchanged']}</strong> Lines Unchanged</div>
        </div>

        <h2>Options Used</h2>
        {options_html}

        <h2>Difference Views</h2>
        <div class="diff-container">
            <div class="diff-column"><h3>Source A</h3>{html_a}</div>
            <div class="diff-column"><h3>Differences</h3>{html_diff}</div>
            <div class="diff-column"><h3>Source B</h3>{html_b}</div>
        </div>
    </body>
    </html>
    """
    return report

def generate_patch_file(lines_a, lines_b, file_a_name, file_b_name):
    """Generates a unified diff patch file content."""
    # Note: difflib.unified_diff expects lines *with* newlines
    lines_a_nl = [line + '\n' for line in lines_a]
    lines_b_nl = [line + '\n' for line in lines_b]
    patch_lines = list(difflib.unified_diff(
        lines_a_nl,
        lines_b_nl,
        fromfile=file_a_name,
        tofile=file_b_name,
        lineterm='\n' # Ensure consistent line endings in patch
    ))
    return "".join(patch_lines)

def filter_and_render_view(view_tuples, filters, search_term):
    """Filters view tuples and renders the final HTML string."""
    filtered_tuples = []
    search_lower = search_term.lower() if search_term else None

    # Map filter names to CSS classes
    filter_map = {
        "Added": "diff-add",
        "Deleted": "diff-sub",
        "Modified": ["diff-add", "diff-sub"], # Replace creates both
        "Unchanged": "diff-equal"
    }
    active_classes = set()
    if filters:
        for f in filters:
            classes = filter_map.get(f)
            if isinstance(classes, list):
                active_classes.update(classes)
            elif classes:
                active_classes.add(classes)
    else: # No filter means show all
        active_classes = set(cls for fm in filter_map.values() for cls in (fm if isinstance(fm, list) else [fm]))
        active_classes.add("diff-context") # Always show context/placeholders if no filter


    for line_num, content_html, line_class in view_tuples:
        is_sep = line_class == 'diff-sep'
        show_line = False

        # Apply change type filter
        if is_sep or line_class == 'diff-context' or line_class == 'diff-placeholder' or any(cls in line_class for cls in active_classes):
            show_line = True


        # Apply search filter (only if line passed change filter)
        if show_line and search_lower and not is_sep:
            # Basic search: check if search term is in the content_html (case-insensitive)
            # A better search would parse out text content, but this is simpler
            if search_lower not in content_html.lower():
                show_line = False

        if show_line:
            filtered_tuples.append((line_num, content_html, line_class))


    # Render to final HTML
    lines_html = []
    for line_num, content_html, line_class in filtered_tuples:
        num_display = line_num if line_num is not None else " "
        if is_sep:
            lines_html.append(content_html)
        else:
            lines_html.append(f'<div class="diff-line-wrapper {line_class}"><span class="line-num">{num_display}</span><span class="line-content">{content_html}</span></div>')

    if not filtered_tuples or all(t[2]=='diff-sep' for t in filtered_tuples):
        return "<div class='diff-view-container'><i style='padding: 10px; color: var(--line-num-color);'>No differences match filters/search.</i></div>"

    return f'<div class="diff-view-container">{"".join(lines_html)}</div>'


# --- Sidebar ---
with st.sidebar:
    st.title("🚀 Ultimate Diff Tool")

    with st.expander("📚 Input Source", expanded=True):
        input_method = st.radio(
            "Select Input Method:",
            ("File Upload", "Text Input", "URL Fetch"),
            label_visibility="collapsed"
        )
        # Conditional Inputs based on method
        if input_method == "File Upload":
            st.session_state.uploaded_file_a = st.file_uploader("Upload File A", type=["txt", "csv", "py", "js", "html", "css", "md", "json", "yaml", "log", "ini", "java", "c", "cpp", "h"], key="upload_a")
            st.session_state.uploaded_file_b = st.file_uploader("Upload File B", type=["txt", "csv", "py", "js", "html", "css", "md", "json", "yaml", "log", "ini", "java", "c", "cpp", "h"], key="upload_b")
            if st.session_state.uploaded_file_a:
                st.session_state.file_a_name, st.session_state.lines_a = read_file_content_from_upload(st.session_state.uploaded_file_a)
            else: st.session_state.lines_a = None
            if st.session_state.uploaded_file_b:
                st.session_state.file_b_name, st.session_state.lines_b = read_file_content_from_upload(st.session_state.uploaded_file_b)
            else: st.session_state.lines_b = None

        elif input_method == "Text Input":
            st.session_state.text_a = st.text_area("Paste Text A", height=150, key="text_a_input", value=st.session_state.text_a)
            st.session_state.text_b = st.text_area("Paste Text B", height=150, key="text_b_input", value=st.session_state.text_b)
            st.session_state.file_a_name, st.session_state.file_b_name = "Pasted Text A", "Pasted Text B"
            st.session_state.lines_a = st.session_state.text_a.splitlines() if st.session_state.text_a else None
            st.session_state.lines_b = st.session_state.text_b.splitlines() if st.session_state.text_b else None

        elif input_method == "URL Fetch":
            st.session_state.url_a = st.text_input("Fetch URL A", key="url_a_input", value=st.session_state.url_a, placeholder="https://example.com/file.txt")
            st.session_state.url_b = st.text_input("Fetch URL B", key="url_b_input", value=st.session_state.url_b, placeholder="https://example.com/other_file.txt")
            lines_a_fetched, lines_b_fetched = None, None
            if st.session_state.url_a and urlparse(st.session_state.url_a).scheme in ['http', 'https']:
                 lines_a_fetched = fetch_url_content(st.session_state.url_a)
                 st.session_state.file_a_name = st.session_state.url_a.split('/')[-1] or "URL Content A"
            if st.session_state.url_b and urlparse(st.session_state.url_b).scheme in ['http', 'https']:
                 lines_b_fetched = fetch_url_content(st.session_state.url_b)
                 st.session_state.file_b_name = st.session_state.url_b.split('/')[-1] or "URL Content B"
            st.session_state.lines_a = lines_a_fetched
            st.session_state.lines_b = lines_b_fetched

    with st.expander("⚙️ Comparison Options"):
        st.session_state.options['ignore_whitespace'] = st.checkbox("Ignore Leading/Trailing Whitespace", value=st.session_state.options['ignore_whitespace'])
        st.session_state.options['ignore_case'] = st.checkbox("Ignore Case", value=st.session_state.options['ignore_case'])
        st.session_state.options['ignore_blank_lines'] = st.checkbox("Ignore Blank Lines", value=st.session_state.options['ignore_blank_lines'])
        st.session_state.options['ignore_comments'] = st.checkbox("Ignore Comments (#, //, /* */)", value=st.session_state.options['ignore_comments'])
        st.session_state.options['ignore_regex'] = st.text_area("Ignore Lines Matching Regex (one per line)", height=100, value=st.session_state.options['ignore_regex'], placeholder="e.g., ^Timestamp:.*")

    with st.expander("👁️ View Options"):
        st.session_state.options['hide_unchanged'] = st.checkbox("Hide Unchanged Lines", value=st.session_state.options['hide_unchanged'])
        st.session_state.options['num_context'] = st.number_input(
            "Context Lines", min_value=0, value=st.session_state.options['num_context'], step=1,
            disabled=not st.session_state.options['hide_unchanged'],
            help="Number of matching lines around differences when 'Hide Unchanged' is active."
        )
        current_theme = st.session_state.options['theme']
        new_theme = st.radio("Theme", ('Light', 'Dark'), index=0 if current_theme == 'Light' else 1, horizontal=True)
        if new_theme != current_theme:
             st.session_state.options['theme'] = new_theme
             st.rerun() # Rerun immediately to apply theme CSS

# --- Main App Area ---
st.title("🚀 Ultimate Diff Tool")
st.caption("Compare files, text, or URLs with syntax highlighting, advanced options, and more.")

# --- Action Bar ---
with st.container():
    st.markdown('<div class="action-bar">', unsafe_allow_html=True) # Start action bar

    # Download Buttons (conditionally enabled)
    can_compare = st.session_state.lines_a is not None and st.session_state.lines_b is not None
    report_ready = st.session_state.diff_results is not None

    if can_compare:
        st.download_button(
            label="📄 Download Patch (.diff)",
            data=generate_patch_file(st.session_state.lines_a or [], st.session_state.lines_b or [], st.session_state.file_a_name, st.session_state.file_b_name),
            file_name=f"compare_{st.session_state.file_a_name}_vs_{st.session_state.file_b_name}.diff",
            mime="text/plain",
            key="download_patch",
            help="Download differences in unified diff format."
        )
    else:
        st.button("📄 Download Patch (.diff)", disabled=True, help="Requires both inputs to be loaded.")

    if report_ready:
         view_a, view_diff, view_b, stats, _ = st.session_state.diff_results
         st.download_button(
             label="📊 Download HTML Report",
             data=generate_html_report(view_a, view_diff, view_b, stats, st.session_state.options, st.session_state.file_a_name, st.session_state.file_b_name),
             file_name=f"report_{st.session_state.file_a_name}_vs_{st.session_state.file_b_name}.html",
             mime="text/html",
             key="download_report",
             help="Download a standalone HTML report of the comparison."
         )
    else:
         st.button("📊 Download HTML Report", disabled=True, help="Comparison results needed first.")

    st.markdown("</div>", unsafe_allow_html=True) # End action bar

st.markdown("---")

# --- Comparison Logic & Display ---
if can_compare:
    # Check for large files (simple line count check)
    if len(st.session_state.lines_a) > 10000 or len(st.session_state.lines_b) > 10000:
        st.warning("One or both inputs are large (>10,000 lines). Performance might be slow.", icon="⏳")

    # --- Generate Diff ---
    # Use hash of inputs and options as part of cache key
    # Note: Caching complex objects like lexers might be tricky, focus on caching the result generation
    # This uses Streamlit's default hashing which should handle lists and dicts reasonably well.
    try:
        diff_results = generate_ultimate_diff_views(
            st.session_state.lines_a,
            st.session_state.lines_b,
            st.session_state.options,
            st.session_state.file_a_name,
            st.session_state.file_b_name
        )
        st.session_state.diff_results = diff_results # Store results
    except Exception as e:
        st.error(f"An error occurred during diff generation: {e}")
        st.exception(e) # Show traceback for debugging
        st.session_state.diff_results = None


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
        filter_col, search_col = st.columns([2,3])
        with filter_col:
            st.session_state.filter_changes = st.multiselect(
                "Filter by Change Type",
                options=["Added", "Deleted", "Modified", "Unchanged"],
                default=st.session_state.filter_changes,
                key="filter_multiselect",
                label_visibility="collapsed",
                placeholder="Filter by Change Type..."
            )
        with search_col:
            st.session_state.search_term = st.text_input(
                "Search in Results",
                value=st.session_state.search_term,
                key="search_input",
                placeholder="Search text within visible lines...",
                label_visibility="collapsed"
            )

        # --- Render Filtered Views ---
        st.subheader("↔️ Side-by-Side Comparison")

        # Prepare data for rendering
        html_a_filtered = filter_and_render_view(view_a_tuples, st.session_state.filter_changes, st.session_state.search_term)
        html_diff_filtered = filter_and_render_view(view_diff_tuples, st.session_state.filter_changes, st.session_state.search_term)
        html_b_filtered = filter_and_render_view(view_b_tuples, st.session_state.filter_changes, st.session_state.search_term)

        # Minimap HTML Generation
        minimap_html_lines = [f'<div class="minimap-line minimap-{line_type}"></div>' for line_type in minimap_data]
        minimap_html = f'<div class="minimap-container">{"".join(minimap_html_lines)}</div>'


        col1, col2, col3, col_map = st.columns([5, 5, 5, 1]) # Adjust ratios as needed
        with col1:
            st.caption(f"Source A: {html.escape(st.session_state.file_a_name)}")
            st.markdown(html_a_filtered, unsafe_allow_html=True)
        with col2:
            st.caption("Differences View")
            st.markdown(html_diff_filtered, unsafe_allow_html=True)
        with col3:
            st.caption(f"Source B: {html.escape(st.session_state.file_b_name)}")
            st.markdown(html_b_filtered, unsafe_allow_html=True)
        with col_map:
             st.caption("Map")
             st.markdown(minimap_html, unsafe_allow_html=True)


    else: # Diff generation failed
        st.error("Could not generate the comparison view.")

elif (input_method == "File Upload" and (st.session_state.uploaded_file_a or st.session_state.uploaded_file_b)) or \
     (input_method == "Text Input" and (st.session_state.text_a or st.session_state.text_b)) or \
     (input_method == "URL Fetch" and (st.session_state.url_a or st.session_state.url_b)):
    st.info("Please provide valid content/sources for both **A** and **B** to start the comparison.", icon="☝️")
else:
    st.info("Select an input method and provide content for **Source A** and **Source B**.", icon="⏳")


# --- Footer ---
st.markdown("---")
st.markdown("Ultimate Diff Tool | Powered by `Streamlit`, `difflib`, and `Pygments`")