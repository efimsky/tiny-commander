# Contributing to Tiny Commander

Thank you for your interest in contributing to Tiny Commander!

## Core Principles

1.  **Zero Dependencies**: We use only the Python 3.13+ standard library. No `pip install` required.
2.  **Simplicity**: We prioritize a clean, maintainable codebase over feature bloat.
3.  **Cross-Platform**: We support Linux and macOS.

## Development Setup

1.  Clone the repository:
    ```bash
    git clone https://github.com/efimsky/tiny-commander.git
    cd tiny-commander
    ```
2.  Run the tests to ensure everything is working:
    ```bash
    python3 -m unittest discover -s tests -v
    ```

## Test-Driven Development

This project follows strict TDD (Test-Driven Development):

1.  **Red**: Write a failing test for the feature or bug fix.
2.  **Green**: Write the minimum code necessary to pass the test.
3.  **Refactor**: Clean up the code while ensuring tests remain green.

Please ensure all tests pass before submitting a Pull Request.

## Code Style

-   Follow PEP 8 guidelines.
-   Use type hints.
-   Keep functions small and focused.
-   Add docstrings for classes and complex functions.

## Submitting Changes

1.  Fork the repository.
2.  Create a new branch for your feature or fix.
3.  Commit your changes with clear messages.
4.  Push to your fork and submit a Pull Request.
