"""File operations for Tiny Commander."""

import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Callable


def validate_filename(name: str | None) -> str | None:
    """Validate a filename for common issues.

    Args:
        name: The filename to validate.

    Returns:
        None if valid, or an error code string:
        - 'empty': Name is empty or whitespace-only
        - 'special': Name is . or ..
        - 'separator': Name contains path separator (/)
        - 'null': Name contains null byte
    """
    name = name.strip() if name else ''
    if not name:
        return 'empty'
    if name in ('.', '..'):
        return 'special'
    if '/' in name:
        return 'separator'
    if '\0' in name:
        return 'null'
    return None


class OverwriteChoice(Enum):
    """User's choice when a file exists at destination."""

    YES = auto()       # Overwrite this file
    NO = auto()        # Skip this file
    YES_ALL = auto()   # Overwrite this and all remaining conflicts
    NO_ALL = auto()    # Skip this and all remaining conflicts
    YES_OLDER = auto() # Overwrite only if source is newer (for all remaining)
    CANCEL = auto()    # Abort the entire operation


@dataclass(frozen=True)
class OverwriteState:
    """State tracking for batch overwrite decisions.

    Immutable state that tracks user's batch decisions during file operations.
    Create new instances with updated values as decisions are made.
    """

    overwrite_all: bool = False
    skip_all: bool = False
    overwrite_older: bool = False


def get_overwrite_decision(
    state: OverwriteState,
    source_mtime: float,
    dest_mtime: float
) -> str:
    """Determine overwrite action based on current state.

    Args:
        state: Current overwrite state with batch decision flags.
        source_mtime: Modification time of source file.
        dest_mtime: Modification time of destination file.

    Returns:
        'skip' - skip this file
        'proceed' - proceed with overwrite
        'prompt' - need to prompt user for decision
    """
    if state.skip_all:
        return 'skip'

    if state.overwrite_older:
        if source_mtime > dest_mtime:
            return 'proceed'
        return 'skip'

    if state.overwrite_all:
        return 'proceed'

    return 'prompt'


def apply_overwrite_choice(
    choice: OverwriteChoice,
    state: OverwriteState,
    source_mtime: float,
    dest_mtime: float
) -> tuple[str, OverwriteState]:
    """Apply user's overwrite choice and return action with updated state.

    Args:
        choice: User's choice from the prompt.
        state: Current overwrite state.
        source_mtime: Modification time of source file.
        dest_mtime: Modification time of destination file.

    Returns:
        Tuple of (action, new_state) where action is:
        - 'proceed' - proceed with overwrite
        - 'skip' - skip this file
        - 'cancel' - cancel the entire operation
    """
    if choice == OverwriteChoice.CANCEL:
        return 'cancel', state

    if choice == OverwriteChoice.NO:
        return 'skip', state

    if choice == OverwriteChoice.NO_ALL:
        return 'skip', OverwriteState(skip_all=True)

    if choice == OverwriteChoice.YES:
        return 'proceed', state

    if choice == OverwriteChoice.YES_ALL:
        return 'proceed', OverwriteState(overwrite_all=True)

    if choice == OverwriteChoice.YES_OLDER:
        new_state = OverwriteState(overwrite_older=True)
        if source_mtime > dest_mtime:
            return 'proceed', new_state
        return 'skip', new_state

    # Default fallback (shouldn't reach here with valid enum)
    return 'prompt', state


class OverwriteHandler(ABC):
    """Abstract handler for overwrite prompts."""

    @abstractmethod
    def prompt(
        self,
        filename: str,
        source_size: int,
        dest_size: int,
        source_mtime: float,
        dest_mtime: float,
        current: int,
        total: int
    ) -> OverwriteChoice:
        """Prompt user for overwrite decision.

        Args:
            filename: Name of the conflicting file.
            source_size: Size of the source file in bytes.
            dest_size: Size of the destination file in bytes.
            source_mtime: Modification time of source file (Unix timestamp).
            dest_mtime: Modification time of destination file (Unix timestamp).
            current: Current file number in operation (1-based).
            total: Total number of files in operation.

        Returns:
            User's choice for this conflict.
        """
        pass


@dataclass
class CopyResult:
    """Result of a copy operation."""

    success: bool
    error: str = ''
    copied_files: list[str] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)
    cancelled: bool = False


@dataclass
class MoveResult:
    """Result of a move operation."""

    success: bool
    error: str = ''
    moved_files: list[str] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)
    cancelled: bool = False


@dataclass
class MkdirResult:
    """Result of a mkdir operation."""

    success: bool
    error: str = ''
    created_name: str = ''


@dataclass
class CreateFileResult:
    """Result of a create file operation."""

    success: bool
    error: str = ''
    created_name: str = ''


@dataclass
class DeleteResult:
    """Result of a delete operation."""

    success: bool
    error: str = ''
    deleted_files: list[str] = field(default_factory=list)


@dataclass
class RenameResult:
    """Result of a rename operation."""

    success: bool
    error: str = ''
    new_name: str = ''


@dataclass
class ChmodResult:
    """Result of a chmod operation."""

    success: bool
    error: str = ''
    changed_files: list[str] = field(default_factory=list)


@dataclass
class ChownResult:
    """Result of a chown operation."""

    success: bool
    error: str = ''
    changed_files: list[str] = field(default_factory=list)


def chmod_files(
    filenames: list[str],
    parent_dir: str | Path,
    mode: int
) -> ChmodResult:
    """Change permissions on files.

    Args:
        filenames: List of filenames to change (relative to parent_dir).
        parent_dir: Directory containing the files.
        mode: New permission mode (e.g., 0o755).

    Returns:
        ChmodResult with success status and list of changed files.
    """
    if not filenames:
        return ChmodResult(success=True)

    parent = Path(parent_dir)
    changed: list[str] = []
    errors: list[str] = []

    for filename in filenames:
        filepath = parent / filename
        try:
            os.chmod(filepath, mode)
            changed.append(filename)
        except FileNotFoundError:
            errors.append(f'{filename}: No such file or directory')
        except PermissionError:
            errors.append(f'{filename}: Permission denied')
        except OSError as err:
            errors.append(f'{filename}: {err}')

    if errors:
        return ChmodResult(
            success=False,
            error='; '.join(errors),
            changed_files=changed
        )

    return ChmodResult(success=True, changed_files=changed)


def chmod_recursive(
    path: str | Path,
    dir_mode: int,
    file_mode: int | None = None
) -> ChmodResult:
    """Change permissions recursively on a directory and its contents.

    Args:
        path: Path to directory (or file) to change.
        dir_mode: Permission mode for directories.
        file_mode: Permission mode for files. If None, uses dir_mode for all.

    Returns:
        ChmodResult with success status and list of changed files.
    """
    target = Path(path)

    if not target.exists():
        return ChmodResult(
            success=False,
            error=f'{path}: No such file or directory'
        )

    if file_mode is None:
        file_mode = dir_mode

    changed: list[str] = []
    errors: list[str] = []

    def process_path(p: Path) -> None:
        """Process a single path, recursing into directories."""
        try:
            if p.is_dir() and not p.is_symlink():
                os.chmod(p, dir_mode)
                changed.append(str(p))
                # Process contents
                for child in p.iterdir():
                    process_path(child)
            else:
                os.chmod(p, file_mode)
                changed.append(str(p))
        except PermissionError:
            errors.append(f'{p}: Permission denied')
        except OSError as err:
            errors.append(f'{p}: {err}')

    process_path(target)

    if errors:
        return ChmodResult(
            success=False,
            error='; '.join(errors),
            changed_files=changed
        )

    return ChmodResult(success=True, changed_files=changed)


def chown_files(
    filenames: list[str],
    parent_dir: str | Path,
    uid: int,
    gid: int
) -> ChownResult:
    """Change ownership on files.

    Args:
        filenames: List of filenames to change (relative to parent_dir).
        parent_dir: Directory containing the files.
        uid: New owner user ID (-1 to leave unchanged).
        gid: New owner group ID (-1 to leave unchanged).

    Returns:
        ChownResult with success status and list of changed files.
    """
    if not filenames:
        return ChownResult(success=True)

    parent = Path(parent_dir)
    changed: list[str] = []
    errors: list[str] = []

    for filename in filenames:
        filepath = parent / filename
        try:
            os.chown(filepath, uid, gid)
            changed.append(filename)
        except FileNotFoundError:
            errors.append(f'{filename}: No such file or directory')
        except PermissionError:
            errors.append(f'{filename}: Operation not permitted')
        except OSError as err:
            errors.append(f'{filename}: {err}')

    if errors:
        return ChownResult(
            success=False,
            error='; '.join(errors),
            changed_files=changed
        )

    return ChownResult(success=True, changed_files=changed)


def _copy_item(source_path: Path, dest_path: Path) -> None:
    """Copy a single file or directory with proper handling for different types.

    Args:
        source_path: Full path to source item.
        dest_path: Full path to destination item.
    """
    if source_path.is_symlink():
        # Copy symlink as symlink
        link_target = os.readlink(source_path)
        if dest_path.exists() or dest_path.is_symlink():
            dest_path.unlink()
        os.symlink(link_target, dest_path)
    elif source_path.is_dir():
        # Copy directory recursively
        shutil.copytree(
            source_path,
            dest_path,
            symlinks=True,
            copy_function=shutil.copy2
        )
    else:
        # Copy file preserving metadata
        shutil.copy2(source_path, dest_path)


def _process_file_operation(
    filenames: list[str],
    source_dir: str | Path,
    dest_dir: str | Path,
    operation: Callable[[Path, Path], None],
    result_class: type,
    result_attr: str
) -> CopyResult | MoveResult:
    """Process file operation (copy or move) with common validation and error handling.

    Args:
        filenames: List of filenames to operate on (relative to source_dir).
        source_dir: Source directory path.
        dest_dir: Destination directory path.
        operation: Callable that performs the operation on (source_path, dest_path).
        result_class: Result class to return (CopyResult or MoveResult).
        result_attr: Attribute name for result list ('copied_files' or 'moved_files').

    Returns:
        Result object with success status and any error message.
    """
    source_dir = Path(source_dir).resolve()
    dest_dir = Path(dest_dir).resolve()

    if source_dir == dest_dir:
        error_msg = 'Cannot copy to same directory' if result_attr == 'copied_files' else 'Cannot move to same directory'
        return result_class(success=False, error=error_msg)

    if not filenames:
        return result_class(success=True)

    processed: list[str] = []
    errors: list[str] = []

    for filename in filenames:
        source_path = source_dir / filename
        dest_path = dest_dir / filename

        try:
            if not source_path.exists() and not source_path.is_symlink():
                errors.append(f'{filename}: File not found')
                continue

            operation(source_path, dest_path)
            processed.append(filename)

        except PermissionError:
            errors.append(f'{filename}: Permission denied')
        except OSError as err:
            errors.append(f'{filename}: {err}')

    if errors:
        return result_class(
            success=False,
            error='; '.join(errors),
            **{result_attr: processed}
        )

    return result_class(success=True, **{result_attr: processed})


def copy_files(
    filenames: list[str],
    source_dir: str | Path,
    dest_dir: str | Path
) -> CopyResult:
    """Copy files from source to destination directory.

    Args:
        filenames: List of filenames to copy (relative to source_dir).
        source_dir: Source directory path.
        dest_dir: Destination directory path.

    Returns:
        CopyResult with success status and any error message.
    """
    return _process_file_operation(
        filenames,
        source_dir,
        dest_dir,
        _copy_item,
        CopyResult,
        'copied_files'
    )


def move_files(
    filenames: list[str],
    source_dir: str | Path,
    dest_dir: str | Path
) -> MoveResult:
    """Move files from source to destination directory.

    Args:
        filenames: List of filenames to move (relative to source_dir).
        source_dir: Source directory path.
        dest_dir: Destination directory path.

    Returns:
        MoveResult with success status and any error message.
    """
    def move_item(source_path: Path, dest_path: Path) -> None:
        # shutil.move handles cross-filesystem moves (falls back to copy+delete)
        shutil.move(str(source_path), str(dest_path))

    return _process_file_operation(
        filenames,
        source_dir,
        dest_dir,
        move_item,
        MoveResult,
        'moved_files'
    )


def mkdir(parent_dir: str | Path, name: str) -> MkdirResult:
    """Create a new directory.

    Args:
        parent_dir: Parent directory path.
        name: Name of the new directory.

    Returns:
        MkdirResult with success status and any error message.
    """
    # Validate name
    name = name.strip() if name else ''
    if error := validate_filename(name):
        error_messages = {
            'empty': 'Directory name cannot be empty',
            'special': 'Invalid directory name',
            'separator': 'Invalid directory name',
            'null': 'Invalid directory name',
        }
        return MkdirResult(success=False, error=error_messages.get(error, 'Invalid directory name'))

    parent_dir = Path(parent_dir).resolve()
    new_dir = parent_dir / name

    # Check if already exists
    if new_dir.exists():
        return MkdirResult(success=False, error='Directory already exists')

    try:
        new_dir.mkdir()
        return MkdirResult(success=True, created_name=name)
    except PermissionError:
        return MkdirResult(success=False, error='Permission denied')
    except OSError as err:
        return MkdirResult(success=False, error=str(err))


def calculate_dir_size(path: str | Path) -> int:
    """Calculate total size of a directory tree recursively.

    Uses lstat (doesn't follow symlinks) to avoid infinite loops.
    Always includes hidden files in the count.
    Only counts file contents, not directory metadata.

    Args:
        path: Directory path to calculate size for.

    Returns:
        Total size in bytes, or -1 if the path doesn't exist or can't be accessed.
    """
    path = Path(path)

    if not path.exists():
        return -1

    # If it's a file or symlink, return its size
    if path.is_file() or path.is_symlink():
        try:
            return path.lstat().st_size
        except OSError:
            return -1

    total = 0
    try:
        for item in path.rglob('*'):
            try:
                # Use lstat to not follow symlinks
                stat_info = item.lstat()
                # Only count files and symlinks, not directories
                if not item.is_dir():
                    total += stat_info.st_size
            except OSError:
                # Skip files we can't stat (permission denied, etc.)
                continue
    except OSError:
        return -1

    return total


def create_file(parent_dir: str | Path, name: str) -> CreateFileResult:
    """Create a new empty file.

    Args:
        parent_dir: Parent directory path.
        name: Name of the new file.

    Returns:
        CreateFileResult with success status and any error message.
    """
    # Validate name
    name = name.strip() if name else ''
    if error := validate_filename(name):
        error_messages = {
            'empty': 'File name cannot be empty',
            'special': 'Invalid file name',
            'separator': 'File name cannot contain path separator',
            'null': 'Invalid file name',
        }
        return CreateFileResult(success=False, error=error_messages.get(error, 'Invalid file name'))

    parent_dir = Path(parent_dir).resolve()
    new_file = parent_dir / name

    # Check if already exists (including broken symlinks)
    if new_file.exists() or new_file.is_symlink():
        return CreateFileResult(success=False, error='File already exists')

    try:
        new_file.touch()
        return CreateFileResult(success=True, created_name=name)
    except PermissionError:
        return CreateFileResult(success=False, error='Permission denied')
    except OSError as err:
        return CreateFileResult(success=False, error=str(err))


def delete_files(filenames: list[str], parent_dir: str | Path) -> DeleteResult:
    """Delete files and directories.

    Args:
        filenames: List of filenames to delete (relative to parent_dir).
        parent_dir: Parent directory path.

    Returns:
        DeleteResult with success status and any error message.
    """
    parent_dir = Path(parent_dir).resolve()

    if not filenames:
        return DeleteResult(success=True)

    deleted: list[str] = []
    errors: list[str] = []

    for filename in filenames:
        # Never allow deleting '..'
        if filename == '..':
            errors.append('Cannot delete ..')
            continue

        target = parent_dir / filename

        try:
            if not target.exists() and not target.is_symlink():
                errors.append(f'{filename}: File not found')
                continue

            if target.is_symlink() or target.is_file():
                target.unlink()
            else:
                # Directory - remove recursively
                shutil.rmtree(target)

            deleted.append(filename)

        except PermissionError:
            errors.append(f'{filename}: Permission denied')
        except OSError as err:
            errors.append(f'{filename}: {err}')

    if errors:
        return DeleteResult(
            success=False,
            error='; '.join(errors),
            deleted_files=deleted
        )

    return DeleteResult(success=True, deleted_files=deleted)


def _process_files_with_overwrite(
    filenames: list[str],
    source_dir: str | Path,
    dest_dir: str | Path,
    handler: OverwriteHandler,
    operation: Callable[[Path, Path], None],
    result_class: type,
    result_attr: str,
    operation_name: str
) -> CopyResult | MoveResult:
    """Process file operation with overwrite confirmation.

    Args:
        filenames: List of filenames to process.
        source_dir: Source directory path.
        dest_dir: Destination directory path.
        handler: Handler for overwrite prompts.
        operation: Function to perform the operation (copy or move).
        result_class: Result class (CopyResult or MoveResult).
        result_attr: Attribute name for processed files list.
        operation_name: Operation name for error messages ('copy' or 'move').

    Returns:
        Result object with success status.
    """
    source_dir = Path(source_dir).resolve()
    dest_dir = Path(dest_dir).resolve()

    if source_dir == dest_dir:
        return result_class(success=False, error=f'Cannot {operation_name} to same directory')

    if not filenames:
        return result_class(success=True)

    processed: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []
    state = OverwriteState()
    total = len(filenames)

    for idx, filename in enumerate(filenames, 1):
        source_path = source_dir / filename
        dest_path = dest_dir / filename

        try:
            if not source_path.exists() and not source_path.is_symlink():
                errors.append(f'{filename}: File not found')
                continue

            # Check for conflict
            if dest_path.exists() or dest_path.is_symlink():
                source_stat = source_path.stat()
                dest_stat = dest_path.stat()
                source_size = source_stat.st_size if source_path.is_file() else 0
                dest_size = dest_stat.st_size if dest_path.is_file() else 0
                source_mtime = source_stat.st_mtime
                dest_mtime = dest_stat.st_mtime

                # Check state-based decision first
                decision = get_overwrite_decision(state, source_mtime, dest_mtime)

                if decision == 'prompt':
                    # Need to ask user
                    choice = handler.prompt(
                        filename, source_size, dest_size,
                        source_mtime, dest_mtime, idx, total
                    )
                    decision, state = apply_overwrite_choice(
                        choice, state, source_mtime, dest_mtime
                    )

                if decision == 'cancel':
                    return result_class(
                        success=False,
                        error='Operation cancelled',
                        cancelled=True,
                        skipped_files=skipped,
                        **{result_attr: processed}
                    )
                elif decision == 'skip':
                    skipped.append(filename)
                    continue

                # Remove existing file/dir before operation
                if dest_path.is_dir() and not dest_path.is_symlink():
                    shutil.rmtree(dest_path)
                else:
                    dest_path.unlink()

            operation(source_path, dest_path)
            processed.append(filename)

        except PermissionError:
            errors.append(f'{filename}: Permission denied')
        except OSError as err:
            errors.append(f'{filename}: {err}')

    if errors:
        return result_class(
            success=False,
            error='; '.join(errors),
            skipped_files=skipped,
            **{result_attr: processed}
        )

    return result_class(success=True, skipped_files=skipped, **{result_attr: processed})


def copy_files_with_overwrite(
    filenames: list[str],
    source_dir: str | Path,
    dest_dir: str | Path,
    handler: OverwriteHandler
) -> CopyResult:
    """Copy files with overwrite confirmation.

    Args:
        filenames: List of filenames to copy.
        source_dir: Source directory path.
        dest_dir: Destination directory path.
        handler: Handler for overwrite prompts.

    Returns:
        CopyResult with success status.
    """
    return _process_files_with_overwrite(
        filenames, source_dir, dest_dir, handler,
        _copy_item, CopyResult, 'copied_files', 'copy'
    )


def move_files_with_overwrite(
    filenames: list[str],
    source_dir: str | Path,
    dest_dir: str | Path,
    handler: OverwriteHandler
) -> MoveResult:
    """Move files with overwrite confirmation.

    Args:
        filenames: List of filenames to move.
        source_dir: Source directory path.
        dest_dir: Destination directory path.
        handler: Handler for overwrite prompts.

    Returns:
        MoveResult with success status.
    """
    def move_item(source_path: Path, dest_path: Path) -> None:
        shutil.move(str(source_path), str(dest_path))

    return _process_files_with_overwrite(
        filenames, source_dir, dest_dir, handler,
        move_item, MoveResult, 'moved_files', 'move'
    )


def rename_file(parent_dir: str | Path, old_name: str, new_name: str) -> RenameResult:
    """Rename a file or directory.

    Args:
        parent_dir: Parent directory path.
        old_name: Current name of the file/directory.
        new_name: New name for the file/directory.

    Returns:
        RenameResult with success status and any error message.
    """
    # Validate new name
    new_name = new_name.strip() if new_name else ''
    if error := validate_filename(new_name):
        error_messages = {
            'empty': 'New name cannot be empty',
            'special': 'Invalid name',
            'separator': 'Name cannot contain path separator',
            'null': 'Invalid name',
        }
        return RenameResult(success=False, error=error_messages.get(error, 'Invalid name'))

    parent_dir = Path(parent_dir).resolve()
    old_path = parent_dir / old_name
    new_path = parent_dir / new_name

    # Check if source exists
    if not old_path.exists() and not old_path.is_symlink():
        return RenameResult(success=False, error='Source does not exist')

    # Check if destination already exists
    if new_path.exists() or new_path.is_symlink():
        return RenameResult(success=False, error='Destination already exists')

    try:
        old_path.rename(new_path)
        return RenameResult(success=True, new_name=new_name)
    except PermissionError:
        return RenameResult(success=False, error='Permission denied')
    except OSError as err:
        return RenameResult(success=False, error=str(err))
