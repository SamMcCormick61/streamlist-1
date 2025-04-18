import streamlit as st
import difflib
from io import StringIO

# --- Page Configuration ---
st.set_page_config(
    page_title="File Comparison Tool",
    layout="wide",  # Use wide layout for better side-by-side view
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
        lines = content.splitlines()
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

# --- Sidebar Options ---
st.sidebar.title("⚙️ Comparison Options")
show_context = st.sidebar.checkbox("Show Context Only", value=False,
                                   help="If checked, only shows differing lines plus some surrounding context lines.")
num_context_lines = st.sidebar.number_input("Number of Context Lines", min_value=0, value=3, step=1,
                                          disabled=not show_context,
                                          help="Number of unchanged lines to show above and below differing blocks.")
ignore_whitespace = st.sidebar.checkbox("Ignore Leading/Trailing Whitespace", value=False,
                                        help="If checked, ignores differences caused only by leading or trailing spaces on a line.")
# wrap_lines = st.sidebar.checkbox("Wrap Long Lines", value=True) # HtmlDiff default handles wrapping reasonably

# --- Main App ---
st.title("📄 File Comparison Tool")
st.write("Upload two text files (e.g., `.txt`, `.py`, `.csv`, `.md`, `.html`) to see their differences.")

# --- File Upload Columns ---
col1, col2 = st.columns(2)
with col1:
    uploaded_file_a = st.file_uploader("Upload File A", type=["txt", "csv", "py", "js", "html", "css", "md", "json", "yaml", "log"], key="file_a")
with col2:
    uploaded_file_b = st.file_uploader("Upload File B", type=["txt", "csv", "py", "js", "html", "css", "md", "json", "yaml", "log"], key="file_b")

# --- Process and Compare Files ---
if uploaded_file_a is not None and uploaded_file_b is not None:
    content_a, lines_a = read_file_content(uploaded_file_a)
    content_b, lines_b = read_file_content(uploaded_file_b)

    if lines_a is not None and lines_b is not None: # Proceed only if both files read successfully

        # Apply preprocessing based on options
        lines_a_processed = [line.strip() if ignore_whitespace else line for line in lines_a]
        lines_b_processed = [line.strip() if ignore_whitespace else line for line in lines_b]

        # --- Calculate Diff Statistics (Optional but helpful) ---
        diff_stats = {"added": 0, "deleted": 0, "modified": 0, "unchanged": 0}
        diff_list = list(difflib.ndiff(lines_a_processed, lines_b_processed)) # Use processed lines for stats too

        i = 0
        while i < len(diff_list):
            line = diff_list[i]
            if line.startswith('+ '):
                diff_stats["added"] += 1
                i += 1
            elif line.startswith('- '):
                diff_stats["deleted"] += 1
                i += 1
            elif line.startswith('? '):
                # A '?' line indicates intra-line changes, often follows a '-' and '+' pair for the same logical line
                # Count this as one modification. We need to be careful not to double count if the '?'
                # follows related '-' and '+' lines. A simple heuristic: if the previous was '-' and next is '+',
                # it's likely a modification block.
                is_modification = False
                if i > 0 and diff_list[i-1].startswith('- '):
                     if (i + 1 < len(diff_list)) and diff_list[i+1].startswith('+ '):
                         is_modification = True
                         diff_stats["modified"] +=1
                         diff_stats["deleted"] -= 1 # Adjust as it's part of a mod
                         diff_stats["added"] -= 1   # Adjust as it's part of a mod
                         i += 2 # Skip the '+ ' line as well
                     else: # ? follows - but not + -> Treat as just deletion? Or mod? Let's call it mod for simplicity here.
                         diff_stats["modified"] += 1
                         diff_stats["deleted"] -= 1 # Adjust
                         i += 1 # Move past '?'
                else: # Standalone '?' or '? ' after '+ ' or ' ' - less common but count as mod? Needs refinement.
                      # For simplicity, let's just move past '?' if not handled above.
                      i += 1


            elif line.startswith('  '):
                diff_stats["unchanged"] += 1
                i += 1
            else: # Should not happen with ndiff, but just in case
                i += 1


        st.subheader("📊 Comparison Summary")
        stat_cols = st.columns(4)
        with stat_cols[0]:
            st.metric("Lines Added", f"{diff_stats['added']}", delta=diff_stats['added'], delta_color="normal")
        with stat_cols[1]:
            st.metric("Lines Deleted", f"{diff_stats['deleted']}", delta=-diff_stats['deleted'] if diff_stats['deleted'] > 0 else 0, delta_color="inverse")
        with stat_cols[2]:
            st.metric("Lines Modified", f"{diff_stats['modified']}")
        with stat_cols[3]:
            st.metric("Lines Unchanged", f"{diff_stats['unchanged']}")


        st.subheader("↔️ Side-by-Side Difference")

        # --- Generate HTML Diff ---
        # Note: We pass the ORIGINAL lines (lines_a, lines_b) to HtmlDiff for display,
        # but the comparison logic might have used the processed lines (lines_a_processed, lines_b_processed)
        # if ignore_whitespace was True. HtmlDiff itself doesn't have a whitespace ignore option,
        # so this approach compares based on the option but displays the original formatting.
        # If you strictly want to see the diff based *only* on non-whitespace content,
        # you'd pass lines_a_processed, lines_b_processed here too.
        # Let's stick to showing original lines for better context.

        # Create HtmlDiff object
        # wrapcolumn=80 helps prevent excessively wide cells, adjust as needed
        d = difflib.HtmlDiff(tabsize=4, wrapcolumn=70)

        # Generate the HTML table
        # Use processed lines for comparison if ignoring whitespace, otherwise use original
        compare_lines_a = lines_a_processed if ignore_whitespace else lines_a
        compare_lines_b = lines_b_processed if ignore_whitespace else lines_b

        html_diff = d.make_file(
            compare_lines_a,  # Use potentially processed lines for the actual diff logic
            compare_lines_b,
            fromdesc=f"File A: {uploaded_file_a.name}",
            todesc=f"File B: {uploaded_file_b.name}",
            context=show_context,       # Apply context option
            numlines=num_context_lines if show_context else 0 # Apply context lines number
        )

        # --- Display HTML Diff ---
        # Inject custom CSS for better styling if needed (optional)
        st.markdown(
            """
            <style>
                table.diff {
                    font-family: Consolas, 'Courier New', monospace;
                    border-collapse: collapse;
                    width: 100%; /* Make table take full width */
                }
                .diff th {
                    background-color: #f0f0f0;
                    text-align: center;
                    padding: 4px;
                    border: 1px solid #ccc;
                }
                .diff td {
                    padding: 2px 4px;
                    vertical-align: top;
                    white-space: pre-wrap; /* Allow wrapping within cells */
                    border: 1px solid #eee;
                }
                .diff_header { background-color: #e0e0e0; font-weight: bold; }
                .diff_next { background-color: #f0f8ff; } /* Context line indicator */
                .diff_add { background-color: #ddffdd; } /* Added lines green */
                .diff_chg { background-color: #ffffcc; } /* Changed lines yellow */
                .diff_sub { background-color: #ffdddd; } /* Deleted lines red */
                /* Ensure line numbers are not overly wide */
                .diff td:first-child, .diff td:nth-child(3) {
                     width: 40px; /* Adjust as needed */
                     text-align: right;
                     color: #888;
                     background-color: #fafafa;
                     padding-right: 6px;
                 }
            </style>
            """, unsafe_allow_html=True
        )

        # Render the HTML diff table
        st.components.v1.html(html_diff, height=800, scrolling=True)

    elif lines_a is None or lines_b is None:
        st.error("Could not process one or both files. Please check the file format and encoding.")

else:
    st.info("Please upload both File A and File B to see the comparison.")

# Add some footer info (optional)
st.markdown("---")
st.markdown("Built with [Streamlit](https://streamlit.io) and Python's `difflib`.")