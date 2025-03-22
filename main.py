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
        # Load the Excel workbook
        wb = openpyxl.load_workbook(file_path, data_only=True)
        
        # Initialize default values
        primary_keyword = ""
        search_volume = "Unknown"
        competition_level = "Medium"
        entities = []
        synonyms = []
        lsi_keywords = {}
        heading_structure = {}
        requirements = {}
        
        # Debug info
        debug_info = {
            "sheets_found": [sheet for sheet in wb.sheetnames],
            "lsi_start_row": None,
            "entities_start_row": None,
            "headings_section": None
        }
        
        # Look for the Basic Tunings sheet
        basic_tunings_sheet = None
        for sheet_name in wb.sheetnames:
            if "basic" in sheet_name.lower() and "tunings" in sheet_name.lower():
                basic_tunings_sheet = wb[sheet_name]
                break
        
        if basic_tunings_sheet:
            print("Found Basic Tunings sheet")
            
            # Extract primary keyword from B1
            if basic_tunings_sheet["B1"].value:
                primary_keyword = basic_tunings_sheet["B1"].value.strip()
                print(f"Primary keyword from B1: {primary_keyword}")
            
            # Extract search volume and competition level
            for row in range(1, 20):  # Check first 20 rows
                cell_a = basic_tunings_sheet.cell(row=row, column=1).value
                if cell_a:
                    cell_a_lower = str(cell_a).lower()
                    if "search volume" in cell_a_lower or "monthly searches" in cell_a_lower:
                        search_volume = basic_tunings_sheet.cell(row=row, column=2).value
                        if search_volume:
                            search_volume = str(search_volume).strip()
                            print(f"Found search volume: {search_volume}")
                    elif "competition" in cell_a_lower or "difficulty" in cell_a_lower:
                        competition_level = basic_tunings_sheet.cell(row=row, column=2).value
                        if competition_level:
                            competition_level = str(competition_level).strip()
                            print(f"Found competition level: {competition_level}")
            
            # Extract synonyms from B2 (pipe-separated)
            if basic_tunings_sheet["B2"].value:
                raw_synonyms = basic_tunings_sheet["B2"].value
                if "|" in raw_synonyms:
                    synonyms = [s.strip() for s in raw_synonyms.split("|") if s.strip()]
                else:
                    synonyms = [raw_synonyms.strip()]
                print(f"Found synonyms: {synonyms}")
            
            # Extract LSI keywords starting from A8 (ignore A7 and above)
            lsi_start_row = 8
            debug_info["lsi_start_row"] = lsi_start_row
            
            # Find the entities section
            entities_start_row = None
            for row in range(lsi_start_row, lsi_start_row + 100):  # Look for "Entities" within reasonable range
                cell_a = basic_tunings_sheet.cell(row=row, column=1).value
                if cell_a and isinstance(cell_a, str) and "entities" in cell_a.lower():
                    entities_start_row = row + 1  # Start from the next row
                    debug_info["entities_start_row"] = entities_start_row
                    break
            
            # If we found a valid entities section, extract LSI keywords up to this point
            if entities_start_row:
                for row in range(lsi_start_row, entities_start_row - 1):
                    keyword = basic_tunings_sheet.cell(row=row, column=1).value
                    frequency = basic_tunings_sheet.cell(row=row, column=3).value
                    
                    if keyword and keyword != "Keyword":  # Skip header row
                        keyword = str(keyword).strip()
                        
                        # Convert frequency to int, defaulting to 1 if not found or invalid
                        try:
                            frequency = int(frequency) if frequency else 1
                        except (ValueError, TypeError):
                            frequency = 1
                        
                        lsi_keywords[keyword] = frequency
                
                # Extract entities
                for row in range(entities_start_row, entities_start_row + 30):  # Assume max 30 entities
                    entity = basic_tunings_sheet.cell(row=row, column=1).value
                    if not entity:
                        break  # Stop at first empty cell
                    
                    entities.append(str(entity).strip())
            
            # Find headings structure
            headings_section = None
            for row in range(1, 100):  # Look for "Headings" within reasonable range
                cell_a = basic_tunings_sheet.cell(row=row, column=1).value
                if cell_a and isinstance(cell_a, str) and "headings" in cell_a.lower():
                    headings_section = row
                    debug_info["headings_section"] = headings_section
                    break
            
            if headings_section:
                # Process rows until another non-empty value in column A (that's not a heading level)
                row = headings_section + 1
                while row < headings_section + 20:  # Limit search to 20 rows after heading section
                    cell_a = basic_tunings_sheet.cell(row=row, column=1).value
                    cell_c = basic_tunings_sheet.cell(row=row, column=3).value
                    cell_e = basic_tunings_sheet.cell(row=row, column=5).value
                    
                    if cell_a and "h" in str(cell_a).lower() and len(str(cell_a).strip()) <= 3:
                        heading_level = str(cell_a).lower().strip()
                        
                        # Get quantity from column E if available, otherwise default to column C
                        quantity = cell_e if cell_e else cell_c
                        try:
                            quantity = int(quantity)
                        except (ValueError, TypeError):
                            quantity = 0
                        
                        if quantity > 0:
                            heading_structure[heading_level] = quantity
                    
                    elif cell_a and not (isinstance(cell_a, str) and "heading" in cell_a.lower()):
                        # Found a non-empty cell that doesn't look like a heading level or heading-related label
                        break
                    
                    row += 1
        
        print(f"Extracted LSI keywords: {lsi_keywords}")
        print(f"Extracted entities: {entities}")
        print(f"Extracted heading structure: {heading_structure}")
        
        # If we don't have a primary keyword, use the first synonym/variation
        if not primary_keyword and synonyms:
            primary_keyword = synonyms[0]
            print(f"Using first synonym as primary keyword: {primary_keyword}")
        
        # Compile results
        results = {
            "primary_keyword": primary_keyword,
            "search_volume": search_volume,
            "competition_level": competition_level,
            "synonyms": synonyms,
            "lsi_keywords": lsi_keywords,
            "entities": entities,
            "heading_structure": heading_structure,
            "requirements": requirements,
            "word_count": 1500,  # Default word count
            "debug_info": debug_info
        }
        
        print(f"✅ Successfully extracted requirements for {primary_keyword}")
        return results
        
    except Exception as e:
        print(f"❌ Error parsing CORA report: {str(e)}")
        import traceback
        traceback.print_exc()
        # Return minimal data to avoid breaking downstream processes
        return {
            "primary_keyword": "Sample Keyword",
            "search_volume": "Unknown",
            "competition_level": "Medium",
            "synonyms": [],
            "lsi_keywords": {},
            "entities": [],
            "heading_structure": {"h2": 3, "h3": 6},
            "requirements": {},
            "word_count": 1500,
            "debug_info": {"error": str(e)}
        }

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
    primary_keyword = requirements["primary_keyword"]
    synonyms = requirements["synonyms"]
    reqs = requirements["requirements"]
    lsi_dict = requirements["lsi_keywords"]
    entities = requirements["entities"]
    word_count = requirements["word_count"]
    heading_overrides = requirements.get("heading_overrides", [])

    # Format requirements, including heading overrides
    req_list = heading_overrides + [f"{desc}: add {amount}" for desc, amount in reqs.items() if "Number of H" not in desc or "tags" not in desc]
    requirements_formatted = "\n".join(req_list)
    synonyms_formatted = ", ".join(synonyms)
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
{synonyms_formatted}
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
def save_markdown_to_file(markdown_str, keyword, iteration):
    """Saves the markdown content to a file with a timestamped filename."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_keyword = keyword.lower().replace(" ", "-").replace("/", "-")
    
    filename = f"{OUTPUT_DIR}/seo_content_{safe_keyword}_iteration_{iteration}_{timestamp}.md"

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
            print(f"✅ Successfully extracted requirements for {requirements['primary_keyword']}")
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
        save_markdown_to_file(markdown_content, requirements["primary_keyword"], 1)
        
        return markdown_content
    except Exception as e:
        print(f"Error in main function: {e}")

if __name__ == "__main__":
    # When running directly, API keys would be provided via environment variables or command line
    import os
    claude_api = os.environ.get("CLAUDE_API_KEY")
    openai_api = os.environ.get("OPENAI_API_KEY")
    main(claude_api, openai_api)