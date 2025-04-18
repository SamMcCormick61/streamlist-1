import streamlit as st
import difflib
from io import StringIO
import html
import textwrap

# --- Page Configuration ---
st.set_page_config(
    page_title="Enhanced File Compare",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "A powerful file comparison tool built with Streamlit."
    }
)

# --- Advanced CSS Styling ---
st.markdown("""
<style>
    /* Main container for each view */
    .diff-view-container {
        border: 1px solid #ccc;
        border-radius: 8px;
        padding: 5px;
        background-color: #f8f9fa;
        height: 600px; /* Fixed height */
        overflow-y: scroll; /* Enable vertical scrolling */
        font-family: Consolas, 'Courier New', monospace;
        font-size: 0.85em; /* Slightly smaller font */
        line-height: 1.5; /* Improve line spacing */
    }

    /* Flex container for line number + content */
    .diff-line-wrapper {
        display: flex;
        align-items: flex-start; /* Align items at the top */
        border-bottom: 1px dotted #eee; /* Subtle line separator */
        padding: 1px 0;
    }
    .diff-line-wrapper:hover {
        background-color: #f1f1f1; /* Subtle hover effect */
    }

    /* Line number styling */
    .line-num {
        flex: 0 0 40px; /* Fixed width, no grow/shrink */
        text-align: right;
        padding-right: 10px;
        color: #888;
        background-color: #f0f0f0; /* Different background for line numbers */
        user-select: none; /* Prevent selecting line numbers */
        position: sticky; /* Keep line numbers visible? - Might need JS */
        left: 0; /* For potential future sticky positioning */
        z-index: 1;
    }

    /* Line content styling */
    .line-content {
        flex: 1 1 auto; /* Allow growing/shrinking */
        white-space: pre; /* Preserve whitespace, but allow wrapping below */
        word-wrap: break-word; /* Break long words if needed */
        padding-left: 5px;
    }

    /* Specific line type styling */
    .diff-equal .line-content { color: #333; }
    .diff-context .line-content { color: #666; font-style: italic; } /* Context lines */
    .diff-placeholder .line-content { color: #aaa; background-color: #fafafa; }
    .diff-add .line-content { background-color: #e6ffed; color: #22863a; }
    .diff-sub .line-content { background-color: #ffeef0; color: #b31d28; text-decoration: line-through; }

    /* Intra-line changes */
    mark {
        background-color: #fffbdd; /* Yellowish highlight for within-line changes */
        padding: 0 2px;
        border-radius: 3px;
        font-weight: bold;
    }
    .diff-sub mark { background-color: #ffdce0; } /* Adjust mark color inside deleted lines */
    .diff-add mark { background-color: #c6f9d0; } /* Adjust mark color inside added lines */

    /* Separator for hidden lines */
    .diff-sep {
        text-align: center;
        color: #888;
        font-style: italic;
        background-color: #fafafa;
        border-top: 1px dashed #ccc;
        border-bottom: 1px dashed #ccc;
        padding: 5px 0;
        margin: 5px 0;
        user-select: none;
    }

    /* Style for the main columns */
    div[data-testid="stHorizontalBlock"] > div[data-testid="stVerticalBlock"] {
        padding: 0 10px; /* Add some horizontal padding between columns */
    }

    /* Center align metrics */
     div[data-testid="stMetric"] {
        text-align: center;
        background-color: #f0f2f6;
        border-radius: 8px;
        padding: 10px;
    }
     div[data-testid="stMetric"] > div { /* Target the value div */
        justify-content: center;
     }
     div[data-testid="stMetric"] label { /* Target the label */
        justify-content: center;
     }

</style>
""", unsafe_allow_html=True)


# --- Helper Functions ---

def read_file_content(uploaded_file):
    """Reads content from uploaded file, handling potential decoding errors."""
    if uploaded_file is None:
        return None, None
    try:
        stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
        content = stringio.read()
        lines = content.splitlines()
        return content, lines
    except UnicodeDecodeError:
        try:
            stringio = StringIO(uploaded_file.getvalue().decode("latin-1"))
            content = stringio.read()
            lines = content.splitlines()
            st.warning(f"File '{uploaded_file.name}' wasn't UTF-8. Decoded using latin-1.", icon="⚠️")
            return content, lines
        except Exception as e:
            st.error(f"Error reading file '{uploaded_file.name}': {e}")
            return None, None
    except Exception as e:
        st.error(f"Error processing file '{uploaded_file.name}': {e}")
        return None, None

def preprocess_lines(lines, ignore_whitespace, ignore_case, ignore_blank_lines):
    """Applies preprocessing options to lines."""
    processed = []
    original_indices = [] # Keep track of original line index for mapping back
    for i, line in enumerate(lines):
        original_line = line # Store original before processing
        if ignore_blank_lines and not line.strip():
            continue # Skip blank lines if option is set
        if ignore_whitespace:
            line = line.strip()
        if ignore_case:
            line = line.lower()
        processed.append(line)
        original_indices.append(i) # Store the original index corresponding to this processed line
    return processed, original_indices

def highlight_intra_line_diffs(line_a, line_b):
    """Uses ndiff to find character-level diffs and inserts <mark> tags."""
    if not line_a or not line_b: # Handle empty lines
        return html.escape(line_a), html.escape(line_b)

    # Use ndiff to get detailed character-level diffs with hints
    s = difflib.SequenceMatcher(None, line_a, line_b)
    highlighted_a = ""
    highlighted_b = ""

    for tag, i1, i2, j1, j2 in s.get_opcodes():
        if tag == 'equal':
            highlighted_a += html.escape(line_a[i1:i2])
            highlighted_b += html.escape(line_b[j1:j2])
        elif tag == 'delete':
            highlighted_a += f"<mark>{html.escape(line_a[i1:i2])}</mark>"
        elif tag == 'insert':
            highlighted_b += f"<mark>{html.escape(line_b[j1:j2])}</mark>"
        elif tag == 'replace':
            highlighted_a += f"<mark>{html.escape(line_a[i1:i2])}</mark>"
            highlighted_b += f"<mark>{html.escape(line_b[j1:j2])}</mark>"

    # Replace literal spaces with   ONLY outside tags to preserve spacing
    # This is tricky - a simpler approach for now is rely on white-space: pre
    # highlighted_a = highlighted_a.replace(' ', ' ')
    # highlighted_b = highlighted_b.replace(' ', ' ')

    return highlighted_a, highlighted_b

def generate_enhanced_diff_views(lines_a_orig, lines_b_orig, options):
    """
    Generates three HTML views with line numbers, highlighting, and context handling.
    """
    processed_a, orig_indices_a = preprocess_lines(
        lines_a_orig, options['ignore_whitespace'], options['ignore_case'], options['ignore_blank_lines']
    )
    processed_b, orig_indices_b = preprocess_lines(
        lines_b_orig, options['ignore_whitespace'], options['ignore_case'], options['ignore_blank_lines']
    )

    s = difflib.SequenceMatcher(None, processed_a, processed_b, autojunk=False)
    opcodes = s.get_opcodes()

    view_a_html = []
    view_b_html = []
    view_diff_html = []
    diff_stats = {"added": 0, "deleted": 0, "modified": 0, "unchanged": 0}

    # Mapping from processed index back to original line index
    map_proc_to_orig_a = {proc_idx: orig_idx for proc_idx, orig_idx in enumerate(orig_indices_a)}
    map_proc_to_orig_b = {proc_idx: orig_idx for proc_idx, orig_idx in enumerate(orig_indices_b)}

    last_proc_a_idx, last_proc_b_idx = 0, 0

    def format_html_line(line_num, content_html, line_class):
        # If content_html is empty (placeholder), provide a non-breaking space
        display_content = content_html if content_html.strip() else ' '
        return f'<div class="diff-line-wrapper {line_class}"><span class="line-num">{line_num if line_num is not None else " "}</span><span class="line-content">{display_content}</span></div>'

    placeholder_html = '' # Use empty string, format_html_line handles display
    separator_html = '<div class="diff-sep">... unchanged lines hidden ...</div>'

    for tag, i1_proc, i2_proc, j1_proc, j2_proc in opcodes:
        # Get corresponding original line indices
        i1_orig = map_proc_to_orig_a.get(i1_proc, None) if i1_proc < len(map_proc_to_orig_a) else None
        i2_orig_limit = map_proc_to_orig_a.get(i2_proc -1, None) if i2_proc > i1_proc else i1_orig
        i2_orig = (i2_orig_limit + 1) if i2_orig_limit is not None else i1_orig

        j1_orig = map_proc_to_orig_b.get(j1_proc, None) if j1_proc < len(map_proc_to_orig_b) else None
        j2_orig_limit = map_proc_to_orig_b.get(j2_proc -1, None) if j2_proc > j1_proc else j1_orig
        j2_orig = (j2_orig_limit + 1) if j2_orig_limit is not None else j1_orig

        # Fetch original lines based on derived original indices
        lines_in_block_a_orig = lines_a_orig[i1_orig:i2_orig] if i1_orig is not None and i2_orig is not None else []
        lines_in_block_b_orig = lines_b_orig[j1_orig:j2_orig] if j1_orig is not None and j2_orig is not None else []

        if options['hide_unchanged'] and tag == 'equal':
            n_lines = i2_proc - i1_proc
            if n_lines > options['num_context'] * 2:
                 # Show context before gap
                 for k in range(options['num_context']):
                     line_num_a = i1_orig + k + 1
                     line_num_b = j1_orig + k + 1
                     content_a = html.escape(lines_in_block_a_orig[k])
                     content_b = html.escape(lines_in_block_b_orig[k])
                     view_a_html.append(format_html_line(line_num_a, content_a, "diff-context"))
                     view_b_html.append(format_html_line(line_num_b, content_b, "diff-context"))
                     view_diff_html.append(format_html_line(None, placeholder_html, "diff-placeholder"))
                 view_a_html.append(separator_html)
                 view_b_html.append(separator_html)
                 view_diff_html.append(separator_html)
                 # Show context after gap
                 for k in range(options['num_context']):
                     idx_a = n_lines - options['num_context'] + k
                     idx_b = n_lines - options['num_context'] + k
                     line_num_a = i1_orig + idx_a + 1
                     line_num_b = j1_orig + idx_b + 1
                     content_a = html.escape(lines_in_block_a_orig[idx_a])
                     content_b = html.escape(lines_in_block_b_orig[idx_b])
                     view_a_html.append(format_html_line(line_num_a, content_a, "diff-context"))
                     view_b_html.append(format_html_line(line_num_b, content_b, "diff-context"))
                     view_diff_html.append(format_html_line(None, placeholder_html, "diff-placeholder"))
            else: # Small equal block, show all
                 for k in range(n_lines):
                     line_num_a = i1_orig + k + 1
                     line_num_b = j1_orig + k + 1
                     content_a = html.escape(lines_in_block_a_orig[k])
                     content_b = html.escape(lines_in_block_b_orig[k])
                     view_a_html.append(format_html_line(line_num_a, content_a, "diff-equal"))
                     view_b_html.append(format_html_line(line_num_b, content_b, "diff-equal"))
                     view_diff_html.append(format_html_line(None, placeholder_html, "diff-placeholder"))
                 diff_stats["unchanged"] += n_lines

        else: # Process difference or show all if not hiding unchanged
            # Add context from preceding equal block if needed
            if options['hide_unchanged'] and tag != 'equal' and i1_proc > last_proc_a_idx:
                prev_equal_proc_len = i1_proc - last_proc_a_idx
                if prev_equal_proc_len > options['num_context']:
                    # Determine original lines for context
                    context_start_a_orig = map_proc_to_orig_a.get(i1_proc - options['num_context'])
                    context_start_b_orig = map_proc_to_orig_b.get(j1_proc - options['num_context'])
                    if context_start_a_orig is not None and context_start_b_orig is not None:
                        if len(view_a_html) > 0 and view_a_html[-1] != separator_html:
                             view_a_html.append(separator_html)
                             view_b_html.append(separator_html)
                             view_diff_html.append(separator_html)
                        for k in range(options['num_context']):
                             line_num_a = context_start_a_orig + k + 1
                             line_num_b = context_start_b_orig + k + 1
                             content_a = html.escape(lines_a_orig[context_start_a_orig + k])
                             content_b = html.escape(lines_b_orig[context_start_b_orig + k])
                             view_a_html.append(format_html_line(line_num_a, content_a, "diff-context"))
                             view_b_html.append(format_html_line(line_num_b, content_b, "diff-context"))
                             view_diff_html.append(format_html_line(None, placeholder_html, "diff-placeholder"))

            # Add actual lines for this opcode tag
            if tag == 'equal':
                n_lines = i2_proc - i1_proc
                for k in range(n_lines):
                    line_num_a = i1_orig + k + 1
                    line_num_b = j1_orig + k + 1
                    content_a = html.escape(lines_in_block_a_orig[k])
                    content_b = html.escape(lines_in_block_b_orig[k])
                    view_a_html.append(format_html_line(line_num_a, content_a, "diff-equal"))
                    view_b_html.append(format_html_line(line_num_b, content_b, "diff-equal"))
                    view_diff_html.append(format_html_line(None, placeholder_html, "diff-placeholder"))
                diff_stats["unchanged"] += n_lines

            elif tag == 'delete':
                n_lines = i2_proc - i1_proc
                for k in range(n_lines):
                    line_num_a = i1_orig + k + 1
                    content_a = html.escape(lines_in_block_a_orig[k])
                    formatted_line = format_html_line(line_num_a, content_a, "diff-sub")
                    view_a_html.append(formatted_line)
                    view_b_html.append(format_html_line(None, placeholder_html, "diff-placeholder"))
                    view_diff_html.append(formatted_line)
                diff_stats["deleted"] += n_lines

            elif tag == 'insert':
                n_lines = j2_proc - j1_proc
                for k in range(n_lines):
                    line_num_b = j1_orig + k + 1
                    content_b = html.escape(lines_in_block_b_orig[k])
                    formatted_line = format_html_line(line_num_b, content_b, "diff-add")
                    view_a_html.append(format_html_line(None, placeholder_html, "diff-placeholder"))
                    view_b_html.append(formatted_line)
                    view_diff_html.append(formatted_line)
                diff_stats["added"] += n_lines

            elif tag == 'replace':
                n_lines_a = i2_proc - i1_proc
                n_lines_b = j2_proc - j1_proc
                diff_stats["modified"] += max(n_lines_a, n_lines_b) # Count based on longer block

                for k in range(max(n_lines_a, n_lines_b)):
                    line_num_a = (i1_orig + k + 1) if k < n_lines_a else None
                    line_num_b = (j1_orig + k + 1) if k < n_lines_b else None
                    line_a_orig_k = lines_in_block_a_orig[k] if k < n_lines_a else ""
                    line_b_orig_k = lines_in_block_b_orig[k] if k < n_lines_b else ""

                    # Intra-line diff highlighting
                    content_a_h, content_b_h = highlight_intra_line_diffs(line_a_orig_k, line_b_orig_k)

                    # Format lines for each view
                    if k < n_lines_a:
                        formatted_a = format_html_line(line_num_a, content_a_h, "diff-sub")
                        view_a_html.append(formatted_a)
                        view_diff_html.append(formatted_a)
                    else:
                        view_a_html.append(format_html_line(None, placeholder_html, "diff-placeholder"))
                        # Add placeholder to diff view only if B also has no line here
                        if k >= n_lines_b:
                            view_diff_html.append(format_html_line(None, placeholder_html, "diff-placeholder"))


                    if k < n_lines_b:
                        formatted_b = format_html_line(line_num_b, content_b_h, "diff-add")
                        view_b_html.append(formatted_b)
                        # Add to diff view only if A didn't have a line here (avoids double entries in diff)
                        if k >= n_lines_a:
                            view_diff_html.append(formatted_b)
                    else:
                        view_b_html.append(format_html_line(None, placeholder_html, "diff-placeholder"))


        last_proc_a_idx = i2_proc
        last_proc_b_idx = j2_proc

    # Filter diff view: remove placeholders unless they are separators
    final_diff_html = [line for line in view_diff_html if 'diff-placeholder' not in line or 'diff-sep' in line]
    if not final_diff_html or all('diff-sep' in line for line in final_diff_html):
        final_diff_html = [format_html_line(None, "<span style='color:#666; font-style:italic;'>Files are identical with current options.</span>", "diff-equal")]


    # Wrap final HTML in containers
    html_a = f'<div class="diff-view-container">{"".join(view_a_html)}</div>'
    html_diff = f'<div class="diff-view-container">{"".join(final_diff_html)}</div>'
    html_b = f'<div class="diff-view-container">{"".join(view_b_html)}</div>'

    return html_a, html_diff, html_b, diff_stats


def generate_html_report(html_a, html_diff, html_b, stats, options, file_a_name, file_b_name):
    """Generates a standalone HTML report file content."""
    css = """
    <style>
        body { font-family: sans-serif; margin: 20px; }
        h1, h2 { border-bottom: 1px solid #eee; padding-bottom: 5px; }
        .diff-container { display: flex; gap: 15px; margin-bottom: 20px;}
        .diff-column { flex: 1; min-width: 0; } /* Allow columns to shrink */
        .diff-view-container {
            border: 1px solid #ccc; border-radius: 8px; padding: 5px;
            background-color: #f8f9fa; height: 600px; overflow: auto;
            font-family: Consolas, 'Courier New', monospace; font-size: 0.85em; line-height: 1.5;
        }
        .diff-line-wrapper { display: flex; align-items: flex-start; border-bottom: 1px dotted #eee; padding: 1px 0; }
        .line-num { flex: 0 0 40px; text-align: right; padding-right: 10px; color: #888; background-color: #f0f0f0; user-select: none; }
        .line-content { flex: 1 1 auto; white-space: pre; word-wrap: break-word; padding-left: 5px; }
        .diff-equal .line-content { color: #333; }
        .diff-context .line-content { color: #666; font-style: italic; }
        .diff-placeholder .line-content { color: #aaa; background-color: #fafafa; }
        .diff-add .line-content { background-color: #e6ffed; color: #22863a; }
        .diff-sub .line-content { background-color: #ffeef0; color: #b31d28; text-decoration: line-through; }
        mark { background-color: #fffbdd; padding: 0 2px; border-radius: 3px; font-weight: bold; }
        .diff-sub mark { background-color: #ffdce0; }
        .diff-add mark { background-color: #c6f9d0; }
        .diff-sep { text-align: center; color: #888; font-style: italic; background-color: #fafafa; border-top: 1px dashed #ccc; border-bottom: 1px dashed #ccc; padding: 5px 0; margin: 5px 0; user-select: none; }
        .summary-container { display: flex; gap: 20px; margin-bottom: 20px; }
        .summary-item { background-color: #f0f2f6; border-radius: 8px; padding: 15px; text-align: center; flex: 1; }
        .summary-item strong { display: block; font-size: 1.5em; margin-bottom: 5px;}
        .options-list { list-style: none; padding-left: 0; }
        .options-list li::before { content: "✓ "; color: green; }
    </style>
    """
    options_html = "<ul class='options-list'>"
    if options['ignore_whitespace']: options_html += "<li>Ignore Leading/Trailing Whitespace</li>"
    if options['ignore_case']: options_html += "<li>Ignore Case</li>"
    if options['ignore_blank_lines']: options_html += "<li>Ignore Blank Lines</li>"
    if options['hide_unchanged']: options_html += f"<li>Hide Unchanged Lines (Context: {options['num_context']})</li>"
    options_html += "</ul>"
    if not options['ignore_whitespace'] and not options['ignore_case'] and not options['ignore_blank_lines'] and not options['hide_unchanged']:
        options_html = "<p>Default comparison options used.</p>"


    report = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Comparison Report: {html.escape(file_a_name)} vs {html.escape(file_b_name)}</title>
        <meta charset="UTF-8">
        {css}
    </head>
    <body>
        <h1>Comparison Report</h1>
        <p><strong>File A:</strong> {html.escape(file_a_name)}</p>
        <p><strong>File B:</strong> {html.escape(file_b_name)}</p>

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
            <div class="diff-column">
                <h3>File A</h3>
                {html_a}
            </div>
            <div class="diff-column">
                <h3>Differences</h3>
                {html_diff}
            </div>
            <div class="diff-column">
                <h3>File B</h3>
                {html_b}
            </div>
        </div>

    </body>
    </html>
    """
    return report


# --- Sidebar ---
st.sidebar.title("⚙️ Comparison Settings")

st.sidebar.subheader("Input Method")
input_method = st.sidebar.radio(
    "Choose Input Method:",
    ("File Upload", "Text Input"),
    label_visibility="collapsed"
)

st.sidebar.subheader("Comparison Options")
options = {}
options['ignore_whitespace'] = st.sidebar.checkbox("Ignore Leading/Trailing Whitespace", value=True)
options['ignore_case'] = st.sidebar.checkbox("Ignore Case", value=False)
options['ignore_blank_lines'] = st.sidebar.checkbox("Ignore Blank Lines", value=False)
options['hide_unchanged'] = st.sidebar.checkbox("Hide Unchanged Lines", value=False)
options['num_context'] = st.sidebar.number_input(
    "Context Lines", min_value=0, value=3, step=1,
    disabled=not options['hide_unchanged'],
    help="Number of matching lines to show around differences when 'Hide Unchanged' is active."
)

# --- Main App Area ---
st.title("✨ Enhanced File Comparison Tool")
st.write("Upload files or paste text below, configure options in the sidebar, and see the differences highlighted.")

# --- Input Area ---
lines_a, lines_b = None, None
file_a_name, file_b_name = "Pasted Text A", "Pasted Text B" # Defaults for text input

if input_method == "File Upload":
    col1, col2 = st.columns(2)
    with col1:
        uploaded_file_a = st.file_uploader("📂 Upload File A", type=["txt", "csv", "py", "js", "html", "css", "md", "json", "yaml", "log", "ini"], key="file_a")
        if uploaded_file_a:
            _, lines_a = read_file_content(uploaded_file_a)
            file_a_name = uploaded_file_a.name
    with col2:
        uploaded_file_b = st.file_uploader("📂 Upload File B", type=["txt", "csv", "py", "js", "html", "css", "md", "json", "yaml", "log", "ini"], key="file_b")
        if uploaded_file_b:
            _, lines_b = read_file_content(uploaded_file_b)
            file_b_name = uploaded_file_b.name

elif input_method == "Text Input":
    col1, col2 = st.columns(2)
    with col1:
        text_a = st.text_area("📝 Paste Text A", height=200, key="text_a", placeholder="Paste content for File A here...")
        if text_a:
            lines_a = text_a.splitlines()
    with col2:
        text_b = st.text_area("📝 Paste Text B", height=200, key="text_b", placeholder="Paste content for File B here...")
        if text_b:
            lines_b = text_b.splitlines()

# --- Comparison Logic & Display ---
st.markdown("---") # Separator

if lines_a is not None and lines_b is not None:
    if not lines_a and not lines_b:
         st.warning("Both inputs are empty.", icon="🤷‍♂️")
    else:
        # Perform comparison
        with st.spinner("Analyzing differences..."):
             html_a, html_diff, html_b, diff_stats = generate_enhanced_diff_views(lines_a, lines_b, options)

        # Display Summary Stats
        st.subheader("📊 Comparison Summary")
        stat_cols = st.columns(4)
        stat_cols[0].metric("Lines Added", f"{diff_stats['added']}", delta=diff_stats['added'] if diff_stats['added'] > 0 else None)
        stat_cols[1].metric("Lines Deleted", f"{diff_stats['deleted']}", delta=-diff_stats['deleted'] if diff_stats['deleted'] > 0 else None, delta_color="inverse")
        stat_cols[2].metric("Lines Modified", f"{diff_stats['modified']}")
        stat_cols[3].metric("Lines Unchanged", f"{diff_stats['unchanged']}")

        # Download Button
        report_html = generate_html_report(html_a, html_diff, html_b, diff_stats, options, file_a_name, file_b_name)
        st.download_button(
            label="📥 Download HTML Report",
            data=report_html,
            file_name=f"comparison_{file_a_name}_vs_{file_b_name}.html",
            mime="text/html",
        )
        st.markdown("---")


        # Display Difference Views
        st.subheader("↔️ Side-by-Side Comparison")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.caption(f"File A: {html.escape(file_a_name)}")
            st.markdown(html_a, unsafe_allow_html=True)
        with col2:
            st.caption("Differences")
            st.markdown(html_diff, unsafe_allow_html=True)
        with col3:
            st.caption(f"File B: {html.escape(file_b_name)}")
            st.markdown(html_b, unsafe_allow_html=True)

elif (input_method == "File Upload" and (uploaded_file_a or uploaded_file_b)) or \
     (input_method == "Text Input" and (text_a or text_b)):
    st.info("Please provide content for both File A and File B to start the comparison.", icon="☝️")
else:
    st.info("Upload files or paste text to begin comparison.", icon="⏳")


# --- Footer ---
st.markdown("---")
st.markdown("Enhanced File Comparison Tool | Built with ❤️ using [Streamlit](https://streamlit.io) & Python `difflib`")