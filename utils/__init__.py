"""
Utility modules for the Writing Assistant application.

This package contains utility modules for file processing, prompt building,
and cleanup operations.
"""

from .file_processor import (
    extract_text_from_file,
    extract_text_from_folder,
    get_file_size,
    get_folder_size
)

from .prompt_builder import (
    construct_prompt,
    optimize_prompt_for_token_limits,
    get_format_details,
    FORMAT_DETAILS
)

from .cleanup import (
    cleanup_old_files,
    get_storage_stats,
    format_size
)

__all__ = [
    # File processor
    'extract_text_from_file',
    'extract_text_from_folder',
    'get_file_size',
    'get_folder_size',
    
    # Prompt builder
    'construct_prompt',
    'optimize_prompt_for_token_limits',
    'get_format_details',
    'FORMAT_DETAILS',
    
    # Cleanup
    'cleanup_old_files',
    'get_storage_stats',
    'format_size'
]
