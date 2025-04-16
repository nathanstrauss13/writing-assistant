#!/usr/bin/env python3
"""
Test script for the Writing Assistant application.
This script tests basic functionality of the application.
"""

import os
import unittest
import tempfile
import shutil
from app import app

class WritingAssistantTestCase(unittest.TestCase):
    """Test case for the Writing Assistant application."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for uploads
        self.test_upload_dir = tempfile.mkdtemp()
        
        # Configure the application for testing
        app.config['TESTING'] = True
        app.config['UPLOAD_FOLDER'] = self.test_upload_dir
        app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF protection for testing
        
        # Create a test client
        self.client = app.test_client()
        
        # Create test files
        self.test_files = {}
        for category in ['style', 'past', 'competitive']:
            # Create category directory
            os.makedirs(os.path.join(self.test_upload_dir, 'test_session', category), exist_ok=True)
            
            # Create a test file
            test_file_path = os.path.join(self.test_upload_dir, f'test_{category}.txt')
            with open(test_file_path, 'w') as f:
                f.write(f'Test content for {category}')
            
            self.test_files[category] = test_file_path
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove the temporary directory
        shutil.rmtree(self.test_upload_dir)
    
    def test_index_page(self):
        """Test that the index page loads correctly."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Writing Assistant', response.data)
    
    def test_file_upload(self):
        """Test file upload functionality."""
        # Set up a test session
        with self.client.session_transaction() as session:
            session['session_id'] = 'test_session'
        
        # Test uploading a file for each category
        for category in ['style', 'past', 'competitive']:
            with open(self.test_files[category], 'rb') as file:
                response = self.client.post(
                    f'/upload/{category}',
                    data={'file': (file, f'test_{category}.txt')},
                    content_type='multipart/form-data'
                )
            
            # Check response
            self.assertEqual(response.status_code, 200)
            response_data = response.get_json()
            self.assertTrue(response_data['success'])
            self.assertEqual(response_data['filename'], f'test_{category}.txt')
    
    def test_get_files(self):
        """Test getting list of files for a category."""
        # Set up a test session
        with self.client.session_transaction() as session:
            session['session_id'] = 'test_session'
        
        # Create test files in the session directory
        for category in ['style', 'past', 'competitive']:
            category_dir = os.path.join(self.test_upload_dir, 'test_session', category)
            os.makedirs(category_dir, exist_ok=True)
            
            # Create a test file
            with open(os.path.join(category_dir, f'test_{category}.txt'), 'w') as f:
                f.write(f'Test content for {category}')
        
        # Test getting files for each category
        for category in ['style', 'past', 'competitive']:
            response = self.client.get(f'/files/{category}')
            
            # Check response
            self.assertEqual(response.status_code, 200)
            response_data = response.get_json()
            self.assertIn(f'test_{category}.txt', response_data['files'])
    
    def test_delete_file(self):
        """Test deleting a file."""
        # Set up a test session
        with self.client.session_transaction() as session:
            session['session_id'] = 'test_session'
        
        # Create a test file
        category = 'style'
        category_dir = os.path.join(self.test_upload_dir, 'test_session', category)
        os.makedirs(category_dir, exist_ok=True)
        
        test_file_path = os.path.join(category_dir, 'test_delete.txt')
        with open(test_file_path, 'w') as f:
            f.write('Test content for deletion')
        
        # Test deleting the file
        response = self.client.delete(f'/delete/{category}/test_delete.txt')
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = response.get_json()
        self.assertTrue(response_data['success'])
        
        # Check that the file was actually deleted
        self.assertFalse(os.path.exists(test_file_path))
    
    def test_invalid_category(self):
        """Test handling of invalid category."""
        # Test uploading to an invalid category
        with open(self.test_files['style'], 'rb') as file:
            response = self.client.post(
                '/upload/invalid_category',
                data={'file': (file, 'test.txt')},
                content_type='multipart/form-data'
            )
        
        # Check response
        self.assertEqual(response.status_code, 400)
        response_data = response.get_json()
        self.assertIn('error', response_data)
        self.assertEqual(response_data['error'], 'Invalid category')

if __name__ == '__main__':
    unittest.main()
