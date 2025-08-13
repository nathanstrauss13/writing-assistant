import os
import uuid
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
from werkzeug.utils import secure_filename
from anthropic import Anthropic
from dotenv import load_dotenv
import logging
import smtplib
from email.message import EmailMessage
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
        os.makedirs(os.path.join(session_folder, 'materials'))
    
    return session_folder

# Routes
@app.route('/')
def index():
    """Render the main page"""
    # Clean up old files on page load (could be moved to a scheduled task)
    cleanup_old_files(config.UPLOAD_FOLDER, config.FILE_RETENTION_DAYS)

    # Capture UTM params for lead attribution
    utm_keys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content']
    utms = {k: request.args.get(k) for k in utm_keys if request.args.get(k)}
    if utms:
        session['utms'] = utms
        app.logger.info(f"Captured UTMs: {utms}")

    return render_template('index.html')

@app.route('/upload/<category>', methods=['POST'])
def upload_file(category):
    """Handle file uploads for a specific category"""
    if category not in ['style', 'past', 'competitive', 'materials']:
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
    if category not in ['style', 'past', 'competitive', 'materials']:
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
    if category not in ['style', 'past', 'competitive', 'materials']:
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
    # No explicit format selector in UI; default to 'custom'
    format_type = data.get('format') or 'custom'
    custom_word_count = data.get('custom_word_count')

    # Structured brief details
    audience = data.get('audience')
    objective = data.get('objective')
    key_messages = data.get('key_messages')
    constraints = data.get('constraints')
    tone_formality = data.get('tone_formality')
    tone_confidence = data.get('tone_confidence')
    region = data.get('region')
    industry = data.get('industry')
    persona = data.get('persona')

    # Optional pasted text (in addition to uploads)
    materials_paste = data.get('materials_paste')
    
    if not brief:
        return jsonify({'error': 'Brief is required'}), 400
    # format_type now inferred/defaulted to 'custom'
    
    # Get session folder
    session_folder = get_session_folder()
    
    # Extract text from uploaded files with size limits to prevent memory issues
    # Set reasonable limits for each category based on their importance
    materials_text_files = extract_text_from_folder(os.path.join(session_folder, 'materials'), max_chars=150000)
    if not materials_text_files:
        # Backward compatibility: fall back to previous category folders if materials is empty
        style_text_files = extract_text_from_folder(os.path.join(session_folder, 'style'), max_chars=100000)
        past_text_files = extract_text_from_folder(os.path.join(session_folder, 'past'), max_chars=50000)
        competitive_text_files = extract_text_from_folder(os.path.join(session_folder, 'competitive'), max_chars=50000)
        materials_text_files = "\n\n".join(filter(None, [style_text_files, past_text_files, competitive_text_files]))

    # Merge pasted text (if any) with extracted text from files
    materials_text = ((materials_paste.strip() + "\n\n") if materials_paste else "") + (materials_text_files or "")
    
    # Log source material size for debugging
    app.logger.info(f"Source material size - Materials: {len(materials_text)} chars")
    
    # Calculate total size for additional logging
    total_size = len(materials_text)
    app.logger.info(f"Total source material size: {total_size} characters")
    
    # Construct optimized prompt for Claude
    prompt = optimize_prompt_for_token_limits(
        brief,
        format_type,
        materials_text,
        None,
        None,
        custom_word_count,
        max_total_tokens=8000,  # Reserve some tokens for the response
        audience=audience,
        objective=objective,
        key_messages=key_messages,
        constraints=constraints,
        tone_formality=tone_formality,
        tone_confidence=tone_confidence,
        region=region,
        industry=industry,
        persona=persona
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
            
            # Log the size of the generated content
            app.logger.info(f"Generated content size: {len(generated_content)} characters")
            
            # Create a file to store the content instead of using the session
            content_file = os.path.join(session_folder, 'generated_content.txt')
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(generated_content)
            
            # Store only the file path in the session, not the entire content
            session['content_file_path'] = content_file
            
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
    content_file_path = session.get('content_file_path', '')
    
    if not content_file_path or not os.path.exists(content_file_path):
        app.logger.warning("No content file found in session or file doesn't exist")
        return redirect(url_for('index'))
    
    try:
        with open(content_file_path, 'r', encoding='utf-8') as f:
            generated_content = f.read()
        
        return render_template('result.html', content=generated_content)
    except Exception as e:
        app.logger.error(f"Error reading content file: {str(e)}")
        return redirect(url_for('index'))

@app.route('/download-docx')
def download_docx():
    """Download the generated content as a DOCX file"""
    content_file_path = session.get('content_file_path', '')
    
    if not content_file_path or not os.path.exists(content_file_path):
        app.logger.warning("No content file found in session or file doesn't exist")
        return redirect(url_for('index'))
    
    try:
        with open(content_file_path, 'r', encoding='utf-8') as f:
            generated_content = f.read()
        
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
    except Exception as e:
        app.logger.error(f"Error creating or sending DOCX file: {str(e)}")
        return jsonify({'error': f'Error creating DOCX file: {str(e)}'}), 500

@app.route('/stats')
def stats():
    """Display storage statistics (admin view)"""
    stats = get_storage_stats(config.UPLOAD_FOLDER)
    return jsonify(stats)

@app.route('/lead', methods=['POST'])
def lead():
    """Capture lead info and mark session as captured"""
    try:
        name = request.form.get('name') or (request.json.get('name') if request.is_json else None)
        email = request.form.get('email') or (request.json.get('email') if request.is_json else None)
        company = request.form.get('company') or (request.json.get('company') if request.is_json else None)
        consent = request.form.get('consent') or (request.json.get('consent') if request.is_json else None)
        action = request.form.get('action') or (request.json.get('action') if request.is_json else None)

        if not email:
            return jsonify({'error': 'Email is required'}), 400

        lead_record = {
            'session_id': session.get('session_id'),
            'name': name,
            'email': email,
            'company': company,
            'consent': bool(consent) and str(consent).lower() not in ('false','0','no','off',''),
            'action': action or 'unknown',
            'utms': session.get('utms', {}),
        }

        # Persist to logs/leads.jsonl
        if not os.path.exists(config.LOG_FOLDER):
            os.makedirs(config.LOG_FOLDER)
        leads_path = os.path.join(config.LOG_FOLDER, 'leads.jsonl')
        with open(leads_path, 'a', encoding='utf-8') as f:
            import json
            f.write(json.dumps(lead_record) + '\n')

        session['lead_captured'] = True
        app.logger.info(f"Lead captured: {lead_record}")
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error capturing lead: {e}")
        return jsonify({'error': 'Failed to capture lead'}), 500

@app.route('/lead-status', methods=['GET'])
def lead_status():
    """Return current gating status for the session"""
    return jsonify({
        'enable_gating': bool(getattr(config, 'ENABLE_GATING', False)),
        'free_docx': bool(getattr(config, 'FREE_DOWNLOAD_DOCX', True)),
        'lead_captured': bool(session.get('lead_captured', False))
    })

@app.route('/email-result', methods=['POST'])
def email_result():
    """Email the generated content to the provided address"""
    content_file_path = session.get('content_file_path', '')
    if not content_file_path or not os.path.exists(content_file_path):
        return jsonify({'error': 'No content to email'}), 400

    to_email = request.form.get('email') or (request.json.get('email') if request.is_json else None)
    name = request.form.get('name') or (request.json.get('name') if request.is_json else None)
    if not to_email:
        return jsonify({'error': 'Email is required'}), 400

    try:
        with open(content_file_path, 'r', encoding='utf-8') as f:
            generated_content = f.read()

        if not config.SMTP_HOST or not config.SMTP_USER or not config.SMTP_PASSWORD or not config.EMAIL_SENDER:
            app.logger.info(f"[DEV] Would send email to {to_email} with sender {config.EMAIL_SENDER}. SMTP not configured.")
            return jsonify({'success': True, 'dev': True})

        msg = EmailMessage()
        msg['Subject'] = 'Your generated content from innate c3 Writing Assistant'
        msg['From'] = config.EMAIL_SENDER
        msg['To'] = to_email
        greeting = f"Hi {name}," if name else "Hi,"
        body = f"""{greeting}

Attached below is the content you generated with the innate c3 Writing Assistant.

—
innate c3
https://innatec3.com
"""
        msg.set_content(body + "\n\n" + generated_content)

        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)

        app.logger.info(f"Emailed result to {to_email}")
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error sending email: {e}")
        return jsonify({'error': 'Failed to send email'}), 500

# Create required directories at startup
def create_directories():
    """Create all required directories at startup"""
    # Ensure upload directory exists
    if not os.path.exists(config.UPLOAD_FOLDER):
        os.makedirs(config.UPLOAD_FOLDER)
        app.logger.info(f"Created upload directory: {config.UPLOAD_FOLDER}")
    
    # Ensure log directory exists
    if not os.path.exists(config.LOG_FOLDER):
        os.makedirs(config.LOG_FOLDER)
        app.logger.info(f"Created log directory: {config.LOG_FOLDER}")

# Call create_directories during initialization
create_directories()

if __name__ == '__main__':
    # Run the app
    app.run(debug=True, port=5001)
