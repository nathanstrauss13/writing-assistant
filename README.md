# Writing Assistant

A companion app to the media analysis tool that assists communications professionals with writing tasks using the Anthropic API.

## Features

- **Multiple File Upload Areas**:
  - **Writing Style Examples**: Upload samples that demonstrate the desired writing style (e.g., CEO's previous communications)
  - **Past Examples**: Upload previous examples of similar content (e.g., past shareholder letters)
  - **Competitive Examples**: Upload examples from competitors or similar organizations for inspiration

- **Customizable Content Generation**:
  - Detailed brief input
  - Multiple format options (speeches, letters, blog posts, etc.)
  - Custom word count option

- **Content Management**:
  - Copy to clipboard
  - Download as TXT
  - (Future feature: Download as DOCX)

## Technical Details

- Built with Flask
- Uses Anthropic's Claude API for content generation
- Supports PDF, DOCX, and TXT file uploads
- Automatic file cleanup after 7 days

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd writing-assistant
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file based on the example:
   ```
   cp .env.example .env
   ```

5. Edit the `.env` file and add your Anthropic API key:
   ```
   ANTHROPIC_API_KEY=your_api_key_here
   ```

## Usage

1. Start the Flask development server:
   ```
   flask run
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:5000/
   ```

3. Fill in the writing brief, select a format, and optionally upload reference files.

4. Click "Generate Content" to create your content.

## File Upload Limits

- Maximum 3 files per category
- Maximum 10MB total upload size
- Supported formats: PDF, DOCX, TXT
- Files are automatically deleted after 7 days

## Development

### Project Structure

```
writing-assistant/
├── app.py                  # Main Flask application
├── config.py               # Configuration settings
├── requirements.txt        # Dependencies
├── .env.example            # Environment variables template
├── static/                 # Static assets
├── templates/              # HTML templates
│   ├── index.html          # Main application page
│   └── result.html         # Results display page
├── utils/                  # Utility functions
│   ├── file_processor.py   # File handling and text extraction
│   ├── prompt_builder.py   # Claude prompt construction
│   └── cleanup.py          # File retention management
└── uploads/                # Temporary file storage (gitignored)
```

### Adding New Format Types

To add a new format type, edit the `FORMAT_DETAILS` dictionary in `utils/prompt_builder.py`:

```python
FORMAT_DETAILS = {
    'new_format_key': {
        'description': 'Description of the format',
        'word_count': 1000,  # Default word count
        'characteristics': 'Characteristics of the format'
    },
    # ... existing formats
}
```

Then update the format dropdown in `templates/index.html` to include the new option.

## License

[MIT License](LICENSE)

## Acknowledgements

- [Anthropic](https://www.anthropic.com/) for the Claude API
- [Flask](https://flask.palletsprojects.com/) web framework
- [Tailwind CSS](https://tailwindcss.com/) for styling
- [Dropzone.js](https://www.dropzonejs.com/) for file uploads
