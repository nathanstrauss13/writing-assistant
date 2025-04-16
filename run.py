#!/usr/bin/env python3
"""
Run script for the Writing Assistant application.
This script provides a convenient way to start the application.
"""

import os
import argparse
from app import app

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run the Writing Assistant application')
    parser.add_argument('--host', default='127.0.0.1', help='Host to run the server on')
    parser.add_argument('--port', type=int, default=5001, help='Port to run the server on')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    return parser.parse_args()

def main():
    """Main entry point for the application."""
    args = parse_args()
    
    # Ensure required directories exist
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    # Print startup message
    print(f"Starting Writing Assistant on http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop the server")
    
    # Run the Flask application
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug
    )

if __name__ == '__main__':
    main()
