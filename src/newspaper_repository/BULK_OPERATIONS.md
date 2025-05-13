# Bulk Operations Support for Newspaper Repository

This document provides an overview of the enhanced background service with bulk operations support, which allows for more efficient processing of large batches of newspaper pages.

## Features

- **Bulk Task Management**: Create and manage groups of related tasks as a single bulk operation
- **Batch Processing**: Process multiple tasks in batches for improved performance
- **Progress Tracking**: Track progress across multiple related tasks
- **Pause/Resume**: Pause and resume specific bulk operations
- **Detailed Status Reporting**: Get detailed status information for bulk operations
- **Automatic Retry**: Retry failed tasks automatically
- **Priority Management**: Prioritize tasks within or across bulk operations

## Usage Examples

### Creating a Bulk Task

```python
from newspaper_repository.background_service import BackgroundServiceManager
from newspaper_repository.bulk_task import BulkOperationType

# Get background service instance
service = BackgroundServiceManager.get_instance(
    db_path="/path/to/repository.db",
    base_directory="/path/to/repository",
    max_concurrent_tasks=3,
    batch_size=5
)

# Create a bulk task
bulk_id = service.create_bulk_task(
    operation_type=BulkOperationType.OCR.value,
    description="Process October 1890 Newspapers",
    parameters={"source": "newspapers_oct_1890"},
    priority=1
)
```

### Adding Tasks to a Bulk Operation

```python
# Add individual tasks
task_id = service.add_task_to_bulk(
    bulk_id=bulk_id,
    page_id="page_123",
    operation="ocr",
    parameters={"quality": "high"}
)

# Add multiple tasks at once
tasks = [
    ("page_124", "ocr", {"quality": "high"}),
    ("page_125", "ocr", {"quality": "high"}),
    ("page_126", "ocr", {"quality": "high"})
]
task_ids = service.add_tasks_to_bulk(bulk_id, tasks)
```

### Getting Bulk Task Status

```python
# Get status of a specific bulk task
status = service.get_bulk_task(bulk_id)
print(f"Progress: {status['progress']:.1%} - {status['completed_tasks']}/{status['total_tasks']} completed")

# Get all bulk tasks
all_tasks = service.get_all_bulk_tasks()
for task in all_tasks:
    print(f"{task['bulk_id']} - {task['description']} - {task['status']}")
```

### Controlling Bulk Operations

```python
# Pause a bulk task
service.pause_bulk_task(bulk_id)

# Resume a paused bulk task
service.resume_bulk_task(bulk_id)

# Cancel a bulk task
service.cancel_bulk_task(bulk_id)

# Retry failed tasks in a bulk operation
retried_count = service.retry_failed_bulk_tasks(bulk_id)
print(f"Requeued {retried_count} tasks for retry")
```

### Enabling Batch Processing

```python
# Enable batch processing for improved performance
service.enable_batch_mode(True)

# Disable batch processing
service.enable_batch_mode(False)
```

## UI Integration

The background service includes a UI widget for controlling bulk operations:

```python
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from newspaper_repository.background_service import BackgroundServiceManager, create_service_control_widget

# Get background service instance
service = BackgroundServiceManager.get_instance(
    db_path="/path/to/repository.db",
    base_directory="/path/to/repository"
)

# Create main window
app = QApplication([])
window = QMainWindow()
central_widget = QWidget()
layout = QVBoxLayout(central_widget)

# Add service control widget
control_widget = create_service_control_widget(central_widget, service)
layout.addWidget(control_widget)

window.setCentralWidget(central_widget)
window.show()
app.exec_()
```

## Architecture

The bulk operations support is implemented using the following components:

1. **BulkProcessingTask**: Represents a collection of related tasks
2. **BulkTaskManager**: Manages bulk tasks and their relationships to individual tasks
3. **BackgroundProcessingService**: Enhanced with bulk operation support

The bulk task status is persisted in the repository database in a new `bulk_processing_tasks` table, allowing operations to survive service restarts.

## Performance Considerations

- Batch processing can significantly improve performance when processing many similar tasks
- The batch size can be configured based on system capabilities
- Task priorities allow for fine-grained control over processing order
- Pause/resume functionality allows for resource management