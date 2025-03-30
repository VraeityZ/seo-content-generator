import streamlit as st
import pandas as pd
import re
import warnings
from main import parse_cora_report, generate_content, generate_meta_and_headings, markdown_to_html, generate_content_from_headings
import os
from collections import Counter
import io
import zipfile
import json
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl.styles.stylesheet")

# Streamlit page configuration
st.set_page_config(
    page_title="SEO Content Generator",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://www.extremelycoolapp.com/help',
        'Report a bug': "https://www.extremelycoolapp.com/bug",
        'About': "# SEO Content Generator\nThis app helps you generate SEO-optimized content based on CORA report data."
    }
)

# Initialize session state variables
if 'step' not in st.session_state:
    st.session_state['step'] = 1  # Starting step
if 'generated_markdown' not in st.session_state:
    st.session_state['generated_markdown'] = ""
if 'generated_html' not in st.session_state:
    st.session_state['generated_html'] = ""
if 'save_path' not in st.session_state:
    st.session_state['save_path'] = ""
if 'meta_and_headings' not in st.session_state:
    st.session_state['meta_and_headings'] = {}
if 'original_meta_and_headings' not in st.session_state:
    st.session_state['original_meta_and_headings'] = {}
if 'original_requirements' not in st.session_state:
    st.session_state['original_requirements'] = {}
if 'requirements' not in st.session_state:
    st.session_state['requirements'] = {}
if 'configured_headings' not in st.session_state:
    st.session_state['configured_headings'] = {}
if 'file' not in st.session_state:
    st.session_state['file'] = None
if 'anthropic_api_key' not in st.session_state:
    st.session_state['anthropic_api_key'] = ""
if 'openai_api' not in st.session_state:
    st.session_state['openai_api'] = ""
if 'auto_generate_content' not in st.session_state:
    st.session_state['auto_generate_content'] = False

# Add CSS to make index column fit content
st.markdown("""
<style>
    .row_heading.level0 {width: auto !important; white-space: nowrap;}
    .blank {width: auto !important; white-space: nowrap;}
</style>
""", unsafe_allow_html=True)

# Utility function to analyze content
def analyze_content(markdown_content, requirements):
    """Analyze the generated content against the SEO requirements."""
    analysis = {
        "primary_keyword": requirements.get("primary_keyword", ""),
        "primary_keyword_count": 0,
        "word_count": 0,
        "variations": requirements.get("variations", []),
        "heading_structure": {"H1": 0, "H2": 0, "H3": 0, "H4": 0, "H5": 0, "H6": 0},
        "lsi_keywords": {},
        "entities": {}
    }
    
    # Remove markdown formatting from content for more accurate word counting
    # This is a simple approach - for production, consider using a proper markdown parser
    text_content = re.sub(r'[#*_`~]', ' ', markdown_content)
    
    # Use word boundaries to ensure we only count whole words
    words = re.findall(r'\b\w+\b', text_content.lower())
    analysis["word_count"] = len(words)
    
    primary_keyword = requirements.get("primary_keyword", "").lower()
    if primary_keyword:
        # Ensure we only count complete keyword matches with word boundaries
        analysis["primary_keyword_count"] = len(re.findall(rf'\b{re.escape(primary_keyword)}\b', text_content.lower()))
    
    heading_pattern = r"^(#{1,6})\s+(.+)$"
    for line in markdown_content.split("\n"):
        match = re.match(heading_pattern, line)
        if match:
            heading_level = f"H{len(match.group(1))}"
            analysis["heading_structure"][heading_level] += 1
    
    # Process variations if they exist
    variations = requirements.get("variations", [])
    if variations:
        analysis["variations"] = {}
        for var in variations:
            count = len(re.findall(rf'\b{re.escape(var.lower())}\b', text_content.lower()))
            status = "✅" if count > 0 else "❌"
            analysis["variations"][var] = {
                "count": count,
                "status": status
            }
    
    # Process LSI keywords
    lsi_keywords = requirements.get("lsi_keywords", {})
    if isinstance(lsi_keywords, list):
        lsi_keywords_dict = {kw: 1 for kw in lsi_keywords}
        lsi_keywords = lsi_keywords_dict

    for keyword, target_count in lsi_keywords.items():
        # Ensure we only count complete keyword matches with word boundaries
        count = len(re.findall(rf'\b{re.escape(keyword.lower())}\b', text_content.lower()))
        status = "✅" if count >= target_count else "❌"
        analysis["lsi_keywords"][keyword] = {
            "count": count,
            "target": target_count,
            "status": status
        }
    
    # Process entities
    entities = requirements.get("entities", [])
    for entity in entities:
        # Ensure we only count complete entity matches with word boundaries
        count = len(re.findall(rf'\b{re.escape(entity.lower())}\b', text_content.lower()))
        status = "✅" if count > 0 else "❌"
        analysis["entities"][entity] = {
            "count": count,
            "status": status
        }
        
    return analysis

def render_extracted_data():
    """
    Displays a persistent expander titled 'View Complete Extracted Data'
    showing the extracted SEO requirements in tables. If configured settings
    exist (headings in Step 2 or word count in Step 3), they are appended.
    """
    requirements = st.session_state.get("requirements", {})
    
    with st.expander("View Complete Extracted Data", expanded=True):
        st.markdown("### Extracted Requirements")
        st.write(f"**Primary Keyword:** {requirements.get('primary_keyword', 'Not found')}")
        st.write(f"**Word Count Target:** {requirements.get('word_count', 'N/A')} words")
        
        # Variations
        variations = requirements.get("variations", [])
        if variations:
            st.write("**Keyword Variations:**")
            st.write(", ".join(f"*{var}*" for var in variations))
        else:
            st.write("**Keyword Variations:** None")
        
        # LSI Keywords
        lsi_keywords = requirements.get("lsi_keywords", {})
        if lsi_keywords:
            st.write("**LSI Keywords:**")
            if isinstance(lsi_keywords, dict):
                lsi_df = pd.DataFrame({
                    "Keyword": list(lsi_keywords.keys()),
                    "Frequency": list(lsi_keywords.values())
                })
            else:
                lsi_df = pd.DataFrame({"Keyword": lsi_keywords})
            st.dataframe(lsi_df, use_container_width=True, height=200, hide_index=True)
        else:
            st.write("**LSI Keywords:** None")
        
        # Entities
        entities = requirements.get("entities", [])
        if entities:
            st.write("**Entities:**")
            ent_df = pd.DataFrame({"Entity": entities})
            st.dataframe(ent_df, use_container_width=True, height=200, hide_index=True)
        else:
            st.write("**Entities:** None")
        
        # Roadmap Requirements (excluding heading counts)
        roadmap_reqs = requirements.get("requirements", {})
        if roadmap_reqs:
            filtered_reqs = {
                k: v for k, v in roadmap_reqs.items() 
                if not k.startswith("Number of H") and k != "Number of heading tags" and k not in ["CP480", "CP380"]
            }
            if filtered_reqs:
                st.markdown("**Roadmap Requirements:**")
                roadmap_df = pd.DataFrame({
                    "Requirement": list(filtered_reqs.keys()),
                    "Value": list(filtered_reqs.values())
                })
                st.dataframe(roadmap_df, use_container_width=True, height=200, hide_index=True)
            else:
                st.write("**Roadmap Requirements:** None")
        else:
            st.write("**Roadmap Requirements:** None")
        
        # Configured Settings for Headings (Step 2)
        if "configured_headings" in st.session_state:
            cfg = st.session_state["configured_headings"]
            st.markdown("### Configured Settings (Headings)")
            st.write(f"H2 Headings: {cfg.get('h2', 'N/A')}")
            st.write(f"H3 Headings: {cfg.get('h3', 'N/A')}")
            st.write(f"H4 Headings: {cfg.get('h4', 'N/A')}")
            st.write(f"H5 Headings: {cfg.get('h5', 'N/A')}")
            st.write(f"H6 Headings: {cfg.get('h6', 'N/A')}")
            st.write(f"Total Headings (includes H1): {cfg.get('total', 'N/A')}")
        
        # Configured Settings for Word Count (Step 3)
        if "configured_settings" in st.session_state:
            cs = st.session_state["configured_settings"]
            st.markdown("### Configured Settings (Content)")
            st.write(f"Word Count Target: {cs.get('word_count', 'N/A')}")

# Create a modal dialog to show prompts
def show_prompt_modal(prompt_title, prompt_content):
    """Show a popup modal with the full prompt."""
    modal = st.expander(f"Click to view: {prompt_title}", expanded=False)
    with modal:
        st.code(prompt_content, language="markdown")

# Footer
st.markdown("---")
st.markdown("SEO Content Generator 2025")

# Main app title and description
st.title("SEO Content Generator")
st.markdown("""
This application generates SEO-optimized content based on CORA report data. 
Upload your CORA report, adjust heading requirements, and click 'Generate Content'.
""")

# Sidebar for API configuration
with st.sidebar:
    st.title("Configuration")
    
    anthropic_api_key = st.text_input(
        "Anthropic API Key", 
        value="",
        type="password",
        help="Enter your Anthropic API key. This will not be stored permanently."
    )
    st.session_state['anthropic_api_key'] = anthropic_api_key
    
    openai_api = st.text_input(
        "OpenAI API Key (Optional)",
        value="",
        type="password",
        help="Enter your OpenAI API key if you want to use OpenAI models."
    )
    st.session_state['openai_api'] = openai_api
    
    if not anthropic_api_key:
        st.warning("Please enter your Anthropic API key to use this app.")

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
                
            # Save to session state
            st.session_state['requirements'] = requirements
            st.session_state['step'] = 2
        
        st.success("CORA report processed successfully!")

    except Exception as e:
        st.error(f"Error processing CORA report: {str(e)}")
        st.write(f"Exception type: {type(e).__name__}")
        st.write(f"Exception message: {str(e)}")
        import traceback
        st.code(traceback.format_exc())

if uploaded_file is not None:
    st.session_state['file'] = uploaded_file
    st.success(f"Successfully uploaded: {uploaded_file.name}")
    
    if st.button("Extract Requirements"):
        process_upload()
else:
    st.info("Please upload a CORA report to get started.")

# Function to handle content generation flow
def generate_content_flow():
    """Generate and display content."""
    content_exists = 'generated_markdown' in st.session_state and len(st.session_state.get('generated_markdown', '')) > 0
    
    print(f"CONTENT_FLOW: Content exists in session: {content_exists}")
    if content_exists:
        print(f"CONTENT_FLOW: Content length: {len(st.session_state['generated_markdown'])}")
    
    if not content_exists:
        if st.session_state.get('auto_generate_content', False):
            print("CONTENT_FLOW: Auto-generate flag is set, initiating API call")
            st.session_state.pop('auto_generate_content', None)
            try:
                with st.status("Generating content...") as status:
                    status.update(label="🧠 Claude is thinking about your content...", state="running")
                    
                    updated_requirements = dict(st.session_state.requirements)
                    
                    print(f"CONTENT_FLOW: Word count: {updated_requirements.get('word_count', 'Not set')}")
                    print(f"CONTENT_FLOW: LSI limit: {updated_requirements.get('lsi_limit', 'Not set')}")
                    
                    result = generate_content_from_headings(
                        updated_requirements,
                        st.session_state.meta_and_headings.get("heading_structure", ""),
                        {"anthropic_api_key": st.session_state.get('anthropic_api_key', '')}
                    )
                    
                    markdown_content = result.get('markdown', '')
                    html_content = result.get('html', '')
                    save_path = result.get('filename', '')
                    token_usage = result.get('token_usage', {})
                    
                    print(f"CONTENT_FLOW: Content generated successfully, length: {len(markdown_content)}")
                    
                    st.session_state['generated_markdown'] = markdown_content
                    
                    if html_content:
                        st.session_state['generated_html'] = html_content
                    else:
                        try:
                            import markdown
                            st.session_state['generated_html'] = markdown.markdown(markdown_content)
                        except Exception as e:
                            st.session_state['generated_html'] = "<p>Error displaying HTML preview</p>"
                            status.update(label=f"⚠️ Content generated, but HTML preview may have errors: {str(e)}", state="complete")
                    
                    st.session_state['save_path'] = save_path
                    
                    if token_usage:
                        input_cost = (token_usage['input_tokens'] / 1000000) * 3
                        output_cost = (token_usage['output_tokens'] / 1000000) * 15
                        total_cost = input_cost + output_cost
                        
                        st.sidebar.markdown("### Content Generation Token Usage")
                        col1, col2, col3 = st.sidebar.columns(3)
                        col1.metric("Input Tokens", token_usage['input_tokens'], delta=f"${input_cost:.4f}", delta_color="off")
                        col2.metric("Output Tokens", token_usage['output_tokens'], delta=f"${output_cost:.4f}", delta_color="off")
                        col3.metric("Total Tokens", token_usage['total_tokens'], delta=f"${total_cost:.4f}", delta_color="off")
                        
                        # Preserve heading generation token usage if it exists
                        if 'heading_token_usage' in st.session_state:
                            heading_token_usage = st.session_state['heading_token_usage']
                            heading_input_cost = (heading_token_usage['input_tokens'] / 1000000) * 3
                            heading_output_cost = (heading_token_usage['output_tokens'] / 1000000) * 15
                            heading_total_cost = heading_input_cost + heading_output_cost
                            
                            st.sidebar.markdown("### Heading Generation Token Usage")
                            col1, col2, col3 = st.sidebar.columns(3)
                            col1.metric("Input Tokens", heading_token_usage['input_tokens'], delta=f"${heading_input_cost:.4f}", delta_color="off")
                            col2.metric("Output Tokens", heading_token_usage['output_tokens'], delta=f"${heading_output_cost:.4f}", delta_color="off")
                            col3.metric("Total Tokens", heading_token_usage['total_tokens'], delta=f"${heading_total_cost:.4f}", delta_color="off")
                    
                    status.update(label="✅ Content generated successfully!", state="complete")
                print("CONTENT_FLOW: Content saved to session state, forcing rerun")
                st.rerun()
            except Exception as e:
                st.error(f"Error generating content: {str(e)}")
                import traceback
                st.text_area("Error Details", traceback.format_exc(), height=300)
        else:
            if 'generate_full_content_button' not in st.session_state or not st.session_state['generate_full_content_button']:
                st.info("Click 'Generate Full Content' in the previous step to generate the content.")
                if st.button("Back to Edit Meta and Headings"):
                    st.session_state['step'] = 2.5
                    st.rerun()
    
    if content_exists:
        st.success("Content generated successfully!")
        st.subheader("Generated Content")
        
        if 'generated_html' not in st.session_state or not st.session_state['generated_html']:
            try:
                import markdown
                st.session_state['generated_html'] = markdown.markdown(st.session_state['generated_markdown'])
            except Exception as e:
                st.session_state['generated_html'] = "<p>Error displaying HTML preview</p>"
                st.warning(f"Could not generate HTML preview: {str(e)}")
        
        tab1, tab2, tab3 = st.tabs(["Preview", "Markdown", "Analysis"])
        
        with tab1:
            st.markdown("""
            <style>
            .content-preview {
                font-family: 'Helvetica', 'Arial', sans-serif;
                line-height: 1.6;
                padding: 20px;
                background-color: #0b0e12;
                border-radius: 5px;
                overflow: scroll;
                box-shadow: 0px 0px 5px 2px rgb(87 87 87 / 35%);
                height: 400px;
            }
            .content-preview h1, .content-preview h2, .content-preview h3, .content-preview h4, .content-preview h5, .content-preview h6 { color: #fff; }
            .content-preview h1 { font-size: 28px; margin-top: 20px; }
            .content-preview h2 { font-size: 24px; margin-top: 18px; }
            .content-preview h3 { font-size: 20px; margin-top: 16px; }
            .content-preview p { margin-bottom: 16px; }
            </style>
            """, unsafe_allow_html=True)
            html_with_styles = f'<div class="content-preview">{st.session_state["generated_html"]}</div>'
            print(html_with_styles)
            st.html(html_with_styles)
        
        with tab2:
            st.markdown("### Raw Markdown")
            st.text_area("Markdown Content", st.session_state['generated_markdown'], height=400, key="raw_markdown_text_area")
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
                html_content = st.session_state['generated_html']
                analysis = analyze_content(html_content, st.session_state.requirements)
                
                st.markdown("### Content Analysis")
                st.write(f"**Primary Keyword:** {analysis['primary_keyword']}")
                st.write(f"**Primary Keyword Count:** {analysis['primary_keyword_count']}")
                st.write(f"**Word Count:** {analysis['word_count']}")
                
                headings = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
                heading_counts = []
                for h in headings:
                    count = len(re.findall(f"<{h}[^>]*>.*?</{h}>", html_content, flags=re.IGNORECASE | re.DOTALL))
                    analysis[f'{h}_count'] = count
                    heading_counts.append(f"{h.upper()} Tags: {count}")
                st.write(" | ".join(heading_counts))
                
                if analysis.get('lsi_keywords'):
                    total_lsi = sum(info['count'] for info in analysis['lsi_keywords'].values())
                    st.write("**LSI Keyword Usage**")
                    st.write(f"*LSI Keyword Count:* {total_lsi}")
                    lsi_density = (total_lsi / analysis['word_count']) * 100 if analysis['word_count'] > 0 else 0
                    st.write(f"*LSI Keyword Density:* {lsi_density:.2f}%")
                    lsi_data = [{'Keyword': k, 'Count': info['count']} for k, info in analysis['lsi_keywords'].items()]
                    st.dataframe(pd.DataFrame(lsi_data), use_container_width=True, height=300)
                
                if analysis.get('variations'):
                    st.write("**Variation Usage:**")
                    variations = analysis['variations']
                    content_lower = html_content.lower()
                    variations_count = {v: content_lower.count(v.lower()) for v in variations}
                    total_variations = sum(variations_count.values())
                    st.write(f"*Variation Count:* {total_variations}")
                    var_density = (total_variations / analysis['word_count']) * 100 if analysis['word_count'] > 0 else 0
                    st.write(f"*Variation Density:* {var_density:.2f}%")
                    var_data = [{'Variation': v, 'Count': cnt} for v, cnt in variations_count.items()]
                    st.dataframe(pd.DataFrame(var_data), use_container_width=True, height=300)
                
                if analysis.get('entities'):
                    st.write("**Entity Usage:**")
                    entities = analysis['entities']
                    if isinstance(entities, dict):
                        entities_count = {ent: int(val.get('count', 0)) for ent, val in entities.items()}
                    elif isinstance(entities, list):
                        entities_count = dict(Counter(entities))
                    else:
                        entities_count = {}
                    total_entities = sum(entities_count.values())
                    st.write(f"*Entity Count:* {total_entities}")
                    ent_density = (total_entities / analysis['word_count']) * 100 if analysis['word_count'] > 0 else 0
                    st.write(f"*Entity Density:* {ent_density:.2f}%")
                    ent_data = [{'Entity': ent, 'Count': cnt} for ent, cnt in entities_count.items()]
                    st.dataframe(pd.DataFrame(ent_data), use_container_width=True, height=300)
                
                overall_count = (
                    sum(info['count'] for info in analysis.get('lsi_keywords', {}).values()) +
                    sum(variations_count.values() if analysis.get('variations') else 0) +
                    total_entities
                )
                overall_density = (overall_count / analysis['word_count']) * 100 if analysis['word_count'] > 0 else 0
                st.write(f"**Total Keyword Count:** {overall_count}")
                st.write(f"**Total Density:** {overall_density:.2f}%")
        
        if st.button("Regenerate Content"):
            del st.session_state['generated_markdown']
            del st.session_state['generated_html']
            st.session_state['auto_generate_content'] = True
            st.rerun()
        
        if st.button("Start Over"):
            for key in ['generated_markdown', 'generated_html', 'save_path', 'meta_and_headings']:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state['step'] = 2
            st.rerun()

if st.session_state.get("step", 1) == 2.5:
    requirements = st.session_state.requirements
    meta_and_headings = st.session_state.meta_and_headings
    
    if 'token_usage' in meta_and_headings:
        token_usage = meta_and_headings['token_usage']
        input_cost = (token_usage['input_tokens'] / 1000000) * 3
        output_cost = (token_usage['output_tokens'] / 1000000) * 15
        total_cost = input_cost + output_cost
        
        st.sidebar.markdown("### Token Usage")
        col1, col2, col3 = st.sidebar.columns(3)
        col1.metric("Input Tokens", token_usage['input_tokens'], delta=f"${input_cost:.4f}", delta_color="off")
        col2.metric("Output Tokens", token_usage['output_tokens'], delta=f"${output_cost:.4f}", delta_color="off")
        col3.metric("Total Tokens", token_usage['total_tokens'], delta=f"${total_cost:.4f}", delta_color="off")
    
    st.subheader("Generated Meta Information and Heading Structure")
    
    if 'original_meta_and_headings' not in st.session_state and 'meta_and_headings' in st.session_state:
        st.session_state['original_meta_and_headings'] = st.session_state['meta_and_headings'].copy()
    
    if 'original_requirements' not in st.session_state and 'requirements' in st.session_state:
        st.session_state['original_requirements'] = st.session_state['requirements'].copy()
    
    meta_title_input = st.text_input(
        "Meta Title", 
        value=meta_and_headings.get("meta_title", ""), 
        help="Edit the generated meta title if needed."
    )
    
    ideal_title_length = requirements.get('requirements', {}).get('CP480', 60)
    min_title_length = max(int(ideal_title_length * 0.8), 40)
    
    meta_title_chars = len(meta_title_input)
    st.caption(f"Character count: {meta_title_chars}/{ideal_title_length} " + 
              (f"✅" if min_title_length <= meta_title_chars <= ideal_title_length else f"⚠️ Ideal length is {min_title_length}-{ideal_title_length} characters"))
    
    meta_description_input = st.text_area(
        "Meta Description", 
        value=meta_and_headings.get("meta_description", ""), 
        height=100, 
        help="Edit the generated meta description if needed."
    )
    
    ideal_desc_length = requirements.get('requirements', {}).get('CP380', 160)
    min_desc_length = max(int(ideal_desc_length * 0.75), 120)
    
    meta_desc_chars = len(meta_description_input)
    st.caption(f"Character count: {meta_desc_chars}/{ideal_desc_length} " + 
              (f"✅" if min_desc_length <= meta_desc_chars <= ideal_desc_length else f"⚠️ Ideal length is {min_desc_length}-{ideal_desc_length} characters"))
    
    word_count = requirements.get('word_count', 1500)
    word_count_input = st.number_input(
        "Word Count Target", 
        min_value=500,
        max_value=10000,
        value=word_count,
        step=100,
        help="Edit the target word count for content generation."
    )
    
    col1, col2 = st.columns(2)
    with col1:
        lsi_limit = requirements.get('lsi_limit', 100)
        lsi_limit_input = st.number_input(
            "Number of LSI Keywords to Include", 
            min_value=10,
            max_value=500,
            value=lsi_limit,
            step=10,
            help="Limit the number of LSI keywords used in content generation."
        )
    
    with col2:
        lsi_keywords = requirements.get('lsi_keywords', {})
        if isinstance(lsi_keywords, dict):
            total_lsi = len(lsi_keywords)
        elif isinstance(lsi_keywords, list):
            total_lsi = len(lsi_keywords)
        else:
            total_lsi = 0
            
        st.write(f"Available LSI Keywords: {total_lsi}")
        st.caption(f"Using top {min(lsi_limit_input, total_lsi)} LSI keywords")
    
    heading_structure_input = st.text_area(
        "Heading Structure", 
        value=meta_and_headings.get("heading_structure", ""), 
        height=400, 
        help="Edit the generated heading structure if needed."
    )
    
    def generate_full_content_button():
        print("===== GENERATE FULL CONTENT BUTTON CLICKED =====")
        if 'generated_markdown' in st.session_state:
            print("Clearing existing generated_markdown from session state")
            del st.session_state['generated_markdown']
        if 'generated_html' in st.session_state:
            print("Clearing existing generated_html from session state")
            del st.session_state['generated_html']
        
        if 'requirements' in st.session_state:
            print(f"Updating word_count to {st.session_state.get('word_count_input', 1250)} and lsi_limit to {st.session_state.get('lsi_limit_input', 20)}")
            st.session_state.requirements['word_count'] = st.session_state.get('word_count_input', 1250)
            st.session_state.requirements['lsi_limit'] = st.session_state.get('lsi_limit_input', 20)
        
        print("SETTING auto_generate_content to True to force API call")
        st.session_state['auto_generate_content'] = True
        print("Setting step to 3 for content generation")
        st.session_state['step'] = 3
        st.rerun()
    
    col1, col2 = st.columns(2)
    with col1:
        generate_full_content = st.button("Generate Full Content", use_container_width=True, on_click=generate_full_content_button)

    with col2:
        if st.button("Back to Requirements"):
            st.session_state['step'] = 2
            st.rerun()

if st.session_state.get("step", 1) == 2:
    requirements = st.session_state.requirements
    meta_and_headings = st.session_state.meta_and_headings
    
    render_extracted_data()
    
    st.subheader("Configure Headings")
    st.markdown("Adjust the number of headings if needed. These values will be used in the prompt.")
    
    default_h2 = requirements.get('requirements', {}).get('Number of H2 tags', 4)
    default_h3 = requirements.get('requirements', {}).get('Number of H3 tags', 8)
    default_h4 = requirements.get('requirements', {}).get('Number of H4 tags', 0)
    default_h5 = requirements.get('requirements', {}).get('Number of H5 tags', 0)
    default_h6 = requirements.get('requirements', {}).get('Number of H6 tags', 0)
    
    heading_sum = 1 + default_h2 + default_h3 + default_h4 + default_h5 + default_h6
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        h2_count = st.number_input("H2 Headings", min_value=0, max_value=100, value=default_h2, key='h2_config')
    with col2:
        h3_count = st.number_input("H3 Headings", min_value=0, max_value=100, value=default_h3, key='h3_config')
    with col3:
        h4_count = st.number_input("H4 Headings", min_value=0, max_value=100, value=default_h4, key='h4_config')
    with col4:
        h5_count = st.number_input("H5 Headings", min_value=0, max_value=100, value=default_h5, key='h5_config')
    with col5:
        h6_count = st.number_input("H6 Headings", min_value=0, max_value=100, value=default_h6, key='h6_config')
    
    total_headings = 1 + h2_count + h3_count + h4_count + h5_count + h6_count
    with col6:
        st.metric("Total Headings (includes H1)", total_headings)
    
    st.session_state.configured_headings = {
        "h2": h2_count,
        "h3": h3_count,
        "h4": h4_count,
        "h5": h5_count,
        "h6": h6_count,
        "total": total_headings
    }
    
    def show_prompt_modal(prompt_title, prompt_content):
        with st.expander(f"🔍 {prompt_title}", expanded=True):
            st.code(prompt_content)
    
    col1, col2 = st.columns(2)
    with col1:
        generate_button = st.button("Generate Meta Title, Description and Headings", use_container_width=True)
    
    if generate_button:
        if not st.session_state.get('anthropic_api_key', ''):
            st.error("Please enter your Anthropic API key in the sidebar.")
        else:
            with st.spinner("🔄 Generating meta information and heading structure..."):
                try:
                    settings = {
                        'model': 'claude',
                        'anthropic_api_key': st.session_state.get('anthropic_api_key', ''),
                    }
                    
                    status = st.status("Generating meta and headings...", expanded=True)
                    status.write("📤 Sending request to Claude API...")
                    
                    api_key = st.session_state.get('anthropic_api_key', '')
                    
                    if not api_key:
                        st.error("Please provide an API key in the sidebar.")
                        status.update(label="Error", state="error")
                    else:
                        if 'configured_headings' in st.session_state:
                            requirements = st.session_state.requirements.copy()
                            
                            if 'requirements' not in requirements:
                                requirements['requirements'] = {}
                            
                            requirements['requirements']['Number of H2 tags'] = st.session_state.configured_headings['h2']
                            requirements['requirements']['Number of H3 tags'] = st.session_state.configured_headings['h3']
                            requirements['requirements']['Number of H4 tags'] = st.session_state.configured_headings['h4']
                            requirements['requirements']['Number of H5 tags'] = st.session_state.configured_headings['h5']
                            requirements['requirements']['Number of H6 tags'] = st.session_state.configured_headings['h6']
                            requirements['requirements']['Number of heading tags'] = st.session_state.configured_headings['total']
                        else:
                            requirements = st.session_state.requirements

                        total_headings = (
                            requirements.get('requirements', {}).get('Number of H2 tags', 4) +
                            requirements.get('requirements', {}).get('Number of H3 tags', 8) +
                            requirements.get('requirements', {}).get('Number of H4 tags', 0) +
                            requirements.get('requirements', {}).get('Number of H5 tags', 0) +
                            requirements.get('requirements', {}).get('Number of H6 tags', 0)
                        )
                        status.write(f"🧠 Claude is thinking about {total_headings + 1} headings for \"{requirements.get('primary_keyword', '')}\"...")
                        
                        meta_and_headings = generate_meta_and_headings(requirements, settings)
                        status.write("✅ Response received! Processing results...")
                        
                        st.session_state['meta_and_headings'] = meta_and_headings
                        st.session_state['original_meta_and_headings'] = dict(meta_and_headings)
                        st.session_state['original_requirements'] = dict(requirements)
                        st.session_state['step'] = 2.5  # Move to heading editing step
                        status.update(label="✅ Meta and headings generated successfully!", state="complete")
                        st.rerun()
                except Exception as e:
                    error_msg = f"Error generating meta and headings: {str(e)}"
                    st.error(error_msg)
                    st.error("⚠️ Please check the error above before proceeding.")
                    import traceback
                    st.text_area("Error Details", traceback.format_exc(), height=300)
                    st.warning("To retry, please click the 'Generate Meta Title...' button again.")
    
    if st.button("Back to Requirements"):
        st.session_state['step'] = 2
        st.rerun()

if st.session_state.get("step", 1) == 3:
    print("==== ENTERING STEP 3 CONTENT GENERATION FLOW ====")
    print(f"Session State Keys: {list(st.session_state.keys())}")
    print(f"Has 'generated_markdown' in session: {'generated_markdown' in st.session_state}")
    
    if st.session_state.get('auto_generate_content', False):
        print("Auto generate content is TRUE - clearing any existing content")
        if 'generated_markdown' in st.session_state:
            print("FORCING REMOVAL of generated_markdown in step 3 initialization")
            del st.session_state['generated_markdown']
        if 'generated_html' in st.session_state:
            print("FORCING REMOVAL of generated_html in step 3 initialization")
            del st.session_state['generated_html']

    st.session_state.configured_settings = {"word_count": st.session_state.requirements.get("word_count", 1500)}
    
    render_extracted_data()
    
    st.subheader("Step 3: Generate Content")
    generate_content_flow()

def create_download_zip():
    md_content = st.session_state.get("generated_markdown", "")
    html_content = st.session_state.get("generated_html", "")
    requirements = st.session_state.get("requirements", {})
    analysis = analyze_content(html_content, requirements)
    
    extracted_data = f"Primary Keyword: {requirements.get('primary_keyword', 'Not found')}\n"
    extracted_data += f"Word Count Target: {requirements.get('word_count', 'N/A')} words\n"
    
    variations = requirements.get("variations", [])
    extracted_data += "Keyword Variations: " + (", ".join(variations) if variations else "None") + "\n"
    
    lsi_keywords = requirements.get("lsi_keywords", {})
    if isinstance(lsi_keywords, dict):
        lsi_str = "\n".join([f"{k}: {v}" for k, v in lsi_keywords.items()])
    else:
        lsi_str = ", ".join(lsi_keywords)
    extracted_data += "LSI Keywords:\n" + (lsi_str if lsi_str else "None") + "\n"
    
    entities = requirements.get("entities", [])
    extracted_data += "Entities: " + (", ".join(entities) if entities else "None") + "\n"
    
    roadmap_reqs = requirements.get("requirements", {})
    filtered_reqs = {k: v for k, v in roadmap_reqs.items() 
                     if not k.startswith("Number of H") and k != "Number of heading tags" and k not in ["CP480", "CP380"]
    }
    if filtered_reqs:
        roadmap_str = "\n".join([f"{k}: {v}" for k, v in filtered_reqs.items()])
    else:
        roadmap_str = "None"
    extracted_data += "Roadmap Requirements:\n" + roadmap_str + "\n"
    
    if "configured_headings" in st.session_state:
        cfg = st.session_state["configured_headings"]
        cfg_str = (
            f"H2 Headings: {cfg.get('h2', 'N/A')}\n"
            f"H3 Headings: {cfg.get('h3', 'N/A')}\n"
            f"H4 Headings: {cfg.get('h4', 'N/A')}\n"
            f"H5 Headings: {cfg.get('h5', 'N/A')}\n"
            f"H6 Headings: {cfg.get('h6', 'N/A')}\n"
            f"Total Headings (includes H1): {cfg.get('total', 'N/A')}\n"
        )
        extracted_data += "Configured Settings (Headings):\n" + cfg_str + "\n"
    if "configured_settings" in st.session_state:
        cs = st.session_state["configured_settings"]
        extracted_data += f"Configured Settings (Content):\nWord Count Target: {cs.get('word_count', 'N/A')}\n"
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("content.html", html_content)
        zip_file.writestr("content.md", md_content)
        zip_file.writestr("analysis.json", json.dumps(analysis, indent=4))
        zip_file.writestr("extracted_data.txt", extracted_data)
    zip_buffer.seek(0)
    return zip_buffer

zip_buffer = create_download_zip()
st.download_button(
    label="Download All as ZIP",
    data=zip_buffer,
    file_name="seo_content_package.zip",
    mime="application/zip"
)
