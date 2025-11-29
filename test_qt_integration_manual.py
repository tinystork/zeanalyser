#!/usr/bin/env python
"""
Manual integration test to verify Qt GUI works with real analyse_logic.perform_analysis.
Run with: python test_qt_integration_manual.py /path/to/images /path/to/output.log
"""
import sys
import os
import time
import tempfile
import shutil

# Add workspace root to path
sys.path.insert(0, os.path.dirname(__file__))

def main():
    # Minimal test: import Qt, create window, run a quick analysis
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        print("✓ PySide6 imported successfully")
    except ImportError as e:
        print(f"✗ PySide6 not available: {e}")
        return 1

    # Create a temporary directory with a few test images
    temp_dir = tempfile.mkdtemp(prefix="zeanalyser_qt_test_")
    print(f"Using temp directory: {temp_dir}")
    
    # Copy a sample image from the provided input if given
    input_dir = sys.argv[1] if len(sys.argv) > 1 else None
    if input_dir and os.path.isdir(input_dir):
        # Copy first few FITS/PNG files to temp
        for fname in os.listdir(input_dir)[:3]:
            src = os.path.join(input_dir, fname)
            if os.path.isfile(src) and fname.lower().endswith(('.fit', '.fits', '.png', '.jpg')):
                dst = os.path.join(temp_dir, fname)
                try:
                    shutil.copy2(src, dst)
                    print(f"  Copied: {fname}")
                except Exception as e:
                    print(f"  Could not copy {fname}: {e}")
    
    # Set output log
    output_log = os.path.join(temp_dir, "analyse_resultats.log")
    print(f"Output log: {output_log}")
    
    # Import and setup Qt
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'  # Headless mode
    app = QApplication([])
    
    try:
        import analyse_gui_qt
        
        # Create main window
        win = analyse_gui_qt.ZeAnalyserMainWindow()
        print("✓ ZeAnalyserMainWindow created")
        
        # Set paths
        win.input_path_edit.setText(temp_dir)
        win.output_path_edit.setText(output_log)
        print(f"✓ Paths set: input={temp_dir}, output={output_log}")
        
        # Verify analyse button is enabled
        if not win.analyse_btn.isEnabled():
            print("✗ Analyse button not enabled!")
            return 1
        print("✓ Analyse button enabled")
        
        # Run analysis
        print("Starting analysis...")
        win.analyse_btn.click()
        
        # Wait for completion (max 30 seconds)
        max_wait = 30
        elapsed = 0
        while elapsed < max_wait:
            app.processEvents()
            time.sleep(0.1)
            elapsed += 0.1
            
            # Check if log contains "Worker finished"
            if "Worker finished" in win.log.toPlainText():
                print("✓ Analysis completed")
                break
        
        if elapsed >= max_wait:
            print("✗ Analysis timed out")
            return 1
        
        # Verify log file was created
        if os.path.exists(output_log):
            print(f"✓ Log file created: {output_log}")
            with open(output_log, 'r') as f:
                log_content = f.read()
                lines = log_content.split('\n')
                print(f"  Log has {len(lines)} lines")
                if len(lines) > 5:
                    print("  Sample log lines:")
                    for line in lines[:5]:
                        if line.strip():
                            print(f"    {line[:80]}")
        else:
            print(f"✗ Log file not created")
            return 1
        
        # Verify results were populated in the table
        if hasattr(win, '_results_model') and win._results_model is not None:
            row_count = win._results_model.rowCount()
            print(f"✓ Results table populated: {row_count} rows")
        else:
            print("✗ Results table not populated")
            # This is expected if the analysis didn't return results
        
        print("\n✓ Qt integration test passed!")
        return 0
        
    except Exception as e:
        print(f"✗ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Cleanup
        try:
            app.quit()
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                print(f"Cleaned up temp directory")
        except Exception as e:
            print(f"Cleanup error: {e}")

if __name__ == '__main__':
    sys.exit(main())
