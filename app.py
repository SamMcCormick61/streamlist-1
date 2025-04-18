import streamlit as st
import difflib
from io import StringIO
import html # For escaping

# --- Page Configuration ---
st.set_page_config(
    page_title="File Comparison Tool",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS Styling ---
# Inject custom CSS for styling the diff views within markdown
st.markdown("""
<style>
    .diff-container {
        font-family: Consolas, 'Courier New', monospace;
        border: 1px solid #ccc;
        padding: 10px;
        border-radius: 5px;
        background-color: #f8f9fa; /* Light background for the container */
        overflow-y: auto; /* Enable vertical scrolling */
        white-space: pre; /* Preserve whitespace and prevent wrapping */
        line-height: 1.4;
        font-size: 0.9em;
    }
    .diff-line {
        display: block; /* Each line as a block */
        min-height: 1.4em; /* Ensure consistent line height */
    }
    .diff-placeholder {
        color: #aaa; /* Lighter color for placeholders */
        background-color: #f0f0f0; /* Slightly different background for placeholders */
        display: block;
        min-height: 1.4em;
    }
    .diff-equal {
        color: #333; /* Standard text color */
    }
    .diff-context {
        color: #777; /* Slightly dimmer for context */
    }
    .diff-add {
        background-color: #e6ffed; /* Light green background */
        color: #22863a; /* Darker green text */
    }
    .diff-sub {
        background-color: #ffeef0; /* Light red background */
        color: #b31d28; /* Darker red text */
        text-decoration: line-through; /* Optional: strike-through deleted text */
    }
    .diff-sep {
        color: #888;
        font-style: italic;
        text-align: center;
        background-color: #fafafa;
        border-top: 1px dashed #ccc;
        border-bottom: 1px dashed #ccc;
        margin-top: 5px;
        margin-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)


# --- Helper Function ---
def read_file_content(uploaded_file):
    """Reads content from uploaded file, handling potential decoding errors."""
    if uploaded_file is None:
        return None, None # Return None for both content and lines

    try:
        # Try decoding as UTF-8 first
        stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
        content = stringio.read()
        lines = content.splitlines() # Keep line endings consistent
        return content, lines
    except UnicodeDecodeError:
        try:
            # Fallback to latin-1 if UTF-8 fails
            stringio = StringIO(uploaded_file.getvalue().decode("latin-1"))
            content = stringio.read()
            lines = content.splitlines()
            st.warning(f"File '{uploaded_file.name}' was not UTF-8 encoded. Decoded using latin-1. Some characters might not display correctly.", icon="⚠️")
            return content, lines
        except Exception as e:
            st.error(f"Error reading file '{uploaded_file.name}': {e}")
            return None, None
    except Exception as e:
        st.error(f"Error processing file '{uploaded_file.name}': {e}")
        return None, None

# --- Core Diff Logic ---
def generate_diff_views_html(lines_a, lines_b, hide_unchanged, num_context, ignore_whitespace):
    """
    Generates three HTML views: File A, Differences Only, File B.
    Applies filtering for unchanged lines based on options.
    Uses HTML/CSS for styling.
    """
    if ignore_whitespace:
        processed_a = [line.strip() for line in lines_a]
        processed_b = [line.strip() for line in lines_b]
    else:
        processed_a = lines_a
        processed_b = lines_b

    s = difflib.SequenceMatcher(None, processed_a, processed_b, autojunk=False)
    opcodes = s.get_opcodes()

    view_a_html = []
    view_b_html = []
    view_diff_html = []
    diff_stats = {"added": 0, "deleted": 0, "modified": 0, "unchanged": 0}

    last_a_idx, last_b_idx = 0, 0 # Keep track of last original line index
    last_processed_a_idx, last_processed_b_idx = 0, 0 # Keep track of last processed line index for context logic

    def escape(text):
        return html.escape(text).replace(' ',' ') # Escape HTML chars and preserve spaces

    def format_line(line_text, line_class, prefix=""):
        return f'<span class="diff-line {line_class}">{prefix}{escape(line_text)}</span>'

    placeholder_line = '<span class="diff-line diff-placeholder"> </span>' # Placeholder HTML
    separator_line = '<div class="diff-sep">... unchanged lines hidden ...</div>'

    for tag, i1, i2, j1, j2 in opcodes:
        lines_in_block_a = lines_a[i1:i2] # Original lines for display
        lines_in_block_b = lines_b[j1:j2]

        # --- Context Handling when Hiding Unchanged ---
        if hide_unchanged and tag == 'equal':
            # Context *before* a difference: Show last `num_context` lines of this equal block
            if len(lines_in_block_a) > num_context * 2: # Only show context if block is large enough
                 # Check if the *next* block is a difference
                 current_opcode_index = opcodes.index((tag, i1, i2, j1, j2))
                 next_opcode_is_diff = (current_opcode_index + 1 < len(opcodes)) and opcodes[current_opcode_index + 1][0] != 'equal'

                 # Show context lines *before* the gap (first num_context)
                 if last_processed_a_idx < i1: # If there was a previous diff block
                     if i1 - last_processed_a_idx > num_context: # Check if lines were actually skipped
                         view_a_html.append(separator_line)
                         view_b_html.append(separator_line)
                     context_a = lines_in_block_a[:num_context]
                     context_b = lines_in_block_b[:num_context]
                     view_a_html.extend([format_line(line, "diff-context", "  ") for line in context_a])
                     view_b_html.extend([format_line(line, "diff-context", "  ") for line in context_b])
                     view_diff_html.extend([placeholder_line] * len(context_a))

                 # Show context lines *after* the gap (last num_context) if next is diff
                 if next_opcode_is_diff:
                     if i2 - i1 > num_context: # Check if lines will be skipped after context
                          view_a_html.append(separator_line)
                          view_b_html.append(separator_line)
                     context_a = lines_in_block_a[-num_context:]
                     context_b = lines_in_block_b[-num_context:]
                     view_a_html.extend([format_line(line, "diff-context", "  ") for line in context_a])
                     view_b_html.extend([format_line(line, "diff-context", "  ") for line in context_b])
                     view_diff_html.extend([placeholder_line] * len(context_a))

            else: # Small equal block, show all of it
                view_a_html.extend([format_line(line, "diff-equal", "  ") for line in lines_in_block_a])
                view_b_html.extend([format_line(line, "diff-equal", "  ") for line in lines_in_block_b])
                view_diff_html.extend([placeholder_line] * len(lines_in_block_a))
                diff_stats["unchanged"] += len(lines_in_block_a)

        # --- Process Difference or All Lines (if not hiding) ---
        else: # tag != 'equal' or not hide_unchanged
            # Add context from preceding equal block if it was skipped
            if hide_unchanged and last_processed_a_idx < i1 : # Check if prev block was equal and skipped
                 prev_equal_lines_a = lines_a[last_a_idx:i1] # Get original lines
                 prev_equal_lines_b = lines_b[last_b_idx:j1]
                 if len(prev_equal_lines_a) > num_context: # Only add context if lines were hidden
                     if not view_a_html or view_a_html[-1] != separator_line: # Avoid double separators
                         view_a_html.append(separator_line)
                         view_b_html.append(separator_line)
                     context_a = prev_equal_lines_a[:num_context] # First N lines as context
                     context_b = prev_equal_lines_b[:num_context]
                     view_a_html.extend([format_line(line, "diff-context", "  ") for line in context_a])
                     view_b_html.extend([format_line(line, "diff-context", "  ") for line in context_b])
                     view_diff_html.extend([placeholder_line] * len(context_a))

            # Add the actual lines for this opcode tag
            if tag == 'equal':
                view_a_html.extend([format_line(line, "diff-equal", "  ") for line in lines_in_block_a])
                view_b_html.extend([format_line(line, "diff-equal", "  ") for line in lines_in_block_b])
                view_diff_html.extend([placeholder_line] * len(lines_in_block_a))
                diff_stats["unchanged"] += len(lines_in_block_a)
            elif tag == 'delete':
                formatted_lines = [format_line(line, "diff-sub", "- ") for line in lines_in_block_a]
                view_a_html.extend(formatted_lines)
                view_b_html.extend([placeholder_line] * len(lines_in_block_a))
                view_diff_html.extend(formatted_lines)
                diff_stats["deleted"] += len(lines_in_block_a)
            elif tag == 'insert':
                formatted_lines = [format_line(line, "diff-add", "+ ") for line in lines_in_block_b]
                view_a_html.extend([placeholder_line] * len(lines_in_block_b))
                view_b_html.extend(formatted_lines)
                view_diff_html.extend(formatted_lines)
                diff_stats["added"] += len(lines_in_block_b)
            elif tag == 'replace':
                diff_stats["modified"] += max(len(lines_in_block_a), len(lines_in_block_b))
                delta = len(lines_in_block_a) - len(lines_in_block_b)
                deleted_lines = [format_line(line, "diff-sub", "- ") for line in lines_in_block_a]
                added_lines = [format_line(line, "diff-add", "+ ") for line in lines_in_block_b]

                view_a_html.extend(deleted_lines)
                view_b_html.extend(added_lines)
                view_diff_html.extend(deleted_lines)
                view_diff_html.extend(added_lines)

                if delta > 0: # More lines in A than B
                    view_b_html.extend([placeholder_line] * delta)
                elif delta < 0: # More lines in B than A
                    view_a_html.extend([placeholder_line] * abs(delta))

        # Update indices for the next iteration
        last_a_idx = i2
        last_b_idx = j2
        last_processed_a_idx = i2 # Update processed index tracker as well
        last_processed_b_idx = j2


    # Filter the diff view to only show actual differences (non-placeholders)
    # Keep separators if they exist
    final_diff_view_html = [line for line in view_diff_html if 'diff-placeholder' not in line or 'diff-sep' in line]
    # If only separators remain, clear it
    if all('diff-sep' in line for line in final_diff_view_html):
         final_diff_view_html = ["<span class='diff-line diff-context'>No differences found</span>"]
    elif not final_diff_view_html:
         final_diff_view_html = ["<span class='diff-line diff-context'>No differences found</span>"]


    # Combine HTML lines into single strings for each view
    # Wrap each view in a container div for scrolling and styling
    container_style = "max-height: 600px;" # Adjust max height as needed
    html_a = f'<div class="diff-container" style="{container_style}">{"".join(view_a_html)}</div>'
    html_diff = f'<div class="diff-container" style="{container_style}">{"".join(final_diff_view_html)}</div>'
    html_b = f'<div class="diff-container" style="{container_style}">{"".join(view_b_html)}</div>'

    return html_a, html_diff, html_b, diff_stats


# --- Sidebar Options ---
st.sidebar.title("⚙️ Comparison Options")
hide_unchanged = st.sidebar.checkbox("Hide Unchanged Lines", value=False,
                                     help="Show only differing lines plus context in File A and File B columns.")
num_context_lines = st.sidebar.number_input("Number of Context Lines", min_value=0, value=3, step=1,
                                          disabled=not hide_unchanged,
                                          help="Number of unchanged lines to show around differences when 'Hide Unchanged' is active.")
ignore_whitespace = st.sidebar.checkbox("Ignore Leading/Trailing Whitespace", value=False,
                                        help="Ignore differences caused only by leading/trailing spaces on a line.")

# --- Main App ---
st.title("↔️ File Comparison Tool")
st.write("Upload two text files. Differences are highlighted by color.")

# --- File Upload Row ---
upload_col1, upload_col2 = st.columns(2)
with upload_col1:
    uploaded_file_a = st.file_uploader("Upload File A", type=["txt", "csv", "py", "js", "html", "css", "md", "json", "yaml", "log"], key="file_a")
with upload_col2:
    uploaded_file_b = st.file_uploader("Upload File B", type=["txt", "csv", "py", "js", "html", "css", "md", "json", "yaml", "log"], key="file_b")

# --- Process and Compare Files ---
if uploaded_file_a is not None and uploaded_file_b is not None:
    content_a, lines_a = read_file_content(uploaded_file_a)
    content_b, lines_b = read_file_content(uploaded_file_b)

    if lines_a is not None and lines_b is not None: # Proceed only if both files read successfully

        # Generate the HTML views using the updated helper function
        view_a_html, view_diff_html, view_b_html, diff_stats = generate_diff_views_html(
            lines_a,
            lines_b,
            hide_unchanged,
            num_context_lines,
            ignore_whitespace
        )

        st.subheader("📊 Comparison Summary")
        stat_cols = st.columns(4)
        stat_cols[0].metric("Lines Added", f"{diff_stats['added']}", delta=diff_stats['added'] if diff_stats['added'] > 0 else None)
        stat_cols[1].metric("Lines Deleted", f"{diff_stats['deleted']}", delta=-diff_stats['deleted'] if diff_stats['deleted'] > 0 else None, delta_color="inverse")
        stat_cols[2].metric("Lines Modified (Replaced)", f"{diff_stats['modified']}")
        stat_cols[3].metric("Lines Unchanged", f"{diff_stats['unchanged']}")


        st.subheader("↔️ Comparison Views")
        # --- Display Columns ---
        col1, col2, col3 = st.columns(3)

        with col1:
            st.caption(f"File A: {uploaded_file_a.name}")
            st.markdown(view_a_html, unsafe_allow_html=True)

        with col2:
            st.caption("Differences Only")
            st.markdown(view_diff_html, unsafe_allow_html=True)

        with col3:
            st.caption(f"File B: {uploaded_file_b.name}")
            st.markdown(view_b_html, unsafe_allow_html=True)

    elif lines_a is None or lines_b is None:
        st.error("Could not process one or both files. Please check the file format and encoding.")

else:
    st.info("Please upload both File A and File B to start the comparison.")

# Add some footer info (optional)
st.markdown("---")
st.markdown("Built with [Streamlit](https://streamlit.io) and Python's `difflib`.")