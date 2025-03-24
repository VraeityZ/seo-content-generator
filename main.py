import os
import re
import pandas as pd
import anthropic
from openai import OpenAI
from datetime import datetime
import warnings
import openpyxl
import math
import logging
import re

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl.styles.stylesheet")

# Define output directory
OUTPUT_DIR = "output_markdown"

# Placeholder for API keys - these should be set in environment variables or Streamlit secrets
def get_api_keys(claude_api, openai_api):
    return claude_api, openai_api

# Model selection
platform = "Claude"  # @param ["Claude"]
claude_model = "claude-3-7-sonnet-latest"
chatgpt_model = "o1-mini-2024-09-12"

# Heading control variables (global for simplicity; adjust as needed for Streamlit)
h2_control = 0  # @param {"type":"number","placeholder":"0"}
h3_control = 0  # @param {"type":"number","placeholder":"0"}
h4_control = 0  # @param {"type":"number","placeholder":"0"}
h5_control = 0  # @param {"type":"number","placeholder":"0"}
h6_control = 0  # @param {"type":"number","placeholder":"0"}

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
    """Placeholder for Streamlit file upload."""
    return None

##############################################################################
# PARSE CORA REPORT
##############################################################################
def parse_cora_report(file_path):
    """Parses a CORA Excel report and extracts SEO requirements."""
    try:
        # Load the Excel workbook
        wb = openpyxl.load_workbook(file_path, data_only=True)
        
        # Initialize default values
        primary_keyword = ""
        entities = []
        variations = []
        lsi_keywords = {}
        heading_structure = {}
        requirements = {}
        word_count = 1500  # Default
        
        # Debug info
        debug_info = {
            "sheets_found": wb.sheetnames,
            "lsi_start_row": None,
            "entities_start_row": None,
            "headings_section": None
        }
        
        # Parse "Roadmap" sheet
        if "Roadmap" in wb.sheetnames:
            roadmap_sheet = wb["Roadmap"]
            
            # Variations from A2
            raw_variations = roadmap_sheet["A2"].value
            variations = [v.strip(' "\'') for v in raw_variations.split(",") if v.strip()] if raw_variations else []
            
            # Extract requirements from "Phase 1: Title & Headings"
            marker_start = "Phase 1: Title & Headings"
            possible_end_markers = [
                "Phase 2: Content",
                "Phase 3: Authority",
                "Phase 4: Diversity",
                "Phase 6: Search Result Presentation",
                "Phase 7: Outbound Linking From the Page"
            ]
            
            # Find start row
            start_row = None
            for row in range(1, 100):
                cell_a = roadmap_sheet.cell(row=row, column=1).value
                if cell_a and marker_start in str(cell_a).strip():
                    start_row = row + 1
                    break
                    
            if start_row:
                # Find end row based on possible markers
                end_row = None
                for row in range(start_row, 100):
                    cell_a = roadmap_sheet.cell(row=row, column=1).value
                    if cell_a:
                        cell_text = str(cell_a).strip()
                        if any(marker in cell_text for marker in possible_end_markers):
                            end_row = row
                            break
                            
                if not end_row:
                    end_row = roadmap_sheet.max_row
                    
                # Extract requirements
                for row in range(start_row, end_row):
                    req_desc = roadmap_sheet.cell(row=row, column=1).value
                    req_amount_text = roadmap_sheet.cell(row=row, column=2).value
                    
                    if req_desc and req_amount_text:
                        try:
                            # Use regex to find the first number in the text
                            match = re.search(r"(\d+)", str(req_amount_text))
                            if match:
                                amount = int(match.group(1))
                                requirements[req_desc] = amount
                        except (ValueError, TypeError):
                            logging.warning(f"Could not parse requirement amount: {req_amount_text}")
                            continue
        
        # Parse "Basic Tunings" sheet
        if "Basic Tunings" in wb.sheetnames:
            basic_tunings_sheet = wb["Basic Tunings"]
            # Primary keyword from B1
            primary_keyword = basic_tunings_sheet["B1"].value.strip() if basic_tunings_sheet["B1"].value else ""
            # Word count from CP492
            for row in range(1, basic_tunings_sheet.max_row + 1):
                if basic_tunings_sheet.cell(row=row, column=2).value == "CP492":
                    word_count_value = basic_tunings_sheet.cell(row=row, column=5).value
                    if word_count_value:
                        try:
                            word_count = int(word_count_value)
                        except ValueError:
                            pass
                    break
            # Number of H2 Tags
            for row in range(1, basic_tunings_sheet.max_row + 1):
                if basic_tunings_sheet.cell(row=row, column=2).value == "CPXR005":
                    heading_2_value = basic_tunings_sheet.cell(row=row, column=5).value
                    if heading_2_value:
                        try:
                            heading_2 = int(heading_2_value)
                        except ValueError:
                            pass
                    break
            # Number of H3 Tags
            for row in range(1, basic_tunings_sheet.max_row + 1):
                if basic_tunings_sheet.cell(row=row, column=2).value == "CPXR006":
                    heading_3_value = basic_tunings_sheet.cell(row=row, column=5).value
                    if heading_3_value:
                        try:
                            heading_3 = int(heading_3_value)
                        except ValueError:
                            pass
                    break
            # Number of H4 Tags
            for row in range(1, basic_tunings_sheet.max_row + 1):
                if basic_tunings_sheet.cell(row=row, column=2).value == "CPXR007":
                    heading_4_value = basic_tunings_sheet.cell(row=row, column=5).value
                    if heading_4_value:
                        try:
                            heading_4 = int(heading_4_value)
                        except ValueError:
                            pass
                    break
            # Number of H5 Tags
            for row in range(1, basic_tunings_sheet.max_row + 1):
                if basic_tunings_sheet.cell(row=row, column=2).value == "CPXR008":
                    heading_5_value = basic_tunings_sheet.cell(row=row, column=5).value
                    if heading_5_value:
                        try:
                            heading_5 = int(heading_5_value)
                        except ValueError:
                            pass
                    break
            # Number of H6 Tags
            for row in range(1, basic_tunings_sheet.max_row + 1):
                if basic_tunings_sheet.cell(row=row, column=2).value == "CPXR009":
                    heading_6_value = basic_tunings_sheet.cell(row=row, column=5).value
                    if heading_6_value:
                        try:
                            heading_6 = int(heading_6_value)
                        except ValueError:
                            pass
                    break   
        # Number of heading tags
            for row in range(1, basic_tunings_sheet.max_row + 1):
                if basic_tunings_sheet.cell(row=row, column=2).value == "CPXR003":
                    total_heading_value = basic_tunings_sheet.cell(row=row, column=5).value
                    if total_heading_value:
                        try:
                            total_heading = int(total_heading_value)
                        except ValueError:
                            pass
                    break   
            requirements["Number of H2 tags"] = heading_2
            requirements["Number of H3 tags"] = heading_3
            requirements["Number of H4 tags"] = heading_4
            requirements["Number of H5 tags"] = heading_5
            requirements["Number of H6 tags"] = heading_6
            requirements["Number of heading tags"] = total_heading

        # Parse "LSI Keywords" sheet
        lsi_sheet_name = next((s for s in wb.sheetnames if "LSI" in s and "Keywords" in s), None)
        if lsi_sheet_name:
            lsi_sheet = wb[lsi_sheet_name]
            for row in range(7, lsi_sheet.max_row + 1):  # Header at row 6
                keyword = lsi_sheet.cell(row=row, column=1).value
                avg = lsi_sheet.cell(row=row, column=2).value
                deficit = lsi_sheet.cell(row=row, column=3).value
                if keyword and avg:
                    try:
                        avg = float(avg)
                        deficit = float(deficit) if deficit else 0
                        if deficit > 0:
                            lsi_keywords[keyword] = math.ceil(avg + deficit)
                    except ValueError:
                        continue
            lsi_keywords = dict(sorted(lsi_keywords.items(), key=lambda x: x[1], reverse=True)[:40])
        
        # Parse "Entities" sheet
        if "Entities" in wb.sheetnames:
            entities_sheet = wb["Entities"]
            for row in range(3, entities_sheet.max_row + 1):  # Header at row 2
                entity = entities_sheet.cell(row=row, column=1).value
                if entity:
                    entities.append(str(entity).strip())
        
        # Handle heading overrides
        heading_controls = {
            2: heading_2,
            3: heading_3,
            4: heading_4,
            5: heading_5,
            6: heading_6
        }
        heading_overrides = []
        for level, control in heading_controls.items():
            if control > 0:
                for key in list(requirements.keys()):
                    if f"number of h{level} tags" in key.lower():
                        del requirements[key]
                requirements[f"Number of H{level} tags"] = control
                heading_overrides.append(f"Important: Headings override. Ignore Number of H{level} required. Instead use {control}")
        
        if "Number of Heading Tags" in requirements:
            total_headings = 1  # For H1
            for row in range(1, basic_tunings_sheet.max_row + 1):
                if basic_tunings_sheet.cell(row=row, column=2).value == "CPXR003":
                    total_heading_value = basic_tunings_sheet.cell(row=row, column=5).value
                    if total_heading_value:
                        try:
                            total_heading = int(total_heading_value)
                        except ValueError:
                            pass
                    break   
            requirements["Number of Heading Tags"] = total_heading

        
        # Compile results
        results = {
            "primary_keyword": primary_keyword,
            "variations": variations,
            "lsi_keywords": lsi_keywords,
            "entities": entities,
            "heading_structure": heading_structure,  # Kept for compatibility, though unused
            "requirements": requirements,
            "word_count": word_count,
            "heading_overrides": heading_overrides,
            "debug_info": debug_info
        }
        
        print(f"✅ Successfully extracted requirements for {primary_keyword}")
        return results
        
    except Exception as e:
        print(f"❌ Error parsing CORA report: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "primary_keyword": "Sample Keyword",
            "variations": [],
            "lsi_keywords": {},
            "entities": [],
            "heading_structure": {"h2": 3, "h3": 6},
            "requirements": {},
            "word_count": 1500,
            "heading_overrides": [],
            "debug_info": {"error": str(e)}
        }

##############################################################################
# GENERATE HEADING STRUCTURE
##############################################################################
def generate_heading_structure(primary_keyword, heading_structure, lsi_keywords=None, entities=None):
    """Generates a heading structure string based on SEO requirements."""
    if lsi_keywords is None:
        lsi_keywords = []
    if entities is None:
        entities = []
    
    headings_text = "HEADING STRUCTURE:\n"
    headings_text += f"1. H1: Include one H1 title that contains the primary keyword '{primary_keyword}'\n"
    
    for level in range(2, 6):
        key = f"h{level}"
        count = heading_structure.get(key, 0)
        if count > 0:
            headings_text += f"{level}. H{level}: Include approximately {count} H{level} headings"
            if level <= 3 and (lsi_keywords or entities):
                headings_text += " - consider including these topics:\n"
                for kw in lsi_keywords[:min(len(lsi_keywords), 3)]:
                    headings_text += f"   - {kw}\n"
                for entity in entities[:min(len(entities), 2)]:
                    headings_text += f"   - {entity}\n"
            else:
                headings_text += "\n"
    
    return headings_text

##############################################################################
# GENERATE INITIAL MARKDOWN
##############################################################################
def generate_initial_markdown(requirements, claude_api, openai_api):
    """Generates SEO-optimized markdown based on CORA report requirements."""
    primary_keyword = requirements["primary_keyword"]
    variations = requirements["variations"]
    reqs = requirements["requirements"]
    lsi_dict = requirements["lsi_keywords"]
    entities = requirements["entities"]
    word_count = requirements["word_count"]
    heading_overrides = requirements.get("heading_overrides", [])

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
title: "Your Title Here"
description: "Your meta description here"
7. IMPORTANT: Ensure and Confirm each step in the final Step list is met.
</final step>
"""
    print("\n=== Initial Markdown Generation Prompt ===")
    with open("prompt.txt", "w") as f:
        f.write(f"System Prompt:\n{system_prompt}\n\n\nUser Prompt:{user_prompt}")
    print("=== Prompt output saved to prompt.txt ===\n")
    
    client, model = initialize_api_clients(claude_api, openai_api)
    if platform == "Claude":
        response = client.messages.create(
            model=model,
            max_tokens=15000,
            system=system_prompt,
            messages=[{"role": "user", "content": [{"type": "text", "text": user_prompt}]}],
            thinking={"type": "enabled", "budget_tokens": 14750}
        )
        markdown_content = "".join(block.text for block in response.content if block.type == "text")
        markdown_content = extract_markdown_from_response(markdown_content)
    else:
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
    """Saves markdown content to a file."""
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
# EXTRACT MARKDOWN FROM RESPONSE
##############################################################################
def extract_markdown_from_response(response_text):
    """Extracts markdown content from an API response."""
    markdown_match = re.search(r'```(?:markdown)?(.*?)```', response_text, re.DOTALL)
    if markdown_match:
        return markdown_match.group(1).strip()
    return response_text.strip()

##############################################################################
# EXTRACT HTML FROM RESPONSE
##############################################################################
def extract_html_from_response(response_text):
    """Extracts HTML content from an API response."""
    html_match = re.search(r'```(?:html)?(.*?)```', response_text, re.DOTALL)
    if html_match:
        return html_match.group(1).strip()
    
    html_tag_match = re.search(r'<html.*?>(.*?)</html>', response_text, re.DOTALL)
    if html_tag_match:
        return f"<html>{html_tag_match.group(1)}</html>"
    
    return response_text.strip()

##############################################################################
# GENERATE INITIAL HTML
##############################################################################
def generate_initial_html(markdown_content, api_key):
    """Converts markdown to HTML."""
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
    if platform == "Claude":
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=claude_model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        html_content = extract_html_from_response(response.content[0].text)
    else:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=chatgpt_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=4096
        )
        html_content = extract_html_from_response(response.choices[0].message.content)
    
    filename = f"{OUTPUT_DIR}/output.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"✅ HTML saved to {filename}")
    return html_content

##############################################################################
# GENERATE CONTENT
##############################################################################
def generate_content(requirements, claude_api=None, openai_api=None, settings=None):
    """Generates markdown and HTML content."""
    try:
        if settings:
            claude_api = settings.get('anthropic_api_key') or claude_api
            openai_api = settings.get('openai_api_key') or openai_api
        
        markdown_content = generate_initial_markdown(requirements, claude_api, openai_api)
        html_content = ""
        try:
            html_content = generate_initial_html(markdown_content, claude_api)
        except Exception as e:
            print(f"Warning: Could not generate HTML: {e}")
            html_content = f"<h1>{requirements.get('primary_keyword', 'Content')}</h1>\n" + markdown_content.replace("\n", "<br>")
        
        save_path = save_markdown_to_file(markdown_content, requirements.get("primary_keyword", "content"), 1)
        return markdown_content, html_content, save_path
    except Exception as e:
        print(f"Error in generate_content: {e}")
        raise e

##############################################################################
# MAIN FUNCTION
##############################################################################
def main(claude_api, openai_api):
    """Orchestrates the markdown generation process."""
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        uploaded = upload_file()
        if not uploaded:
            print("No file uploaded. Exiting.")
            return
        
        file_path = uploaded
        print("Parsing CORA report...")
        requirements = parse_cora_report(file_path)
        print(f"✅ Successfully extracted requirements for {requirements['primary_keyword']}")
        print(f"Primary Keyword: {requirements['primary_keyword']}")
        print(f"Word Count Target: {requirements['word_count']}")
        print(f"Entities Found: {len(requirements['entities'])}")
        print(f"LSI Keywords Found: {len(requirements['lsi_keywords'])}")
        print()
        
        markdown_content = generate_initial_markdown(requirements, claude_api, openai_api)
        save_markdown_to_file(markdown_content, requirements["primary_keyword"], 1)
        return markdown_content
    except Exception as e:
        print(f"Error in main function: {e}")
        return None

if __name__ == "__main__":
    claude_api = os.environ.get("CLAUDE_API_KEY")
    openai_api = os.environ.get("OPENAI_API_KEY")
    main(claude_api, openai_api)