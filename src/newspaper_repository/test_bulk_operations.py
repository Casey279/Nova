"""
Test script for bulk operations in the background service.

This script demonstrates how to use the bulk operation features
of the enhanced background service.
"""

import os
import time
import sys
import logging
from typing import Dict, List, Any
import json
import datetime
import argparse

# Mock classes to handle missing database
class MockRepositoryDatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.pages = {}
        self.queue = {}
        self.segments = {}
        self.articles = {}
    
    def _execute_query(self, query, params=None):
        # Mock implementation that returns empty list for all queries
        if "SELECT" in query.upper() and "bulk_processing_tasks" in query:
            return []
        return []
    
    def add_to_processing_queue(self, page_id, operation, parameters=None, priority=1):
        task_id = f"{page_id}_{operation}"
        self.queue[task_id] = {
            "page_id": page_id,
            "operation": operation,
            "parameters": parameters,
            "priority": priority,
            "status": "pending",
            "created_at": datetime.datetime.now().isoformat(),
            "retries": 0
        }
        return task_id
    
    def update_processing_queue_item(self, item_id, **kwargs):
        if item_id in self.queue:
            self.queue[item_id].update(kwargs)
        return True
    
    def get_processing_queue_item(self, item_id):
        return self.queue.get(item_id)
    
    def get_pending_processing_queue_items(self):
        return [item for item_id, item in self.queue.items() 
                if item.get("status") == "pending"]
    
    def remove_from_processing_queue(self, item_id):
        if item_id in self.queue:
            del self.queue[item_id]
            return True
        return False
    
    def get_newspaper_page(self, page_id):
        # Return mock page data
        return {
            "page_id": page_id,
            "image_path": f"/tmp/mock_image_{page_id}.jpg",
            "ocr_hocr_path": f"/tmp/mock_hocr_{page_id}.html",
            "ocr_text": ""
        }
    
    def update_newspaper_page(self, page_id, **kwargs):
        if page_id not in self.pages:
            self.pages[page_id] = {
                "page_id": page_id,
                "image_path": f"/tmp/mock_image_{page_id}.jpg"
            }
        self.pages[page_id].update(kwargs)
        return True
    
    def get_segments_for_page(self, page_id):
        # Return mock segments
        return [
            {
                "segment_id": f"{page_id}_segment_1",
                "page_id": page_id,
                "segment_type": "headline",
                "content": "Mock Headline",
                "position_data": '{"x": 100, "y": 100, "width": 400, "height": 50}'
            },
            {
                "segment_id": f"{page_id}_segment_2",
                "page_id": page_id,
                "segment_type": "paragraph",
                "content": "Mock paragraph text for testing.",
                "position_data": '{"x": 100, "y": 150, "width": 400, "height": 200}'
            }
        ]
    
    def add_article_segment(self, page_id, segment_type, content, position_data, confidence, image_path):
        segment_id = f"{page_id}_{segment_type}_{len(self.segments)}"
        self.segments[segment_id] = {
            "segment_id": segment_id,
            "page_id": page_id,
            "segment_type": segment_type,
            "content": content,
            "position_data": position_data,
            "confidence": confidence,
            "image_path": image_path
        }
        return segment_id
    
    def add_newspaper_article(self, page_id, title, content, article_type, segment_ids, metadata):
        article_id = f"{page_id}_article_{len(self.articles)}"
        self.articles[article_id] = {
            "article_id": article_id,
            "page_id": page_id,
            "title": title,
            "content": content,
            "article_type": article_type,
            "segment_ids": segment_ids,
            "metadata": metadata
        }
        return article_id

class MockFileManager:
    def __init__(self, base_directory):
        self.base_directory = base_directory

# Make sure we can import the necessary modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from background_service import BackgroundServiceManager
# Lazily import BulkOperationType
BulkOperationType = None
def get_bulk_operation_type():
    global BulkOperationType
    if BulkOperationType is None:
        from bulk_task import BulkOperationType
    return BulkOperationType

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# For running this test directly
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test bulk operations in the background service")
    parser.add_argument("--mode", choices=["console", "gui"], default="console", 
                       help="Run in console mode or show GUI")
    parser.add_argument("--count", type=int, default=20, 
                       help="Number of test tasks to create")
    parser.add_argument("--repo-dir", type=str, default="./test_repository",
                       help="Repository directory")
    args = parser.parse_args()
    
    # Create repository directory if it doesn't exist
    os.makedirs(args.repo_dir, exist_ok=True)
    os.makedirs(os.path.join(args.repo_dir, "original"), exist_ok=True)
    os.makedirs(os.path.join(args.repo_dir, "processed"), exist_ok=True)
    
    # Create test database if it doesn't exist
    db_path = os.path.join(args.repo_dir, "repository.db")
    
    # Define mock processing functions for testing
    class MockOCRProcessor:
        def process_page(self, image_path):
            # Simulate processing time
            time.sleep(0.5)
            
            # Return mock result
            from collections import namedtuple
            OCRResult = namedtuple('OCRResult', ['text', 'hocr_path'])
            return OCRResult(
                text="This is mock OCR text for testing",
                hocr_path="/mock/path/to/hocr.html"
            )
        
        def analyze_layout_from_hocr(self, hocr_path, image_path):
            # Simulate processing time
            time.sleep(1)
            
            # Return mock result
            from collections import namedtuple
            ArticleSegment = namedtuple('ArticleSegment', 
                                      ['segment_type', 'text', 'position', 'confidence', 'image_path'])
            
            # Create a few mock segments
            return [
                ArticleSegment(
                    segment_type="headline",
                    text="Mock Headline",
                    position={"x": 100, "y": 100, "width": 400, "height": 50},
                    confidence=0.9,
                    image_path="/mock/path/to/segment1.png"
                ),
                ArticleSegment(
                    segment_type="paragraph",
                    text="This is a mock paragraph for testing purposes.",
                    position={"x": 100, "y": 150, "width": 400, "height": 200},
                    confidence=0.8,
                    image_path="/mock/path/to/segment2.png"
                )
            ]
    
    # Get background service instance
    service = BackgroundServiceManager.get_instance(
        db_path=db_path,
        base_directory=args.repo_dir,
        max_concurrent_tasks=3,
        batch_size=5
    )
    
    # Replace the OCR processor with our mock for testing
    service.ocr_processor = MockOCRProcessor()
    
    # Set up progress callback for console output
    def progress_callback(update):
        update_type = update["type"]
        data = update["data"]
        
        if update_type == "bulk_task_created":
            logger.info(f"Created bulk task: {data['bulk_id']} - {data['description']}")
        elif update_type == "bulk_task_progress":
            logger.info(f"Bulk task progress: {data['bulk_id']} - {data['progress']:.1%} - "
                        f"{data['completed_tasks']}/{data['total_tasks']} completed "
                        f"({data['failed_tasks']} failed)")
        elif update_type == "task_completed":
            if "bulk_id" in data:
                logger.info(f"Task completed: {data['task_id']} (part of bulk {data['bulk_id']})")
        elif update_type == "task_failed":
            if "bulk_id" in data:
                logger.info(f"Task failed: {data['task_id']} (part of bulk {data['bulk_id']}): {data['error']}")
    
    service.register_progress_callback(progress_callback)
    
    # Start the service
    service.start()
    logger.info("Started background service")
    
    # Enable batch mode for better performance
    service.enable_batch_mode(True)
    logger.info("Enabled batch mode")
    
    # Replace the database manager with our mock for testing
    service.db_manager = MockRepositoryDatabaseManager(db_path)
    service.file_manager = MockFileManager(args.repo_dir)
    
    # Create a bulk task
    BulkOpType = get_bulk_operation_type()
    bulk_id = service.create_bulk_task(
        operation_type=BulkOpType.OCR.value,
        description=f"Test Bulk Operation - {datetime.datetime.now()}",
        parameters={"test": True},
        priority=2
    )
    
    logger.info(f"Created bulk task: {bulk_id}")
    
    # Add test tasks to the bulk task
    tasks = []
    for i in range(args.count):
        page_id = f"test_page_{i}"
        operation = "ocr" if i % 3 != 0 else "segment"
        parameters = {
            "test_param": f"value_{i}",
            "should_fail": i % 7 == 0  # Make some tasks fail for testing
        }
        tasks.append((page_id, operation, parameters))
    
    logger.info(f"Adding {len(tasks)} tasks to bulk operation")
    task_ids = service.add_tasks_to_bulk(bulk_id, tasks)
    logger.info(f"Added {len(task_ids)} tasks to bulk operation")
    
    # If running in console mode, monitor progress
    if args.mode == "console":
        try:
            while True:
                # Get bulk task status
                status = service.get_bulk_task(bulk_id)
                if not status:
                    logger.error(f"Bulk task {bulk_id} not found")
                    break
                
                # Print status
                progress = status["progress"] * 100
                logger.info(f"Bulk task status: {status['status']} - {progress:.1f}% - "
                            f"{status['completed_tasks']}/{status['total_tasks']} completed "
                            f"({status['failed_tasks']} failed)")
                
                # Check if completed
                if status["status"] in ["completed", "failed", "partially_completed"]:
                    logger.info(f"Bulk task {status['status']}: {bulk_id}")
                    
                    # Retry failed tasks if there are any
                    if status["failed_tasks"] > 0:
                        logger.info(f"Retrying {status['failed_tasks']} failed tasks")
                        retried = service.retry_failed_bulk_tasks(bulk_id)
                        logger.info(f"Requeued {retried} tasks for retry")
                    else:
                        break
                
                # Wait before checking again
                time.sleep(2)
            
            # Task completed, wait a moment and then stop the service
            logger.info("Waiting 5 seconds before stopping service...")
            time.sleep(5)
            
            service.stop()
            logger.info("Stopped background service")
            
        except KeyboardInterrupt:
            # Stop the service on Ctrl+C
            logger.info("Interrupted, stopping service...")
            service.stop()
            logger.info("Stopped background service")
    
    # If running in GUI mode, show the control panel
    elif args.mode == "gui":
        from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
        from background_service import create_service_control_widget
        
        app = QApplication(sys.argv)
        
        window = QMainWindow()
        window.setWindowTitle("Bulk Operations Test")
        window.setGeometry(100, 100, 800, 600)
        
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        
        # Add control widget
        control_widget = create_service_control_widget(central_widget, service)
        layout.addWidget(control_widget)
        
        window.setCentralWidget(central_widget)
        window.show()
        
        # Add some additional tasks after a delay
        def add_more_tasks():
            new_tasks = []
            for i in range(5):
                page_id = f"additional_page_{i}"
                operation = "ocr"
                parameters = {"additional": True}
                new_tasks.append((page_id, operation, parameters))
            
            logger.info(f"Adding {len(new_tasks)} additional tasks to bulk operation")
            service.add_tasks_to_bulk(bulk_id, new_tasks)
        
        # Schedule adding tasks after 5 seconds
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(5000, add_more_tasks)
        
        sys.exit(app.exec_())