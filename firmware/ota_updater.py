"""
Minimal GitHub OTA Updater for Pico W - Ultra-lightweight for memory-constrained updates
"""

import urequests
import ujson
import os
import gc
import time
import machine
from logger import log_info, log_warn, log_error, log_debug


class GitHubOTAUpdater:
    def __init__(self):
        log_info("Initializing minimal OTA updater", "OTA")

        # Initialize version tag storage
        self._current_version_tag = None

        # Load configuration from device config instead of hardcoding
        try:
            from device_config import get_ota_config
            ota_config = get_ota_config()
            github_repo = ota_config.get("github_repo", {})

            self.repo_owner = github_repo.get("owner", "ThorstenMuellerEE")
            self.repo_name = github_repo.get("name", "th-pico2w_elmo")
            self.branch = github_repo.get("branch", "main")

            log_info(f"OTA config loaded: {self.repo_owner}/{self.repo_name} (branch: {self.branch})", "OTA")
        except Exception as e:
            # Fallback to hardcoded values if config fails
            log_warn(f"Failed to load OTA config, using defaults: {e}", "OTA")
            self.repo_owner = "ThorstenMuellerEE"
            self.repo_name = "th-pico2w_elmo"
            self.branch = "main"

        # GitHub URLs
        self.api_base = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}"
        self.raw_base = f"https://raw.githubusercontent.com/{self.repo_owner}/{self.repo_name}"

        # Local directories
        self.temp_dir = "temp"
        self.update_files = []

        # Ensure temp directory exists
        try:
            os.mkdir(self.temp_dir)
        except OSError:
            pass

        log_info(f"Minimal OTA ready: {self.repo_owner}/{self.repo_name} (branch: {self.branch})", "OTA")

    def reload_config(self):
        """Reload configuration directly from device config file to pick up changes without restart."""
        try:
            log_info("Reloading OTA configuration", "OTA")

            # Import and reload the config directly from file
            from device_config import load_device_config
            config = load_device_config()
            ota_config = config.get("ota", {})
            github_repo = ota_config.get("github_repo", {})

            old_branch = self.branch
            self.repo_owner = github_repo.get("owner", "ThorstenMuellerEE")
            self.repo_name = github_repo.get("name", "th-pico2w_elmo")
            self.branch = github_repo.get("branch", "main")

            # Update URLs with new config
            self.api_base = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}"
            self.raw_base = f"https://raw.githubusercontent.com/{self.repo_owner}/{self.repo_name}"

            if old_branch != self.branch:
                log_info(f"Branch changed: {old_branch} -> {self.branch}", "OTA")

            log_info(f"OTA config reloaded: {self.repo_owner}/{self.repo_name} (branch: {self.branch})", "OTA")
            return True
        except Exception as e:
            log_error(f"Failed to reload OTA config: {e}", "OTA")
            return False

    def get_current_version(self):
        try:
            with open("version.txt", "r") as f:
                return f.read().strip()
        except OSError:
            return "unknown"

    def set_current_version(self, version):
        with open("version.txt", "w") as f:
            f.write(version)

    def create_update_flag(self):
        """Create a flag file indicating update is in progress (survives reboot)."""
        try:
            with open("update_in_progress.flag", "w") as f:
                f.write("1")
            log_info("Update flag created", "OTA")
            return True
        except Exception as e:
            log_error(f"Failed to create update flag: {e}", "OTA")
            return False

    def clear_update_flag(self):
        """Clear the update flag after successful boot."""
        try:
            import os
            os.remove("update_in_progress.flag")
            log_info("Update flag cleared", "OTA")
            return True
        except OSError:
            # File didn't exist, that's fine
            return True
        except Exception as e:
            log_warn(f"Failed to clear update flag: {e}", "OTA")
            return False

    def _get_headers(self):
        return {
            'User-Agent': 'Pico-W-OTA/1.0',
            'Accept': 'application/vnd.github.v3+json',
            'Accept-Encoding': 'identity'
        }

    def _make_request(self, url, headers=None, timeout=30, retries=3):
        if headers is None:
            headers = self._get_headers()

        for attempt in range(retries):
            try:
                print(f"OTA: HTTP Request attempt {attempt + 1}/{retries}: {url}")
                log_debug(f"Request {attempt + 1}/{retries}: {url}", "OTA")

                gc.collect()
                response = urequests.get(url, headers=headers)

                if response.status_code == 200:
                    print(f"OTA: HTTP 200 OK - response received")
                    return True, response
                else:
                    print(f"OTA: HTTP {response.status_code} ERROR")
                    log_error(f"HTTP {response.status_code}", "OTA")
                    response.close()

                    if 400 <= response.status_code < 500:
                        return False, f"HTTP {response.status_code}"

                    if attempt < retries - 1:
                        print(f"OTA: Retrying in 2s...")
                        time.sleep(2)
                        continue
                    else:
                        return False, f"HTTP {response.status_code}"

            except Exception as e:
                print(f"OTA: Request exception - {e}")
                log_error(f"Request failed: {e}", "OTA")
                if attempt < retries - 1:
                    print(f"OTA: Retrying in 2s...")
                    time.sleep(2)
                    continue
                else:
                    return False, str(e)

        print(f"OTA: All retries failed for {url}")
        return False, "All retries failed"

    def check_for_updates(self):
        try:
            log_info("Checking for updates", "OTA")
            current_version = self.get_current_version()

            # Determine release channel based on branch
            if self.branch == "dev":
                # For dev branch, get only the latest release and check if it's a pre-release
                url = f"{self.api_base}/releases?per_page=1"
                log_info("Checking for dev releases (pre-releases)", "OTA")
            else:
                # For main branch, use latest stable release
                url = f"{self.api_base}/releases/latest"
                log_info("Checking for stable releases", "OTA")

            success, response_or_error = self._make_request(url)

            if not success:
                log_error(f"Update check failed: {response_or_error}", "OTA")
                # Check if it's a 404 error (repository not found)
                if "HTTP 404" in str(response_or_error):
                    return False, None, "REPO_NOT_FOUND"
                return False, None, None

            try:
                if self.branch == "dev":
                    # Parse releases list (only 1 release due to per_page=1)
                    releases_data = response_or_error.json()
                    response_or_error.close()

                    # Check if we got any releases
                    if not releases_data or len(releases_data) == 0:
                        log_info("No releases found", "OTA")
                        return False, None, None

                    # Get the first (and only) release
                    latest_release = releases_data[0]

                    # Check if it's a pre-release (dev release)
                    if not latest_release.get("prerelease", False):
                        log_info("Latest release is not a dev release", "OTA")
                        return False, None, None

                    release_data = latest_release
                    latest_version = release_data["tag_name"]
                    # Store the tag_name for use in download URL
                    self._current_version_tag = latest_version
                    log_info(f"Found latest dev release: {latest_version}", "OTA")
                else:
                    # Parse single latest release
                    release_data = response_or_error.json()
                    response_or_error.close()
                    latest_version = release_data["tag_name"]
                    # Store the tag_name for use in download URL
                    self._current_version_tag = latest_version
                    log_info(f"Found latest stable release: {latest_version}", "OTA")

            except Exception as e:
                log_error(f"JSON parse failed: {e}", "OTA")
                response_or_error.close()
                return False, None, None

            has_update = latest_version != current_version

            if has_update:
                log_info(f"Update available: {current_version} -> {latest_version}", "OTA")
            else:
                log_info("No update needed", "OTA")

            return has_update, latest_version, release_data

        except Exception as e:
            log_error(f"Update check failed: {e}", "OTA")
            return False, None, None

    def _download_file_ultra_minimal(self, url, filename, target_dir=""):
        try:
            # Ultra-aggressive memory management
            gc.collect()
            initial_mem = gc.mem_free()
            
            # Record start time and print message
            start_time = time.time()
            print(f"OTA: Download started - {filename} at {time.localtime(start_time)[:5]}")
            print(f"OTA: URL: {url}")
            print(f"OTA: Target dir: {target_dir}")
            log_debug(f"Ultra-minimal download {filename}, mem: {initial_mem}", "OTA")

            success, response_or_error = self._make_request(url)
            if not success:
                print(f"OTA: Download FAILED - {filename}: {response_or_error}")
                log_error(f"Download failed: {response_or_error}", "OTA")
                return False

            print(f"OTA: Response received, parsing content...")
            try:
                target_path = f"{target_dir}/{filename}" if target_dir else filename
                temp_path = f"{target_path}.tmp"
                
                print(f"OTA: Target path: {target_path}")
                print(f"OTA: Temp path: {temp_path}")

                # ULTRA-SMALL chunks - 256 bytes to prevent allocation failures
                chunk_size = 256
                total_bytes = 0

                content = response_or_error.text
                content_size = len(content)
                
                print(f"OTA: Content size: {content_size} bytes")

                # Quick validation
                if content_size == 0:
                    print(f"OTA: Download FAILED - {filename} is empty")
                    log_error(f"{filename} is empty", "OTA")
                    response_or_error.close()
                    return False

                if content.strip().startswith('<!DOCTYPE html>'):
                    print(f"OTA: Download FAILED - {filename} is error page")
                    log_error(f"{filename} is error page", "OTA")
                    response_or_error.close()
                    return False

                response_or_error.close()
                gc.collect()

                print(f"OTA: Writing to file in chunks...")
                # Write in ultra-small chunks with aggressive GC
                with open(temp_path, "w") as f:
                    for i in range(0, content_size, chunk_size):
                        gc.collect()  # GC before each chunk

                        chunk = content[i:i + chunk_size]
                        f.write(chunk)
                        total_bytes += len(chunk)

                        del chunk  # Clear immediately

                        # GC every 512 bytes
                        if i % (chunk_size * 2) == 0:
                            gc.collect()
                
                print(f"OTA: Wrote {total_bytes} bytes, flushing...")

                # Clear content and GC
                del content
                gc.collect()

                print(f"OTA: Renaming temp file to final location...")
                # Atomic rename
                try:
                    os.rename(temp_path, target_path)
                except OSError as e:
                    print(f"OTA: Rename failed - {e}, trying removal first...")
                    try:
                        os.remove(target_path)
                    except OSError:
                        pass
                    os.rename(temp_path, target_path)

                # Verify file exists
                try:
                    stat_info = os.stat(target_path)
                    print(f"OTA: File verified - size: {stat_info[6]} bytes")
                except OSError as e:
                    print(f"OTA: Download FAILED - {target_path} not created: {e}")
                    log_error(f"{target_path} not created", "OTA")
                    return False

                gc.collect()
                final_mem = gc.mem_free()
                
                # Calculate elapsed time and print completion message
                elapsed_time = time.time() - start_time
                end_time = time.localtime()
                print(f"OTA: Download finished - {filename} ({total_bytes} bytes) in {elapsed_time:.1f}s at {end_time[:5]}")
                log_info(f"Downloaded {filename} ({total_bytes} bytes, mem: {final_mem})", "OTA")
                return True

            except Exception as e:
                print(f"OTA: Download FAILED - Write error in {filename}: {e}")
                log_error(f"Write failed {filename}: {e}", "OTA")

                # Cleanup
                temp_path = f"{target_dir}/{filename}.tmp" if target_dir else f"{filename}.tmp"
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
                return False

        except Exception as e:
            print(f"OTA: Download FAILED - {filename}: {e}")
            log_error(f"Ultra-minimal download failed {filename}: {e}", "OTA")
            return False

    def download_file(self, filename, target_dir=""):
        # Construct URL for firmware files - all discovered files are from /firmware/
        # Use the version tag (e.g., v1.1.1) instead of branch name for release downloads
        firmware_files = ["main.py", "config.py", "ota_updater.py", "device_config.py", "logger.py", "version.txt", 
                         "web_interface.py", "dashboard.py", "internal_temp.py", "ota_init.py", "ota_task.py", 
                         "prom_discovery.py", "recovery.py", "system_info.py"]
        
        if filename in firmware_files:
            # Use version tag for download URL - this is critical for releases!
            # The tag (e.g., v1.1.1) points to the exact commit, not the branch
            download_ref = self._current_version_tag if self._current_version_tag else self.branch
            url = f"{self.raw_base}/{download_ref}/firmware/{filename}"
        else:
            download_ref = self._current_version_tag if self._current_version_tag else self.branch
            url = f"{self.raw_base}/{download_ref}/{filename}"

        print(f"OTA: Preparing to download: {filename}")
        print(f"OTA: Base: {self.raw_base}, Branch: {self.branch}, Version tag: {self._current_version_tag}")
        print(f"OTA: Using download ref: {download_ref}")
        print(f"OTA: Full URL: {url}")
        log_info(f"Downloading {filename}", "OTA")

        # Always use ultra-minimal streaming
        return self._download_file_ultra_minimal(url, filename, target_dir)

    def _discover_firmware_files(self):
        try:
            contents_url = f"{self.api_base}/contents/firmware"
            print(f"OTA: Querying GitHub API: {contents_url}")
            success, response_or_error = self._make_request(contents_url)

            if not success:
                # Fallback to essential files
                print(f"OTA: GitHub API failed, using fallback file list")
                return ["main.py", "config.py", "ota_updater.py", "device_config.py", "logger.py", "web_interface.py", "version.txt"]

            try:
                contents_data = response_or_error.json()
                response_or_error.close()
            except Exception as e:
                print(f"OTA: JSON parse failed - {e}, using fallback file list")
                response_or_error.close()
                return ["main.py", "config.py", "ota_updater.py", "device_config.py", "logger.py", "web_interface.py", "version.txt"]

            # Extract firmware files (exclude secrets.py)
            firmware_files = []
            for item in contents_data:
                if item["type"] == "file":
                    filename = item["name"]
                    if (filename.endswith(".py") or filename == "version.txt") and filename != "secrets.py":
                        firmware_files.append(filename)

            print(f"OTA: Discovered {len(firmware_files)} files from GitHub: {firmware_files}")
            log_info(f"Discovered {len(firmware_files)} files", "OTA")
            return firmware_files

        except Exception as e:
            print(f"OTA: File discovery exception - {e}, using fallback file list")
            log_error(f"File discovery failed: {e}", "OTA")
            return ["main.py", "config.py", "ota_updater.py", "device_config.py", "logger.py", "web_interface.py", "version.txt"]

    def download_update(self, version, release_info=None):
        """Download all firmware files from GitHub. Returns True on success, False on failure."""
        try:
            print(f"OTA: Starting download of all files for version {version}...")
            print(f"OTA: Using temp directory: {self.temp_dir}")
            log_info(f"Starting staged download for {version}", "OTA")

            # Clean temp directory
            try:
                print(f"OTA: Cleaning temp directory...")
                for filename in os.listdir(self.temp_dir):
                    filepath = f"{self.temp_dir}/{filename}"
                    print(f"OTA: Removing old file: {filepath}")
                    os.remove(filepath)
            except OSError as e:
                print(f"OTA: Could not clean temp dir (may not exist): {e}")
                pass

            # Get files to download
            print(f"OTA: Discovering firmware files to download...")
            files_to_download = self._discover_firmware_files()
            self.update_files = files_to_download

            print(f"OTA: Will download {len(files_to_download)} files total: {files_to_download}")
            log_info(f"Staged download: {len(files_to_download)} files", "OTA")

            if not files_to_download:
                log_error("No files to download!", "OTA")
                print("OTA: ERROR - No files to download!")
                return False

            # Staged download: one file at a time with aggressive cleanup
            failed_downloads = []
            for i, filename in enumerate(files_to_download, 1):
                print(f"OTA: File {i}/{len(files_to_download)}: {filename}")
                log_info(f"Stage {i}/{len(files_to_download)}: {filename}", "OTA")

                # Aggressive memory cleanup before each download
                gc.collect()
                initial_mem = gc.mem_free()

                if not self.download_file(filename, self.temp_dir):
                    if filename == "version.txt":
                        print(f"OTA: Skipping optional file {filename}")
                        log_warn(f"Skipping optional file {filename}", "OTA")
                        continue
                    else:
                        print(f"OTA: FAILED - Could not download {filename}")
                        log_error(f"Failed to download {filename}", "OTA")
                        failed_downloads.append(filename)
                        # Continue trying other files
                        continue

                # Immediate cleanup after each file
                gc.collect()
                final_mem = gc.mem_free()
                log_info(f"Stage {i} complete: {filename} (mem: {initial_mem}->{final_mem})", "OTA")

                # Brief pause for memory stabilization
                time.sleep(0.3)

            # Check if critical files failed to download
            critical_files = ["main.py", "config.py", "ota_updater.py"]
            critical_failed = [f for f in failed_downloads if f in critical_files]
            
            if critical_failed:
                log_error(f"Critical files failed to download: {critical_failed}", "OTA")
                print(f"OTA: CRITICAL ERROR - Failed to download: {critical_failed}")
                return False
            
            if failed_downloads:
                log_warn(f"Some optional files failed to download: {failed_downloads}", "OTA")
                print(f"OTA: Warning - some optional files failed: {failed_downloads}")
                # Continue anyway - non-critical files failed

            print(f"OTA: All files downloaded successfully - {len(files_to_download)} files")
            log_info(f"Staged download complete: {len(files_to_download)} files", "OTA")
            return True

        except Exception as e:
            print(f"OTA: Download FAILED - {e}")
            log_error(f"Staged download failed: {e}", "OTA")
            return False

    def create_backup(self, files_to_backup):
        """Create backup of critical files before update."""
        try:
            log_info("Creating backup of current files", "OTA")
            backup_count = 0

            for filename in files_to_backup:
                try:
                    # Check if original file exists
                    os.stat(filename)

                    # Create backup
                    backup_name = f"{filename}.bak"

                    # Read original file
                    with open(filename, "r") as src:
                        content = src.read()

                    # Write backup
                    with open(backup_name, "w") as dst:
                        dst.write(content)

                    backup_count += 1
                    log_info(f"Backed up {filename}", "OTA")

                except OSError:
                    log_warn(f"Could not backup {filename} (file not found)", "OTA")

            log_info(f"Created {backup_count} backup files", "OTA")
            return backup_count > 0

        except Exception as e:
            log_error(f"Backup creation failed: {e}", "OTA")
            return False

    def validate_update_files(self):
        """Validate that downloaded files can be imported."""
        try:
            log_info("Validating downloaded files", "OTA")

            # Test critical files for basic syntax
            critical_files = ["main.py", "web_interface.py", "config.py"]

            for filename in critical_files:
                temp_path = f"{self.temp_dir}/{filename}"
                try:
                    os.stat(temp_path)

                    # Basic validation - check file is not empty
                    with open(temp_path, "r") as f:
                        content = f.read()

                    if len(content) < 100:  # Too small
                        log_error(f"{filename} too small ({len(content)} bytes)", "OTA")
                        return False

                    # Check for HTML error pages - only if file starts with HTML
                    # This distinguishes actual error pages from files containing HTML in strings
                    stripped = content.strip()
                    if stripped.startswith('<!DOCTYPE html>') or stripped.startswith('<!DOCTYPE'):
                        log_error(f"{filename} is HTML error page", "OTA")
                        return False

                    # For Python files, check for Python indicators (not HTML in strings)
                    if filename.endswith('.py'):
                        # Check if it's a legitimate Python file by looking for Python indicators
                        # at the start of the file (not in strings)
                        has_python_indicator = (
                            stripped.startswith('"""') or  # Docstring
                            stripped.startswith("'''") or  # Docstring
                            stripped.startswith('import ') or
                            stripped.startswith('from ')
                        )
                        
                        # Also check for web_interface.py specifically - it legitimately contains
                        # HTML templates in Python strings, so we need special handling
                        if filename == "web_interface.py":
                            # web_interface.py is a valid Python file with HTML in strings
                            # Just verify it has Python code structure
                            if 'def ' in content and ('import ' in content or '"""' in content):
                                log_info(f"Validated {filename} ({len(content)} bytes)", "OTA")
                                continue
                            else:
                                log_error(f"{filename} missing Python code structure", "OTA")
                                return False
                        
                        # For other Python files, check for imports
                        if filename not in ['config.py', 'secrets.py']:
                            if 'import' not in content and not has_python_indicator:
                                log_error(f"{filename} missing imports", "OTA")
                                return False

                    log_info(f"Validated {filename} ({len(content)} bytes)", "OTA")

                except OSError:
                    log_warn(f"Could not validate {filename}", "OTA")

            log_info("File validation completed", "OTA")
            return True

        except Exception as e:
            log_error(f"Validation failed: {e}", "OTA")
            return False

    def apply_update(self, version):
        """
        Apply the downloaded update to the device.
        Returns True on success, False on failure.
        On failure, automatically triggers rollback.
        """
        try:
            log_info(f"Applying update to {version}", "OTA")
            print(f"OTA: Applying update to version {version}...")

            # Step 1: Create backups of existing files
            if not self.create_backup(self.update_files):
                log_warn("Backup creation failed, proceeding anyway", "OTA")
                print("OTA: Warning - backup creation failed, proceeding anyway")

            # Step 2: Validate downloaded files
            if not self.validate_update_files():
                log_error("File validation failed, aborting update", "OTA")
                print("OTA: File validation FAILED - aborting update!")
                
                # Trigger rollback since validation failed
                log_info("Initiating rollback due to validation failure", "OTA")
                self.rollback_update()
                return False

            # Step 3: Apply updates with error handling
            updated_files = []
            errors = []
            for filename in self.update_files:
                temp_path = f"{self.temp_dir}/{filename}"
                try:
                    os.stat(temp_path)  # Check if file exists

                    # Copy file content
                    with open(temp_path, "r") as src:
                        content = src.read()
                    with open(filename, "w") as dst:
                        dst.write(content)

                    updated_files.append(filename)
                    log_info(f"Updated {filename}", "OTA")
                    print(f"OTA: Updated {filename}")
                except OSError as oe:
                    errors.append(f"{filename}: {oe}")
                    log_warn(f"Skipping missing {filename}: {oe}", "OTA")
                except Exception as e:
                    errors.append(f"{filename}: {e}")
                    log_error(f"Failed to update {filename}: {e}", "OTA")

            # Step 4: Update version only if files were updated
            if updated_files:
                self.set_current_version(version)
                log_info(f"Updated {len(updated_files)} files to version {version}", "OTA")
                print(f"OTA: Updated {len(updated_files)} files to version {version}")
            else:
                log_error("No files were updated", "OTA")
                print("OTA: ERROR - No files were updated!")
                
                # Trigger rollback
                log_info("Initiating rollback due to no files updated", "OTA")
                self.rollback_update()
                return False

            # Step 5: Clean temp directory
            try:
                for filename in os.listdir(self.temp_dir):
                    filepath = f"{self.temp_dir}/{filename}"
                    os.remove(filepath)
            except OSError:
                pass

            log_info(f"Update to {version} completed successfully", "OTA")
            print(f"OTA: Update to {version} completed successfully!")
            return True

        except Exception as e:
            log_error(f"Apply failed: {e}", "OTA")
            print(f"OTA: Apply FAILED - {e}")
            
            # Trigger rollback on any exception
            log_info("Initiating rollback due to exception", "OTA")
            self.rollback_update()
            return False

    def rollback_update(self):
        """Rollback to backup files if available."""
        try:
            log_info("Rolling back to backup files", "OTA")
            rollback_count = 0

            # Find and restore backup files
            for filename in os.listdir():
                if filename.endswith('.bak'):
                    original_name = filename[:-4]  # Remove .bak extension
                    try:
                        # Read backup content
                        with open(filename, "r") as src:
                            content = src.read()

                        # Restore original file
                        with open(original_name, "w") as dst:
                            dst.write(content)

                        rollback_count += 1
                        log_info(f"Restored {original_name} from backup", "OTA")

                    except Exception as e:
                        log_error(f"Failed to restore {original_name}: {e}", "OTA")

            if rollback_count > 0:
                log_info(f"Rollback completed: restored {rollback_count} files", "OTA")
                return True
            else:
                log_warn("No backup files found for rollback", "OTA")
                return False

        except Exception as e:
            log_error(f"Rollback failed: {e}", "OTA")
            return False

    def perform_update(self):
        try:
            # Create update flag FIRST - this survives reboot and signals rollback on failure
            self.create_update_flag()
            
            # Check for updates
            has_update, new_version, release_info = self.check_for_updates()

            if not has_update:
                log_info("No updates available", "OTA")
                self.clear_update_flag()  # Clear flag since no update happened
                return False

            log_info(f"Update available: {new_version}", "OTA")

            # Download update
            if not self.download_update(new_version):
                log_error("Download failed", "OTA")
                self.clear_update_flag()  # Clear flag since download failed
                return False

            # Apply update
            if not self.apply_update(new_version):
                log_error("Apply failed", "OTA")
                self.clear_update_flag()  # Clear flag since apply failed
                return False

            # Flag remains set - device will boot into new firmware
            # If boot fails, main.py will detect flag and rollback
            log_info("Update completed, preparing restart...", "OTA")
            
            # Create reboot marker before reset
            try:
                with open("ota_reboot_marker.txt", "w") as f:
                    import time
                    f.write(str(time.time()))
                log_info("OTA reboot marker created", "OTA")
            except Exception as e:
                log_warn(f"Could not create reboot marker: {e}", "OTA")
            
            gc.collect()
            time.sleep(1)  # Small delay to ensure filesystem operations complete
            machine.reset()

        except Exception as e:
            log_error(f"Update failed: {e}", "OTA")
            self.clear_update_flag()  # Clear flag on any exception
            return False

    def get_update_status(self):
        try:
            from device_config import get_ota_config
            ota_config = get_ota_config()
            ota_enabled = ota_config.get("enabled", True)
            auto_check = ota_config.get("auto_update", True)
        except Exception:
            ota_enabled = True
            auto_check = True

        return {
            "current_version": self.get_current_version(),
            "ota_enabled": ota_enabled,
            "auto_check": auto_check,
            "repo": f"{self.repo_owner}/{self.repo_name}",
            "branch": self.branch,
            "update_files": self.update_files
        }
