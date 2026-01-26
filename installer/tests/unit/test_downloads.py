"""Tests for downloads module."""

from __future__ import annotations

import tempfile
from pathlib import Path


class TestDownloadConfig:
    """Test DownloadConfig class."""

    def test_download_config_stores_values(self):
        """DownloadConfig stores repository settings."""
        from installer.downloads import DownloadConfig

        config = DownloadConfig(
            repo_url="https://github.com/test/repo",
            repo_branch="main",
        )
        assert config.repo_url == "https://github.com/test/repo"
        assert config.repo_branch == "main"
        assert config.local_mode is False
        assert config.local_repo_dir is None

    def test_download_config_local_mode(self):
        """DownloadConfig supports local mode."""
        from installer.downloads import DownloadConfig

        config = DownloadConfig(
            repo_url="https://github.com/test/repo",
            repo_branch="main",
            local_mode=True,
            local_repo_dir=Path("/tmp/repo"),
        )
        assert config.local_mode is True
        assert config.local_repo_dir == Path("/tmp/repo")


class TestDownloadFile:
    """Test download_file function."""

    def test_download_file_creates_parent_dirs(self):
        """download_file creates parent directories."""
        from installer.downloads import DownloadConfig, download_file

        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "subdir" / "file.txt"
            config = DownloadConfig(
                repo_url="https://github.com/test/repo",
                repo_branch="main",
                local_mode=True,
                local_repo_dir=Path(tmpdir),
            )

            # Create source file
            source = Path(tmpdir) / "test.txt"
            source.write_text("test content")

            download_file("test.txt", dest, config)
            assert dest.parent.exists()

    def test_download_file_local_mode_copies(self):
        """download_file copies file in local mode."""
        from installer.downloads import DownloadConfig, download_file

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = Path(tmpdir) / "source"
            source_dir.mkdir()
            source = source_dir / "test.txt"
            source.write_text("local content")

            dest = Path(tmpdir) / "dest" / "test.txt"
            config = DownloadConfig(
                repo_url="https://github.com/test/repo",
                repo_branch="main",
                local_mode=True,
                local_repo_dir=source_dir,
            )

            result = download_file("test.txt", dest, config)
            assert result is True
            assert dest.exists()
            assert dest.read_text() == "local content"

    def test_download_file_returns_false_on_missing_source(self):
        """download_file returns False if source doesn't exist."""
        from installer.downloads import DownloadConfig, download_file

        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "dest" / "test.txt"
            config = DownloadConfig(
                repo_url="https://github.com/test/repo",
                repo_branch="main",
                local_mode=True,
                local_repo_dir=Path(tmpdir),
            )

            result = download_file("nonexistent.txt", dest, config)
            assert result is False


class TestGetRepoFiles:
    """Test get_repo_files function."""

    def test_get_repo_files_local_mode(self):
        """get_repo_files returns FileInfo objects in local mode."""
        from installer.downloads import DownloadConfig, get_repo_files

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create directory structure
            subdir = Path(tmpdir) / "mydir"
            subdir.mkdir()
            (subdir / "file1.txt").write_text("content1")
            (subdir / "file2.txt").write_text("content2")

            config = DownloadConfig(
                repo_url="https://github.com/test/repo",
                repo_branch="main",
                local_mode=True,
                local_repo_dir=Path(tmpdir),
            )

            file_infos = get_repo_files("mydir", config)
            assert len(file_infos) == 2
            paths = [f.path for f in file_infos]
            assert "mydir/file1.txt" in paths
            assert "mydir/file2.txt" in paths
            # Local mode has no SHA
            assert all(f.sha is None for f in file_infos)

    def test_get_repo_files_returns_empty_for_missing_dir(self):
        """get_repo_files returns empty list for missing directory."""
        from installer.downloads import DownloadConfig, get_repo_files

        with tempfile.TemporaryDirectory() as tmpdir:
            config = DownloadConfig(
                repo_url="https://github.com/test/repo",
                repo_branch="main",
                local_mode=True,
                local_repo_dir=Path(tmpdir),
            )

            files = get_repo_files("nonexistent", config)
            assert files == []


class TestDownloadDirectory:
    """Test download_directory function."""

    def test_download_directory_local_mode(self):
        """download_directory copies directory in local mode."""
        from installer.downloads import DownloadConfig, download_directory

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source directory
            source_dir = Path(tmpdir) / "source"
            subdir = source_dir / "mydir"
            subdir.mkdir(parents=True)
            (subdir / "file1.txt").write_text("content1")
            (subdir / "file2.txt").write_text("content2")

            dest_dir = Path(tmpdir) / "dest"
            config = DownloadConfig(
                repo_url="https://github.com/test/repo",
                repo_branch="main",
                local_mode=True,
                local_repo_dir=source_dir,
            )

            count = download_directory("mydir", dest_dir, config)
            assert count == 2
            assert (dest_dir / "file1.txt").exists()
            assert (dest_dir / "file2.txt").exists()

    def test_download_directory_excludes_patterns(self):
        """download_directory respects exclude patterns."""
        from installer.downloads import DownloadConfig, download_directory

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source directory
            source_dir = Path(tmpdir) / "source"
            subdir = source_dir / "mydir"
            subdir.mkdir(parents=True)
            (subdir / "file.txt").write_text("content")
            (subdir / "file.pyc").write_text("compiled")

            dest_dir = Path(tmpdir) / "dest"
            config = DownloadConfig(
                repo_url="https://github.com/test/repo",
                repo_branch="main",
                local_mode=True,
                local_repo_dir=source_dir,
            )

            count = download_directory("mydir", dest_dir, config, exclude_patterns=["*.pyc"])
            assert count == 1
            assert (dest_dir / "file.txt").exists()
            assert not (dest_dir / "file.pyc").exists()
