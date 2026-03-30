import pytest
import os
import json
import subprocess
from oracle_arm_manager.reporter import get_run_count, build_daily_report, send_daily_report

def test_get_run_count_success(mocker):
    mock_run = mocker.patch("subprocess.run")
    # Simulate list of runs
    mock_run.return_value.stdout = json.dumps([
        {"createdAt": "2030-01-01T00:00:00Z"},
        {"createdAt": "1990-01-01T00:00:00Z"}
    ])
    
    count = get_run_count("repo", "workflow", "2000-01-01T00:00:00Z")
    assert count == 1
    
def test_get_run_count_error(mocker, caplog):
    mocker.patch("subprocess.run", side_effect=Exception("gh CLI fail"))
    count = get_run_count("repo", "workflow", "2000-01-01T00:00:00Z")
    assert count == 0
    assert "gh CLI fail" in caplog.text

def test_build_daily_report(mocker):
    mocker.patch("os.getenv", side_effect=lambda k, d=None: "owner/repo" if k == "GITHUB_REPOSITORY" else d)
    mocker.patch("oracle_arm_manager.reporter.get_run_count", side_effect=[10, 5, 2])
    
    msg = build_daily_report()
    assert msg is not None
    assert "今日失敗嘗試：10" in msg
    assert "通知執行次數：5" in msg
    assert "通知失敗次數：2" in msg

def test_build_daily_report_no_repo(mocker, caplog):
    mocker.patch("os.getenv", return_value=None)
    msg = build_daily_report()
    assert msg is None
    assert "缺少 GITHUB_REPOSITORY" in caplog.text

def test_send_daily_report(mocker):
    mocker.patch("oracle_arm_manager.reporter.build_daily_report", return_value="Test Msg")
    mock_send = mocker.patch("oracle_arm_manager.reporter.send_notification")
    
    send_daily_report()
    mock_send.assert_called_once_with("每日監控回報", "Test Msg", is_success=True)
