#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Create Service Control Widget

This module provides a function to create a control widget for the background service.
It's separated from the main background_service.py to avoid circular import issues.
"""

import os
import logging
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                           QLabel, QProgressBar, QFrame)
from PyQt5.QtCore import Qt, QTimer

logger = logging.getLogger(__name__)

def create_service_control_widget(service, parent=None):
    """
    Create a widget for controlling the background service.
    
    Args:
        service: The background service to control
        parent: Parent widget
        
    Returns:
        A widget with controls for the background service
    """
    if service is None:
        return QLabel("Background service not available")
        
    widget = QWidget(parent)
    layout = QVBoxLayout(widget)
    
    # Status display
    status_layout = QHBoxLayout()
    status_label = QLabel("Service Status:")
    status_value = QLabel("Stopped")
    status_value.setStyleSheet("font-weight: bold; color: red;")
    
    status_layout.addWidget(status_label)
    status_layout.addWidget(status_value)
    status_layout.addStretch()
    
    # Task count display
    tasks_layout = QHBoxLayout()
    queue_label = QLabel("Queue:")
    queue_value = QLabel("0")
    in_progress_label = QLabel("In Progress:")
    in_progress_value = QLabel("0")
    
    tasks_layout.addWidget(queue_label)
    tasks_layout.addWidget(queue_value)
    tasks_layout.addWidget(in_progress_label)
    tasks_layout.addWidget(in_progress_value)
    tasks_layout.addStretch()
    
    # Progress bar
    progress_bar = QProgressBar()
    progress_bar.setRange(0, 100)
    progress_bar.setValue(0)
    
    # Control buttons
    buttons_layout = QHBoxLayout()
    
    start_button = QPushButton("Start")
    stop_button = QPushButton("Stop")
    pause_button = QPushButton("Pause")
    resume_button = QPushButton("Resume")
    
    # Initially disable buttons that shouldn't be pressed
    stop_button.setEnabled(False)
    pause_button.setEnabled(False)
    resume_button.setEnabled(False)
    
    buttons_layout.addWidget(start_button)
    buttons_layout.addWidget(stop_button)
    buttons_layout.addWidget(pause_button)
    buttons_layout.addWidget(resume_button)
    
    # Add everything to main layout
    layout.addLayout(status_layout)
    layout.addLayout(tasks_layout)
    layout.addWidget(progress_bar)
    layout.addLayout(buttons_layout)
    
    # Separator
    separator = QFrame()
    separator.setFrameShape(QFrame.HLine)
    separator.setFrameShadow(QFrame.Sunken)
    layout.addWidget(separator)
    
    # Stats display
    stats_label = QLabel("Service Statistics")
    stats_layout = QHBoxLayout()
    
    processed_label = QLabel("Processed:")
    processed_value = QLabel("0")
    succeeded_label = QLabel("Succeeded:")
    succeeded_value = QLabel("0")
    failed_label = QLabel("Failed:")
    failed_value = QLabel("0")
    
    stats_layout.addWidget(processed_label)
    stats_layout.addWidget(processed_value)
    stats_layout.addWidget(succeeded_label)
    stats_layout.addWidget(succeeded_value)
    stats_layout.addWidget(failed_label)
    stats_layout.addWidget(failed_value)
    stats_layout.addStretch()
    
    layout.addWidget(stats_label)
    layout.addLayout(stats_layout)
    
    # Event functions
    def update_ui():
        """Update the UI based on service state"""
        try:
            if not hasattr(service, 'running'):
                return
                
            # Update status
            if service.running:
                if service.paused:
                    status_value.setText("Paused")
                    status_value.setStyleSheet("font-weight: bold; color: orange;")
                else:
                    status_value.setText("Running")
                    status_value.setStyleSheet("font-weight: bold; color: green;")
            else:
                status_value.setText("Stopped")
                status_value.setStyleSheet("font-weight: bold; color: red;")
                
            # Update buttons
            start_button.setEnabled(not service.running)
            stop_button.setEnabled(service.running)
            pause_button.setEnabled(service.running and not service.paused)
            resume_button.setEnabled(service.running and service.paused)
            
            # Update task counts
            if hasattr(service, 'task_queue') and hasattr(service.task_queue, 'qsize'):
                queue_value.setText(str(service.task_queue.qsize()))
            else:
                queue_value.setText("N/A")
                
            if hasattr(service, 'in_progress_tasks'):
                in_progress_value.setText(str(len(service.in_progress_tasks)))
            else:
                in_progress_value.setText("N/A")
                
            # Update stats
            if hasattr(service, 'stats'):
                processed_value.setText(str(service.stats.get('tasks_processed', 0)))
                succeeded_value.setText(str(service.stats.get('tasks_succeeded', 0)))
                failed_value.setText(str(service.stats.get('tasks_failed', 0)))
                
                # Calculate progress if we have processed tasks
                total_tasks = (service.stats.get('tasks_processed', 0) + 
                              (service.task_queue.qsize() if hasattr(service, 'task_queue') and hasattr(service.task_queue, 'qsize') else 0) + 
                              len(service.in_progress_tasks) if hasattr(service, 'in_progress_tasks') else 0)
                
                if total_tasks > 0:
                    progress = int(service.stats.get('tasks_processed', 0) / total_tasks * 100)
                    progress_bar.setValue(min(progress, 100))
                else:
                    progress_bar.setValue(0)
        except Exception as e:
            logger.error(f"Error updating service control UI: {e}")
    
    # Set up button actions
    def on_start():
        if hasattr(service, 'start'):
            service.start()
            update_ui()
    
    def on_stop():
        if hasattr(service, 'stop'):
            service.stop()
            update_ui()
    
    def on_pause():
        if hasattr(service, 'pause'):
            service.pause()
            update_ui()
    
    def on_resume():
        if hasattr(service, 'resume'):
            service.resume()
            update_ui()
    
    # Connect button signals
    start_button.clicked.connect(on_start)
    stop_button.clicked.connect(on_stop)
    pause_button.clicked.connect(on_pause)
    resume_button.clicked.connect(on_resume)
    
    # Set up timer for periodic updates
    update_timer = QTimer(widget)
    update_timer.timeout.connect(update_ui)
    update_timer.start(1000)  # Update every second
    
    # Initial update
    update_ui()
    
    return widget


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    
    # Create a mock service for testing
    class MockService:
        def __init__(self):
            self.running = False
            self.paused = False
            self.task_queue = type('obj', (), {'qsize': lambda: 5})()
            self.in_progress_tasks = {}
            self.stats = {
                'tasks_processed': 10,
                'tasks_succeeded': 8,
                'tasks_failed': 2
            }
        
        def start(self):
            self.running = True
            
        def stop(self):
            self.running = False
            
        def pause(self):
            self.paused = True
            
        def resume(self):
            self.paused = False
    
    app = QApplication(sys.argv)
    
    service = MockService()
    widget = create_service_control_widget(service)
    widget.show()
    
    sys.exit(app.exec_())