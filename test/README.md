# Chatybot Test Suite

This directory contains comprehensive unit tests for the Chatybot application using the pytest testing framework.

## Test Files

The test suite consists of the following files:

- `test_buffer_manager.py` - Unit tests for the BufferManager class
- `test_config_manager.py` - Unit tests for the ConfigManager class
- `test_extract_code.py` - Unit tests for the extract_code module
- `test_logging_manager.py` - Unit tests for the LoggingManager class
- `run_all_tests.py` - Convenience script to execute the complete test suite

## Running Tests

### Execute Complete Test Suite
```bash
python3 test/run_all_tests.py
```

### Run Tests for Specific Module
```bash
python3 -m pytest test/test_buffer_manager.py -v
```

### Run Individual Test
```bash
python3 -m pytest test/test_buffer_manager.py::TestBufferManager::test_initialization -v
```

## Test Coverage

The test suite provides comprehensive coverage of the following components:

### BufferManager Module
- Object initialization and state management
- File buffer operations (loading, clearing, displaying)
- File bank operations (loading, clearing, displaying)
- Script variable management and manipulation
- Placeholder replacement functionality
- Memory usage reporting and analysis
- Variable dumping and inspection

### ConfigManager Module
- Configuration file loading and parsing
- Configuration validation and error handling
- Model configuration management
- Active model switching and selection
- Model listing and enumeration

### ExtractCode Module
- Code file detection and classification
- Code block extraction from mixed content
- File processing and transformation

### LoggingManager Module
- Logging lifecycle management (start/stop)
- Message logging and persistence
- Date/time formatting and localization
- Log file naming conventions and organization

## Test Design Principles

The test suite follows these key design principles:

1. **Isolation**: Each test operates with fresh instances and temporary resources
2. **Comprehensive Coverage**: Tests include both normal use cases and edge conditions
3. **Non-destructive**: No modifications are made to production source code
4. **Self-contained**: Tests perform complete cleanup of any temporary artifacts
5. **Performance**: Tests execute rapidly to support frequent development iterations

## System Requirements

- Python 3.7 or higher
- pytest 6.0 or higher
- All runtime dependencies required by the main application

## Adding New Tests

When extending Chatybot functionality, follow these guidelines for adding tests:

1. Create new test files following established naming conventions
2. Implement test classes and methods consistent with existing patterns
3. Include tests for both typical usage and edge cases
4. Ensure tests remain isolated and independent of external state
5. Update test runner scripts as needed for new test files
6. Maintain consistent code style and documentation standards

## Test Results

Current test suite status:
- Total tests: 50
- Passing tests: 50
- Coverage: Core functionality of 4 major modules
- Execution time: Approximately 5 seconds for complete suite

## Maintenance

To maintain test effectiveness:
- Update tests when corresponding functionality changes
- Add new tests for additional features
- Review and refactor tests periodically
- Ensure tests continue to execute in isolated environments
