import os
import uuid
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
from werkzeug.utils import secure_filename
from anthropic import Anthropic
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler

# Import utility modules
from utils.file_processor import extract_text_from_folder, create_docx_from_text
from utils.prompt_builder import optimize_prompt_for_token_limits, FORMAT_DETAILS
from utils.cleanup import cleanup_old_files, get_storage_stats

# Import configuration
from config import get_config

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
config = get_config()
app.config.from_object(config)

# Configure logging
if not os.path.exists(config.LOG_FOLDER):
    os.makedirs(config.LOG_FOLDER)
file_handler = RotatingFileHandler(
    config.LOG_FILE, 
    maxBytes=config.LOG_MAX_BYTES, 
    backupCount=config.LOG_BACKUP_COUNT
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Writing Assistant startup')

# Initialize Anthropic client
anthropic = Anthropic(api_key=config.ANTHROPIC_API_KEY)

# Helper functions
def allowed_file(filename):
    """Check if a filename has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS

def get_session_folder():
    """Get or create a unique session folder for file uploads"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    session_folder = os.path.join(config.UPLOAD_FOLDER, session['session_id'])
    if not os.path.exists(session_folder):
        os.makedirs(session_folder)
        # Create subdirectories for each upload category
        os.makedirs(os.path.join(session_folder, 'style'))
        os.makedirs(os.path.join(session_folder, 'past'))
        os.makedirs(os.path.join(session_folder, 'competitive'))
    
    return session_folder

# Routes
@app.route('/')
def index():
    """Render the main page"""
    # Clean up old files on page load (could be moved to a scheduled task)
    cleanup_old_files(config.UPLOAD_FOLDER, config.FILE_RETENTION_DAYS)
    return render_template('index.html')

@app.route('/upload/<category>', methods=['POST'])
def upload_file(category):
    """Handle file uploads for a specific category"""
    if category not in ['style', 'past', 'competitive']:
        return jsonify({'error': 'Invalid category'}), 400
    
    # Check if the post request has the file part
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    # If user does not select file, browser also
    # submit an empty part without filename
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        # Get session folder
        session_folder = get_session_folder()
        category_folder = os.path.join(session_folder, category)
        
        # Check if maximum files per category is reached
        existing_files = os.listdir(category_folder)
        if len(existing_files) >= config.MAX_FILES_PER_CATEGORY:
            return jsonify({'error': f'Maximum {config.MAX_FILES_PER_CATEGORY} files allowed per category'}), 400
        
        # Save the file
        filename = secure_filename(file.filename)
        file_path = os.path.join(category_folder, filename)
        file.save(file_path)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'category': category
        })
    
    return jsonify({'error': 'File type not allowed'}), 400

@app.route('/files/<category>', methods=['GET'])
def get_files(category):
    """Get list of uploaded files for a category"""
    if category not in ['style', 'past', 'competitive']:
        return jsonify({'error': 'Invalid category'}), 400
    
    session_folder = get_session_folder()
    category_folder = os.path.join(session_folder, category)
    
    files = []
    if os.path.exists(category_folder):
        files = os.listdir(category_folder)
    
    return jsonify({'files': files})

@app.route('/delete/<category>/<filename>', methods=['DELETE'])
def delete_file(category, filename):
    """Delete an uploaded file"""
    if category not in ['style', 'past', 'competitive']:
        return jsonify({'error': 'Invalid category'}), 400
    
    session_folder = get_session_folder()
    file_path = os.path.join(session_folder, category, secure_filename(filename))
    
    if os.path.exists(file_path):
        os.remove(file_path)
        return jsonify({'success': True})
    
    return jsonify({'error': 'File not found'}), 404

@app.route('/generate', methods=['POST'])
def generate_content():
    """Generate content using Anthropic API"""
    # Get form data
    data = request.form
    brief = data.get('brief', '')
    format_type = data.get('format', '')
    custom_word_count = data.get('custom_word_count')
    
    if not brief:
        return jsonify({'error': 'Brief is required'}), 400
    
    if not format_type:
        return jsonify({'error': 'Format is required'}), 400
    
    # Get session folder
    session_folder = get_session_folder()
    
    # Extract text from uploaded files
    style_text = extract_text_from_folder(os.path.join(session_folder, 'style'))
    past_text = extract_text_from_folder(os.path.join(session_folder, 'past'))
    competitive_text = extract_text_from_folder(os.path.join(session_folder, 'competitive'))
    
    # Construct optimized prompt for Claude
    prompt = optimize_prompt_for_token_limits(
        brief, 
        format_type, 
        style_text, 
        past_text, 
        competitive_text,
        custom_word_count,
        max_total_tokens=8000  # Reserve some tokens for the response
    )
    
    try:
        # Log the request parameters
        app.logger.info(f"Generating content with model: {config.CLAUDE_MODEL}")
        app.logger.info(f"Brief length: {len(brief)} characters")
        app.logger.info(f"Format: {format_type}")
        
        # Call Anthropic API - updated for version 0.45.2
        try:
            response = anthropic.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=config.MAX_TOKENS,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # Log successful API call
            app.logger.info("Anthropic API call successful")
            
            # Extract content from the response
            generated_content = response.content[0].text
            
            # Store the generated content in the session
            session['generated_content'] = generated_content
            
            return jsonify({
                'success': True,
                'content': generated_content
            })
        except Exception as api_error:
            # Log detailed API error
            app.logger.error(f"Anthropic API error details: {type(api_error).__name__}: {str(api_error)}")
            if hasattr(api_error, '__dict__'):
                app.logger.error(f"API error attributes: {str(api_error.__dict__)}")
            
            # Re-raise to be caught by the outer try-except
            raise
    except Exception as e:
        app.logger.error(f"Error generating content: {type(e).__name__}: {str(e)}")
        # Return a proper JSON response with error details
        error_response = {'error': f'Error generating content: {str(e)}'}
        app.logger.info(f"Returning error response: {error_response}")
        return jsonify(error_response), 500

@app.route('/result')
def result():
    """Display the generated content"""
    generated_content = session.get('generated_content', '')
    if not generated_content:
        return redirect(url_for('index'))
    
    return render_template('result.html', content=generated_content)

@app.route('/download-docx')
def download_docx():
    """Download the generated content as a DOCX file"""
    generated_content = session.get('generated_content', '')
    if not generated_content:
        return redirect(url_for('index'))
    
    # Convert the content to a DOCX file
    docx_bytes = create_docx_from_text(generated_content)
    if not docx_bytes:
        app.logger.error("Failed to create DOCX file")
        return jsonify({'error': 'Failed to create DOCX file'}), 500
    
    # Return the DOCX file as a download
    return send_file(
        docx_bytes,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True,
        download_name='generated_content.docx'
    )

@app.route('/stats')
def stats():
    """Display storage statistics (admin view)"""
    stats = get_storage_stats(config.UPLOAD_FOLDER)
    return jsonify(stats)

if __name__ == '__main__':
    # Ensure all required directories exist
    if not os.path.exists(config.UPLOAD_FOLDER):
        os.makedirs(config.UPLOAD_FOLDER)
    
    if not os.path.exists(config.LOG_FOLDER):
        os.makedirs(config.LOG_FOLDER)
    
    # Run the app
    app.run(debug=True, port=5001)

# Create required directories at startup
def create_directories():
    """Create all required directories at startup"""
    # Ensure upload directory exists
    if not os.path.exists(config.UPLOAD_FOLDER):
        os.makedirs(config.UPLOAD_FOLDER)
    
    # Ensure log directory exists
    if not os.path.exists(config.LOG_FOLDER):
        os.makedirs(config.LOG_FOLDER)
    
    app.logger.info('Created required directories')

# Call create_directories during initialization
create_directories()
