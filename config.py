import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration class"""
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'writing_assistant_secret_key')
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
    
    # File upload settings
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx'}
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
    MAX_FILES_PER_CATEGORY = 3
    FILE_RETENTION_DAYS = 7
    
    # Logging settings
    LOG_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    LOG_FILE = os.path.join(LOG_FOLDER, 'writing_assistant.log')
    LOG_MAX_BYTES = 10240
    LOG_BACKUP_COUNT = 10
    
    # Claude model settings
    CLAUDE_MODEL = "claude-2.0"  # Compatible with Completions API
    MAX_TOKENS = 4000

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = False
    TESTING = True
    # Use a separate test upload folder
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_uploads')

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    # In production, you might want to use a more secure secret key
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

# Dictionary to map environment names to config classes
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

# Get the current configuration based on environment variable
def get_config():
    """Get the current configuration based on environment variable"""
    env = os.environ.get('FLASK_ENV', 'default')
    return config.get(env, config['default'])
