import streamlit as st
import pandas as pd
import os
import anthropic
import json
import re

from main import (
    parse_cora_report,
    generate_heading_structure,
    generate_initial_markdown,
    extract_lsi_keywords,
    extract_entities,
    extract_html_from_response,
    generate_initial_html,
    initialize_api_clients,
    get_api_keys
)

st.set_page_config(
    page_title="SEO Content Generator",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

def validate_markdown(markdown_content, requirements, api_key, model="claude-3-7-sonnet-latest"):
    """Validates the generated markdown against SEO requirements."""
    client = anthropic.Anthropic(api_key=api_key)
    
    # Keyword requirements
    primary_keyword = requirements.get("primary_keyword", "")
    synonyms = requirements.get("synonyms", [])
    entities = requirements.get("entities", [])
    secondary_keywords = requirements.get("lsi_keywords", [])
    
    keyword_info = ""
    if primary_keyword:
        keyword_info += f"- Primary keyword: '{primary_keyword}' should appear 2-6 times depending on content length\n"
    if synonyms:
        keyword_info += f"- Synonyms that should be included: {', '.join([f'`{s}`' for s in synonyms])}\n"
    if entities:
        keyword_info += f"- Entities that should be mentioned: {', '.join([f'`{e}`' for e in entities])}\n"
    if secondary_keywords:
        keyword_info += f"- Secondary keywords/phrases: {', '.join([f'`{k}`' for k in secondary_keywords])}\n"
    
    # Heading structure requirements
    heading_structure = requirements.get("heading_structure", {})
    heading_info = "Heading structure requirements:\n"
    for level in range(2, 6):
        if heading_structure.get(f"h{level}", 0) > 0:
            heading_info += f"- H{level} headings: {heading_structure[f'h{level}']} required\n"

    prompt = f"""You are a professional SEO content validator. Your task is to evaluate the provided markdown content against specific SEO requirements and provide a clear validation report.

CONTENT TO VALIDATE:
```markdown
{markdown_content}
```

SEO REQUIREMENTS:
{keyword_info}
{heading_info}

VALIDATION TASKS:
1. Check if the primary keyword appears an appropriate number of times (2-6 times depending on content length)
2. Verify that all required synonyms are included
3. Confirm that all entities are mentioned at least once
4. Ensure that secondary keywords are incorporated naturally
5. Validate the heading structure against requirements

FORMAT YOUR RESPONSE AS FOLLOWS:
```json
{{
  "passes_validation": true|false,
  "primary_keyword_frequency": X,
  "primary_keyword_assessment": "good"|"too_low"|"too_high",
  "missing_synonyms": ["synonym1", "synonym2"],
  "missing_entities": ["entity1", "entity2"],
  "missing_secondary_keywords": ["keyword1", "keyword2"],
  "heading_structure_assessment": {{
    "h2_required": X,
    "h2_found": Y,
    "h2_assessment": "good"|"too_few"|"too_many",
    "h3_required": X,
    "h3_found": Y,
    "h3_assessment": "good"|"too_few"|"too_many",
    "h4_required": X,
    "h4_found": Y,
    "h4_assessment": "good"|"too_few"|"too_many",
    "h5_required": X,
    "h5_found": Y,
    "h5_assessment": "good"|"too_few"|"too_many"
  }},
  "suggestions_for_improvement": [
    "Suggestion 1",
    "Suggestion 2"
  ]
}}
```

IMPORTANT GUIDELINES:
- Be strict but fair in your assessment
- Provide specific, actionable suggestions for improvement
- Do not get into the specifics of the content quality, ONLY focus on SEO requirements
- Use "passes_validation": true only if all requirements are met
"""

    try:
        # Get response directly from Claude in non-thinking mode to avoid extra cost
        message = client.messages.create(
            model=model,
            max_tokens=1500,
            temperature=0,
            system="You are an expert SEO validator. Respond in JSON format only, no thinking aloud.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        response_text = message.content[0].text
        
        # Extract JSON from response if needed
        json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response_text
            
        # Clean up any non-JSON content
        json_str = re.sub(r'^[^{]*', '', json_str)
        json_str = re.sub(r'[^}]*$', '', json_str)
        
        # Parse JSON
        validation_result = json.loads(json_str)
        return validation_result
    except Exception as e:
        st.error(f"Error validating content: {str(e)}")
        return {
            "passes_validation": False,
            "error": str(e),
            "suggestions_for_improvement": ["Please try again or check your API key."]
        }

# Main app
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
    
    openai_api = st.text_input(
        "OpenAI API Key (Optional)",
        value="",
        type="password",
        help="Enter your OpenAI API key if you want to use OpenAI models."
    )
    
    if not claude_api:
        st.warning("Please enter your Claude API key to use this app.")
    
# File upload section
uploaded_file = st.file_uploader("Upload CORA report", type=["xlsx", "xls"])

if uploaded_file is not None:
    st.success(f"Successfully uploaded: {uploaded_file.name}")
    
    # Display heading controls
    with st.expander("Configure Headings (optional)"):
        st.markdown("### Heading controls")
        st.markdown("Use these controls to override the number of headings recommended in the CORA report")
        col1, col2 = st.columns(2)
        
        with col1:
            h2_control = st.number_input("Number of H2 headings", min_value=0, max_value=10, value=0, step=1)
            h3_control = st.number_input("Number of H3 headings", min_value=0, max_value=20, value=0, step=1)
        
        with col2:
            h4_control = st.number_input("Number of H4 headings", min_value=0, max_value=20, value=0, step=1)
            h5_control = st.number_input("Number of H5 headings", min_value=0, max_value=20, value=0, step=1)
    
    # Button to extract requirements
    if st.button("Extract Requirements"):
        with st.spinner("Extracting requirements..."):
            try:
                # Pass the uploaded file directly to the parse_cora_report function
                requirements = parse_cora_report(uploaded_file)
                
                # Override heading structure with user inputs if provided
                if h2_control > 0:
                    requirements["heading_structure"]["h2"] = h2_control
                if h3_control > 0:
                    requirements["heading_structure"]["h3"] = h3_control
                if h4_control > 0:
                    requirements["heading_structure"]["h4"] = h4_control
                if h5_control > 0:
                    requirements["heading_structure"]["h5"] = h5_control
                
                # Store results in session state
                st.session_state.requirements = requirements
                st.session_state.step = 2
                
                # Force rerun to update the UI
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Error extracting requirements: {str(e)}")
                st.exception(e)
else:
    st.info("Please upload a CORA report to get started.")

if st.session_state.get("step", 1) == 2:
    requirements = st.session_state.requirements
    
    # Display requirements
    st.subheader("Extracted Requirements")
    
    # Basic info
    st.write(f"**Primary Keyword:** {requirements.get('primary_keyword', 'Not found')}")
    st.write(f"**Search Volume:** {requirements.get('search_volume', 'Not found')}")
    st.write(f"**Competition Level:** {requirements.get('competition_level', 'Not found')}")
    
    # Keywords
    with st.expander("Keywords"):
        st.write(f"**Synonyms:** {', '.join(requirements.get('synonyms', []))}")
        
        # LSI Keywords
        st.write("**LSI Keywords:**")
        lsi_keywords = requirements.get('lsi_keywords', [])
        if lsi_keywords:
            for keyword in lsi_keywords[:10]:  # Show first 10
                st.write(f"- {keyword}")
            if len(lsi_keywords) > 10:
                st.write(f"... and {len(lsi_keywords) - 10} more")
    
    # Entities
    with st.expander("Entities"):
        entities = requirements.get('entities', [])
        if entities:
            for entity in entities[:10]:  # Show first 10
                st.write(f"- {entity}")
            if len(entities) > 10:
                st.write(f"... and {len(entities) - 10} more")
    
    # Heading structure
    with st.expander("Heading Structure"):
        heading_structure = requirements.get('heading_structure', {})
        for level in range(2, 6):
            key = f"h{level}"
            st.write(f"**{key.upper()} Headings:** {heading_structure.get(key, 0)}")
    
    # Generate content button
    if st.button("Generate Content"):
        if not claude_api:
            st.error("Please enter your Claude API key in the sidebar.")
        else:
            with st.spinner("Generating content... This may take a few minutes."):
                try:
                    # Generate markdown content
                    markdown_content = generate_initial_markdown(
                        requirements, 
                        claude_api=claude_api, 
                        openai_api=openai_api
                    )
                    
                    # Display the markdown content
                    st.subheader("Generated Content")
                    st.markdown(markdown_content)
                    
                    # Validate the content button
                    if st.button("Validate Content"):
                        with st.spinner("Validating content..."):
                            validation_result = validate_markdown(
                                markdown_content, 
                                requirements, 
                                claude_api
                            )
                            
                            # Display validation results
                            st.subheader("Validation Results")
                            
                            # Overall result
                            if validation_result.get("passes_validation", False):
                                st.success("✅ Content passes all SEO requirements!")
                            else:
                                st.error("❌ Content needs improvement to meet SEO requirements.")
                            
                            # Primary keyword assessment
                            st.write(f"**Primary Keyword Frequency:** {validation_result.get('primary_keyword_frequency', 'N/A')}")
                            assessment = validation_result.get('primary_keyword_assessment', 'N/A')
                            if assessment == "good":
                                st.success("✅ Primary keyword frequency is good.")
                            elif assessment == "too_low":
                                st.warning("⚠️ Primary keyword frequency is too low.")
                            elif assessment == "too_high":
                                st.warning("⚠️ Primary keyword frequency is too high.")
                            
                            # Missing elements
                            if validation_result.get('missing_synonyms', []):
                                st.warning(f"⚠️ Missing synonyms: {', '.join(validation_result['missing_synonyms'])}")
                            else:
                                st.success("✅ All required synonyms are included.")
                                
                            if validation_result.get('missing_entities', []):
                                st.warning(f"⚠️ Missing entities: {', '.join(validation_result['missing_entities'])}")
                            else:
                                st.success("✅ All required entities are included.")
                                
                            if validation_result.get('missing_secondary_keywords', []):
                                st.warning(f"⚠️ Missing secondary keywords: {', '.join(validation_result['missing_secondary_keywords'][:5])}")
                                if len(validation_result.get('missing_secondary_keywords', [])) > 5:
                                    st.write(f"... and {len(validation_result['missing_secondary_keywords']) - 5} more")
                            else:
                                st.success("✅ All secondary keywords are included.")
                            
                            # Heading structure assessment
                            st.subheader("Heading Structure Assessment")
                            heading_assessment = validation_result.get('heading_structure_assessment', {})
                            
                            for level in range(2, 6):
                                key = f"h{level}"
                                required = heading_assessment.get(f"{key}_required", 0)
                                found = heading_assessment.get(f"{key}_found", 0)
                                assessment = heading_assessment.get(f"{key}_assessment", "N/A")
                                
                                if assessment == "good":
                                    st.success(f"✅ {key.upper()}: {found}/{required} headings (Good)")
                                elif assessment == "too_few":
                                    st.warning(f"⚠️ {key.upper()}: {found}/{required} headings (Too few)")
                                elif assessment == "too_many":
                                    st.warning(f"⚠️ {key.upper()}: {found}/{required} headings (Too many)")
                            
                            # Suggestions for improvement
                            if validation_result.get('suggestions_for_improvement', []):
                                st.subheader("Suggestions for Improvement")
                                for suggestion in validation_result['suggestions_for_improvement']:
                                    st.write(f"- {suggestion}")
                    
                    # Download button for markdown
                    st.download_button(
                        label="Download Markdown",
                        data=markdown_content,
                        file_name=f"{requirements.get('primary_keyword', 'content').replace(' ', '_')}.md",
                        mime="text/markdown"
                    )
                except Exception as e:
                    st.error(f"Error generating content: {str(e)}")

# Footer
st.markdown("---")
st.markdown("SEO Content Generator 2025")
