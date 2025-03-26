import streamlit as st
import pandas as pd
import anthropic
import json
import re
import warnings
from main import parse_cora_report, generate_content, generate_meta_and_headings, markdown_to_html, generate_content_from_headings
import time

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl.styles.stylesheet")

# Streamlit page configuration
st.set_page_config(
    page_title="SEO Content Generator",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

# Update the session state to include step 2.5 (heading editing)
if 'step' not in st.session_state:
    st.session_state['step'] = 1  # Starting step

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
            h6_control = st.session_state.get('h6_control', 0)
            
            # Override heading structure with user inputs if provided
            if h2_control > 0:
                requirements["heading_structure"]["h2"] = h2_control
            if h3_control > 0:
                requirements["heading_structure"]["h3"] = h3_control
            if h4_control > 0:
                requirements["heading_structure"]["h4"] = h4_control
            if h5_control > 0:
                requirements["heading_structure"]["h5"] = h5_control
            if h6_control > 0:
                requirements["heading_structure"]["h6"] = h6_control
            
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
               f"H5={requirements['heading_structure'].get('h5', 0)}, " +
               f"H6={requirements['heading_structure'].get('h6', 0)}")
        
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
        h6_control = st.number_input("Number of H6 headings", min_value=0, max_value=20, value=0, step=1, key='h6_control')
    
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
        
        st.markdown("### Keyword Variations")
        variations = requirements.get('variations', [])
        if variations:
            st.write(f"Found {len(variations)} variations:")
            variations_df = pd.DataFrame({
                'Variation': variations
            })
            st.dataframe(variations_df, use_container_width=True, height=300, hide_index=True)
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
            st.dataframe(lsi_df, use_container_width=True, height=300, hide_index=True)
        else:
            st.write("No LSI keywords found")
        
        st.markdown("### Entities")
        entities = requirements.get('entities', [])
        if entities:
            st.write(f"Found {len(entities)} entities:")
            entities_df = pd.DataFrame({
                'Entity': entities
            })
            st.dataframe(entities_df, use_container_width=True, height=300, hide_index=True)
        else:
            st.write("No entities found")
        
        st.markdown("### Heading Structure")
        heading_structure = requirements.get('heading_structure', {})
        if heading_structure:
            h_df = pd.DataFrame({
                'Heading Level': [f"H{i}" for i in range(1, 6)],
                'Count': [1] + [heading_structure.get(f"h{i}", 0) for i in range(2, 6)]
            })
            st.dataframe(h_df, use_container_width=True, height=300, hide_index=True)
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
            st.dataframe(req_df, use_container_width=True, height=300, hide_index=True)
        else:
            st.write("No specific requirements found")
    
    # Define functions for displaying prompts
    def show_prompt_modal(prompt_title, prompt_content):
        """Display a prompt in an expander."""
        with st.expander(f"🔍 {prompt_title}", expanded=True):
            st.code(prompt_content)
    
    # Generate Heading Structure button
    col1, col2 = st.columns([5, 1])
    with col1:
        generate_button = st.button("Generate Meta Title, Description and Headings", use_container_width=True)
    with col2:
        if st.button("See Prompt", type="secondary", use_container_width=True):
            # Create variables for display that will be substituted in main.py
            primary_keyword = st.session_state.requirements.get('primary_keyword', '[primary keyword]')
            variations = st.session_state.requirements.get('keyword_variations', [])[:5] if st.session_state.requirements.get('keyword_variations') else []
            word_count = st.session_state.requirements.get('word_count', 1500)
            
            # Format LSI keywords similar to how it's done in main.py
            lsi_keywords = st.session_state.requirements.get('top_lsi_keywords', [])
            lsi_formatted = ""
            if isinstance(lsi_keywords, list):
                for keyword in lsi_keywords[:10]:
                    lsi_formatted += f"  - {keyword}\n"
            else:
                lsi_formatted = "  - No LSI keywords available\n"
                
            # Format entities similar to how it's done in main.py
            entities = st.session_state.requirements.get('entities', [])[:10] if st.session_state.requirements.get('entities') else []
            
            # Get heading structure requirements (simplified as we don't have the exact values)
            heading_structure = {"h2": 4, "h3": 8, "h4": 0, "h5": 0, "h6": 0}
            
            # Show the exact prompt from main.py
            prompt_content = f"""Please create a meta title, meta description, and heading structure for an article about "{primary_keyword}".

<requirements>
- Primary Keyword: {primary_keyword}
- Variations to consider: {', '.join(variations)}
- Word Count Target: {word_count} words
- LSI Keywords to Include:
{lsi_formatted}
- Entities to Include: {', '.join(entities)}
</requirements>

<step 1>
Using the information and requirements provided tackle the SEO-optimized content. First, establish the key elements required:
- Title Tag:
- Meta Description:
- Headings Tags:
Please follow these guidelines for content structure:
1. Title: Include at least one instance of the main keyword and should be within 80 characters unless the requirements state otherwise.
2. Meta Description: 150 to 160 characters unless the requirements state otherwise.
3. Avoid Redundancy
3A. Definition: Prevent the repetition of identical factual information, phrasing, or ideas across different sections unless necessary for context or emphasis.
3B. Guidelines:
3B1. Each section should introduce new information or a fresh perspective.
3B2. Avoid reusing the same sentences or key points under different headings.
3B3. If overlap occurs, merge sections or reframe the content to add distinct value.
3C. Example:
3C1. Redundant: Two sections both state, '[Topic] is beneficial.'
3C2. Fixed: One section defines '[Topic]', while another explains another aspect of '[Topic]'.
4. Include an FAQ if the topic involves common user questions or multiple subtopics. FAQ Section should be an H2. The Questions must each be an H3.
5. Merge variations into single headings when possible (as long as it makes sense for readability, SEO and adheres with the heading requirements).
6. IMPORTANT: Ensure and Confirm each step in the Step 1 list is met.
</step 1>

<step 2>
1. Create a heading structure with the following requirements:
   - H1: Contains the primary keyword
   - H2: {heading_structure.get("h2", 0)} headings
   - H3: {heading_structure.get("h3", 0)} headings
   - H4: {heading_structure.get("h4", 0)} headings
   - H5: {heading_structure.get("h5", 0)} headings
   - H6: {heading_structure.get("h6", 0)} headings

2. The headings should:
   - Contain the primary keyword and/or variations where appropriate
   - Include some LSI keywords where relevant
   - Form a logical content flow
   - Be engaging and click-worthy while still being informative
   - Be formatted in Markdown (# for H1, ## for H2, etc.)
2. Confirm all the requirements are being met in the headings.
3. Confirm all the requirements are being met in the title.
4. Confirm all the requirements are being met in the description.
5.IMPORTANT: Ensure and Confirm each step in the Step 2 list is met.
</step 2>

Format your response exactly like this:
META TITLE: [Your meta title here]
META DESCRIPTION: [Your meta description here]
HEADING STRUCTURE:
[Complete markdown heading structure with # for H1, ## for H2, etc.]"""
            show_prompt_modal("Heading Generation Prompt", prompt_content)
    
    if generate_button:
        if not st.session_state.get('claude_api', ''):
            st.error("Please enter your Claude API key in the sidebar.")
        else:
            with st.spinner("🔄 Generating meta information and heading structure... This may take a minute..."):
                try:
                    settings = {
                        'model': 'claude',
                        'anthropic_api_key': st.session_state.get('claude_api', ''),
                        'openai_api_key': st.session_state.get('openai_api', ''),
                    }
                    
                    # Create and display a progress bar
                    progress_text = "Operation in progress. Please wait."
                    progress_bar = st.progress(0, text=progress_text)
                    for percent_complete in range(101):
                        time.sleep(0.05)  # Simulate API call time
                        progress_bar.progress(percent_complete, text=f"{progress_text} ({percent_complete}%)")
                    
                    # Generate meta and headings
                    meta_and_headings = generate_meta_and_headings(requirements, settings)
                    st.session_state['meta_and_headings'] = meta_and_headings
                    st.session_state['step'] = 2.5  # Move to heading editing step
                except Exception as e:
                    st.error(f"Error generating meta and headings: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
                st.rerun()
    
    # Back button to return to requirements
    if st.button("Back to Requirements"):
        st.session_state['step'] = 2
        st.rerun()

# Add a new step for editing the heading structure
if st.session_state.get("step", 1) == 2.5:
    requirements = st.session_state.requirements
    meta_and_headings = st.session_state.meta_and_headings
    
    st.subheader("Generated Meta Information and Heading Structure")
    
    # Display meta information
    meta_title = meta_and_headings.get("meta_title", "")
    meta_description = meta_and_headings.get("meta_description", "")
    heading_structure = meta_and_headings.get("heading_structure", "")
    
    st.markdown("### Meta Information")
    meta_title_input = st.text_input("Meta Title", value=meta_title)
    meta_description_input = st.text_area("Meta Description", value=meta_description, height=100)
    
    # Display and allow editing of heading structure
    st.markdown("### Heading Structure")
    heading_structure_input = st.text_area("Edit Heading Structure", value=heading_structure, height=400)
    
    # Continue to content generation
    col1, col2 = st.columns([5, 1])
    with col1:
        generate_full_content = st.button("Generate Full Content", use_container_width=True)
    with col2:
        if st.button("See Prompt", key="fullprompt", type="secondary", use_container_width=True):
            # Get values for prompt display
            primary_keyword = st.session_state.requirements.get('primary_keyword', '[primary keyword]')
            variations = st.session_state.requirements.get('keyword_variations', [])[:10] if st.session_state.requirements.get('keyword_variations') else []
            variations_text = ", ".join(variations) if variations else "None"
            
            # Format LSI keywords
            lsi_dict = {}
            lsi_keywords = st.session_state.requirements.get('lsi_keywords', [])
            lsi_formatted = ""
            if isinstance(lsi_keywords, list):
                for kw in lsi_keywords[:10]:
                    lsi_dict[kw] = 1  # Default frequency
                lsi_formatted = "\n".join([f"- '{kw}' => use at least {freq} times" for kw, freq in lsi_dict.items()])
            else:
                lsi_formatted = "- No LSI keywords available"
            
            # Format entities
            entities = st.session_state.requirements.get('entities', [])[:10] if st.session_state.requirements.get('entities') else []
            entities_text = "\n".join([f"- {entity}" for entity in entities])
            
            # Get metadata from session state
            meta_title = st.session_state.meta_and_headings.get("meta_title", "")
            meta_description = st.session_state.meta_and_headings.get("meta_description", "")
            heading_structure = st.session_state.meta_and_headings.get("heading_structure", "")
            word_count = st.session_state.requirements.get('word_count', 1500)
            
            # Show the exact content prompt from main.py
            prompt_content = f"""
# SEO Content Writing Task
    
Please write a comprehensive, SEO-optimized article about **{primary_keyword}**. 
    
## Meta Information
- Meta Title: {meta_title}
- Meta Description: {meta_description}
    
## Key Requirements:
- Word Count: {word_count} words (minimum)
- Primary Keyword: {primary_keyword}
- Use the EXACT following heading structure (do not change or add to it):
    
{heading_structure}
    
## Keyword Usage Requirements:
- Use the primary keyword ({primary_keyword}) in the first 100 words, in at least one H2 heading, and naturally throughout the content.
- Include these keyword variations naturally: {variations_text}
    
## LSI Keywords to Include (with minimum frequencies):
{lsi_formatted}
    
## Entities/Topics to Cover:
{entities_text}
    
## Content Writing Guidelines:
1. Write in a clear, authoritative style suitable for an expert audience
2. Make the content deeply informative and comprehensive
3. Always write in active voice and maintain a conversational but professional tone
4. Include only factually accurate information
5. Ensure the content flows naturally between sections
6. Include the primary keyword in the first 100 words of the content
7. Format the content using markdown
8. DO NOT include any introductory notes, explanations, or meta-commentary about your process
9. DO NOT use placeholder text or suggest that the client should add information
10. DO NOT use the phrases "in conclusion" or "in summary" for the final section
    
IMPORTANT: Return ONLY the pure markdown content without any explanations, introductions, or notes about your approach."""
            show_prompt_modal("Content Generation Prompt", prompt_content)
    
    if generate_full_content:
        if not st.session_state.get('claude_api', ''):
            st.error("Please enter your Claude API key in the sidebar.")
        else:
            # Update session state with edited values
            st.session_state.meta_and_headings["meta_title"] = meta_title_input
            st.session_state.meta_and_headings["meta_description"] = meta_description_input
            st.session_state.meta_and_headings["heading_structure"] = heading_structure_input
            
            # Add meta information to requirements
            st.session_state.requirements["meta_title"] = meta_title_input
            st.session_state.requirements["meta_description"] = meta_description_input
            
            st.session_state['step'] = 3
            st.rerun()
    
    # Back button to return to requirements
    if st.button("Back to Requirements"):
        st.session_state['step'] = 2
        st.rerun()

# Update the content generation flow
def generate_content_flow():
    """Generate and display content."""
    if 'generated_markdown' not in st.session_state:
        requirements = st.session_state.requirements
        meta_and_headings = st.session_state.get('meta_and_headings', {})
        
        # Show the content generation prompt before sending
        col1, col2 = st.columns([5, 1])
        with col1:
            confirm_button = st.button("Confirm and Send Prompt", use_container_width=True)
        with col2:
            if st.button("View Prompt", key="viewprompt", type="secondary", use_container_width=True):
                # Get values for prompt display
                primary_keyword = st.session_state.requirements.get('primary_keyword', '[primary keyword]')
                variations = st.session_state.requirements.get('keyword_variations', [])[:10] if st.session_state.requirements.get('keyword_variations') else []
                variations_text = ", ".join(variations) if variations else "None"
                
                # Format LSI keywords
                lsi_dict = {}
                lsi_keywords = st.session_state.requirements.get('lsi_keywords', [])
                lsi_formatted = ""
                if isinstance(lsi_keywords, list):
                    for kw in lsi_keywords[:10]:
                        lsi_dict[kw] = 1  # Default frequency
                    lsi_formatted = "\n".join([f"- '{kw}' => use at least {freq} times" for kw, freq in lsi_dict.items()])
                else:
                    lsi_formatted = "- No LSI keywords available"
                
                # Format entities
                entities = st.session_state.requirements.get('entities', [])[:10] if st.session_state.requirements.get('entities') else []
                entities_text = "\n".join([f"- {entity}" for entity in entities])
                
                # Get metadata from session state
                meta_title = st.session_state.meta_and_headings.get("meta_title", "")
                meta_description = st.session_state.meta_and_headings.get("meta_description", "")
                heading_structure = st.session_state.meta_and_headings.get("heading_structure", "")
                word_count = st.session_state.requirements.get('word_count', 1500)
                
                # Show the exact content prompt from main.py
                prompt_content = f"""
# SEO Content Writing Task
    
Please write a comprehensive, SEO-optimized article about **{primary_keyword}**. 
    
## Meta Information
- Meta Title: {meta_title}
- Meta Description: {meta_description}
    
## Key Requirements:
- Word Count: {word_count} words (minimum)
- Primary Keyword: {primary_keyword}
- Use the EXACT following heading structure (do not change or add to it):
    
{heading_structure}
    
## Keyword Usage Requirements:
- Use the primary keyword ({primary_keyword}) in the first 100 words, in at least one H2 heading, and naturally throughout the content.
- Include these keyword variations naturally: {variations_text}
    
## LSI Keywords to Include (with minimum frequencies):
{lsi_formatted}
    
## Entities/Topics to Cover:
{entities_text}
    
## Content Writing Guidelines:
1. Write in a clear, authoritative style suitable for an expert audience
2. Make the content deeply informative and comprehensive
3. Always write in active voice and maintain a conversational but professional tone
4. Include only factually accurate information
5. Ensure the content flows naturally between sections
6. Include the primary keyword in the first 100 words of the content
7. Format the content using markdown
8. DO NOT include any introductory notes, explanations, or meta-commentary about your process
9. DO NOT use placeholder text or suggest that the client should add information
10. DO NOT use the phrases "in conclusion" or "in summary" for the final section
    
IMPORTANT: Return ONLY the pure markdown content without any explanations, introductions, or notes about your approach."""
                show_prompt_modal("Content Generation Prompt", prompt_content)
        
        if confirm_button:
            settings = {
                'model': 'claude',
                'anthropic_api_key': st.session_state.get('claude_api', ''),
                'openai_api_key': st.session_state.get('openai_api', ''),
            }
            with st.spinner("🔄 Generating full content... This may take several minutes..."):
                try:
                    # Create and display a progress bar
                    progress_text = "Content generation in progress. Please wait."
                    progress_bar = st.progress(0, text=progress_text)
                    for percent_complete in range(101):
                        time.sleep(0.1)  # Simulate API call time - content generation takes longer
                        progress_bar.progress(percent_complete, text=f"{progress_text} ({percent_complete}%)")
                    
                    heading_structure = meta_and_headings.get("heading_structure", "")
                    markdown_content, html_content, save_path = generate_content_from_headings(
                        requirements, 
                        heading_structure,
                        settings=settings
                    )
                    st.session_state['generated_markdown'] = markdown_content
                    st.session_state['generated_html'] = html_content
                    st.session_state['save_path'] = save_path
                except Exception as e:
                    st.error(f"Error generating content: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
                    return
    
    if 'generated_markdown' in st.session_state:
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
                    st.dataframe(lsi_df, use_container_width=True, height=300, hide_index=True)
                else:
                    st.write("No LSI keywords analyzed.")
                st.markdown("### Entities Usage")
                if analysis['entities']:
                    entity_df = pd.DataFrame(analysis['entities']).T.reset_index()
                    entity_df.columns = ['Entity', 'Found', 'Status']
                    st.dataframe(entity_df, use_container_width=True, height=300, hide_index=True)
                else:
                    st.write("No entities analyzed.")
    
        # Reset button - optional
        if st.button("Start Over"):
            for key in ['generated_markdown', 'generated_html', 'save_path', 'meta_and_headings']:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state['step'] = 2
            st.rerun()

if st.session_state.get("step", 1) == 3:
    generate_content_flow()

# Footer
st.markdown("---")
st.markdown("SEO Content Generator 2025")