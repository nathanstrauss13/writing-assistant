import logging

# Set up logging
logger = logging.getLogger(__name__)

# Format definitions
FORMAT_DETAILS = {
    'speech_15min': {
        'description': '15-minute speech',
        'word_count': 2000,
        'characteristics': 'conversational, engaging, with clear sections and natural transitions'
    },
    'letter_1000': {
        'description': '1,000-word letter',
        'word_count': 1000,
        'characteristics': 'formal, structured, with a clear introduction and conclusion'
    },
    'blog_500': {
        'description': '500-word blog post',
        'word_count': 500,
        'characteristics': 'informative, engaging, with a compelling headline and clear takeaways'
    },
    'linkedin': {
        'description': 'LinkedIn post',
        'word_count': 300,
        'characteristics': 'professional, concise, with a hook and call-to-action'
    },
    'press_release': {
        'description': 'Press release',
        'word_count': 800,
        'characteristics': 'formal, factual, with quotes and a clear news angle'
    },
    'exec_summary': {
        'description': 'Executive summary',
        'word_count': 500,
        'characteristics': 'concise, data-driven, highlighting key points and recommendations'
    },
    'custom': {
        'description': 'Custom format',
        'word_count': 1000,
        'characteristics': 'well-structured and professional'
    }
}

def get_format_details(format_type, custom_word_count=None):
    """
    Get the details for a specific format type
    
    Args:
        format_type (str): The format type key
        custom_word_count (int, optional): Custom word count for 'custom' format
        
    Returns:
        dict: Format details including description, word count, and characteristics
    """
    # Get the format details or default to custom if not found
    format_info = FORMAT_DETAILS.get(format_type, FORMAT_DETAILS['custom'])
    
    # If it's a custom format and a word count is provided, update the word count
    if format_type == 'custom' and custom_word_count is not None:
        try:
            word_count = int(custom_word_count)
            format_info = format_info.copy()  # Create a copy to avoid modifying the original
            format_info['word_count'] = word_count
        except (ValueError, TypeError):
            logger.warning(f"Invalid custom word count: {custom_word_count}. Using default.")
    
    return format_info

def construct_prompt(brief, format_type, style_text=None, past_text=None, competitive_text=None, custom_word_count=None):
    """
    Construct a prompt for Claude based on the user inputs and uploaded files
    
    Args:
        brief (str): The writing brief
        format_type (str): The format type key
        style_text (str, optional): Text from style examples
        past_text (str, optional): Text from past examples
        competitive_text (str, optional): Text from competitive examples
        custom_word_count (int, optional): Custom word count for 'custom' format
        
    Returns:
        str: The constructed prompt for Claude
    """
    # Get format details
    format_info = get_format_details(format_type, custom_word_count)
    
    # Construct the prompt
    prompt = f"""You are an expert communications professional tasked with writing a {format_info['description']} (approximately {format_info['word_count']} words) that is {format_info['characteristics']}.

BRIEF:
{brief}

"""
    
    # Add writing style examples if available
    if style_text:
        prompt += f"""
WRITING STYLE EXAMPLES:
The following examples demonstrate the desired writing style and tone. Please emulate this style in your response:

{style_text}

"""
    
    # Add past examples if available
    if past_text:
        prompt += f"""
PAST EXAMPLES:
The following are examples of similar content from the past. Use these for reference on structure and approach:

{past_text}

"""
    
    # Add competitive examples if available
    if competitive_text:
        prompt += f"""
COMPETITIVE EXAMPLES:
The following are examples from competitors or similar organizations. Draw inspiration from these while maintaining originality:

{competitive_text}

"""
    
    # Final instructions
    prompt += f"""
Please write a {format_info['description']} based on the brief provided, incorporating the style from the examples and drawing inspiration from the competitive examples. The content should be approximately {format_info['word_count']} words and should be {format_info['characteristics']}.

Format your response as a complete, ready-to-use document without explanations or meta-commentary.
"""
    
    logger.info(f"Constructed prompt for {format_info['description']} with {len(prompt)} characters")
    
    return prompt

def estimate_token_count(text):
    """
    Estimate the number of tokens in a text (rough approximation)
    
    Args:
        text (str): The text to estimate tokens for
        
    Returns:
        int: Estimated token count
    """
    # A very rough approximation: 1 token ≈ 4 characters for English text
    return len(text) // 4

def truncate_text_to_fit(text, max_tokens, section_name):
    """
    Truncate text to fit within token limits
    
    Args:
        text (str): The text to truncate
        max_tokens (int): Maximum number of tokens
        section_name (str): Name of the section for logging
        
    Returns:
        str: Truncated text
    """
    estimated_tokens = estimate_token_count(text)
    
    if estimated_tokens <= max_tokens:
        return text
    
    # Simple truncation strategy - keep the beginning and add a note
    # A more sophisticated approach would be to extract key sections or summarize
    chars_to_keep = max_tokens * 4  # Convert tokens back to approximate characters
    truncated_text = text[:chars_to_keep]
    
    # Add a note about truncation
    truncation_note = f"\n\n[Note: The {section_name} content was truncated to fit within token limits.]"
    
    logger.warning(f"Truncated {section_name} from {estimated_tokens} to {max_tokens} tokens")
    
    return truncated_text + truncation_note

def optimize_prompt_for_token_limits(brief, format_type, style_text=None, past_text=None, competitive_text=None, 
                                    custom_word_count=None, max_total_tokens=8000):
    """
    Optimize the prompt to fit within token limits by allocating tokens to different sections
    
    Args:
        brief (str): The writing brief
        format_type (str): The format type key
        style_text (str, optional): Text from style examples
        past_text (str, optional): Text from past examples
        competitive_text (str, optional): Text from competitive examples
        custom_word_count (int, optional): Custom word count for 'custom' format
        max_total_tokens (int): Maximum total tokens for the prompt
        
    Returns:
        str: The optimized prompt
    """
    # Reserve tokens for the prompt structure and instructions
    structure_tokens = 500
    
    # Reserve tokens for the brief (highest priority)
    brief_tokens = min(estimate_token_count(brief), 1500)
    
    # Calculate remaining tokens for examples
    remaining_tokens = max_total_tokens - structure_tokens - brief_tokens
    
    # If we have all three types of examples, allocate tokens proportionally
    if style_text and past_text and competitive_text:
        style_tokens = remaining_tokens // 3
        past_tokens = remaining_tokens // 3
        competitive_tokens = remaining_tokens - style_tokens - past_tokens
    
    # If we have two types of examples, split remaining tokens
    elif style_text and past_text:
        style_tokens = remaining_tokens // 2
        past_tokens = remaining_tokens - style_tokens
        competitive_tokens = 0
    elif style_text and competitive_text:
        style_tokens = remaining_tokens // 2
        past_tokens = 0
        competitive_tokens = remaining_tokens - style_tokens
    elif past_text and competitive_text:
        style_tokens = 0
        past_tokens = remaining_tokens // 2
        competitive_tokens = remaining_tokens - past_tokens
    
    # If we have only one type of example, allocate all remaining tokens
    elif style_text:
        style_tokens = remaining_tokens
        past_tokens = 0
        competitive_tokens = 0
    elif past_text:
        style_tokens = 0
        past_tokens = remaining_tokens
        competitive_tokens = 0
    elif competitive_text:
        style_tokens = 0
        past_tokens = 0
        competitive_tokens = remaining_tokens
    
    # If we have no examples, no need to allocate tokens
    else:
        style_tokens = 0
        past_tokens = 0
        competitive_tokens = 0
    
    # Truncate texts if necessary
    optimized_brief = brief
    optimized_style_text = truncate_text_to_fit(style_text, style_tokens, "writing style examples") if style_text else None
    optimized_past_text = truncate_text_to_fit(past_text, past_tokens, "past examples") if past_text else None
    optimized_competitive_text = truncate_text_to_fit(competitive_text, competitive_tokens, "competitive examples") if competitive_text else None
    
    # Construct the optimized prompt
    return construct_prompt(
        optimized_brief, 
        format_type, 
        optimized_style_text, 
        optimized_past_text, 
        optimized_competitive_text, 
        custom_word_count
    )
