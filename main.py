import os
import re
import pandas as pd
import anthropic
from openai import OpenAI
from datetime import datetime
from bs4 import BeautifulSoup
import warnings
import math
import io
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl.styles.stylesheet")

# Define output directory
OUTPUT_DIR = "output_markdown"

# Placeholder for API keys - these should be set in environment variables or Streamlit secrets
def get_api_keys(claude_api, openai_api):
    return claude_api, openai_api

# Model selection (choose between Claude and ChatGPT)
platform = "Claude"  # @param ["Claude"]
claude_model = "claude-3-7-sonnet-latest"  # Verify with Anthropic API docs
chatgpt_model = "o1-mini-2024-09-12"  # ChatGPT's o1 model

# Heading control variables
h2_control = 0  # @param {"type":"number","placeholder":"0"}
h3_control = 0  # @param {"type":"number","placeholder":"0"}
h4_control = 0  # @param {"type":"number","placeholder":"0"}
h5_control = 0  # @param {"type":"number","placeholder":"0"}

# Initialize API clients
def initialize_api_clients(claude_api, openai_api):
    if platform == "Claude":
        client = anthropic.Anthropic(api_key=claude_api)
        model = claude_model
    elif platform == "ChatGPT":
        client = OpenAI(api_key=openai_api)
        model = chatgpt_model
    else:
        raise ValueError(f"Unsupported platform: {platform}")
    return client, model

##############################################################################
# UPLOAD FILE
##############################################################################
def upload_file():
    """A placeholder function for compatibility. In Streamlit, file upload is handled directly by the Streamlit UI."""
    return None

##############################################################################
# PARSE CORA REPORT
##############################################################################
def parse_cora_report(file_path):
    """Parses a CORA Excel report and extracts the SEO requirements."""
    try:
        # Define default heading controls
        h2_control = 0  # Default to no override
        h3_control = 0
        h4_control = 0
        h5_control = 0
        
        # Read the Excel file (main sheet)
        # For Streamlit compatibility: handle both file paths and BytesIO objects
        if isinstance(file_path, str):
            df = pd.read_excel(file_path, engine="openpyxl", header=None)
        else:
            # If it's a file object (from Streamlit), convert to BytesIO
            df = pd.read_excel(file_path, engine="openpyxl", header=None)
        
        # Debug info to verify structure
        print(f"Excel file loaded with {df.shape[0]} rows and {df.shape[1]} columns")
        
        # Find the URL (should be in cell B2)
        primary_keyword = ""
        url = ""
        
        # Look for URL in the first few rows
        for i in range(min(5, df.shape[0])):
            for j in range(min(3, df.shape[1])):
                cell_value = str(df.iloc[i, j]).strip() if not pd.isna(df.iloc[i, j]) else ""
                if cell_value.lower().startswith(("http://", "https://")):
                    url = cell_value
                    print(f"Found URL in cell ({i},{j}): {url}")
                    break
        
        # If URL not found, try to find it in a specific location (B2)
        if not url and df.shape[0] > 1 and df.shape[1] > 1:
            cell_value = str(df.iloc[0, 1]).strip() if not pd.isna(df.iloc[0, 1]) else ""
            if cell_value:
                url = cell_value
                print(f"Using cell B2 as URL: {url}")
        
        # If we still don't have a URL, look for the Primary Keyword
        if not url:
            for i in range(min(5, df.shape[0])):
                for j in range(min(3, df.shape[1])):
                    header = str(df.iloc[i, j]).strip() if not pd.isna(df.iloc[i, j]) else ""
                    if "primary keyword" in header.lower() and i+1 < df.shape[0]:
                        primary_keyword = str(df.iloc[i+1, j]).strip() if not pd.isna(df.iloc[i+1, j]) else ""
                        url = f"https://{primary_keyword.replace(' ', '-')}.com"
                        print(f"Constructed URL from primary keyword: {url}")
                        break
        
        if not url:
            # If we still don't have a URL, use a default placeholder
            url = "https://example.com"
            print(f"No URL found, using placeholder: {url}")
        
        # Check if the URL contains location indicators
        location_info = extract_location_from_url(url)

        # Extract variations more robustly
        variations_list = []
        # Try to find variations specifically labeled
        for i in range(min(10, df.shape[0])):
            for j in range(min(3, df.shape[1])):
                cell_value = str(df.iloc[i, j]).strip() if not pd.isna(df.iloc[i, j]) else ""
                if "variation" in cell_value.lower():
                    # Look for variations in the next cell to the right or below
                    if j+1 < df.shape[1] and not pd.isna(df.iloc[i, j+1]):
                        raw_variations = str(df.iloc[i, j+1]).strip()
                        variations_list = [p.strip(' "\'') for p in raw_variations.split(",") if p.strip()]
                        print(f"Found {len(variations_list)} variations")
                    elif i+1 < df.shape[0] and not pd.isna(df.iloc[i+1, j]):
                        raw_variations = str(df.iloc[i+1, j]).strip()
                        variations_list = [p.strip(' "\'') for p in raw_variations.split(",") if p.strip()]
                        print(f"Found {len(variations_list)} variations")
        
        # If we didn't find variations with a label, try using the second row
        if not variations_list and df.shape[0] > 1:
            raw_variations = str(df.iloc[1, 0]).strip() if not pd.isna(df.iloc[1, 0]) else ""
            if raw_variations and "," in raw_variations:
                variations_list = [p.strip(' "\'') for p in raw_variations.split(",") if p.strip()]
                print(f"Found {len(variations_list)} variations in second row")
        
        # Find and process requirements section
        requirements = {}
        requirements_section_found = False
        
        # Look for the heading markers more flexibly
        for i in range(df.shape[0]):
            row_text = str(df.iloc[i, 0]).strip() if not pd.isna(df.iloc[i, 0]) else ""
            
            # Check if we've found the start of the requirements section
            marker_start = "Phase 1: Title & Headings"
            if marker_start in row_text or "Phase 1" in row_text:
                requirements_section_found = True
                start_idx = i + 1
                continue
                
            # Check if we've reached the end of the requirements section
            possible_end_markers = [
                "Phase 2: Content",
                "Phase 3: Authority",
                "Phase 4: Diversity",
                "Phase 6: Search Result Presentation",
                "Phase 7: Outbound Linking From the Page"
            ]
            if requirements_section_found:
                end_found = False
                for marker in possible_end_markers:
                    if marker in row_text:
                        end_idx = i
                        end_found = True
                        break
                        
                if end_found:
                    break
        
        # If we found a requirements section, process it
        if requirements_section_found:
            end_idx = end_idx if 'end_idx' in locals() else df.shape[0]
            
            for idx in range(start_idx, end_idx):
                if idx >= df.shape[0]:
                    break
                    
                req_desc = str(df.iloc[idx, 0]).strip() if not pd.isna(df.iloc[idx, 0]) else ""
                req_amount_text = str(df.iloc[idx, 1]).strip() if df.shape[1] > 1 and not pd.isna(df.iloc[idx, 1]) else ""
                
                if req_desc and req_amount_text:
                    match = re.search(r"(\d+)", req_amount_text)
                    if match:
                        amount = int(match.group(1))
                        requirements[req_desc] = amount
        
        # Extract word count more flexibly
        word_count = 1500  # Default word count
        
        # Look for word count in various places
        for i in range(min(20, df.shape[0])):
            for j in range(min(5, df.shape[1])):
                cell_value = str(df.iloc[i, j]).strip() if not pd.isna(df.iloc[i, j]) else ""
                if "word count" in cell_value.lower() or "cp492" in cell_value.lower():
                    # Check cells to the right and below for a number
                    for check_i, check_j in [(i, j+1), (i+1, j)]:
                        if check_i < df.shape[0] and check_j < df.shape[1] and not pd.isna(df.iloc[check_i, check_j]):
                            try:
                                cell_value = str(df.iloc[check_i, check_j]).strip()
                                # Extract numeric part
                                match = re.search(r"(\d+)", cell_value)
                                if match:
                                    word_count = int(match.group(1))
                                    print(f"Found word count: {word_count}")
                            except:
                                pass
        
        # If no primary keyword found yet, look for it more broadly
        if not primary_keyword:
            for i in range(min(10, df.shape[0])):
                for j in range(min(3, df.shape[1])):
                    header = str(df.iloc[i, j]).strip() if not pd.isna(df.iloc[i, j]) else ""
                    if "primary keyword" in header.lower() and i+1 < df.shape[0]:
                        primary_keyword = str(df.iloc[i+1, j]).strip() if not pd.isna(df.iloc[i+1, j]) else ""
                        print(f"Found primary keyword: {primary_keyword}")
                        break
                    # Also check if the cell itself is labeled
                    elif j+1 < df.shape[1]:
                        value = str(df.iloc[i, j+1]).strip() if not pd.isna(df.iloc[i, j+1]) else ""
                        if value and "keyword" in header.lower() and "primary" in header.lower():
                            primary_keyword = value
                            print(f"Found primary keyword: {primary_keyword}")
                            break
        
        # If we still don't have a primary keyword, use the first variation or the URL
        if not primary_keyword:
            if variations_list:
                primary_keyword = variations_list[0]
                print(f"Using first variation as primary keyword: {primary_keyword}")
            else:
                # Extract domain from URL as a last resort
                domain = url.replace("https://", "").replace("http://", "").split("/")[0]
                primary_keyword = domain.replace("-", " ").replace(".", " ")
                print(f"Using domain as primary keyword: {primary_keyword}")
        
        # Extract heading structures requirements
        heading_structure = {"h2": 0, "h3": 0, "h4": 0, "h5": 0}
        
        # Set heading structure based on requirements
        for key in requirements:
            if "h2" in key.lower() and "tag" in key.lower():
                match = re.search(r"(\d+)", str(requirements[key]))
                if match:
                    heading_structure["h2"] = int(match.group(1))
            elif "h3" in key.lower() and "tag" in key.lower():
                match = re.search(r"(\d+)", str(requirements[key]))
                if match:
                    heading_structure["h3"] = int(match.group(1))
            elif "h4" in key.lower() and "tag" in key.lower():
                match = re.search(r"(\d+)", str(requirements[key]))
                if match:
                    heading_structure["h4"] = int(match.group(1))
            elif "h5" in key.lower() and "tag" in key.lower():
                match = re.search(r"(\d+)", str(requirements[key]))
                if match:
                    heading_structure["h5"] = int(match.group(1))
        
        # Set defaults if none found
        if heading_structure["h2"] == 0:
            heading_structure["h2"] = 3
        if heading_structure["h3"] == 0 and heading_structure["h2"] > 0:
            heading_structure["h3"] = heading_structure["h2"] * 2
        
        heading_overrides = []
        
        # Extract LSI keywords and entities
        lsi_keywords = extract_lsi_keywords(file_path)
        entities = extract_entities(file_path)
        
        # If we couldn't extract any LSI keywords, use variations
        if not lsi_keywords and variations_list:
            lsi_keywords = variations_list
            print(f"Using variations as LSI keywords")
        
        # Create synonyms from variations if available
        synonyms = variations_list[:5] if variations_list else []
        
        # Build the final result structure
        results = {
            "primary_keyword": primary_keyword,
            "url": url,
            "variations": variations_list,
            "competition_level": "Medium",  # Default value
            "search_volume": "1K-10K",      # Default value
            "word_count": word_count,
            "requirements": requirements,
            "entities": entities,
            "lsi_keywords": lsi_keywords,
            "synonyms": synonyms,
            "heading_structure": heading_structure,
            "content_structure": "",
            "heading_overrides": heading_overrides
        }
        
        print(f"Successfully extracted requirements for {primary_keyword}")
        return results
    except Exception as e:
        print(f"Error parsing CORA report: {e}")
        raise

##############################################################################
# EXTRACT LOCATION FROM URL
##############################################################################
def extract_location_from_url(url):
    """Extract location information from URL for local SEO optimization."""
    city_state_pattern = re.compile(r'(?:[-_/])([a-z]+[-_]?[a-z]*?)(?:[-_/])([a-z]{2})(?:[-_/]|$)', re.IGNORECASE)
    city_pattern = re.compile(r'(?:in-|near-|[-_/])([a-z]+(?:[-_][a-z]+)*)(?:[-_/]|$)', re.IGNORECASE)
    match = city_state_pattern.search(url)
    if match:
        city = match.group(1).replace('-', ' ').replace('_', ' ').title()
        state = match.group(2).upper()
        return {"city": city, "state": state}
    match = city_pattern.search(url)
    if match:
        city = match.group(1).replace('-', ' ').replace('_', ' ').title()
        return {"city": city}
    return None

##############################################################################
# EXTRACT LSI KEYWORDS
##############################################################################
MAX_LSI_KEYWORDS = 40

def extract_lsi_keywords(file_path):
    """Extracts LSI keywords from the CORA report, gracefully handling empty data."""
    try:
        # Handle different file path types
        if isinstance(file_path, str):
            try:
                xl = pd.ExcelFile(file_path, engine="openpyxl")
            except:
                print("Warning: Could not open LSI Keywords sheet")
                return []
        else:
            # Handle Streamlit's UploadedFile object
            import io
            if hasattr(file_path, 'getvalue'):
                bytes_data = file_path.getvalue()
                xl = pd.ExcelFile(io.BytesIO(bytes_data), engine="openpyxl")
            else:
                xl = pd.ExcelFile(file_path, engine="openpyxl")

        # Check if LSI Keywords sheet exists
        if "LSI Keywords" not in xl.sheet_names:
            print("Warning: LSI Keywords sheet not found in Excel file")
            return []
        
        # Load the LSI Keywords sheet
        df = pd.read_excel(xl, sheet_name="LSI Keywords", header=None)
        
        # Extract keywords from first column
        keywords = []
        for i in range(len(df)):
            if not pd.isna(df.iloc[i, 0]) and df.iloc[i, 0] != "":
                keywords.append(df.iloc[i, 0])
        
        return keywords
    except Exception as e:
        print(f"Error extracting LSI keywords: {e}")
        return []

##############################################################################
# EXTRACT ENTITIES
##############################################################################
def extract_entities(file_path):
    """Extracts entities from the CORA report, gracefully handling empty data."""
    try:
        # Handle different file path types
        if isinstance(file_path, str):
            try:
                xl = pd.ExcelFile(file_path, engine="openpyxl")
            except:
                print("Warning: Could not open Entity Mentions sheet")
                return []
        else:
            # Handle Streamlit's UploadedFile object
            import io
            if hasattr(file_path, 'getvalue'):
                bytes_data = file_path.getvalue()
                xl = pd.ExcelFile(io.BytesIO(bytes_data), engine="openpyxl")
            else:
                xl = pd.ExcelFile(file_path, engine="openpyxl")
        
        # Check if Entity Mentions sheet exists
        if "Entity Mentions" not in xl.sheet_names:
            print("Warning: Entity Mentions sheet not found in Excel file")
            return []
        
        # Load the Entity Mentions sheet
        df = pd.read_excel(xl, sheet_name="Entity Mentions", header=None)
        
        # Extract entities from first column
        entities = []
        for i in range(len(df)):
            if not pd.isna(df.iloc[i, 0]) and df.iloc[i, 0] != "":
                entities.append(df.iloc[i, 0])
        
        return entities
    except Exception as e:
        print(f"Error extracting entities: {e}")
        return []

##############################################################################
# EXTRACT MARKDOWN FROM API RESPONSE
##############################################################################
def extract_markdown_from_response(response_text):
    """Extracts Markdown content from the API response, expecting it within triple backticks."""
    match = re.search(r'```(?:markdown|md)?(.*?)```', response_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    else:
        return response_text.strip()

##############################################################################
# GENERATE HEADING STRUCTURE
##############################################################################
def generate_heading_structure(primary_keyword, heading_structure, lsi_keywords=None, entities=None):
    """Generates a heading structure based on SEO requirements.
    
    Args:
        primary_keyword: The main keyword for the content
        heading_structure: Dict containing required number of headings (h2, h3, etc.)
        lsi_keywords: List of LSI keywords to potentially use in headings
        entities: List of entities to potentially use in headings
        
    Returns:
        A string representation of the heading structure requirements
    """
    if lsi_keywords is None:
        lsi_keywords = []
    if entities is None:
        entities = []
    
    headings_text = "HEADING STRUCTURE:\n"
    
    # Add H1 requirements
    headings_text += f"1. H1: Include one H1 title that contains the primary keyword '{primary_keyword}'\n"
    
    # Add requirements for other heading levels
    for level in range(2, 6):
        key = f"h{level}"
        count = heading_structure.get(key, 0)
        if count > 0:
            headings_text += f"{level}. H{level}: Include approximately {count} H{level} headings"
            
            # Add suggestions for H2 and H3 headings
            if level <= 3 and (lsi_keywords or entities):
                headings_text += " - consider including these topics:\n"
                
                # Add some LSI keywords as potential heading topics
                sample_keywords = lsi_keywords[:min(len(lsi_keywords), 3)]
                if sample_keywords:
                    for kw in sample_keywords:
                        headings_text += f"   - {kw}\n"
                
                # Add some entities as potential heading topics
                sample_entities = entities[:min(len(entities), 2)]
                if sample_entities:
                    for entity in sample_entities:
                        headings_text += f"   - {entity}\n"
            else:
                headings_text += "\n"
    
    return headings_text

##############################################################################
# GENERATE INITIAL MARKDOWN
##############################################################################
def generate_initial_markdown(requirements, claude_api, openai_api):
    """Generates an SEO-optimized markdown page based on CORA report requirements using the new prompt structure."""
    url = requirements["url"]
    variations = requirements["variations"]
    reqs = requirements["requirements"]
    lsi_dict = requirements["lsi_keywords"]
    entities = requirements["entities"]
    word_count = requirements["word_count"]
    heading_overrides = requirements.get("heading_overrides", [])

    # Format requirements, including heading overrides
    req_list = heading_overrides + [f"{desc}: add {amount}" for desc, amount in reqs.items() if "Number of H" not in desc or "tags" not in desc]
    requirements_formatted = "\n".join(req_list)
    variations_formatted = ", ".join(variations)
    lsi_formatted = "\n".join([f"'{kw}' => at least {freq} occurrences" for kw, freq in lsi_dict.items()])
    entities_formatted = ", ".join(entities)

    system_prompt = (
        "You are an SEO and content writing expert. Using your experience I need you to generate a complete "
        "SEO-optimized User friendly structured page with the following requirements:\n"
        "1. Important: You MUST Follow the steps in syntax order\n"
        "2. Respond with just the Markdown code - no explanations, preamble or additional text."
    )

    user_prompt = f"""
<requirements>
{requirements_formatted}
</requirements>

<variations>
{variations_formatted}
</variations>

<lsi>
{lsi_formatted}
</lsi>

<entities>
{entities_formatted}
</entities>

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
3B2. Use transitional phrases (e.g., "In addition," "As a result," "Next") to link ideas where needed.
3B3. Avoid sudden jumps between unrelated topics.
3C. Example:
3C1. Redundant: Two sections both state, '[Topic] is beneficial.'
3C2. Fixed: One section defines SEO, while another explains how it boosts visibility with specific strategies.
4. Include an FAQ if the topic involves common user questions or multiple subtopics. FAQ Section should be an H2. The Questions must each be an H3.
5. Merge variations into single headings when possible (as long as it makes sense for readability, SEO and in line with the heading requirements).
6. IMPORTANT: Ensure and Confirm each step in the Step 1 list is met.
</step 1>

<step 2>
1. Plan the page structure in a heading hierarchy format (Not organized by type, but instead (# > ## > ###...)).
2. Confirm all the requirements are being met in the headings.
3. Confirm all the requirements are being met in the title.
4. Confirm all the requirements are being met in the description.
IMPORTANT: Ensure and Confirm each step in the Step 2 list is met.
</step 2>

<step 3>
Now that the headings are laid out and confirmed. Generate content for each section appropriately.
1. Content Must have all specified variations, LSI keywords, and entities integrated naturally.
2. Level 2 heading (##) sections should have at least 75 words of content
3. Level 3 heading (###) sections should have at least 15 words of content
4. Each entity should be used at least once within the content.
5. Start each section with the most valuable information first.
6. Present information in an easily scannable format with bullet points, lists and tables.
7. FAQ Answers should be short and concise and answer the question within 15 words when possible. any extra words or fluff can be added after.
8. Overall content should be both informative and engaging.
9. *Content Must have all specified variations, LSI keywords, and entities integrated naturally.*
10. Use proper markdown formatting:
    - # for main title (h1)
    - ## for section headings (h2)
    - ### for subsections (h3)
    - #### and ##### for lower-level headings
    - **bold text** for emphasis
    - *italic text* for minor emphasis
    - - or * for bullet points
    - 1., 2., etc. for numbered lists
    - [Text](URL) for links
    - | cell | cell | for tables with header row, separator row, and content rows
11. Do NOT USE em dashes. Eliminate any and all use of em dashes from the text.
12. Confirm all the requirements are being met in the content.
13. Confirm entities are being utilized.
14. Confirm the Topical reference entities are being used appropriately to Confirm topical coverage.
15. Confirm Good Content Flow
15A. Definition: Ensure ideas progress logically from one section to the next, with smooth transitions that enhance readability and comprehension.
15B. Guidelines:
15B1. Arrange content in a natural sequence (e.g., basics before advanced topics).
15B2. Use transitional phrases (e.g., "In addition," "As a result," "Next") to link ideas where needed.
15B3. Avoid sudden jumps between unrelated topics.
15C. Example:
15C1. Poor Flow: A section on '[Detailed Subtopic]' followed abruptly by '[Topic Basics].'
15C2. Good Flow: '[Basic Concept of [Topic]]' → '[Why [Topic] Matters]' → '[Tools or Methods for [Topic]]'
16. IMPORTANT: Ensure and Confirm each step in the Step 3 list is met.
17. Content Length should be approximately {word_count} words, but slightly more if necessary to meet all requirements.
</step 3>

<final step>
1. Review the generated content and Confirm all entities are naturally being used at least once if appropriate.
2. Review the generated content and Confirm all the LSIs are naturally being used at least once if appropriate.
3. Review the generated content and Confirm the topical coverage is being covered effectively.
4. Review the generated content and Confirm the content flows well for the user, there is no redundancy and every section provides real value for the user.
4A. Provide Real Value Definition: Deliver unique, actionable, or insightful content that directly addresses the user's needs or solves their problem.
4B. Guidelines:
4B1. Include information not easily found elsewhere (e.g., original tips, data, or examples).
4B2. Offer clear, practical steps or solutions the user can apply.
4B3. Tailor the content to the query's intent.
4C. Example:
4C1. Low Value: "[Topic] is important."
4C2. High Value: "[Topic] can [achieve specific benefit]—here's a [practical method] to [take action].
5. Review the generated content and Confirm the heading hierarchy is being used effectively. The heading structure should always follow the hierarchy.
6. For front-matter, include at the top of the markdown:
   ```
   ---
   title: "Your Title Here"
   description: "Your meta description here"
   ---
   ```
7. IMPORTANT: Ensure and Confirm each step in the final Step list is met.
</final step>
"""
    print("\n=== Initial Markdown Generation Prompt ===")
    with open("prompt.txt", "w") as f:
        f.write(f"System Prompt:\n{system_prompt}\n\n\nUser Prompt:{user_prompt}")
    print("=== Prompt output saved to prompt.txt ===\n")
    # API call based on platform
    client, model = initialize_api_clients(claude_api, openai_api)
    if platform == "Claude":
        response = client.messages.create(
            model=model,
            max_tokens=15000,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_prompt
                        }
                    ]
                }
            ],
            thinking={
                "type": "enabled",
                "budget_tokens": 14750
            }
        )
        # Extract text from text blocks
        markdown_content = ""
        for block in response.content:
            if block.type == "text":
                markdown_content += block.text
        markdown_content = extract_markdown_from_response(markdown_content)
    else:  # ChatGPT
        full_prompt = system_prompt + "\n\n" + user_prompt
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.7
        )
        markdown_content = extract_markdown_from_response(response.choices[0].message.content)

    return markdown_content

##############################################################################
# SAVE MARKDOWN
##############################################################################
def save_markdown_to_file(markdown_str, url, iteration):
    """Saves the markdown content to a file with a timestamped filename."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    domain = url.split("//")[1].split("/")[0].replace("www.", "")
    filename = f"{OUTPUT_DIR}/seo_content_{domain}_iteration_{iteration}_{timestamp}.md"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(markdown_str)
    
    print(f"\nMarkdown content saved to: {filename}")
    return filename

##############################################################################
# EXTRACT HTML FROM RESPONSE
##############################################################################
def extract_html_from_response(response_text):
    """Extracts HTML content from an API response."""
    # Look for HTML content within HTML tags or code blocks
    html_match = re.search(r'```(?:html)?(.*?)```', response_text, re.DOTALL)
    if html_match:
        return html_match.group(1).strip()
    
    # If no HTML code blocks, try to find content between <html> tags
    html_tag_match = re.search(r'<html.*?>(.*?)</html>', response_text, re.DOTALL)
    if html_tag_match:
        return f"<html>{html_tag_match.group(1)}</html>"
    
    # If neither is found, just return the original text
    return response_text.strip()

##############################################################################
# GENERATE INITIAL HTML
##############################################################################
def generate_initial_html(markdown_content, api_key):
    """Converts markdown content to HTML using the specified AI platform."""
    print("Converting markdown to HTML...")
    
    system_prompt = """You are an expert web developer specializing in converting markdown to clean, semantic HTML.
Your task is to convert the provided markdown content into valid HTML5 that follows best practices.

Instructions:
1. Convert all markdown syntax to proper HTML5 elements
2. Ensure all headings (h1-h5) maintain their hierarchy
3. Apply proper HTML semantics (article, section, etc.) where appropriate
4. Convert markdown lists to proper HTML lists (ul/ol with li elements)
5. Convert emphasis and strong formatting to appropriate HTML tags
6. Format the HTML with proper indentation for readability
7. Do not add any CSS or JavaScript
8. Return ONLY the HTML code without any explanation
"""

    user_prompt = f"""Please convert this markdown content to clean, semantic HTML5:

{markdown_content}

Return ONLY the HTML code.
"""

    # Make API call based on platform
    if platform == "Claude":
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=claude_model,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )
        html_content = extract_html_from_response(response.content[0].text)
    
    elif platform == "ChatGPT":
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=chatgpt_model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user", 
                    "content": user_prompt
                }
            ],
            max_tokens=4096
        )
        html_content = extract_html_from_response(response.choices[0].message.content)
    
    # Save HTML to file
    filename = f"{OUTPUT_DIR}/output.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"✅ HTML saved to {filename}")
    return html_content

##############################################################################
# MAIN FUNCTION
##############################################################################
def main(claude_api, openai_api):
    """Main function to orchestrate the markdown generation process."""
    try:
        # Create output directory if it doesn't exist
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Upload file
        uploaded = upload_file()
        if not uploaded:
            print("No file uploaded. Exiting.")
            return
        file_path = uploaded
        
        # Parse CORA report
        try:
            print("Parsing CORA report...")
            requirements = parse_cora_report(file_path)
            print(f"✅ Successfully extracted requirements for {requirements['url']}")
            print(f"Primary Keyword: {requirements['primary_keyword']}")
            print(f"Word Count Target: {requirements['word_count']}")
            print(f"Entities Found: {len(requirements['entities'])}")
            print(f"LSI Keywords Found: {len(requirements['lsi_keywords'])}")
            print()
        except Exception as e:
            print(f"❌ Error parsing CORA report: {e}")
            return

        # Generate initial markdown
        markdown_content = generate_initial_markdown(requirements, claude_api, openai_api)
        
        # Save markdown to file
        save_markdown_to_file(markdown_content, requirements["url"], 1)
        
        return markdown_content
    except Exception as e:
        print(f"Error in main function: {e}")

if __name__ == "__main__":
    # When running directly, API keys would be provided via environment variables or command line
    import os
    claude_api = os.environ.get("CLAUDE_API_KEY")
    openai_api = os.environ.get("OPENAI_API_KEY")
    main(claude_api, openai_api)