import sys
import pyodbc
import time
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QLabel, QProgressBar, QPushButton, QSystemTrayIcon)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
import logging
from plyer import notification  # For cross-platform notifications

class DatabaseMonitorUI(QMainWindow):
    update_signal = pyqtSignal(bool, str, float)
    
    def __init__(self, server_name, database_name):
        super().__init__()
        self.server_name = server_name
        self.database_name = database_name
        self.session_start = None
        self.max_duration = 60 * 60  # 60 minutes
        self.notification_sent = False
        self.conn_str = (
            f'Driver={{SQL Server}};'
            f'Server={server_name};'
            f'Database={database_name};'
            'Trusted_Connection=yes;'
        )
        
        self.setup_ui()
        self.setup_monitoring()
        
        # Set up logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('db_monitor.log'),
                logging.StreamHandler()
            ]
        )
        
        # Create system tray icon
        self.setup_system_tray()

    def setup_ui(self):
        self.setWindowTitle("Database Activity Monitor")
        self.setFixedSize(600, 400)

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Add labels for information display
        self.server_label = QLabel(f"Server: {self.server_name}")
        self.database_label = QLabel(f"Database: {self.database_name}")
        self.status_label = QLabel("Waiting for database activity...")
        self.program_label = QLabel("Program: None")
        self.time_label = QLabel("Time Remaining: --:--:--")

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)

        # Add all widgets to layout
        layout.addWidget(self.server_label)
        layout.addWidget(self.database_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.program_label)
        layout.addWidget(self.time_label)
        layout.addWidget(self.progress_bar)

        # Add some styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QLabel {
                font-size: 14px;
                margin: 5px;
            }
            QProgressBar {
                text-align: center;
                border: 2px solid grey;
                border-radius: 5px;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)

    def setup_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon.fromTheme("applications-system"))  # Use system icon
        self.tray_icon.setVisible(True)
        self.tray_icon.setToolTip("Database Monitor")

    def setup_monitoring(self):
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.check_database_activity)
        self.monitor_timer.start(2000)  # Check every 2 seconds

    def send_notification(self, title, message):
        notification.notify(
            title=title,
            message=message,
            app_icon=None,  # e.g. 'C:\\icon_32x32.ico'
            timeout=10,  # seconds
        )

    def check_database_activity(self):
        try:
            with pyodbc.connect(self.conn_str, timeout=5) as conn:
                with conn.cursor() as cursor:
                    query = """
                    SELECT 
                        s.session_id,
                        s.program_name,
                        s.login_name,
                        s.host_name,
                        s.last_request_start_time
                    FROM sys.dm_exec_sessions s
                    WHERE s.database_id = DB_ID(?)
                        AND s.session_id != @@SPID
                        AND s.is_user_process = 1
                    """
                    
                    cursor.execute(query, (self.database_name,))
                    rows = cursor.fetchall()
                    
                    is_active = len(rows) > 0
                    program = rows[0].program_name if rows else "Unknown"
                    
                    self.update_ui(is_active, program)
                    
        except Exception as e:
            logging.error(f"Connection error: {str(e)}")
            self.status_label.setText(f"Error: {str(e)}")

    def update_ui(self, is_active, program):
        if is_active and not self.session_start:
            self.session_start = time.time()
            self.status_label.setText("Activity detected! Monitoring...")
            self.program_label.setText(f"Program: {program}")
            
        if self.session_start:
            current_time = time.time()
            elapsed = current_time - self.session_start
            remaining = self.max_duration - elapsed
            
            if remaining <= 0:
                self.session_start = None
                self.status_label.setText("Time's up! Session completed.")
                self.send_notification("Database Monitor", "Time's up! 60 minutes completed.")
                self.notification_sent = False
                return
            
            # Check for 5-minute warning
            if remaining <= 300 and not self.notification_sent:  # 5 minutes in seconds
                self.send_notification("Database Monitor", "5 minutes remaining!")
                self.notification_sent = True
            
            # Update progress bar and time label
            progress = (elapsed / self.max_duration) * 100
            self.progress_bar.setValue(int(progress))
            
            time_remaining = str(timedelta(seconds=int(remaining)))
            self.time_label.setText(f"Time Remaining: {time_remaining}")

def main():
    app = QApplication(sys.argv)
    SERVER_NAME = "ElarizTaghiyev\\SQLEXPRESS03"
    DATABASE_NAME = "train_test"
    
    window = DatabaseMonitorUI(SERVER_NAME, DATABASE_NAME)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
