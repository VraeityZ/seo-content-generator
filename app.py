import os
import streamlit as st
import pandas as pd
import anthropic
import warnings
from datetime import datetime
from main import (
    parse_cora_report, 
    extract_markdown_from_response, 
    generate_initial_markdown, 
    save_markdown_to_file
)

# Suppress openpyxl warnings
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl.styles.stylesheet")

# Page config
st.set_page_config(
    page_title="SEO Content Generator",
    page_icon="📝",
    layout="wide"
)

# Define output directory
OUTPUT_DIR = "output_markdown"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def validate_markdown(markdown_content, requirements, api_key, model="claude-3-7-sonnet-latest"):
    """Validate markdown content using Claude non-thinking mode to save costs"""
    client = anthropic.Anthropic(api_key=api_key)
    
    # Get key requirements for validation
    lsi_keywords = requirements.get("lsi_keywords", {})
    entities = requirements.get("entities", [])
    
    # Construct validation prompt
    validation_prompt = f"""
    You are a content validation expert. Analyze this markdown content and check if it meets all SEO requirements.
    
    CONTENT TO VALIDATE:
    ```markdown
    {markdown_content}
    ```
    
    VALIDATION REQUIREMENTS:
    1. Check if frontmatter contains title and description
    2. Check if these LSI keywords appear with correct frequency:
    {', '.join([f"'{kw}' (min: {count})" for kw, count in list(lsi_keywords.items())[:10]])}
    
    3. Check if these entities appear at least once:
    {', '.join(entities[:10])}
    
    4. Check heading structure (# > ## > ###)
    
    RESPONSE FORMAT:
    Return a JSON in this exact format:
    {{
      "passes_validation": true/false,
      "issues": [
        {{
          "type": "keyword_frequency",
          "keyword": "keyword name",
          "required": 5, 
          "found": 2,
          "fix": "suggestion to fix"
        }},
        ...other issues
      ],
      "summary": "Brief overall assessment"
    }}
    Return ONLY the JSON, no other text.
    """
    
    # Make API call without thinking capability to save tokens
    response = client.messages.create(
        model=model,
        max_tokens=1000,
        system="You are a content validation expert. You analyze markdown for SEO compliance.",
        messages=[
            {
                "role": "user",
                "content": validation_prompt
            }
        ]
    )
    
    # Extract response
    validation_result = response.content[0].text
    
    return validation_result

# Sidebar for API configuration
with st.sidebar:
    st.title("Configuration")
    
    # Try to get API key from secrets, otherwise request it from user
    default_api_key = ""
    try:
        default_api_key = st.secrets["anthropic"]["api_key"]
    except:
        pass
    
    claude_api = st.text_input(
        "Claude API Key", 
        value="",
        type="password",
        help="Enter your Claude API key. This will not be stored permanently."
    )
    
    if not claude_api:
        st.warning("Please enter your Claude API key to use this app.")
    
    st.subheader("Heading Controls")
    h2_control = st.number_input("H2 Headings", min_value=0, value=0)
    h3_control = st.number_input("H3 Headings", min_value=0, value=0)
    h4_control = st.number_input("H4 Headings", min_value=0, value=0)
    h5_control = st.number_input("H5 Headings", min_value=0, value=0)

# Main content area
st.title("SEO Content Generator")
st.write("Upload a CORA report to generate SEO-optimized markdown content")

# File upload
uploaded_file = st.file_uploader("Upload CORA Excel Report", type=["xlsx"])

if uploaded_file is not None:
    # Save the uploaded file temporarily
    temp_file_path = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    with open(temp_file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    try:
        if st.button("Process CORA Report"):
            with st.spinner("Parsing CORA report..."):
                # Parse the report
                requirements = parse_cora_report(temp_file_path)
                
                st.success(f"✅ Parsed {len(requirements['requirements'])} requirements")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"📊 LSI Keywords: {len(requirements['lsi_keywords'])}")
                    if requirements.get("location"):
                        st.write(f"📍 Location: {requirements['location']}")
                
                with col2:
                    st.write(f"🏷️ Entities: {len(requirements['entities'])}")
                    st.write(f"📝 Word Count Target: {requirements['word_count']}")
                
                # Generate content
                with st.spinner("Generating markdown content with Claude 3.7..."):
                    markdown_content = generate_initial_markdown(requirements)
                
                # Validate content
                with st.spinner("Validating content..."):
                    validation_result = validate_markdown(markdown_content, requirements, claude_api)
                
                # Display content and validation
                st.subheader("Generated Markdown Content")
                st.text_area("Markdown", markdown_content, height=300)
                
                st.subheader("Validation Results")
                st.code(validation_result, language="json")
                
                # Save file and provide download
                output_file = save_markdown_to_file(markdown_content, requirements["url"], 1)
                with open(output_file, "r") as f:
                    st.download_button(
                        "Download Markdown File",
                        f,
                        file_name=os.path.basename(output_file),
                        mime="text/markdown"
                    )
                
                # Clean up
                os.remove(temp_file_path)
    
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# Footer
st.markdown("---")
st.caption("SEO Content Generator powered by Claude 3.7")
