import os
import shutil
import logging
from datetime import datetime, timedelta

# Set up logging
logger = logging.getLogger(__name__)

def cleanup_old_files(upload_folder, retention_days=7):
    """
    Remove files and folders older than the specified retention period
    
    Args:
        upload_folder (str): Path to the upload folder
        retention_days (int): Number of days to retain files
        
    Returns:
        tuple: (int, int) - Number of files removed, number of directories removed
    """
    if not os.path.exists(upload_folder):
        logger.warning(f"Upload folder does not exist: {upload_folder}")
        return 0, 0
    
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    logger.info(f"Cleaning up files older than {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")
    
    files_removed = 0
    dirs_removed = 0
    
    # Iterate through session directories
    for session_id in os.listdir(upload_folder):
        session_path = os.path.join(upload_folder, session_id)
        
        # Skip if not a directory
        if not os.path.isdir(session_path):
            continue
        
        # Check the modification time of the session directory
        try:
            mod_time = datetime.fromtimestamp(os.path.getmtime(session_path))
            
            if mod_time < cutoff_date:
                logger.info(f"Removing old session directory: {session_id} (last modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')})")
                
                # Count files before removal
                file_count = sum(len(files) for _, _, files in os.walk(session_path))
                
                # Remove the directory and all its contents
                shutil.rmtree(session_path)
                
                files_removed += file_count
                dirs_removed += 1
                
                logger.info(f"Removed session directory {session_id} with {file_count} files")
        except Exception as e:
            logger.error(f"Error processing session directory {session_id}: {str(e)}")
    
    logger.info(f"Cleanup complete. Removed {files_removed} files and {dirs_removed} directories.")
    return files_removed, dirs_removed

def get_storage_stats(upload_folder):
    """
    Get statistics about the storage usage
    
    Args:
        upload_folder (str): Path to the upload folder
        
    Returns:
        dict: Storage statistics
    """
    if not os.path.exists(upload_folder):
        logger.warning(f"Upload folder does not exist: {upload_folder}")
        return {
            'total_size': 0,
            'total_files': 0,
            'total_sessions': 0,
            'oldest_session': None,
            'newest_session': None
        }
    
    total_size = 0
    total_files = 0
    sessions = []
    
    # Iterate through session directories
    for session_id in os.listdir(upload_folder):
        session_path = os.path.join(upload_folder, session_id)
        
        # Skip if not a directory
        if not os.path.isdir(session_path):
            continue
        
        # Get session modification time
        try:
            mod_time = datetime.fromtimestamp(os.path.getmtime(session_path))
            
            # Count files and size
            session_size = 0
            session_files = 0
            
            for root, _, files in os.walk(session_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_size = os.path.getsize(file_path)
                    
                    session_size += file_size
                    session_files += 1
            
            # Add to totals
            total_size += session_size
            total_files += session_files
            
            # Add session info
            sessions.append({
                'id': session_id,
                'modified': mod_time,
                'size': session_size,
                'files': session_files
            })
        except Exception as e:
            logger.error(f"Error processing session directory {session_id}: {str(e)}")
    
    # Sort sessions by modification time
    sessions.sort(key=lambda x: x['modified'])
    
    # Get oldest and newest sessions
    oldest_session = sessions[0] if sessions else None
    newest_session = sessions[-1] if sessions else None
    
    return {
        'total_size': total_size,
        'total_files': total_files,
        'total_sessions': len(sessions),
        'oldest_session': oldest_session,
        'newest_session': newest_session
    }

def format_size(size_bytes):
    """
    Format a size in bytes to a human-readable string
    
    Args:
        size_bytes (int): Size in bytes
        
    Returns:
        str: Formatted size string
    """
    # Handle edge cases
    if size_bytes < 0:
        return "Invalid size"
    if size_bytes == 0:
        return "0 B"
    
    # Define size units and their thresholds
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    
    # Convert to appropriate unit
    while size_bytes >= 1024 and i < len(units) - 1:
        size_bytes /= 1024.0
        i += 1
    
    # Format with appropriate precision
    if i == 0:  # Bytes
        return f"{int(size_bytes)} {units[i]}"
    else:
        return f"{size_bytes:.2f} {units[i]}"
