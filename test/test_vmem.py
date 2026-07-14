import os
import time
import pytest
from unittest.mock import patch, MagicMock
from src.chatybot.chatybot_app import ChatybotApp

class TestVmemMonitoring:
    @pytest.fixture
    def app(self):
        with patch('src.chatybot.chatybot_app.readline'):
            with patch('src.chatybot.chatybot_app.ConfigManager') as mock_cfg:
                cfg_instance = mock_cfg.return_value
                cfg_instance.config = {}
                cfg_instance.active_model_alias = "test_model"
                cfg_instance.system_message = "System"
                
                application = ChatybotApp()
                application.config_manager = cfg_instance
                yield application

    def test_vmem_defaults(self, app):
        assert app.vmem_monitor_active is False
        assert app.vmem_monitor_thread is None
        assert app.vmem_log_file is None

    @pytest.mark.anyio
    async def test_vmem_start_stop_status(self, app, tmp_path):
        # Change working dir in test to tmp_path to write log file there
        with patch('os.path.join', side_effect=lambda *args: os.path.join(tmp_path, args[-1]) if any("chatybot.vmem" in arg for arg in args) else os.path.join(*args)):
            with patch('builtins.print') as mock_print:
                # 1. Check status when OFF
                await app.handle_escape_command("/debug vmem status")
                printed = [call[0][0] for call in mock_print.call_args_list if call[0]]
                assert any("Active Monitoring: OFF" in line for line in printed)

                mock_print.reset_mock()

                # 2. Start monitoring
                # To prevent writing actual log file to current workspace, override log name
                await app.handle_escape_command("/debug vmem start")
                assert app.vmem_monitor_active is True
                assert app.vmem_monitor_thread is not None
                assert app.vmem_log_file is not None
                
                # Check log file exists or is created within a short delay
                log_path = app.vmem_log_file
                # Wait up to 1.5 seconds for log file creation and first write
                for _ in range(15):
                    if os.path.exists(log_path) and os.path.getsize(log_path) > 0:
                        break
                    time.sleep(0.1)
                
                assert os.path.exists(log_path)
                with open(log_path, "r") as f:
                    content = f.read()
                    print(f"DEBUG: log_path={log_path}, content={repr(content)}")
                    assert "Virtual Memory Monitoring Started" in content

                # 4. Check status when ON
                mock_print.reset_mock()
                await app.handle_escape_command("/debug vmem status")
                printed = [call[0][0] for call in mock_print.call_args_list if call[0]]
                assert any("Active Monitoring: ON" in line for line in printed)

                # 5. Stop monitoring
                mock_print.reset_mock()
                await app.handle_escape_command("/debug vmem stop")
                assert app.vmem_monitor_active is False

                # Cleanup the log file if created
                if os.path.exists(log_path):
                    os.remove(log_path)
