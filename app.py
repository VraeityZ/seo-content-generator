import streamlit as st
import pandas as pd
import anthropic
import json
import re
import warnings
from main import parse_cora_report, generate_heading_structure, generate_content

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl.styles.stylesheet")

# Utility function to analyze content
def analyze_content(markdown_content, requirements):
    """Analyze the generated content against the SEO requirements."""
    analysis = {
        "primary_keyword": requirements.get("primary_keyword", ""),
        "primary_keyword_count": 0,
        "word_count": 0,
        "heading_structure": {"H1": 0, "H2": 0, "H3": 0, "H4": 0, "H5": 0, "H6": 0},
        "lsi_keywords": {},
        "entities": {}
    }
    
    words = markdown_content.split()
    analysis["word_count"] = len(words)
    
    primary_keyword = requirements.get("primary_keyword", "").lower()
    if primary_keyword:
        analysis["primary_keyword_count"] = markdown_content.lower().count(primary_keyword)
    
    heading_pattern = r"^(#{1,6})\s+(.+)$"
    for line in markdown_content.split("\n"):
        match = re.match(heading_pattern, line)
        if match:
            heading_level = f"H{len(match.group(1))}"
            analysis["heading_structure"][heading_level] += 1
    
    lsi_keywords = requirements.get("lsi_keywords", {})
    if isinstance(lsi_keywords, list):
        lsi_keywords_dict = {kw: 1 for kw in lsi_keywords}
        lsi_keywords = lsi_keywords_dict

    for keyword, target_count in lsi_keywords.items():
        count = markdown_content.lower().count(keyword.lower())
        status = "✅" if count >= target_count else "❌"
        analysis["lsi_keywords"][keyword] = {
            "count": count,
            "target": target_count,
            "status": status
        }
    
    entities = requirements.get("entities", [])
    for entity in entities:
        found = entity.lower() in markdown_content.lower()
        status = "✅" if found else "❌"
        analysis["entities"][entity] = {
            "found": found,
            "status": status
        }
    
    return analysis

# Streamlit page configuration
st.set_page_config(
    page_title="SEO Content Generator",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Main app title and description
st.title("SEO Content Generator")
st.markdown("""
This application generates SEO-optimized content based on CORA report data. 
Upload your CORA report, adjust heading requirements, and click 'Generate Content'.
""")

# Sidebar for API configuration
with st.sidebar:
    st.title("Configuration")
    
    claude_api = st.text_input(
        "Claude API Key", 
        value="",
        type="password",
        help="Enter your Claude API key. This will not be stored permanently."
    )
    st.session_state['claude_api'] = claude_api
    
    openai_api = st.text_input(
        "OpenAI API Key (Optional)",
        value="",
        type="password",
        help="Enter your OpenAI API key if you want to use OpenAI models."
    )
    st.session_state['openai_api'] = openai_api
    
    if not claude_api:
        st.warning("Please enter your Claude API key to use this app.")

# File upload section
uploaded_file = st.file_uploader("Upload CORA report", type=["xlsx", "xls"])

def process_upload():
    """Process the uploaded CORA report and extract requirements."""
    if 'file' not in st.session_state:
        st.error("Please upload a CORA report first.")
        return
    
    try:
        file = st.session_state['file']
        
        with st.spinner("Processing CORA report..."):
            # Parse the CORA report
            requirements = parse_cora_report(file)
            
            # Ensure lsi_keywords is a dictionary
            if isinstance(requirements.get('lsi_keywords', {}), list):
                lsi_dict = {kw: 1 for kw in requirements.get('lsi_keywords', [])}
                requirements['lsi_keywords'] = lsi_dict
                
            # Apply heading controls if they're set in the UI
            h2_control = st.session_state.get('h2_control', 0)
            h3_control = st.session_state.get('h3_control', 0)
            h4_control = st.session_state.get('h4_control', 0)
            h5_control = st.session_state.get('h5_control', 0)
            
            # Override heading structure with user inputs if provided
            if h2_control > 0:
                requirements["heading_structure"]["h2"] = h2_control
            if h3_control > 0:
                requirements["heading_structure"]["h3"] = h3_control
            if h4_control > 0:
                requirements["heading_structure"]["h4"] = h4_control
            if h5_control > 0:
                requirements["heading_structure"]["h5"] = h5_control
            
            # Save to session state
            st.session_state['requirements'] = requirements
            st.session_state['step'] = 2
        
        # Display key information about the extracted requirements
        st.success("CORA report processed successfully!")
        st.info(f"Primary Keyword: {requirements['primary_keyword']}")
        st.info(f"Found {len(requirements.get('synonyms', []))} keyword variations")
        st.info(f"Found {len(requirements.get('lsi_keywords', {}))} LSI keywords")
        st.info(f"Word Count Target: {requirements['word_count']} words")
        st.info(f"Heading Structure: H2={requirements['heading_structure'].get('h2', 0)}, " +
               f"H3={requirements['heading_structure'].get('h3', 0)}, " +
               f"H4={requirements['heading_structure'].get('h4', 0)}, " +
               f"H5={requirements['heading_structure'].get('h5', 0)}")
        
    except Exception as e:
        st.error(f"Error processing CORA report: {str(e)}")
        st.write(f"Exception type: {type(e).__name__}")
        st.write(f"Exception message: {str(e)}")
        import traceback
        st.code(traceback.format_exc())

if uploaded_file is not None:
    st.session_state['file'] = uploaded_file
    st.success(f"Successfully uploaded: {uploaded_file.name}")
    
    # Display heading controls in a single column
    with st.expander("Configure Headings (optional)", expanded=False):
        st.markdown("### Heading Controls")
        st.markdown("Use these controls to override the number of headings recommended in the CORA report")
        h2_control = st.number_input("Number of H2 headings", min_value=0, max_value=10, value=0, step=1, key='h2_control')
        h3_control = st.number_input("Number of H3 headings", min_value=0, max_value=20, value=0, step=1, key='h3_control')
        h4_control = st.number_input("Number of H4 headings", min_value=0, max_value=20, value=0, step=1, key='h4_control')
        h5_control = st.number_input("Number of H5 headings", min_value=0, max_value=20, value=0, step=1, key='h5_control')
    
    # Button to extract requirements
    if st.button("Extract Requirements"):
        process_upload()

else:
    st.info("Please upload a CORA report to get started.")

if st.session_state.get("step", 1) == 2:
    requirements = st.session_state.requirements
    
    # Display requirements
    st.subheader("Extracted Requirements")
    
    # Debug section to show all extracted information
    with st.expander("🔍 View Complete Extracted Data", expanded=False):
        st.markdown("### Core Information")
        st.write(f"**Primary Keyword:** {requirements.get('primary_keyword', 'Not found')}")
        st.write(f"**Word Count Target:** {requirements['word_count']} words")
        
        st.markdown("### Debug Information")
        debug_info = requirements.get('debug_info', {})
        if debug_info:
            st.write(f"**Sheets Found:** {', '.join(debug_info.get('sheets_found', ['None']))}")
            st.write(f"**LSI Start Row:** {debug_info.get('lsi_start_row', 'Not found')}")
            st.write(f"**Entities Start Row:** {debug_info.get('entities_start_row', 'Not found')}")
            st.write(f"**Headings Section:** {debug_info.get('headings_section', 'Not found')}")
        
        st.markdown("### Keyword Variations")
        variations = requirements.get('variations', [])
        if variations:
            st.write(f"Found {len(variations)} variations:")
            variations_df = pd.DataFrame({
                'Variation': variations
            })
            st.dataframe(variations_df, use_container_width=True, height=300)
        else:
            st.write("No variations found")
        
        st.markdown("### LSI Keywords")
        lsi_keywords = requirements.get('lsi_keywords', {})
        if lsi_keywords:
            st.write(f"Found {len(lsi_keywords)} LSI keywords:")
            lsi_df = pd.DataFrame({
                'Keyword': list(lsi_keywords.keys()), 
                'Frequency': list(lsi_keywords.values())
            })
            st.dataframe(lsi_df, use_container_width=True, height=300)
        else:
            st.write("No LSI keywords found")
        
        st.markdown("### Entities")
        entities = requirements.get('entities', [])
        if entities:
            st.write(f"Found {len(entities)} entities:")
            entities_df = pd.DataFrame({
                'Entity': entities
            })
            st.dataframe(entities_df, use_container_width=True, height=300)
        else:
            st.write("No entities found")
        
        st.markdown("### Heading Structure")
        heading_structure = requirements.get('heading_structure', {})
        if heading_structure:
            h_df = pd.DataFrame({
                'Heading Level': [f"H{i}" for i in range(1, 6)],
                'Count': [1] + [heading_structure.get(f"h{i}", 0) for i in range(2, 6)]
            })
            st.dataframe(h_df, use_container_width=True, height=300)
            total_headings = 1 + sum(heading_structure.values())
            st.write(f"**Total Headings:** {total_headings}")
        
        st.markdown("### Specific Requirements (from Roadmap)")
        roadmap_reqs = requirements.get('requirements', {})
        if roadmap_reqs:
            sorted_reqs = dict(sorted(roadmap_reqs.items()))
            req_df = pd.DataFrame({
                'Requirement': list(sorted_reqs.keys()),
                'Value': list(sorted_reqs.values())
            })
            st.dataframe(req_df, use_container_width=True, height=300)
        else:
            st.write("No specific requirements found")
    
    # Show the API prompt
    with st.expander("🔍 View API Prompt", expanded=False):
        st.markdown("### Prompt That Will Be Sent to Claude/ChatGPT")
        
        primary_keyword = requirements.get('primary_keyword', '')
        variations = requirements.get('variations', [])
        lsi_dict = requirements.get('lsi_keywords', {})
        entities = requirements.get('entities', [])
        word_count = requirements['word_count']
        heading_structure = requirements.get('heading_structure', {"h2": 3, "h3": 6})
        
        variations_text = ", ".join(variations[:5]) + (f"... and {len(variations) - 5} more" if len(variations) > 5 else "")
        lsi_formatted = "\n".join([f"'{kw}' => at least {freq} occurrences" for kw, freq in list(lsi_dict.items())[:5]])
        if len(lsi_dict) > 5:
            lsi_formatted += f"\n... and {len(lsi_dict) - 5} more keywords"
        entities_text = ", ".join(entities[:5]) + (f"... and {len(entities) - 5} more" if len(entities) > 5 else "")
        
        headings_text = generate_heading_structure(
            primary_keyword, 
            heading_structure,
            list(lsi_dict.keys())[:3] if lsi_dict else [],
            entities[:3] if entities else []
        )
        
        prompt_preview = f"""
        ## SEO Content Writing Task

        **PRIMARY KEYWORD:** {primary_keyword}
        **VARIATIONS:** {variations_text}
        **WORD COUNT:** {word_count} words

        ### CONTENT REQUIREMENTS:
        
        {headings_text}
        
        ### LSI KEYWORDS:
        {lsi_formatted}
        
        ### ENTITIES TO INCLUDE:
        {entities_text}
        
        ### ADDITIONAL INSTRUCTIONS:
        - Write in a clear, authoritative style
        - Include the primary keyword in the first 100 words
        - Use a variety of heading levels for better readability
        - Ensure content is factually accurate and helpful to the reader
        """
        
        st.code(prompt_preview, language="markdown")
    
    # Basic requirements summary
    with st.expander("Basic Requirements Summary", expanded=False):
        st.write(f"**Primary Keyword:** {requirements.get('primary_keyword', 'Not found')}")
        st.write(f"**Variations:** {', '.join(requirements.get('variations', []))[:100]}{'...' if len(', '.join(requirements.get('variations', []))) > 100 else ''}")
        st.write("**LSI Keywords:**")
        lsi_keywords = requirements.get('lsi_keywords', {})
        if lsi_keywords:
            for keyword, freq in list(lsi_keywords.items())[:5]:
                st.write(f"- {keyword} ({freq})")
            if len(lsi_keywords) > 5:
                st.write(f"... and {len(lsi_keywords) - 5} more")
        else:
            st.write("No LSI keywords found")
        st.write("**Entities:**")
        entities = requirements.get('entities', [])
        if entities:
            for entity in entities[:5]:
                st.write(f"- {entity}")
            if len(entities) > 5:
                st.write(f"... and {len(entities) - 5} more")
        st.write("**Heading Structure:**")
        heading_structure = requirements.get('heading_structure', {})
        for level in range(2, 6):
            key = f"h{level}"
            st.write(f"- **{key.upper()} Headings:** {heading_structure.get(key, 0)}")
    
    # Generate content button
    if st.button("Generate Content"):
        if not st.session_state.get('claude_api', ''):
            st.error("Please enter your Claude API key in the sidebar.")
        else:
            st.session_state['step'] = 3
            st.experimental_rerun()

    # Download button for markdown (if content exists)
    if st.session_state.get('generated_markdown', ''):
        st.download_button(
            label="Download Markdown",
            data=st.session_state['generated_markdown'],
            file_name=f"{requirements.get('primary_keyword', 'content').replace(' ', '_')}.md",
            mime="text/markdown"
        )

def generate_content_flow():
    """Generate and display content."""
    if 'generated_markdown' not in st.session_state:
        requirements = st.session_state.requirements
        settings = {
            'model': 'claude',  # Default model
            'anthropic_api_key': st.session_state.get('claude_api', ''),
            'openai_api_key': st.session_state.get('openai_api', ''),
        }
        with st.spinner("Generating content..."):
            try:
                markdown_content, html_content, save_path = generate_content(
                    requirements, 
                    settings=settings
                )
                st.session_state['generated_markdown'] = markdown_content
                st.session_state['generated_html'] = html_content
                st.session_state['save_path'] = save_path
                st.session_state['step'] = 3
            except Exception as e:
                st.error(f"Error generating content: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
                return
    
    st.success("Content generated successfully!")
    st.subheader("Generated Content")
    
    tab1, tab2, tab3 = st.tabs(["Preview", "Markdown", "Analysis"])
    
    with tab1:
        st.components.v1.html(st.session_state['generated_html'], height=800, scrolling=True)
    
    with tab2:
        st.markdown("### Raw Markdown")
        st.text_area("Markdown Content", st.session_state['generated_markdown'], height=400)
        st.download_button(
            label="Download Markdown",
            data=st.session_state['generated_markdown'],
            file_name=f"seo_content_{st.session_state.requirements['primary_keyword'].replace(' ', '_').lower()}.md",
            mime="text/markdown"
        )
        if st.session_state.get('save_path'):
            st.write(f"Content also saved to: {st.session_state['save_path']}")
    
    with tab3:
        with st.spinner("Analyzing content..."):
            analysis = analyze_content(st.session_state['generated_markdown'], st.session_state.requirements)
            st.markdown("### Content Analysis")
            st.write(f"**Primary Keyword:** {analysis['primary_keyword']}")
            st.write(f"**Primary Keyword Count:** {analysis['primary_keyword_count']}")
            st.progress(min(1.0, analysis['primary_keyword_count'] / 5))
            st.write(f"**Word Count:** {analysis['word_count']}")
            target_word_count = st.session_state.requirements['word_count']
            st.progress(min(1.0, analysis['word_count'] / target_word_count))
            st.write("**Heading Structure:**")
            for level, count in analysis['heading_structure'].items():
                target_count = st.session_state.requirements.get('heading_structure', {}).get(level.lower(), 0)
                if level.lower() == 'h1':
                    target_count = 1
                st.write(f"- {level}: {count} (Target: {target_count})")
                if target_count > 0:
                    st.progress(min(1.0, count / target_count))
            st.markdown("### LSI Keywords Usage")
            if analysis['lsi_keywords']:
                lsi_df = pd.DataFrame(analysis['lsi_keywords']).T.reset_index()
                lsi_df.columns = ['Keyword', 'Count', 'Target', 'Status']
                st.dataframe(lsi_df)
            else:
                st.write("No LSI keywords analyzed.")
            st.markdown("### Entities Usage")
            if analysis['entities']:
                entity_df = pd.DataFrame(analysis['entities']).T.reset_index()
                entity_df.columns = ['Entity', 'Found', 'Status']
                st.dataframe(entity_df)
            else:
                st.write("No entities analyzed.")

if st.session_state.get("step", 1) == 3:
    generate_content_flow()

# Footer
st.markdown("---")
st.markdown("SEO Content Generator 2025")