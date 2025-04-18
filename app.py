import streamlit as st
import difflib
from io import StringIO
import collections

# --- Page Configuration ---
st.set_page_config(
    page_title="File Comparison Tool",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
def generate_diff_views(lines_a, lines_b, hide_unchanged, num_context, ignore_whitespace):
    """
    Generates three views: File A, Differences Only, File B.
    Applies filtering for unchanged lines based on options.
    """
    if ignore_whitespace:
        processed_a = [line.strip() for line in lines_a]
        processed_b = [line.strip() for line in lines_b]
    else:
        processed_a = lines_a
        processed_b = lines_b

    # Use SequenceMatcher to get opcodes, which are better for context handling
    s = difflib.SequenceMatcher(None, processed_a, processed_b, autojunk=False)
    opcodes = s.get_opcodes()

    view_a = []
    view_b = []
    view_diff = []
    diff_stats = {"added": 0, "deleted": 0, "modified": 0, "unchanged": 0}

    last_a_idx, last_b_idx = 0, 0 # Keep track of last displayed line index for context

    for tag, i1, i2, j1, j2 in opcodes:
        lines_in_block_a = lines_a[i1:i2] # Use original lines for display
        lines_in_block_b = lines_b[j1:j2]

        is_diff_block = (tag != 'equal')

        # --- Context Handling when Hiding Unchanged ---
        if hide_unchanged and tag == 'equal':
            # Show context *before* a difference block
            # Check if the *next* block is a difference
            next_opcode_is_diff = (opcodes.index((tag, i1, i2, j1, j2)) + 1 < len(opcodes)) and opcodes[opcodes.index((tag, i1, i2, j1, j2)) + 1][0] != 'equal'
            context_before = []
            if next_opcode_is_diff and len(lines_in_block_a) > num_context:
                 context_before = lines_in_block_a[-num_context:]
                 if not view_a or view_a[-1] == "...": # Add separator if needed
                     view_a.append("...")
                     view_b.append("...")
                 view_a.extend([f"  {line}" for line in context_before]) # Prefix unchanged context
                 view_b.extend([f"  {line}" for line in lines_b[j2-num_context:j2]]) # Corresponding B context
                 last_a_idx = i2
                 last_b_idx = j2

            # Show context *after* a difference block
            # Check if the *previous* block was a difference (handled when processing the diff block itself)
            # We mainly skip the bulk of equal blocks here
            if not context_before and (view_a and view_a[-1] != "..."): # Add separator if context wasn't added and lines were skipped
                view_a.append("...")
                view_b.append("...")

        # --- Process Difference or All Lines (if not hiding) ---
        else: # tag != 'equal' or not hide_unchanged
            # Add context *before* this block if hiding and previous was equal & skipped
            if hide_unchanged and last_a_idx < i1:
                 # Find the preceding equal block's lines
                 prev_equal_lines_a = lines_a[last_a_idx:i1]
                 prev_equal_lines_b = lines_b[last_b_idx:j1]
                 if len(prev_equal_lines_a) > num_context:
                     if not view_a or view_a[-1] == "...": # Add separator if needed
                        view_a.append("...")
                        view_b.append("...")
                     context_lines_a = prev_equal_lines_a[:num_context]
                     context_lines_b = prev_equal_lines_b[:num_context]
                     view_a.extend([f"  {line}" for line in context_lines_a])
                     view_b.extend([f"  {line}" for line in context_lines_b])


            # Add the actual lines for this opcode
            if tag == 'equal':
                view_a.extend([f"  {line}" for line in lines_in_block_a]) # Prefix with '  '
                view_b.extend([f"  {line}" for line in lines_in_block_b])
                view_diff.extend([""] * len(lines_in_block_a)) # Placeholders in diff view
                diff_stats["unchanged"] += len(lines_in_block_a)
            elif tag == 'delete':
                view_a.extend([f"- {line}" for line in lines_in_block_a]) # Prefix with '- '
                view_b.extend([""] * len(lines_in_block_a)) # Placeholders
                view_diff.extend([f"- {line}" for line in lines_in_block_a])
                diff_stats["deleted"] += len(lines_in_block_a)
            elif tag == 'insert':
                view_a.extend([""] * len(lines_in_block_b)) # Placeholders
                view_b.extend([f"+ {line}" for line in lines_in_block_b]) # Prefix with '+ '
                view_diff.extend([f"+ {line}" for line in lines_in_block_b])
                diff_stats["added"] += len(lines_in_block_b)
            elif tag == 'replace':
                 # Treat replace as delete + insert for clearer side-by-side
                 delta = len(lines_in_block_a) - len(lines_in_block_b)
                 view_a.extend([f"- {line}" for line in lines_in_block_a])
                 view_b.extend([f"+ {line}" for line in lines_in_block_b])
                 view_diff.extend([f"- {line}" for line in lines_in_block_a])
                 view_diff.extend([f"+ {line}" for line in lines_in_block_b])
                 diff_stats["modified"] += max(len(lines_in_block_a), len(lines_in_block_b)) # Count modified lines

                 # Add placeholders to make columns align better if lengths differ
                 if delta > 0: # More lines in A than B
                     view_b.extend([""] * delta)
                 elif delta < 0: # More lines in B than A
                     view_a.extend([""] * abs(delta))

            last_a_idx = i2
            last_b_idx = j2


    # Filter the diff view to only show actual differences
    final_diff_view = [line for line in view_diff if line.strip() and not line.startswith("  ")]

    # Calculate a reasonable height for text areas
    # Max height of 800, proportional to longest view, min height 200
    max_lines = max(len(view_a), len(view_b), len(final_diff_view), 1) # Avoid division by zero
    height = min(800, max(200, max_lines * 18)) # Approx 18px per line

    return "\n".join(view_a), "\n".join(final_diff_view), "\n".join(view_b), diff_stats, height


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
st.write("Upload two text files. Differences are highlighted with `+` (added) or `-` (deleted) prefixes.")

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

        # Generate the views using the helper function
        view_a_str, view_diff_str, view_b_str, diff_stats, text_area_height = generate_diff_views(
            lines_a,
            lines_b,
            hide_unchanged,
            num_context_lines,
            ignore_whitespace
        )

        st.subheader("📊 Comparison Summary")
        stat_cols = st.columns(4)
        stat_cols[0].metric("Lines Added", f"{diff_stats['added']}", delta=diff_stats['added'], delta_color="normal")
        stat_cols[1].metric("Lines Deleted", f"{diff_stats['deleted']}", delta=-diff_stats['deleted'] if diff_stats['deleted'] > 0 else 0, delta_color="inverse")
        # Note: Modified stat calculation is approximate based on replace blocks
        stat_cols[2].metric("Lines Modified (Replaced)", f"{diff_stats['modified']}")
        stat_cols[3].metric("Lines Unchanged", f"{diff_stats['unchanged']}")


        st.subheader("↔️ Comparison Views")
        # --- Display Columns ---
        col1, col2, col3 = st.columns(3)

        with col1:
            st.caption(f"File A: {uploaded_file_a.name}")
            # Use st.text_area for scrollable, selectable text with fixed height
            st.text_area("File A Content", value=view_a_str, height=text_area_height, key="view_a", disabled=True, label_visibility="collapsed")

        with col2:
            st.caption("Differences Only")
            st.text_area("Differences", value=view_diff_str, height=text_area_height, key="view_diff", disabled=True, label_visibility="collapsed")

        with col3:
            st.caption(f"File B: {uploaded_file_b.name}")
            st.text_area("File B Content", value=view_b_str, height=text_area_height, key="view_b", disabled=True, label_visibility="collapsed")

    elif lines_a is None or lines_b is None:
        st.error("Could not process one or both files. Please check the file format and encoding.")

else:
    st.info("Please upload both File A and File B to start the comparison.")

# Add some footer info (optional)
st.markdown("---")
st.markdown("Built with [Streamlit](https://streamlit.io) and Python's `difflib`.")